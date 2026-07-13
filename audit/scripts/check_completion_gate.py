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
    "note-only-but-amendment-required",
    "source-limited-historical-note",
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


def main() -> int:
    failures: List[str] = []

    final_ledger = read_json(FINAL_LEDGER)
    provision_ledger = read_json(PROVISION_LEDGER)
    codex_progress = read_json(CODex_PROGRESS)
    unresolved = read_json(UNRESOLVED)
    full_validation = read_json(FULL_VALIDATION)
    canonical_validation = read_json(CANONICAL_VALIDATION)
    provision_map = read_json(PROVISION_MAP)

    final_laws = [law for law in final_ledger.get("laws", []) if isinstance(law, dict)]
    final_provisions = [prov for prov in provision_ledger.get("provisions", []) if isinstance(prov, dict)]
    full_reports = {item.get("review_report"): item for item in full_validation.get("reports", []) if isinstance(item, dict)}
    canonical_reports = {item.get("review_report"): item for item in canonical_validation.get("reports", []) if isinstance(item, dict)}

    require(len(final_laws) == 270, f"expected 270 final laws, found {len(final_laws)}", failures)
    require(final_ledger.get("summary", {}).get("total_laws") == 270, "final-ledger total_laws must be 270", failures)
    require(codex_progress.get("total_laws") == final_ledger.get("summary", {}).get("total_laws"), "codex-progress total_laws must match final-ledger", failures)
    require(codex_progress.get("completed_laws") == final_ledger.get("summary", {}).get("primary_complete"), "codex-progress completed_laws must match final-ledger primary_complete", failures)
    require(codex_progress.get("total_laws") == 270, "codex-progress total_laws must be 270", failures)
    require(final_ledger.get("summary", {}).get("high_risk") == codex_progress.get("total_laws", 0) - codex_progress.get("completed_laws", 0), "final-ledger high_risk must match progress remainder", failures)

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
        if classes & ACTION_CLASSES and treatment.lower() not in NOTE_TREATMENTS:
            require(nonempty(target), f"action provision {prov.get('law_id')} / {prov.get('ref')} missing target", failures)
            require(nonempty(exact_change), f"action provision {prov.get('law_id')} / {prov.get('ref')} missing exact change", failures)

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

    if failures:
        for message in failures:
            print(message)
        return 1

    print("completion gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
