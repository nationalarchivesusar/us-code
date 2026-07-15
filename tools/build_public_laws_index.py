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
OUTPUT = ROOT / "data" / "public-laws.json"

TARGET_RE = re.compile(
    r"^/us/usc/t(?P<title>\d+[A-Za-z]?)(?:/s(?P<section>[^/]+))?(?P<rest>/.*)?$"
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


def xml_title_number(action: dict) -> str | None:
    value = action.get("xml_file_after") or action.get("xml_file_before") or ""
    match = re.search(r"usc(\d+[A-Za-z]?)\.xml$", value.replace("\\", "/"))
    return match.group(1) if match else None


def target_from_action(action: dict, repealed: bool) -> dict | None:
    identifier = (action.get("final_section_or_subsection_identifier") or "").strip()
    title = None
    section = None
    rest = ""

    match = TARGET_RE.match(identifier)
    if match:
        title = match.group("title")
        section = match.group("section")
        rest = match.group("rest") or ""
    else:
        title = xml_title_number(action)

    if not title:
        return None

    pinpoint = "".join(f"({part})" for part in rest.strip("/").split("/") if part)
    if section:
        citation = f"{title} U.S.C. § {section}{pinpoint}"
        href = None
        if not repealed:
            href = f"cite/{quote(title)}/{quote(section)}/"
            if identifier and rest:
                href += f"?p={quote(identifier, safe='')}"
    else:
        citation = f"Title {title}, United States Code"
        href = None if repealed else f"./?t={quote(title)}"

    return {
        "identifier": identifier or f"/us/usc/t{title}",
        "title": title,
        "section": section,
        "citation": citation,
        "href": href,
        "historical": repealed,
    }


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

    candidates = [
        action.get("documented_no_op_explanation"),
        action.get("exact_enacted_text_applied"),
        action.get("validation_result"),
    ]
    for candidate in candidates:
        text = " ".join((candidate or "").split())
        if not text:
            continue
        if len(text) > 420:
            text = text[:417].rstrip() + "..."
        return text

    planned = " ".join((action.get("planned_action") or "").split())
    return planned or friendly_result_status(action.get("result_status") or "")


def build() -> dict:
    ledger = load_json(FINAL_LEDGER)
    results = load_json(INTEGRATION_RESULTS)
    repealed_data = load_json(REPEALED_LAWS)
    reconciliation = load_json(REPEAL_RECONCILIATION)

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
        missing = sorted(repealed_ids - reconciliation_ids)
        extra = sorted(reconciliation_ids - repealed_ids)
        raise SystemExit(
            f"Repealed-law status mismatch. Missing={missing[:5]} Extra={extra[:5]}"
        )

    laws: dict[str, dict] = {}
    for row in ledger.get("laws", []):
        law_id = row["law_id"]
        public_law = row["public_law"]
        repealed = law_id in repealed_ids
        laws[law_id] = {
            "law_id": law_id,
            "public_law": public_law,
            "title": clean_title(row.get("title", ""), public_law),
            "status": "repealed" if repealed else "active",
            "status_label": "Repealed" if repealed else "Active",
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
        target_index: dict[str, dict] = {}
        effect_categories: set[str] = set()

        for action in grouped_actions.get(law_id, []):
            category, effect_label = classify_action(action, repealed)
            target = target_from_action(action, repealed)
            if target:
                target_index.setdefault(target["identifier"], target)
            effect_categories.add(category)

            law["actions"].append(
                {
                    "action_id": action.get("action_id"),
                    "provision": action.get("provision_reference") or "Unspecified provision",
                    "effect_category": category,
                    "effect_label": effect_label,
                    "result_status": action.get("result_status"),
                    "result_label": friendly_result_status(
                        action.get("result_status") or ""
                    ),
                    "planned_action": action.get("planned_action"),
                    "treatment": action.get("planned_treatment"),
                    "target": target,
                    "description": compact_description(action, repealed),
                }
            )

        law["targets"] = sorted(
            target_index.values(),
            key=lambda item: (
                int(re.sub(r"\D", "", item["title"]) or 0),
                item.get("section") or "",
                item["identifier"],
            ),
        )
        law["effect_categories"] = sorted(effect_categories)
        law["action_count"] = len(law["actions"])
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

    ordered_laws = sorted(laws.values(), key=lambda item: law_sort_key(item["public_law"]))

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

    active_count = sum(law["status"] == "active" for law in ordered_laws)
    repealed_count = sum(law["status"] == "repealed" for law in ordered_laws)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_note": (
            "Statuses come from the authoritative USAR public-law archive. "
            "Code effects come from the completed codification action ledger."
        ),
        "counts": {
            "total": len(ordered_laws),
            "active": active_count,
            "repealed": repealed_count,
            "actions": len(results.get("results", [])),
            "laws_with_code_locations": sum(bool(law["targets"]) for law in ordered_laws),
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
        "Wrote "
        f"{payload['counts']['total']} laws and "
        f"{payload['counts']['actions']} actions to {OUTPUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
