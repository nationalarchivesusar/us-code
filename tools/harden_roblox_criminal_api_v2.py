#!/usr/bin/env python3
"""Fail-closed, charge-only hardening for the Roblox-facing criminal-law API.

Policy:
- Only positively identified criminal charges are exposed.
- Restricted references are never exposed through the Roblox-facing API.
- A legitimate charge is not discarded merely because its full statutory body
  contains a restricted reference. If the charge metadata itself is safe, the
  charge remains available and its statutory body is replaced with a neutral
  platform-safety placeholder.
- False positives are preferred only for questionable charge classification,
  not for ordinary non-graphic crimes such as murder, kidnapping, robbery, or
  assault.
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

WITHHELD_TEXT = (
    "Full statutory text is not displayed in this Roblox-facing reference. "
    "The charge citation and name remain available for booking."
)

# Broad on purpose. These patterns are applied to displayed metadata and text.
# If only the body trips a pattern, the body is withheld rather than deleting
# an otherwise valid, safely named charge.
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
        r"controlled\s+substances|marijuana|marihuana|cannabis|cocaine|heroin|"
        r"methamphetamine|meth|fentanyl|opioid|opioids|opiate|opiates|lsd|pcp|"
        r"ecstasy|mdma)\b",
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

# These are unambiguously criminal offense sections whose statutory bodies can
# contain cross-references that make a purely textual classifier too brittle.
# They remain subject to all metadata/content-safety rules.
KNOWN_TITLE18_CHARGES = {
    "111",   # assaulting/resisting/impeding certain officers
    "113",   # assaults within maritime/territorial jurisdiction
    "1111",  # murder
    "1112",  # manslaughter
    "1201",  # kidnapping
    "2113",  # bank robbery and incidental crimes
}


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


def title18_is_positive_charge(detail: dict) -> bool:
    if detail.get("status") != "current" or not detail.get("charge_candidate"):
        return False

    heading = str(detail.get("heading") or "")
    body = str(detail.get("text") or "")
    section = str(detail.get("section") or "")
    if not body.strip() or NON_CHARGE_HEADING.search(heading):
        return False

    if section in KNOWN_TITLE18_CHARGES:
        return True

    return (
        any(pattern.search(body) for pattern in TITLE18_ACTOR_PATTERNS)
        and any(pattern.search(body) for pattern in TITLE18_PENALTY_PATTERNS)
    )


def displayed_metadata(record: dict) -> dict:
    """Return only fields that can be exposed as human-visible legal metadata."""
    keys = {
        "id", "source", "citation", "formal_citation", "section", "label",
        "heading", "part", "chapter", "chapter_heading", "status",
        "offense_class", "sentencing_mode", "sentencing_reason",
    }
    return {key: record.get(key) for key in keys if key in record}


def safe_charge_body(record: dict) -> tuple[dict, bool]:
    """Withhold unsafe body text without discarding a safely named charge."""
    result = dict(record)
    text = str(result.get("text") or "")
    if text and blocked_reason(text):
        result["text"] = WITHHELD_TEXT
        result["text_withheld"] = True
        result["text_display_scope"] = "withheld_for_platform_safety"
        return result, True
    result["text_withheld"] = False
    return result, False


def sanitize_supporting_value(value: Any) -> Any:
    if isinstance(value, str):
        return "[PLATFORM-SAFETY TEXT WITHHELD]" if blocked_reason(value) else value
    if isinstance(value, list):
        return [sanitize_supporting_value(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_supporting_value(item) for key, item in value.items()}
    return value


def harden() -> None:
    required = (
        "charges.json",
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
    if (BASE / "federal-code.json").exists():
        raise RuntimeError("Duplicative federal-code.json must not be published")

    dc = load(BASE / "dc-code.json")
    title18_index = load(BASE / "title18-index.json")
    title18_search = load(BASE / "title18-search.json")
    charges = load(BASE / "charges.json")
    manifest = load(BASE / "manifest.json")

    def harden_local(sections: list[dict]) -> list[dict]:
        kept = []
        for sec in sections:
            if sec.get("is_offense") is not True:
                continue
            if not is_safe(displayed_metadata(sec)):
                continue
            safe_sec, _ = safe_charge_body(sec)
            kept.append(safe_sec)
        return kept

    dc_sections = harden_local(dc.get("sections", []))
    dc["sections"] = dc_sections
    dc["display_scope"] = "roblox_safe_charges_only"
    allowed_dc = {sec["id"] for sec in dc_sections}

    # Classify from the original operative text first. Then apply display safety.
    # Unsafe body text is withheld; unsafe metadata removes the charge entirely.
    allowed_title18: dict[str, dict] = {}
    removed_files = 0
    withheld_files = 0
    for path in sorted(TITLE18_DIR.glob("*.json")):
        detail = load(path)
        if not title18_is_positive_charge(detail):
            path.unlink()
            removed_files += 1
            continue

        if not is_safe(displayed_metadata(detail)):
            path.unlink()
            removed_files += 1
            continue

        detail, withheld = safe_charge_body(detail)
        if withheld:
            withheld_files += 1
        detail.pop("charge_candidate", None)
        detail["is_charge"] = True
        detail["display_scope"] = "roblox_safe_charge"
        write(path, detail)
        allowed_title18[detail["id"]] = detail

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
        if not old:
            continue
        old.pop("charge_candidate", None)
        if not is_safe(displayed_metadata(old)):
            continue
        old["is_charge"] = True
        old["display_scope"] = "roblox_safe_charge"
        old["text_withheld"] = bool(detail.get("text_withheld"))
        safe_index_sections.append(old)

    title18_index["sections"] = safe_index_sections
    title18_index["counts"] = {
        "sections": len(safe_index_sections),
        "charges": len(safe_index_sections),
        "filtered_out": removed_files,
        "text_withheld": withheld_files,
    }
    title18_index["display_scope"] = "roblox_safe_charges_only"

    allowed_title18_ids = {item["id"] for item in safe_index_sections}
    search_by_id = {
        item.get("id"): item for item in title18_search.get("entries", [])
    }
    safe_search_entries = []
    for item in safe_index_sections:
        charge_id = item["id"]
        old = dict(search_by_id.get(charge_id) or {})
        if not old:
            continue
        detail = allowed_title18[charge_id]
        if detail.get("text_withheld"):
            chapter = item.get("chapter") or {}
            safe_text = " ".join(
                str(value)
                for value in (
                    item.get("citation"),
                    item.get("heading"),
                    chapter.get("number") if isinstance(chapter, dict) else "",
                    chapter.get("heading") if isinstance(chapter, dict) else "",
                )
                if value
            )
            old["search_text"] = safe_text
        if not is_safe(old):
            old = {
                "id": charge_id,
                "search_text": " ".join(
                    str(v) for v in (item.get("citation"), item.get("heading")) if v
                ),
            }
        safe_search_entries.append(old)

    title18_search["entries"] = safe_search_entries
    title18_search["count"] = len(safe_search_entries)
    title18_search["display_scope"] = "roblox_safe_charges_only"

    safe_charges = []
    for entry in charges.get("charges", []):
        source = entry.get("source")
        charge_id = entry.get("id")
        allowed = (
            (source == "dc-criminal-code-federalized" and charge_id in allowed_dc)
            or (source == "title18" and charge_id in allowed_title18_ids)
        )
        if not allowed:
            continue
        if not is_safe(displayed_metadata(entry)):
            continue
        entry.pop("charge_candidate", None)
        entry["is_charge"] = True
        entry["content_policy"] = "roblox_safe"
        if source == "title18":
            entry["charge_classification"] = (
                "known_positive_charge"
                if str(entry.get("section") or "") in KNOWN_TITLE18_CHARGES
                else "strict_positive_rule"
            )
            entry["text_withheld"] = bool(
                allowed_title18[charge_id].get("text_withheld")
            )
        safe_charges.append(entry)

    counts = {
        "total": len(safe_charges),
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
        "preserve_safe_charge_metadata_when_text_withheld": True,
        "note": (
            "Only positively classified criminal charges are exposed. "
            "Restricted references are withheld. Safely named ordinary charges "
            "remain available even when their full statutory body cannot be displayed."
        ),
    }

    sentencing = sanitize_supporting_value(load(BASE / "sentencing.json"))
    documents = sanitize_supporting_value(load(BASE / "documents.json"))
    manifest = sanitize_supporting_value(manifest)

    roblox = manifest.setdefault("roblox", {})
    roblox["display_contract"] = {
        "charge_catalog": "charges.json",
        "charge_only": True,
        "roblox_safe_only": True,
        "fail_closed": True,
        "never_display_unlisted_sections": True,
        "withhold_restricted_body_without_deleting_safe_charge": True,
    }
    roblox["booking_catalog_sources"] = [
        "Positively classified current Title 18 charges",
        "D.C. Criminal Code offenses federalized by Public Law 36-260",
    ]
    roblox["title18_classification"] = (
        "Title 18 is charge-only. Positive offense classification is required. "
        "A safely named charge may remain available with its body withheld when "
        "the body contains material not suitable for the Roblox-facing reference."
    )
    roblox["content_filter"] = (
        "Restricted references are removed before publication. "
        "Clients must never display an unlisted section."
    )

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
        f"{counts['dc_code']} D.C. + "
        f"{counts['title18']} Title 18 charges; {removed_files} Title 18 "
        f"non-charge/restricted-metadata files removed; {withheld_files} "
        "charge bodies withheld."
    )


def ensure_core_violent_charges() -> None:
    """Regression guard: ordinary non-graphic violent charges must remain usable."""
    charges = load(BASE / "charges.json").get("charges", [])
    present = {
        (item.get("source"), str(item.get("section")))
        for item in charges
    }
    required = {
        ("dc-criminal-code-federalized", "301"),
        ("dc-criminal-code-federalized", "308"),
        ("dc-criminal-code-federalized", "309"),
        ("title18", "111"),
        ("title18", "1111"),
        ("title18", "1201"),
    }
    missing = sorted(required - present)
    if missing:
        raise RuntimeError(
            "Safety filtering became overbroad and removed core ordinary charges: "
            + repr(missing)
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

    if (BASE / "federal-code.json").exists():
        raise RuntimeError("Duplicative federal-code.json survived the API build")
    dc = load(BASE / "dc-code.json")
    title18 = load(BASE / "title18-index.json")
    charges = load(BASE / "charges.json")

    if not all(sec.get("is_offense") is True for sec in dc.get("sections", [])):
        raise RuntimeError("dc-code.json contains a non-offense section")
    if not all(sec.get("is_charge") is True for sec in title18.get("sections", [])):
        raise RuntimeError("title18-index.json contains a non-charge section")
    if not all(item.get("is_charge") is True for item in charges.get("charges", [])):
        raise RuntimeError("charges.json contains an entry not explicitly classified as a charge")

    allowed_ids = {
        *(sec["id"] for sec in dc.get("sections", [])),
        *(sec["id"] for sec in title18.get("sections", [])),
    }
    charge_ids = {item["id"] for item in charges.get("charges", [])}
    if not charge_ids <= allowed_ids:
        raise RuntimeError("charges.json contains an entry without an allowed charge detail record")
    if any(
        item.get("source") == "federal-criminal-code-2025"
        for item in charges.get("charges", [])
    ):
        raise RuntimeError("charges.json contains a duplicative FCC charge")

    for path in TITLE18_DIR.glob("*.json"):
        detail = load(path)
        if detail.get("is_charge") is not True or not is_safe(detail):
            raise RuntimeError(f"Restricted/non-charge Title 18 detail survived: {path.name}")

    ensure_core_violent_charges()


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
