#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from merge_review_resolution import (
    canonical_text,
    canonical_xml_file,
    review_chronology,
    review_evidence,
    review_exact_change,
    review_exact_target,
    review_provisions,
    review_recommendation,
    review_status,
    review_targets,
    review_treatment,
    review_xml,
)


ROOT = Path(__file__).resolve().parents[2]
FINAL_LEDGER = ROOT / "audit" / "final-ledger.json"
PROVISION_LEDGER = ROOT / "audit" / "provision-ledger.json"
FULL_VALIDATION = ROOT / "audit" / "review-report-validation.json"
REVIEW_DIR = ROOT / "audit" / "review"
CONTROLLING_INDEX = ROOT / "audit" / "controlling-review-index.json"
XML_PLAN = ROOT / "audit" / "xml-integration-plan.json"
CURRENT_IMPLEMENTATION = ROOT / "audit" / "current-implementation.json"

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

EXECUTABLE_TREATMENTS = {
    "operative-text-required",
    "amend-existing-text",
    "new-section",
    "new-subsection",
    "repeal-marking",
    "transfer",
    "redesignation",
    "substitution",
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def normalize_text(value: Any) -> str:
    return canonical_text(value).lower().replace("-", "_")


def report_manifest_index(source_manifest: str, report_path: str) -> int:
    m = re.search(r"manifest-(\d{2})\.json$", source_manifest or "")
    if m:
        return int(m.group(1))
    m = re.search(r"review-repair-(\d{2})(?:-(\d{2}))?\.json$", report_path or "")
    if m:
        return 1000 + int(m.group(1)) * 10 + int(m.group(2) or 0)
    m = re.search(r"review-(\d{2})\.json$", report_path or "")
    if m:
        return int(m.group(1))
    return 0


def review_kind(report_path: str) -> str:
    stem = Path(report_path).stem
    if stem.startswith("review-repair-"):
        return "repair"
    if stem.startswith("review-"):
        return "review"
    return "unknown"


def scan_review_files() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for path in sorted(REVIEW_DIR.glob("review-*.json")):
        try:
            out[f"audit/review/{path.name}"] = read_json(path)
        except Exception:
            continue
    return out


def validation_by_report(full_validation: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {row.get("review_report"): row for row in full_validation.get("reports", []) if isinstance(row, dict)}


def law_candidates(
    review_files: Dict[str, Dict[str, Any]],
    validations: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    candidates: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for report_path, report in review_files.items():
        source_manifest = str(report.get("source_manifest") or "")
        validation = validations.get(report_path, {})
        report_status = canonical_text(validation.get("status") or report.get("status"))
        report_issues = list(validation.get("issues") or report.get("issues") or [])
        for law in report.get("laws") or []:
            if not isinstance(law, dict):
                continue
            law_id = str(law.get("law_id") or "")
            if not law_id:
                continue
            law_issues = list(law.get("issues") or [])
            candidate = {
                "review_report": report_path,
                "group_index": report_manifest_index(source_manifest, report_path),
                "source_manifest": source_manifest,
                "validation_status": report_status,
                "report_issues": report_issues,
                "law_id": law_id,
                "public_law": law.get("public_law"),
                "title": law.get("title"),
                "legal_conclusion": canonical_text(law.get("status") or review_status(law)),
                "treatment": canonical_text(law.get("approved_code_treatment") or law.get("required_code_treatment") or law.get("code_treatment") or law.get("treatment")),
                "targets": review_targets(law),
                "exact_change": review_exact_change(law),
                "declares_repair_or_replacement": review_kind(report_path) == "repair",
                "law_issues": law_issues,
                "review_issues": law_issues,
                "reviewed_against": list(report.get("reviewed_against") or []),
                "source_evidence": list(law.get("source_evidence") or []),
                "current_xml_comparison": canonical_text(law.get("current_xml_comparison") or review_xml(law)),
                "confidence": canonical_text(law.get("confidence")),
                "chronology": canonical_text(law.get("chronology_conclusion") or law.get("chronology") or review_chronology(law)),
                "recommended_action": canonical_text(law.get("final_recommended_action") or review_recommendation(law)),
            }
            candidates[law_id].append(candidate)
    return candidates


def select_controlling_candidate(candidates: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], str, List[str], List[Dict[str, Any]]]:
    if not candidates:
        placeholder = {
            "review_report": "",
            "group_index": -1,
            "source_manifest": "",
            "validation_status": "missing",
            "law_issues": ["missing review candidate"],
            "legal_conclusion": "",
            "treatment": "",
            "targets": [],
            "exact_change": "",
            "declares_repair_or_replacement": False,
        }
        return placeholder, "no candidate reports were available", [], []

    def score(row: Dict[str, Any]) -> Tuple[int, int, int, int, int]:
        return (
            1 if row.get("validation_status") == "valid" else 0,
            int(row.get("group_index") or 0),
            1 if row.get("legal_conclusion") else 0,
            1 if row.get("treatment") else 0,
            1 if row.get("exact_change") else 0,
        )

    ranked = sorted(candidates, key=score, reverse=True)
    selected = ranked[0]
    superseded = [row["review_report"] for row in ranked[1:]]
    conflicting = []
    for row in ranked[1:]:
        if row.get("legal_conclusion") != selected.get("legal_conclusion") or row.get("treatment") != selected.get("treatment") or row.get("targets") != selected.get("targets"):
            conflicting.append(
                {
                    "review_report": row.get("review_report"),
                    "legal_conclusion": row.get("legal_conclusion"),
                    "treatment": row.get("treatment"),
                    "targets": row.get("targets"),
                    "exact_change": row.get("exact_change"),
                    "issues": row.get("law_issues"),
                }
            )
    reason = "selected as the latest valid candidate with the most complete law-level record"
    if selected.get("validation_status") != "valid":
        reason = "selected as the best available candidate because no fully valid law-level candidate was available"
    elif selected.get("declares_repair_or_replacement"):
        reason = "selected as a valid repair or replacement report that supersedes earlier conflicting candidates"
    return selected, reason, superseded, conflicting


def build_controlling_review_index(final_ledger: Dict[str, Any], review_files: Dict[str, Dict[str, Any]], validations: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    candidate_map = law_candidates(review_files, validations)
    laws = []
    for law in final_ledger.get("laws", []) or []:
        if not isinstance(law, dict):
            continue
        law_id = str(law.get("law_id") or "")
        candidates = candidate_map.get(law_id, [])
        selected, reason, superseded, conflicting = select_controlling_candidate(candidates)
        laws.append(
            {
                "law_id": law_id,
                "public_law": law.get("public_law"),
                "title": law.get("title"),
                "candidate_reports": candidates,
                "selected_controlling_report": selected.get("review_report"),
                "selected_validation_status": selected.get("validation_status"),
                "selected_legal_conclusion": selected.get("legal_conclusion"),
                "selected_treatment": selected.get("treatment"),
                "selected_targets": selected.get("targets"),
                "selected_declares_repair_or_replacement": selected.get("declares_repair_or_replacement"),
                "selection_reason": reason,
                "superseded_reports": superseded,
                "conflicting_conclusions": conflicting,
            }
        )
    return {
        "summary": {
            "law_count": len(laws),
            "selected_valid_reports": sum(1 for row in laws if row.get("selected_validation_status") == "valid"),
            "controlling_reports": len({row.get("selected_controlling_report") for row in laws if row.get("selected_controlling_report")}),
        },
        "laws": laws,
    }


def current_node_ids_by_law() -> Dict[str, List[str]]:
    data = read_json(CURRENT_IMPLEMENTATION)
    out: Dict[str, List[str]] = collections.defaultdict(list)
    by_public_law = data.get("by_public_law") or {}
    if isinstance(by_public_law, dict):
        for public_law, entries in by_public_law.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for candidate in [entry.get("note_id"), entry.get("placement_identifier"), entry.get("identifier"), entry.get("file")]:
                    if candidate and candidate not in out[str(public_law)]:
                        out[str(public_law)].append(str(candidate))
    notes_section = data.get("notes") or {}
    if isinstance(notes_section, dict):
        notes_iter = notes_section.items()
    else:
        notes_iter = []
    for law_id, entries in notes_iter:
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for candidate in [entry.get("note_id"), entry.get("placement_identifier"), entry.get("identifier")]:
                if candidate and candidate not in out[str(law_id)]:
                    out[str(law_id)].append(str(candidate))
    return out


def plan_action_type(law: Dict[str, Any], prov: Dict[str, Any], target_xml_file: str, exact_text: str) -> str:
    treatment = normalize_text(prov.get("treatment"))
    classes = set(prov.get("classes") or [])
    summary = canonical_text(prov.get("text_summary")).lower()
    if treatment in {"new_section", "new_subsection", "amend_existing_text"} and target_xml_file and exact_text:
        if treatment == "new_subsection" or "definition" in summary or "definitions" in summary:
            return "insert new subsection"
        if treatment == "amend_existing_text":
            return "amend existing text"
        return "insert new section"
    if treatment in {"repeal_marking"} and target_xml_file and exact_text:
        return "repeal or remove project-added text"
    if treatment in {"transfer", "transfer_note"} and target_xml_file and exact_text:
        return "transfer"
    if treatment in {"redesignation"} and target_xml_file and exact_text:
        return "redesignate"
    if treatment in {"substitution"} and target_xml_file and exact_text:
        return "substitution"
    if "short-title" in classes or "findings-or-sense" in classes:
        return "add statutory note"
    if "effective-date" in classes:
        return "add historical note"
    if normalize_text(law.get("review_status")) in {"current", "operative_text_required"} and "new-permanent-general" in classes and target_xml_file and exact_text:
        if "definition" in summary:
            return "insert new subsection"
        return "insert new section"
    if treatment in NOTE_TREATMENTS:
        if "amendment" in treatment:
            return "add amendment note"
        if "historical" in treatment or "history" in treatment:
            return "add historical note"
        return "add statutory note"
    return "no Code action"


def build_xml_integration_plan(final_ledger: Dict[str, Any], provision_ledger: Dict[str, Any]) -> Dict[str, Any]:
    final_by_law = {str(law.get("law_id") or ""): law for law in final_ledger.get("laws", []) or []}
    node_ids = current_node_ids_by_law()
    rows = []
    for idx, prov in enumerate(provision_ledger.get("provisions", []) or [], start=1):
        if not isinstance(prov, dict):
            continue
        law = final_by_law.get(str(prov.get("law_id") or ""), {})
        treatment = canonical_text(prov.get("treatment"))
        target = canonical_text(prov.get("target") or law.get("exact_target"))
        exact_text = canonical_text(
            prov.get("exact_change")
            or prov.get("review_exact_change")
            or law.get("exact_enacted_text_or_amendment_command")
            or law.get("review_exact_change")
        )
        if not exact_text:
            exact_text = canonical_text(prov.get("text_summary"))
        target_xml = canonical_xml_file(target) or canonical_xml_file(canonical_text(law.get("exact_target")))
        action_type = plan_action_type(law, prov, target_xml, exact_text)
        identifiers = list(node_ids.get(str(prov.get("public_law") or ""), []))
        if not identifiers and target:
            identifiers.append(f"{target}::{prov.get('ref')}")
        source_evidence = []
        for candidate in [prov.get("evidence"), prov.get("review_evidence"), law.get("review_source_evidence")]:
            if isinstance(candidate, list):
                source_evidence.extend([canonical_text(v) for v in candidate if canonical_text(v)])
            elif candidate:
                source_evidence.append(canonical_text(candidate))
        rows.append(
            {
                "action_id": f"ACTION-{idx:04d}",
                "law_id": prov.get("law_id"),
                "public_law": prov.get("public_law"),
                "provision_reference": prov.get("ref"),
                "final_legal_status": law.get("review_status") or law.get("status"),
                "action_type": action_type,
                "treatment": treatment,
                "target_xml_file": target_xml,
                "exact_uslm_code_identifier": target or f"{prov.get('law_id')}::{prov.get('ref')}",
                "exact_textual_command_or_final_statutory_text": exact_text,
                "source_evidence": source_evidence,
                "chronology_dependencies": [canonical_text(law.get("review_chronology") or law.get("status_basis"))] if canonical_text(law.get("review_chronology") or law.get("status_basis")) else [],
                "existing_project_node_ids_to_remove_or_replace": identifiers,
                "source_credit_required": action_type in {"add statutory note", "add historical note", "add amendment note"},
                "amendment_note_required": action_type in {"amend existing text", "insert new section", "insert new subsection", "repeal or remove project-added text", "redesignate", "transfer", "substitution"},
                "toc_update_required": action_type in {"insert new section", "insert new subsection", "redesignate", "transfer"},
                "documented_no_op_or_exclusion": action_type == "no Code action",
            }
        )
    return {
        "summary": {
            "provision_count": len(rows),
            "executable_action_count": sum(1 for row in rows if row["action_type"] not in {"no Code action", "add statutory note", "add historical note", "add amendment note"}),
        },
        "provisions": rows,
    }


def main() -> None:
    final_ledger = read_json(FINAL_LEDGER)
    provision_ledger = read_json(PROVISION_LEDGER)
    full_validation = read_json(FULL_VALIDATION)
    review_files = scan_review_files()
    validations = validation_by_report(full_validation)
    controlling_index = build_controlling_review_index(final_ledger, review_files, validations)
    xml_plan = build_xml_integration_plan(final_ledger, provision_ledger)
    write_json(CONTROLLING_INDEX, controlling_index)
    write_json(XML_PLAN, xml_plan)


if __name__ == "__main__":
    main()
