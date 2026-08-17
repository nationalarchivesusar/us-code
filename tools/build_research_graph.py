#!/usr/bin/env python3
"""Build a current U.S. Code cross-reference graph from USLM XML.

The graph is intentionally descriptive rather than interpretive: an edge means
that the source section contains a USLM reference whose href resolves to another
U.S. Code section. It does not infer citations from ordinary prose.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
USC_DIR = ROOT / "usc"
OUTPUT = ROOT / "data" / "research" / "references.json"
USLM = "http://xml.house.gov/schemas/uslm/1.0"
Q = lambda name: f"{{{USLM}}}{name}"

SECTION_RE = re.compile(r"^/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/#?]+)", re.I)
HREF_RE = re.compile(r"(?:^|/)us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/#?]+)", re.I)


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def key(title: str, section: str) -> str:
    return f"{title.lower()}:{section.lower()}"


def direct_text(element, name: str) -> str:
    child = element.find(Q(name))
    return clean("".join(child.itertext())) if child is not None else ""


def section_identity(section) -> tuple[str, str] | None:
    identifier = section.get("identifier") or ""
    match = SECTION_RE.match(identifier)
    if not match:
        return None
    title = match.group("title").lstrip("0") or "0"
    return title, match.group("section")


def parse_target(href: str) -> tuple[str, str] | None:
    match = HREF_RE.search(href or "")
    if not match:
        return None
    title = match.group("title").lstrip("0") or "0"
    return title, match.group("section")


def title_sort(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d+)([A-Za-z]?)", value)
    return (int(match.group(1)), match.group(2).lower()) if match else (10**9, value.lower())


def citation(title: str, section: str) -> str:
    return f"{title} U.S.C. § {section}"


def build() -> dict:
    metadata: dict[str, dict] = {}
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    source_files = 0

    parser = etree.XMLParser(huge_tree=True, recover=False, resolve_entities=False)
    for path in sorted(USC_DIR.glob("usc*.xml")):
        raw = path.read_bytes()
        if raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise RuntimeError(f"Git LFS source is not materialized: {path.relative_to(ROOT)}")
        root = etree.fromstring(raw, parser=parser)
        source_files += 1

        for section in root.xpath("//*[local-name()='section'][@identifier]"):
            identity = section_identity(section)
            if not identity:
                continue
            title, number = identity
            source_key = key(title, number)
            metadata.setdefault(
                source_key,
                {
                    "title": title,
                    "section": number,
                    "citation": citation(title, number),
                    "heading": direct_text(section, "heading"),
                },
            )

            for ref in section.xpath(".//*[local-name()='ref'][@href]"):
                target = parse_target(ref.get("href") or "")
                if not target:
                    continue
                target_title, target_section = target
                target_key = key(target_title, target_section)
                if target_key == source_key:
                    continue
                outgoing[source_key].add(target_key)
                incoming[target_key].add(source_key)
                metadata.setdefault(
                    target_key,
                    {
                        "title": target_title,
                        "section": target_section,
                        "citation": citation(target_title, target_section),
                        "heading": "",
                    },
                )

    def edge_record(item_key: str) -> dict:
        record = metadata[item_key]
        return {
            "title": record["title"],
            "section": record["section"],
            "citation": record["citation"],
            "heading": record.get("heading") or "",
            "url": f"cite/{record['title']}/{record['section']}/",
        }

    sections: dict[str, dict] = {}
    all_keys = set(outgoing) | set(incoming)
    for item_key in sorted(all_keys):
        record = metadata[item_key]
        references = [edge_record(k) for k in sorted(outgoing.get(item_key, set()))]
        cited_by = [edge_record(k) for k in sorted(incoming.get(item_key, set()))]
        sections[item_key] = {
            "title": record["title"],
            "section": record["section"],
            "citation": record["citation"],
            "heading": record.get("heading") or "",
            "references": references,
            "cited_by": cited_by,
        }

    edge_count = sum(len(values) for values in outgoing.values())
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "method": "USLM ref[href] section-to-section links only",
        "counts": {
            "source_xml_files": source_files,
            "sections_with_relationships": len(sections),
            "directed_references": edge_count,
        },
        "sections": sections,
        "limitations": [
            "Only explicit USLM ref elements resolving to U.S. Code section identifiers are included.",
            "Plain-text citations that are not encoded as USLM references are not inferred.",
            "A reference edge does not imply endorsement, incorporation, or judicial interpretation.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> int:
    payload = build()
    counts = payload["counts"]
    print(
        f"Built statutory reference graph: {counts['sections_with_relationships']} sections, "
        f"{counts['directed_references']} directed references."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
