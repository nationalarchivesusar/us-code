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
        idx = report_index(report_path)
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
        ("required_code_treatment", "approved_code_treatment", "provision_level_disposition", "provision_disposition"),
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
        return [canonical_text(v) for v in targets if canonical_text(v)]
    return []


def review_provisions(review_law: Dict[str, Any]) -> List[Dict[str, Any]]:
    provs = review_law.get("provisions")
    return provs if isinstance(provs, list) else []


def final_provisions_by_law(provision_ledger: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for prov in provision_ledger.get("provisions", []) or []:
        if isinstance(prov, dict):
            out[str(prov.get("law_id") or "")].append(prov)
    return out


def merge_provision_details(final_prov: Dict[str, Any], review_prov: Dict[str, Any]) -> None:
    final_prov["review_treatment"] = review_prov.get("treatment") or review_prov.get("approved_code_treatment") or review_prov.get("disposition")
    final_prov["review_target"] = review_prov.get("target") or review_prov.get("exact_target")
    final_prov["review_exact_change"] = review_prov.get("exact_change") or review_prov.get("final_statutory_text")
    final_prov["review_evidence"] = review_prov.get("evidence") or review_prov.get("source_evidence")
    final_prov["review_notes"] = review_prov.get("notes")
    final_prov["review_classes"] = review_prov.get("classes")
    final_prov["review_refs"] = review_prov.get("refs") or review_prov.get("ref")
    final_prov["review_current_implementation"] = review_prov.get("current_implementation")
    final_prov["review_recommended_action"] = review_prov.get("recommended_action") or review_prov.get("recommended_actions")


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

    final_rec = normalize_text(final_law.get("recommended_actions"))
    review_rec = normalize_text(review_recommendation(review_law))
    if final_rec and review_rec and final_rec != review_rec:
        disagreements.append("source-evidence disagreement")

    final_provs = final_provisions_by_law
    return sorted(set(disagreements))


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
    canonical_validation = read_json(CANONICAL_REVIEW_VALIDATION)
    full_validation = read_json(FULL_REVIEW_VALIDATION)
    validation_reports = validation_by_report()
    latest_reviews = latest_review_laws()

    final_by_law = {str(law.get("law_id") or ""): law for law in final_ledger.get("laws", []) or []}
    final_provs_by_law = final_provisions_by_law(provision_ledger)

    unresolved_laws: List[Dict[str, Any]] = []
    unresolved_provisions: List[Dict[str, Any]] = []
    disagreement_counts = collections.Counter()

    for law_id, (idx, report_path, review_law, law_validation) in latest_reviews.items():
        final_law = final_by_law.get(law_id)
        report_validation = validation_reports.get(report_path, {})
        validation_issues = set(law_validation.get("issues", []) or [])
        report_status = report_validation.get("status", "valid")

        if final_law is not None:
            final_law["review_report"] = report_path
            final_law["review_report_status"] = report_status
            final_law["review_issues"] = sorted(validation_issues)
            final_law["review_status"] = review_status(review_law)
            final_law["review_chronology"] = review_chronology(review_law)
            final_law["review_treatment"] = review_treatment(review_law)
            final_law["review_recommended_action"] = review_recommendation(review_law)
            final_law["review_current_implementation"] = review_law.get("current_implementation")
            final_law["review_source_evidence"] = review_law.get("source_evidence") or review_law.get("evidence")
            final_law["review_confidence"] = review_law.get("confidence")
            final_law["review_targets"] = review_targets(review_law)

        disagreements = []
        if final_law is not None:
            disagreements = compare_law_fields(final_law, review_law)
            for cat in disagreements:
                disagreement_counts[cat] += 1

        provs = review_provisions(review_law)
        final_provs = final_provs_by_law.get(law_id, [])
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
                prov_issues = []
                prov_target = canonical_text(review_prov.get("target") or review_prov.get("exact_target"))
                prov_treatment = canonical_text(review_prov.get("treatment") or review_prov.get("approved_code_treatment") or review_prov.get("disposition"))
                prov_evidence = canonical_text(review_prov.get("evidence") or review_prov.get("source_evidence"))
                if (set(review_prov.get("classes") or []) & ACTION_CLASSES) and not prov_target and normalize_text(prov_treatment) not in {normalize_text(t) for t in NOTE_TREATMENTS}:
                    prov_issues.append("missing target")
                if not prov_evidence:
                    prov_issues.append("missing source evidence")
                if prov_issues:
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
                prov_issues = []
                prov_target = canonical_text(review_prov.get("target") or review_prov.get("exact_target"))
                prov_evidence = canonical_text(review_prov.get("evidence") or review_prov.get("source_evidence"))
                if (set(review_prov.get("classes") or []) & ACTION_CLASSES) and not prov_target:
                    prov_issues.append("missing target")
                if not prov_evidence:
                    prov_issues.append("missing source evidence")
                if prov_issues:
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

        unresolved_issues = sorted(set(validation_issues))
        if report_status != "valid" or unresolved_issues:
            unresolved_laws.append(
                {
                    "law_id": law_id,
                    "public_law": review_law.get("public_law"),
                    "title": review_law.get("title"),
                    "review_report": report_path,
                    "issues": unresolved_issues or [f"report:{report_status}"],
                    "categories": build_issue_categories(unresolved_issues),
                }
            )
            for issue in unresolved_issues:
                disagreement_counts[issue] += 1

    final_ledger.setdefault("summary", {})
    final_ledger["summary"]["reviewed_laws"] = canonical_validation.get("summary", {}).get("reviewed_law_count", len(latest_reviews))
    final_ledger["summary"]["review_invalid_reports"] = sum(1 for item in full_validation.get("reports", []) if item.get("status") != "valid")
    final_ledger["summary"]["review_disagreements"] = sum(1 for item in unresolved_laws)
    final_ledger["summary"]["review_report_validation"] = str(FULL_REVIEW_VALIDATION.relative_to(ROOT)).replace("\\", "/")
    final_ledger["summary"]["review_disagreement_counts"] = dict(disagreement_counts)

    provision_ledger.setdefault("summary", {})
    provision_ledger["summary"]["review_disagreements"] = sum(1 for item in unresolved_provisions)
    provision_ledger["summary"]["review_disagreement_counts"] = dict(disagreement_counts)

    write_json(FINAL_LEDGER, final_ledger)
    write_json(PROVISION_LEDGER, provision_ledger)
    write_json(
        UNRESOLVED,
        {
            "laws": unresolved_laws,
            "provisions": unresolved_provisions,
            "report_validation": full_validation,
        },
    )


def main() -> None:
    merge_review_resolution()


if __name__ == "__main__":
    main()
