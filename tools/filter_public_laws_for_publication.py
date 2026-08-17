#!/usr/bin/env python3
"""Prepare and validate the public-law website dataset for publication."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

from augment_public_laws_with_current_laws import augment
from build_canonical_enactment_history import build as build_enactment_history
from build_code_api import build as build_code_api
from build_reference_graph import build as build_reference_graph
from build_section_history import (
    DEFAULT_BASELINE,
    OUTPUT_DIR as SECTION_HISTORY_DIR,
    build as build_section_history,
)
from build_version_history import build as build_version_history
from usc_target_normalization import (
    build_section_index as build_canonical_section_index,
    expand_authoritative_targets,
    fold_section_token,
    resolve_canonical_section,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "public-laws.json"
SECTION_SUFFIX_RE = re.compile(
    r"-(?:source(?:-credit)?|amendment-note|effective-date|short-title|"
    r"statutory-notes-heading|codification-note|toc-entry|source-defect)$",
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
    return build_canonical_section_index(ROOT / "usc")


def normalize_section(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().split()[0].strip("\"'.,;:|)]}")
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

    canonical = resolve_canonical_section(title, value, section_index)
    if canonical:
        return canonical, True

    # Some older inferred node identifiers append subdivision-like suffixes to
    # the section token.  Preserve the existing fallback, but only after first
    # trying the complete dash-normalized token against the live Code.  This is
    # what prevents 2000e?2 from collapsing to the nearby section 2000e.
    shortened = fold_section_token(value)
    while "-" in shortened:
        shortened = shortened.rsplit("-", 1)[0]
        canonical = resolve_canonical_section(title, shortened, section_index)
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
    payload = augment(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    section_index = build_section_index()

    for law in payload.get("laws", []):
        repealed = law.get("status") == "repealed"
        trello_url = law.get("trello_url")
        if trello_url and not re.fullmatch(
            r"https://trello\.com/c/[0-9A-Za-z]{8}", trello_url
        ):
            raise SystemExit(f"Invalid Trello card URL for {law.get('law_id')}.")

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
            raw_targets = expand_authoritative_targets(raw_targets, section_index)
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
    malformed_targets = [
        target
        for target in all_targets
        if "|" in str(target.get("section") or "")
        or "?" in str(target.get("section") or "")
    ]
    if malformed_targets:
        raise SystemExit(
            "Malformed compound or placeholder U.S. Code targets remain after canonicalization."
        )
    if len(clickable) < 200:
        raise SystemExit(f"Too few exact section links were generated: {len(clickable)}.")

    laws_by_number = {
        law.get("public_law"): law for law in payload.get("laws", [])
    }
    equality_law = laws_by_number.get("24-178")
    equality_action = next(
        (
            action
            for action in (equality_law or {}).get("actions", [])
            if action.get("action_id") == "ACTION-0530"
        ),
        None,
    )
    equality_targets = (equality_action or {}).get("targets", [])
    if not any(
        target.get("title") == "42"
        and fold_section_token(target.get("section")) == "2000e-2"
        for target in equality_targets
    ):
        raise SystemExit(
            "Pub. L. 24-178 ACTION-0530 no longer resolves to 42 U.S.C. § 2000e-2."
        )
    if any(
        target.get("title") == "42"
        and fold_section_token(target.get("section")) == "2000e"
        for target in equality_targets
    ):
        raise SystemExit(
            "Pub. L. 24-178 ACTION-0530 incorrectly resolves to 42 U.S.C. § 2000e."
        )

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

    history = build_section_history(
        baseline=DEFAULT_BASELINE,
        output_dir=SECTION_HISTORY_DIR,
        public_laws_path=DATA_FILE,
    )
    counts = history["counts"]
    if counts["changed"] <= 0:
        raise SystemExit("Section-history build produced no verified changed sections.")
    print(
        f"Prepared section-history publication data: {counts['changed']} changed sections "
        f"from {counts['tracked_targets']} tracked Public Law targets."
    )

    versions = build_version_history(public_laws_path=DATA_FILE)
    if versions["counts"]["versioned_sections"] <= 0:
        raise SystemExit("Version-history build produced no verified versioned sections.")
    print(
        f"Prepared exact repository version history for "
        f"{versions['counts']['versioned_sections']} sections."
    )

    enactments = build_enactment_history(public_laws_path=DATA_FILE)
    if enactments["counts"]["events"] <= 0:
        raise SystemExit("Enactment-history build produced no verified law-by-law events.")
    print(
        f"Prepared verified enactment history with {enactments['counts']['events']} events "
        f"across {enactments['counts']['sections']} sections."
    )

    references = build_reference_graph()
    if references["counts"]["directed_reference_edges"] <= 0:
        raise SystemExit("Reference-graph build produced no verified statutory edges.")
    print(
        f"Prepared statutory reference graph with "
        f"{references['counts']['directed_reference_edges']} verified edges."
    )

    code_api = build_code_api()
    if code_api["counts"]["sections"] <= 0:
        raise SystemExit("General Code API build produced no sections.")
    print(
        f"Prepared general Code API with {code_api['counts']['titles']} titles and "
        f"{code_api['counts']['sections']} sections."
    )


if __name__ == "__main__":
    main()
