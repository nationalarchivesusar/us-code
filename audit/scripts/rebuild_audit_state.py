#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import os
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
PRIMARY_DIR = ROOT / "audit" / "primary"
REPORT_RE = re.compile(r"^batch-\d{2}-\d{2}\.json$")
ACTION_CLASSES = {"direct-amendment", "repeal", "transfer", "redesignation", "substitution"}
NULL_TARGET_TREATMENTS = {
    "amend-existing-text",
    "repeal-marking",
    "new-section",
    "new-subsection",
    "transfer-note",
    "amendment-note",
}


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def norm_report_path(name: str) -> str:
    return f"audit/primary/{name}"


def batch_from_name(name: str) -> int:
    m = re.match(r"^batch-(\d{2})-\d{2}\.json$", name)
    if not m:
        raise ValueError(f"Cannot derive batch from {name}")
    return int(m.group(1))


def law_status_for_validation(law: Dict[str, Any], risk: Dict[str, Any]) -> str:
    status = (law.get("status") or "").lower()
    confidence = (law.get("confidence") or "").lower()
    basis = f"{law.get('status_basis') or ''} {' '.join(law.get('recommended_actions') or [])}".lower()

    if risk["unsupported_source"]:
        return "unsupported"
    if risk["missing_source"]:
        return "missing source evidence"
    if risk["missing_target_actions"]:
        return "incomplete"
    if risk["chronology_required"]:
        return "missing chronology analysis"
    if risk["duplicate_law"]:
        return "duplicated"
    if risk["missing_xml_comparison"]:
        return "missing XML comparison"

    if status in {"fully-repealed", "repealed", "superseded", "expired", "temporary-operative", "partially-repealed"}:
        return "contradicted by source"
    if confidence in {"low", "medium"} or "if later" in basis or "if intended" in basis or "conditional" in basis:
        return "accepted with corrections"
    if risk["has_action"] or risk["has_npg"]:
        return "accepted with corrections"
    return "accepted"


def law_risk_flags(
    law: Dict[str, Any],
    chronology_targets: Dict[str, List[Tuple[str, str]]],
    law_id_counts: collections.Counter,
) -> Dict[str, Any]:
    status = (law.get("status") or "").lower()
    confidence = (law.get("confidence") or "").lower()
    basis = f"{law.get('status_basis') or ''} {' '.join(law.get('recommended_actions') or [])}".lower()
    provisions = law.get("provisions") or []

    has_action = False
    has_npg = False
    missing_target_actions = False
    conditional = False
    unsupported_source = False
    missing_source = False
    chronology_required = False
    duplicate_law = law_id_counts[law["law_id"]] > 1
    missing_xml_comparison = False

    for prov in provisions:
        classes = set(prov.get("classes") or [])
        treatment = (prov.get("treatment") or "").lower()
        notes = f"{prov.get('notes') or ''} {prov.get('evidence') or ''} {prov.get('exact_change') or ''}".lower()
        target = prov.get("target")

        if classes & ACTION_CLASSES:
            has_action = True
            if not target and treatment in NULL_TARGET_TREATMENTS:
                missing_target_actions = True
        if "new-permanent-general" in classes:
            has_npg = True
        if any(term in notes or term in basis for term in ("if later", "if intended", "conditional")):
            conditional = True
        if any(term in notes or term in basis for term in ("download-error", "can't download", "cannot download", "ocr", "unrecoverable")):
            unsupported_source = True
        if any(term in notes or term in basis for term in ("unresolved", "source unavailable", "no usable source", "lacking usable source", "missing source")):
            missing_source = True
        if not prov.get("target") and (
            "amend-existing-text" in treatment
            or "repeal-marking" in treatment
            or "new-section" in treatment
            or "new-subsection" in treatment
            or "transfer" in treatment
            or "amendment-note" in treatment
        ):
            missing_target_actions = True
        if prov.get("target") and chronology_targets.get(prov["target"]):
            # Multiple laws touching the same target are chronology-sensitive.
            chronology_required = True

    if status in {"unresolved"} or confidence in {"low", "medium"}:
        missing_source = missing_source or status == "unresolved"
    if status in {"expired", "temporary-operative", "superseded", "fully-repealed", "partially-repealed"}:
        chronology_required = True

    return {
        "has_action": has_action,
        "has_npg": has_npg,
        "missing_target_actions": missing_target_actions,
        "conditional": conditional,
        "unsupported_source": unsupported_source,
        "missing_source": missing_source,
        "chronology_required": chronology_required,
        "duplicate_law": duplicate_law,
        "missing_xml_comparison": missing_xml_comparison,
    }


def build_source_reports() -> List[Path]:
    reports = []
    for path in sorted(PRIMARY_DIR.glob("batch-*.json")):
        if REPORT_RE.match(path.name):
            reports.append(path)
    return reports


