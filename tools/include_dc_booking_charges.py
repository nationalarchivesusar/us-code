#!/usr/bin/env python3
"""Finalize the Roblox booking catalog and attach sentencing metadata.

Federalized D.C. offenses use their enacted A-G class rules. Title 18
offenses are classified pursuant to 18 U.S.C. § 3559 only when the section
yields one unambiguous federal felony/misdemeanor class; Public Law 39-267
then supplies the matching non-court maximum. Mixed or uncertain sections stay
manual so the API never guesses a subsection or penalty variant.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "api" / "v1" / "criminal-law"
PUBLIC_API = "https://nationalarchivesusar.github.io/us-code/data/api/v1/criminal-law/"

T18_RULES = {
    ("felony", "A"): (17, "18 U.S.C. § 3559(a)(1)", "Public Law 39-267 § 6(a)"),
    ("felony", "B"): (15, "18 U.S.C. § 3559(a)(2)", "Public Law 39-267 § 6(b)"),
    ("felony", "C"): (13, "18 U.S.C. § 3559(a)(3)", "Public Law 39-267 § 6(c)"),
    ("felony", "D"): (10, "18 U.S.C. § 3559(a)(4)", "Public Law 39-267 § 6(d)"),
    ("felony", "E"): (8, "18 U.S.C. § 3559(a)(5)", "Public Law 39-267 § 6(e)"),
    ("misdemeanor", "A"): (7, "18 U.S.C. § 3559(a)(6)", "Public Law 39-267 § 7(a)"),
    ("misdemeanor", "B"): (5, "18 U.S.C. § 3559(a)(7)", "Public Law 39-267 § 7(b)"),
    ("misdemeanor", "C"): (2, "18 U.S.C. § 3559(a)(8)", "Public Law 39-267 § 7(c)"),
}

WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
ATOM = (
    r"(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)"
)
NUMBER = rf"{ATOM}(?:[-\s]+{ATOM})*"
DURATION = rf"(?P<number>{NUMBER})\s+(?P<unit>years?|months?|days?)"
MAX_PATTERNS = (
    re.compile(
        rf"\b(?:not\s+more\s+than|no\s+more\s+than|not\s+exceeding|"
        rf"not\s+to\s+exceed|up\s+to|maximum(?:\s+term)?(?:\s+of)?"
        rf"(?:\s+imprisonment)?(?:\s+of)?)\s+{DURATION}\b",
        re.I,
    ),
    re.compile(
        rf"\b(?:imprisoned|imprisonment|term\s+of\s+imprisonment)\b"
        rf"[^.;:\n]{{0,60}}?\bfor\s+(?:a\s+term\s+of\s+)?{DURATION}\b",
        re.I,
    ),
)
MIN_PATTERN = re.compile(
    rf"\b(?:not\s+less\s+than|at\s+least|minimum(?:\s+term)?(?:\s+of)?"
    rf"(?:\s+imprisonment)?(?:\s+of)?)\s+{DURATION}\b",
    re.I,
)
ANY_DURATION = re.compile(rf"\b{DURATION}\b", re.I)
EXPLICIT_CLASS = re.compile(r"\bclass\s+([A-E])\s+(felony|misdemeanor)\b", re.I)
LIFE = re.compile(
    r"\b(?:life\s+imprisonment|imprison(?:ed|ment)[^.;:\n]{0,40}\b(?:for\s+)?life)\b",
    re.I,
)
DEATH = re.compile(
    r"\b(?:punish(?:ed|able)\s+by\s+death|penalty\s+of\s+death|sentenced\s+to\s+death)\b",
    re.I,
)
PENALTY_XREF = re.compile(
    r"\b(?:punish(?:ed|ment|able)?|penalt(?:y|ies)|sentenc(?:e|ed|ing))\b"
    r"[^.;:\n]{0,100}\b(?:under|pursuant\s+to|provided\s+(?:for\s+)?in|"
    r"prescribed\s+in|set\s+forth\s+in)\s+"
    r"(?:section|subsection|paragraph|chapter|title)\b",
    re.I,
)
PENALTY_WORD = re.compile(
    r"\b(?:imprison(?:ed|ment)|punish(?:ed|ment|able)?|penalt(?:y|ies)|"
    r"sentenc(?:e|ed|ing)|fine(?:d)?)\b",
    re.I,
)

META_KEYS = (
    "offense_category", "offense_class", "class_display", "classification_basis",
    "classification_status", "sentencing_basis", "sentencing_mode",
    "sentencing_range_minutes", "sentencing_max_minutes", "suggested_minutes",
    "statutory_minimum_specified", "sentencing_reason", "detected_classes",
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def number_value(raw: str) -> float | None:
    raw = raw.strip().lower().replace("-", " ")
    try:
        return float(raw)
    except ValueError:
        pass
    current = 0
    for token in raw.split():
        if token == "and":
            continue
        if token == "hundred":
            current = (current or 1) * 100
        elif token in WORDS:
            current += WORDS[token]
        else:
            return None
    return float(current)


def duration_class(n: float, unit: str) -> tuple[str, str] | None:
    unit = unit.lower()
    if unit.startswith("year"):
        if n >= 25: return ("felony", "B")
        if n >= 10: return ("felony", "C")
        if n >= 5: return ("felony", "D")
        if n > 1: return ("felony", "E")
        if n > .5: return ("misdemeanor", "A")
        return None
    if unit.startswith("month"):
        if n >= 300: return ("felony", "B")
        if n >= 120: return ("felony", "C")
        if n >= 60: return ("felony", "D")
        if n > 12: return ("felony", "E")
        if n > 6: return ("misdemeanor", "A")
        if n > 1: return ("misdemeanor", "B")
        return None
    if unit.startswith("day"):
        if n >= 25 * 365: return ("felony", "B")
        if n >= 10 * 365: return ("felony", "C")
        if n >= 5 * 365: return ("felony", "D")
        if n > 365: return ("felony", "E")
        if n > 183: return ("misdemeanor", "A")
        if n > 30: return ("misdemeanor", "B")
        if n > 5: return ("misdemeanor", "C")
        return ("infraction", "")
    return None


def covered(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(span[0] >= start and span[1] <= end for start, end in spans)


def penalty_segments(text: str) -> list[tuple[int, str]]:
    result = []
    for match in re.finditer(r".*?(?:[.;](?=\s|$)|\n+|$)", text, re.S):
        raw = match.group(0)
        stripped = raw.strip()
        if stripped and PENALTY_WORD.search(stripped):
            lead = len(raw) - len(raw.lstrip())
            result.append((match.start() + lead, stripped))
    return result


def classify_title18(text: str) -> dict:
    if PENALTY_XREF.search(text):
        return {"status": "manual", "reason": (
            "This Title 18 section uses a cross-referenced penalty provision; "
            "the API will not infer its 18 U.S.C. § 3559 class."
        )}

    classes = {(m.group(2).lower(), m.group(1).upper()) for m in EXPLICIT_CLASS.finditer(text)}
    if LIFE.search(text) or DEATH.search(text):
        classes.add(("felony", "A"))

    max_spans: list[tuple[int, int]] = []
    for pattern in MAX_PATTERNS:
        for match in pattern.finditer(text):
            value = number_value(match.group("number"))
            cls = None if value is None else duration_class(value, match.group("unit"))
            if cls is None:
                return {"status": "manual", "reason": (
                    "A maximum imprisonment term does not map cleanly to one "
                    "18 U.S.C. § 3559 class."
                )}
            classes.add(cls)
            max_spans.append(match.span())

    min_spans = [m.span() for m in MIN_PATTERN.finditer(text)]
    for offset, segment in penalty_segments(text):
        end = offset + len(segment)
        local = [
            (start - offset, stop - offset)
            for start, stop in max_spans + min_spans
            if start >= offset and stop <= end
        ]
        if any(not covered(m.span(), local) for m in ANY_DURATION.finditer(segment)):
            return {"status": "manual", "reason": (
                "This Title 18 section contains unresolved duration language in a "
                "penalty clause; manual sentencing is required."
            )}

    if any(category == "infraction" for category, _ in classes):
        return {"status": "manual", "reason": (
            "This section includes an infraction-level penalty, while Public Law "
            "39-267 supplies non-court maxima only for felony and misdemeanor classes."
        )}

    classes = {item for item in classes if item[0] != "infraction"}
    if len(classes) > 1:
        labels = sorted(f"Class {letter} {category}" for category, letter in classes)
        return {
            "status": "manual",
            "reason": (
                "This section contains penalty variants in different 18 U.S.C. "
                "§ 3559 classes: " + ", ".join(labels) + "."
            ),
            "detected_classes": labels,
        }
    if not classes:
        return {"status": "manual", "reason": (
            "No single Title 18 offense class or maximum imprisonment term could "
            "be extracted safely from this section."
        )}

    category, letter = next(iter(classes))
    rule = T18_RULES.get((category, letter))
    if not rule:
        return {"status": "manual", "reason": (
            "The detected federal class has no Public Law 39-267 non-court rule."
        )}
    maximum, class_basis, sentence_basis = rule
    return {
        "status": "automatic", "category": category, "letter": letter,
        "class_display": f"Class {letter} {category}", "max_minutes": maximum,
        "classification_basis": class_basis, "sentencing_basis": sentence_basis,
    }


def apply_title18(entry: dict, text: str) -> dict:
    for key in META_KEYS:
        entry.pop(key, None)
    decision = classify_title18(text)
    if decision["status"] != "automatic":
        entry["sentencing_mode"] = "manual_required"
        entry["classification_status"] = "manual_review_required"
        entry["sentencing_reason"] = decision["reason"]
        if decision.get("detected_classes"):
            entry["detected_classes"] = decision["detected_classes"]
        return decision

    maximum = decision["max_minutes"]
    entry.update({
        "offense_category": decision["category"],
        "offense_class": decision["letter"],
        "class_display": decision["class_display"],
        "classification_basis": decision["classification_basis"],
        "classification_status": "derived_from_title18",
        "sentencing_basis": decision["sentencing_basis"],
        "sentencing_mode": "automatic_class_rule",
        "sentencing_range_minutes": {"min": 0, "max": maximum},
        "sentencing_max_minutes": maximum,
        "suggested_minutes": maximum,
        "statutory_minimum_specified": False,
        "sentencing_reason": (
            "Automatic non-court maximum: the federal offense class is determined "
            "pursuant to 18 U.S.C. § 3559 and the matching felony/misdemeanor class "
            "maximum comes from Public Law 39-267. The 0-minute lower bound is an "
            "API/UI bound, not a statutory minimum."
        ),
    })
    return decision


def apply_local(entry: dict) -> None:
    rule = entry.get("class_rule") or {}
    lo = rule.get("initial_min_minutes")
    hi = rule.get("initial_max_minutes")
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        entry["sentencing_mode"] = "automatic_class_rule"
        entry["sentencing_range_minutes"] = {"min": lo, "max": hi}
        entry["suggested_minutes"] = hi
    else:
        entry["sentencing_mode"] = "manual_required"
        entry["sentencing_reason"] = "No authoritative in-game class rule is attached to this entry."


def copy_meta(source: dict, target: dict) -> None:
    for key in META_KEYS:
        if key in source:
            target[key] = source[key]
        else:
            target.pop(key, None)


def title18_path(entry: dict) -> Path:
    section = re.sub(r"[^0-9A-Za-z._-]", "_", str(entry.get("section", "")))
    return BASE / "title18" / f"{section}.json"


def main() -> int:
    charges_path = BASE / "charges.json"
    sentencing_path = BASE / "sentencing.json"
    manifest_path = BASE / "manifest.json"
    index_path = BASE / "title18-index.json"

    charges = load(charges_path)
    dc = load(BASE / "dc-code.json")
    sentencing = load(sentencing_path)
    manifest = load(manifest_path)
    index = load(index_path)

    title18 = [x for x in charges.get("charges", []) if x.get("source") == "title18"]

    automatic = manual = 0
    by_id = {}
    for entry in title18:
        path = title18_path(entry)
        if not path.exists():
            entry.update({
                "sentencing_mode": "manual_required",
                "classification_status": "manual_review_required",
                "sentencing_reason": "The generated Title 18 detail record is unavailable.",
            })
            manual += 1
            continue
        detail = load(path)
        decision = apply_title18(entry, detail.get("text", ""))
        copy_meta(entry, detail)
        write(path, detail)
        by_id[entry["id"]] = entry
        automatic += decision["status"] == "automatic"
        manual += decision["status"] != "automatic"

    for item in index.get("sections", []):
        if item.get("id") in by_id:
            copy_meta(by_id[item["id"]], item)
    write(index_path, index)

    dc_entries = []
    for sec in dc.get("sections", []):
        if not sec.get("is_offense"):
            continue
        entry = {
            "id": sec["id"], "source": "dc-criminal-code-federalized",
            "citation": f"D.C. Criminal Code § {sec['section']}",
            "formal_citation": sec["citation"], "section": sec["section"],
            "label": sec["heading"], "status": "current",
            "offense_class": sec.get("offense_class"), "class_rule": sec.get("class_rule"),
            "chapter": sec.get("chapter"), "chapter_heading": sec.get("chapter_heading"),
            "details_url": f"{PUBLIC_API}dc-code.json", "web_url": sec["web_url"],
            "anchor": f"dcc-{sec['section']}",
            "legal_basis": "Public Law 36-260 § 10(b), subject to § 10(e)",
        }
        apply_local(entry)
        dc_entries.append(entry)

    combined = dc_entries + title18
    charges["charges"] = combined
    charges["counts"] = {
        "total": len(combined), "dc_code": len(dc_entries),
        "title18": len(title18), "title18_automatic": automatic, "title18_manual": manual,
    }
    charges["available_local_codes"] = ["dc-criminal-code-federalized"]
    charges["local_code_status_note"] = (
        "Public Law 36-260 § 10(b) adopted the D.C. Criminal Code as federal law, "
        "and § 10(e) keeps adopted municipal laws in force until amended or repealed "
        "by Congress. The Federal Criminal Code enacted by Public Law 37-261 is not "
        "included in this API because all 66 of its offenses duplicate D.C. Criminal "
        "Code offenses by section number, offense heading, and class. Its enacted "
        "source remains preserved outside the API."
    )

    rules = sentencing.get("rules") or {}
    cap = rules.get("multi_charge_max_minutes")
    charges["sentencing_policy"] = {
        "non_court_scope": rules.get("scope"),
        "multi_charge_max_minutes": cap,
        "automatic_sources": ["dc-criminal-code-federalized", "title18"],
        "conditionally_manual_sources": ["title18"],
        "manual_sources": ["title18"],
        "per_charge_mode_is_authoritative": True,
        "class_crosswalk_status": rules.get("crosswalk_status"),
        "automatic_rule": (
            "Federalized D.C. charges use their local class rules. A Title 18 "
            "charge is automatic only when one federal class is resolved pursuant to "
            "18 U.S.C. § 3559; Public Law 39-267 then supplies the matching "
            "felony/misdemeanor non-court maximum."
        ),
        "title18_rule": (
            "Mixed penalty variants, cross-referenced penalties, infractions, and "
            "sections without one safely extractable class remain manual_required. "
            "Never choose a subsection or penalty variant client-side."
        ),
        "title18_automatic_count": automatic,
        "title18_manual_count": manual,
    }
    write(charges_path, charges)

    sentencing["title18_classification"] = {
        "basis": "18 U.S.C. § 3559(a)",
        "sentencing_basis": "Public Law 39-267 §§ 6-7",
        "mode": "conditional_automatic",
        "rule": (
            "When a Title 18 section has one unambiguous federal felony or misdemeanor "
            "class pursuant to 18 U.S.C. § 3559, use the matching Public Law 39-267 "
            "class maximum for non-court sentencing. Mixed or ambiguous section-level "
            "charges remain manual."
        ),
        "important_distinction": (
            "This does not crosswalk D.C. A-G offense classes to Public Law 39-267. "
            "Title 18 uses the federal felony/misdemeanor letter classes supplied by "
            "18 U.S.C. § 3559 itself."
        ),
        "statutory_minimum_note": (
            "Public Law 39-267 supplies maxima only. A 0-minute API lower bound is not "
            "a statutory minimum."
        ),
        "automatic_count": automatic,
        "manual_count": manual,
    }
    write(sentencing_path, sentencing)

    for source in manifest.get("sources", []):
        if source.get("id") == "dc-criminal-code-federalized":
            source["status"] = "current federalized law under Public Law 36-260 § 10(b), subject to § 10(e)"
    roblox = manifest.setdefault("roblox", {})
    roblox["booking_catalog_sources"] = [
        "18 U.S.C. current Part I charge candidates",
        "D.C. Criminal Code federalized by Public Law 36-260",
    ]
    roblox["local_code_note"] = charges["local_code_status_note"]
    roblox["multi_charge_max_minutes"] = cap
    roblox["automatic_sentencing_sources"] = charges["sentencing_policy"]["automatic_sources"]
    roblox["conditionally_manual_sentencing_sources"] = ["title18"]
    roblox["manual_sentencing_sources"] = ["title18"]
    roblox["title18_automatic_count"] = automatic
    roblox["title18_manual_count"] = manual
    roblox["sentencing_policy"] = (
        "Read charges.json sentencing_policy and each charge's sentencing_mode. "
        "Title 18 is automatic only where the API resolves one unambiguous 18 U.S.C. "
        "§ 3559 class; never infer a missing or mixed class client-side."
    )
    write(manifest_path, manifest)

    print(
        "Booking catalog includes "
        f"{len(dc_entries)} federalized D.C. offenses, "
        f"and {len(title18)} Title 18 charge candidates ({automatic} automatic, {manual} manual); "
        f"multi-charge cap={cap!r} minutes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
