#!/usr/bin/env python3
"""Compatibility entry point for the Roblox criminal-law API hardener.

This wrapper installs the production Title 18 charge classifier used by the
Roblox booking catalog, then runs the balanced content-safety hardener, narrow
section-level exclusions, and the Roblox-specific 20-minute booking cap.

The classifier is deliberately broader than the original exact-phrase matcher:
criminal statutes use many formulations (conditional penalties, cross-referenced
penalties, ``shall—`` penalty lists, ``is guilty of``, and substantive
``unlawful`` prohibitions). Safely named criminal charges should not disappear
merely because Congress used a different drafting form. Content safety remains a
separate step: unsafe displayed metadata is excluded, while unsafe body text is
withheld without deleting an otherwise safe charge.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import harden_roblox_criminal_api_v2 as hardener
from apply_roblox_api_exclusions import main as exclusions_main
from set_roblox_booking_cap import main as booking_cap_main


# Reject headings that BEGIN as framework/administrative provisions. Do not use
# a substring test here: legitimate criminal headings can contain words such as
# "jurisdiction", "penalties", "records", or "disclosure" descriptively (for
# example §§ 113, 1751, and 2511).
NON_CHARGE_HEADING = re.compile(
    r"^\s*(?:definitions?|definition of terms|defined|rules?|regulations?|reports?|"
    r"annual report|construction|applicability|effective dates?|jurisdiction|venue|"
    r"limitations?|limitation of actions|procedures?|administrative|authorization|"
    r"appropriations?|duties|powers|establishment|findings|severability|separability|"
    r"preemption|exceptions?|exemptions?|immunity|disclosure|records?|civil remedies?|"
    r"civil proceedings?|civil actions?|injunctions?|forfeitures?|restitution|"
    r"sentencing|penalties|penalty|definitions and rules|use of certain terms|"
    r"licensing|licenses? and user permits|laws? governing|exclusive remedies|"
    r"effect on state law)\b",
    re.I,
)

# These sections can contain offense vocabulary while functioning as liability,
# jurisdiction, or charging frameworks rather than independent offenses.
TITLE18_NON_CHARGE_SECTIONS = {
    "2",     # principals / derivative liability
    "1153",  # Indian-country jurisdiction and offense incorporation framework
}

# Ordinary criminal drafting forms. These are intentionally syntax-oriented,
# not subject-matter allowlists, so future offenses using the same forms are not
# silently dropped.
TITLE18_ACTOR_PATTERNS = (
    re.compile(r"\bwhoever\b", re.I),
    re.compile(r"\b(?:any|a|an|each|every)\s+(?:person|individual|citizen|driver)\b", re.I),
    re.compile(r"\btwo\s+or\s+more\s+persons?\b", re.I),
    re.compile(r"\b(?:person|individual)\s+who\b", re.I),
)

TITLE18_STRONG_OFFENSE_PATTERNS = (
    # Direct substantive prohibitions, including statutes whose penalty is in
    # another section of the same chapter.
    re.compile(r"\b(?:it\s+)?(?:is|shall\s+be)\s+unlawful\b", re.I),
    re.compile(r"\bno\s+person\s+shall\b", re.I),
    # Explicit declarations of criminal guilt, contempt, or offense class.
    re.compile(r"\b(?:shall\s+be|is|are)\s+guilty\s+of\b", re.I),
    re.compile(r"\bis\s+(?:a|an)\s+criminal\s+(?:contempt|offense)\b", re.I),
    re.compile(
        r"\b(?:is|are|shall\s+be)\s+subject\s+to\b.{0,180}"
        r"\b(?:felony|misdemeanor|criminal\s+offense)\b",
        re.I | re.S,
    ),
    re.compile(
        r"\b(?:shall\s+be|is|are)\s+punishable\s+by\b.{0,300}"
        r"\b(?:fine|imprisonment)\b",
        re.I | re.S,
    ),
)

TITLE18_PENALTY_PATTERNS = (
    # Covers normal, conditional, parenthetical, and em-dash penalty syntax:
    #   shall be fined
    #   shall, if ..., be fined
    #   shall, subject to ..., be fined
    #   shall— (1) ... be fined / imprisoned
    re.compile(
        r"\bshall\b(?:(?!\bshall\b).){0,560}?"
        r"\b(?:be\s+)?(?:fined|imprisoned|punished|sentenced)\b",
        re.I | re.S,
    ),
    re.compile(r"\b(?:is|are|shall\s+be)\s+guilty\s+of\b", re.I),
    # Conflict-of-interest and similar provisions often incorporate a penalty
    # section instead of restating the punishment.
    re.compile(
        r"\bshall\s+be\s+subject\s+to\b.{0,260}?\bpenalt(?:y|ies)\b",
        re.I | re.S,
    ),
    re.compile(
        r"\b(?:shall\s+be|is|are)\s+punishable\s+by\b.{0,300}"
        r"\b(?:fine|imprisonment)\b",
        re.I | re.S,
    ),
)

# The original classifier already has a small set of charges whose complex
# cross-references make any text-only recognition rule unnecessarily brittle.
# Keep that escape hatch, and include §751 as a permanent regression guard.
hardener.KNOWN_TITLE18_CHARGES.add("751")

# "Intoxicant" is an alternate label for the already-blocked regulated-
# intoxicant category. Treat it the same way so a synonym cannot bypass the
# display-safety policy.
if not any(label == "regulated-intoxicants-alias" for label, _ in hardener.BLOCKED_PATTERNS):
    hardener.BLOCKED_PATTERNS = (
        *hardener.BLOCKED_PATTERNS,
        ("regulated-intoxicants-alias", re.compile(r"\bintoxicants?\b", re.I)),
    )


def title18_is_positive_charge(detail: dict) -> bool:
    """Return True for a positively identified current Part I criminal charge.

    This remains fail-closed: framework/non-charge headings are excluded, and a
    section must either be a known charge, contain an unmistakable substantive
    prohibition/offense declaration, or combine an actor formulation with a
    criminal penalty formulation.
    """
    if detail.get("status") != "current" or not detail.get("charge_candidate"):
        return False

    heading = str(detail.get("heading") or "")
    body = str(detail.get("text") or "")
    section = str(detail.get("section") or "")

    if not body.strip():
        return False
    if section in TITLE18_NON_CHARGE_SECTIONS:
        return False
    # Check known positive charges before the heading guard. A descriptive
    # heading must never make an already-audited offense disappear.
    if section in hardener.KNOWN_TITLE18_CHARGES:
        return True
    if NON_CHARGE_HEADING.search(heading):
        return False
    if any(pattern.search(body) for pattern in TITLE18_STRONG_OFFENSE_PATTERNS):
        return True

    return (
        any(pattern.search(body) for pattern in TITLE18_ACTOR_PATTERNS)
        and any(pattern.search(body) for pattern in TITLE18_PENALTY_PATTERNS)
    )


# Install the generalized classifier into the existing hardening engine. This
# keeps the safety/output machinery in one place while replacing only the
# brittle recognition step.
hardener.NON_CHARGE_HEADING = NON_CHARGE_HEADING
hardener.TITLE18_ACTOR_PATTERNS = TITLE18_ACTOR_PATTERNS
hardener.TITLE18_PENALTY_PATTERNS = TITLE18_PENALTY_PATTERNS
hardener.title18_is_positive_charge = title18_is_positive_charge


# Regression set spans the exact false-negative families found in the source
# audit: descriptive headings, conditional penalties, body-only safety hits,
# incorporated penalties, direct prohibitions, and older drafting styles.
REQUIRED_TITLE18_CHARGES = {
    "81", "113", "241", "371", "752", "956", "1001", "1031", "1113",
    "1121", "1501", "1505", "1751", "1962", "2119", "2384", "2511",
}
OBVIOUS_NON_CHARGES = {"5", "17", "2518"}


def audit_charge_coverage() -> None:
    """Fail CI if representative legitimate charges disappear again."""
    path = Path(__file__).resolve().parents[1] / "data" / "api" / "v1" / "criminal-law" / "charges.json"
    if not path.is_file():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    present = {
        str(item.get("section") or "")
        for item in payload.get("charges", [])
        if item.get("source") == "title18"
    }

    missing = sorted(REQUIRED_TITLE18_CHARGES - present)
    if missing:
        raise RuntimeError(
            "Title 18 charge coverage audit failed; legitimate charges were filtered out: "
            + repr(missing)
        )

    leaked = sorted(OBVIOUS_NON_CHARGES & present)
    if leaked:
        raise RuntimeError(
            "Title 18 charge coverage audit failed; obvious non-charge sections were exposed: "
            + repr(leaked)
        )


def main() -> int:
    result = hardener.main()
    if result not in (None, 0):
        return int(result)
    result = exclusions_main()
    if result not in (None, 0):
        return int(result)
    result = booking_cap_main()
    if result not in (None, 0):
        return int(result)
    audit_charge_coverage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
