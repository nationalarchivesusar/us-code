#!/usr/bin/env python3
"""Deterministic checks for the chunked Title 42 website build.

Run after tools/build_title42_chunks.py and tools/build_index.py. Intended
for local verification and for the Pages workflow build step; exits
non-zero (with a clear message) on the first failed check.

Checks performed:
  1. The Title 42 manifest exists.
  2. Its reported section_count exceeds 8000.
  3. Every section file the manifest's tree references actually exists on
     disk (walking the whole tree, not just a sample).
  4. data/titles.json marks Title 42 as chunked and points at the manifest,
     never at usc/usc42.xml.
  5. assets/js/app.js contains no literal reference to "usc/usc42.xml" (the
     frontend must never be able to request the file the Pages workflow
     deletes before publishing).
  6. One representative Title 42 section (42 U.S.C. 1983) can be loaded
     from its chunk file and parses as well-formed XML with the expected
     identifier and heading.
  7. Manifest-index resolution: building the same index the frontend builds
     (identifier/number -> node) resolves 42 U.S.C. 1983 to a section node
     whose file exists -- a static proxy for "direct citation restoration
     works," since this script has no browser to drive.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "data" / "title-42" / "manifest.json"
TITLES_JSON = REPO_ROOT / "data" / "titles.json"
APP_JS = REPO_ROOT / "assets" / "js" / "app.js"
MIN_SECTION_COUNT = 8000


class CheckFailed(Exception):
    pass


def check_manifest_exists() -> dict:
    if not MANIFEST_PATH.exists():
        raise CheckFailed(
            f"{MANIFEST_PATH.relative_to(REPO_ROOT)} does not exist. "
            "Run: py -3 tools/build_title42_chunks.py"
        )
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def check_section_count(manifest: dict) -> int:
    count = manifest.get("section_count", 0)
    if count <= MIN_SECTION_COUNT:
        raise CheckFailed(
            f"Title 42 manifest reports only {count} sections; expected more than {MIN_SECTION_COUNT}."
        )
    return count


def walk_sections(node, out):
    if node.get("type") == "section":
        out.append(node)
    for child in node.get("children", []):
        walk_sections(child, out)


def check_all_section_files_exist(manifest: dict) -> list:
    sections = []
    walk_sections(manifest["root"], sections)
    missing = []
    for node in sections:
        rel = node.get("file")
        if not rel:
            missing.append((node.get("identifier"), "<no file field>"))
            continue
        if not (REPO_ROOT / rel).exists():
            missing.append((node.get("identifier"), rel))
    if missing:
        sample = "; ".join(f"{ident} -> {rel}" for ident, rel in missing[:10])
        raise CheckFailed(
            f"{len(missing)} manifest section file(s) are missing on disk. First few: {sample}"
        )
    if len(sections) != manifest.get("section_count"):
        raise CheckFailed(
            f"Manifest section_count ({manifest.get('section_count')}) does not match the "
            f"number of section nodes actually found in the tree ({len(sections)})."
        )
    return sections


def check_titles_json_chunked() -> dict:
    if not TITLES_JSON.exists():
        raise CheckFailed(
            f"{TITLES_JSON.relative_to(REPO_ROOT)} does not exist. Run: py -3 tools/build_index.py"
        )
    data = json.loads(TITLES_JSON.read_text(encoding="utf-8"))
    entry = next((t for t in data.get("titles", []) if t.get("number") == "42"), None)
    if entry is None:
        raise CheckFailed("Title 42 is missing from data/titles.json entirely.")
    if not entry.get("chunked"):
        raise CheckFailed(f"Title 42 entry in titles.json is not marked chunked: {entry}")
    if entry.get("file") == "usc/usc42.xml" or entry.get("file", "").endswith("usc42.xml"):
        raise CheckFailed(f"Title 42 entry still points at the source XML file: {entry}")
    if not entry.get("file", "").endswith("manifest.json"):
        raise CheckFailed(f"Title 42 entry's 'file' does not point at a manifest: {entry}")
    return entry


def check_frontend_never_fetches_source_xml() -> None:
    if not APP_JS.exists():
        raise CheckFailed(f"{APP_JS.relative_to(REPO_ROOT)} does not exist.")
    source = APP_JS.read_text(encoding="utf-8")
    if re.search(r"""["'`][^"'`]*usc42\.xml["'`]""", source):
        raise CheckFailed(
            "assets/js/app.js contains a literal reference to a usc42.xml path. "
            "The frontend must only ever use metadata.file (the manifest) for a chunked title."
        )
    if "fetchChunkManifest" not in source or "fetchChunkSection" not in source:
        raise CheckFailed(
            "assets/js/app.js is missing the chunked-title fetch helpers "
            "(fetchChunkManifest / fetchChunkSection)."
        )


def check_representative_section_loads(manifest: dict) -> None:
    sections = []
    walk_sections(manifest["root"], sections)
    target = next((n for n in sections if n.get("identifier") == "/us/usc/t42/s1983"), None)
    if target is None:
        raise CheckFailed("42 U.S.C. 1983 is not present in the Title 42 manifest tree.")
    chunk_path = REPO_ROOT / target["file"]
    if not chunk_path.exists():
        raise CheckFailed(f"Chunk file for 42 U.S.C. 1983 is missing: {target['file']}")

    from lxml import etree

    parser = etree.XMLParser(recover=False)
    root = etree.parse(str(chunk_path), parser).getroot()
    identifier = root.get("identifier")
    if identifier != "/us/usc/t42/s1983":
        raise CheckFailed(f"Chunk file identifier mismatch: expected /us/usc/t42/s1983, got {identifier}")
    ns = "{http://xml.house.gov/schemas/uslm/1.0}"
    heading = root.find(f"{ns}heading")
    if heading is None or "deprivation of rights" not in "".join(heading.itertext()).lower():
        raise CheckFailed("Chunk file for 42 U.S.C. 1983 does not contain the expected heading text.")


def check_citation_index_resolves(manifest: dict) -> None:
    """Mirror the frontend's buildIndex()/sectionKey() logic well enough to
    prove that citation-based lookup ("42 U.S.C. 1983" / /cite/42/1983/)
    resolves to a real, loadable chunk -- without needing a browser."""

    def section_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    index = {}

    def build_index(node, path):
        path = path + [node]
        if node.get("identifier"):
            index[node["identifier"]] = path
        if node.get("type") == "section" and node.get("number"):
            index[section_key(node["number"])] = path
        for child in node.get("children", []):
            build_index(child, path)

    build_index(manifest["root"], [])

    path = index.get(section_key("1983")) or index.get("/us/usc/t42/s1983")
    if path is None:
        raise CheckFailed("Citation index does not resolve section number '1983' for Title 42.")
    section_node = path[-1]
    if section_node.get("type") != "section" or not (REPO_ROOT / section_node["file"]).exists():
        raise CheckFailed("Citation index resolved to a node with no loadable chunk file.")


CHECKS = [
    ("Manifest exists", check_manifest_exists, True),
    ("Section count exceeds threshold", check_section_count, False),
    ("Every manifest section file exists on disk", check_all_section_files_exist, False),
    ("data/titles.json marks Title 42 as chunked", check_titles_json_chunked, False),
    ("Frontend never fetches usc/usc42.xml", check_frontend_never_fetches_source_xml, False),
    ("Representative section (42 U.S.C. 1983) loads from its chunk", check_representative_section_loads, False),
    ("Citation index resolves 42 U.S.C. 1983 to a loadable chunk", check_citation_index_resolves, False),
]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    manifest = None
    failures = 0
    for label, fn, produces_manifest in CHECKS:
        try:
            if fn is check_manifest_exists:
                manifest = fn()
            elif fn in (check_section_count, check_all_section_files_exist,
                        check_representative_section_loads, check_citation_index_resolves):
                fn(manifest)
            else:
                fn()
            print(f"PASS: {label}")
        except CheckFailed as exc:
            print(f"FAIL: {label}\n      {exc}")
            failures += 1
        except Exception as exc:  # pragma: no cover - defensive
            print(f"ERROR: {label}\n      {exc!r}")
            failures += 1

    print()
    if failures:
        print(f"{failures} Title 42 build check(s) failed.")
        return 1
    print("All Title 42 build checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
