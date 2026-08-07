#!/usr/bin/env python3
"""Finalize the compact criminal booking catalog for Roblox clients.

Public Law 36-260 § 10(b) adopted the D.C. Criminal Code as federal law and
§ 10(e) keeps adopted municipal laws in force until amended or repealed by
Congress. The supplied Public Law 37-261 establishes an additional Federal
Criminal Code but does not expressly repeal the PL 36-260 adoption. The
booking API therefore exposes both local-code sources instead of silently
choosing one and hiding the other.

This pass also adds explicit sentencing-mode metadata so game clients never
have to infer whether an offense can be sentenced automatically. FCC and
federalized D.C. offenses use their authoritative A-G class_rule metadata;
Title 18 remains manual unless later API data supplies an in-game rule.
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


def apply_class_sentencing(entry: dict) -> None:
    rule = entry.get("class_rule") or {}
    minimum = rule.get("initial_min_minutes")
    maximum = rule.get("initial_max_minutes")
    if isinstance(minimum, (int, float)) and isinstance(maximum, (int, float)):
        entry["sentencing_mode"] = "automatic_class_rule"
        entry["sentencing_range_minutes"] = {
            "min": minimum,
            "max": maximum,
        }
        # This is a booking-system suggestion, not a new legal rule. The game
        # may display the range, while the server uses the lawful maximum as
        # its default computed contribution unless its booking policy changes.
        entry["suggested_minutes"] = maximum
    else:
        entry["sentencing_mode"] = "manual_required"
        entry["sentencing_reason"] = "No authoritative in-game class rule is attached to this catalog entry."


def main() -> int:
    charges_path = BASE / "charges.json"
    dc_path = BASE / "dc-code.json"
    sentencing_path = BASE / "sentencing.json"
    manifest_path = BASE / "manifest.json"

    charges = load(charges_path)
    dc = load(dc_path)
    sentencing = load(sentencing_path)
    manifest = load(manifest_path)

    federal_entries = [
        item for item in charges.get("charges", [])
        if item.get("source") == "federal-criminal-code-2025"
    ]
    title18_entries = [
        item for item in charges.get("charges", [])
        if item.get("source") == "title18"
    ]

    for entry in federal_entries:
        apply_class_sentencing(entry)

    for entry in title18_entries:
        entry["sentencing_mode"] = "manual_required"
        entry["sentencing_reason"] = (
            "No authoritative USAR in-game sentencing classification is attached "
            "to this Title 18 section."
        )

    dc_entries = []
    for sec in dc.get("sections", []):
        if not sec.get("is_offense"):
            continue
        entry = {
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
        }
        apply_class_sentencing(entry)
        dc_entries.append(entry)

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

    sentencing_rules = sentencing.get("rules") or {}
    multi_charge_cap = sentencing_rules.get("multi_charge_max_minutes")
    charges["sentencing_policy"] = {
        "non_court_scope": sentencing_rules.get("scope"),
        "multi_charge_max_minutes": multi_charge_cap,
        "automatic_sources": [
            "federal-criminal-code-2025",
            "dc-criminal-code-federalized",
        ],
        "manual_sources": ["title18"],
        "class_crosswalk_status": sentencing_rules.get("crosswalk_status"),
        "automatic_rule": (
            "Use each selected offense's class_rule initial range. The catalog exposes "
            "suggested_minutes as that offense's initial_max_minutes for booking UI calculation."
        ),
        "title18_rule": (
            "Manual sentence required unless a future API revision supplies authoritative "
            "USAR in-game sentencing metadata. The server must still apply the non-court cap."
        ),
    }
    write(charges_path, charges)

    for source in manifest.get("sources", []):
        if source.get("id") == "dc-criminal-code-federalized":
            source["status"] = (
                "current federalized law under Public Law 36-260 § 10(b), "
                "subject to the safeguard in § 10(e)"
            )
    roblox = manifest.setdefault("roblox", {})
    roblox["booking_catalog_sources"] = [
        "18 U.S.C. current Part I charge candidates",
        "Federal Criminal Code enacted by Public Law 37-261",
        "D.C. Criminal Code federalized by Public Law 36-260",
    ]
    roblox["local_code_note"] = charges["local_code_status_note"]
    roblox["multi_charge_max_minutes"] = multi_charge_cap
    roblox["automatic_sentencing_sources"] = charges["sentencing_policy"]["automatic_sources"]
    roblox["manual_sentencing_sources"] = charges["sentencing_policy"]["manual_sources"]
    roblox["sentencing_policy"] = "Read charges.json sentencing_policy and per-charge sentencing_mode; never infer a missing class mapping client-side."
    write(manifest_path, manifest)

    print(
        "Booking catalog includes "
        f"{len(federal_entries)} FCC offenses, {len(dc_entries)} federalized D.C. offenses, "
        f"and {len(title18_entries)} Title 18 charge candidates; "
        f"multi-charge cap={multi_charge_cap!r} minutes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
