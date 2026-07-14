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
BASELINE_TEXT_CACHE: dict[str, str | None] = {}
DIFF_TEXT_CACHE: dict[str, str] = {}
BASELINE_NODE_EXISTS_CACHE: dict[str, bool] = {}
BASELINE_NODE_IDS: set[str] | None = None


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8")


def git_maybe(*args: str) -> str | None:
    try:
        return git(*args)
    except subprocess.CalledProcessError:
        return None


def resolve_lfs_pointer(text: str) -> str:
    if not text.startswith("version https://git-lfs.github.com/spec/v1"):
        return text
    oid_match = re.search(r"oid sha256:([0-9a-f]{64})", text)
    if not oid_match:
        return text
    oid = oid_match.group(1)
    lfs_path = ROOT / ".git" / "lfs" / "objects" / oid[:2] / oid[2:4] / oid
    if lfs_path.exists():
        return lfs_path.read_text(encoding="utf-8")
    return text


def git_show_text(revision_path: str) -> str | None:
    text = git_maybe("show", revision_path)
    return resolve_lfs_pointer(text) if text is not None else None


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write_json(path: str, data: dict) -> None:
    (ROOT / path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def changed_xml_files() -> set[str]:
    out = git("diff", "--name-only", BASELINE, "--", "usc")
    return {line.strip().replace("\\", "/") for line in out.splitlines() if line.strip().endswith(".xml")}


def file_diff(rel_file: str | None) -> str:
    if not rel_file:
        return ""
    rel = rel_file.replace("\\", "/")
    if not rel.startswith("usc/"):
        rel = f"usc/{rel}"
    if rel not in DIFF_TEXT_CACHE:
        DIFF_TEXT_CACHE[rel] = git_maybe("diff", "--unified=0", BASELINE, "--", rel) or ""
    return DIFF_TEXT_CACHE[rel]


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
    if not all(proof.get(key) for key in required) or proof.get("baseline_commit") != BASELINE:
        return False
    xml_file = str(proof["xml_file"]).replace("\\", "/")
    if xml_file not in BASELINE_TEXT_CACHE:
        BASELINE_TEXT_CACHE[xml_file] = git_show_text(f"{BASELINE}:{xml_file}")
    baseline_text = BASELINE_TEXT_CACHE[xml_file]
    if not baseline_text:
        return False
    if f'id="{proof["xml_node_id"]}"' not in baseline_text:
        return False
    return proof["uslm_identifier"] in baseline_text and bool(str(proof.get("source_text_comparison") or "").strip())


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


def final_node_ids(texts: dict[str, str]) -> set[str]:
    ids: set[str] = set()
    for text in texts.values():
        ids.update(re.findall(r'\bid="([^"]+)"', text))
    return ids


def build_note_index(texts: dict[str, str]) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    pattern = re.compile(r'<note\b(?=[^>]*\bid="(rp-pl\d{6}-codification)")[^>]*>.*?</note>', re.S)
    for rel, text in texts.items():
        for match in pattern.finditer(text):
            found[match.group(1)] = (rel, match.group(0))
    return found


def node_exists_in_baseline(node_id: str, rel_file: str | None, baseline_cache: dict[str, str | None]) -> bool:
    if not rel_file:
        return False
    rel = rel_file.replace("\\", "/")
    if not rel.startswith("usc/"):
        rel = f"usc/{rel}"
    if rel not in baseline_cache:
        baseline_cache[rel] = git_maybe("show", f"{BASELINE}:{rel}")
    return bool(baseline_cache[rel] and f'id="{node_id}"' in baseline_cache[rel])


def node_exists_in_baseline_repo(node_id: str) -> bool:
    global BASELINE_NODE_IDS
    if not node_id:
        return False
    if BASELINE_NODE_IDS is None:
        BASELINE_NODE_IDS = set()
        files = git("ls-tree", "-r", "--name-only", BASELINE, "usc").splitlines()
        for rel in files:
            if not rel.endswith(".xml"):
                continue
            text = git_show_text(f"{BASELINE}:{rel}") or ""
            BASELINE_NODE_IDS.update(re.findall(r'\bid="([^"]+)"', text))
    return node_id in BASELINE_NODE_IDS


def baseline_text(rel_file: str | None, baseline_cache: dict[str, str | None]) -> str | None:
    if not rel_file:
        return None
    rel = rel_file.replace("\\", "/")
    if not rel.startswith("usc/"):
        rel = f"usc/{rel}"
    if rel not in baseline_cache:
        baseline_cache[rel] = git_show_text(f"{BASELINE}:{rel}")
    return baseline_cache[rel]


def read_final_xml_texts() -> dict[str, str]:
    return {path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8") for path in (ROOT / "usc").glob("*.xml")}


def is_note_action(plan_row: dict) -> bool:
    action = plan_row.get("action_type")
    treatment = str(plan_row.get("treatment") or "")
    return action in {"add statutory note", "add historical note", "add amendment note"} or "note" in treatment


def normalized_words(value: object) -> list[str]:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.findall(r"[A-Za-z0-9]{4,}", text.lower())


def text_has_claim(container: str, claim: object, *, minimum: int = 6) -> bool:
    words = normalized_words(claim)
    if not words:
        return False
    container_words = set(normalized_words(container))
    sample = []
    for word in words:
        if word not in sample:
            sample.append(word)
        if len(sample) >= 20:
            break
    if len(sample) < minimum:
        return all(word in container_words for word in sample)
    return sum(1 for word in sample if word in container_words) >= minimum


def identifier_exists(identifier: str | None, texts: dict[str, str]) -> bool:
    if not identifier:
        return False
    note_match = re.search(r"/note/([^/\s]+)", identifier)
    if note_match:
        note_id = note_match.group(1)
        if any(f'id="{note_id}"' in text for text in texts.values()):
            return True
    identifiers = re.findall(r"/us/usc/t\d+[A-Za-z]?(?:/[A-Za-z0-9_.-]+)*", identifier)
    if not identifiers:
        return True
    return any(any(f'identifier="{candidate}"' in text or f'href="{candidate}"' in text for text in texts.values()) for candidate in identifiers)


def final_file_text(xml_file: str | None, texts: dict[str, str]) -> str:
    if not xml_file:
        return ""
    rel = xml_file.replace("\\", "/")
    if not rel.startswith("usc/"):
        rel = f"usc/{rel}"
    return texts.get(rel, "")


def node_context(text: str | None, node_id: str, radius: int = 1200) -> str:
    if not text:
        return ""
    index = text.find(f'id="{node_id}"')
    if index == -1:
        return ""
    return text[max(0, index - radius) : index + radius]


def action_specific_diff_matches(result: dict, final_id: str | None, diff_text: str) -> bool:
    if not diff_text:
        return False
    for key in ("actual_node_ids_added", "actual_node_ids_changed", "actual_node_ids_removed"):
        for node_id in result.get(key) or []:
            if node_id and node_id in diff_text:
                return True
    for candidate in re.findall(r"/us/usc/t\d+[A-Za-z]?/s[0-9A-Za-z.-]+(?:/[0-9A-Za-z.-]+)*", final_id or ""):
        if candidate in diff_text:
            return True
    return text_has_claim(diff_text, result.get("exact_enacted_text_applied"), minimum=4)


def action_specific_baseline_change_matches(result: dict, baseline: str | None, final: str) -> bool:
    if not baseline or baseline == final:
        return False
    for node_id in result.get("actual_node_ids_added") or []:
        if f'id="{node_id}"' in final and f'id="{node_id}"' not in baseline:
            return True
    for node_id in result.get("actual_node_ids_changed") or []:
        old_context = node_context(baseline, node_id)
        new_context = node_context(final, node_id)
        if old_context and new_context and old_context != new_context:
            return True
    for node_id in result.get("actual_node_ids_removed") or []:
        if f'id="{node_id}"' in baseline and f'id="{node_id}"' not in final:
            return True
    return text_has_claim(final, result.get("exact_enacted_text_applied")) and not text_has_claim(baseline, result.get("exact_enacted_text_applied"))


def forbidden_executable_text(text: object) -> bool:
    value = str(text or "").lower()
    forbidden = [
        "no operative text",
        "not section-level codification",
        "retain as repeal history only",
        "no code action",
    ]
    return any(phrase in value for phrase in forbidden)


def main() -> int:
    plan = load_json("audit/xml-integration-plan.json")
    results = load_json("audit/xml-integration-results.json")
    plan_rows = plan.get("provisions", [])
    result_rows = results.get("results", [])
    changed = changed_xml_files()
    final_texts = read_final_xml_texts()
    final_ids = final_node_ids(final_texts)
    final_notes = build_note_index(final_texts)
    baseline_cache: dict[str, str | None] = {}
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
    claimed_added_nodes_missing = 0
    claimed_changed_nodes_unchanged = 0
    claimed_removed_nodes_still_present = 0
    baseline_proof_failures = 0
    note_action_proof_failures = 0
    source_credit_failures = 0
    amendment_note_failures = 0
    toc_failures = 0
    final_identifier_failures = 0
    final_text_failures = 0
    action_specific_diff_failures = 0
    changed_node_baseline_failures = 0
    removed_node_baseline_failures = 0
    supersession_metadata_failures = 0

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
        xml_after = result.get("xml_file_after") or result.get("xml_file_before")
        xml_after_rel = f"usc/{xml_after}" if xml_after and not str(xml_after).startswith("usc/") else xml_after
        added_nodes = [node for node in result.get("actual_node_ids_added") or [] if node]
        changed_nodes = [node for node in result.get("actual_node_ids_changed") or [] if node]
        removed_nodes = [node for node in result.get("actual_node_ids_removed") or [] if node]
        final_id = result.get("final_section_or_subsection_identifier") or plan_row.get("exact_uslm_code_identifier")
        target_text = final_file_text(str(xml_after_rel or ""), final_texts)
        diff_text = file_diff(str(xml_after_rel or ""))
        baseline_target_text = baseline_text(xml_after_rel, baseline_cache)

        for node_id in added_nodes:
            if node_id not in final_ids:
                claimed_added_nodes_missing += 1
                issues.append(f"{action_id}: claimed added node {node_id} is absent from final XML")
            if node_exists_in_baseline(node_id, xml_after_rel, baseline_cache):
                issues.append(f"{action_id}: claimed added node {node_id} already existed in baseline {xml_after_rel}")

        for node_id in changed_nodes:
            if node_id not in final_ids:
                claimed_changed_nodes_unchanged += 1
                issues.append(f"{action_id}: claimed changed node {node_id} is absent from final XML")
            if not node_exists_in_baseline_repo(node_id):
                changed_node_baseline_failures += 1
                issues.append(f"{action_id}: claimed changed node {node_id} did not exist anywhere in baseline XML")
            elif node_exists_in_baseline(node_id, xml_after_rel, baseline_cache) and node_context(baseline_target_text, node_id) == node_context(target_text, node_id):
                changed_node_baseline_failures += 1
                issues.append(f"{action_id}: claimed changed node {node_id} has no file-level XML difference from baseline")

        for node_id in removed_nodes:
            if node_id in final_ids:
                claimed_removed_nodes_still_present += 1
                issues.append(f"{action_id}: claimed removed node {node_id} remains in final XML")
            if not node_exists_in_baseline_repo(node_id):
                removed_node_baseline_failures += 1
                issues.append(f"{action_id}: claimed removed node {node_id} did not exist anywhere in baseline XML")

        if executable:
            executable_count += 1
            if status not in VALID_EXECUTABLE_STATUSES:
                issues.append(f"{action_id}: executable action has invalid/incomplete status {status!r}")
            if status == "blocked":
                blocked += 1
            if status == "already-satisfied":
                false_already += 1
            if status == "already-satisfied-with-baseline-proof" and not has_baseline_node(result.get("baseline_proof")):
                baseline_proof_failures += 1
                issues.append(f"{action_id}: already-satisfied-with-baseline-proof lacks required baseline node proof")
            if status == "applied":
                files = {f"usc/{name}" if not str(name).startswith("usc/") else str(name) for name in [result.get("xml_file_after") or result.get("xml_file_before")] if name}
                if not files.intersection(changed):
                    issues.append(f"{action_id}: applied result has no changed XML file after baseline")
                if not action_specific_diff_matches(result, final_id, diff_text) and not action_specific_baseline_change_matches(result, baseline_target_text, target_text):
                    action_specific_diff_failures += 1
                    issues.append(f"{action_id}: applied result lacks an action-specific diff anchor in {xml_after_rel}")
            if action_type in {"insert new section", "insert new subsection"} and is_title_root(final_id):
                title_root_exec += 1
                issues.append(f"{action_id}: executable insertion uses only title-root identifier {final_id!r}")
            if status in {"applied", "already-satisfied-with-baseline-proof"} and not identifier_exists(final_id, final_texts):
                final_identifier_failures += 1
                issues.append(f"{action_id}: final identifier {final_id!r} is not present as a final XML identifier or href")
            if status in {"applied", "already-satisfied-with-baseline-proof"} and not result.get("exact_enacted_text_applied"):
                issues.append(f"{action_id}: executable completed result lacks exact statutory text")
            elif status == "applied" and not text_has_claim(target_text, result.get("exact_enacted_text_applied")):
                final_text_failures += 1
                issues.append(f"{action_id}: final XML file does not contain enough of the claimed statutory/action text")
            if status == "applied" and forbidden_executable_text(result.get("exact_enacted_text_applied")):
                issues.append(f"{action_id}: executable applied result contains non-executable/no-operative wording")
            if status in {"applied", "already-satisfied-with-baseline-proof"} and not result.get("source_credit_change"):
                source_credit_failures += 1
                issues.append(f"{action_id}: executable completed result lacks source-credit result")
            if status in {"applied", "already-satisfied-with-baseline-proof"} and not result.get("amendment_note_change"):
                amendment_note_failures += 1
                issues.append(f"{action_id}: executable completed result lacks amendment-note result")
            if action_type in {"insert new section", "insert new subsection"} and status in {"applied", "already-satisfied-with-baseline-proof"}:
                toc_text = str(result.get("toc_change") or "")
                if not toc_text or re.search(r"\bno toc change\b", toc_text, re.I):
                    toc_failures += 1
                    issues.append(f"{action_id}: executable insertion lacks required TOC result")
            if status == "superseded-by-later-action":
                proof_text = " ".join(str(result.get(key) or "") for key in ("validation_result", "documented_no_op_explanation", "toc_change"))
                if "superseded" not in proof_text.lower() and "later" not in proof_text.lower():
                    issues.append(f"{action_id}: superseded result lacks supersession explanation")
                for required in ("later_action_id", "superseding_law", "shared_target", "chronology_explanation", "supersession_proof"):
                    if not result.get(required):
                        supersession_metadata_failures += 1
                        issues.append(f"{action_id}: superseded result lacks {required}")
                if not identifier_exists(final_id, final_texts):
                    supersession_metadata_failures += 1
                    issues.append(f"{action_id}: superseded final target {final_id!r} is absent from final XML")
        else:
            if status not in VALID_NON_EXECUTABLE_STATUSES:
                issues.append(f"{action_id}: non-executable action has invalid status {status!r}")
            if status == "documented-no-code-action":
                if action_type != "no Code action":
                    issues.append(f"{action_id}: documented-no-code-action used for non-no-Code plan action {action_type!r}")
                if not result.get("documented_no_op_explanation"):
                    issues.append(f"{action_id}: documented non-executable disposition lacks explanation")
            if is_note_action(plan_row):
                note_id = result.get("verified_note_node_id") or (plan_row.get("existing_project_node_ids_to_remove_or_replace") or [None])[0]
                note_file, note_xml = final_notes.get(str(note_id), (None, None)) if note_id else (None, None)
                if status != "applied" or not note_id or not note_xml:
                    note_action_proof_failures += 1
                    issues.append(f"{action_id}: note action lacks applied result with physical XML note proof")
                elif result.get("verified_note_xml_file") and str(result["verified_note_xml_file"]).replace("\\", "/") != str(note_file):
                    note_action_proof_failures += 1
                    issues.append(f"{action_id}: note proof file {result['verified_note_xml_file']} does not match final XML location {note_file}")
                elif "trello.com" in note_xml.lower() or "<quotedcontent" in note_xml.lower() or "authenticated statutory text was unavailable" in note_xml.lower():
                    note_action_proof_failures += 1
                    issues.append(f"{action_id}: physical XML note {note_id} contains stale URL, full dump, or false source boilerplate")
                elif not text_has_claim(note_xml, result.get("verified_note_text_excerpt") or result.get("exact_enacted_text_applied")):
                    note_action_proof_failures += 1
                    issues.append(f"{action_id}: physical XML note {note_id} does not contain the recorded note text")
                elif status == "applied" and not action_specific_diff_matches(result, result.get("final_section_or_subsection_identifier"), diff_text) and not action_specific_baseline_change_matches(result, baseline_target_text, target_text):
                    action_specific_diff_failures += 1
                    issues.append(f"{action_id}: note action lacks an action-specific diff anchor in {xml_after_rel}")

    missing = set(plan_by_id) - seen
    if missing:
        issues.append(f"missing result rows: {len(missing)}")
    if executable_count != 137:
        issues.append(f"executable action count is {executable_count}, expected 137")

    artifact_issues = scan_xml_artifacts()
    issues.extend(artifact_issues)

    summary = {
        "plan_actions": len(plan_rows),
        "result_actions": len(result_rows),
        "executable_actions": executable_count,
        "blocked_actions": blocked,
        "false_already_satisfied_claims": false_already,
        "title_root_executable_targets": title_root_exec,
        "claimed_added_nodes_missing": claimed_added_nodes_missing,
        "claimed_changed_nodes_unchanged": claimed_changed_nodes_unchanged,
        "claimed_removed_nodes_still_present": claimed_removed_nodes_still_present,
        "already_satisfied_baseline_proof_failures": baseline_proof_failures,
        "note_action_proof_failures": note_action_proof_failures,
        "source_credit_failures": source_credit_failures,
        "amendment_note_failures": amendment_note_failures,
        "toc_failures": toc_failures,
        "final_identifier_failures": final_identifier_failures,
        "final_text_failures": final_text_failures,
        "action_specific_diff_failures": action_specific_diff_failures,
        "changed_node_baseline_failures": changed_node_baseline_failures,
        "removed_node_baseline_failures": removed_node_baseline_failures,
        "supersession_metadata_failures": supersession_metadata_failures,
        "stale_or_inaccurate_project_notes": len(artifact_issues),
        "changed_xml_files": sorted(changed),
        "issue_count": len(issues),
    }
    results.setdefault("summary", {}).update(summary)
    results["status"] = "complete" if not issues else "validation-failed"
    write_json("audit/xml-integration-results.json", results)
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
