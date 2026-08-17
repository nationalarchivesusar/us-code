#!/usr/bin/env python3
"""Canonicalize U.S. Code targets emitted by the codification audit.

The historical audit contains a small number of records whose
``final_section_or_subsection_identifier`` field names more than one target
using `` | ``.  It also contains legacy ``?`` placeholders where the live
USLM source uses a dash in section identifiers (for example ``2000e?2`` for
``2000e–2``).

Public-facing datasets must never guess those strings into a nearby section.
This module resolves them against the section identifiers that actually exist
in the current ``usc/*.xml`` corpus and expands compound identifiers into one
canonical target per section.
"""

from __future__ import annotations

import copy
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SECTION_PATH_RE = re.compile(
    r"/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/\"'<>&?#\s]+)",
    re.IGNORECASE,
)
SECTION_IDENTIFIER_RE = re.compile(
    r"^/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/|\s]+)(?P<rest>/.*)?$",
    re.IGNORECASE,
)
COMPOUND_SEPARATOR_RE = re.compile(r"\s*\|\s*")
DASHES = ("–", "—", "−", "‑", "‒")


def normalize_title(value: Any) -> str:
    text = str(value or "").strip()
    if text.isdigit():
        return str(int(text))
    stripped = text.lstrip("0")
    return stripped or "0"


def fold_section_token(value: Any) -> str:
    """Return a comparison key that treats legacy dash spellings alike."""
    text = str(value or "").strip()
    text = re.sub(r"(?<=[0-9A-Za-z])\?(?=[0-9A-Za-z])", "-", text)
    for dash in DASHES:
        text = text.replace(dash, "-")
    return text


def section_lookup_key(value: Any) -> str:
    return fold_section_token(value).lower()


def build_section_index(usc_dir: Path) -> dict[str, dict[str, str]]:
    """Map exact and dash-folded section aliases to canonical USLM tokens."""
    index: dict[str, dict[str, str]] = defaultdict(dict)
    for path in sorted(usc_dir.glob("usc*.xml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in SECTION_PATH_RE.finditer(text):
            title = normalize_title(match.group("title"))
            section = match.group("section").rstrip(".,;:|)]}")
            aliases = index[title]
            aliases.setdefault(section.lower(), section)
            aliases.setdefault(section_lookup_key(section), section)
    return index


def resolve_canonical_section(
    title: Any,
    section: Any,
    section_index: dict[str, dict[str, str]],
) -> str | None:
    title_key = normalize_title(title)
    value = str(section or "").strip()
    if not value:
        return None
    known = section_index.get(title_key, {})
    return known.get(value.lower()) or known.get(section_lookup_key(value))


def split_compound_identifier(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in COMPOUND_SEPARATOR_RE.split(text) if part.strip()]


def parse_section_identifier(
    value: Any,
    section_index: dict[str, dict[str, str]],
) -> dict[str, str] | None:
    """Parse one audit target and replace its section token with live canonical text."""
    text = str(value or "").strip()
    match = SECTION_IDENTIFIER_RE.match(text)
    if not match:
        return None
    title = normalize_title(match.group("title"))
    raw_section = match.group("section")
    canonical = resolve_canonical_section(title, raw_section, section_index)
    section = canonical or fold_section_token(raw_section)
    rest = match.group("rest") or ""
    return {
        "title": title,
        "section": section,
        "rest": rest,
        "identifier": f"/us/usc/t{title}/s{section}{rest}",
    }


def expand_authoritative_targets(
    targets: Iterable[dict[str, Any]],
    section_index: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Expand an explicit compound identifier and discard inference fallbacks.

    ``build_public_laws_index`` intentionally gathers fallback targets from node
    IDs and prose.  When the audit itself provides a compound final identifier,
    however, that explicit list is more authoritative than those fallbacks.
    Keeping both is what previously turned 42 U.S.C. 2000e-2 into 2000e.
    """
    raw_targets = [dict(target) for target in targets if isinstance(target, dict)]
    expanded: list[dict[str, Any]] = []
    saw_compound = False

    for raw in raw_targets:
        parts = split_compound_identifier(raw.get("identifier"))
        if len(parts) <= 1:
            continue
        saw_compound = True
        for part in parts:
            parsed = parse_section_identifier(part, section_index)
            if not parsed:
                continue
            target = dict(raw)
            target.update(
                {
                    "identifier": parsed["identifier"],
                    "title": parsed["title"],
                    "section": parsed["section"],
                    "inferred": False,
                }
            )
            expanded.append(target)

    return expanded if saw_compound and expanded else raw_targets


def canonicalize_audit_payload(
    payload: dict[str, Any],
    section_index: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Clone audit records so every final identifier names at most one target."""
    result = dict(payload)
    canonical_records: list[dict[str, Any]] = []

    for raw in payload.get("results", []):
        if not isinstance(raw, dict):
            continue
        identifier = raw.get("final_section_or_subsection_identifier")
        parts = split_compound_identifier(identifier)
        if not parts:
            canonical_records.append(copy.deepcopy(raw))
            continue

        for part in parts:
            record = copy.deepcopy(raw)
            parsed = parse_section_identifier(part, section_index)
            record["final_section_or_subsection_identifier"] = (
                parsed["identifier"] if parsed else part
            )
            canonical_records.append(record)

    result["results"] = canonical_records
    result["canonical_target_expansion"] = {
        "source_record_count": len(payload.get("results", [])),
        "expanded_record_count": len(canonical_records),
    }
    return result
