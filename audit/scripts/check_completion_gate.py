#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
FINAL_LEDGER = ROOT / "audit" / "final-ledger.json"
PROVISION_LEDGER = ROOT / "audit" / "provision-ledger.json"
CODex_PROGRESS = ROOT / "audit" / "codex-progress.json"
UNRESOLVED = ROOT / "audit" / "unresolved.json"
FULL_VALIDATION = ROOT / "audit" / "review-report-validation.json"
CANONICAL_VALIDATION = ROOT / "audit" / "review-validation.json"
PROVISION_MAP = ROOT / "audit" / "provision-consolidation-map.json"
CONTROLLING_INDEX = ROOT / "audit" / "controlling-review-index.json"
INTEGRATION_PLAN = ROOT / "audit" / "xml-integration-plan.json"

ACTION_CLASSES = {"direct-amendment", "repeal", "transfer", "redesignation", "substitution"}
NOTE_TREATMENTS = {
    "historical-note-only",
    "historical preservation",
    "historical-preservation",
    "historical-note",
    "statutory-note",
    "statutory-note-only",
    "transfer-note",
    "amendment-note",
    "exclude-from-code",
    "savings-note",
    "effective-date-note",
    "history-only",
    "note-only",
    "source-limited-historical-note",
}

EXECUTABLE_LAW_TREATMENTS = {
    "operative-text-required",
    "amend-existing-text",
    "new-section",
    "new-subsection",
    "repeal-marking",
    "transfer",
    "redesignation",
    "substitution",
}

EXECUTABLE_ACTION_TYPES = {
    "amend_existing_text",
    "insert_new_section",
    "insert_new_subsection",
    "repeal_or_remove_project_added_text",
    "redesignate",
    "transfer",
    "substitution",
}