def derive_coverage(
    reports: Iterable[Path],
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    Dict[str, List[Tuple[str, str]]],
    Dict[str, List[Dict[str, Any]]],
]:
    # Later reports supersede earlier ones for the same law_id. Keep a canonical
    # unique view instead of concatenating every historical primary report.
    law_order: List[str] = []
    law_records: Dict[str, Tuple[Path, Dict[str, Any], Dict[str, Any]]] = {}
    parsed_reports: List[Tuple[Path, Dict[str, Any]]] = []

    for report_path in reports:
        report = read_json(report_path)
        parsed_reports.append((report_path, report))
        for law in report.get("laws") or []:
            law_id = law["law_id"]
            if law_id not in law_records:
                law_order.append(law_id)
            law_records[law_id] = (report_path, report, law)

    chronology_targets: Dict[str, List[Tuple[str, str]]] = collections.defaultdict(list)
    law_provisions: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    all_provisions: List[Dict[str, Any]] = []

    for law_id in law_order:
        report_path, report, law = law_records[law_id]
        rel_report = norm_report_path(report_path.name)
        batch = int(report.get("batch") or batch_from_name(report_path.name))
        provision_entries: List[Dict[str, Any]] = []
        for prov in law.get("provisions") or []:
            classes = list(prov.get("classes") or [])
            target = prov.get("target")
            prov_entry = {
                "law_id": law["law_id"],
                "public_law": law["public_law"],
                "title": law["title"],
                "report_path": rel_report,
                "batch": batch,
                "ref": prov.get("ref"),
                "text_summary": prov.get("text_summary"),
                "classes": classes,
                "treatment": prov.get("treatment"),
                "target": target,
                "exact_change": prov.get("exact_change"),
                "evidence": prov.get("evidence"),
                "notes": prov.get("notes"),
                "risk_flags": [],
            }
            all_provisions.append(prov_entry)
            if set(classes) & ACTION_CLASSES:
                prov_entry["risk_flags"].append("action")
            if "new-permanent-general" in classes:
                prov_entry["risk_flags"].append("new-permanent-general")
            if not target and prov.get("treatment") in NULL_TARGET_TREATMENTS:
                prov_entry["risk_flags"].append("missing-target")
            provision_entries.append(prov_entry)
        law_provisions[law_id] = provision_entries

    for prov in all_provisions:
        target = prov.get("target")
        if target and set(prov.get("classes") or []) & ACTION_CLASSES:
            chronology_targets[target].append((prov["law_id"], prov.get("ref") or ""))

    law_id_counts = collections.Counter({law_id: 1 for law_id in law_order})
    laws: List[Dict[str, Any]] = []
    provisions: List[Dict[str, Any]] = []
    for law_id in law_order:
        report_path, report, law = law_records[law_id]
        rel_report = norm_report_path(report_path.name)
        batch = int(report.get("batch") or batch_from_name(report_path.name))
        risk = law_risk_flags(law, chronology_targets, law_id_counts)
        validation_status = law_status_for_validation(law, risk)
        law_entry = {
            "law_id": law["law_id"],
            "public_law": law["public_law"],
            "title": law["title"],
            "report_path": rel_report,
            "batch": batch,
            "validation_status": validation_status,
            "source_status": law.get("status"),
            "current_implementation": law.get("current_implementation", {}).get("assessment"),
            "confidence": law.get("confidence"),
            "status_basis": law.get("status_basis"),
            "risk_flags": [k for k, v in risk.items() if v],
        }
        laws.append(law_entry)
        provisions.extend(law_provisions[law_id])

    return laws, all_provisions, parsed_reports, chronology_targets, law_provisions


