#!/usr/bin/env python3
"""Conservative Title 18 sentencing classification helpers for the Roblox API.

18 U.S.C. § 3559(a) supplies a letter-grade classification for federal offenses
that are not already letter-graded, based on the maximum authorized term of
imprisonment. Public Law 39-267 uses the same A-E felony / A-C misdemeanor
class labels for non-court-imposed in-game sentencing.

This module deliberately classifies only sections whose operative text yields a
single unambiguous § 3559 class. Sections with multiple penalty tiers spanning
more than one class, cross-referenced penalties, or no reliably parseable
maximum remain manual. It is better to require a manual sentence than to assign
an incorrect class.
"""
from __future__ import annotations

import re
from typing import Any

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "twenty-one": 21,
    "twenty-two": 22,
    "twenty-three": 23,
    "twenty-four": 24,
    "twenty-five": 25,
    "thirty": 30,
}

NUMBER = r"(?:\d+(?:\.\d+)?|" + "|".join(
    sorted((re.escape(word) for word in NUMBER_WORDS), key=len, reverse=True)
) + r")"
UNIT = r"(?:years?|months?|days?)"

EXPLICIT_CLASS = re.compile(
    r"\bclass\s+([A-E])\s+(felony|misdemeanor)\b",
    re.I,
)

# Capture only formulations that actually state a maximum or fixed custodial
# term. Minimum-only language is intentionally ignored.
MAX_TERM_PATTERNS = (
    re.compile(
        rf"\b(?:imprisoned|imprisonment)\b.{{0,90}}?"
        rf"\b(?:not\s+more\s+than|not\s+to\s+exceed|not\s+exceeding|"
        rf"no\s+more\s+than|up\s+to|maximum\s+(?:term\s+)?(?:of\s+)?)\s+"
        rf"({NUMBER})\s*({UNIT})\b",
        re.I | re.S,
    ),
    re.compile(
        rf"\b(?:imprisoned|imprisonment)\b.{{0,40}}?"
        rf"\bfor\s+(?:a\s+term\s+of\s+)?({NUMBER})\s*({UNIT})\b",
        re.I | re.S,
    ),
)

LIFE_OR_DEATH_PENALTY = re.compile(
    r"\b(?:punished\s+by\s+death|sentenced\s+to\s+death|"
    r"imprison(?:ed|ment)[^.;]{0,90}\b(?:for\s+)?life\b|"
    r"imprison(?:ed|ment)[^.;]{0,90}\bfor\s+any\s+term\s+of\s+years\s+or\s+(?:for\s+)?life\b)",
    re.I | re.S,
)


def _number(value: str) -> float | None:
    value = value.strip().lower().replace("–", "-").replace("—", "-")
    if value in NUMBER_WORDS:
        return float(NUMBER_WORDS[value])
    try:
        return float(value)
    except ValueError:
        return None


def _days(value: float, unit: str) -> float:
    unit = unit.lower()
    if unit.startswith("year"):
        return value * 365.0
    if unit.startswith("month"):
        return value * (365.0 / 12.0)
    return value


def classify_maximum_days(days: float) -> tuple[str, str, str]:
    """Return (grade, class letter, §3559 paragraph) for a finite maximum."""
    if days >= 25 * 365:
        return ("felony", "B", "18 U.S.C. § 3559(a)(2)")
    if days >= 10 * 365:
        return ("felony", "C", "18 U.S.C. § 3559(a)(3)")
    if days >= 5 * 365:
        return ("felony", "D", "18 U.S.C. § 3559(a)(4)")
    if days > 365:
        return ("felony", "E", "18 U.S.C. § 3559(a)(5)")
    if days > 6 * (365.0 / 12.0):
        return ("misdemeanor", "A", "18 U.S.C. § 3559(a)(6)")
    if days > 30:
        return ("misdemeanor", "B", "18 U.S.C. § 3559(a)(7)")
    if days > 5:
        return ("misdemeanor", "C", "18 U.S.C. § 3559(a)(8)")
    return ("infraction", "", "18 U.S.C. § 3559(a)(9)")


