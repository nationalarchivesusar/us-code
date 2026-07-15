#!/usr/bin/env python3
"""Prepare and validate the public-law website dataset for publication."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "public-laws.json"
SECTION_SUFFIX_RE = re.compile(
    r"-(?:source(?:-credit)?|amendment-note|effective-date|short-title|"
    r"statutory-notes-heading|codification-note|toc-entry)$",
    re.IGNORECASE,
)


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


def clean_section(section: str | None) -> str | None:
    if not section:
        return None
    value = section.strip()
    while SECTION_SUFFIX_RE.search(value):
        value = SECTION_SUFFIX_RE.sub("", value)
    return value or None


def clean_target(target: dict, repealed: bool) -> dict:
    target = dict(target)
    section = clean_section(target.get("section"))
    title = str(target.get("title") or "").lstrip("0") or "0"
    target["title"] = title
    target["section"] = section
    target["historical"] = repealed

    if section:
        target["citation"] = f"{title} U.S.C. § {section}"
        target["href"] = None if repealed else f"cite/{quote(title)}/{quote(section)}/"
        target["identifier"] = f"/us/usc/t{title}/s{section}"
    else:
        target["citation"] = f"Title {title}, United States Code (title-wide material)"
        target["href"] = None
        target["identifier"] = f"/us/usc/t{title}"
    return target


def dedupe_targets(targets: list[dict], repealed: bool) -> list[dict]:
    unique: dict[tuple[str, str, str], dict] = {}
    for raw in targets:
        target = clean_target(raw, repealed)
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

    for law in payload.get("laws", []):
        repealed = law.get("status") == "repealed"
        if not re.fullmatch(r"https://trello\.com/c/[0-9A-Za-z]{8}", law.get("trello_url") or ""):
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
            action["targets"] = dedupe_targets(raw_targets, repealed)
            action["target"] = action["targets"][0] if action["targets"] else None
            law_targets.extend(action["targets"])

        law["targets"] = dedupe_targets(law_targets or law.get("targets", []), repealed)
        law["target_count"] = len(law["targets"])

    all_targets = [
        target
        for law in payload.get("laws", [])
        for target in law.get("targets", [])
    ]
    clickable = [target for target in all_targets if target.get("href")]
    if any(not target.get("section") for target in clickable):
        raise SystemExit("Clickable title-only U.S. Code target remains.")
    if any(SECTION_SUFFIX_RE.search(target.get("section") or "") for target in all_targets):
        raise SystemExit("Internal XML note suffix remains in a public section link.")

    payload.setdefault("counts", {})["direct_section_links"] = len(clickable)
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
        f"Filtered public-law dataset: {len(clickable)} direct section links and "
        f"{payload['counts']['trello_links']} Trello card links."
    )


if __name__ == "__main__":
    main()
