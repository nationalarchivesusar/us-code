#!/usr/bin/env python3
"""Phase 6 engine (dry-run-capable): precisely locate every rp-pl* codification note in usc/*.xml
and support three ledger-driven operations per note:
  - REMOVE  : delete the note entirely (law excluded, no note warranted)
  - CLEAN   : rewrite to a concise honest statutory note (strip quotedContent dump, trello link,
              and false source-limitation boilerplate; keep heading + Status + Codification + SHA)
  - KEEP    : leave as-is (rare)
Direct textual amendments are handled separately by hand-authored edits, not here.

This module is import-safe and, run directly, performs a DRY RUN: it reports what it would do
using a trivial default policy (CLEAN all), writing nothing. The real run is driven by the ledger.
"""
import json, os, re, glob

ROOT = r"D:/us-code"
USC = os.path.join(ROOT, "usc")

NOTE_RE = re.compile(r'<note\b[^>]*\bid="(rp-pl(\d{3})(\d{3})[^"]*)"[^>]*>.*?</note>', re.DOTALL)
HEADING_RE = re.compile(r'(<heading\b[^>]*>.*?</heading>)', re.DOTALL)
SHA_RE = re.compile(r'([0-9a-fA-F]{64})')
TRELLO_P = re.compile(r'<p>\s*<b>\s*Archive record\.?\s*</b>.*?</p>', re.DOTALL)
LIMIT_P = re.compile(r'<p>\s*<b>\s*Source limitation\.?\s*</b>.*?</p>', re.DOTALL)
QUOTED_RE = re.compile(r'<quotedContent\b.*?</quotedContent>', re.DOTALL)
STATUS_P = re.compile(r'<p>\s*<b>\s*Status\.?\s*</b>\s*(.*?)</p>', re.DOTALL)


def find_notes(text):
    return list(NOTE_RE.finditer(text))


def clean_note(note_xml, new_status=None, new_codif=None):
    """Return a cleaned note: drop quotedContent, trello 'Archive record' <p>, and false
    'Source limitation' <p>. Optionally override Status/Codification text."""
    s = note_xml
    s = QUOTED_RE.sub("", s)
    s = TRELLO_P.sub("", s)
    s = LIMIT_P.sub("", s)
    # collapse any doubled whitespace between tags
    s = re.sub(r'>\s+<', '><', s)
    if new_status is not None:
        s = STATUS_P.sub(f'<p><b>Status.</b> {new_status}</p>', s, count=1)
    return s


def analyze():
    rows = []
    for path in sorted(glob.glob(os.path.join(USC, "usc*.xml"))):
        text = open(path, encoding="utf-8", errors="replace").read()
        for m in find_notes(text):
            nx = m.group(0)
            rows.append({
                "file": os.path.basename(path),
                "note_id": m.group(1),
                "has_quoted": bool(QUOTED_RE.search(nx)),
                "has_trello": bool(TRELLO_P.search(nx)),
                "has_limitation": bool(LIMIT_P.search(nx)),
                "orig_len": len(nx),
                "clean_len": len(clean_note(nx)),
            })
    return rows


if __name__ == "__main__":
    rows = analyze()
    tot = len(rows)
    dumps = sum(r["has_quoted"] for r in rows)
    trello = sum(r["has_trello"] for r in rows)
    limit = sum(r["has_limitation"] for r in rows)
    saved = sum(r["orig_len"] - r["clean_len"] for r in rows)
    print(f"notes located: {tot}")
    print(f"  with quotedContent dump: {dumps}")
    print(f"  with trello Archive record <p>: {trello}")
    print(f"  with Source limitation <p>: {limit}")
    print(f"  chars removed if all CLEANed: {saved:,}")
    # show 3 before/after samples
    for path in sorted(glob.glob(os.path.join(USC, "usc*.xml")))[:1]:
        text = open(path, encoding="utf-8", errors="replace").read()
        for m in find_notes(text)[:1]:
            nx = m.group(0)
            print("\n--- SAMPLE ORIG (first 500) ---\n", nx[:500])
            print("\n--- SAMPLE CLEAN (first 500) ---\n", clean_note(nx)[:500])
