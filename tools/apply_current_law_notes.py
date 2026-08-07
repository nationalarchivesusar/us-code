#!/usr/bin/env python3
"""Project USAR current-law transfer and supersession notes into title XML.

The repository intentionally preserves the OLRC baseline wording of a section unless
an enactment supplies a uniquely executable Code amendment. Some later USAR laws,
however, transfer functions or supersede procedures without literally striking every
older U.S. Code section that names the former agency or procedure. Readers need to
see those later enactments where they encounter the older text.

This tool reads legal-data/current-law-notes.json and inserts deterministic `rp-`
notes at the affected Code sections. The source manifest is the reviewable legal
mapping; this script contains no hard-coded substantive law.

The GitHub Pages workflow runs the projection after checkout and before the search
index/title chunks are built. Thus the published Code, citation pages, and keyword
search all consume the reconciled XML while the repository can continue to retain
its upstream OLRC baseline plus separately reviewable USAR overlays.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "legal-data" / "current-law-notes.json"
USLM_NS = "http://xml.house.gov/schemas/uslm/1.0"
NS = {"u": USLM_NS}
PARSER = etree.XMLParser(remove_blank_text=False, huge_tree=True, recover=False)


def q(name: str) -> str:
    return f"{{{USLM_NS}}}{name}"


def title_path(root: Path, title: str) -> Path:
    if not str(title).isdigit():
        raise ValueError(f"Unsupported title number {title!r}")
    return root / "usc" / f"usc{int(title):02d}.xml"


def section_identifier(title: str, section: str) -> str:
    return f"/us/usc/t{int(title)}/s{section}"


def note_style(topic: str) -> str:
    return "-uslm-lc:I85" if topic == "transfer" else "-uslm-lc:I74"


def normalized_text(node: etree._Element | None) -> str:
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def direct_paragraphs(note: etree._Element) -> list[str]:
    return [normalized_text(p) for p in note.findall(q("p"))]


def configure_note(note: etree._Element, spec: dict) -> None:
    note.set("id", spec["id"])
    note.set("topic", spec["topic"])
    note.set("style", note_style(spec["topic"]))
    note.attrib.pop("role", None)

    for child in list(note):
        note.remove(child)
    note.text = None

    heading = etree.SubElement(note, q("heading"))
    heading.set("class", "centered smallCaps")
    heading.text = spec["heading"]

    for paragraph in spec["paragraphs"]:
        p = etree.SubElement(note, q("p"))
        p.set("style", "-uslm-lc:I21")
        p.set("class", "indent0")
        p.text = paragraph


def verify_note(note: etree._Element, spec: dict) -> list[str]:
    problems: list[str] = []
    if note.get("topic") != spec["topic"]:
        problems.append(
            f"topic is {note.get('topic')!r}, expected {spec['topic']!r}"
        )
    heading = note.find(q("heading"))
    if normalized_text(heading) != " ".join(spec["heading"].split()):
        problems.append("heading differs from manifest")
    expected_paragraphs = [" ".join(p.split()) for p in spec["paragraphs"]]
    if direct_paragraphs(note) != expected_paragraphs:
        problems.append("paragraph text differs from manifest")
    return problems


def parse_document(raw: bytes) -> etree._ElementTree:
    # etree.parse, unlike fromstring, preserves processing instructions that
    # precede the root element (notably the OLRC xml-stylesheet instruction).
    return etree.parse(io.BytesIO(raw), PARSER)


def serialize(tree: etree._ElementTree, original: bytes) -> bytes:
    had_declaration = original.lstrip().startswith(b"<?xml")
    output = etree.tostring(
        tree,
        encoding="UTF-8",
        xml_declaration=had_declaration,
        pretty_print=False,
    )
    if original.endswith(b"\n") and not output.endswith(b"\n"):
        output += b"\n"
    return output


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0":
        raise ValueError("Unsupported current-law-notes schema version")
    notes = payload.get("notes")
    if not isinstance(notes, list) or not notes:
        raise ValueError("Manifest contains no notes")

    ids: set[str] = set()
    locations: set[tuple[str, str, str]] = set()
    for index, spec in enumerate(notes, start=1):
        required = {"id", "title", "section", "topic", "heading", "paragraphs"}
        missing = sorted(required - set(spec))
        if missing:
            raise ValueError(f"Manifest note {index} missing fields: {', '.join(missing)}")
        if not spec["id"].startswith("rp-"):
            raise ValueError(f"Manifest note {index} id must start with 'rp-'")
        if spec["id"] in ids:
            raise ValueError(f"Duplicate manifest id {spec['id']}")
        ids.add(spec["id"])
        if spec["topic"] not in {"transfer", "miscellaneous", "amendments"}:
            raise ValueError(f"Unsupported topic {spec['topic']!r} for {spec['id']}")
        if not isinstance(spec["paragraphs"], list) or not spec["paragraphs"]:
            raise ValueError(f"Manifest note {spec['id']} has no paragraph text")
        if any(not isinstance(p, str) or not p.strip() for p in spec["paragraphs"]):
            raise ValueError(f"Manifest note {spec['id']} contains an empty paragraph")
        location = (str(spec["title"]), str(spec["section"]), spec["id"])
        if location in locations:
            raise ValueError(f"Duplicate manifest location {location}")
        locations.add(location)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that the projected notes already exist and exactly match the manifest.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    manifest = args.manifest.resolve()
    payload = load_manifest(manifest)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for spec in payload["notes"]:
        grouped[str(spec["title"])].append(spec)

    parsed: dict[str, tuple[Path, bytes, etree._ElementTree]] = {}
    errors: list[str] = []
    inserted = 0
    updated = 0
    verified = 0

    # Parse and validate every affected title before writing any file.
    for title in sorted(grouped, key=lambda value: int(value)):
        path = title_path(root, title)
        if not path.is_file():
            errors.append(f"Title {title}: missing {path.relative_to(root)}")
            continue
        original = path.read_bytes()
        if original.startswith(b"version https://git-lfs.github.com/spec"):
            errors.append(f"Title {title}: {path.name} is an unresolved Git LFS pointer")
            continue
        try:
            tree = parse_document(original)
        except etree.XMLSyntaxError as exc:
            errors.append(f"Title {title}: XML parse failed: {exc}")
            continue
        parsed[title] = (path, original, tree)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for title in sorted(grouped, key=lambda value: int(value)):
        path, original, tree = parsed[title]
        for spec in grouped[title]:
            identifier = section_identifier(title, str(spec["section"]))
            sections = tree.xpath(
                "//u:section[@identifier=$identifier]",
                namespaces=NS,
                identifier=identifier,
            )
            if len(sections) != 1:
                errors.append(
                    f"{path.name}: expected exactly one section {identifier}, found {len(sections)}"
                )
                continue
            section = sections[0]

            all_with_id = tree.xpath("//*[@id=$id]", id=spec["id"])
            if len(all_with_id) > 1:
                errors.append(f"{path.name}: duplicate existing id {spec['id']}")
                continue
            existing = all_with_id[0] if all_with_id else None
            if existing is not None and existing.getparent() is not None:
                ancestor_sections = existing.xpath("ancestor::u:section[1]", namespaces=NS)
                if not ancestor_sections or ancestor_sections[0] is not section:
                    errors.append(
                        f"{path.name}: id {spec['id']} already exists outside target {identifier}"
                    )
                    continue

            if args.check:
                if existing is None:
                    errors.append(f"{path.name}: missing projected note {spec['id']} at {identifier}")
                    continue
                problems = verify_note(existing, spec)
                if problems:
                    errors.append(
                        f"{path.name}: {spec['id']}: " + "; ".join(problems)
                    )
                else:
                    verified += 1
                continue

            if existing is None:
                notes = section.find(q("notes"))
                if notes is None:
                    notes = etree.SubElement(section, q("notes"))
                    notes.set("type", "uscNote")
                note = etree.Element(q("note"))
                configure_note(note, spec)
                notes.insert(0, note)
                inserted += 1
            else:
                problems = verify_note(existing, spec)
                if problems:
                    configure_note(existing, spec)
                    updated += 1
                else:
                    verified += 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.check:
        print(f"Verified {verified} current-law note(s) across {len(grouped)} title(s).")
        return 0

    changed_files: list[str] = []
    for title in sorted(grouped, key=lambda value: int(value)):
        path, original, tree = parsed[title]
        projected = serialize(tree, original)
        # Strictly reparse the staged full document before replacing the build-workspace file.
        try:
            parse_document(projected)
        except etree.XMLSyntaxError as exc:
            print(f"ERROR: staged {path.name} is not well formed: {exc}", file=sys.stderr)
            return 1
        if projected != original:
            path.write_bytes(projected)
            changed_files.append(path.name)

    print(
        f"Projected {inserted} new and {updated} updated current-law note(s); "
        f"{verified} already current."
    )
    if changed_files:
        print("Changed build-workspace titles: " + ", ".join(changed_files))
    else:
        print("No title XML changes were necessary.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
