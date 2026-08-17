#!/usr/bin/env python3
"""Build a compact, versioned general U.S. Code index API.

The general API intentionally does not duplicate the full statutory body already
published in authoritative USLM form. Section records provide stable metadata,
deep links, and USLM identifiers; each title manifest points to the production
source that actually exists on the published site.
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
SCHEMA_VERSION = "1.1"
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


def published_source(title: str, meta: dict, xml_path: Path) -> dict:
    """Describe the source path that survives the Pages packaging step."""
    if title.lower() == "42":
        return {
            "type": "uslm-section-manifest",
            "path": "data/title-42/manifest.json",
            "format": "chunked USLM XML",
            "note": (
                "Title 42 is published as a section manifest and individual USLM XML "
                "section files; the monolithic usc42.xml source is intentionally omitted "
                "from the Pages artifact."
            ),
        }
    return {
        "type": "uslm-xml",
        "path": meta.get("file") or f"usc/{xml_path.name}",
        "format": "USLM XML",
        "note": "Locate the section by the compact API record's USLM identifier.",
    }


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
        source = published_source(title, meta, xml_path)
        manifest_relative = f"data/api/v1/code/titles/{title.lower()}/manifest.json"
        title_manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "title": title,
            "label": meta.get("label") or f"Title {title}",
            "heading": meta.get("heading") or "",
            "section_count": len(ordered),
            "source": source,
            "source_xml": source["path"] if source["type"] == "uslm-xml" else None,
            "source_manifest": source["path"] if source["type"] == "uslm-section-manifest" else None,
            "source_format": source["format"],
            "source_note": source["note"],
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
                "source": source,
                "source_xml": title_manifest["source_xml"],
                "source_manifest": title_manifest["source_manifest"],
            }
        )
        total_sections += len(ordered)

    index = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "name": "USAR General U.S. Code API",
        "namespace": "data/api/v1/code/",
        "publication_model": "compact section metadata with production-valid USLM source pointers",
        "criminal_law_api_unchanged": True,
        "lookup": {
            "step_1": "Fetch index.json and choose a title manifest.",
            "step_2": "Use section_to_chunk in that title manifest to locate the compact section chunk.",
            "step_3": "Read the matching section metadata object from the chunk's sections array.",
            "full_text": (
                "Follow the title manifest's source object. Most titles use one USLM XML file; "
                "Title 42 uses its published section manifest and individual USLM XML section files."
            ),
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
