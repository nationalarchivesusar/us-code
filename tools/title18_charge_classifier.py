#!/usr/bin/env python3
"""Conservative positive classifier for Title 18 booking charges.

The Roblox API exposes only sections that positively define or prohibit criminal
conduct. The classifier recognizes common drafting styles throughout Title 18,
including conditional penalty clauses, split prohibition/penalty sections, and
older subject formulations, without treating every Part I section as a charge.
"""
from __future__ import annotations

import re

# Unambiguous offense sections retained even when their headings or drafting
# style resemble otherwise administrative wording.
KNOWN_TITLE18_CHARGES = {
    "111",   # assaulting/resisting/impeding certain officers
    "113",   # assaults within maritime/territorial jurisdiction
    "751",   # escape
    "1111",  # murder
    "1112",  # manslaughter
    "1201",  # kidnapping
    "2113",  # bank robbery and incidental crimes
}

# Only reject headings that BEGIN with genuinely administrative/non-charge
# labels. The former substring rule incorrectly dropped offenses merely because
# a descriptive heading contained words such as "jurisdiction", "penalties",
# "records", or "disclosure".
NON_CHARGE_HEADING = re.compile(
    r"^\s*(?:"
    r"definitions?\b|definition of\b|use of certain terms\b|"
    r"rules?\b|regulations?\b|reports?\b|annual report\b|construction\b|"
    r"applicability\b|effective dates?\b|jurisdiction\b|venue\b|"
    r"limitations?\b|limitation of actions\b|procedures?\b|procedure\b|"
    r"administrative\b|authorization\b|appropriations?\b|duties\b|powers?\b|"
    r"establishment\b|findings\b|severability\b|preemption\b|exceptions?\b|"
    r"immunity\b|civil remedies?\b|civil actions?\b|civil proceedings?\b|"
    r"injunctions?\b|forfeiture\b|(?:mandatory\s+)?restitution\b|sentencing\b|"
    r"(?:criminal\s+|enhanced\s+|civil\s+)?penalt(?:y|ies)\b|"
    r"record(?:\s|-)?keeping\b|remedies\b|exclusive remedies\b|effect on\b|"
    r"presumptions?\b|separability\b|laws governing\b|"
    r"offenses committed within indian country\b"
    r")",
    re.I,
)

TITLE18_ACTOR_PATTERNS = (
    re.compile(r"\bwhoever\b", re.I),
    re.compile(r"\bany\s+person\s+who\b", re.I),
    re.compile(r"\ba\s+person\s+who\b", re.I),
    re.compile(r"\bit\s+shall\s+be\s+unlawful\s+for\b", re.I),
    re.compile(r"\bno\s+person\s+shall\b", re.I),
    re.compile(r"\bif\s+(?:two|2)\s+or\s+more\s+persons\b", re.I),
    # Older and specialized sections often name a regulated actor instead of
    # using "whoever" (for example a driver, officer, citizen, or depositary).
    re.compile(
        r"\b(?:a|an|any|each|every)\s+"
        r"(?:(?![.;]).){0,160}?"
        r"(?:person|individual|officer|employee|driver|citizen|corporation|"
        r"association|owner|operator|captain|engineer|pilot|depositary|preparer|"
        r"carrier|master)\b",
        re.I | re.S,
    ),
)

TITLE18_PENALTY_PATTERNS = (
    # Handles "shall, if ..., be fined", "shall, except ..., be fined",
    # "shall—(1) be imprisoned", "shall each be fined", and similar variants.
    re.compile(
        r"\bshall\b(?:(?![.;]).){0,700}?\b(?:each\s+)?(?:be\s+)?"
        r"(?:fined|imprisoned|punished|sentenced)\b",
        re.I | re.S,
    ),
    re.compile(r"\b(?:is|are)\s+guilty\s+of\b", re.I),
    re.compile(r"\b(?:is|are|shall\s+be)\s+punishable\s+by\b", re.I),
    re.compile(
        r"\bshall\b(?:(?![.;]).){0,450}?\bsubject\s+to\b"
        r"(?:(?![.;]).){0,240}?\bpenalt(?:y|ies)\b",
        re.I | re.S,
    ),
    re.compile(r"\bshall\s+(?:each\s+)?suffer\s+death\b", re.I),
)

# Some criminal chapters separate the prohibition from the punishment. These
# sections are still chargeable even though the penalty lives in a neighboring
# section (for example headings such as "Unlawful acts" or "Prohibited
# activities").
STANDALONE_PROHIBITION_HEADING = re.compile(
    r"\b(?:unlawful|prohibited|prohibition)\b",
    re.I,
)
STANDALONE_PROHIBITION_BODY = re.compile(
    r"\b(?:it\s+shall\s+be\s+unlawful\s+for|no\s+person\s+shall)\b",
    re.I,
)


def title18_is_positive_charge(detail: dict) -> bool:
    """Return True only for a positively identified current criminal charge."""
    if detail.get("status") != "current" or not detail.get("charge_candidate"):
        return False

    heading = str(detail.get("heading") or "")
    body = str(detail.get("text") or "")
    section = str(detail.get("section") or "")
    if not body.strip():
        return False

    # Known charges must be checked before the negative heading screen. This
    # prevents descriptive offense headings such as §113's "... jurisdiction"
    # wording from being rejected.
    if section in KNOWN_TITLE18_CHARGES:
        return True

    if NON_CHARGE_HEADING.search(heading):
        return False

    if (
        any(pattern.search(body) for pattern in TITLE18_ACTOR_PATTERNS)
        and any(pattern.search(body) for pattern in TITLE18_PENALTY_PATTERNS)
    ):
        return True

    return bool(
        STANDALONE_PROHIBITION_HEADING.search(heading)
        and STANDALONE_PROHIBITION_BODY.search(body)
    )
