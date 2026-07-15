#!/usr/bin/env python3
"""Build the public-facing USAR public-law cross-reference index."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
FINAL_LEDGER = ROOT / "audit" / "final-ledger.json"
INTEGRATION_RESULTS = ROOT / "audit" / "xml-integration-results.json"
REPEALED_LAWS = ROOT / "legal-data" / "repealed-public-laws.json"
REPEAL_RECONCILIATION = ROOT / "audit" / "repealed-law-reconciliation.json"
TRELLO_LINKS = ROOT / "legal-data" / "public-law-trello.json"
OUTPUT = ROOT / "data" / "public-laws.json"

TARGET_RE = re.compile(
    r"^/us/usc/t(?P<title>\d+[A-Za-z]?)(?:/s(?P<section>[^/]+))?(?P<rest>/.*)?$"
)
TARGET_ANY_RE = re.compile(
    r"/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/\s,;]+)(?P<rest>(?:/[^\s,;]+)*)"
)
NODE_TARGET_RE = re.compile(
    r"(?:^|-)t(?P<title>\d+[A-Za-z]?)-s(?P<section>[0-9A-Za-z.-]+)(?:-|$)",
    re.IGNORECASE,
)
NODE_SECTION_RE = re.compile(
    r"(?:^|-)s(?P<section>\d+[A-Za-z]?(?:-\d+[A-Za-z]?)?)(?:-|$)",
    re.IGNORECASE,
)
USC_CITATION_RE = re.compile(
    r"(?P<title>\d+[A-Za-z]?)\s+U\.?S\.?C\.?\s*(?:§+|sections?|secs?\.?)*\s*(?P<section>\d+[A-Za-z]?(?:-[0-9A-Za-z]+)?)",
    re.IGNORECASE,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_title(raw: str, public_law: str) -> str:
    value = " ".join((raw or "").split())
    prefix = f"Public Law {public_law} |"
    if value.startswith(prefix):
        value = value[len(prefix) :].strip()
    elif "|" in value:
        value = value.split("|", 1)[1].strip()
    return value or f"Public Law {public_law}"


def law_sort_key(public_law: str) -> tuple[int, int, str]:
    match = re.fullmatch(r"(\d+)-(\d+)", public_law or "")
    if not match:
        return (10**9, 10**9, public_law or "")
    return (int(match.group(1)), int(match.group(2)), public_law)


def normalized_title(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.lstrip("0")
    return stripped or "0"


def xml_title_number(action: dict) -> str | None:
    value = action.get("xml_file_after") or action.get("xml_file_before") or ""
    match = re.search(r"usc(\d+[A-Za-z]?)\.xml$", value.replace("\\", "/"))
    return normalized_title(match.group(1)) if match else None


def make_target(
    title: str,
    section: str | None,
    rest: str = "",
    *,
    repealed: bool,
    identifier: str | None = None,
    inferred: bool = False,
) -> dict:
    title = normalized_title(title) or title
    section = (section or "").strip() or None
    rest = rest or ""
    pinpoint = "".join(f"({part})" for part in rest.strip("/").split("/") if part)
    if section:
        citation = f"{title} U.S.C. § {section}{pinpoint}"
        href = None if repealed else f"cite/{quote(title)}/{quote(section)}/"
        if href and identifier and rest:
            href += f"?p={quote(identifier, safe='')}"
        resolved_identifier = identifier or f"/us/usc/t{title}/s{section}{rest}"
    else:
        citation = f"Title {title}, United States Code (title-wide material)"
        href = None
        resolved_identifier = identifier or f"/us/usc/t{title}"
    return {
        "identifier": resolved_identifier,
        "title": title,
        "section": section,
        "citation": citation,
        "href": href,
        "historical": repealed,
        "inferred": inferred,
    }


def target_key(target: dict) -> tuple[str, str, str]:
    return (
        target.get("title") or "",
        target.get("section") or "",
        target.get("identifier") or "",
    )


def dedupe_targets(targets: list[dict]) -> list[dict]:
    unique: dict[tuple[str, str, str], dict] = {}
    for target in targets:
        unique.setdefault(target_key(target), target)
    return sorted(
        unique.values(),
        key=lambda item: (
            int(re.sub(r"\D", "", item["title"]) or 0),
            item.get("section") or "",
            item["identifier"],
        ),
    )


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
                f"{law['target_count']} Code location"
                f"{'' if law['target_count'] == 1 else 's'}."
            )
        else:
            law["summary"] = (
                f"Active law with {law['action_count']} recorded action"
                f"{'' if law['action_count'] == 1 else 's'} and no direct Code location."
            )

    ordered_laws = sorted(
        laws.values(), key=lambda item: law_sort_key(item["public_law"])
    )
    expected_total = ledger.get("summary", {}).get("total_laws", 270)
    if len(ordered_laws) != expected_total:
        raise SystemExit(
            f"Expected {expected_total} public laws, generated {len(ordered_laws)}."
        )
    if len(repealed_ids) != 129:
        raise SystemExit(f"Expected 129 repealed laws, found {len(repealed_ids)}.")
    if len(results.get("results", [])) != 903:
        raise SystemExit(
            f"Expected 903 integration actions, found {len(results.get('results', []))}."
        )

    clickable_targets = [
        target
        for law in ordered_laws
        for target in law.get("targets", [])
        if target.get("href")
    ]
    bad_clickable = [target for target in clickable_targets if not target.get("section")]
    if bad_clickable:
        raise SystemExit("Public-law page contains clickable title-only Code targets.")

    active_count = sum(law["status"] == "active" for law in ordered_laws)
    repealed_count = sum(law["status"] == "repealed" for law in ordered_laws)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_note": (
            "Statuses and Trello card links come from the authoritative USAR "
            "public-law archive. Code effects come from the completed codification action ledger."
        ),
        "trello_board_url": trello_data.get("board_url"),
        "counts": {
            "total": len(ordered_laws),
            "active": active_count,
            "repealed": repealed_count,
            "actions": len(results.get("results", [])),
            "laws_with_code_locations": sum(
                bool(law["targets"]) for law in ordered_laws
            ),
            "direct_section_links": len(clickable_targets),
            "trello_links": len(trello_links),
        },
        "laws": ordered_laws,
    }


def main() -> None:
    payload = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {payload['counts']['total']} laws, {payload['counts']['actions']} actions, "
        f"{payload['counts']['direct_section_links']} direct section links, and "
        f"{payload['counts']['trello_links']} Trello links to {OUTPUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