TREATMENT_ACTION_MAP = {
    "new_section": "insert new section",
    "new_subsection": "insert new subsection",
    "amend_existing_text": "amend existing text",
    "repeal_marking": "repeal or remove project-added text",
    "redesignation": "redesignate",
    "transfer": "transfer",
    "substitution": "substitution",
    "statutory_note": "add statutory note",
    "statutory_note_only": "add statutory note",
    "note_only": "add statutory note",
    "historical_note_only": "add historical note",
    "historical_note": "add historical note",
    "history_only": "add historical note",
    "source_limited_historical_note": "add historical note",
    "amendment_note": "add amendment note",
    "effective_date_note": "add historical note",
    "savings_note": "add historical note",
    "transfer_note": "add statutory note",
    "exclude_from_code": "no Code action",
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def canonical_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        parts = [canonical_text(v) for v in value if canonical_text(v)]
        return " | ".join(parts)
    return json.dumps(value, ensure_ascii=False, sort_keys=True).strip()


def require(condition: bool, message: str, failures: List[str]) -> None:
    if not condition:
        failures.append(message)


def nonempty(value: Any) -> bool:
    return value not in (None, "", [], {})


def normalize_text(value: Any) -> str:
    return canonical_text(value).lower().replace("-", "_").replace(" ", "_")


def plan_requires_command(action_type: str) -> bool:
    normalized = normalize_text(action_type)
    return normalized in {
        "amend_existing_text",
        "insert_new_section",
        "insert_new_subsection",
        "repeal_or_remove_project_added_text",
        "redesignate",
        "transfer",
        "substitution",
    }


def plan_action_for_treatment(treatment: Any) -> str:
    return TREATMENT_ACTION_MAP.get(normalize_text(treatment), "no Code action")


def is_valid_node_identifier(value: Any) -> bool:
    text = canonical_text(value)
    if not text:
        return False
    if text.startswith("/") or "/us/usc/" in text or text.lower().endswith(".xml"):
        return False
    return True


def contains_inconsistent_command_text(value: Any) -> bool:
    text = canonical_text(value).lower()
    phrases = (
        "no operative text",
        "not section-level codification",
        "retain as repeal history only",
        "do not carry this into live code text",
        "do not retain live text",
        "history only",
    )
    return any(phrase in text for phrase in phrases)


def main() -> int:
    failures: List[str] = []

    final_ledger = read_json(FINAL_LEDGER)
    provision_ledger = read_json(PROVISION_LEDGER)
    codex_progress = read_json(CODex_PROGRESS)
    unresolved = read_json(UNRESOLVED)
    full_validation = read_json(FULL_VALIDATION)
    canonical_validation = read_json(CANONICAL_VALIDATION)
    provision_map = read_json(PROVISION_MAP)
    controlling_index = read_json(CONTROLLING_INDEX)
    integration_plan = read_json(INTEGRATION_PLAN)

    final_laws = [law for law in final_ledger.get("laws", []) if isinstance(law, dict)]
    final_provisions = [prov for prov in provision_ledger.get("provisions", []) if isinstance(prov, dict)]
    full_reports = {item.get("review_report"): item for item in full_validation.get("reports", []) if isinstance(item, dict)}
    canonical_reports = {item.get("review_report"): item for item in canonical_validation.get("reports", []) if isinstance(item, dict)}
    controlling_rows = [row for row in controlling_index.get("laws", []) if isinstance(row, dict)]
    plan_rows = [row for row in integration_plan.get("provisions", []) if isinstance(row, dict)]

    require(integration_plan.get("summary", {}).get("treatment_action_conflicts") == 0, "integration-plan treatment_action_conflicts must be zero", failures)
    require(integration_plan.get("summary", {}).get("invalid_node_identifiers") == 0, "integration-plan invalid_node_identifiers must be zero", failures)
    require(integration_plan.get("summary", {}).get("executable_actions_missing_targets") == 0, "integration-plan executable_actions_missing_targets must be zero", failures)
    require(integration_plan.get("summary", {}).get("executable_actions_missing_commands") == 0, "integration-plan executable_actions_missing_commands must be zero", failures)

    require(len(final_laws) == 270, f"expected 270 final laws, found {len(final_laws)}", failures)
    require(final_ledger.get("summary", {}).get("total_laws") == 270, "final-ledger total_laws must be 270", failures)
    require(final_ledger.get("summary", {}).get("reviewed_laws") == 270, "final-ledger reviewed_laws must be 270", failures)
    require(final_ledger.get("summary", {}).get("audit_complete_laws") == 270, "final-ledger audit_complete_laws must be 270", failures)
    require(codex_progress.get("total_laws") == final_ledger.get("summary", {}).get("total_laws"), "codex-progress total_laws must match final-ledger", failures)
    require(codex_progress.get("completed_laws") == final_ledger.get("summary", {}).get("primary_complete"), "codex-progress completed_laws must match final-ledger primary_complete", failures)
    require(codex_progress.get("total_laws") == 270, "codex-progress total_laws must be 270", failures)
    require(final_ledger.get("summary", {}).get("high_risk") == codex_progress.get("total_laws", 0) - codex_progress.get("completed_laws", 0), "final-ledger high_risk must match progress remainder", failures)
    require(final_ledger.get("summary", {}).get("high_risk_reviewed") == final_ledger.get("summary", {}).get("high_risk"), "high_risk_reviewed must match high_risk", failures)

    require(len(controlling_rows) == 270, f"controlling-review-index must contain 270 laws, found {len(controlling_rows)}", failures)
    require(final_ledger.get("summary", {}).get("audit_complete_laws") == len(controlling_rows), "audit_complete_laws must match controlling-review-index law count", failures)
    require(len(plan_rows) == 903, f"integration plan must contain 903 provisions, found {len(plan_rows)}", failures)

    require(len(unresolved.get("laws", [])) == 0, "unresolved.json must contain zero laws", failures)
    require(len(unresolved.get("provisions", [])) == 0, "unresolved.json must contain zero provisions", failures)

    require(final_ledger.get("summary", {}).get("controlling_invalid_reports", 0) == 0, "controlling_invalid_reports must be zero", failures)
    require(final_ledger.get("summary", {}).get("controlling_laws_with_issues", 0) == 0, "controlling_laws_with_issues must be zero", failures)
    require(final_ledger.get("summary", {}).get("controlling_provisions_with_issues", 0) == 0, "controlling_provisions_with_issues must be zero", failures)

    controlling_reports = set()
    for law in final_laws:
        report_path = law.get("review_report")
        require(nonempty(report_path), f"law {law.get('law_id')} missing review_report", failures)
        require(canonical_text(law.get("review_report_status")) == "valid", f"law {law.get('law_id')} has non-valid controlling report", failures)
        require(not law.get("review_issues"), f"law {law.get('law_id')} has controlling issues", failures)
        controlling_reports.add(report_path)

        controlling_row = next((row for row in controlling_rows if row.get("law_id") == law.get("law_id")), None)
        require(controlling_row is not None, f"missing controlling-review-index row for {law.get('law_id')}", failures)
        if controlling_row is not None:
            require(
                controlling_row.get("selected_controlling_report") == report_path,
                f"controlling-review-index disagrees with final-ledger for {law.get('law_id')}",
                failures,
            )
            latest_candidates = controlling_row.get("candidate_reports") or []
            if latest_candidates:
                latest = max(latest_candidates, key=lambda row: row.get("group_index", -1))
                latest_report = latest.get("review_report")
                if latest_report and latest_report != report_path:
                    superseded = set(controlling_row.get("superseded_reports") or [])
                    require(
                        latest_report in superseded,
                        f"latest candidate {latest_report} for {law.get('law_id')} must be formally superseded",
                        failures,
                    )

        report = full_reports.get(report_path)
        if report is None:
            report = canonical_reports.get(report_path)
        require(report is not None, f"missing validation record for {report_path}", failures)
        if report is not None:
            require(canonical_text(report.get("status")) == "valid", f"validation report {report_path} is not valid", failures)

        require(nonempty(law.get("review_status")), f"law {law.get('law_id')} missing review_status", failures)
        require(nonempty(law.get("review_chronology")), f"law {law.get('law_id')} missing chronology", failures)
        require(nonempty(law.get("review_treatment")), f"law {law.get('law_id')} missing treatment", failures)
        require(nonempty(law.get("review_recommended_action")), f"law {law.get('law_id')} missing final action", failures)
        require(nonempty(law.get("review_source_evidence")), f"law {law.get('law_id')} missing evidence", failures)
        require(nonempty(law.get("review_current_implementation")), f"law {law.get('law_id')} missing XML comparison", failures)
        require(nonempty(law.get("review_confidence")), f"law {law.get('law_id')} missing confidence", failures)
    for prov in final_provisions:
        classes = set(prov.get("classes") or [])
        treatment = canonical_text(prov.get("treatment"))
        target = canonical_text(prov.get("target"))
        evidence = canonical_text(prov.get("evidence"))
        exact_change = canonical_text(prov.get("exact_change"))

        require(nonempty(treatment), f"provision {prov.get('law_id')} / {prov.get('ref')} missing final treatment", failures)
        require(nonempty(evidence), f"provision {prov.get('law_id')} / {prov.get('ref')} missing evidence", failures)
        if classes & ACTION_CLASSES and normalize_text(treatment) not in {normalize_text(t) for t in NOTE_TREATMENTS}:
            require(nonempty(target), f"action provision {prov.get('law_id')} / {prov.get('ref')} missing target", failures)
            require(nonempty(exact_change), f"action provision {prov.get('law_id')} / {prov.get('ref')} missing exact change", failures)
        if normalize_text(treatment) in EXECUTABLE_LAW_TREATMENTS:
            require(nonempty(target), f"executable provision {prov.get('law_id')} / {prov.get('ref')} missing target", failures)
            require(nonempty(exact_change), f"executable provision {prov.get('law_id')} / {prov.get('ref')} missing exact change", failures)

        plan_row = next((row for row in plan_rows if row.get("law_id") == prov.get("law_id") and row.get("provision_reference") == prov.get("ref")), None)
        require(plan_row is not None, f"missing integration-plan row for {prov.get('law_id')} / {prov.get('ref')}", failures)
        if plan_row is not None:
            require(nonempty(plan_row.get("action_id")), f"integration-plan row missing action_id for {prov.get('law_id')} / {prov.get('ref')}", failures)
            require(plan_row.get("action_type") is not None, f"integration-plan row missing action_type for {prov.get('law_id')} / {prov.get('ref')}", failures)
            expected_action = plan_action_for_treatment(treatment)
            require(
                canonical_text(plan_row.get("action_type")) == expected_action,
                f"provision {prov.get('law_id')} / {prov.get('ref')} treatment-action conflict",
                failures,
            )
            require(
                not (normalize_text(treatment) in {"historical_note_only", "historical_note", "history_only", "source_limited_historical_note"} and normalize_text(plan_row.get("action_type")) in EXECUTABLE_ACTION_TYPES),
                f"historical-note treatment has executable action for {prov.get('law_id')} / {prov.get('ref')}",
                failures,
            )
            require(
                not (normalize_text(treatment) in {"statutory_note", "statutory_note_only", "note_only", "effective_date_note", "savings_note", "transfer_note"} and normalize_text(plan_row.get("action_type")) in EXECUTABLE_ACTION_TYPES),
                f"statutory-note treatment has operative-text action for {prov.get('law_id')} / {prov.get('ref')}",
                failures,
            )
            require(
                not (normalize_text(treatment) == "exclude_from_code" and normalize_text(plan_row.get("action_type")) != "no_code_action"),
                f"exclude-from-code treatment has non-no-op action for {prov.get('law_id')} / {prov.get('ref')}",
                failures,
            )
            if normalize_text(plan_row.get("action_type")) in EXECUTABLE_ACTION_TYPES:
                require(nonempty(plan_row.get("target_xml_file")), f"executable integration-plan row missing target_xml_file for {prov.get('law_id')} / {prov.get('ref')}", failures)
                require(nonempty(plan_row.get("exact_uslm_code_identifier")), f"executable integration-plan row missing exact identifier for {prov.get('law_id')} / {prov.get('ref')}", failures)
                require(nonempty(plan_row.get("exact_textual_command_or_final_statutory_text")), f"executable integration-plan row missing exact command for {prov.get('law_id')} / {prov.get('ref')}", failures)
                require(not contains_inconsistent_command_text(plan_row.get("exact_textual_command_or_final_statutory_text")), f"inconsistent executable command for {prov.get('law_id')} / {prov.get('ref')}", failures)
            node_ids = plan_row.get("existing_project_node_ids_to_remove_or_replace") or []
            require(all(is_valid_node_identifier(v) for v in node_ids), f"invalid node identifier for {prov.get('law_id')} / {prov.get('ref')}", failures)
        if normalize_text(treatment) in EXECUTABLE_LAW_TREATMENTS or (plan_row is not None and normalize_text(plan_row.get("action_type")) in EXECUTABLE_ACTION_TYPES):
            require(nonempty(target) or nonempty(law.get("exact_target")) or nonempty(plan_row.get("exact_uslm_code_identifier")), f"executable provision {prov.get('law_id')} / {prov.get('ref')} missing exact target", failures)
            require(nonempty(exact_change) or nonempty(law.get("exact_enacted_text_or_amendment_command")) or nonempty(plan_row.get("exact_textual_command_or_final_statutory_text")), f"executable provision {prov.get('law_id')} / {prov.get('ref')} missing exact change", failures)

    mapping_rows = provision_map.get("mappings", [])
    require(len(mapping_rows) == 1777, f"expected 1777 source provision mappings, found {len(mapping_rows)}", failures)
    unique_consolidated = {
        (
            row.get("consolidated", {}).get("law_id"),
            row.get("consolidated", {}).get("ref"),
            row.get("consolidated", {}).get("batch"),
            row.get("consolidated", {}).get("index"),
        )
        for row in mapping_rows
        if isinstance(row, dict) and isinstance(row.get("consolidated"), dict)
    }
    require(len(unique_consolidated) == 903, f"expected 903 canonical provisions, found {len(unique_consolidated)}", failures)
    require(len(final_provisions) == 903, f"expected 903 provisions in provision-ledger, found {len(final_provisions)}", failures)
    require(provision_ledger.get("summary", {}).get("source_provision_count") == 1777, "provision-ledger source_provision_count must be 1777", failures)
    require(provision_ledger.get("summary", {}).get("consolidated_provision_count") == 903, "provision-ledger consolidated_provision_count must be 903", failures)
    require(provision_ledger.get("summary", {}).get("action_provisions_missing_target") == 0, "action_provisions_missing_target must be zero", failures)

    require(final_ledger.get("summary", {}).get("controlling_invalid_reports", 0) == 0, "controlling_invalid_reports must remain zero", failures)
    require(final_ledger.get("summary", {}).get("controlling_laws_with_issues", 0) == 0, "controlling_laws_with_issues must remain zero", failures)
    require(final_ledger.get("summary", {}).get("controlling_provisions_with_issues", 0) == 0, "controlling_provisions_with_issues must remain zero", failures)
    require(final_ledger.get("summary", {}).get("primary_complete") is not None, "final-ledger primary_complete missing", failures)
    require(final_ledger.get("summary", {}).get("high_risk_reviewed") is not None, "final-ledger high_risk_reviewed missing", failures)
    require(final_ledger.get("summary", {}).get("audit_complete_laws") is not None, "final-ledger audit_complete_laws missing", failures)

    if failures:
        for message in failures:
            print(message)
        return 1

    print("completion gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
