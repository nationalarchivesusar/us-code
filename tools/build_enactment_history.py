#!/usr/bin/env python3
"""Build conservative Public Law enactment timelines for U.S. Code sections.

This dataset is intentionally distinct from ``data/version-history``. The
repository-state history proves what statutory text existed at selected Git
states. This builder records *law-by-law codification events* proved by the
codification audit ledger.

Audit descriptions and source quotations are evidence about an operation; they
are never promoted into an exact intermediate U.S. Code text snapshot.

A narrower high-confidence tier is available when all of the following are
true for a section:

* the audit yields exactly one verified substantive enactment event;
* the finalized public-law crosswalk names exactly that same Public Law for
  the section; and
* the separately generated section-history dataset proves an exact
  baseline-to-current textual change.

Only in that sole-enactment situation is the exact baseline/current pair
attached to the event. This is attribution of two independently verified
repository states to the sole published enactment, not reconstruction from
summary prose.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "audit" / "xml-integration-results.json"
PUBLIC_LAWS_PATH = ROOT / "data" / "public-laws.json"
SECTION_HISTORY_DIR = ROOT / "data" / "section-history"
OUTPUT_DIR = ROOT / "data" / "enactment-history"

TARGET_RE = re.compile(r"^/us/usc/t(?P<title>\d+)/s(?P<section>[^/]+)(?P<remainder>/.*)?$", re.I)
LAW_RE = re.compile(r"^(?P<congress>\d+)-(?P<number>\d+)$")

# These treatments alter notes, metadata, organization, or publication
# apparatus rather than the operative section text. They must never appear as
# statutory enactment events merely because their audit record points at a
# section node.
NON_SUBSTANTIVE_MARKERS = (
    "note",
    "toc",
    "table-of-contents",
    "table of contents",
    "source-credit",
    "source credit",
    "heading-only",
    "heading only",
    "historical-only",
    "historical only",
    "codification-only",
    "codification only",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_law_number(value: Any) -> str | None:
    text = str(value or "").strip()
    text = re.sub(r"^(?:Pub(?:lic)?\.?\s*L(?:aw)?\.?\s*)", "", text, flags=re.I)
    text = text.replace("–", "-").replace("—", "-").replace("_", "-")
    match = re.search(r"(\d+)\s*-\s*(\d+)", text)
    if not match:
        return None
    return f"{int(match.group(1))}-{int(match.group(2))}"


def law_sort_key(value: str) -> tuple[int, int, str]:
    match = LAW_RE.match(value or "")
    if not match:
        return (10**9, 10**9, value or "")
    return (int(match.group("congress")), int(match.group("number")), value)


def section_key(title: str, section: str) -> str:
    return f"{str(title).lower()}:{str(section).lower()}"


def target_from_identifier(value: Any) -> dict[str, Any] | None:
    match = TARGET_RE.match(str(value or "").strip())
    if not match:
        return None
    title = str(int(match.group("title")))
    section = match.group("section")
    remainder = match.group("remainder") or ""
    return {
        "title": title,
        "section": section,
        "subsection_path": remainder.lstrip("/") or None,
        "usc_node_id": str(value),
    }


def is_substantive_record(record: dict[str, Any]) -> bool:
    if str(record.get("result_status") or "").strip().lower() != "applied":
        return False
    if not target_from_identifier(record.get("final_section_or_subsection_identifier")):
        return False

    treatment = str(record.get("planned_treatment") or "").strip().lower()
    action = str(record.get("planned_action") or "").strip().lower()
    combined = f"{treatment} {action}"
    if any(marker in combined for marker in NON_SUBSTANTIVE_MARKERS):
        return False

    # An applied record must identify a concrete XML node change. This keeps
    # scope-only/planning entries out even if their prose uses an operative verb.
    changed = []
    for field in (
        "actual_node_ids_added",
        "actual_node_ids_changed",
        "actual_node_ids_removed",
        "nodes_created",
        "nodes_deleted",
    ):
        value = record.get(field)
        if isinstance(value, list):
            changed.extend(str(item) for item in value if str(item).strip())
    return bool(changed)


def treatment_label(record: dict[str, Any]) -> str:
    treatment = str(record.get("planned_treatment") or "").strip().lower()
    action = str(record.get("planned_action") or "").strip().lower()
    combined = f"{treatment} {action}"
    if "repeal" in combined or "remove" in combined or "delete" in combined:
        return "repealed"
    if "new-section" in treatment or "insert new section" in action or "add new section" in action:
        return "added"
    if "new-subsection" in treatment or "insert subsection" in action or "add subsection" in action:
        return "added subsection"
    if "redesignat" in combined or "renumber" in combined:
        return "redesignated"
    if "replace" in combined:
        return "replaced text"
    return "amended"


def public_law_lookup(payload: Any) -> dict[str, dict[str, Any]]:
    if isinstance(payload, dict):
        laws = payload.get("laws")
        if not isinstance(laws, list):
            laws = payload.get("public_laws")
    else:
        laws = payload
    if not isinstance(laws, list):
        return {}

    lookup: dict[str, dict[str, Any]] = {}
    for law in laws:
        if not isinstance(law, dict):
            continue
        number = normalize_law_number(
            law.get("public_law") or law.get("public_law_number") or law.get("number")
        )
        if number:
            lookup[number] = law
    return lookup


def target_candidates(law: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for target in law.get("targets") or []:
        if isinstance(target, dict):
            yield target
    for action in law.get("actions") or []:
        if not isinstance(action, dict):
            continue
        for target in action.get("targets") or []:
            if isinstance(target, dict):
                yield target
        target = action.get("target")
        if isinstance(target, dict):
            yield target


def public_laws_by_section(payload: Any) -> dict[str, set[str]]:
    """Return all published Public Laws associated with each exact section."""
    result: dict[str, set[str]] = defaultdict(set)
    for number, law in public_law_lookup(payload).items():
        for target in target_candidates(law):
            title = str(target.get("title") or "").lstrip("0") or "0"
            section = str(target.get("section") or "").strip()
            if title and section:
                result[section_key(title, section)].add(number)
    return result


def compact_law_metadata(number: str, law: dict[str, Any] | None) -> dict[str, Any]:
    law = law or {}
    title = law.get("title") or law.get("name") or law.get("short_title")
    url = law.get("trello_url") or law.get("url") or law.get("source_url")
    status = law.get("status")
    return {
        "public_law": number,
        "citation": f"Pub. L. {number}",
        "title": str(title).strip() if title else None,
        "url": str(url).strip() if url else None,
        "status": str(status).strip() if status else None,
    }


def unique_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def build_records(audit_payload: Any, laws_payload: Any) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    results = audit_payload.get("results", []) if isinstance(audit_payload, dict) else audit_payload
    if not isinstance(results, list):
        raise ValueError("Audit payload does not contain a results list")

    laws = public_law_lookup(laws_payload)
    grouped: dict[tuple[str, str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    considered = 0

    for raw in results:
        if not isinstance(raw, dict):
            continue
        considered += 1
        if not is_substantive_record(raw):
            continue
        number = normalize_law_number(raw.get("public_law"))
        target = target_from_identifier(raw.get("final_section_or_subsection_identifier"))
        if not number or not target:
            continue
        grouped[(target["title"], target["section"], number)].append((raw, target))

    sections: dict[tuple[str, str], dict[str, Any]] = {}
    for (title, section, number), items in grouped.items():
        key = (title, section)
        section_record = sections.setdefault(
            key,
            {
                "schema_version": "1.1",
                "title": title,
                "section": section,
                "citation": f"{title} U.S.C. § {section}",
                "history_kind": "verified-enactment-events",
                "reliability": {
                    "event_claim": "Each event is backed by an applied codification-audit record tied to this U.S. Code section.",
                    "text_claim": "Audit descriptions and quotations are evidence only; they are never converted into statutory text.",
                    "exact_attribution_rule": "Exact before/after text may be attached only when this is the sole verified enactment and sole published Public Law associated with the section, and section-history independently proves the text change.",
                },
                "events": [],
            },
        )

        rows = [item[0] for item in items]
        targets = [item[1] for item in items]
        labels = unique_strings(treatment_label(row) for row in rows)
        operations = unique_strings(
            row.get("planned_action") or row.get("planned_treatment") for row in rows
        )
        source_provisions = unique_strings(row.get("provision_reference") for row in rows)
        source_files = unique_strings(row.get("source_file") for row in rows)
        source_quotations = unique_strings(row.get("source_quotation") for row in rows)
        validation = unique_strings(row.get("validation_result") for row in rows)
        node_ids = unique_strings(
            value
            for row in rows
            for field in (
                "actual_node_ids_added",
                "actual_node_ids_changed",
                "actual_node_ids_removed",
                "nodes_created",
                "nodes_deleted",
            )
            for value in (row.get(field) if isinstance(row.get(field), list) else [])
        )
        subsection_paths = unique_strings(target.get("subsection_path") for target in targets)

        event = {
            **compact_law_metadata(number, laws.get(number)),
            "verified_enactment_event": True,
            "change_labels": labels,
            "operations": operations,
            "source_provisions": source_provisions,
            "subsection_paths": subsection_paths,
            "changed_node_ids": node_ids,
            "source_files": source_files,
            "source_quotations": source_quotations,
            "validation_evidence": validation,
            "audit_action_ids": unique_strings(row.get("action_id") for row in rows),
            "exact_text_snapshot_available": False,
            "exact_text_snapshot": None,
        }
        event["evidence_sha256"] = sha256_text(
            json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        )
        section_record["events"].append(event)

    for section_record in sections.values():
        section_record["events"].sort(key=lambda event: law_sort_key(event["public_law"]))
        section_record["event_count"] = len(section_record["events"])
        section_record["public_law_count"] = len({event["public_law"] for event in section_record["events"]})

    manifest = manifest_for_sections(audit_payload, sections, considered, exact_pairs=0)
    return manifest, sections


def attach_exact_sole_enactment_pairs(
    sections: dict[tuple[str, str], dict[str, Any]],
    laws_payload: Any,
    section_history_dir: Path = SECTION_HISTORY_DIR,
) -> int:
    """Attach exact baseline/current text only to a uniquely attributable event."""
    manifest_path = section_history_dir / "manifest.json"
    if not manifest_path.is_file():
        return 0
    history_manifest = read_json(manifest_path)
    history_sections = history_manifest.get("sections", {})
    crosswalk = public_laws_by_section(laws_payload)
    attached = 0

    for (title, section), record in sections.items():
        events = record.get("events") or []
        if len(events) != 1:
            continue
        event = events[0]
        law_number = event.get("public_law")
        if crosswalk.get(section_key(title, section), set()) != {law_number}:
            continue

        history_meta = history_sections.get(section_key(title, section))
        if not isinstance(history_meta, dict) or not history_meta.get("path"):
            continue
        history_path = ROOT / history_meta["path"]
        if not history_path.is_file():
            continue
        history = read_json(history_path)
        if history.get("status") not in {"added", "amended", "removed"}:
            continue

        baseline = history.get("baseline") or {}
        current = history.get("current") or {}
        event["exact_text_snapshot_available"] = True
        event["exact_text_snapshot"] = {
            "basis": "sole-published-enactment-between-verified-repository-states",
            "attribution_conditions": {
                "verified_enactment_events_for_section": 1,
                "published_public_laws_for_section": 1,
                "sole_public_law": law_number,
                "section_history_status": history.get("status"),
            },
            "baseline": {
                "commit": baseline.get("commit"),
                "present": baseline.get("present"),
                "heading": baseline.get("heading"),
                "text": baseline.get("text"),
                "sha256": baseline.get("sha256"),
            },
            "current": {
                "present": current.get("present"),
                "heading": current.get("heading"),
                "text": current.get("text"),
                "sha256": current.get("sha256"),
            },
            "diff": history.get("diff") or [],
            "caveat": "This exact pair is attributed to the Public Law because it is the sole verified substantive enactment event and sole published Public Law associated with this section between the fixed baseline and current repository states.",
        }
        event["evidence_sha256"] = sha256_text(
            json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        )
        record["exact_enactment_pair_count"] = 1
        attached += 1
    return attached


def manifest_for_sections(
    audit_payload: Any,
    sections: dict[tuple[str, str], dict[str, Any]],
    considered: int,
    *,
    exact_pairs: int,
) -> dict[str, Any]:
    manifest_sections: dict[str, Any] = {}
    total_events = 0
    for (title, section), record in sorted(
        sections.items(), key=lambda item: (int(item[0][0]), item[0][1].lower())
    ):
        total_events += record["event_count"]
        manifest_sections[section_key(title, section)] = {
            "title": title,
            "section": section,
            "citation": record["citation"],
            "event_count": record["event_count"],
            "public_law_count": record["public_law_count"],
            "exact_enactment_pair_count": record.get("exact_enactment_pair_count", 0),
            "path": f"data/enactment-history/{title}/{section}.json",
        }

    return {
        "schema_version": "1.1",
        "history_kind": "verified-enactment-events",
        "source": "audit/xml-integration-results.json",
        "audit_status": audit_payload.get("status") if isinstance(audit_payload, dict) else None,
        "audit_baseline_commit": audit_payload.get("baseline_commit") if isinstance(audit_payload, dict) else None,
        "reliability": {
            "verified_event_definition": "Applied, validated codification action tied to a concrete U.S. Code section or subsection target and concrete XML node changes.",
            "audit_prose_is_statutory_text": False,
            "exact_pair_definition": "An exact baseline/current statutory pair is exposed only where the event is uniquely attributable under both the audit timeline and finalized Public Law crosswalk.",
            "warning": "Sections with multiple enactments remain event-only unless independently verified intermediate statutory states are available.",
        },
        "counts": {
            "audit_records_considered": considered,
            "sections": len(sections),
            "events": total_events,
            "public_laws": len({event["public_law"] for record in sections.values() for event in record["events"]}),
            "exact_sole_enactment_pairs": exact_pairs,
        },
        "sections": manifest_sections,
    }


def write_dataset(manifest: dict[str, Any], sections: dict[tuple[str, str], dict[str, Any]], output_dir: Path = OUTPUT_DIR) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for (title, section), payload in sections.items():
        path = output_dir / title / f"{section}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def build(
    audit_path: Path = AUDIT_PATH,
    public_laws_path: Path = PUBLIC_LAWS_PATH,
    output_dir: Path = OUTPUT_DIR,
    section_history_dir: Path = SECTION_HISTORY_DIR,
) -> dict[str, Any]:
    audit_payload = read_json(audit_path)
    laws_payload = read_json(public_laws_path)
    initial_manifest, sections = build_records(audit_payload, laws_payload)
    exact_pairs = attach_exact_sole_enactment_pairs(sections, laws_payload, section_history_dir)
    manifest = manifest_for_sections(
        audit_payload,
        sections,
        initial_manifest["counts"]["audit_records_considered"],
        exact_pairs=exact_pairs,
    )
    write_dataset(manifest, sections, output_dir)
    return manifest


def main() -> int:
    manifest = build()
    counts = manifest["counts"]
    print(
        "Enactment history: "
        f"{counts['events']} verified events across {counts['sections']} sections "
        f"from {counts['public_laws']} Public Laws; "
        f"{counts['exact_sole_enactment_pairs']} exact sole-enactment text pairs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
