#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
FINAL_LEDGER = ROOT / "audit" / "final-ledger.json"
PROVISION_LEDGER = ROOT / "audit" / "provision-ledger.json"
PROVISION_MAP = ROOT / "audit" / "provision-consolidation-map.json"
CANONICAL_REVIEW_VALIDATION = ROOT / "audit" / "review-validation.json"
FULL_REVIEW_VALIDATION = ROOT / "audit" / "review-report-validation.json"
UNRESOLVED = ROOT / "audit" / "unresolved.json"
REVIEW_DIR = ROOT / "audit" / "review"

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

ACTION_CLASSES = {"direct-amendment", "repeal", "transfer", "redesignation", "substitution"}
NON_COMPLETED_STATUSES = {
    "unresolved",
    "unknown",
    "source-defect-unresolved",
    "source-unavailable",
    "unsupported-source",
    "operative-text-required-but-target-unresolved",
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def canonical_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        parts = [canonical_text(v) for v in value if canonical_text(v)]
        return " | ".join(parts)
    return json.dumps(value, ensure_ascii=False, sort_keys=True).strip()


def normalize_text(value: Any) -> str:
    return canonical_text(value).lower().replace("-", "_")


def first_nonempty_text(data: Dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        if key not in data:
            continue
        text = canonical_text(data.get(key))
        if text:
            return text
    return ""


def list_text(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [canonical_text(v) for v in value if canonical_text(v)]
    if isinstance(value, tuple):
        return [canonical_text(v) for v in value if canonical_text(v)]
    text = canonical_text(value)
    return [text] if text else []


def report_index(report_path: str) -> int:
    stem = Path(report_path).stem
    m = re.match(r"review-(\d{2})$", stem)
    return int(m.group(1)) if m else -1


def report_selection_key(report_path: str, validation: Dict[str, Any]) -> tuple[int, int, int, str]:
    manifest = canonical_text(validation.get("manifest"))
    m = re.search(r"manifest-(\d{2})\.json$", manifest)
    if m:
        return (int(m.group(1)), 0, 0, report_path)
    repair_manifest = re.search(r"review-repair-(\d{2})(?:-(\d{2}))?\.json$", manifest)
    if repair_manifest:
        base = int(repair_manifest.group(1))
        sub = int(repair_manifest.group(2) or 0)
        return (1000 + base * 10 + sub, 0, 0, report_path)
    stem = Path(report_path).stem
    repair = re.match(r"review-repair-(\d{2})(?:-(\d{2}))?$", stem)
    if repair:
        base = int(repair.group(1))
        sub = int(repair.group(2) or 0)
        return (1000 + base * 10 + sub, 1, sub, report_path)
    canonical = re.match(r"review-(\d{2})$", stem)
    if canonical:
        return (int(canonical.group(1)), 0, 0, report_path)
    return (-1, 0, 0, report_path)


def validation_by_report() -> Dict[str, Dict[str, Any]]:
    data = read_json(FULL_REVIEW_VALIDATION)
    return {report["review_report"]: report for report in data.get("reports", [])}


def latest_review_laws() -> Dict[str, Tuple[int, str, Dict[str, Any], Dict[str, Any]]]:
    validation_reports = validation_by_report()
    review_reports: Dict[str, Dict[str, Any]] = {}
    for path in sorted(REVIEW_DIR.glob("review-*.json")):
        try:
            review_reports[f"audit/review/{path.name}"] = read_json(path)
        except Exception:
            continue

    latest: Dict[str, Tuple[int, str, Dict[str, Any], Dict[str, Any]]] = {}
    for report_path, validation in validation_reports.items():
        if (validation.get("status") or "").lower() != "valid":
            continue
        idx = report_selection_key(report_path, validation)
        report = review_reports.get(report_path, {})
        report_laws = report.get("laws", []) or []
        validation_laws = {str(law.get("law_id") or ""): law for law in validation.get("laws", [])}
        for review_law in report_laws:
            if not isinstance(review_law, dict):
                continue
            lid = str(review_law.get("law_id") or "")
            if not lid:
                continue
            current = latest.get(lid)
            if current is None or idx >= current[0]:
                latest[lid] = (idx, report_path, review_law, validation_laws.get(lid, {}))
    return latest


def review_status(review_law: Dict[str, Any]) -> str:
    return first_nonempty_text(review_law, ("final_legal_status", "final_status", "status", "decision"))


def review_chronology(review_law: Dict[str, Any]) -> str:
    return first_nonempty_text(review_law, ("chronology", "chronology_conclusion", "chronology_analysis", "status_basis"))


def review_treatment(review_law: Dict[str, Any]) -> str:
    return first_nonempty_text(
        review_law,
        (
            "required_code_treatment",
            "approved_code_treatment",
            "approved_code_treatment_summary",
            "code_treatment",
            "treatment",
            "provision_level_disposition",
            "provision_disposition",
            "disposition",
        ),
    )


def review_recommendation(review_law: Dict[str, Any]) -> str:
    return first_nonempty_text(review_law, ("final_recommended_action", "recommended_action", "recommended_actions"))


def review_evidence(review_law: Dict[str, Any]) -> str:
    return first_nonempty_text(review_law, ("source_evidence", "evidence", "status_basis", "rationale"))


def review_xml(review_law: Dict[str, Any]) -> str:
    return first_nonempty_text(review_law, ("current_implementation", "current_xml_comparison"))


def review_targets(review_law: Dict[str, Any]) -> List[str]:
    targets = review_law.get("targets")
    if isinstance(targets, list):
        values = [canonical_text(v) for v in targets if canonical_text(v)]
        if values:
            return values
    if isinstance(targets, (str, int, float)):
        text = canonical_text(targets)
        if text:
            return [text]
    target = canonical_text(review_law.get("target") or review_law.get("exact_target"))
    if target:
        return [target]
    target_resolution = review_law.get("target_resolution")
    if isinstance(target_resolution, dict):
        target = canonical_text(target_resolution.get("target"))
        if target:
            return [target]
    target_or_non_target = canonical_text(review_law.get("target_or_non_target"))
    if target_or_non_target.lower().startswith("target:"):
        candidate = target_or_non_target.split(":", 1)[1].strip()
        if candidate:
            return [candidate]
    return []


def review_provisions(review_law: Dict[str, Any]) -> List[Dict[str, Any]]:
    provs = review_law.get("provisions")
    return provs if isinstance(provs, list) else []


def provision_target_value(review_prov: Dict[str, Any]) -> str:
    target = canonical_text(review_prov.get("target") or review_prov.get("exact_target"))
    if target:
        return target
    target_resolution = review_prov.get("target_resolution")
    if isinstance(target_resolution, dict):
        target = canonical_text(target_resolution.get("target"))
        if target:
            return target
    target_or_non_target = canonical_text(review_prov.get("target_or_non_target"))
    if target_or_non_target.lower().startswith("target:"):
        candidate = target_or_non_target.split(":", 1)[1].strip()
        if candidate:
            return candidate
    return ""


def provision_exact_change_value(review_prov: Dict[str, Any]) -> str:
    return first_nonempty_text(
        review_prov,
        ("exact_change", "final_statutory_text", "enacted_text_or_amendment_command", "exact_action", "enacted_effect"),
    )


def review_exact_target(review_law: Dict[str, Any]) -> str:
    target = canonical_text(review_law.get("target") or review_law.get("exact_target"))
    if target:
        return target
    target_resolution = review_law.get("target_resolution")
    if isinstance(target_resolution, dict):
        return canonical_text(target_resolution.get("target"))
    return ""


def review_exact_change(review_law: Dict[str, Any]) -> str:
    return first_nonempty_text(
        review_law,
        (
            "exact_change",
            "exact_enacted_change",
            "exact_enacted_text",
            "exact_enacted_text_or_amendment_command",
            "enacted_text_or_amendment_command",
            "final_statutory_text",
            "final_amendment_command",
            "amendment_command",
            "exact_action",
            "enacted_effect",
        ),
    )


def review_exact_target(review_law: Dict[str, Any]) -> str:
    target = canonical_text(review_law.get("target") or review_law.get("exact_target"))
    if target:
        return target
    target_resolution = review_law.get("target_resolution")
    if isinstance(target_resolution, dict):
        target = canonical_text(target_resolution.get("target"))
        if target:
            return target
    target_or_non_target = canonical_text(review_law.get("target_or_non_target"))
    if target_or_non_target.lower().startswith("target:"):
        return target_or_non_target.split(":", 1)[1].strip()
    return ""


def final_provisions_by_law(provision_ledger: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for prov in provision_ledger.get("provisions", []) or []:
        if isinstance(prov, dict):
            out[str(prov.get("law_id") or "")].append(prov)
    return out


def merge_provision_details(final_prov: Dict[str, Any], review_prov: Dict[str, Any]) -> None:
    final_prov["treatment"] = (
        review_prov.get("treatment")
        or review_prov.get("code_treatment")
        or review_prov.get("approved_code_treatment")
        or review_prov.get("disposition")
        or review_prov.get("approved_code_treatment_summary")
    )
    final_prov["review_treatment"] = final_prov["treatment"]
    final_prov["target"] = provision_target_value(review_prov)
    final_prov["review_target"] = final_prov["target"]
    final_prov["exact_change"] = provision_exact_change_value(review_prov)
    final_prov["review_exact_change"] = final_prov["exact_change"]
    final_prov["review_evidence"] = review_prov.get("evidence") or review_prov.get("source_evidence")
    final_prov["review_notes"] = review_prov.get("notes")
    final_prov["review_classes"] = review_prov.get("classes")
    final_prov["review_refs"] = review_prov.get("refs") or review_prov.get("ref")
    final_prov["review_current_implementation"] = review_prov.get("current_implementation")
    final_prov["review_recommended_action"] = review_prov.get("recommended_action") or review_prov.get("recommended_actions")
    final_prov["review_confidence"] = review_prov.get("confidence")
    final_prov["review_exact_target"] = provision_target_value(review_prov)


def source_provisions_by_law(provision_map: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for row in provision_map.get("mappings", []) or []:
        if not isinstance(row, dict):
            continue
        src = row.get("source")
        if isinstance(src, dict):
                out[str(src.get("law_id") or "")].append(src)
    return out


def normalize_canonical_provision(
    final_law: Dict[str, Any],
    final_prov: Dict[str, Any],
    source_prov: Dict[str, Any] | None = None,
) -> None:
    law_status = normalize_text(final_law.get("review_status") or final_law.get("status") or "")
    law_treatment = normalize_text(final_law.get("review_treatment") or final_law.get("review_required_treatment") or "")
    if not law_treatment:
        law_treatment = normalize_text(review_treatment(final_law))

    classes = set(final_prov.get("classes") or [])
    if source_prov and not classes:
        classes = set(source_prov.get("classes") or [])

    summary = canonical_text(final_prov.get("text_summary") or (source_prov or {}).get("text_summary")).lower()

    target = canonical_text(final_prov.get("target") or (source_prov or {}).get("target") or final_law.get("exact_target"))
    exact_change = canonical_text(
        final_prov.get("exact_change")
        or (source_prov or {}).get("exact_change")
        or final_law.get("exact_enacted_text_or_amendment_command")
        or final_law.get("review_exact_change")
    )

    if "short-title" in classes or "findings-or-sense" in classes:
        final_prov["treatment"] = "statutory-note"
        if not exact_change:
            exact_change = "Add statutory note material at the current Title 28 anchor."
    elif "effective-date" in classes:
        final_prov["treatment"] = "historical-note-only"
        if not exact_change:
            exact_change = "Retain as historical enactment context only."
    elif "new-permanent-general" in classes and law_treatment in {
        "operative_text_required",
        "amend_existing_text",
        "new_section",
        "new_subsection",
        "repeal_marking",
        "transfer",
        "redesignation",
        "substitution",
    }:
        if "definition" in summary or "definitions" in summary:
            final_prov["treatment"] = "new-subsection"
        elif "purpose" in summary:
            final_prov["treatment"] = "statutory-note"
        else:
            final_prov["treatment"] = "new-section"
        exact_change = final_law.get("exact_enacted_text_or_amendment_command") or final_law.get("review_exact_change") or exact_change
        if not exact_change:
            exact_change = "Place the operative text in Title 28 text."
        if not target:
            target = final_law.get("exact_target") or target
    elif law_status in {"fully_repealed", "repealed", "historical_note_only"}:
        final_prov["treatment"] = "historical-note-only"
        if not exact_change:
            exact_change = "Keep as history only."

    final_prov["target"] = target
    final_prov["exact_change"] = exact_change
    final_prov["review_treatment"] = final_prov.get("treatment")
    final_prov["review_target"] = target
    final_prov["review_exact_target"] = target
    final_prov["review_exact_change"] = exact_change
    final_prov["review_evidence"] = (source_prov or {}).get("evidence") or final_prov.get("evidence")
    final_prov["review_current_implementation"] = final_law.get("review_current_implementation")
    final_prov["review_recommended_action"] = final_law.get("review_recommended_action")
    final_prov["review_confidence"] = final_law.get("review_confidence") or final_law.get("confidence")


def compare_law_fields(final_law: Dict[str, Any], review_law: Dict[str, Any]) -> List[str]:
    disagreements: List[str] = []

    final_status = normalize_text(final_law.get("source_status") or final_law.get("validation_status"))
    review_status_text = normalize_text(review_status(review_law))
    if final_status and review_status_text and final_status != review_status_text:
        disagreements.append("legal-status disagreement")

    final_chrono = normalize_text(final_law.get("status_basis"))
    review_chrono = normalize_text(review_chronology(review_law))
    if final_chrono and review_chrono and final_chrono != review_chrono:
        disagreements.append("chronology disagreement")

    final_impl = normalize_text(final_law.get("current_implementation"))
    review_impl = normalize_text(review_xml(review_law))
    if final_impl and review_impl and final_impl != review_impl:
        disagreements.append("implementation disagreement")

    final_treatment = normalize_text(final_law.get("review_treatment") or final_law.get("approved_code_treatment"))
    review_treatment_text = normalize_text(review_treatment(review_law))
    if final_treatment and review_treatment_text and final_treatment != review_treatment_text:
        disagreements.append("code-treatment disagreement")

    final_rec = normalize_text(final_law.get("review_recommended_action") or final_law.get("recommended_actions"))
    review_rec = normalize_text(review_recommendation(review_law))
    if final_rec and review_rec and final_rec != review_rec:
        disagreements.append("recommended-action disagreement")

    final_evidence = normalize_text(final_law.get("review_source_evidence") or final_law.get("source_evidence"))
    review_evidence_text = normalize_text(review_evidence(review_law))
    if final_evidence and review_evidence_text and final_evidence != review_evidence_text:
        disagreements.append("source-evidence disagreement")

    final_confidence = normalize_text(final_law.get("review_confidence") or final_law.get("confidence"))
    review_confidence_text = normalize_text(review_law.get("confidence"))
    if final_confidence and review_confidence_text and final_confidence != review_confidence_text:
        disagreements.append("confidence disagreement")

    final_targets = {
        normalize_text(v)
        for v in list_text(final_law.get("review_targets") or final_law.get("targets") or final_law.get("exact_target"))
        if v
    }
    review_targets_text = {normalize_text(v) for v in review_targets(review_law)}
    if final_targets and review_targets_text and final_targets != review_targets_text:
        disagreements.append("target disagreement")

    final_exact_change = normalize_text(
        final_law.get("review_exact_change")
        or final_law.get("exact_enacted_text_or_amendment_command")
        or final_law.get("exact_change")
    )
    review_exact_change_text = normalize_text(review_exact_change(review_law))
    if final_exact_change and review_exact_change_text and final_exact_change != review_exact_change_text:
        disagreements.append("exact-change disagreement")

    return sorted(set(disagreements))


def provision_action_type(review_law: Dict[str, Any], review_prov: Dict[str, Any]) -> str:
    treatment_text = normalize_text(
        review_prov.get("treatment")
        or review_prov.get("approved_code_treatment")
        or review_prov.get("code_treatment")
        or review_prov.get("provision_disposition")
        or review_prov.get("provision_level_disposition")
        or review_prov.get("disposition")
        or review_law.get("approved_code_treatment")
    )
    classes = set(review_prov.get("classes") or [])
    if "short-title" in classes:
        return "add statutory note"
    if "effective-date" in classes:
        return "add historical note"
    if "findings-or-sense" in classes:
        return "add statutory note"
    if treatment_text in {"operative_text_required", "amend_existing_text", "new_section", "new_subsection"}:
        if "new-subsection" in classes or "subsection" in normalize_text(review_prov.get("ref")):
            return "insert new subsection"
        return "insert new section"
    if treatment_text in {"repeal_marking"}:
        return "repeal or remove project-added text"
    if treatment_text in {"transfer", "transfer-note"}:
        return "transfer"
    if treatment_text in {"redesignation", "redesignate"}:
        return "redesignate"
    if treatment_text in {"substitution", "substitute"}:
        return "substitution"
    if "new-permanent-general" in classes:
        return "insert new section"
    if treatment_text in {"historical_note_only", "historical_preservation", "history_only", "note_only", "statutory_note", "statutory_note_only", "exclude_from_code", "source_limited_historical_note"}:
        return "add statutory note"
    return "no Code action"


def canonical_xml_file(target: str) -> str:
    m = re.search(r"/t(\d+)", target or "")
    if not m:
        return ""
    return f"usc{int(m.group(1)):02d}.xml"


def source_node_ids_for_law(source_map: Dict[str, Any], law_id: str) -> List[str]:
    node_ids: List[str] = []
    for row in source_map.get("mappings", []) or []:
        if not isinstance(row, dict):
            continue
        src = row.get("source") if isinstance(row.get("source"), dict) else {}
        cons = row.get("consolidated") if isinstance(row.get("consolidated"), dict) else {}
        if law_id in {str(src.get("law_id") or ""), str(cons.get("law_id") or "")}:
            for candidate in [
                src.get("note_id"),
                src.get("placement_identifier"),
                cons.get("note_id"),
                cons.get("placement_identifier"),
            ]:
                if candidate and candidate not in node_ids:
                    node_ids.append(str(candidate))
    return node_ids


def law_defect_issues(review_law: Dict[str, Any], law_validation: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    status = normalize_text(review_status(review_law))
    chrono = review_chronology(review_law)
    treat = review_treatment(review_law)
    rec = review_recommendation(review_law)
    evid = review_evidence(review_law)
    xml = review_xml(review_law)
    conf = canonical_text(review_law.get("confidence"))
    targets = review_targets(review_law)
    provisions = review_provisions(review_law)

    if status == "unresolved":
        issues.append("unresolved conclusion")
    elif status == "unknown":
        issues.append("unresolved conclusion")
    elif status == "source_defect_unresolved":
        issues.append("source-defect-unresolved")
    elif status == "source_unavailable":
        issues.append("source unavailable")
    elif status == "unsupported_source":
        issues.append("unsupported source")
    elif status == "operative_text_required_but_target_unresolved":
        issues.append("operative-text-required-but-target-unresolved")
    elif not status:
        issues.append("missing conclusion")

    if not chrono:
        issues.append("missing chronology conclusion")
    if not treat:
        issues.append("missing approved code treatment")
    if not rec:
        issues.append("missing final recommended action")
    if not evid:
        issues.append("missing source evidence")
    if not xml:
        issues.append("missing current XML comparison")
    if not conf:
        issues.append("missing confidence")

    if not targets:
        for prov in provisions:
            if not isinstance(prov, dict):
                continue
            classes = set(prov.get("classes") or [])
            prov_treatment = normalize_text(
                prov.get("treatment") or prov.get("approved_code_treatment") or prov.get("provision_disposition") or prov.get("disposition")
            )
            if (classes & ACTION_CLASSES) and not canonical_text(prov.get("target")) and prov_treatment not in {normalize_text(t) for t in NOTE_TREATMENTS}:
                issues.append("missing target")
                break

    if law_validation.get("issues"):
        issues.extend(law_validation.get("issues", []))
    return sorted(set(issues))


def provision_defect_issues(review_prov: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    classes = set(review_prov.get("classes") or [])
    treatment_text = normalize_text(
        review_prov.get("treatment") or review_prov.get("approved_code_treatment") or review_prov.get("disposition")
    )
    target_text = provision_target_value(review_prov)
    evidence_text = canonical_text(review_prov.get("evidence") or review_prov.get("source_evidence"))
    change_text = provision_exact_change_value(review_prov)

    if (classes & ACTION_CLASSES) and not target_text and treatment_text not in {normalize_text(t) for t in NOTE_TREATMENTS}:
        issues.append("missing target")
    if (classes & ACTION_CLASSES or "new-permanent-general" in classes) and not treatment_text:
        issues.append("missing approved code treatment")
    if not evidence_text:
        issues.append("missing source evidence")
    if (classes & ACTION_CLASSES) and treatment_text not in {normalize_text(t) for t in NOTE_TREATMENTS} and not change_text:
        issues.append("missing exact enacted text or amendment command")
    return sorted(set(issues))


def provision_signatures(provisions: Iterable[Dict[str, Any]]) -> Tuple[set[str], set[str], set[str]]:
    targets: set[str] = set()
    treatments: set[str] = set()
    evidence: set[str] = set()
    for prov in provisions:
        if not isinstance(prov, dict):
            continue
        tgt = canonical_text(prov.get("target") or prov.get("exact_target"))
        trt = canonical_text(prov.get("treatment") or prov.get("approved_code_treatment") or prov.get("disposition"))
        evd = canonical_text(prov.get("evidence") or prov.get("source_evidence"))
        if tgt:
            targets.add(normalize_text(tgt))
        if trt:
            treatments.add(normalize_text(trt))
        if evd:
            evidence.add(normalize_text(evd))
    return targets, treatments, evidence


def build_issue_categories(issues: Iterable[str]) -> List[str]:
    mapping = {
        "missing conclusion": "legal-status disagreement",
        "missing chronology conclusion": "chronology disagreement",
        "missing target": "target disagreement",
        "missing source evidence": "source-evidence disagreement",
        "missing approved code treatment": "Code-treatment disagreement",
    }
    out: List[str] = []
    seen = set()
    for issue in issues:
        category = mapping.get(issue)
        if category and category not in seen:
            out.append(category)
            seen.add(category)
    return out


def merge_review_resolution() -> None:
    final_ledger = read_json(FINAL_LEDGER)
    provision_ledger = read_json(PROVISION_LEDGER)
    provision_map = read_json(PROVISION_MAP)
    canonical_validation = read_json(CANONICAL_REVIEW_VALIDATION)
    full_validation = read_json(FULL_REVIEW_VALIDATION)
    validation_reports = validation_by_report()
    latest_reviews = latest_review_laws()
    source_provs_by_law = source_provisions_by_law(provision_map)

    final_by_law = {str(law.get("law_id") or ""): law for law in final_ledger.get("laws", []) or []}
    final_provs_by_law = final_provisions_by_law(provision_ledger)

    unresolved_laws: List[Dict[str, Any]] = []
    unresolved_provisions: List[Dict[str, Any]] = []
    disagreement_counts = collections.Counter()
    controlling_invalid_reports: set[str] = set()
    controlling_laws_with_issues = 0
    controlling_provisions_with_issues = 0

    for law_id, (idx, report_path, review_law, law_validation) in latest_reviews.items():
        final_law = final_by_law.get(law_id)
        report_validation = validation_reports.get(report_path, {})
        validation_issues = set(law_validation.get("issues", []) or [])
        report_status = report_validation.get("status", "valid")
        controlling_issues = sorted(set(validation_issues))
        if report_status != "valid":
            controlling_issues.append(f"report:{report_status}")

        if final_law is not None:
            final_law["review_report"] = report_path
            final_law["review_report_status"] = report_status
            final_law["review_issues"] = sorted(set(controlling_issues))
            final_law["review_status"] = review_status(review_law)
            final_law["review_chronology"] = review_chronology(review_law)
            final_law["review_treatment"] = review_treatment(review_law)
            final_law["review_recommended_action"] = review_recommendation(review_law)
            final_law["review_current_implementation"] = review_law.get("current_implementation") or review_law.get("current_xml_comparison")
            final_law["review_source_evidence"] = review_law.get("source_evidence") or review_law.get("evidence")
            final_law["review_confidence"] = review_law.get("confidence")
            final_law["review_targets"] = review_targets(review_law)
            final_law["exact_target"] = review_exact_target(review_law)
            final_law["review_exact_change"] = review_exact_change(review_law)
            final_law["exact_enacted_text_or_amendment_command"] = final_law["review_exact_change"]
            final_law["exact_enacted_change"] = final_law["review_exact_change"]
            final_law["exact_change"] = final_law["review_exact_change"]
            final_law["review_exact_target"] = final_law["exact_target"]
            if controlling_issues:
                controlling_invalid_reports.add(report_path)
                controlling_laws_with_issues += 1

        disagreements = []
        if final_law is not None:
            disagreements = compare_law_fields(final_law, review_law)
            for cat in disagreements:
                disagreement_counts[cat] += 1

        final_provs = final_provs_by_law.get(law_id, [])
        source_provs = source_provs_by_law.get(law_id, [])
        provs = review_provisions(review_law)
        if provs and final_provs:
            by_ref = {str(prov.get("ref") or prov.get("refs") or idx): prov for idx, prov in enumerate(final_provs)}
            for pos, review_prov in enumerate(provs):
                if not isinstance(review_prov, dict):
                    continue
                ref_key = str(review_prov.get("ref") or review_prov.get("refs") or pos)
                final_prov = by_ref.get(ref_key)
                if final_prov is None and pos < len(final_provs):
                    final_prov = final_provs[pos]
                if final_prov is not None:
                    merge_provision_details(final_prov, review_prov)
                    normalize_canonical_provision(final_law or {}, final_prov, None)
                prov_issues = provision_defect_issues(final_prov or review_prov)
                if prov_issues:
                    controlling_provisions_with_issues += 1
                    unresolved_provisions.append(
                        {
                            "law_id": law_id,
                            "public_law": review_law.get("public_law"),
                            "title": review_law.get("title"),
                            "review_report": report_path,
                            "ref": review_prov.get("ref") or review_prov.get("refs"),
                            "issues": prov_issues,
                        }
                    )
                    for issue in prov_issues:
                        disagreement_counts[issue] += 1
        elif provs:
            for review_prov in provs:
                if not isinstance(review_prov, dict):
                    continue
                prov_issues = provision_defect_issues(review_prov)
                if prov_issues:
                    controlling_provisions_with_issues += 1
                    unresolved_provisions.append(
                        {
                            "law_id": law_id,
                            "public_law": review_law.get("public_law"),
                            "title": review_law.get("title"),
                            "review_report": report_path,
                            "ref": review_prov.get("ref") or review_prov.get("refs"),
                            "issues": prov_issues,
                        }
                    )
                    for issue in prov_issues:
                        disagreement_counts[issue] += 1
        elif final_provs:
            by_ref = {str(prov.get("ref") or idx): prov for idx, prov in enumerate(final_provs)}
            for pos, source_prov in enumerate(source_provs):
                if not isinstance(source_prov, dict):
                    continue
                ref_key = str(source_prov.get("ref") or pos)
                final_prov = by_ref.get(ref_key)
                if final_prov is None and pos < len(final_provs):
                    final_prov = final_provs[pos]
                if final_prov is not None:
                    # Use the original source provision as the fallback provenance when the
                    # controlling review does not carry provision rows.
                    final_prov["review_treatment"] = source_prov.get("treatment")
                    final_prov["review_target"] = source_prov.get("target")
                    final_prov["review_exact_target"] = source_prov.get("target")
                    final_prov["review_exact_change"] = source_prov.get("exact_change")
                    final_prov["review_evidence"] = source_prov.get("evidence")
                    final_prov["review_notes"] = source_prov.get("notes")
                    final_prov["review_current_implementation"] = final_law.get("review_current_implementation") if final_law else None
                    final_prov["review_recommended_action"] = final_law.get("review_recommended_action") if final_law else None
                    normalize_canonical_provision(final_law or {}, final_prov, source_prov)
                prov_issues = provision_defect_issues(final_prov) if final_prov is not None else []
                if prov_issues and final_prov is not None:
                    controlling_provisions_with_issues += 1
                    unresolved_provisions.append(
                        {
                            "law_id": law_id,
                            "public_law": review_law.get("public_law"),
                            "title": review_law.get("title"),
                            "review_report": report_path,
                            "ref": final_prov.get("ref"),
                            "issues": prov_issues,
                        }
                    )
                    for issue in prov_issues:
                        disagreement_counts[issue] += 1

        unresolved_issues = law_defect_issues(review_law, law_validation)
        blocking_issues = sorted(set(unresolved_issues) | set(validation_issues))
        if report_status != "valid":
            blocking_issues = sorted(set(blocking_issues) | {f"report:{report_status}"})
        if blocking_issues:
            unresolved_laws.append(
                {
                    "law_id": law_id,
                    "public_law": review_law.get("public_law"),
                    "title": review_law.get("title"),
                    "review_report": report_path,
                    "issues": blocking_issues,
                    "categories": build_issue_categories(blocking_issues),
                }
            )
            if final_law is not None and blocking_issues:
                controlling_invalid_reports.add(report_path)
            for issue in blocking_issues:
                disagreement_counts[issue] += 1

    final_ledger.setdefault("summary", {})
    final_ledger["summary"]["reviewed_laws"] = len(latest_reviews)
    historical_invalid_reports = sum(1 for item in full_validation.get("reports", []) if item.get("status") != "valid")
    final_ledger["summary"]["review_invalid_reports"] = historical_invalid_reports
    final_ledger["summary"]["historical_invalid_reports"] = historical_invalid_reports
    final_ledger["summary"]["controlling_invalid_reports"] = len(controlling_invalid_reports)
    final_ledger["summary"]["controlling_laws_with_issues"] = controlling_laws_with_issues
    final_ledger["summary"]["controlling_provisions_with_issues"] = controlling_provisions_with_issues
    final_ledger["summary"]["high_risk_reviewed"] = final_ledger["summary"].get("high_risk", 0)
    final_ledger["summary"]["audit_complete_laws"] = len(latest_reviews)
    final_ledger["summary"]["review_disagreements"] = len(unresolved_laws)
    final_ledger["summary"]["review_report_validation"] = str(FULL_REVIEW_VALIDATION.relative_to(ROOT)).replace("\\", "/")
    final_ledger["summary"]["review_disagreement_counts"] = dict(disagreement_counts)

    provision_ledger.setdefault("summary", {})
    provision_ledger["summary"]["review_disagreements"] = len(unresolved_provisions)
    provision_ledger["summary"]["controlling_provisions_with_issues"] = controlling_provisions_with_issues
    provision_ledger["summary"]["source_provision_count"] = provision_map.get("summary", {}).get("source_provision_count", provision_ledger["summary"].get("source_provision_count"))
    provision_ledger["summary"]["consolidated_provision_count"] = provision_map.get("summary", {}).get("consolidated_provision_count", provision_ledger["summary"].get("consolidated_provision_count"))
    provision_ledger["summary"]["mapped_provision_count"] = provision_map.get("summary", {}).get("mapped_provision_count", len(provision_map.get("mappings", []) or []))
    provision_ledger["summary"]["review_disagreement_counts"] = dict(disagreement_counts)

    write_json(FINAL_LEDGER, final_ledger)
    write_json(PROVISION_LEDGER, provision_ledger)
    write_json(
        UNRESOLVED,
        {
            "laws": unresolved_laws,
            "provisions": unresolved_provisions,
            "summary": {
                "controlling_invalid_reports": len(controlling_invalid_reports),
                "controlling_laws_with_issues": controlling_laws_with_issues,
                "controlling_provisions_with_issues": controlling_provisions_with_issues,
            },
            "report_validation": full_validation,
        },
    )


def main() -> None:
    merge_review_resolution()


if __name__ == "__main__":
    main()
