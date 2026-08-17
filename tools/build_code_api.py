#!/usr/bin/env python3
"""Build a compact, versioned general U.S. Code index API.

The general API intentionally does not duplicate the full statutory body already
published in the authoritative USLM XML. Section records provide stable metadata,
deep links, and USLM identifiers; each title manifest points to its source XML for
clients that need the complete statutory text.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from build_section_history import ROOT, USC_DIR, extract_sections

OUTPUT_DIR = ROOT / "data" / "api" / "v1" / "code"
TITLES_FILE = ROOT / "data" / "titles.json"
SCHEMA_VERSION = "1.0"
CHUNK_SIZE = 500


def natural_section_key(value: str):
    pieces = re.split(r"(\d+)", value)
    return tuple(int(piece) if piece.isdigit() else piece.lower() for piece in pieces)


def title_filename_number(path: Path) -> str:
    match = re.fullmatch(r"usc(\d+)([A-Za-z]?)\.xml", path.name)
    if not match:
        raise ValueError(path.name)
    number, suffix = match.groups()
    return f"{int(number)}{suffix.lower()}"


def load_title_metadata() -> dict[str, dict]:
    if not TITLES_FILE.is_file():
        return {}
    payload = json.loads(TITLES_FILE.read_text(encoding="utf-8"))
    return {str(item.get("number", "")).lower(): item for item in payload.get("titles", [])}


def build(output_dir: Path = OUTPUT_DIR) -> dict:
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    titles_dir = output_dir / "titles"
    titles_dir.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC).isoformat()
    title_meta = load_title_metadata()
    index_titles = []
    total_sections = 0

    for xml_path in sorted(USC_DIR.glob("usc*.xml")):
        title = title_filename_number(xml_path)
        sections = extract_sections(xml_path.read_bytes(), expected_title=title)
        ordered = [sections[key] for key in sorted(sections, key=natural_section_key)]
        if not ordered:
            continue

        title_output = titles_dir / title.lower()
        title_output.mkdir(parents=True, exist_ok=True)
        section_to_chunk: dict[str, str] = {}
        chunks = []

        for offset in range(0, len(ordered), CHUNK_SIZE):
            chunk_sections = ordered[offset : offset + CHUNK_SIZE]
            chunk_no = offset // CHUNK_SIZE + 1
            chunk_name = f"chunk-{chunk_no:03d}.json"
            relative_chunk = f"data/api/v1/code/titles/{title.lower()}/{chunk_name}"
            items = []
            for record in chunk_sections:
                section = record["section"]
                section_to_chunk[section.lower()] = relative_chunk
                items.append(
                    {
                        "section": section,
                        "citation": f"{title} U.S.C. § {section}",
                        "identifier": record["identifier"],
                        "heading": record["heading"],
                        "web_url": f"cite/{title}/{section}/",
                    }
                )
            (title_output / chunk_name).write_text(
                json.dumps(
                    {
                        "schema_version": SCHEMA_VERSION,
                        "title": title,
                        "generated_at": generated_at,
                        "sections": items,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            chunks.append(
                {
                    "path": relative_chunk,
                    "count": len(items),
                    "first_section": items[0]["section"],
                    "last_section": items[-1]["section"],
                }
            )

        meta = title_meta.get(title.lower(), {})
        source_xml = meta.get("file") or f"usc/{xml_path.name}"
        manifest_relative = f"data/api/v1/code/titles/{title.lower()}/manifest.json"
        title_manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "title": title,
            "label": meta.get("label") or f"Title {title}",
            "heading": meta.get("heading") or "",
            "section_count": len(ordered),
            "source_xml": source_xml,
            "source_format": "USLM XML",
            "source_note": (
                "Use the section identifier from the compact API record to locate the "
                "complete statutory text in source_xml."
            ),
            "chunks": chunks,
            "section_to_chunk": section_to_chunk,
        }
        (title_output / "manifest.json").write_text(
            json.dumps(title_manifest, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        index_titles.append(
            {
                "title": title,
                "label": title_manifest["label"],
                "heading": title_manifest["heading"],
                "section_count": len(ordered),
                "manifest": manifest_relative,
                "source_xml": source_xml,
            }
        )
        total_sections += len(ordered)

    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "name": "USAR General U.S. Code API",
        "namespace": "data/api/v1/code/",
        "publication_model": "compact section metadata with authoritative USLM source pointers",
        "criminal_law_api_unchanged": True,
        "lookup": {
            "step_1": "Fetch index.json and choose a title manifest.",
            "step_2": "Use section_to_chunk in that title manifest to locate the compact section chunk.",
            "step_3": "Read the matching section metadata object from the chunk's sections array.",
            "full_text": "Fetch source_xml from the title manifest and locate the record's USLM identifier.",
        },
        "counts": {"titles": len(index_titles), "sections": total_sections},
        "titles": index_titles,
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return index


def main() -> int:
    index = build()
    print(
        f"Built compact general Code API: {index['counts']['titles']} titles, "
        f"{index['counts']['sections']} sections."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
