#!/usr/bin/env python3
"""Compatibility entry point for the Roblox criminal-law API hardener.

This wrapper installs the production Title 18 charge classifier used by the
Roblox booking catalog, then runs the balanced content-safety hardener, narrow
section-level exclusions, and the Roblox-specific 20-minute booking cap.

The classifier is deliberately broader than an exact-phrase matcher: criminal
statutes use conditional penalties, cross-referenced penalties, ``shall—``
penalty lists, guilt declarations, direct prohibitions, older actor labels, and
headings whose ordinary words can also occur in administrative provisions.
Safely named criminal charges should not disappear merely because Congress used
one of those drafting forms. Content safety remains a separate step: unsafe
displayed metadata is excluded, while unsafe body text is withheld without
deleting an otherwise safe charge.
"""
from __future__ import annotations

import re

import harden_roblox_criminal_api_v2 as hardener
from apply_roblox_api_exclusions import main as exclusions_main
from set_roblox_booking_cap import main as booking_cap_main


# Reject headings only when they are clearly framework/remedy provisions. The
# former substring rule was too broad: it treated words such as "jurisdiction",
# "records", "disclosure", "regulations", and "penalties" as disqualifying no
# matter where they appeared, which incorrectly removed substantive offenses
# such as §§ 81, 113, 641, 798, 1751, and 2511.
CLEARLY_NON_CHARGE_HEADING = re.compile(
    r"^\s*(?:"
    r"definitions?\b|definition of(?:\s+terms)?\b|"
    r"rules?(?:\s+and\s+regulations?)?\b|regulations?\b|annual report\b|"
    r"construction\b|applicability\b|effective dates?\b|"
    r"jurisdiction(?:\s+and\s+venue)?\b|venue\b|limitations?\b|"
    r"limitation of actions\b|procedures?\b|administrative\b|authorization\b|"
    r"appropriations?\b|duties(?:\s+and\s+powers)?\b|powers?\b|"
    r"establishment\b|findings\b|severability\b|separability\b|"
    r"preemption\s*$|exceptions?\b|exemptions?\b|immunity\b|"
    r"civil\s+(?:remedies?|proceedings?|actions?|penalties?)\b|"
    r"injunctions?\b|(?:criminal\s+)?forfeitures?\b|"
    r"seizure,\s*forfeiture\b|(?:mandatory\s+)?restitution\b|sentencing\b|"
    r"licensing\b|licenses?\s+and\s+user\s+permits\b|laws?\s+governing\b|"
    r"exclusive\s+remedies\b|effect\s+on\s+state\s+law\b|"
    r"general\s+rules?\s+for\s+civil\s+forfeiture\b|"
    r"record(?:\s|-)?keeping\b|reporting\s+requirements?\b|"
    r"enhanced\s+penalties\b|criminal\s+penalties\s*$|"
    r"penalties(?:\s+and\s+injunctions)?\s*$|penalty\s+when\b"
    r")",
    re.I,
)
DEFINED_HEADING = re.compile(r"\bdefined\s*$", re.I)

# These provisions can contain offense vocabulary but function as incorporation,
# derivative-liability, or jurisdiction frameworks rather than independent
# section-level booking charges.
TITLE18_NON_CHARGE_SECTIONS = {
    "2",     # principals / derivative liability
    "13",    # Assimilative Crimes Act; incorporates another jurisdiction's offense
    "1153",  # Indian-country jurisdiction and offense-incorporation framework
}

# Ordinary criminal drafting forms. Include role nouns used by older statutes so
# a charge is not lost just because the subject is "every officer" or another
# regulated actor rather than "whoever".
TITLE18_ACTOR_PATTERNS = (
    re.compile(r"\bwhoever\b", re.I),
    re.compile(
        r"\b(?:any|a|an|each|every)\s+"
        r"(?:person|individual|citizen|driver|officer|employee|owner|operator|"
        r"captain|engineer|pilot|depositary|preparer|carrier|master|corporation|"
        r"association)\b",
        re.I,
    ),
    re.compile(r"\b(?:two|2)\s+or\s+more\s+persons?\b", re.I),
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
    # Keep this person-specific so civil/property forfeiture provisions do not
    # become false charges merely because they mention a felony elsewhere.
    re.compile(
        r"\b(?:person|individual)\b.{0,120}"
        r"\b(?:is|shall\s+be)\s+subject\s+to\b.{0,160}"
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
        r"\bshall\b(?:(?!\bshall\b).){0,700}?"
        r"\b(?:each\s+)?(?:be\s+)?(?:fined|imprisoned|punished|sentenced)\b",
        re.I | re.S,
    ),
    re.compile(r"\b(?:is|are|shall\s+be)\s+guilty\s+of\b", re.I),
    # Incorporated criminal-penalty clauses are valid, but a provision saying
    # only that somebody is subject to a *civil* penalty is not a booking charge.
    re.compile(
        r"\bshall\s+be\s+subject\s+to\b"
        r"(?![^.;]{0,100}\bcivil\b).{0,260}?\bpenalt(?:y|ies)\b",
        re.I | re.S,
    ),
    re.compile(
        r"\b(?:shall\s+be|is|are)\s+punishable\s+by\b.{0,300}"
        r"\b(?:fine|imprisonment)\b",
        re.I | re.S,
    ),
    re.compile(r"\bshall\b.{0,120}\bsuffer\s+death\b", re.I | re.S),
)

# The underlying hardener already has a small set of charges whose complex
# cross-references make any text-only recognition rule unnecessarily brittle.
# §751 is the original conditional-penalty regression. §2332 is also genuinely
# substantive despite the otherwise penalty-like heading "Criminal penalties."
hardener.KNOWN_TITLE18_CHARGES.update({"751", "2332"})

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

    This remains fail-closed: known framework sections and clearly administrative
    headings are excluded, and everything else must have unmistakable offense or
    criminal-penalty syntax.
    """
    if detail.get("status") != "current" or not detail.get("charge_candidate"):
        return False

    heading = str(detail.get("heading") or "")
    body = str(detail.get("text") or "")
    section = str(detail.get("section") or "")

    if not body.strip() or section in TITLE18_NON_CHARGE_SECTIONS:
        return False

    # Known positives must precede the heading screen. §113, for example, is an
    # assault offense whose descriptive heading happens to contain "jurisdiction".
    if section in hardener.KNOWN_TITLE18_CHARGES:
        return True

    if CLEARLY_NON_CHARGE_HEADING.search(heading) or DEFINED_HEADING.search(heading):
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
hardener.NON_CHARGE_HEADING = CLEARLY_NON_CHARGE_HEADING
hardener.TITLE18_ACTOR_PATTERNS = TITLE18_ACTOR_PATTERNS
hardener.TITLE18_PENALTY_PATTERNS = TITLE18_PENALTY_PATTERNS
hardener.title18_is_positive_charge = title18_is_positive_charge


def main() -> int:
    result = hardener.main()
    if result not in (None, 0):
        return int(result)
    result = exclusions_main()
    if result not in (None, 0):
        return int(result)
    result = booking_cap_main()
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
