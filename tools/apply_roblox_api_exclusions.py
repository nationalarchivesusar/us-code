#!/usr/bin/env python3
"""Apply targeted display exclusions to the Roblox-facing criminal-law API.

This pass is intentionally narrow. It removes specifically excluded charges
from the generated booking catalog and withholds the statutory body of one
otherwise retained charge. It does not alter the underlying U.S. Code or Public
Law sources elsewhere on the site.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "api" / "v1" / "criminal-law"
TITLE18_DIR = BASE / "title18"

# Local-code charges to remove entirely from the Roblox-facing catalog.
LOCAL_REMOVE_SECTIONS = {"312"}

# Title 18 charges to remove entirely from the Roblox-facing catalog.
TITLE18_REMOVE_SECTIONS = {
    # Chapter 3 and other animal-specific offenses are not useful to this RP's
    # booking flow and are intentionally omitted from the Roblox catalog.
    "41",
    "42",
    "43",
    "47",
    "48",
    "49",
    "1368",
    "2316",
    "2317",
    # Existing content exclusions.
    "175",
    "1091",
    "2280a",
    "2283",
    "2340A",
    "2441",
}

# Title 18 charges that remain selectable, but whose statutory body must not be
# displayed in Roblox.
TITLE18_WITHHOLD_BODY = {"2385"}

WITHHELD_TEXT = (
    "Full statutory text is not displayed in this Roblox-facing reference. "
    "The charge citation and name remain available for booking."
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def section_key(value: object) -> str:
    return str(value or "").strip()


def safe_search_text(item: dict) -> str:
    chapter = item.get("chapter") or {}
    values = [item.get("citation"), item.get("heading")]
    if isinstance(chapter, dict):
        values.extend([chapter.get("number"), chapter.get("heading")])
    return " ".join(str(value) for value in values if value)


def apply() -> None:
    dc_path = BASE / "dc-code.json"
    title18_index_path = BASE / "title18-index.json"
    title18_search_path = BASE / "title18-search.json"
    charges_path = BASE / "charges.json"

    dc = load(dc_path)
    title18_index = load(title18_index_path)
    title18_search = load(title18_search_path)
    charges = load(charges_path)

    dc["sections"] = [
        item for item in dc.get("sections", [])
        if section_key(item.get("section")) not in LOCAL_REMOVE_SECTIONS
    ]

    retained_title18 = []
    title18_by_id: dict[str, dict] = {}
    for item in title18_index.get("sections", []):
        section = section_key(item.get("section"))
        if section in TITLE18_REMOVE_SECTIONS:
            continue
        copy = dict(item)
        if section in TITLE18_WITHHOLD_BODY:
            copy["text_withheld"] = True
        retained_title18.append(copy)
        if copy.get("id"):
            title18_by_id[str(copy["id"])] = copy
    title18_index["sections"] = retained_title18

    # Delete removed detail records, and neutralize the retained-withheld body.
    for path in sorted(TITLE18_DIR.glob("*.json")):
        detail = load(path)
        section = section_key(detail.get("section"))
        if section in TITLE18_REMOVE_SECTIONS:
            path.unlink()
            continue
        if section in TITLE18_WITHHOLD_BODY:
            detail["text"] = WITHHELD_TEXT
            detail["text_withheld"] = True
            detail["text_display_scope"] = "withheld_for_platform_safety"
            write(path, detail)

    allowed_title18_ids = set(title18_by_id)
    search_entries = []
    for item in title18_search.get("entries", []):
        charge_id = str(item.get("id") or "")
        if charge_id not in allowed_title18_ids:
            continue
        index_item = title18_by_id[charge_id]
        copy = dict(item)
        if section_key(index_item.get("section")) in TITLE18_WITHHOLD_BODY:
            copy["search_text"] = safe_search_text(index_item)
        search_entries.append(copy)
    title18_search["entries"] = search_entries
    title18_search["count"] = len(search_entries)

    # Remove the same charges from the authoritative booking catalog. Preserve
    # the retained-withheld charge but mark its detail body withheld.
    kept_charges = []
    for item in charges.get("charges", []):
        source = item.get("source")
        section = section_key(item.get("section"))
        if source == "dc-criminal-code-federalized":
            if section in LOCAL_REMOVE_SECTIONS:
                continue
        if source == "title18" and section in TITLE18_REMOVE_SECTIONS:
            continue
        copy = dict(item)
        if source == "title18" and section in TITLE18_WITHHOLD_BODY:
            copy["text_withheld"] = True
        kept_charges.append(copy)
    charges["charges"] = kept_charges

    counts = {
        "total": len(kept_charges),
        "dc_code": sum(
            item.get("source") == "dc-criminal-code-federalized"
            for item in kept_charges
        ),
        "title18": sum(item.get("source") == "title18" for item in kept_charges),
    }
    charges["counts"] = counts

    index_counts = dict(title18_index.get("counts") or {})
    index_counts["sections"] = len(retained_title18)
    index_counts["charges"] = len(retained_title18)
    index_counts["text_withheld"] = sum(
        bool(item.get("text_withheld")) for item in retained_title18
    )
    title18_index["counts"] = index_counts

    write(dc_path, dc)
    write(title18_index_path, title18_index)
    write(title18_search_path, title18_search)
    write(charges_path, charges)

    check()
    print(
        "Applied targeted Roblox API exclusions, including animal-specific Title 18 "
        "offenses; retained §2385 with its body withheld."
    )


def check() -> None:
    if (BASE / "federal-code.json").exists():
        raise RuntimeError("Duplicative federal-code.json must not be published")
    dc = load(BASE / "dc-code.json")
    title18 = load(BASE / "title18-index.json")
    title18_search = load(BASE / "title18-search.json")
    charges = load(BASE / "charges.json")

    present = {section_key(item.get("section")) for item in dc.get("sections", [])}
    bad = present & LOCAL_REMOVE_SECTIONS
    if bad:
        raise RuntimeError(f"dc-code still contains excluded sections: {sorted(bad)}")

    title_sections = {
        section_key(item.get("section")): item for item in title18.get("sections", [])
    }
    bad_title = set(title_sections) & TITLE18_REMOVE_SECTIONS
    if bad_title:
        raise RuntimeError(f"Title 18 index still contains excluded sections: {sorted(bad_title)}")

    for section in TITLE18_REMOVE_SECTIONS:
        if (TITLE18_DIR / f"{section}.json").exists():
            raise RuntimeError(f"Excluded Title 18 detail still exists: {section}.json")

    for section in TITLE18_WITHHOLD_BODY:
        item = title_sections.get(section)
        if not item or item.get("text_withheld") is not True:
            raise RuntimeError(f"Title 18 § {section} is missing or not marked text-withheld")
        detail_path = TITLE18_DIR / f"{section}.json"
        if not detail_path.is_file():
            raise RuntimeError(f"Retained Title 18 detail is missing: {section}.json")
        detail = load(detail_path)
        if detail.get("text") != WITHHELD_TEXT or detail.get("text_withheld") is not True:
            raise RuntimeError(f"Title 18 § {section} body is not safely withheld")

    charge_pairs = {
        (str(item.get("source") or ""), section_key(item.get("section")))
        for item in charges.get("charges", [])
    }
    if any(
        ("dc-criminal-code-federalized", section) in charge_pairs
        for section in LOCAL_REMOVE_SECTIONS
    ):
        raise RuntimeError("Booking catalog still contains an excluded local D.C. charge")
    if any(source == "federal-criminal-code-2025" for source, _ in charge_pairs):
        raise RuntimeError("Booking catalog contains a duplicative FCC charge")
    if any(("title18", section) in charge_pairs for section in TITLE18_REMOVE_SECTIONS):
        raise RuntimeError("Booking catalog still contains an excluded Title 18 charge")
    if not all(("title18", section) in charge_pairs for section in TITLE18_WITHHOLD_BODY):
        raise RuntimeError("Booking catalog lost a body-withheld Title 18 charge")

    search_ids = {str(item.get("id") or "") for item in title18_search.get("entries", [])}
    index_ids = {str(item.get("id") or "") for item in title18.get("sections", [])}
    if search_ids != index_ids:
        raise RuntimeError("Title 18 search/index IDs diverged after targeted exclusions")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
        print("Targeted Roblox API exclusion check passed.")
    else:
        apply()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
