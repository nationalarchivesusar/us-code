#!/usr/bin/env python3
"""Generate a lightweight metadata index for the US Code XML files."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict

import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[1]
USC_DIR = REPO_ROOT / "usc"
OUTPUT_FILE = REPO_ROOT / "data" / "titles.json"
NS = {
    "uslm": "http://xml.house.gov/schemas/uslm/1.0",
    "dc": "http://purl.org/dc/elements/1.1/",
}
ROOT_TAGS = {
    f"{{{NS['uslm']}}}title",
    f"{{{NS['uslm']}}}appendix",
    f"{{{NS['uslm']}}}division",
    f"{{{NS['uslm']}}}subtitle",
}


def _clean(text: str | None) -> str:
    if text is None:
        return ""
    return " ".join(text.split())


def _pointer_metadata(xml_path: Path) -> Dict[str, str]:
    name = xml_path.stem
    number = name[3:]
    label = f"Title {number}" if number else name
    return {
        "file": f"usc/{xml_path.name}",
        "identifier": "",
        "number": number,
        "heading": f"{label} (data stored via Git LFS; fetch required)",
        "pointer": True,
    }


def extract_title_metadata(xml_path: Path) -> Dict[str, str]:
    with xml_path.open("r", encoding="utf-8") as text_fh:
        first_line = text_fh.readline().strip()
        if first_line.startswith("version https://git-lfs.github.com"):
            return _pointer_metadata(xml_path)

    identifier = ""
    number = ""
    short_heading = ""
    long_heading = ""
    watching_root = False

    with xml_path.open("rb") as fh:
        context = ET.iterparse(fh, events=("start", "end"))
        for event, elem in context:
            tag = elem.tag
            if event == "start":
                if tag == f"{{{NS['uslm']}}}uscDoc" and not identifier:
                    identifier = elem.get("identifier", "")
                elif tag in ROOT_TAGS and not long_heading:
                    current_id = elem.get("identifier", "")
                    watching_root = True
                    if current_id.startswith("/us/usc/") and not identifier:
                        identifier = current_id
            elif event == "end":
                if tag == f"{{{NS['dc']}}}title" and not short_heading:
                    short_heading = _clean(elem.text)
                elif tag == f"{{{NS['uslm']}}}docNumber" and not number:
                    number = _clean(elem.text)
                elif watching_root and tag == f"{{{NS['uslm']}}}heading" and not long_heading:
                    long_heading = _clean(elem.text)
                elif watching_root and tag in ROOT_TAGS:
                    watching_root = False
                elem.clear()
            if short_heading and number and long_heading:
                break
        else:
            raise RuntimeError(f"Unable to extract metadata from {xml_path.name}")

    heading = long_heading if long_heading else short_heading
    return {
        "file": f"usc/{xml_path.name}",
        "identifier": identifier,
        "number": number,
        "heading": heading,
        "label": short_heading or heading,
    }


def build_index():
    titles = []
    for xml_path in sorted(USC_DIR.glob("usc*.xml")):
        titles.append(extract_title_metadata(xml_path))
    return {
        "generated": datetime.now(UTC).isoformat(),
        "titles": titles,
    }


def main() -> int:
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    index = build_index()
    OUTPUT_FILE.write_text(json.dumps(index, indent=2))
    print(f"Wrote metadata for {len(index['titles'])} titles to {OUTPUT_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
