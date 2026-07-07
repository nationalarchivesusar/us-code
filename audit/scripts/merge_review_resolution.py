#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
FINAL_LEDGER = ROOT / "audit" / "final-ledger.json"
PROVISION_LEDGER = ROOT / "audit" / "provision-ledger.json"
REVIEW_VALIDATION = ROOT / "audit" / "review-validation.json"
UNRESOLVED = ROOT / "audit" / "unresolved.json"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def merge_review_resolution() -> None:
    final_ledger = read_json(FINAL_LEDGER)
    provision_ledger = read_json(PROVISION_LEDGER)
    review_validation = read_json(REVIEW_VALIDATION)

    review_by_law: Dict[str, Dict[str, Any]] = {law["law_id"]: law for law in review_validation.get("laws", [])}

    merged_laws = []
    unresolved_laws = []

    for law in final_ledger.get("laws", []):
        merged = dict(law)
        review = review_by_law.get(law["law_id"])
        if review:
            merged["review_report"] = review.get("review_report")
            merged["reviewer"] = review.get("reviewer")
            merged["review_group_index"] = review.get("group_index")
            merged["review_status_key"] = review.get("status_key")
            merged["review_status_value"] = review.get("status_value")
            merged["review_normalized_status"] = review.get("normalized_status")
            merged["review_resolved_status"] = review.get("resolved_status")
            merged["review_required_code_treatment"] = review.get("required_code_treatment")
            merged["review_disagreement_reasons"] = review.get("disagreement_reasons")
            if review.get("resolved_status") == "unresolved":
                unresolved_laws.append(merged)
        merged_laws.append(merged)

    final_ledger["laws"] = merged_laws
    final_ledger.setdefault("summary", {})
    final_ledger["summary"]["reviewed_laws"] = len(review_by_law)
    final_ledger["summary"]["review_unresolved"] = len(unresolved_laws)
    final_ledger["summary"]["review_disagreements"] = len(review_validation.get("disagreements", []))

    provision_ledger.setdefault("summary", {})
    provision_ledger["summary"]["reviewed_laws"] = len(review_by_law)
    provision_ledger["summary"]["review_disagreements"] = len(review_validation.get("disagreements", []))

    write_json(FINAL_LEDGER, final_ledger)
    write_json(PROVISION_LEDGER, provision_ledger)
    write_json(UNRESOLVED, {"laws": [], "provisions": []})


def main() -> None:
    merge_review_resolution()


if __name__ == "__main__":
    main()