def derive_title18_class(text: str) -> dict[str, Any]:
    """Conservatively derive one Title 18 class from the section text.

    Returns a dict with ``automatic`` plus explanatory metadata. Automatic is
    true only if every detected custodial maximum resolves to the same class.
    """
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return {"automatic": False, "reason": "No operative statutory text is available for classification."}

    explicit = {
        (match.group(2).lower(), match.group(1).upper())
        for match in EXPLICIT_CLASS.finditer(text)
    }
    if explicit:
        if len(explicit) != 1:
            return {
                "automatic": False,
                "reason": "The section expressly contains more than one federal offense class.",
                "detected_classes": sorted(f"Class {letter} {grade}" for grade, letter in explicit),
            }
        grade, letter = next(iter(explicit))
        return {
            "automatic": True,
            "grade": grade,
            "class": letter,
            "display_class": f"Class {letter} {grade}",
            "classification_basis": "Express letter-grade classification in the defining section",
        }

    classes: set[tuple[str, str, str]] = set()
    detected_terms: set[str] = set()

    if LIFE_OR_DEATH_PENALTY.search(text):
        classes.add(("felony", "A", "18 U.S.C. § 3559(a)(1)"))
        detected_terms.add("life imprisonment or death")

    seen_spans: set[tuple[int, int]] = set()
    for pattern in MAX_TERM_PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if any(max(span[0], old[0]) < min(span[1], old[1]) for old in seen_spans):
                continue
            seen_spans.add(span)
            number = _number(match.group(1))
            if number is None:
                continue
            unit = match.group(2).lower()
            days = _days(number, unit)
            grade, letter, paragraph = classify_maximum_days(days)
            classes.add((grade, letter, paragraph))
            detected_terms.add(f"{match.group(1)} {unit}")

    if not classes:
        return {
            "automatic": False,
            "reason": (
                "No single maximum term of imprisonment could be reliably derived from the section text. "
                "The section may use a cross-reference, fine-only rule, or nonstandard penalty formulation."
            ),
        }

    grade_letters = {(grade, letter) for grade, letter, _ in classes}
    if len(grade_letters) != 1:
        return {
            "automatic": False,
            "reason": "The section contains penalty tiers that span more than one federal offense class.",
            "detected_classes": sorted(
                "Infraction" if grade == "infraction" else f"Class {letter} {grade}"
                for grade, letter in grade_letters
            ),
            "detected_maximum_terms": sorted(detected_terms),
        }

    grade, letter = next(iter(grade_letters))
    if grade == "infraction":
        return {
            "automatic": False,
            "reason": "The derived federal classification is an infraction, for which Public Law 39-267 supplies no custodial class rule.",
            "detected_maximum_terms": sorted(detected_terms),
        }

    paragraphs = sorted({paragraph for g, l, paragraph in classes if g == grade and l == letter})
    return {
        "automatic": True,
        "grade": grade,
        "class": letter,
        "display_class": f"Class {letter} {grade}",
        "classification_basis": paragraphs[0] if len(paragraphs) == 1 else "18 U.S.C. § 3559(a)",
        "detected_maximum_terms": sorted(detected_terms),
    }


def apply_title18_sentencing(entry: dict, detail: dict, sentencing_rules: dict) -> None:
    """Attach automatic PL39 sentencing metadata when §3559 classification is clear."""
    derived = derive_title18_class(str(detail.get("text") or ""))
    entry["title18_classification"] = derived

    if not derived.get("automatic"):
        entry["sentencing_mode"] = "manual_required"
        entry["sentencing_reason"] = derived.get("reason") or "Title 18 classification requires manual review."
        return

    grade = str(derived["grade"])
    letter = str(derived["class"])
    maximum = (sentencing_rules.get(grade) or {}).get(letter)
    if not isinstance(maximum, (int, float)):
        entry["sentencing_mode"] = "manual_required"
        entry["sentencing_reason"] = (
            f"{derived['display_class']} is derived under {derived['classification_basis']}, "
            "but Public Law 39-267 supplies no matching non-court sentencing rule."
        )
        return

    entry["offense_class"] = letter
    entry["offense_grade"] = grade
    entry["class_display"] = derived["display_class"]
    entry["class_rule"] = {
        "maximum_minutes": maximum,
        "scope": "Non-court-imposed sentencing only",
        "source": "Public Law 39-267 § 6" if grade == "felony" else "Public Law 39-267 § 7",
        "classification_source": derived["classification_basis"],
    }
    entry["sentencing_mode"] = "automatic_class_rule"
    entry["sentencing_range_minutes"] = {"min": 0, "max": maximum}
    entry["suggested_minutes"] = maximum
    entry["sentencing_reason"] = (
        f"{derived['display_class']} derived under {derived['classification_basis']}; "
        "non-court maximum taken from Public Law 39-267."
    )
