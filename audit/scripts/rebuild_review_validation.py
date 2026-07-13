#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = ROOT / "audit" / "review"
MANIFEST_DIR = ROOT / "audit" / "manifests"
REPORT_VALIDATION = ROOT / "audit" / "review-report-validation.json"
REVIEW_VALIDATION = ROOT / "audit" / "review-validation.json"
MANIFEST_RE = re.compile(r"^manifest-(\d{2})\.json$")
REVIEW_RE = re.compile(r"^review-(\d{2})\.json$")
MANIFEST_REPAIR_RE = re.compile(r"^review-repair-(\d{2})(?:-(\d{2}))?\.json$")
REVIEW_REPAIR_RE = re.compile(r"^review-repair-(\d{2})(?:-(\d{2}))?\.json$")

LAW_STATUS_KEYS = ("final_legal_status", "final_status", "status", "decision")
CHRONOLOGY_KEYS = ("chronology", "chronology_conclusion", "chronology_analysis", "status_basis")
TREATMENT_KEYS = (
    "required_code_treatment",
    "approved_code_treatment",
    "provision_level_disposition",
    "provision_disposition",
    "decision",
)
TARGET_KEYS = ("exact_target", "target", "manifest_target", "targets")
TEXTUAL_INTEGRATION_KEYS = (
    "final_statutory_text",
    "exact_change",
    "final_amendment_command",
    "exact_enacted_text",
)
EVIDENCE_KEYS = ("source_evidence", "evidence", "status_basis", "rationale")
XML_KEYS = ("current_implementation", "current_xml_comparison")
RECOMMENDATION_KEYS = ("final_recommended_action", "recommended_action", "recommended_actions")
CONFIDENCE_KEYS = ("confidence",)
ACTION_CLASSES = {"direct-amendment", "repeal", "transfer", "redesignation", "substitution"}
NOTE_TREATMENTS = {
    "historical-note-only",
    "historical preservation",
    "historical-preservation",
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


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def scan_reports(directory: Path) -> Dict[int, Path]:
    out: Dict[int, Path] = {}
    if not directory.exists():
        return out
    for path in directory.glob("*.json"):
        name = path.name
        m = REVIEW_RE.match(name)
        if m:
            out.setdefault(int(m.group(1)), path)
            continue
        m = REVIEW_REPAIR_RE.match(name)
        if m:
            base = int(m.group(1))
            sub = int(m.group(2)) if m.group(2) else 0
            out.setdefault(1000 + base * 10 + sub, path)
    return out


def scan_manifests(*directories: Path) -> Dict[int, Path]:
    out: Dict[int, Path] = {}
    for directory in directories:
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            name = path.name
            m = MANIFEST_RE.match(name)
            if m:
                out.setdefault(int(m.group(1)), path)
                continue
            if directory == MANIFEST_DIR:
                m = MANIFEST_REPAIR_RE.match(name)
                if m:
                    base = int(m.group(1))
                    sub = int(m.group(2)) if m.group(2) else 0
                    out.setdefault(1000 + base * 10 + sub, path)
    return out


def canonical_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        return " | ".join(canonical_text(v) for v in value if canonical_text(v))
    return json.dumps(value, ensure_ascii=False).strip()


def first_nonempty_value(data: Dict[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        if key not in data:
            continue
        value = data.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def first_nonempty_text(data: Dict[str, Any], keys: Sequence[str]) -> str:
    return canonical_text(first_nonempty_value(data, keys))


def normalize_status(value: Any) -> str:
    text = canonical_text(value).lower().replace("-", "_").replace(" ", "_")
    return text


def legal_status(law: Dict[str, Any]) -> str:
    return first_nonempty_text(law, LAW_STATUS_KEYS)


def chronology(law: Dict[str, Any]) -> str:
    return first_nonempty_text(law, CHRONOLOGY_KEYS)


def treatment(law: Dict[str, Any]) -> str:
    return first_nonempty_text(law, TREATMENT_KEYS)


def recommendation(law: Dict[str, Any]) -> str:
    return first_nonempty_text(law, RECOMMENDATION_KEYS)


def evidence(law: Dict[str, Any]) -> str:
    return first_nonempty_text(law, EVIDENCE_KEYS)


def xml_comparison(law: Dict[str, Any]) -> str:
    current = first_nonempty_value(law, XML_KEYS)
    if current is None:
        return ""
    if isinstance(current, dict):
        return canonical_text(current)
    return canonical_text(current)


def confidence(law: Dict[str, Any]) -> str:
    return first_nonempty_text(law, CONFIDENCE_KEYS)


def target_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set)):
        return " | ".join(target_value(v) for v in value if target_value(v))
    return canonical_text(value)


def provision_target(provision: Dict[str, Any]) -> str:
    return target_value(first_nonempty_value(provision, ("exact_target", "target", "manifest_target", "targets")))


def provision_treatment(provision: Dict[str, Any]) -> str:
    return canonical_text(first_nonempty_value(provision, ("treatment", "approved_code_treatment", "provision_disposition", "disposition", "decision")))


def provision_evidence(provision: Dict[str, Any]) -> str:
    return first_nonempty_text(provision, ("source_evidence", "evidence", "exact_change", "final_statutory_text"))


def provision_text_change(provision: Dict[str, Any]) -> str:
    return first_nonempty_text(provision, ("exact_change", "final_statutory_text", "exact_enacted_text", "amendment_command"))


def provision_issues(provision: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    classes = set(provision.get("classes") or [])
    prov_treatment = normalize_status(provision_treatment(provision))
    prov_target = provision_target(provision)
    prov_evidence = provision_evidence(provision)
    prov_change = provision_text_change(provision)

    if (classes & ACTION_CLASSES) and not prov_target and prov_treatment not in {normalize_status(t) for t in NOTE_TREATMENTS}:
        issues.append("missing target")
    if (classes & ACTION_CLASSES or "new-permanent-general" in classes) and not prov_treatment:
        issues.append("missing approved code treatment")
    if not prov_evidence:
        issues.append("missing source evidence")
    if (classes & ACTION_CLASSES) and prov_treatment not in {normalize_status(t) for t in NOTE_TREATMENTS} and not prov_change:
        issues.append("missing exact enacted text or amendment command")
    return sorted(set(issues))


def law_issues(law: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    status = normalize_status(legal_status(law))
    chrono = chronology(law)
    treat = normalize_status(treatment(law))
    target = target_value(first_nonempty_value(law, TARGET_KEYS))
    text_change = first_nonempty_text(law, TEXTUAL_INTEGRATION_KEYS)
    evidence_text = evidence(law)
    xml_text = xml_comparison(law)
    rec_text = recommendation(law)
    conf_text = confidence(law)
    provisions = law.get("provisions") or []

    if not status or status in {"unknown", "n_a", "na"}:
        issues.append("missing conclusion")
    if not chrono:
        issues.append("missing chronology conclusion")
    if not treat:
        issues.append("missing approved code treatment")
    if not rec_text:
        issues.append("missing final recommended action")
    if not evidence_text:
        issues.append("missing source evidence")
    if not xml_text:
        issues.append("missing current XML comparison")
    if not conf_text:
        issues.append("missing confidence")

    # Law-level target coverage is only required when the law declares an executable target
    # or includes action-like provisions without a documented note-only disposition.
    if target:
        pass
    elif provisions:
        for prov in provisions:
            if not isinstance(prov, dict):
                issues.append("schema-invalid")
                continue
            pissues = provision_issues(prov)
            if "missing target" in pissues:
                issues.append("missing target")
                break

    for prov in provisions:
        if not isinstance(prov, dict):
            issues.append("schema-invalid")
            continue
        issues.extend(provision_issues(prov))

    return sorted(set(issues))


def compare_law_sets(report: Dict[str, Any], manifest: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    report_ids = [str(law.get("law_id") or "") for law in report.get("laws", [])]
    manifest_ids = [str(law.get("law_id") or "") for law in manifest.get("laws", [])]
    missing = [law_id for law_id in manifest_ids if law_id and law_id not in report_ids]
    extra = [law_id for law_id in report_ids if law_id and law_id not in manifest_ids]
    dupes = [law_id for law_id, count in collections.Counter(report_ids).items() if law_id and count > 1]
    issues: List[str] = []
    if missing or extra or dupes:
        issues.append("missing laws")
    return issues, missing


def report_status(issues: List[str]) -> str:
    issue_set = set(issues)
    if "schema-invalid" in issue_set:
        return "schema-invalid"
    if "missing laws" in issue_set:
        return "missing laws"
    if "missing conclusion" in issue_set:
        return "missing conclusion"
    if "missing evidence" in issue_set:
        return "missing evidence"
    if "missing target" in issue_set:
        return "missing target"
    if issue_set:
        return "incomplete"
    return "valid"


def report_validation() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    reports = scan_reports(REVIEW_DIR)
    manifests = scan_manifests(REVIEW_DIR, MANIFEST_DIR)

    all_entries: List[Dict[str, Any]] = []
    canon_entries: List[Dict[str, Any]] = []
    all_summary = collections.Counter()
    canon_summary = collections.Counter()
    all_unknown_laws: List[Dict[str, Any]] = []
    canon_unknown_laws: List[Dict[str, Any]] = []
    all_laws_lacking_source: List[Dict[str, Any]] = []
    canon_laws_lacking_source: List[Dict[str, Any]] = []
    all_reports_with_unknowns: List[str] = []
    canon_reports_with_unknowns: List[str] = []
    all_reports_lacking_source: List[str] = []
    canon_reports_lacking_source: List[str] = []
    latest_all: Dict[str, Tuple[int, Dict[str, Any], str]] = {}
    latest_canon: Dict[str, Tuple[int, Dict[str, Any], str]] = {}
    canon_law_ids: set[str] = set()

    for idx in sorted(set(reports) | set(manifests)):
        report_path = reports.get(idx)
        manifest_path = manifests.get(idx)
        report: Dict[str, Any] = {}
        manifest: Dict[str, Any] | None = None

        if report_path and report_path.exists():
            try:
                report = read_json(report_path)
            except Exception:
                report = {}
        if manifest_path and manifest_path.exists():
            try:
                manifest = read_json(manifest_path)
            except Exception:
                manifest = None

        report_ref = f"audit/review/review-{idx:02d}.json"
        manifest_ref = f"audit/review/manifest-{idx:02d}.json"
        if report and report.get("source_manifest"):
            manifest_ref = canonical_text(report.get("source_manifest"))

        if not report_path or not report_path.exists() or manifest is None:
            entry = {
                "review_report": report_ref,
                "manifest": manifest_ref,
                "status": "schema-invalid",
                "issues": ["missing manifest file" if manifest is None else "missing report file"],
                "law_count": report.get("law_count"),
                "manifest_law_count": None if manifest is None else manifest.get("law_count"),
                "laws": [],
            }
            all_entries.append(entry)
            all_summary["schema-invalid"] += 1
            if idx <= 26:
                canon_entries.append(entry)
                canon_summary["schema-invalid"] += 1
            continue

        if report_path.read_bytes() == manifest_path.read_bytes() and report:
            entry = {
                "review_report": report_ref,
                "manifest": manifest_ref,
                "status": "manifest-copy",
                "issues": ["byte-identical to manifest"],
                "law_count": report.get("law_count"),
                "manifest_law_count": manifest.get("law_count") if manifest else None,
                "laws": [],
            }
            all_entries.append(entry)
            all_summary["manifest-copy"] += 1
            if idx <= 26:
                canon_entries.append(entry)
                canon_summary["manifest-copy"] += 1
            continue

        report_laws = report.get("laws")
        manifest_laws = manifest.get("laws") if manifest else []
        issues: List[str] = []
        law_issue_rows: List[Dict[str, Any]] = []

        if not isinstance(report_laws, list):
            issues.append("schema-invalid")
            report_laws = []
        if report.get("law_count") != len(report_laws):
            issues.append("schema-invalid")
        law_set_issues, missing_ids = compare_law_sets(report, manifest)
        issues.extend(law_set_issues)

        report_report_ref = f"audit/review/{report_path.name}"
        if idx <= 26:
            for law in report_laws:
                lid = str(law.get("law_id") or "")
                if lid:
                    canon_law_ids.add(lid)

        for law in report_laws:
            if not isinstance(law, dict):
                issues.append("schema-invalid")
                continue
            detail_issues = law_issues(law)
            law_issue_rows.append(
                {
                    "law_id": law.get("law_id"),
                    "public_law": law.get("public_law"),
                    "title": law.get("title"),
                    "status": legal_status(law),
                    "issues": detail_issues,
                }
            )
            if "missing conclusion" in detail_issues:
                all_unknown_laws.append(
                    {
                        "report": report_report_ref,
                        "law_id": law.get("law_id"),
                        "public_law": law.get("public_law"),
                        "title": law.get("title"),
                        "issue": "missing conclusion",
                    }
                )
                issues.append("missing conclusion")
                if idx <= 26:
                    canon_unknown_laws.append(
                        {
                            "report": report_report_ref,
                            "law_id": law.get("law_id"),
                            "public_law": law.get("public_law"),
                            "title": law.get("title"),
                            "issue": "missing conclusion",
                        }
                    )
            if "missing source evidence" in detail_issues:
                issues.append("missing evidence")
                all_laws_lacking_source.append(
                    {
                        "report": report_report_ref,
                        "law_id": law.get("law_id"),
                        "public_law": law.get("public_law"),
                        "title": law.get("title"),
                        "issues": ["missing source evidence"],
                    }
                )
                if idx <= 26:
                    canon_laws_lacking_source.append(
                        {
                            "report": report_report_ref,
                            "law_id": law.get("law_id"),
                            "public_law": law.get("public_law"),
                            "title": law.get("title"),
                            "issues": ["missing source evidence"],
                        }
                    )
            if "missing target" in detail_issues:
                issues.append("missing target")

            if detail_issues:
                if idx <= 26:
                    canon_reports_with_unknowns.append(report_report_ref) if "missing conclusion" in detail_issues else None
                all_reports_with_unknowns.append(report_report_ref) if "missing conclusion" in detail_issues else None
            if not evidence(law) or not chronology(law):
                all_reports_lacking_source.append(report_report_ref)
                if idx <= 26:
                    canon_reports_lacking_source.append(report_report_ref)

            current = latest_all.get(str(law.get("law_id") or ""))
            if str(law.get("law_id") or "") and (current is None or idx >= current[0]):
                latest_all[str(law.get("law_id") or "")] = (idx, law, report_report_ref)
            if idx <= 26 and str(law.get("law_id") or ""):
                current_canon = latest_canon.get(str(law.get("law_id") or ""))
                if current_canon is None or idx >= current_canon[0]:
                    latest_canon[str(law.get("law_id") or "")] = (idx, law, report_report_ref)

        status = report_status(issues)
        entry = {
            "review_report": report_ref,
            "manifest": manifest_ref,
            "status": status,
            "issues": sorted(set(issues)),
            "law_count": report.get("law_count"),
            "manifest_law_count": manifest.get("law_count") if manifest else None,
            "missing_law_ids": missing_ids,
            "laws": law_issue_rows,
        }
        all_entries.append(entry)
        all_summary[status] += 1
        if idx <= 26:
            canon_entries.append(entry)
            canon_summary[status] += 1

    all_latest_laws: List[Dict[str, Any]] = []
    for law_id, (idx, law, report_ref) in latest_all.items():
        issues = law_issues(law)
        all_latest_laws.append(
            {
                "law_id": law.get("law_id"),
                "public_law": law.get("public_law"),
                "title": law.get("title"),
                "status": legal_status(law),
                "issues": issues,
                "source_report": report_ref,
            }
        )

    canon_latest_laws: List[Dict[str, Any]] = []
    for law_id, (idx, law, report_ref) in latest_canon.items():
        issues = law_issues(law)
        canon_latest_laws.append(
            {
                "law_id": law.get("law_id"),
                "public_law": law.get("public_law"),
                "title": law.get("title"),
                "status": legal_status(law),
                "issues": issues,
                "source_report": report_ref,
            }
        )

    full_data = {
        "summary": {
            "review_report_count": len(all_entries),
            "status_counts": dict(all_summary),
            "reviewed_law_count": len(latest_all),
            "unknown_law_count": len(all_unknown_laws),
            "reports_with_unknowns": sorted(set(all_reports_with_unknowns)),
            "reports_lacking_source_grounded_conclusions": sorted(set(all_reports_lacking_source)),
        },
        "reports": all_entries,
        "unknown_laws": all_unknown_laws,
        "latest_laws": all_latest_laws,
    }

    canonical_data = {
        "summary": {
            "review_report_count": len(canon_entries),
            "status_counts": dict(canon_summary),
            "reviewed_law_count": len(canon_law_ids),
            "unknown_law_count": len(canon_unknown_laws),
            "reports_with_unknowns": sorted(set(canon_reports_with_unknowns)),
            "reports_lacking_source_grounded_conclusions": sorted(set(canon_reports_lacking_source)),
        },
        "reports": canon_entries,
        "unknown_laws": canon_unknown_laws,
        "latest_laws": canon_latest_laws,
    }
    return full_data, canonical_data


def main() -> None:
    full_data, canonical_data = report_validation()
    write_json(REPORT_VALIDATION, full_data)
    write_json(REVIEW_VALIDATION, canonical_data)


if __name__ == "__main__":
    main()
