#!/usr/bin/env python3
"""Finalize the compact criminal booking catalog for Roblox clients.

Public Law 36-260 § 10(b) adopted the D.C. Criminal Code as federal law and
§ 10(e) keeps adopted municipal laws in force until amended or repealed by
Congress. The supplied Public Law 37-261 establishes an additional Federal
Criminal Code but does not expressly repeal the PL 36-260 adoption. The
booking API therefore exposes both local-code sources instead of silently
choosing one and hiding the other.

This pass also attaches sentencing metadata. FCC and federalized D.C. offenses
use their authoritative A-G class_rule metadata. Title 18 offenses are
classified under 18 U.S.C. § 3559 when the defining section supplies a
single, unambiguous offense class or maximum imprisonment class; Public Law
39-267 then supplies the corresponding non-court in-game maximum. Sections
with mixed penalty variants, cross-referenced penalties, or otherwise
ambiguous classification remain manual rather than guessing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "api" / "v1" / "criminal-law"
PUBLIC_API = "https://nationalarchivesusar.github.io/us-code/data/api/v1/criminal-law/"

TITLE18_CLASS_RULES = {
    ("felony", "A"): {
        "max_minutes": 17,
        "classification_basis": "18 U.S.C. § 3559(a)(1)",
        "sentencing_basis": "Public Law 39-267 § 6(a)",
    },
    ("felony", "B"): {
        "max_minutes": 15,
        "classification_basis": "18 U.S.C. § 3559(a)(2)",
        "sentencing_basis": "Public Law 39-267 § 6(b)",
    },
    ("felony", "C"): {
        "max_minutes": 13,
        "classification_basis": "18 U.S.C. § 3559(a)(3)",
        "sentencing_basis": "Public Law 39-267 § 6(c)",
    },
    ("felony", "D"): {
        "max_minutes": 10,
        "classification_basis": "18 U.S.C. § 3559(a)(4)",
        "sentencing_basis": "Public Law 39-267 § 6(d)",
    },
    ("felony", "E"): {
        "max_minutes": 8,
        "classification_basis": "18 U.S.C. § 3559(a)(5)",
        "sentencing_basis": "Public Law 39-267 § 6(e)",
    },
    ("misdemeanor", "A"): {
        "max_minutes": 7,
        "classification_basis": "18 U.S.C. § 3559(a)(6)",
        "sentencing_basis": "Public Law 39-267 § 7(a)",
    },
    ("misdemeanor", "B"): {
        "max_minutes": 5,
        "classification_basis": "18 U.S.C. § 3559(a)(7)",
        "sentencing_basis": "Public Law 39-267 § 7(b)",
    },
    ("misdemeanor", "C"): {
        "max_minutes": 2,
        "classification_basis": "18 U.S.C. § 3559(a)(8)",
        "sentencing_basis": "Public Law 39-267 § 7(c)",
    },
}

_WORD_VALUES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
    "ninety": 90,
}
_NUMBER_ATOM = (
    r"(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)"
)
_NUMBER = rf"{_NUMBER_ATOM}(?:[-\s]+{_NUMBER_ATOM})*"
_DURATION = rf"(?P<number>{_NUMBER})\s+(?P<unit>years?|months?|days?)"

MAX_PATTERNS = [
    re.compile(
        rf"\b(?:not\s+more\s+than|no\s+more\s+than|not\s+exceeding|"
        rf"not\s+to\s+exceed|up\s+to|maximum(?:\s+term)?(?:\s+of)?(?:\s+imprisonment)?(?:\s+of)?)"
        rf"\s+{_DURATION}\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:imprisoned|imprisonment|term\s+of\s+imprisonment)\b"
        rf"[^.;:\n]{{0,60}}?\bfor\s+(?:a\s+term\s+of\s+)?{_DURATION}\b",
        re.IGNORECASE,
    ),
]
MIN_PATTERN = re.compile(
    rf"\b(?:not\s+less\s+than|at\s+least|minimum(?:\s+term)?(?:\s+of)?(?:\s+imprisonment)?(?:\s+of)?)"
    rf"\s+{_DURATION}\b",
    re.IGNORECASE,
)
ANY_DURATION_PATTERN = re.compile(rf"\b{_DURATION}\b", re.IGNORECASE)
EXPLICIT_CLASS_PATTERN = re.compile(
    r"\bclass\s+([A-E])\s+(felony|misdemeanor)\b",
    re.IGNORECASE,
)
LIFE_PATTERN = re.compile(
    r"\b(?:life\s+imprisonment|imprison(?:ed|ment)[^.;:\n]{0,40}\b(?:for\s+)?life)\b",
    re.IGNORECASE,
)
DEATH_PATTERN = re.compile(
    r"\b(?:punish(?:ed|able)\s+by\s+death|penalty\s+of\s+death|sentenced\s+to\s+death)\b",
    re.IGNORECASE,
)
PENALTY_CROSS_REFERENCE_PATTERN = re.compile(
    r"\b(?:punish(?:ed|ment|able)?|penalt(?:y|ies)|sentenc(?:e|ed|ing))\b"
    r"[^.;:\n]{0,100}\b(?:under|pursuant\s+to|provided\s+(?:for\s+)?in|"
    r"prescribed\s+in|set\s+forth\s+in)\s+"
    r"(?:section|subsection|paragraph|chapter|title)\b",
    re.IGNORECASE,
)
PENALTY_KEYWORD_PATTERN = re.compile(
    r"\b(?:imprison(?:ed|ment)|punish(?:ed|ment|able)?|penalt(?:y|ies)|"
    r"sentenc(?:e|ed|ing)|fine(?:d)?)\b",
    re.IGNORECASE,
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def parse_number(value: str) -> float | None:
    value = value.strip().lower().replace("-", " ")
    try:
        return float(value)
    except ValueError:
        pass

    total = 0
    current = 0
    for token in value.split():
        if token == "and":
            continue
        if token == "hundred":
            if current == 0:
                current = 1
            current *= 100
            continue
        amount = _WORD_VALUES.get(token)
        if amount is None:
            return None
        current += amount
    total += current
    return float(total)


def classify_duration(number: float, unit: str) -> tuple[str, str] | None:
    unit = unit.lower()
    if unit.startswith("year"):
        if number >= 25:
            return ("felony", "B")
        if number >= 10:
            return ("felony", "C")
        if number >= 5:
            return ("felony", "D")
        if number > 1:
            return ("felony", "E")
        if number > 0.5:
            return ("misdemeanor", "A")
        return None

    if unit.startswith("month"):
        if number >= 300:
            return ("felony", "B")
        if number >= 120:
            return ("felony", "C")
        if number >= 60:
            return ("felony", "D")
        if number > 12:
            return ("felony", "E")
        if number > 6:
            return ("misdemeanor", "A")
        if number > 1:
            return ("misdemeanor", "B")
        # "One month" can be 28-31 days, straddling § 3559(a)(7)-(8).
        return None

    if unit.startswith("day"):
        if number >= 25 * 365:
            return ("felony", "B")
        if number >= 10 * 365:
            return ("felony", "C")
        if number >= 5 * 365:
            return ("felony", "D")
        if number > 365:
            return ("felony", "E")
        if number > 183:
            return ("misdemeanor", "A")
        if number > 30:
            return ("misdemeanor", "B")
        if number > 5:
            return ("misdemeanor", "C")
        return ("infraction", "")

    return None


def _span_is_covered(span: tuple[int, int], covered: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start >= cstart and end <= cend for cstart, cend in covered)


def _penalty_segments(text: str) -> list[tuple[int, str]]:
    segments: list[tuple[int, str]] = []
    cursor = 0
    for match in re.finditer(r".*?(?:[.;](?=\s|$)|\n+|$)", text, re.DOTALL):
        raw = match.group(0)
        stripped = raw.strip()
        if stripped and PENALTY_KEYWORD_PATTERN.search(stripped):
            leading = len(raw) - len(raw.lstrip())
            segments.append((match.start() + leading, stripped))
        cursor = match.end()
    if cursor < len(text):
        raw = text[cursor:]
        stripped = raw.strip()
        if stripped and PENALTY_KEYWORD_PATTERN.search(stripped):
            leading = len(raw) - len(raw.lstrip())
            segments.append((cursor + leading, stripped))
    return segments


def classify_title18_text(text: str) -> dict:
    """Return a conservative Title 18 classification decision.

    Automatic classification is allowed only when every detected penalty
    variant resolves to one § 3559 class and no unresolved duration or
    cross-referenced penalty appears in the relevant penalty language.
    """
    explicit_classes = {
        (match.group(2).lower(), match.group(1).upper())
        for match in EXPLICIT_CLASS_PATTERN.finditer(text)
    }

    if PENALTY_CROSS_REFERENCE_PATTERN.search(text):
        return {
            "status": "manual",
            "reason": (
                "This Title 18 section uses a cross-referenced penalty provision; "
                "the booking API will not infer the applicable 18 U.S.C. § 3559 class."
            ),
        }

    classes = set(explicit_classes)
    evidence: list[str] = []

    if DEATH_PATTERN.search(text) or LIFE_PATTERN.search(text):
        classes.add(("felony", "A"))
        evidence.append("life_or_death")

    recognized_max_spans: list[tuple[int, int]] = []
    recognized_min_spans: list[tuple[int, int]] = []
    for pattern in MAX_PATTERNS:
        for match in pattern.finditer(text):
            value = parse_number(match.group("number"))
            if value is None:
                continue
            classification = classify_duration(value, match.group("unit"))
            if classification is None:
                return {
                    "status": "manual",
                    "reason": (
                        "A maximum imprisonment term in this Title 18 section does not "
                        "map cleanly to a single 18 U.S.C. § 3559 class."
                    ),
                }
            classes.add(classification)
            recognized_max_spans.append(match.span())
            evidence.append(match.group(0))

    recognized_min_spans.extend(match.span() for match in MIN_PATTERN.finditer(text))

    # Fail closed if a penalty clause contains an otherwise-unaccounted-for
    # duration. This prevents reading the first maximum in a multi-variant
    # sentence while silently missing a second differently drafted term.
    for segment_offset, segment in _penalty_segments(text):
        segment_end = segment_offset + len(segment)
        local_covered = [
            (start - segment_offset, end - segment_offset)
            for start, end in recognized_max_spans + recognized_min_spans
            if start >= segment_offset and end <= segment_end
        ]
        for duration in ANY_DURATION_PATTERN.finditer(segment):
            if not _span_is_covered(duration.span(), local_covered):
                return {
                    "status": "manual",
                    "reason": (
                        "This Title 18 section contains additional duration language in "
                        "a penalty clause that cannot be safely identified as a single "
                        "maximum term; manual sentencing is required."
                    ),
                }

    mapped_classes = {item for item in classes if item[0] != "infraction"}
    has_infraction = any(item[0] == "infraction" for item in classes)
    if has_infraction:
        return {
            "status": "manual",
            "reason": (
                "This Title 18 section includes an infraction-level penalty, but "
                "Public Law 39-267 supplies non-court maxima only for felony and "
                "misdemeanor classes."
            ),
        }

    if len(mapped_classes) > 1:
        labels = sorted(
            f"Class {letter} {category}"
            for category, letter in mapped_classes
        )
        return {
            "status": "manual",
            "reason": (
                "This Title 18 section contains penalty variants that fall into "
                "different 18 U.S.C. § 3559 classes: " + ", ".join(labels) + "."
            ),
            "detected_classes": labels,
        }

    if len(mapped_classes) == 0:
        return {
            "status": "manual",
            "reason": (
                "No single authoritative Title 18 offense class or maximum "
                "imprisonment term could be extracted safely from this section."
            ),
        }

    category, letter = next(iter(mapped_classes))
    rule = TITLE18_CLASS_RULES.get((category, letter))
    if rule is None:
        return {
            "status": "manual",
            "reason": (
                "The detected Title 18 class has no Public Law 39-267 "
                "non-court sentencing rule."
            ),
        }

    return {
        "status": "automatic",
        "category": category,
        "letter": letter,
        "class_display": f"Class {letter} {category}",
        "max_minutes": rule["max_minutes"],
        "classification_basis": rule["classification_basis"],
        "sentencing_basis": rule["sentencing_basis"],
        "evidence_count": len(evidence) + len(explicit_classes),
    }


def clear_title18_sentencing(entry: dict) -> None:
    for key in (
        "offense_category",
        "offense_class",
        "class_display",
        "classification_basis",
        "classification_status",
        "sentencing_basis",
        "sentencing_range_minutes",
        "sentencing_max_minutes",
        "suggested_minutes",
        "statutory_minimum_specified",
        "detected_classes",
    ):
        entry.pop(key, None)


def apply_title18_sentencing(entry: dict, text: str) -> dict:
    decision = classify_title18_text(text)
    clear_title18_sentencing(entry)

    if decision["status"] != "automatic":
        entry["sentencing_mode"] = "manual_required"
        entry["classification_status"] = "manual_review_required"
        entry["sentencing_reason"] = decision["reason"]
        if decision.get("detected_classes"):
            entry["detected_classes"] = decision["detected_classes"]
        return decision

    category = decision["category"]
    letter = decision["letter"]
    maximum = decision["max_minutes"]
    entry["offense_category"] = category
    entry["offense_class"] = letter
    entry["class_display"] = decision["class_display"]
    entry["classification_basis"] = decision["classification_basis"]
    entry["classification_status"] = "derived_from_title18"
    entry["sentencing_basis"] = decision["sentencing_basis"]
    entry["sentencing_mode"] = "automatic_class_rule"
    entry["sentencing_range_minutes"] = {"min": 0, "max": maximum}
    entry["sentencing_max_minutes"] = maximum
    entry["suggested_minutes"] = maximum
    entry["statutory_minimum_specified"] = False
    entry["sentencing_reason"] = (
        "Automatic non-court maximum: the Title 18 offense class is determined "
        "under 18 U.S.C. § 3559 and mapped to the same felony/misdemeanor class "
        "in Public Law 39-267. The 0-minute lower bound is an API/UI bound, not "
        "a statutory minimum."
    )
    return decision


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
        entry["suggested_minutes"] = maximum
    else:
        entry["sentencing_mode"] = "manual_required"
        entry["sentencing_reason"] = "No authoritative in-game class rule is attached to this catalog entry."


def _title18_detail_path(entry: dict) -> Path:
    section = re.sub(r"[^0-9A-Za-z._-]", "_", str(entry.get("section", "")))
    return BASE / "title18" / f"{section}.json"


def _copy_sentencing_metadata(source: dict, target: dict) -> None:
    keys = (
        "offense_category",
        "offense_class",
        "class_display",
        "classification_basis",
        "classification_status",
        "sentencing_basis",
        "sentencing_mode",
        "sentencing_range_minutes",
        "sentencing_max_minutes",
        "suggested_minutes",
        "statutory_minimum_specified",
        "sentencing_reason",
        "detected_classes",
    )
    for key in keys:
        if key in source:
            target[key] = source[key]
        else:
            target.pop(key, None)


def main() -> int:
    charges_path = BASE / "charges.json"
    dc_path = BASE / "dc-code.json"
    sentencing_path = BASE / "sentencing.json"
    manifest_path = BASE / "manifest.json"
    title18_index_path = BASE / "title18-index.json"

    charges = load(charges_path)
    dc = load(dc_path)
    sentencing = load(sentencing_path)
    manifest = load(manifest_path)
    title18_index = load(title18_index_path)

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

    title18_auto = 0
    title18_manual = 0
    title18_detail_by_id: dict[str, dict] = {}
    for entry in title18_entries:
        detail_path = _title18_detail_path(entry)
        if not detail_path.exists():
            entry["sentencing_mode"] = "manual_required"
            entry["classification_status"] = "manual_review_required"
            entry["sentencing_reason"] = (
                "The generated Title 18 detail record is unavailable; "
                "automatic classification is disabled."
            )
            title18_manual += 1
            continue

        detail = load(detail_path)
        decision = apply_title18_sentencing(entry, detail.get("text", ""))
        _copy_sentencing_metadata(entry, detail)
        write(detail_path, detail)
        title18_detail_by_id[entry["id"]] = entry

        if decision["status"] == "automatic":
            title18_auto += 1
        else:
            title18_manual += 1

    # Mirror sentencing metadata into the lightweight Title 18 index so clients
    # can display class and mode without fetching the full statutory text.
    for index_entry in title18_index.get("sections", []):
        source_entry = title18_detail_by_id.get(index_entry.get("id"))
        if source_entry is not None:
            _copy_sentencing_metadata(source_entry, index_entry)
    write(title18_index_path, title18_index)

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
        "title18_automatic": title18_auto,
        "title18_manual": title18_manual,
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
            "title18",
        ],
        "conditionally_manual_sources": ["title18"],
        "manual_sources": ["title18"],
        "per_charge_mode_is_authoritative": True,
        "class_crosswalk_status": sentencing_rules.get("crosswalk_status"),
        "automatic_rule": (
            "FCC and federalized D.C. charges use each offense's local class_rule. "
            "A Title 18 charge may use automatic_class_rule only when its federal "
            "offense class is unambiguous under 18 U.S.C. § 3559; Public Law 39-267 "
            "then supplies the matching felony/misdemeanor non-court maximum."
        ),
        "title18_rule": (
            "Use 18 U.S.C. § 3559 for Title 18 offense classification. If a section "
            "contains mixed penalty variants, cross-referenced penalties, an infraction, "
            "or no safely extractable single class, sentencing remains manual_required. "
            "Never choose a subsection or penalty variant client-side."
        ),
        "title18_automatic_count": title18_auto,
        "title18_manual_count": title18_manual,
    }
    write(charges_path, charges)

    sentencing["title18_classification"] = {
        "basis": "18 U.S.C. § 3559(a)",
        "sentencing_basis": "Public Law 39-267 §§ 6-7",
        "mode": "conditional_automatic",
        "rule": (
            "When a Title 18 section has one unambiguous federal felony or misdemeanor "
            "class under 18 U.S.C. § 3559, use the matching Public Law 39-267 class "
            "maximum for non-court sentencing. Mixed or ambiguous section-level charges "
            "remain manual."
        ),
        "important_distinction": (
            "This does not crosswalk FCC/D.C. A-G offense classes to Public Law 39-267. "
            "Title 18 uses the federal felony/misdemeanor letter classes supplied by "
            "18 U.S.C. § 3559 itself."
        ),
        "statutory_minimum_note": (
            "Public Law 39-267 supplies maxima only. A 0-minute API lower bound is not "
            "a statutory minimum."
        ),
        "automatic_count": title18_auto,
        "manual_count": title18_manual,
    }
    write(sentencing_path, sentencing)

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
    roblox["conditionally_manual_sentencing_sources"] = ["title18"]
    roblox["manual_sentencing_sources"] = ["title18"]
    roblox["title18_automatic_count"] = title18_auto
    roblox["title18_manual_count"] = title18_manual
    roblox["sentencing_policy"] = (
        "Read charges.json sentencing_policy and each charge's sentencing_mode. "
        "Title 18 is automatic only where the API resolved one unambiguous 18 U.S.C. "
        "§ 3559 class; never infer a missing or mixed class client-side."
    )
    write(manifest_path, manifest)

    print(
        "Booking catalog includes "
        f"{len(federal_entries)} FCC offenses, {len(dc_entries)} federalized D.C. offenses, "
        f"and {len(title18_entries)} Title 18 charge candidates "
        f"({title18_auto} automatic, {title18_manual} manual); "
        f"multi-charge cap={multi_charge_cap!r} minutes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
