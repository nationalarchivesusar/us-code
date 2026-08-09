#!/usr/bin/env python3
"""Shared robustness patch for the Roblox-facing Title 18 charge classifier.

The generated Title 18 source uses several perfectly ordinary criminal drafting
forms that the original strict classifier did not recognize, for example:

- ``shall, if ..., be fined``
- ``shall, for each offense, be fined``
- ``shall—(1) be fined ...``
- ``shall be subject to the penalties set forth in section ...``
- ``shall be sentenced to ...``
- ``is subject to a misdemeanor offense punishable by ...``

This module broadens only the positive criminal-offense grammar. It does not
relax any Roblox content-safety rule. It also makes the primary body-withholding
pass aware of the secondary safety vocabulary, so a safely named charge is not
later deleted merely because restricted wording appeared only in its statutory
body.
"""
from __future__ import annotations

import re
from types import ModuleType

from finalize_roblox_criminal_api import SECONDARY_BLOCKED


EXTRA_ACTOR_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:any|an)\s+individual\s+who\b", re.I),
    re.compile(r"\ba\s+person\s+that\b", re.I),
    re.compile(r"\b(?:a|the)\s+respondent\s+who\b", re.I),
    re.compile(r"\b(?:a|the)\s+provider\s+that\b", re.I),
)

# Keep these high-confidence. An actor signal is still required, and the
# existing NON_CHARGE_HEADING guard continues to reject definitions,
# procedures, sentencing-only provisions, etc.
EXTRA_PENALTY_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Covers intervening conditions/qualifiers and em-dash lists:
    #   shall, if ..., be fined
    #   shall, for each offense, be fined
    #   shall—(1) be fined
    #   shall, subject to ..., be fined
    re.compile(
        r"\bshall\b.{0,500}?\b(?:be\s+)?(?:fined|imprisoned|punished|sentenced)\b",
        re.I | re.S,
    ),
    # Cross-referenced criminal penalties, common in the conflicts chapter.
    re.compile(
        r"\bshall\s+be\s+subject\s+to\s+(?:the\s+)?(?:same\s+)?penalt(?:y|ies)\b",
        re.I,
    ),
    re.compile(r"\bshall\s+be\s+guilty\s+of\b", re.I),
    # USAR-added provisions may express the grade first and punishment second.
    re.compile(
        r"\bis\s+subject\s+to\s+(?:an?\s+)?(?:felony|misdemeanor)\s+offense\s+"
        r"punishable\s+by\b",
        re.I,
    ),
)


def _extend_unique(
    existing: tuple[re.Pattern[str], ...],
    additions: tuple[re.Pattern[str], ...],
) -> tuple[re.Pattern[str], ...]:
    keys = {(pattern.pattern, pattern.flags) for pattern in existing}
    result = list(existing)
    for pattern in additions:
        key = (pattern.pattern, pattern.flags)
        if key not in keys:
            result.append(pattern)
            keys.add(key)
    return tuple(result)


def install(hardener: ModuleType) -> None:
    """Install the robust classifier/safety behavior into the primary hardener."""
    hardener.TITLE18_ACTOR_PATTERNS = _extend_unique(
        tuple(hardener.TITLE18_ACTOR_PATTERNS), EXTRA_ACTOR_PATTERNS
    )
    hardener.TITLE18_PENALTY_PATTERNS = _extend_unique(
        tuple(hardener.TITLE18_PENALTY_PATTERNS), EXTRA_PENALTY_PATTERNS
    )

    # The secondary pass historically deleted a whole charge when secondary-only
    # vocabulary occurred in the body. Feed that vocabulary into the primary
    # body-withholding pass instead. Metadata is still rejected when unsafe.
    existing_blocked = {
        (pattern.pattern, pattern.flags)
        for _, pattern in hardener.BLOCKED_PATTERNS
    }
    blocked = list(hardener.BLOCKED_PATTERNS)
    for index, pattern in enumerate(SECONDARY_BLOCKED, start=1):
        key = (pattern.pattern, pattern.flags)
        if key not in existing_blocked:
            blocked.append((f"secondary-safety-{index}", pattern))
            existing_blocked.add(key)
    hardener.BLOCKED_PATTERNS = tuple(blocked)

    def robust_title18_is_positive_charge(detail: dict) -> bool:
        if detail.get("status") != "current" or not detail.get("charge_candidate"):
            return False

        heading = str(detail.get("heading") or "")
        body = str(detail.get("text") or "")
        section = str(detail.get("section") or "")
        if not body.strip() or hardener.NON_CHARGE_HEADING.search(heading):
            return False

        if section in hardener.KNOWN_TITLE18_CHARGES:
            return True

        return (
            any(pattern.search(body) for pattern in hardener.TITLE18_ACTOR_PATTERNS)
            and any(pattern.search(body) for pattern in hardener.TITLE18_PENALTY_PATTERNS)
        )

    hardener.title18_is_positive_charge = robust_title18_is_positive_charge