def build_high_risk_queue(
    laws: List[Dict[str, Any]],
    chronology_targets: Dict[str, List[Tuple[str, str]]],
    law_provisions: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    queue = []
    for law in laws:
        provs = law_provisions.get(law["law_id"], [])
        reasons = []
        refs = []
        targets = set()
        for prov in provs:
            classes = set(prov.get("classes") or [])
            if classes & ACTION_CLASSES:
                reasons.append("direct-action-provision")
                refs.append(prov.get("ref"))
            if "new-permanent-general" in classes:
                reasons.append("standalone-permanent-provision")
                refs.append(prov.get("ref"))
            if not prov.get("target") and classes & ACTION_CLASSES:
                reasons.append("missing-target")
                refs.append(prov.get("ref"))
            if prov.get("target"):
                targets.add(prov["target"])
                if len({lid for lid, _ in chronology_targets.get(prov["target"], [])}) > 1:
                    reasons.append("multiple-laws-same-target")
        status = (law.get("source_status") or law.get("status") or "").lower()
        confidence = (law.get("confidence") or "").lower()
        basis = f"{law.get('status_basis') or ''} {' '.join(law.get('recommended_actions') or [])}".lower()
        if status in {"unresolved", "expired", "temporary-operative", "superseded", "fully-repealed", "partially-repealed"}:
            reasons.append(f"status:{status}")
        if confidence in {"low", "medium"}:
            reasons.append(f"confidence:{confidence}")
        if any(term in basis for term in ("if later", "if intended", "conditional")):
            reasons.append("conditional-recommendation")
        if "download-error" in basis or "ocr" in basis:
            reasons.append("unsupported-source")
        if reasons:
            queue.append(
                {
                    "law_id": law["law_id"],
                    "public_law": law["public_law"],
                    "title": law["title"],
                    "report_path": law["report_path"],
                    "batch": law["batch"],
                    "source_status": law.get("source_status"),
                    "validation_status": law.get("validation_status"),
                    "confidence": law.get("confidence"),
                    "reasons": sorted(set(reasons)),
                    "provision_refs": sorted({r for r in refs if r}),
                    "targets": sorted(targets),
                }
            )
    queue.sort(key=lambda x: x["law_id"])
    return {
        "total_laws": len(laws),
        "high_risk_laws": len(queue),
        "queue": queue,
    }


def build_exception_report(provisions: List[Dict[str, Any]], laws: List[Dict[str, Any]], chronology_targets: Dict[str, List[Tuple[str, str]]]) -> Dict[str, Any]:
    action_prov_missing_target = []
    npg_notes = []
    exclude_current = []
    conditional = []
    low_medium = []
    unresolved = []
    lacking_source = []

    by_law = {law["law_id"]: law for law in laws}
    for prov in provisions:
        classes = set(prov.get("classes") or [])
        blob = " ".join(
            str(prov.get(k) or "") for k in ("treatment", "text_summary", "notes", "evidence", "exact_change")
        ).lower()
        risky_missing_target = (
            not prov.get("target")
            and (
                classes & ACTION_CLASSES
                or any(term in blob for term in ("amend", "repeal", "transfer", "redesign", "supersed"))
            )
        )
        if risky_missing_target:
            action_prov_missing_target.append(prov)
        if "new-permanent-general" in classes and prov.get("treatment") == "statutory-note":
            npg_notes.append(prov)
        if by_law[prov["law_id"]]["source_status"] == "current" and prov.get("treatment") in ("historical-note-only", "exclude-from-code"):
            exclude_current.append(prov)
    for law in laws:
        basis = f"{law.get('status_basis') or ''} {' '.join(law.get('recommended_actions') or [])}".lower()
        if any(term in basis for term in ("if later", "if intended", "conditional")):
            conditional.append(law)
        if (law.get("confidence") or "").lower() in {"low", "medium"}:
            low_medium.append(law)
        if (law.get("source_status") or "").lower() == "unresolved":
            unresolved.append(law)
        if (law.get("confidence") or "").lower() in {"low", "medium"} or "download-error" in basis or "ocr" in basis:
            lacking_source.append(law)

    def slim_prov(entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "law_id": entry["law_id"],
            "public_law": entry["public_law"],
            "title": entry["title"],
            "report_path": entry["report_path"],
            "batch": entry["batch"],
            "ref": entry["ref"],
            "text_summary": entry["text_summary"],
            "classes": entry["classes"],
            "treatment": entry["treatment"],
            "target": entry["target"],
            "exact_change": entry["exact_change"],
            "notes": entry["notes"],
        }

    def slim_law(entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "law_id": entry["law_id"],
            "public_law": entry["public_law"],
            "title": entry["title"],
            "report_path": entry["report_path"],
            "batch": entry["batch"],
            "validation_status": entry["validation_status"],
            "source_status": entry["source_status"],
            "confidence": entry["confidence"],
        }

    return {
        "risky_provisions_lacking_target": [slim_prov(p) for p in action_prov_missing_target],
        "new_permanent_general_statutory_notes": [slim_prov(p) for p in npg_notes],
        "current_permanent_provisions_recommended_for_exclusion": [slim_prov(p) for p in exclude_current],
        "conditional_recommendations": [slim_law(l) for l in conditional],
        "low_or_medium_confidence_laws": [slim_law(l) for l in low_medium],
        "unresolved_laws": [slim_law(l) for l in unresolved],
        "laws_lacking_exact_source_evidence": [slim_law(l) for l in lacking_source],
        "counts": {
            "risky_provisions_lacking_target": len(action_prov_missing_target),
            "new_permanent_general_statutory_notes": len(npg_notes),
            "current_permanent_provisions_recommended_for_exclusion": len(exclude_current),
            "conditional_recommendations": len(conditional),
            "low_or_medium_confidence_laws": len(low_medium),
            "unresolved_laws": len(unresolved),
            "laws_lacking_exact_source_evidence": len(lacking_source),
        },
    }


def build_chronology_report() -> Dict[str, Any]:
    seed = read_json(ROOT / "audit" / "chronology-seed.json")
    files = sorted(PRIMARY_DIR.glob("batch-??-??.json"))
    target_map: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for report_path in files:
        report = read_json(report_path)
        rel_report = norm_report_path(report_path.name)
        for law in report.get("laws") or []:
            for prov in law.get("provisions") or []:
                target = prov.get("target")
                classes = set(prov.get("classes") or [])
                if target and classes & ACTION_CLASSES:
                    target_map[target].append(
                        {
                            "law_id": law["law_id"],
                            "public_law": law["public_law"],
                            "title": law["title"],
                            "report_path": rel_report,
                            "ref": prov.get("ref"),
                            "treatment": prov.get("treatment"),
                            "classes": sorted(classes),
                        }
                    )

    overlaps = []
    for target, entries in sorted(target_map.items()):
        laws = sorted({e["law_id"] for e in entries})
        if len(laws) > 1:
            overlaps.append({"target": target, "law_ids": laws, "entries": entries})

    return {
        "source_seed": "audit/chronology-seed.json",
        "cross_reference_edges": seed.get("edge_count", 0),
        "self_sunset_laws": seed.get("laws_with_selfsunset", []),
        "strong_edge_count": len([e for e in seed.get("edges", []) if any(v in e.get("verbs", []) for v in ("repeal", "supersede", "revive"))]),
        "target_overlap_count": len(overlaps),
        "target_overlaps": overlaps,
    }


def build_ledger_files() -> None:
    reports = build_source_reports()
    laws, provisions, parsed_reports, chronology_targets, law_provisions = derive_coverage(reports)
    risk_laws = {law["law_id"] for law in laws if law["risk_flags"]}
    progress_laws = []
    for law in laws:
        status = "high-risk review required" if law["law_id"] in risk_laws else "primary audit complete"
        progress_laws.append(
            {
                "law_id": law["law_id"],
                "public_law": law["public_law"],
                "title": law["title"],
                "status": status,
                "batch": law["batch"],
                "source_report": law["report_path"],
                "validation_status": law["validation_status"],
            }
        )

    claude = {
        "summary": {
            "reports": [norm_report_path(p.name) for p in reports],
            "validated_laws": len(laws),
            "current": sum(1 for law in laws if (law.get("source_status") or "").lower() == "current"),
            "unresolved": sum(1 for law in laws if (law.get("source_status") or "").lower() == "unresolved"),
        },
        "laws": laws,
    }
    progress = {
        "total_laws": len(laws),
        "completed_laws": sum(1 for law in progress_laws if law["status"] == "primary audit complete"),
        "laws": progress_laws,
    }

    final_ledger = {
        "summary": {
            "total_laws": len(laws),
            "primary_complete": sum(1 for law in progress_laws if law["status"] == "primary audit complete"),
            "high_risk": sum(1 for law in progress_laws if law["status"] == "high-risk review required"),
        },
        "laws": laws,
    }
    provision_ledger = {
        "summary": {
            "total_provisions": len(provisions),
            "action_provisions_missing_target": sum(
                1 for p in provisions if set(p.get("classes") or []) & ACTION_CLASSES and not p.get("target")
            ),
        },
        "provisions": provisions,
    }

    chronology_report = build_chronology_report()
    high_risk_queue = build_high_risk_queue(laws, chronology_targets, law_provisions)
    exception_report = build_exception_report(provisions, laws, chronology_targets)

    unresolved = {
        "laws": [law for law in laws if law["validation_status"] in {"missing source evidence", "unsupported", "incomplete", "missing chronology analysis"}],
        "provisions": [p for p in provisions if set(p.get("classes") or []) & ACTION_CLASSES and not p.get("target")],
    }

    write_json(ROOT / "audit" / "claude-validation.json", claude)
    write_json(ROOT / "audit" / "codex-progress.json", progress)
    write_json(ROOT / "audit" / "final-ledger.json", final_ledger)
    write_json(ROOT / "audit" / "provision-ledger.json", provision_ledger)
    write_json(ROOT / "audit" / "chronology-report.json", chronology_report)
    write_json(ROOT / "audit" / "high-risk-queue.json", high_risk_queue)
    write_json(ROOT / "audit" / "exception-report.json", exception_report)
    write_json(ROOT / "audit" / "unresolved.json", unresolved)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    build_ledger_files()


if __name__ == "__main__":
    main()
