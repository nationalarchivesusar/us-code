#!/usr/bin/env python3
"""Build verified repository-snapshot version histories for Public-Law-linked Code sections.

This does not invent one version per enactment. It publishes exact section text only
for repository states that can be retrieved and verified, and associates a Public Law
with a snapshot only when the snapshot commit message explicitly names that law.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

from build_section_history import (
    DEFAULT_BASELINE,
    PUBLIC_LAWS,
    ROOT,
    USC_DIR,
    extract_sections,
    git_output,
    load_json,
    public_law_targets,
    sha256_text,
    title_filename,
    token_diff,
)

OUTPUT_DIR = ROOT / "data" / "version-history"
SCHEMA_VERSION = "1.0"
SNAPSHOTS = [
    {
        "commit": DEFAULT_BASELINE,
        "label": "Codification repository baseline",
        "kind": "baseline",
    },
    {
        "commit": "21e483ef2f71762f954f20c48a9a207898848645",
        "label": "Public-law corpus reconciled",
        "kind": "repository-snapshot",
    },
    {
        "commit": "6ece679f3e504db46d27fbd06a48980850a056f1",
        "label": "2026 enactments integrated",
        "kind": "repository-snapshot",
    },
]
LAW_NUMBER_RE = re.compile(r"\b(\d{1,3}-\d{1,4})\b")


def section_key(title: str, section: str) -> str:
    return f"{title.lower()}:{section.lower()}"


def git_file_bytes(commit: str, relative_path: str) -> bytes:
    raw = git_output(["git", "show", f"{commit}:{relative_path}"])
    if raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raw = git_output(["git", "lfs", "smudge"], input_bytes=raw)
        if raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise RuntimeError(f"LFS object unavailable for {commit}:{relative_path}")
    return raw


def commit_metadata(commit: str) -> dict:
    fmt = "%cI%x00%B"
    output = git_output(["git", "show", "-s", f"--format={fmt}", commit]).decode("utf-8", errors="replace")
    committed_at, _, message = output.partition("\x00")
    law_numbers = sorted(set(LAW_NUMBER_RE.findall(message)))
    return {
        "commit": commit,
        "committed_at": committed_at.strip() or None,
        "message": " ".join(message.split()),
        "named_public_laws": law_numbers,
    }


def laws_by_section(payload: dict) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for law in payload.get("laws", []):
        seen: set[str] = set()
        candidates = list(law.get("targets") or [])
        for action in law.get("actions") or []:
            candidates.extend(action.get("targets") or [])
            if action.get("target"):
                candidates.append(action["target"])
        for target in candidates:
            title = str(target.get("title") or "").lstrip("0") or "0"
            section = str(target.get("section") or "").strip()
            if not section:
                continue
            key = section_key(title, section)
            if key in seen:
                continue
            seen.add(key)
            result.setdefault(key, []).append(
                {
                    "public_law": law.get("public_law"),
                    "title": law.get("title"),
                    "status": law.get("status"),
                }
            )
    return result


def version_payload(record: dict | None, state: dict) -> dict:
    text = record["text"] if record else ""
    return {
        "state_id": state["state_id"],
        "label": state["label"],
        "kind": state["kind"],
        "commit": state.get("commit"),
        "committed_at": state.get("committed_at"),
        "present": record is not None,
        "heading": record["heading"] if record else None,
        "text": text if record else None,
        "sha256": sha256_text(text) if record else None,
        "named_public_laws": state.get("named_public_laws", []),
    }


def collapse_identical_versions(versions: list[dict]) -> list[dict]:
    collapsed: list[dict] = []
    for version in versions:
        identity = (version["present"], version["sha256"])
        if collapsed and (collapsed[-1]["present"], collapsed[-1]["sha256"]) == identity:
            collapsed[-1].setdefault("also_represents", []).append(
                {
                    "state_id": version["state_id"],
                    "label": version["label"],
                    "kind": version["kind"],
                    "commit": version.get("commit"),
                    "committed_at": version.get("committed_at"),
                }
            )
            if version["kind"] == "current":
                collapsed[-1]["label"] = version["label"]
                collapsed[-1]["kind"] = "current"
            collapsed[-1]["named_public_laws"] = sorted(
                set(collapsed[-1].get("named_public_laws", [])) | set(version.get("named_public_laws", []))
            )
            continue
        collapsed.append(version)
    return collapsed


def build(*, output_dir: Path = OUTPUT_DIR, public_laws_path: Path = PUBLIC_LAWS) -> dict:
    laws = load_json(public_laws_path)
    targets = public_law_targets(laws)
    law_index = laws_by_section(laws)

    snapshot_states = []
    for index, snapshot in enumerate(SNAPSHOTS):
        meta = commit_metadata(snapshot["commit"])
        snapshot_states.append(
            {
                **snapshot,
                **meta,
                "state_id": f"snapshot-{index + 1}",
            }
        )
    current_state = {
        "state_id": "current",
        "label": "Current published Code",
        "kind": "current",
        "commit": None,
        "committed_at": datetime.now(UTC).isoformat(),
        "named_public_laws": [],
    }

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_sections: dict[str, dict] = {}
    unavailable: dict[str, dict[str, str]] = {}
    versioned_count = 0

    for title, sections in sorted(targets.items()):
        filename = title_filename(title)
        current_path = USC_DIR / filename
        if not current_path.is_file():
            unavailable.setdefault(title, {})["current"] = f"Current source missing: usc/{filename}"
            continue
        current_sections = extract_sections(current_path.read_bytes(), expected_title=title)

        historical_sets: list[tuple[dict, dict[str, dict]]] = []
        for state in snapshot_states:
            try:
                historical_sets.append(
                    (
                        state,
                        extract_sections(
                            git_file_bytes(state["commit"], f"usc/{filename}"),
                            expected_title=title,
                        ),
                    )
                )
            except (RuntimeError, etree.XMLSyntaxError) as exc:
                unavailable.setdefault(title, {})[state["state_id"]] = str(exc)

        for section in sorted(sections, key=str.lower):
            versions: list[dict] = []
            for state, records in historical_sets:
                versions.append(version_payload(records.get(section.lower()), state))
            versions.append(version_payload(current_sections.get(section.lower()), current_state))
            versions = collapse_identical_versions(versions)
            if len(versions) < 2:
                continue

            comparisons: dict[str, list[dict[str, str]]] = {}
            for left in range(len(versions)):
                for right in range(left + 1, len(versions)):
                    before = versions[left]["text"] or ""
                    after = versions[right]["text"] or ""
                    comparisons[f"{left}:{right}"] = token_diff(before, after)

            key = section_key(title, section)
            section_laws = law_index.get(key, [])
            section_law_numbers = {item["public_law"] for item in section_laws if item.get("public_law")}
            for version in versions:
                version["named_public_laws"] = [
                    law_no for law_no in version.get("named_public_laws", []) if law_no in section_law_numbers
                ]

            relative_path = Path("data") / "version-history" / title.lower() / f"{section}.json"
            destination = ROOT / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "schema_version": SCHEMA_VERSION,
                "title": title,
                "section": section,
                "citation": f"{title} U.S.C. § {section}",
                "evidence": "Exact section text from verified repository states; no inferred per-enactment snapshots.",
                "versions": versions,
                "comparisons": comparisons,
                "associated_public_laws": section_laws,
                "limitations": [
                    "A repository snapshot may incorporate more than one enactment.",
                    "A Public Law is attached to a snapshot only when the commit message explicitly names that law.",
                    "Associated Public Laws are section history and do not by themselves prove the exact text after each enactment.",
                ],
            }
            destination.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            manifest_sections[key] = {
                "title": title,
                "section": section,
                "citation": record["citation"],
                "versions": len(versions),
                "path": relative_path.as_posix(),
            }
            versioned_count += 1

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "states": [{k: v for k, v in state.items() if k != "message"} for state in snapshot_states] + [current_state],
        "counts": {
            "versioned_sections": versioned_count,
            "unavailable_titles": len(unavailable),
        },
        "unavailable": unavailable,
        "sections": manifest_sections,
        "limitations": [
            "Version history is repository-state history, not a fabricated enactment-by-enactment chronology.",
            "Only exact retrievable statutory text is published as a version.",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    manifest = build()
    print(f"Built verified version history for {manifest['counts']['versioned_sections']} sections.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
