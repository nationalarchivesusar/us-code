#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
try:
    from lxml import etree
except ImportError as exc:
    raise SystemExit("lxml is required: py -3 -m pip install lxml") from exc
from common import load_registry, NS_URI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    reg = load_registry(repo)
    drafts = repo / "codification" / "plans" / "draft"
    errors = []
    seen_ids = set()

    for law in reg["laws"]:
        plan = drafts / f"{law['law_id']}.json"
        if law["candidate_classification"].get("method") == "survival_audit_only":
            continue
        if not plan.exists():
            errors.append(f"missing draft plan {plan.name}")
            continue
        data = json.loads(plan.read_text(encoding="utf-8"))
        if data.get("status") != "draft":
            errors.append(f"{plan.name}: status is not draft")
        if not data.get("summary") or not data.get("operations"):
            errors.append(f"{plan.name}: blank summary or operations")
        for op in data.get("operations", []):
            if op.get("op") != "replace_element_xml":
                errors.append(f"{plan.name}: unsupported operation {op.get('op')}")
            frag = drafts / op["fragment_file"]
            if not frag.exists():
                errors.append(f"{plan.name}: missing fragment {frag.name}")
                continue
            try:
                root = etree.fromstring(frag.read_bytes(), etree.XMLParser(huge_tree=True, recover=False))
            except Exception as exc:
                errors.append(f"{frag.name}: invalid XML: {exc}")
                continue
            for el in root.iter():
                eid = el.get("id")
                if eid and eid.startswith("rp-"):
                    if eid in seen_ids:
                        errors.append(f"duplicate generated id {eid}")
                    seen_ids.add(eid)
            text = " ".join(root.itertext())
            if law["title"] not in text:
                errors.append(f"{frag.name}: missing law title marker")

    # CRACK survival audit
    crack = (repo / "codification" / "round3" / "sources" / "text" / "PL-003-025.txt").read_text(encoding="utf-8")
    later = "\n".join(
        (repo / "codification" / "round3" / "sources" / "text" / f"{x}.txt").read_text(encoding="utf-8")
        for x in ["PL-038-263", "PL-038-264"]
    )
    amendment_lines = [
        ln.strip() for ln in crack.splitlines()
        if re.search(r"\b(amend|strike|insert|redesignate|codif|United States Code)\b", ln, re.I)
    ]
    audit = {
        "crack_source_lines_flagged": amendment_lines,
        "later_laws_reference_crack": "crack act" in later.lower(),
        "automatic_survival_conclusion": None,
        "reason": "Provision-by-provision legal review required; no wholesale catch-up plan generated."
    }
    rp = repo / "codification" / "reports" / "PL-003-025-survival-audit.json"
    rp.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    if errors:
        raise SystemExit("Validation failed:\n- " + "\n- ".join(errors))
    print("Round 3 candidate package validation passed.")
    print("No live XML or codification state was modified.")

if __name__ == "__main__":
    main()
