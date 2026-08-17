#!/usr/bin/env python3
"""Prepare and validate the public-law website dataset for publication."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

from augment_public_laws_with_current_laws import augment
from build_code_api import build as build_code_api
from build_enactment_history import build as build_enactment_history
from build_reference_graph import build as build_reference_graph
from build_section_history import (
    DEFAULT_BASELINE,
    OUTPUT_DIR as SECTION_HISTORY_DIR,
    build as build_section_history,
)
from build_version_history import build as build_version_history

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "public-laws.json"
SECTION_PATH_RE = re.compile(r"/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/\"'<>&?#\s]+)")
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
    known = section_index.get(title, {})
    candidates = [value]
    shortened = value
    while "-" in shortened:
        shortened = shortened.rsplit("-", 1)[0]
        candidates.append(shortened)
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


def action_text(action: dict) -> str:
    parts: list[str] = []
    for key in (
        "final_section_or_subsection_identifier",
        "planned_action",
        "planned_treatment",
        "exact_enacted_text_applied",
        "source_credit_change",
        "amendment_note_change",
        "toc_change",
        "validation_result",
        "documented_no_op_explanation",
        "verified_note_text_excerpt",
    ):
        value = action.get(key)
        if isinstance(value, str):
            parts.append(value)
    baseline = action.get("baseline_proof")
    if isinstance(baseline, str):
        parts.append(baseline)
    elif baseline is not None:
        parts.append(json.dumps(baseline, ensure_ascii=False))
    return " ".join(parts)


def targets_from_action(action: dict, repealed: bool) -> list[dict]:
    identifier = (action.get("final_section_or_subsection_identifier") or "").strip()
    title = xml_title_number(action)
    targets: list[dict] = []

    match = TARGET_RE.match(identifier)
    if match:
        explicit_title = normalized_title(match.group("title")) or match.group("title")
        explicit_section = match.group("section")
        explicit_rest = match.group("rest") or ""
        targets.append(
            make_target(
                explicit_title,
                explicit_section,
                explicit_rest,
                repealed=repealed,
                identifier=identifier,
            )
        )
        title = explicit_title

    for node_id in (
        list(action.get("actual_node_ids_added") or [])
        + list(action.get("actual_node_ids_changed") or [])
        + list(action.get("actual_node_ids_removed") or [])
    ):
        match = NODE_TARGET_RE.search(str(node_id))
        if match:
            targets.append(
                make_target(
                    match.group("title"),
                    match.group("section"),
                    repealed=repealed,
                    inferred=True,
                )
            )
            continue
        match = NODE_SECTION_RE.search(str(node_id))
        if match and title:
            targets.append(
                make_target(
                    title,
                    match.group("section"),
                    repealed=repealed,
                    inferred=True,
                )
            )

    text = action_text(action)
    for match in TARGET_ANY_RE.finditer(text):
        found_identifier = match.group(0)
        targets.append(
            make_target(
                match.group("title"),
                match.group("section"),
                match.group("rest") or "",
                repealed=repealed,
                identifier=found_identifier,
                inferred=True,
            )
        )
    for match in USC_CITATION_RE.finditer(text):
        targets.append(
            make_target(
                match.group("title"),
                match.group("section"),
                repealed=repealed,
                inferred=True,
            )
        )

    if not targets and title:
        targets.append(make_target(title, None, repealed=repealed, identifier=identifier or None))

    return dedupe_targets(targets)


def friendly_result_status(value: str) -> str:
    labels = {
        "applied": "Applied",
        "already-satisfied-with-baseline-proof": "Already reflected in the Code",
        "superseded-by-later-action": "Superseded by a later action",
        "documented-no-code-action": "No Code amendment required",
        "blocked": "Blocked",
        "pending": "Pending",
    }
    return labels.get(value, (value or "Recorded").replace("-", " ").title())


def classify_action(action: dict, repealed: bool) -> tuple[str, str]:
    if repealed:
        return "repealed-history", "Repealed — historical effect"
    result_status = action.get("result_status") or ""
    planned_action = (action.get("planned_action") or "").lower()
    treatment = (action.get("planned_treatment") or "").lower()
    if result_status == "documented-no-code-action":
        return "no-code", "No Code amendment"
    if result_status == "superseded-by-later-action":
        return "superseded", "Superseded"
    if "note" in treatment or "note" in planned_action:
        return "note", "Statutory or historical note"
    if result_status == "already-satisfied-with-baseline-proof":
        return "code", "Already reflected in the Code"
    return "code", "Integrated into the Code"


def compact_description(action: dict, repealed: bool) -> str:
    if repealed:
        return (
            "This law is repealed. Its former Code effect is shown for historical "
            "reference; law-specific operative text has been removed."
        )
    for key in (
        "documented_no_op_explanation",
        "exact_enacted_text_applied",
        "validation_result",
    ):
        text = " ".join((action.get(key) or "").split())
        if text:
            return text[:417].rstrip() + "..." if len(text) > 420 else text
    planned = " ".join((action.get("planned_action") or "").split())
    return planned or friendly_result_status(action.get("result_status") or "")


def build() -> dict:
    ledger = load_json(FINAL_LEDGER)
    results = load_json(INTEGRATION_RESULTS)
    repealed_data = load_json(REPEALED_LAWS)
    reconciliation = load_json(REPEAL_RECONCILIATION)
    trello_data = load_json(TRELLO_LINKS)

    repealed_ids = {row["law_id"] for row in repealed_data.get("laws", [])}
    reconciliation_ids = {
        row["law_id"]
        for row in reconciliation.get("laws", [])
        if row.get("disposition") == "repealed-history-only"
    }
    reconciliation_summary = reconciliation.get("summary", {})
    if reconciliation_summary.get("errors") != 0:
        raise SystemExit("Repealed-law reconciliation still reports errors.")
    if reconciliation_summary.get("manual_review_required") != 0:
        raise SystemExit("Repealed-law reconciliation still requires manual review.")
    if reconciliation_ids != repealed_ids:
        raise SystemExit("Repealed-law status mismatch.")

    short_links = trello_data.get("short_links", {})
    trello_links = {
        law_id: f"https://trello.com/c/{short_link}"
        for law_id, short_link in short_links.items()
    }
    if len(trello_links) != 270 or not all(
        re.fullmatch(r"https://trello\.com/c/[0-9A-Za-z]{8}", url)
        for url in trello_links.values()
    ):
        raise SystemExit("Expected 270 direct Trello card links.")

    laws: dict[str, dict] = {}
    for row in ledger.get("laws", []):
        law_id = row["law_id"]
        public_law = row["public_law"]
        repealed = law_id in repealed_ids
        if law_id not in trello_links:
            raise SystemExit(f"Missing Trello card link for {law_id}.")
        laws[law_id] = {
            "law_id": law_id,
            "public_law": public_law,
            "title": clean_title(row.get("title", ""), public_law),
            "status": "repealed" if repealed else "active",
            "status_label": "Repealed" if repealed else "Active",
            "trello_url": trello_links[law_id],
            "actions": [],
        }

    grouped_actions: dict[str, list[dict]] = defaultdict(list)
    for action in results.get("results", []):
        law_id = action.get("law_id")
        if law_id not in laws:
            raise SystemExit(f"Integration result references unknown law: {law_id}")
        grouped_actions[law_id].append(action)

    for law_id, law in laws.items():
        repealed = law["status"] == "repealed"
        effect_categories: set[str] = set()
        section_targets_by_title: dict[str, list[dict]] = defaultdict(list)
        prepared_actions: list[dict] = []

        for action in grouped_actions.get(law_id, []):
            category, effect_label = classify_action(action, repealed)
            targets = targets_from_action(action, repealed)
            for target in targets:
                if target.get("section"):
                    section_targets_by_title[target["title"]].append(target)
            effect_categories.add(category)
            prepared_actions.append(
                {
                    "action_id": action.get("action_id"),
                    "provision": action.get("provision_reference")
                    or "Unspecified provision",
                    "effect_category": category,
                    "effect_label": effect_label,
                    "result_status": action.get("result_status"),
                    "result_label": friendly_result_status(
                        action.get("result_status") or ""
                    ),
                    "planned_action": action.get("planned_action"),
                    "treatment": action.get("planned_treatment"),
                    "targets": targets,
                    "description": compact_description(action, repealed),
                }
            )

        for title, targets in list(section_targets_by_title.items()):
            section_targets_by_title[title] = dedupe_targets(targets)

        law_targets: list[dict] = []
        for action in prepared_actions:
            expanded: list[dict] = []
            for target in action["targets"]:
                if not target.get("section") and section_targets_by_title.get(
                    target["title"]
                ):
                    expanded.extend(section_targets_by_title[target["title"]])
                else:
                    expanded.append(target)
            action["targets"] = dedupe_targets(expanded)
            action["target"] = action["targets"][0] if action["targets"] else None
            law_targets.extend(action["targets"])

        law["actions"] = prepared_actions
        law["targets"] = dedupe_targets(law_targets)
        law["effect_categories"] = sorted(effect_categories)
        law["action_count"] = len(prepared_actions)
        law["target_count"] = len(law["targets"])

        if repealed:
            law["summary"] = (
                "Repealed law. Former U.S. Code effects are listed for historical "
                "reference, and no law-specific operative text remains."
            )
        elif law["action_count"] == 0:
            law["summary"] = "Active law with no separately recorded Code action."
        elif law["target_count"]:
            law["summary"] = (
                f"Active law with {law['action_count']} recorded action"
                f"{'' if law['action_count'] == 1 else 's'} affecting "
                f"{law['target_count']} U.S. Code target"
                f"{'' if law['target_count'] == 1 else 's'}."
            )
        else:
            law["summary"] = (
                f"Active law with {law['action_count']} recorded action"
                f"{'' if law['action_count'] == 1 else 's'} and no exact Code section link."
            )

    ordered_laws = sorted(laws.values(), key=lambda law: law_sort_key(law["public_law"]))
    counts = {
        "total": len(ordered_laws),
        "active": sum(law["status"] == "active" for law in ordered_laws),
        "repealed": sum(law["status"] == "repealed" for law in ordered_laws),
        "actions": sum(law["action_count"] for law in ordered_laws),
        "targets": sum(law["target_count"] for law in ordered_laws),
    }
    return {
        "schema_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "laws": ordered_laws,
    }


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
    if len(clickable) < 200:
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
