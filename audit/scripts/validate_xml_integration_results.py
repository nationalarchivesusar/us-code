#!/usr/bin/env python3
"""Validate XML integration results against the approved plan and Git state."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
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
VALID_EXECUTABLE_STATUSES = {
    "applied",
    "already-satisfied-with-baseline-proof",
    "superseded-by-later-action",
    "blocked",
}
VALID_NON_EXECUTABLE_STATUSES = {
    "applied",
    "documented-no-code-action",
    "already-satisfied-with-baseline-proof",
    "superseded-by-later-action",
    "blocked",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8")


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def changed_xml_files() -> set[str]:
    out = git("diff", "--name-only", BASELINE, "--", "usc")
    return {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip().endswith(".xml")}


def has_baseline_node(proof: object) -> bool:
    if not isinstance(proof, dict):
        return False
    required = [
        "baseline_commit",
        "xml_file",
        "xml_node_id",
        "uslm_identifier",
        "existing_statutory_text",
        "source_text_comparison",
    ]
    return all(proof.get(key) for key in required) and proof.get("baseline_commit") == BASELINE


def is_title_root(identifier: str | None) -> bool:
    if not identifier:
        return True
    parts = [part.strip() for part in re.split(r"[|;]", identifier) if part.strip()]
    if not parts:
        return True
    return any(re.fullmatch(r"/us/usc/t\d+[A-Za-z]?", part) for part in parts)


def scan_xml_artifacts() -> list[str]:
    issues: list[str] = []
    project_note_re = re.compile(r'<note\b(?=[^>]*\bid="rp-pl\d{6}-codification")[^>]*>.*?</note>', re.S)
    for path in (ROOT / "usc").glob("*.xml"):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        if "trello.com" in text:
            issues.append(f"{rel}: Trello URL remains")
        if "Authenticated statutory text was unavailable or the supplied attachment yielded only viewer" in text:
            issues.append(f"{rel}: false source-limitation boilerplate remains")
        for note in project_note_re.findall(text):
            if '<quotedContent origin="/us/pl/' in note:
                issues.append(f"{rel}: project full-law quotedContent remains in rp codification note")
                break
    return issues


def main() -> int:
    plan = load_json("audit/xml-integration-plan.json")
    results = load_json("audit/xml-integration-results.json")
    plan_rows = plan.get("provisions", [])
    result_rows = results.get("results", [])
    changed = changed_xml_files()
    issues: list[str] = []

    if len(plan_rows) != 903:
        issues.append(f"plan action count is {len(plan_rows)}, expected 903")
    if len(result_rows) != len(plan_rows):
        issues.append(f"result action count is {len(result_rows)}, expected {len(plan_rows)}")

    plan_by_id = {row.get("action_id"): row for row in plan_rows}
    seen = set()
    executable_count = 0
    blocked = 0
    false_already = 0
    title_root_exec = 0

    for result in result_rows:
        action_id = result.get("action_id")
        seen.add(action_id)
        plan_row = plan_by_id.get(action_id)
        if not plan_row:
            issues.append(f"{action_id}: result has no matching plan row")
            continue
        action_type = plan_row.get("action_type")
        status = result.get("result_status")
        executable = action_type in EXECUTABLE_ACTIONS
        if executable:
            executable_count += 1
            if status not in VALID_EXECUTABLE_STATUSES:
                issues.append(f"{action_id}: executable action has invalid/incomplete status {status!r}")
            if status == "blocked":
                blocked += 1
            if status == "already-satisfied":
                false_already += 1
            if status == "already-satisfied-with-baseline-proof" and not has_baseline_node(result.get("baseline_proof")):
                issues.append(f"{action_id}: already-satisfied-with-baseline-proof lacks required baseline node proof")
            if status == "applied":
                files = {f"usc/{name}" if not str(name).startswith("usc/") else str(name) for name in [result.get("xml_file_after") or result.get("xml_file_before")] if name}
                if not files.intersection(changed):
                    issues.append(f"{action_id}: applied result has no changed XML file after baseline")
            final_id = result.get("final_section_or_subsection_identifier") or plan_row.get("exact_uslm_code_identifier")
            if action_type in {"insert new section", "insert new subsection"} and is_title_root(final_id):
                title_root_exec += 1
                issues.append(f"{action_id}: executable insertion uses only title-root identifier {final_id!r}")
            if status in {"applied", "already-satisfied-with-baseline-proof"} and not result.get("exact_enacted_text_applied"):
                issues.append(f"{action_id}: executable completed result lacks exact statutory text")
        else:
            if status not in VALID_NON_EXECUTABLE_STATUSES:
                issues.append(f"{action_id}: non-executable action has invalid status {status!r}")
            if status == "documented-no-code-action" and not result.get("documented_no_op_explanation"):
                issues.append(f"{action_id}: documented non-executable disposition lacks explanation")

    missing = set(plan_by_id) - seen
    if missing:
        issues.append(f"missing result rows: {len(missing)}")
    if executable_count != 137:
        issues.append(f"executable action count is {executable_count}, expected 137")

    issues.extend(scan_xml_artifacts())

    summary = {
        "plan_actions": len(plan_rows),
        "result_actions": len(result_rows),
        "executable_actions": executable_count,
        "blocked_actions": blocked,
        "false_already_satisfied_claims": false_already,
        "title_root_executable_targets": title_root_exec,
        "changed_xml_files": sorted(changed),
        "issue_count": len(issues),
    }
    print(json.dumps(summary, indent=2))
    if issues:
        print("issues:", file=sys.stderr)
        for issue in issues[:200]:
            print(f"- {issue}", file=sys.stderr)
        if len(issues) > 200:
            print(f"- ... {len(issues) - 200} more", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
