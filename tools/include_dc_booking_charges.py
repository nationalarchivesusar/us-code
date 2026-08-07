#!/usr/bin/env python3
"""Include the federalized D.C. Criminal Code in the compact booking catalog.

Public Law 36-260 § 10(b) adopted the D.C. Criminal Code as federal law and
§ 10(e) keeps adopted municipal laws in force until amended or repealed by
Congress. The supplied Public Law 37-261 establishes an additional Federal
Criminal Code but does not expressly repeal the PL 36-260 adoption. The
booking API therefore exposes both local-code sources instead of silently
choosing one and hiding the other.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "api" / "v1" / "criminal-law"
PUBLIC_API = "https://nationalarchivesusar.github.io/us-code/data/api/v1/criminal-law/"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> int:
    charges_path = BASE / "charges.json"
    dc_path = BASE / "dc-code.json"
    manifest_path = BASE / "manifest.json"

    charges = load(charges_path)
    dc = load(dc_path)
    manifest = load(manifest_path)

    federal_entries = [
        item for item in charges.get("charges", [])
        if item.get("source") == "federal-criminal-code-2025"
    ]
    title18_entries = [
        item for item in charges.get("charges", [])
        if item.get("source") == "title18"
    ]

    dc_entries = []
    for sec in dc.get("sections", []):
        if not sec.get("is_offense"):
            continue
        dc_entries.append({
            "id": sec["id"],
            "source": "dc-criminal-code-federalized",
            "citation": f"D.C. Criminal Code § {sec['section']}",
            "formal_citation": sec["citation"],
            "section": sec["section"],
            "label": sec["heading"],
            "status": "current",
            "offense_class": sec.get("offense_class"),
            "class_rule": sec.get("class_rule"),
            "chapter": sec.get("chapter"),
            "chapter_heading": sec.get("chapter_heading"),
            "details_url": f"{PUBLIC_API}dc-code.json",
            "web_url": sec["web_url"],
            "anchor": f"dcc-{sec['section']}",
            "legal_basis": "Public Law 36-260 § 10(b), subject to § 10(e)",
        })

    combined = federal_entries + dc_entries + title18_entries
    charges["charges"] = combined
    charges["counts"] = {
        "total": len(combined),
        "federal_code": len(federal_entries),
        "dc_code": len(dc_entries),
        "title18": len(title18_entries),
    }
    charges["available_local_codes"] = [
        "federal-criminal-code-2025",
        "dc-criminal-code-federalized",
    ]
    charges["local_code_status_note"] = (
        "Public Law 36-260 § 10(b) adopted the D.C. Criminal Code as federal law, "
        "and § 10(e) provides that adopted municipal laws remain in force until "
        "amended or repealed by Congress. The supplied Public Law 37-261 establishes "
        "a Federal Criminal Code but contains no express repeal of that adoption, so "
        "both local-code offense sets are exposed to clients."
    )
    write(charges_path, charges)

    for source in manifest.get("sources", []):
        if source.get("id") == "dc-criminal-code-federalized":
            source["status"] = (
                "current federalized law under Public Law 36-260 § 10(b), "
                "subject to the safeguard in § 10(e)"
            )
    manifest.setdefault("roblox", {})["booking_catalog_sources"] = [
        "18 U.S.C. current Part I charge candidates",
        "Federal Criminal Code enacted by Public Law 37-261",
        "D.C. Criminal Code federalized by Public Law 36-260",
    ]
    manifest["roblox"]["local_code_note"] = charges["local_code_status_note"]
    write(manifest_path, manifest)

    print(
        "Booking catalog includes "
        f"{len(federal_entries)} FCC offenses, {len(dc_entries)} federalized D.C. offenses, "
        f"and {len(title18_entries)} Title 18 charge candidates."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
