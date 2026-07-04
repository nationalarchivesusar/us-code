#!/usr/bin/env python3
"""Encoding audit for USAR-modified U.S. Code XML.

Hard failures (exit 1):
  - Any literal Unicode replacement character (U+FFFD) anywhere in a title
    file. Properly UTF-8-encoded text should never contain one; its presence
    means some upstream step lost data it could not recover.
  - Any of a known set of mojibake byte/character sequences that result from
    reading correctly UTF-8-encoded punctuation as if it were Latin-1/cp1252
    and re-saving it (e.g. a right single quotation mark turning into a
    three-character garbage sequence). These indicate a double-encoding bug,
    not intentional content, and are generated programmatically below rather
    than typed as literal source text, so this file never itself has to
    contain the very mojibake sequences it is trying to detect.

Informational only (never fails the build):
  - A count of literal "?" characters outside XML processing instructions,
    per file. Real OLRC content legitimately contains genuine question marks
    (quoted historical questions, IFP-affidavit forms with "Yes/No?"
    checkboxes, etc.), so this is reported for human review rather than
    treated as an automatic failure. Phase 2 of the post-codification cleanup
    manually reviewed and fixed every instance introduced by this project's
    own codification fragments (3 U.S.C. 19; 5 U.S.C. 3345-3349e; 5 U.S.C.
    5332); this check exists to catch any future regression of the same
    kind before it reaches the live Code.

Usage:
    py -3 tools/check_encoding.py [path ...]
       (defaults to every usc/usc*.xml file if no paths are given)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USC_DIR = ROOT / "usc"

REPLACEMENT_CHAR = "�"


def _mojibake(codepoint: int) -> str:
    """The garbage string produced when a correctly UTF-8-encoded character
    is later mis-decoded as Latin-1/cp1252 and re-saved. Latin-1 maps every
    byte 0x00-0xFF to a character, so this never raises, unlike cp1252 which
    leaves a handful of bytes (e.g. 0x81, 0x8D, 0x9D) undefined."""
    return chr(codepoint).encode("utf-8").decode("latin-1")


# Common mojibake sequences: a correctly UTF-8-encoded punctuation mark that
# was later decoded as Latin-1/cp1252 and re-saved, producing multi-character
# garbage in place of a single real character.
MOJIBAKE_PATTERNS = [
    (_mojibake(0x2019), "right single quotation mark (U+2019) double-encoded"),
    (_mojibake(0x2018), "left single quotation mark (U+2018) double-encoded"),
    (_mojibake(0x201C), "left double quotation mark (U+201C) double-encoded"),
    (_mojibake(0x201D), "right double quotation mark (U+201D) double-encoded"),
    (_mojibake(0x2014), "em dash (U+2014) double-encoded"),
    (_mojibake(0x2013), "en dash (U+2013) double-encoded"),
    (_mojibake(0x202F), "narrow no-break space (U+202F) double-encoded"),
    (_mojibake(0x00A7), "section symbol (U+00A7) double-encoded"),
]

PI_RE = re.compile(r"<\?.*?\?>", re.DOTALL)


def scan_file(path: Path) -> tuple[list[str], int]:
    """Return (hard_failures, informational_question_mark_count)."""
    with path.open("r", encoding="utf-8", errors="surrogateescape") as fh:
        first = fh.readline()
    if first.startswith("version https://git-lfs.github.com"):
        return [], 0

    text = path.read_text(encoding="utf-8")
    failures = []

    if REPLACEMENT_CHAR in text:
        count = text.count(REPLACEMENT_CHAR)
        idx = text.find(REPLACEMENT_CHAR)
        failures.append(
            f"{count} Unicode replacement character(s) (U+FFFD); first near: "
            f"{text[max(0, idx - 40):idx + 10]!r}"
        )

    for pattern, description in MOJIBAKE_PATTERNS:
        if pattern in text:
            count = text.count(pattern)
            idx = text.find(pattern)
            failures.append(
                f"{count} occurrence(s) of mojibake pattern ({description}); first near: "
                f"{text[max(0, idx - 40):idx + 10]!r}"
            )

    stripped = PI_RE.sub("", text)
    question_marks = stripped.count("?")

    return failures, question_marks


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    paths = [Path(p) for p in argv] if argv else sorted(USC_DIR.glob("usc*.xml"))

    total_failures = 0
    info_lines = []
    for path in paths:
        failures, question_marks = scan_file(path)
        if failures:
            total_failures += len(failures)
            print(f"FAIL: {path}")
            for f in failures:
                print(f"    {f}")
        if question_marks:
            info_lines.append(
                f"  {path.name}: {question_marks} literal '?' outside XML processing instructions"
            )

    if info_lines:
        print("\nInformational (not a failure -- review manually if any of these are new):")
        print("\n".join(info_lines))

    print()
    if total_failures:
        print(f"{total_failures} hard encoding failure(s) found.")
        return 1
    print("No replacement characters or known mojibake patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
