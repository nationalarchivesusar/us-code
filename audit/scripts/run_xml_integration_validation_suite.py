#!/usr/bin/env python3
"""Run and record the XML integration validation suite."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "audit" / "xml-integration-validation-report.json"


def run_command(label: str, command: list[str], timeout: int = 300) -> dict:
    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )
    return {
        "label": label,
        "command": command,
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-8000:],
        "stderr_tail": proc.stderr[-8000:],
    }


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def xml_parse_checks() -> dict:
    files = sorted((ROOT / "usc").glob("usc*.xml"))
    failures = []
    for path in files:
        try:
            ET.parse(path)
        except Exception as exc:  # pragma: no cover - records real corpus state
            failures.append({"file": path.relative_to(ROOT).as_posix(), "error": str(exc)})
    return {"xml_files_checked": len(files), "failures": failures, "exit_code": 0 if not failures else 1}


def duplicate_id_scan() -> dict:
    locations: dict[str, list[str]] = defaultdict(list)
    for path in sorted((ROOT / "usc").glob("usc*.xml")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        for match in re.finditer(r'\bid="([^"]+)"', text):
            locations[match.group(1)].append(rel)

    results = load_json("audit/xml-integration-results.json")
    claimed = set()
    for row in results.get("results", []):
        for key in ("actual_node_ids_added", "actual_node_ids_changed"):
            claimed.update(row.get(key) or [])

    global_duplicates = {node: files for node, files in locations.items() if len(files) > 1}
    claimed_duplicates = {node: files for node, files in global_duplicates.items() if node in claimed}
    return {
        "global_duplicate_id_count": len(global_duplicates),
        "global_duplicate_id_sample": dict(list(global_duplicates.items())[:20]),
        "claimed_integration_duplicate_id_count": len(claimed_duplicates),
        "claimed_integration_duplicate_id_sample": dict(list(claimed_duplicates.items())[:20]),
        "legacy_duplicate_note": "The corpus contains legacy cross-title duplicate IDs, primarily generic footnote IDs; completion is blocked only by duplicates among integration-claimed nodes.",
        "exit_code": 0 if not claimed_duplicates else 1,
    }


def source_text_reconciliation() -> dict:
    results = load_json("audit/xml-integration-results.json")
    missing_source_file = []
    missing_source_quote = []
    missing_exact_text = []
    for row in results.get("results", []):
        status = row.get("result_status")
        action = row.get("planned_action")
        if status in {"applied", "already-satisfied-with-baseline-proof"}:
            if not row.get("source_file"):
                missing_source_file.append(row.get("action_id"))
            if not row.get("source_quotation"):
                missing_source_quote.append(row.get("action_id"))
            if action != "no Code action" and not row.get("exact_enacted_text_applied"):
                missing_exact_text.append(row.get("action_id"))
    failures = missing_source_file or missing_source_quote or missing_exact_text
    return {
        "missing_source_file": missing_source_file,
        "missing_source_quotation": missing_source_quote,
        "missing_exact_text": missing_exact_text,
        "exit_code": 0 if not failures else 1,
    }


def note_action_reconciliation() -> dict:
    plan = load_json("audit/xml-integration-plan.json")
    results = load_json("audit/xml-integration-results.json")
    result_by_id = {row["action_id"]: row for row in results.get("results", [])}
    note_actions = {
        "add statutory note",
        "add historical note",
        "add amendment note",
        "effective-date-note",
        "savings-note",
        "transfer-note",
    }
    missing = []
    stale = []
    verified = 0
    xml_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "usc").glob("usc*.xml"))
    for row in plan.get("provisions", []):
        action = row.get("action_type")
        treatment = str(row.get("treatment") or "")
        if action not in note_actions and "note" not in treatment:
            continue
        result = result_by_id.get(row["action_id"], {})
        note_id = result.get("verified_note_node_id") or (row.get("existing_project_node_ids_to_remove_or_replace") or [None])[0]
        if result.get("result_status") not in {"applied", "already-satisfied-with-baseline-proof", "superseded-by-later-action"}:
            missing.append(row["action_id"])
            continue
        if result.get("result_status") == "applied":
            if not note_id or f'id="{note_id}"' not in xml_text:
                missing.append(row["action_id"])
            else:
                verified += 1
    project_note_re = re.compile(r'<note\b(?=[^>]*\bid="rp-pl\d{6}-codification")[^>]*>.*?</note>', re.S)
    for note in project_note_re.findall(xml_text):
        lowered = note.lower()
        if "trello.com" in lowered:
            stale.append("project-note Trello URL")
        if "<quotedcontent" in lowered:
            stale.append("project-note quotedContent dump")
        if "authenticated statutory text was unavailable" in lowered:
            stale.append("project-note false authenticated-source boilerplate")
    return {
        "note_actions_verified": verified,
        "missing_note_action_results": missing,
        "stale_note_patterns": stale,
        "exit_code": 0 if not missing and not stale else 1,
    }


def trello_and_boilerplate_scan() -> dict:
    patterns = {
        "trello_urls": "trello.com",
        "false_source_boilerplate": "Authenticated statutory text was unavailable",
        "viewer_boilerplate": "supplied attachment yielded only viewer",
    }
    hits = {key: [] for key in patterns}
    for path in sorted((ROOT / "usc").glob("usc*.xml")):
        text = path.read_text(encoding="utf-8")
        for key, pattern in patterns.items():
            if pattern.lower() in text.lower():
                hits[key].append(path.relative_to(ROOT).as_posix())
    return {**hits, "exit_code": 0 if not any(hits.values()) else 1}


def result_status_counts() -> dict:
    results = load_json("audit/xml-integration-results.json")
    return {
        "top_level_status": results.get("status"),
        "status_counts": dict(Counter(row.get("result_status") for row in results.get("results", []))),
        "summary": results.get("summary", {}),
        "exit_code": 0 if results.get("status") == "complete" else 1,
    }


def main() -> int:
    checks = {
        "xml_parse_checks": xml_parse_checks(),
        "duplicate_id_scan": duplicate_id_scan(),
        "source_text_reconciliation": source_text_reconciliation(),
        "note_action_reconciliation": note_action_reconciliation(),
        "trello_url_and_obsolete_boilerplate_scan": trello_and_boilerplate_scan(),
        "result_status_counts": result_status_counts(),
    }

    commands = [
        run_command("replacement-character scan", ["py", "-3", "tools/check_encoding.py"], 300),
        run_command("build Title 42 chunks", ["py", "-3", "tools/build_title42_chunks.py"], 300),
        run_command("build Code index", ["py", "-3", "tools/build_index.py"], 300),
        run_command("Title 42 build validation", ["py", "-3", "tools/check_title42_build.py"], 300),
        run_command("Python tests", ["py", "-3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], 300),
        run_command("Node citation routing tests", ["node", "tests/test_citation_routing.mjs"], 120),
        run_command("Node USAR notes tests", ["node", "tests/test_usar_notes.mjs"], 120),
        run_command("strengthened integration-result validation", ["python", "audit/scripts/validate_xml_integration_results.py"], 300),
    ]

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "repository": str(ROOT),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "checks": checks,
        "commands": commands,
    }
    failed_checks = [name for name, check in checks.items() if check.get("exit_code") != 0]
    failed_commands = [cmd["label"] for cmd in commands if cmd["exit_code"] != 0]
    report["summary"] = {
        "failed_checks": failed_checks,
        "failed_commands": failed_commands,
        "exit_code": 0 if not failed_checks and not failed_commands else 1,
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return report["summary"]["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
