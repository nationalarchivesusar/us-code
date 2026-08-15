#!/usr/bin/env python3
"""Build a static criminal-law API for the website and Roblox clients.

Inputs:
  legal-data/criminal-law/*.json
  usc/usc18.xml
Outputs:
  data/api/v1/criminal-law/*.json
  data/api/v1/criminal-law/title18/*.json
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "legal-data" / "criminal-law"
TITLE18 = ROOT / "usc" / "usc18.xml"
OUT = ROOT / "data" / "api" / "v1" / "criminal-law"
TITLE18_OUT = OUT / "title18"
PUBLIC_BASE = "https://nationalarchivesusar.github.io/us-code/"
API_BASE = f"{PUBLIC_BASE}data/api/v1/criminal-law/"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def compact_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def element_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return compact_text(" ".join(node.itertext()))


def direct_child(node: ET.Element, name: str) -> ET.Element | None:
    for child in list(node):
        if local_name(child.tag) == name:
            return child
    return None


def section_body_text(section: ET.Element) -> str:
    blocks: list[str] = []
    excluded = {"num", "heading", "sourceCredit", "notes", "note"}
    for child in list(section):
        if local_name(child.tag) in excluded:
            continue
        text = element_text(child)
        if text:
            blocks.append(text)
    return "\n".join(blocks)


def safe_filename(section: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]", "_", section)


def section_status(heading: str) -> str:
    lowered = heading.lower()
    if "repealed" in lowered:
        return "repealed"
    if "omitted" in lowered:
        return "omitted"
    if "transferred" in lowered:
        return "transferred"
    return "current"


def title18_sections(path: Path) -> list[dict]:
    tree = ET.parse(path)
    root = tree.getroot()
    sections: list[dict] = []

    def walk(node: ET.Element, part: dict | None = None, chapter: dict | None = None):
        kind = local_name(node.tag)
        next_part = part
        next_chapter = chapter
        if kind == "part":
            next_part = {
                "number": element_text(direct_child(node, "num")),
                "heading": element_text(direct_child(node, "heading")),
            }
        elif kind == "chapter":
            next_chapter = {
                "number": element_text(direct_child(node, "num")),
                "heading": element_text(direct_child(node, "heading")),
            }
        elif kind == "section":
            identifier = node.attrib.get("identifier", "")
            match = re.fullmatch(r"/us/usc/t18/s([^/]+)", identifier)
            if match:
                number = match.group(1)
                num_text = element_text(direct_child(node, "num"))
                heading = element_text(direct_child(node, "heading")) or f"Section {number}"
                body = section_body_text(node)
                part_number = (next_part or {}).get("number", "")
                status = section_status(heading)
                is_part_i = bool(re.search(r"\bI\b", part_number)) or (number.isdigit() and int(number) < 3000)
                charge_candidate = is_part_i and status == "current"
                sections.append({
                    "id": f"usc-18-{number}",
                    "source": "title18",
                    "title": "18",
                    "section": number,
                    "citation": f"18 U.S.C. § {number}",
                    "num": num_text,
                    "heading": heading,
                    "part": next_part,
                    "chapter": next_chapter,
                    "status": status,
                    "charge_candidate": charge_candidate,
                    "text": body,
                    "cite_url": f"{PUBLIC_BASE}cite/18/{number}/",
                    "web_url": f"{PUBLIC_BASE}criminal/title18/{number}/",
                })
        for child in list(node):
            walk(child, next_part, next_chapter)

    walk(root)
    unique = {}
    for item in sections:
        unique[item["section"]] = item
    return list(unique.values())


def code_payload(doc: dict, *, apply_integration: bool = False) -> dict:
    rules = doc.get("class_rules") or {}
    sections = []
    route_family = {
        "dc-criminal-code-federalized": "dc",
    }.get(doc["id"])
    for raw in doc.get("sections", []):
        text = raw.get("text", "")
        if apply_integration and raw.get("integration_append"):
            text = f"{text}\n{raw['integration_append']}".strip()
        cls = raw.get("offense_class")
        section = {
            "id": f"{doc['id']}-{raw['number']}",
            "source": doc["id"],
            "section": raw["number"],
            "citation": f"{doc['citation']} § {raw['number']}",
            "heading": raw.get("heading") or f"Section {raw['number']}",
            "chapter": raw.get("chapter"),
            "chapter_heading": raw.get("chapter_heading"),
            "offense_class": cls,
            "is_offense": bool(raw.get("is_offense")),
            "text": text,
        }
        if route_family:
            section["web_url"] = f"{PUBLIC_BASE}criminal/{route_family}/{raw['number']}/"
        if cls and cls in rules:
            section["class_rule"] = rules[cls]
        sections.append(section)
    return {
        "schema_version": "1.0",
        "id": doc["id"],
        "title": doc["title"],
        "citation": doc["citation"],
        "status": doc.get("status"),
        "source_date": doc.get("source_date"),
        "enacted_by": doc.get("enacted_by") or doc.get("adopted_by"),
        "integration_note": doc.get("integration_note"),
        "chapters": doc.get("chapters", []),
        "class_rules": rules,
        "sections": sections,
    }


def assert_fcc_offenses_are_duplicated(federal: dict, dc: dict) -> int:
    """Fail if the FCC ever gains an offense not represented in the D.C. code.

    The two enactments contain minor whitespace, numbering, and drafting
    variations. For catalog deduplication, a statute is the same offense when
    section number, normalized heading, and enacted A-G class all match.
    """
    def identities(payload: dict) -> set[tuple[str, str, str]]:
        return {
            (
                str(section["section"]),
                re.sub(r"[^a-z0-9]+", " ", section["heading"].lower()).strip(),
                str(section.get("offense_class") or ""),
            )
            for section in payload.get("sections", [])
            if section.get("is_offense") is True
        }

    federal_offenses = identities(federal)
    dc_offenses = identities(dc)
    unique_federal = sorted(federal_offenses - dc_offenses)
    if unique_federal:
        raise RuntimeError(
            "The Federal Criminal Code now contains offenses not duplicated in "
            f"the D.C. Criminal Code; reassess the API exclusion: {unique_federal}"
        )
    return len(federal_offenses)


def main() -> int:
    source_paths = sorted(SOURCE_DIR.glob("*.json"))
    docs = {}
    chapter_parts = {}
    for source_path in source_paths:
        payload = load_json(source_path)
        if payload.get("type") == "code-chapter":
            chapter_parts.setdefault(payload["parent_id"], []).extend(payload.get("sections", []))
            continue
        docs[payload["id"]] = payload
    for parent_id, sections in chapter_parts.items():
        if parent_id not in docs:
            raise RuntimeError(f"Code chapter data has no metadata document: {parent_id}")
        docs[parent_id]["sections"] = sorted(sections, key=lambda item: int(item["number"]))
    required = {"pl-36-260","dc-criminal-code-federalized","pl-37-261","federal-criminal-code-2025","pl-39-267"}
    missing = required - set(docs)
    if missing:
        raise RuntimeError(f"Missing criminal-law source documents: {sorted(missing)}")
    federal = code_payload(docs["federal-criminal-code-2025"])
    dc = code_payload(docs["dc-criminal-code-federalized"], apply_integration=True)
    duplicated_fcc_offenses = assert_fcc_offenses_are_duplicated(federal, dc)
    title18 = title18_sections(TITLE18)

    if OUT.exists():
        shutil.rmtree(OUT)
    TITLE18_OUT.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    digest = hashlib.sha256()
    for source_path in source_paths:
        digest.update(source_path.read_bytes())
    digest.update(TITLE18.read_bytes())
    source_hash = digest.hexdigest()

    title18_index_sections = []
    title18_search_entries = []
    title18_charge_entries = []
    for sec in title18:
        filename = f"{safe_filename(sec['section'])}.json"
        detail_url = f"{API_BASE}title18/{filename}"
        detail = {"schema_version":"1.0", "generated_at":generated_at, **sec}
        write_json(TITLE18_OUT / filename, detail)
        index_item = {k: sec[k] for k in ("id","section","citation","heading","part","chapter","status","charge_candidate","cite_url","web_url")}
        index_item["details_url"] = detail_url
        title18_index_sections.append(index_item)
        title18_search_entries.append({
            "id": sec["id"],
            "search_text": compact_text(" ".join([
                sec["citation"],
                sec["heading"],
                (sec.get("chapter") or {}).get("heading", ""),
                sec["text"],
            ])).lower(),
        })
        if sec["charge_candidate"]:
            title18_charge_entries.append({
                "id": sec["id"],
                "source": "title18",
                "citation": sec["citation"],
                "section": sec["section"],
                "label": sec["heading"],
                "status": sec["status"],
                "part": sec["part"],
                "chapter": sec["chapter"],
                "details_url": detail_url,
                "web_url": sec["web_url"],
                "cite_url": sec["cite_url"],
            })

    status_counts = {}
    for sec in title18:
        status_counts[sec["status"]] = status_counts.get(sec["status"], 0) + 1

    write_json(OUT / "title18-index.json", {
        "schema_version":"1.0",
        "generated_at":generated_at,
        "source":"18 U.S.C.",
        "title":"Crimes and Criminal Procedure",
        "counts":{"sections":len(title18_index_sections),"charge_candidates":len(title18_charge_entries),"by_status":status_counts},
        "sections":title18_index_sections,
    })
    write_json(OUT / "title18-search.json", {
        "schema_version":"1.0",
        "generated_at":generated_at,
        "count":len(title18_search_entries),
        "entries":title18_search_entries,
    })
    write_json(OUT / "dc-code.json", {"generated_at":generated_at, **dc})

    rsa = docs["pl-39-267"]
    write_json(OUT / "sentencing.json", {
        "schema_version":"1.0",
        "generated_at":generated_at,
        "source":rsa["citation"],
        "title":rsa["title"],
        "status":rsa.get("status"),
        "rules":rsa.get("sentencing_rules", {}),
        "sections":rsa.get("sections", []),
        "dc_code_class_rules":dc["class_rules"],
        "note":"Public Law 39-267 governs non-court-imposed sentencing, but its felony/misdemeanor class scheme is not expressly cross-walked in the supplied text to the A–G offense classes used by the federalized D.C. Criminal Code. The API therefore exposes both rules without inventing a mapping.",
    })

    public_law_docs = []
    for doc_id in ("pl-36-260","pl-37-261","pl-39-267"):
        doc = docs[doc_id]
        law_number = doc["citation"].replace("Public Law ", "")
        sections = []
        for section in doc.get("sections", []):
            item = dict(section)
            item["web_url"] = f"{PUBLIC_BASE}criminal/public-law/{law_number}/{section['number']}/"
            sections.append(item)
        public_law_docs.append({
            "id":doc["id"], "citation":doc["citation"], "title":doc["title"],
            "status":doc.get("status"), "source_date":doc.get("source_date"),
            "sections":sections,
            "public_law_url":f"{PUBLIC_BASE}public-laws.html#pl-{law_number}",
            "permanent_index_url":f"{PUBLIC_BASE}criminal/public-law/{law_number}/",
        })
    write_json(OUT / "documents.json", {
        "schema_version":"1.0","generated_at":generated_at,"documents":public_law_docs,
    })

    charges = title18_charge_entries
    write_json(OUT / "charges.json", {
        "schema_version":"1.0",
        "generated_at":generated_at,
        "revision":source_hash[:16],
        "default_local_code":"dc-criminal-code-federalized",
        "sentencing_overlay":"Public Law 39-267",
        "sentencing_crosswalk_status":"not_expressly_defined",
        "counts":{"total":len(charges),"dc_code":0,"title18":len(title18_charge_entries)},
        "excluded_sources":[{
            "id":"federal-criminal-code-2025",
            "citation":"Public Law 37-261 § 4",
            "reason":f"Omitted from the booking API to avoid duplicating all {duplicated_fcc_offenses} FCC offenses already represented by the federalized D.C. Criminal Code.",
        }],
        "charges":charges,
    })

    write_json(OUT / "manifest.json", {
        "schema_version":"1.0",
        "generated_at":generated_at,
        "revision":source_hash[:16],
        "site_url":PUBLIC_BASE,
        "permanent_index_url":f"{PUBLIC_BASE}criminal/",
        "api_base":API_BASE,
        "endpoints":{
            "charges":"charges.json",
            "dc_code":"dc-code.json",
            "title18_index":"title18-index.json",
            "title18_search":"title18-search.json",
            "title18_section":"title18/{section}.json",
            "sentencing":"sentencing.json",
            "source_documents":"documents.json",
        },
        "sources":[
            {"id":"title18","citation":"18 U.S.C.","status":"current sections only are included in the booking charge catalog"},
            {"id":"dc-criminal-code-federalized","citation":"Public Law 36-260 § 10(b)","status":"federalized source"},
            {"id":"sentencing","citation":"Public Law 39-267","status":"current"},
        ],
        "excluded_sources":[{
            "id":"federal-criminal-code-2025",
            "citation":"Public Law 37-261 § 4",
            "reason":f"Not published as an API endpoint or charge source because its {duplicated_fcc_offenses} offenses duplicate the federalized D.C. Criminal Code by section, offense heading, and class. The enacted source remains preserved outside the API.",
        }],
        "roblox":{
            "recommended_startup_endpoint":"charges.json",
            "cache_strategy":"Cache the manifest revision and charges catalog server-side; use each charge's absolute details_url when full statutory text is requested.",
            "browser_only_endpoint":"title18-search.json is intended for full-text website search and normally should not be downloaded by Roblox clients.",
        },
    })

    print(
        "Built criminal-law API: FCC omitted as a fully duplicated offense set "
        f"({duplicated_fcc_offenses} offenses); {len(title18_index_sections)} Title 18 "
        f"sections, {len(title18_charge_entries)} current Title 18 charge candidates."
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
