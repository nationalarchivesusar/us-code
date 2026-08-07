#!/usr/bin/env python3
"""Fail-closed hardening for the Roblox-facing criminal-law API.

This post-build pass enforces two rules:
1. Platform-restricted content is removed wholesale from charge/detail/search
   output. Supporting metadata is scrubbed fail-closed.
2. Only positively identified criminal charges are displayable.

FCC and federalized D.C. entries must be explicitly marked is_offense=true.
Title 18 is intentionally stricter: only current Part I sections with both
actor language and direct criminal-punishment language survive, and obvious
administrative/definition/procedure headings are excluded. False negatives are
preferred to false positives.

The pass ends with a recursive audit of every generated API JSON file. Any
surviving blocked reference or non-charge display record fails the build.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "api" / "v1" / "criminal-law"
TITLE18_DIR = BASE / "title18"

# Intentionally broad. False positives remove an entry from the Roblox API but
# do not alter the legal source material elsewhere in the repository.
BLOCKED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("protected-youth", re.compile(
        r"\b(?:minor|minor's|minors|child|children|juvenile|juveniles|underage|infant|youth)\b"
        r"|\bunder\s+(?:the\s+)?age\s+of\b"
        r"|\bunder\s+(?:sixteen|seventeen|eighteen|16|17|18)\b",
        re.I,
    )),
    ("adult-content", re.compile(
        r"\b(?:sex|sexual|sexually|rape|raped|raping|sodomy|prostitut(?:e|ion)|"
        r"porn(?:ography|ographic)?|obscene|obscenity|lewd|indecent|genital|"
        r"intercourse|molest(?:ation|ed|ing)?|erotic|nudity|nude|naked)\b",
        re.I,
    )),
    ("controlled-substances", re.compile(
        r"\b(?:drug|drugs|drugged|drugging|narcotic|narcotics|controlled\s+substance|"
        r"controlled\s+substances|marijuana|cannabis|cocaine|heroin|methamphetamine|"
        r"meth|fentanyl|opioid|opioids|opiate|opiates|lsd|pcp|ecstasy|mdma)\b",
        re.I,
    )),
    ("regulated-intoxicants", re.compile(
        r"\b(?:alcohol|alcoholic|liquor|beer|wine|tobacco|cigarette|cigarettes|"
        r"cigar|cigars|nicotine|vape|vaping|vapor\s+product)\b",
        re.I,
    )),
    ("gambling", re.compile(
        r"\b(?:gambling|gamble|wager|wagering|betting|bookmaking|lottery|lotteries)\b",
        re.I,
    )),
    ("self-injury", re.compile(
        r"\b(?:suicide|suicidal|self[- ]?harm|self[- ]?injur(?:y|ies|ious))\b",
        re.I,
    )),
)

NON_CHARGE_HEADING = re.compile(
    r"\b(?:definitions?|definition of terms|rules?|regulations?|reports?|annual report|"
    r"construction|applicability|effective dates?|jurisdiction|venue|limitations?|"
    r"limitation of actions|procedures?|administrative|authorization|appropriations?|"
    r"duties|powers|establishment|findings|severability|preemption|exceptions?|"
    r"immunity|disclosure|records?|civil remedies?|injunctions?|forfeiture|restitution|"
    r"sentencing|penalties|penalty|definitions and rules|use of certain terms)\b",
    re.I,
)

TITLE18_ACTOR_PATTERNS = (
    re.compile(r"\bwhoever\b", re.I),
    re.compile(r"\bany\s+person\s+who\b", re.I),
    re.compile(r"\ba\s+person\s+who\b", re.I),
    re.compile(r"\bit\s+shall\s+be\s+unlawful\s+for\b", re.I),
)
TITLE18_PENALTY_PATTERNS = (
    re.compile(r"\bshall\s+be\s+fined\b", re.I),
    re.compile(r"\bshall\s+be\s+imprisoned\b", re.I),
    re.compile(r"\bshall\s+be\s+punished\b", re.I),
    re.compile(r"\bis\s+guilty\s+of\b", re.I),
    re.compile(
        r"\bshall\s+be\s+subject\s+to\b.{0,120}\b(?:fine|imprisonment)\b",
        re.I | re.S,
    ),
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def blocked_reason(value: Any) -> str | None:
    for text in iter_strings(value):
        for label, pattern in BLOCKED_PATTERNS:
            if pattern.search(text):
                return label
    return None


def is_safe(value: Any) -> bool:
    return blocked_reason(value) is None


def strict_title18_charge(detail: dict) -> bool:
    """Positive, fail-closed classification for a displayable Title 18 charge."""
    if detail.get("status") != "current" or not detail.get("charge_candidate"):
        return False
    if not is_safe(detail):
        return False

    heading = str(detail.get("heading") or "")
    body = str(detail.get("text") or "")
    if not body.strip() or NON_CHARGE_HEADING.search(heading):
        return False

    return (
        any(pattern.search(body) for pattern in TITLE18_ACTOR_PATTERNS)
        and any(pattern.search(body) for pattern in TITLE18_PENALTY_PATTERNS)
    )


def sanitize_supporting_value(value: Any) -> Any:
    """Scrub blocked strings from non-charge supporting metadata."""
    if isinstance(value, str):
        return "[PLATFORM-RESTRICTED CONTENT REMOVED]" if blocked_reason(value) else value
    if isinstance(value, list):
        return [sanitize_supporting_value(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_supporting_value(item) for key, item in value.items()}
    return value


def harden() -> None:
    required = (
        "charges.json",
        "federal-code.json",
        "dc-code.json",
        "title18-index.json",
        "title18-search.json",
        "manifest.json",
        "sentencing.json",
        "documents.json",
    )
    missing = [name for name in required if not (BASE / name).is_file()]
    if missing:
        raise RuntimeError(f"Cannot harden missing API files: {missing}")

    federal = load(BASE / "federal-code.json")
    dc = load(BASE / "dc-code.json")
    title18_index = load(BASE / "title18-index.json")
    title18_search = load(BASE / "title18-search.json")
    charges = load(BASE / "charges.json")
    manifest = load(BASE / "manifest.json")

    # Local-code detail endpoints become charge-only.
    federal_sections = [
        sec for sec in federal.get("sections", [])
        if sec.get("is_offense") is True and is_safe(sec)
    ]
    dc_sections = [
        sec for sec in dc.get("sections", [])
        if sec.get("is_offense") is True and is_safe(sec)
    ]
    federal["sections"] = federal_sections
    dc["sections"] = dc_sections
    federal["display_scope"] = "roblox_safe_charges_only"
    dc["display_scope"] = "roblox_safe_charges_only"
    allowed_federal = {sec["id"] for sec in federal_sections}
    allowed_dc = {sec["id"] for sec in dc_sections}

    # Title 18 detail files are deleted unless positively classified AND safe.
    allowed_title18: dict[str, dict] = {}
    removed_files = 0
    for path in sorted(TITLE18_DIR.glob("*.json")):
        detail = load(path)
        if strict_title18_charge(detail):
            detail.pop("charge_candidate", None)
            detail["is_charge"] = True
            detail["display_scope"] = "roblox_safe_charge"
            write(path, detail)
            allowed_title18[detail["id"]] = detail
        else:
            path.unlink()
            removed_files += 1

    index_by_id = {
        item.get("id"): item for item in title18_index.get("sections", [])
    }
    safe_index_sections = []
    for charge_id, detail in sorted(
        allowed_title18.items(),
        key=lambda pair: (
            int(pair[1]["section"]) if str(pair[1]["section"]).isdigit() else 10**9,
            str(pair[1]["section"]),
        ),
    ):
        old = dict(index_by_id.get(charge_id) or {})
        old.pop("charge_candidate", None)
        old["is_charge"] = True
        old["display_scope"] = "roblox_safe_charge"
        safe_index_sections.append(old)

    title18_index["sections"] = safe_index_sections
    title18_index["counts"] = {
        "sections": len(safe_index_sections),
        "charges": len(safe_index_sections),
        "filtered_out": removed_files,
    }
    title18_index["display_scope"] = "roblox_safe_charges_only"

    allowed_title18_ids = set(allowed_title18)
    safe_search_entries = [
        item for item in title18_search.get("entries", [])
        if item.get("id") in allowed_title18_ids and is_safe(item)
    ]
    title18_search["entries"] = safe_search_entries
    title18_search["count"] = len(safe_search_entries)
    title18_search["display_scope"] = "roblox_safe_charges_only"

    # The booking catalog can contain only backed, safe charge records.
    safe_charges = []
    for entry in charges.get("charges", []):
        source = entry.get("source")
        charge_id = entry.get("id")
        allowed = (
            (source == "federal-criminal-code-2025" and charge_id in allowed_federal)
            or (source == "dc-criminal-code-federalized" and charge_id in allowed_dc)
            or (source == "title18" and charge_id in allowed_title18_ids)
        )
        if not allowed or not is_safe(entry):
            continue
        entry.pop("charge_candidate", None)
        entry["is_charge"] = True
        entry["content_policy"] = "roblox_safe"
        if source == "title18":
            entry["charge_classification"] = "strict_positive_rule"
        safe_charges.append(entry)

    counts = {
        "total": len(safe_charges),
        "federal_code": sum(
            item.get("source") == "federal-criminal-code-2025"
            for item in safe_charges
        ),
        "dc_code": sum(
            item.get("source") == "dc-criminal-code-federalized"
            for item in safe_charges
        ),
        "title18": sum(item.get("source") == "title18" for item in safe_charges),
    }
    charges["charges"] = safe_charges
    charges["counts"] = counts
    charges["display_contract"] = {
        "charge_only": True,
        "roblox_safe_only": True,
        "fail_closed": True,
        "note": (
            "Only positively classified criminal charges that pass the platform "
            "safety filter are exposed. Ambiguous, administrative, definitional, "
            "procedural, restricted-content, and other non-charge sections are excluded."
        ),
    }

    # Supporting endpoints are scrubbed as well so restricted references cannot
    # survive anywhere under the Roblox-facing API path.
    sentencing = sanitize_supporting_value(load(BASE / "sentencing.json"))
    documents = load(BASE / "documents.json")
    for doc in documents.get("documents", []):
        doc["sections"] = [
            sec for sec in doc.get("sections", []) if is_safe(sec)
        ]
    documents = sanitize_supporting_value(documents)

    manifest = sanitize_supporting_value(manifest)
    roblox = manifest.setdefault("roblox", {})
    roblox["display_contract"] = {
        "charge_catalog": "charges.json",
        "charge_only": True,
        "roblox_safe_only": True,
        "fail_closed": True,
        "never_display_unlisted_sections": True,
    }
    roblox["booking_catalog_sources"] = [
        "Strictly classified, platform-safe current Title 18 charges",
        "Platform-safe Federal Criminal Code offenses enacted by Public Law 37-261",
        "Platform-safe D.C. Criminal Code offenses federalized by Public Law 36-260",
    ]
    roblox["title18_classification"] = (
        "Title 18 is fail-closed: only current Part I sections with positive "
        "actor-and-criminal-penalty language and no administrative, definition, "
        "or procedure heading are exposed."
    )
    roblox["content_filter"] = (
        "A fail-closed platform-safety filter removes restricted-content sections "
        "before publication. Clients must never display an unlisted section."
    )

    write(BASE / "federal-code.json", federal)
    write(BASE / "dc-code.json", dc)
    write(BASE / "title18-index.json", title18_index)
    write(BASE / "title18-search.json", title18_search)
    write(BASE / "charges.json", charges)
    write(BASE / "sentencing.json", sentencing)
    write(BASE / "documents.json", documents)
    write(BASE / "manifest.json", manifest)

    audit()
    print(
        "Roblox criminal API hardened: "
        f"{counts['federal_code']} FCC + {counts['dc_code']} D.C. + "
        f"{counts['title18']} Title 18 charges; {removed_files} Title 18 "
        "restricted/non-charge detail files removed."
    )


def audit() -> None:
    """Abort if blocked text or a non-charge display record survives."""
    if not BASE.is_dir():
        raise RuntimeError(f"API directory does not exist: {BASE}")

    offenders: list[str] = []
    for path in sorted(BASE.rglob("*.json")):
        payload = load(path)
        reason = blocked_reason(payload)
        if reason:
            offenders.append(f"{path.relative_to(ROOT)} ({reason})")
    if offenders:
        raise RuntimeError(
            "Roblox safety audit failed; blocked content survived: "
            + ", ".join(offenders[:20])
        )

    federal = load(BASE / "federal-code.json")
    dc = load(BASE / "dc-code.json")
    title18 = load(BASE / "title18-index.json")
    charges = load(BASE / "charges.json")

    if not all(sec.get("is_offense") is True for sec in federal.get("sections", [])):
        raise RuntimeError("federal-code.json contains a non-offense section")
    if not all(sec.get("is_offense") is True for sec in dc.get("sections", [])):
        raise RuntimeError("dc-code.json contains a non-offense section")
    if not all(sec.get("is_charge") is True for sec in title18.get("sections", [])):
        raise RuntimeError("title18-index.json contains a non-charge section")
    if not all(item.get("is_charge") is True for item in charges.get("charges", [])):
        raise RuntimeError("charges.json contains an entry not explicitly classified as a charge")

    allowed_ids = {
        *(sec["id"] for sec in federal.get("sections", [])),
        *(sec["id"] for sec in dc.get("sections", [])),
        *(sec["id"] for sec in title18.get("sections", [])),
    }
    charge_ids = {item["id"] for item in charges.get("charges", [])}
    if not charge_ids <= allowed_ids:
        raise RuntimeError("charges.json contains an entry without an allowed charge detail record")

    for path in TITLE18_DIR.glob("*.json"):
        detail = load(path)
        if detail.get("is_charge") is not True or not is_safe(detail):
            raise RuntimeError(f"Restricted/non-charge Title 18 detail survived: {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit the already-generated API without modifying it.",
    )
    args = parser.parse_args()
    if args.check:
        audit()
        print("Roblox criminal API safety audit passed.")
    else:
        harden()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
