#!/usr/bin/env python3
"""Phase 5 audit: scan every title touched by the USAR codification round
for structural/formatting defects, without changing anything.

This is a read-only reporting tool. It never writes to any file. Findings
are for human review; nothing here is auto-applied.

Scope: the set of usc/usc*.xml files listed in any applied law's
"changed_files" in codification/state.json (read-only reference -- this
script never writes to state.json). If codification/state.json is not
present (e.g. a checkout that excludes local workbench tooling), the
script falls back to scanning every usc/usc*.xml file.

Checks performed per file:
  - XML is well-formed.
  - No duplicate `id` attribute values anywhere in the document.
  - No duplicate `identifier` attribute value where at least one of the
    colliding elements was added by this project's tooling (id starts with
    "rp-"). Plain duplicate identifiers elsewhere are common, legitimate
    pre-existing OLRC content -- e.g. a real drafting error preserved
    verbatim with a "So in original" footnote, or a <quotedContent> block
    that intentionally re-quotes a provision's identifier -- and are out of
    scope for this project.
  - Every USAR-added note (id starts with "rp-") has non-empty text.
  - No two USAR amendment notes in the same <notes> container cite the
    same public law + section (a sign a law was applied twice).
  - Every section touched by a USAR amendment note still has a
    <sourceCredit> element (only flagged if the section has other
    sourceCredit-adjacent content and is not reserved/repealed, since
    reserved sections never had one).
  - No placeholder tokens (TODO, FIXME, PLACEHOLDER, Lorem ipsum, TBD,
    XXXX) inside USAR-added content.
  - No empty <content>/<p> elements and no <subsection> missing a <num>
    inside USAR-added content.
  - Every <ref href="/us/usc/..."> inside USAR-added content resolves to
    an identifier that actually exists in the same title file.
  - Every element added by this project's tooling stays in the USLM
    namespace (no accidental default-namespace reset).

Stale <tocItem> headings are audited and repaired separately by
tools/sync_stale_toc_headings.py (it needs the same section/chapter-row
disambiguation logic as tools/rp_codifier.py's replace_toc_heading, so it
lives there instead of being duplicated here).

Usage:
    py -3 tools/audit_applied_material.py [path ...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
USC_DIR = ROOT / "usc"
STATE_PATH = ROOT / "codification" / "state.json"
USLM_NS = "http://xml.house.gov/schemas/uslm/1.0"
Q = lambda name: f"{{{USLM_NS}}}{name}"

PLACEHOLDER_TOKENS = ["TODO", "FIXME", "PLACEHOLDER", "LOREM IPSUM", "TBD", "XXXX"]


def default_scope() -> list[Path]:
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        files = set()
        for info in state.get("applied", {}).values():
            for f in info.get("changed_files", []):
                if f.replace("\\", "/").startswith("usc/") and f.endswith(".xml"):
                    files.add(ROOT / f.replace("\\", "/"))
        if files:
            return sorted(files)
    return sorted(USC_DIR.glob("usc*.xml"))


def is_lfs_pointer(path: Path) -> bool:
    with path.open("rb") as fh:
        return fh.read(60).startswith(b"version https://git-lfs.github.com")


def is_usar_id(value: str | None) -> bool:
    return bool(value) and value.startswith("rp-")


def audit_file(path: Path) -> list[str]:
    findings: list[str] = []
    if is_lfs_pointer(path):
        return [f"{path.name}: SKIPPED (LFS pointer, not materialized)"]

    try:
        tree = etree.parse(str(path), etree.XMLParser(huge_tree=True))
    except etree.XMLSyntaxError as exc:
        return [f"{path.name}: XML NOT WELL-FORMED: {exc}"]
    root = tree.getroot()

    # -- Duplicate id / identifier values -----------------------------------
    ids: dict[str, int] = {}
    identifiers: dict[str, list[etree._Element]] = {}
    for el in root.iter():
        eid = el.get("id")
        if eid:
            ids[eid] = ids.get(eid, 0) + 1
        eident = el.get("identifier")
        if eident:
            identifiers.setdefault(eident, []).append(el)
    for value, count in ids.items():
        if count > 1:
            findings.append(f"{path.name}: duplicate id={value!r} appears {count} times")
    for value, elements in identifiers.items():
        if len(elements) > 1 and any(is_usar_id(el.get("id")) for el in elements):
            findings.append(
                f"{path.name}: duplicate identifier={value!r} appears {len(elements)} times "
                "and at least one instance was added by this project"
            )

    # -- Build an identifier index for internal-ref resolution --------------
    known_identifiers = set(identifiers.keys())

    # -- Per-section checks --------------------------------------------------
    # (Stale TOC headings are audited and repaired separately by
    # tools/sync_stale_toc_headings.py, which correctly disambiguates
    # section-level TOC rows from chapter/part-level starting-section
    # references -- a naive href-to-first-match lookup here would
    # misidentify chapter summary rows as the section's own TOC entry.)
    for section in root.iter(Q("section")):
        section_id = section.get("identifier", "")
        heading_el = section.find(Q("heading"))
        section_heading = " ".join(heading_el.itertext()).strip() if heading_el is not None else ""

        notes_el = section.find(Q("notes"))
        usar_notes = []
        if notes_el is not None:
            for note in notes_el.findall(Q("note")):
                if is_usar_id(note.get("id")):
                    usar_notes.append(note)

        if not usar_notes:
            continue  # Not touched by USAR tooling; out of scope for these checks.

        # Empty USAR note content.
        for note in usar_notes:
            text = " ".join(note.itertext()).strip()
            if not text:
                findings.append(f"{path.name}: empty USAR note id={note.get('id')} in section {section_id}")

        # Duplicate amendment-note citations (same PL + section cited twice).
        seen_markers: dict[str, int] = {}
        for note in usar_notes:
            if note.get("topic") != "amendments":
                continue
            for ref in note.findall(Q("p") + "/" + Q("ref")):
                marker = (ref.text or "").strip()
                if marker:
                    seen_markers[marker] = seen_markers.get(marker, 0) + 1
        for marker, count in seen_markers.items():
            if count > 1:
                findings.append(
                    f"{path.name}: section {section_id} cites {marker!r} {count} times "
                    "(possible duplicate application)"
                )

        # Missing sourceCredit on a USAR-touched section that has other
        # substantive content (heuristic: has at least one subsection or
        # content paragraph, meaning it is a real, non-reserved section).
        # Reserved/repealed sections never carry a sourceCredit (there is no
        # operative text to cite a source for), so they are excluded here.
        normalized_heading = " ".join(section_heading.split())
        is_reserved = normalized_heading in ("[Reserved]", "[Repealed]") or section.get("status") == "repealed"
        has_body = bool(section.findall(Q("subsection")) or section.findall(Q("content")))
        source_credit = section.find(Q("sourceCredit"))
        if has_body and source_credit is None and not is_reserved:
            findings.append(
                f"{path.name}: section {section_id} has USAR amendment notes and a "
                "statutory body but no <sourceCredit> -- review whether one was lost"
            )

        # Placeholder tokens, empty content/p, subsections missing <num>,
        # namespace sanity, and broken internal refs -- scoped to the USAR
        # notes plus any USAR-added subsections/content in this section
        # (elements whose own id starts with "rp-").
        usar_elements = [el for el in section.iter() if is_usar_id(el.get("id"))]
        for el in usar_elements:
            text = " ".join(el.itertext())
            upper = text.upper()
            for token in PLACEHOLDER_TOKENS:
                if token in upper:
                    findings.append(
                        f"{path.name}: section {section_id} USAR element id={el.get('id')} "
                        f"contains placeholder-like token {token!r}"
                    )
            if el.tag == Q("content") and not text.strip() and len(el) == 0:
                findings.append(f"{path.name}: section {section_id} has an empty <content> (id={el.get('id')})")
            if el.tag == Q("p") and not text.strip() and len(el) == 0:
                findings.append(f"{path.name}: section {section_id} has an empty <p> (id={el.get('id')})")
            if el.tag == Q("subsection") and el.find(Q("num")) is None:
                findings.append(f"{path.name}: section {section_id} subsection id={el.get('id')} is missing <num>")
            if el.tag.startswith("{") and not el.tag.startswith("{" + USLM_NS + "}"):
                findings.append(f"{path.name}: section {section_id} USAR element id={el.get('id')} has wrong namespace: {el.tag}")
            for ref in el.iter(Q("ref")):
                href = ref.get("href", "")
                if href.startswith("/us/usc/") and href not in known_identifiers:
                    findings.append(
                        f"{path.name}: section {section_id} USAR ref href={href!r} does not "
                        "resolve to any identifier in this title"
                    )

    return findings


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    paths = [Path(p) for p in argv] if argv else default_scope()
    total = 0
    for path in paths:
        findings = audit_file(path)
        if findings:
            print(f"== {path.name} ==")
            for f in findings:
                print(f"  {f}")
            total += len([f for f in findings if "SKIPPED" not in f])
    print()
    print(f"{total} finding(s) across {len(paths)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
