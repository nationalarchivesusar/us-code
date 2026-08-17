#!/usr/bin/env python3
"""Build enactment history after canonicalizing compound audit targets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from .build_enactment_history import (
        AUDIT_PATH,
        OUTPUT_DIR,
        PUBLIC_LAWS_PATH,
        SECTION_HISTORY_DIR,
        attach_exact_sole_enactment_pairs,
        build_records,
        manifest_for_sections,
        read_json,
        write_dataset,
    )
    from .usc_target_normalization import (
        build_section_index,
        canonicalize_audit_payload,
    )
except ImportError:  # pragma: no cover - direct script execution
    from build_enactment_history import (
        AUDIT_PATH,
        OUTPUT_DIR,
        PUBLIC_LAWS_PATH,
        SECTION_HISTORY_DIR,
        attach_exact_sole_enactment_pairs,
        build_records,
        manifest_for_sections,
        read_json,
        write_dataset,
    )
    from usc_target_normalization import (
        build_section_index,
        canonicalize_audit_payload,
    )

ROOT = Path(__file__).resolve().parents[1]


def build(
    audit_path: Path = AUDIT_PATH,
    public_laws_path: Path = PUBLIC_LAWS_PATH,
    output_dir: Path = OUTPUT_DIR,
    section_history_dir: Path = SECTION_HISTORY_DIR,
) -> dict[str, Any]:
    audit_payload = read_json(audit_path)
    laws_payload = read_json(public_laws_path)
    section_index = build_section_index(ROOT / "usc")
    canonical_audit = canonicalize_audit_payload(audit_payload, section_index)

    _, sections = build_records(canonical_audit, laws_payload)
    exact_pairs = attach_exact_sole_enactment_pairs(
        sections,
        laws_payload,
        section_history_dir,
    )
    source_record_count = len(audit_payload.get("results", []))
    manifest = manifest_for_sections(
        audit_payload,
        sections,
        source_record_count,
        exact_pairs=exact_pairs,
    )
    manifest["target_normalization"] = canonical_audit.get(
        "canonical_target_expansion", {}
    )

    invalid = [
        key
        for key, meta in manifest.get("sections", {}).items()
        if "|" in str(meta.get("section") or "")
        or "?" in str(meta.get("section") or "")
    ]
    if invalid:
        raise ValueError(
            "Canonical enactment history still contains malformed section targets: "
            + ", ".join(invalid[:10])
        )

    write_dataset(manifest, sections, output_dir)
    return manifest


def main() -> int:
    manifest = build()
    counts = manifest["counts"]
    expansion = manifest.get("target_normalization", {})
    print(
        "Canonical enactment history: "
        f"{counts['events']} verified events across {counts['sections']} sections "
        f"from {counts['public_laws']} Public Laws; "
        f"{counts['exact_sole_enactment_pairs']} exact sole-enactment text pairs. "
        f"Expanded {expansion.get('source_record_count', 0)} audit records to "
        f"{expansion.get('expanded_record_count', 0)} single-target records."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
