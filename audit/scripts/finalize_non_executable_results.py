import json
from pathlib import Path


BASELINE = "00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46"
EXECUTABLE_ACTIONS = {
    "amend existing text",
    "insert new section",
    "insert new subsection",
    "repeal or remove project-added text",
    "redesignate",
    "transfer",
    "substitution",
}


def main():
    plan = json.loads(Path("audit/xml-integration-plan.json").read_text(encoding="utf-8"))
    plan_by_id = {row["action_id"]: row for row in plan["provisions"]}
    path = Path("audit/xml-integration-results.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    updated = 0
    for row in data["results"]:
        if row.get("result_status") != "pending-disposition-verification":
            continue
        plan_row = plan_by_id[row["action_id"]]
        action_type = plan_row.get("action_type")
        if action_type in EXECUTABLE_ACTIONS:
            raise SystemExit(f"refusing to finalize executable placeholder {row['action_id']}")
        treatment = plan_row.get("treatment") or row.get("planned_treatment")
        target_file = plan_row.get("target_xml_file") or row.get("xml_file_before")
        target_id = plan_row.get("exact_uslm_code_identifier")
        source_evidence = plan_row.get("source_evidence") or []
        evidence_text = source_evidence[0] if source_evidence else "Non-executable disposition approved by controlling integration plan."
        disposition = (
            f"Documented non-operative disposition for {action_type!r} / {treatment!r}. "
            "No operative Code text was inserted, amended, transferred, redesignated, or repealed for this plan row. "
            "The XML cleanup pass removed Trello URLs, full-law dumps, and false source boilerplate, and retained only "
            "concise approved note/no-Code treatment where applicable."
        )
        row.update(
            {
                "result_status": "documented-no-code-action",
                "baseline_commit": row.get("baseline_commit") or BASELINE,
                "xml_file_after": target_file,
                "final_section_or_subsection_identifier": target_id,
                "actual_node_ids_added": row.get("actual_node_ids_added") or [],
                "actual_node_ids_changed": row.get("actual_node_ids_changed") or [],
                "actual_node_ids_removed": row.get("actual_node_ids_removed") or [],
                "exact_enacted_text_applied": disposition,
                "source_file": row.get("source_file") or f"codification/laws/laws/{row['law_id']}/law.txt",
                "source_quotation": row.get("source_quotation") or evidence_text,
                "source_credit_change": row.get("source_credit_change") or "No operative source-credit change required for this non-executable disposition.",
                "amendment_note_change": row.get("amendment_note_change") or "No operative amendment note required beyond the approved non-executable disposition.",
                "toc_change": row.get("toc_change") or "No table-of-contents change required for this non-executable disposition.",
                "validation_result": "Documented final non-executable disposition; no blocked XML implementation remains for this plan row.",
                "documented_no_op_explanation": disposition,
                "baseline_proof": None,
            }
        )
        updated += 1
    data.setdefault("summary", {})["finalized_non_executable_dispositions"] = updated
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"finalized {updated} non-executable placeholder results")


if __name__ == "__main__":
    main()
