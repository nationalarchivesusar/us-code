#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
PRIMARY_VALIDATION = ROOT / "audit" / "claude-validation.json"
CLASSIFICATION_CSV = ROOT / "codification" / "reference" / "all_270_laws_classification.csv"
REVIEW_DIR = ROOT / "audit" / "review"
REVIEW_RE = re.compile(r"^review-(\d{2})\.json$")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def review_reports() -> List[Path]:
    return sorted(p for p in REVIEW_DIR.glob("review-*.json") if REVIEW_RE.match(p.name))


def primary_by_law() -> Dict[str, Dict[str, Any]]:
    primary = read_json(PRIMARY_VALIDATION)
    return {law["law_id"]: law for law in primary.get("laws", [])}


def classification_by_law() -> Dict[str, Dict[str, str]]:
    if not CLASSIFICATION_CSV.exists():
        return {}
    import csv

    with CLASSIFICATION_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return {row["law_id"]: row for row in reader if row.get("law_id")}


def extract_review_status(law: Dict[str, Any]) -> Tuple[str, str]:
    for key in ("final_legal_status", "final_status", "status", "decision"):
        value = law.get(key)
        if value:
            return key, str(value)
    return "unknown", "unknown"


def extract_code_treatment(law: Dict[str, Any], status_key: str, status_value: str) -> str:
    for key in ("required_code_treatment", "required_code_treatment", "provision_level_disposition"):
        value = law.get(key)
        if value:
            return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    if status_key == "decision":
        return status_value
    return "unknown"


def normalize_review_law(
    law: Dict[str, Any],
    report_path: Path,
    report: Dict[str, Any],
    primary: Dict[str, Dict[str, Any]],
    classification: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    status_key, status_value = extract_review_status(law)
    code_treatment = extract_code_treatment(law, status_key, status_value)
    primary_law = primary.get(law["law_id"], {})
    class_row = classification.get(law["law_id"], {})
    blob = json.dumps(law, ensure_ascii=False).lower()

    current_impl = law.get("current_implementation")
    primary_validation = primary_law.get("validation_status")
    primary_source = primary_law.get("source_status")
    primary_impl = primary_law.get("current_implementation")

    disagreement_reasons: List[str] = []
    if primary_validation and primary_validation != status_value:
        disagreement_reasons.append("primary-validation-status-differs")
    if primary_source and primary_source != law.get("status") and status_key != "final_legal_status":
        disagreement_reasons.append("primary-source-status-differs")
    if primary_impl and isinstance(current_impl, dict):
        primary_impl_kind = primary_impl if isinstance(primary_impl, str) else primary_impl.get("assessment")
        review_impl_kind = current_impl.get("assessment") or current_impl.get("status") or current_impl.get("state")
        if primary_impl_kind and review_impl_kind and primary_impl_kind != review_impl_kind:
            disagreement_reasons.append("implementation-assessment-differs")

    resolved_status = status_value.lower().replace(" ", "_").replace("-", "_")
    if resolved_status in {"unresolved", "source_unavailable", "source_defect_unresolved", "unsupported_source"}:
        if "leave unresolved" in blob and class_row.get("current_status_analysis") != "repealed_recorded":
            resolved_status = "unresolved"
        elif any(
            term in blob
            for term in (
                "historical-note-only",
                "source-limited-historical-note",
                "retain only a concise historical note",
                "retain as source-limited history",
                "source-limited history",
                "history-only",
                "no current code text",
                "no code change",
            )
        ):
            resolved_status = "source_limited_historical_note"
        elif "statutory-note-only" in blob:
            resolved_status = "statutory_note_only"
        elif "keep only" in blob and "history" in blob:
            resolved_status = "source_limited_historical_note"
        elif class_row.get("current_status_analysis") == "repealed_recorded":
            resolved_status = "historical_note_only"
        elif class_row.get("classification") == "standalone_general_permanent":
            resolved_status = "source_limited_historical_note"

    return {
        "law_id": law.get("law_id"),
        "public_law": law.get("public_law"),
        "title": law.get("title"),
        "review_report": f"audit/review/{report_path.name}",
        "reviewer": report.get("reviewer"),
        "group_index": report.get("group_index"),
        "status_key": status_key,
        "status_value": status_value,
        "normalized_status": status_value.lower().replace(" ", "_").replace("-", "_"),
        "resolved_status": resolved_status,
        "required_code_treatment": code_treatment,
        "current_implementation": current_impl,
        "primary_validation_status": primary_validation,
        "primary_source_status": primary_source,
        "primary_current_implementation": primary_impl,
        "disagreement_reasons": disagreement_reasons,
    }


def build_review_validation() -> Dict[str, Any]:
    primary = primary_by_law()
    classification = classification_by_law()
    laws: List[Dict[str, Any]] = []
    disagreements: List[Dict[str, Any]] = []
    counts = collections.Counter()
    resolved_counts = collections.Counter()
    reports = []

    for report_path in review_reports():
        report = read_json(report_path)
        reports.append(f"audit/review/{report_path.name}")
        for law in report.get("laws") or []:
            normalized = normalize_review_law(law, report_path, report, primary, classification)
            laws.append(normalized)
            counts[normalized["normalized_status"]] += 1
            resolved_counts[normalized["resolved_status"]] += 1
            if normalized["disagreement_reasons"]:
                disagreements.append(normalized)

    return {
        "summary": {
            "review_reports": reports,
            "reviewed_laws": len(laws),
            "disagreements": len(disagreements),
            "distinct_statuses": sorted(counts),
            "status_counts": dict(counts),
            "resolved_status_counts": dict(resolved_counts),
            "resolved_unresolved_count": resolved_counts.get("unresolved", 0),
        },
        "laws": laws,
        "disagreements": disagreements,
    }


def main() -> None:
    review_validation = build_review_validation()
    write_json(ROOT / "audit" / "review-validation.json", review_validation)


if __name__ == "__main__":
    main()
