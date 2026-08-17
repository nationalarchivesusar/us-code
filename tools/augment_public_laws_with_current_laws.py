#!/usr/bin/env python3
"""Merge post-audit/current-law enactments into the public-law website dataset.

The original public-law builder is intentionally tied to the completed 270-law audit
ledger. New enactments whose substantive Code treatment is maintained by the 2026
current-law overlay live in ``legal-data/current-public-laws.json`` and are merged here.
Existing law IDs are replaced, so a law such as Pub. L. 41-271 can keep its audited
archive identity while displaying its newer substantive codification instead of the
obsolete pre-overlay disposition.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
CURRENT_LAWS = ROOT / "legal-data" / "current-public-laws.json"
TRELLO_LINKS = ROOT / "legal-data" / "public-law-trello.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def law_sort_key(public_law: str) -> tuple[int, int, str]:
    match = re.fullmatch(r"(\d+)-(\d+)", public_law or "")
    if not match:
        return (10**9, 10**9, public_law or "")
    return (int(match.group(1)), int(match.group(2)), public_law)


def make_target(title: str, section: str, *, repealed: bool) -> dict:
    title = str(title).lstrip("0") or "0"
    section = str(section)
    return {
        "identifier": f"/us/usc/t{title}/s{section}",
        "title": title,
        "section": section,
        "citation": f"{title} U.S.C. § {section}",
        "href": None if repealed else f"cite/{quote(title)}/{quote(section)}/",
        "historical": repealed,
        "inferred": False,
    }


def expand_targets(specs: list[dict], *, repealed: bool) -> list[dict]:
    targets: list[dict] = []
    for spec in specs:
        title = str(spec.get("title") or "").strip()
        if not title:
            raise SystemExit("Current public-law target is missing a title.")
        if "section" in spec:
            targets.append(make_target(title, str(spec["section"]), repealed=repealed))
            continue
        section_range = spec.get("range")
        if (
            not isinstance(section_range, list)
            or len(section_range) != 2
            or not all(isinstance(value, int) for value in section_range)
        ):
            raise SystemExit(f"Invalid current public-law target specification: {spec!r}")
        start, end = section_range
        if start > end:
            raise SystemExit(f"Descending current public-law target range: {spec!r}")
        targets.extend(
            make_target(title, str(section), repealed=repealed)
            for section in range(start, end + 1)
        )

    unique: dict[tuple[str, str], dict] = {}
    for target in targets:
        unique.setdefault((target["title"], target["section"]), target)
    return sorted(
        unique.values(),
        key=lambda target: (
            int(re.sub(r"\D", "", target["title"]) or 0),
            int(target["section"]) if target["section"].isdigit() else 10**9,
            target["section"],
        ),
    )


def build_current_law(row: dict, short_links: dict[str, str]) -> dict:
    law_id = str(row.get("law_id") or "").strip()
    public_law = str(row.get("public_law") or "").strip()
    title = " ".join(str(row.get("title") or "").split())
    status = row.get("status", "active")
    if not re.fullmatch(r"PL-\d{3}-\d{3}", law_id):
        raise SystemExit(f"Invalid current public-law ID: {law_id!r}")
    if not re.fullmatch(r"\d+-\d+", public_law):
        raise SystemExit(f"Invalid current public-law number for {law_id}: {public_law!r}")
    if not title:
        raise SystemExit(f"Current public law {law_id} is missing a title.")
    if status not in {"active", "repealed"}:
        raise SystemExit(f"Invalid status for {law_id}: {status!r}")

    repealed = status == "repealed"
    actions: list[dict] = []
    law_targets: list[dict] = []
    effect_categories: set[str] = set()

    for index, raw_action in enumerate(row.get("actions") or [], start=1):
        targets = expand_targets(raw_action.get("targets") or [], repealed=repealed)
        category = raw_action.get("effect_category") or "code"
        effect_categories.add(category)
        law_targets.extend(targets)
        actions.append(
            {
                "action_id": f"{law_id}-current-{index:02d}",
                "provision": raw_action.get("provision") or "Unspecified provision",
                "effect_category": category,
                "effect_label": raw_action.get("effect_label") or "Integrated into the Code",
                "result_status": "applied",
                "result_label": "Applied",
                "planned_action": raw_action.get("description") or "",
                "treatment": raw_action.get("treatment") or "current-law overlay",
                "targets": targets,
                "target": targets[0] if targets else None,
                "description": raw_action.get("description") or "Current-law codification applied.",
            }
        )

    unique_targets: dict[tuple[str, str], dict] = {}
    for target in law_targets:
        unique_targets.setdefault((target["title"], target["section"]), target)
    targets = sorted(
        unique_targets.values(),
        key=lambda target: (
            int(re.sub(r"\D", "", target["title"]) or 0),
            int(target["section"]) if target["section"].isdigit() else 10**9,
            target["section"],
        ),
    )

    short_link = str(row.get("trello_short_link") or "").strip() or short_links.get(law_id)
    trello_url = f"https://trello.com/c/{short_link}" if short_link else None
    action_count = len(actions)
    target_count = len(targets)
    if repealed:
        summary = (
            "Repealed law. Former U.S. Code effects are listed for historical "
            "reference, and no law-specific operative text remains."
        )
    elif target_count:
        summary = (
            f"Active law with {action_count} recorded codification action"
            f"{'' if action_count == 1 else 's'} affecting {target_count} Code location"
            f"{'' if target_count == 1 else 's'}."
        )
    else:
        summary = (
            f"Active law with {action_count} recorded codification action"
            f"{'' if action_count == 1 else 's'} and no direct Code location."
        )

    return {
        "law_id": law_id,
        "public_law": public_law,
        "title": title,
        "status": status,
        "status_label": "Repealed" if repealed else "Active",
        "trello_url": trello_url,
        "actions": actions,
        "targets": targets,
        "effect_categories": sorted(effect_categories),
        "action_count": action_count,
        "target_count": target_count,
        "summary": summary,
    }


def augment(payload: dict) -> dict:
    registry = load_json(CURRENT_LAWS)
    trello_data = load_json(TRELLO_LINKS)
    short_links = trello_data.get("short_links", {})

    laws_by_id = {law["law_id"]: law for law in payload.get("laws", [])}
    public_law_to_id = {
        law.get("public_law"): law.get("law_id") for law in payload.get("laws", [])
    }
    seen_registry_ids: set[str] = set()
    for row in registry.get("laws", []):
        law = build_current_law(row, short_links)
        if law["law_id"] in seen_registry_ids:
            raise SystemExit(f"Duplicate current public-law ID: {law['law_id']}")
        seen_registry_ids.add(law["law_id"])
        existing_id = public_law_to_id.get(law["public_law"])
        if existing_id and existing_id != law["law_id"]:
            raise SystemExit(
                f"Public-law number collision: {law['public_law']} belongs to {existing_id}, "
                f"not {law['law_id']}."
            )
        laws_by_id[law["law_id"]] = law
        public_law_to_id[law["public_law"]] = law["law_id"]

    laws = sorted(laws_by_id.values(), key=lambda law: law_sort_key(law["public_law"]))
    active_count = sum(law.get("status") == "active" for law in laws)
    repealed_count = sum(law.get("status") == "repealed" for law in laws)
    action_count = sum(len(law.get("actions") or []) for law in laws)

    payload["laws"] = laws
    payload.setdefault("counts", {}).update(
        {
            "total": len(laws),
            "active": active_count,
            "repealed": repealed_count,
            "actions": action_count,
            "laws_with_code_locations": sum(bool(law.get("targets")) for law in laws),
            "trello_links": sum(bool(law.get("trello_url")) for law in laws),
        }
    )
    payload["source_note"] = (
        "Historical audit statuses and available Trello card links come from the "
        "authoritative USAR public-law archive. Post-audit enactments and updated "
        "substantive Code dispositions come from the current-law publication registry."
    )
    return payload


if __name__ == "__main__":
    raise SystemExit(
        "This module augments data/public-laws.json through "
        "tools/filter_public_laws_for_publication.py."
    )
