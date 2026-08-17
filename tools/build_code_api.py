#!/usr/bin/env python3
"""Build a public, read-only U.S. Code API under data/api/v1/code/.

This namespace is intentionally separate from data/api/v1/criminal-law/ so the
existing Roblox criminal-law contract remains untouched.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
USC_DIR = ROOT / "usc"
OUTPUT = ROOT / "data" / "api" / "v1" / "code"
WEB_BASE = "https://nationalarchivesusar.github.io/us-code/"
API_BASE = WEB_BASE + "data/api/v1/code/"
USLM = "http://xml.house.gov/schemas/uslm/1.0"
Q = lambda name: f"{{{USLM}}}{name}"
SECTION_RE = re.compile(r"^/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/]+)$", re.I)
SKIP_BODY = {"num", "heading", "sourceCredit", "notes", "toc"}


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def direct_text(element, name: str) -> str:
    child = element.find(Q(name))
    return clean("".join(child.itertext())) if child is not None else ""


def flatten_body(section) -> str:
    pieces: list[str] = []
    for child in section:
        local = etree.QName(child).localname
        if local in SKIP_BODY:
            continue
        text = clean("".join(child.itertext()))
        if text:
            pieces.append(text)
    return "\n\n".join(pieces)


def source_credit(section) -> str:
    return direct_text(section, "sourceCredit")


def section_identity(section) -> tuple[str, str] | None:
    match = SECTION_RE.fullmatch(section.get("identifier") or "")
    if not match:
        return None
    title = match.group("title").lstrip("0") or "0"
    return title, match.group("section")


def safe_filename(section: str) -> str:
    if "/" in section or "\\" in section or section in {".", ".."}:
        raise ValueError(f"Unsafe section identifier: {section!r}")
    return section


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def title_key(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d+)([A-Za-z]?)", value)
    return (int(match.group(1)), match.group(2).lower()) if match else (10**9, value.lower())


def build() -> dict:
    shutil.rmtree(OUTPUT, ignore_errors=True)
    (OUTPUT / "sections").mkdir(parents=True, exist_ok=True)
    (OUTPUT / "titles").mkdir(parents=True, exist_ok=True)

    parser = etree.XMLParser(huge_tree=True, recover=False, resolve_entities=False)
    title_manifests: list[dict] = []
    total_sections = 0

    for path in sorted(USC_DIR.glob("usc*.xml")):
        raw = path.read_bytes()
        if raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise RuntimeError(f"Git LFS source is not materialized: {path.relative_to(ROOT)}")
        root = etree.fromstring(raw, parser=parser)
        title_records: list[dict] = []
        title_number = None

        for section in root.xpath("//*[local-name()='section'][@identifier]"):
            identity = section_identity(section)
            if not identity:
                continue
            title, number = identity
            title_number = title_number or title
            number = safe_filename(number)
            heading = direct_text(section, "heading")
            body = flatten_body(section)
            credit = source_credit(section)
            citation = f"{title} U.S.C. § {number}"
            text = f"§ {number}. {heading}".strip()
            if body:
                text += f"\n\n{body}"
            relative = Path("sections") / title / f"{number}.json"
            destination = OUTPUT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)

            record = {
                "schema_version": "1.0",
                "title": title,
                "section": number,
                "citation": citation,
                "heading": heading,
                "body": body,
                "text": text,
                "source_credit": credit,
                "identifier": section.get("identifier") or "",
                "source_xml": f"usc/{path.name}",
                "web_url": WEB_BASE + f"cite/{title}/{number}/",
                "api_url": API_BASE + relative.as_posix(),
                "sha256": sha256(text),
            }
            destination.write_text(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            title_records.append(
                {
                    "section": number,
                    "citation": citation,
                    "heading": heading,
                    "web_url": record["web_url"],
                    "api_url": record["api_url"],
                    "sha256": record["sha256"],
                }
            )

        if not title_number:
            continue
        title_records.sort(key=lambda item: item["section"].lower())
        title_payload = {
            "schema_version": "1.0",
            "title": title_number,
            "count": len(title_records),
            "sections": title_records,
        }
        title_path = OUTPUT / "titles" / f"{title_number}.json"
        title_path.write_text(
            json.dumps(title_payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        total_sections += len(title_records)
        title_manifests.append(
            {
                "title": title_number,
                "count": len(title_records),
                "index_url": API_BASE + f"titles/{title_number}.json",
                "source_xml": f"usc/{path.name}",
            }
        )

    title_manifests.sort(key=lambda item: title_key(item["title"]))
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "api_base": API_BASE,
        "web_base": WEB_BASE,
        "description": "Read-only current U.S. Code section API for USAR legal research.",
        "counts": {"titles": len(title_manifests), "sections": total_sections},
        "routes": {
            "manifest": API_BASE + "manifest.json",
            "title_index": API_BASE + "titles/{title}.json",
            "section": API_BASE + "sections/{title}/{section}.json",
        },
        "titles": title_manifests,
        "compatibility": {
            "criminal_law_api_unchanged": True,
            "criminal_law_namespace": WEB_BASE + "data/api/v1/criminal-law/",
        },
        "notes": [
            "This API publishes current codified text, not historical intermediate versions.",
            "Section text excludes statutory notes and table-of-contents material; source_credit is provided separately.",
            "Consumers should treat sha256 as a text-version verifier, not a legal authentication signature.",
        ],
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    manifest = build()
    print(
        f"Built general Code API: {manifest['counts']['titles']} titles, "
        f"{manifest['counts']['sections']} sections."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
