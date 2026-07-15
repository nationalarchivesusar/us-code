#!/usr/bin/env python3
"""Prepare and validate the public-law website dataset for publication."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "public-laws.json"
SECTION_PATH_RE = re.compile(r"/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/\"'<>&?#\s]+)")
SECTION_SUFFIX_RE = re.compile(
    r"-(?:source(?:-credit)?|amendment-note|effective-date|short-title|"
    r"statutory-notes-heading|codification-note|toc-entry)$",
    re.IGNORECASE,
)
TRAILING_SUBDIVISION_RE = re.compile(r"^(?P<base>.+)-[a-z]$", re.IGNORECASE)


def public_no_code_description(treatment: str) -> str:
    treatment = (treatment or "").lower()
    if "already-incorporated" in treatment:
        return "No additional U.S. Code amendment was required because this effect was already reflected in the Code."
    if "source-limited-history" in treatment:
        return "No operative U.S. Code amendment was made; the available source supports historical treatment only."
    if "exclude-from-code" in treatment:
        return "This provision was not codified because it does not enact or amend permanent U.S. Code text."
    if "toc-update" in treatment:
        return "This provision affected organizational or table-of-contents treatment without adding operative Code text."
    return "No direct U.S. Code amendment was required for this provision."


def build_section_index() -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = defaultdict(dict)
    for path in sorted((ROOT / "usc").glob("usc*.xml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in SECTION_PATH_RE.finditer(text):
            title = match.group("title").lstrip("0") or "0"
            section = match.group("section").rstrip(".,;:|)]}")
            index[title].setdefault(section.lower(), section)
    return index


def normalize_section(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().strip("\"'.,;:|)]}")
    value = value.lstrip("([{\"")
    value = re.sub(r"(?<=[0-9A-Za-z])\?(?=[0-9A-Za-z])", "-", value)
    while SECTION_SUFFIX_RE.search(value):
        value = SECTION_SUFFIX_RE.sub("", value)
    return value or None


def resolve_section(
    title: str,
    section: str | None,
    section_index: dict[str, dict[str, str]],
) -> tuple[str | None, bool]:
    value = normalize_section(section)
    if not value:
        return None, False
    known = section_index.get(title, {})
    candidates = [value]
    subdivision = TRAILING_SUBDIVISION_RE.match(value)
    if subdivision:
        candidates.append(subdivision.group("base"))
    for candidate in candidates:
        canonical = known.get(candidate.lower())
        if canonical:
            return canonical, True
    return value, False


def clean_target(
    target: dict,
    repealed: bool,
    section_index: dict[str, dict[str, str]],
) -> dict:
    target = dict(target)
    title = str(target.get("title") or "").lstrip("0") or "0"
    section, available = resolve_section(title, target.get("section"), section_index)
    target["title"] = title
    target["section"] = section
    target["historical"] = repealed
    target["available"] = available

    if section:
        target["citation"] = f"{title} U.S.C. § {section}"
        if not available and not repealed:
            target["citation"] += " (not present in current Code)"
        target["href"] = (
            f"cite/{quote(title)}/{quote(section)}/"
            if available and not repealed
            else None
        )
        target["identifier"] = f"/us/usc/t{title}/s{section}"
    else:
        target["citation"] = f"Title {title}, United States Code (title-wide material)"
        target["href"] = None
        target["identifier"] = f"/us/usc/t{title}"
    return target


def dedupe_targets(
    targets: list[dict],
    repealed: bool,
    section_index: dict[str, dict[str, str]],
) -> list[dict]:
    unique: dict[tuple[str, str, str], dict] = {}
    for raw in targets:
        target = clean_target(raw, repealed, section_index)
        key = (
            target.get("title") or "",
            target.get("section") or "",
            target.get("citation") or "",
        )
        unique.setdefault(key, target)
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            int(re.sub(r"\D", "", item.get("title") or "") or 0),
            item.get("section") or "",
            item.get("citation") or "",
        ),
    )
    section_titles = {target["title"] for target in ordered if target.get("section")}
    return [
        target
        for target in ordered
        if target.get("section") or target.get("title") not in section_titles
    ]


def main() -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    section_index = build_section_index()

    for law in payload.get("laws", []):
        repealed = law.get("status") == "repealed"
        if not re.fullmatch(
            r"https://trello\.com/c/[0-9A-Za-z]{8}", law.get("trello_url") or ""
        ):
            raise SystemExit(f"Missing or invalid Trello card URL for {law.get('law_id')}.")

        law_targets: list[dict] = []
        for action in law.get("actions", []):
            if repealed:
                action["result_label"] = "Historical disposition"

            description = action.get("description") or ""
            internal_no_code = (
                description.startswith("Documented non-operative disposition")
                or "The XML cleanup pass removed Trello URLs" in description
                or "full-law dumps" in description
                or "false source boilerplate" in description
            )
            if internal_no_code:
                action["description"] = public_no_code_description(
                    action.get("treatment") or ""
                )

            raw_targets = action.get("targets") or (
                [action["target"]] if action.get("target") else []
            )
            action["targets"] = dedupe_targets(
                raw_targets, repealed, section_index
            )
            action["target"] = action["targets"][0] if action["targets"] else None
            law_targets.extend(action["targets"])

        law["targets"] = dedupe_targets(
            law_targets or law.get("targets", []), repealed, section_index
        )
        law["target_count"] = len(law["targets"])

    all_targets = [
        target
        for law in payload.get("laws", [])
        for target in law.get("targets", [])
    ]
    clickable = [target for target in all_targets if target.get("href")]
    if any(not target.get("section") for target in clickable):
        raise SystemExit("Clickable title-only U.S. Code target remains.")
    if any(not target.get("available") for target in clickable):
        raise SystemExit("Clickable U.S. Code target does not exist in the published Code.")
    if any(SECTION_SUFFIX_RE.search(target.get("section") or "") for target in all_targets):
        raise SystemExit("Internal XML note suffix remains in a public section link.")
    if len(clickable) < 250:
        raise SystemExit(f"Too few exact section links were generated: {len(clickable)}.")

    payload.setdefault("counts", {})["direct_section_links"] = len(clickable)
    payload["counts"]["unavailable_section_references"] = sum(
        bool(target.get("section")) and not target.get("available")
        for target in all_targets
    )
    payload["counts"]["trello_links"] = sum(
        bool(law.get("trello_url")) for law in payload.get("laws", [])
    )

    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    forbidden = (
        "Documented non-operative disposition",
        "The XML cleanup pass",
        "Trello URLs",
        "full-law dumps",
        "false source boilerplate",
    )
    hits = [phrase for phrase in forbidden if phrase in serialized]
    if hits:
        raise SystemExit(f"Public-law dataset still contains internal language: {hits}")

    DATA_FILE.write_text(serialized, encoding="utf-8")
    print(
        f"Filtered public-law dataset: {len(clickable)} verified section links, "
        f"{payload['counts']['unavailable_section_references']} nonlinked section references, "
        f"and {payload['counts']['trello_links']} Trello card links."
    )


if __name__ == "__main__":
    main()
