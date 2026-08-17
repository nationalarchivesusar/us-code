#!/usr/bin/env python3
"""Build a verified U.S. Code statutory reference / cited-by graph from USLM refs."""

from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
USC_DIR = ROOT / "usc"
OUTPUT_DIR = ROOT / "data" / "references"
SCHEMA_VERSION = "1.0"
USLM = "http://xml.house.gov/schemas/uslm/1.0"
Q = lambda name: f"{{{USLM}}}{name}"
SECTION_RE = re.compile(r"^/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/]+)$", re.I)
REF_RE = re.compile(r"/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/#?]+)", re.I)


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def section_key(title: str, section: str) -> str:
    return f"{title.lower()}:{section.lower()}"


def direct_text(element, name: str) -> str:
    child = element.find(Q(name))
    return clean("".join(child.itertext())) if child is not None else ""


def iter_section_metadata(path: Path):
    context = etree.iterparse(str(path), events=("end",), tag=Q("section"), huge_tree=True)
    for _, element in context:
        identifier = element.get("identifier", "")
        match = SECTION_RE.fullmatch(identifier)
        if match:
            title = match.group("title").lstrip("0") or "0"
            section = match.group("section")
            yield {
                "title": title,
                "section": section,
                "identifier": identifier,
                "citation": f"{title} U.S.C. § {section}",
                "heading": direct_text(element, "heading"),
            }
        element.clear()
        while element.getprevious() is not None:
            del element.getparent()[0]


def build_section_index() -> dict[str, dict]:
    index: dict[str, dict] = {}
    for path in sorted(USC_DIR.glob("usc*.xml")):
        for record in iter_section_metadata(path):
            index[section_key(record["title"], record["section"])] = record
    return index


def iter_section_refs(path: Path):
    context = etree.iterparse(str(path), events=("end",), tag=Q("section"), huge_tree=True)
    for _, element in context:
        identifier = element.get("identifier", "")
        match = SECTION_RE.fullmatch(identifier)
        if match:
            title = match.group("title").lstrip("0") or "0"
            section = match.group("section")
            refs: set[tuple[str, str]] = set()
            for ref in element.iter(Q("ref")):
                href = ref.get("href") or ref.get("identifier") or ""
                target = REF_RE.search(href)
                if not target:
                    continue
                refs.add((target.group("title").lstrip("0") or "0", target.group("section")))
            yield title, section, refs
        element.clear()
        while element.getprevious() is not None:
            del element.getparent()[0]


def build(output_dir: Path = OUTPUT_DIR) -> dict:
    section_index = build_section_index()
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)

    for path in sorted(USC_DIR.glob("usc*.xml")):
        for title, section, refs in iter_section_refs(path):
            source_key = section_key(title, section)
            if source_key not in section_index:
                continue
            for target_title, target_section in refs:
                target_key = section_key(target_title, target_section)
                if target_key not in section_index or target_key == source_key:
                    continue
                outgoing[source_key].add(target_key)
                incoming[target_key].add(source_key)

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_sections: dict[str, dict] = {}
    edge_count = 0

    for key, meta in sorted(section_index.items()):
        references = [section_index[item] for item in sorted(outgoing.get(key, set()))]
        cited_by = [section_index[item] for item in sorted(incoming.get(key, set()))]
        if not references and not cited_by:
            continue
        edge_count += len(references)
        relative_path = Path("data") / "references" / meta["title"].lower() / f"{meta['section']}.json"
        destination = ROOT / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "title": meta["title"],
            "section": meta["section"],
            "citation": meta["citation"],
            "heading": meta["heading"],
            "references": references,
            "cited_by": cited_by,
            "evidence": "USLM ref href/identifier links only",
        }
        destination.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        manifest_sections[key] = {
            "title": meta["title"],
            "section": meta["section"],
            "citation": meta["citation"],
            "references": len(references),
            "cited_by": len(cited_by),
            "path": relative_path.as_posix(),
        }

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence": "Verified explicit USLM statutory references; no fuzzy text matching.",
        "counts": {
            "indexed_sections": len(section_index),
            "connected_sections": len(manifest_sections),
            "directed_reference_edges": edge_count,
        },
        "sections": manifest_sections,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    manifest = build()
    counts = manifest["counts"]
    print(f"Built statutory reference graph: {counts['connected_sections']} connected sections, {counts['directed_reference_edges']} verified edges.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
