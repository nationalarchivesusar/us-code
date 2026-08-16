#!/usr/bin/env python3
"""Build verified baseline-to-current U.S. Code section comparisons.

The public-law index tells us which sections have codification history. This
builder compares those sections against a fixed repository codification
baseline and publishes only verified textual differences. It deliberately does
not infer intermediate per-enactment versions.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
USC_DIR = ROOT / "usc"
PUBLIC_LAWS = ROOT / "data" / "public-laws.json"
OUTPUT_DIR = ROOT / "data" / "section-history"
DEFAULT_BASELINE = "00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46"
SCHEMA_VERSION = "1.0"

USLM = "http://xml.house.gov/schemas/uslm/1.0"
Q = lambda name: f"{{{USLM}}}{name}"

SECTION_IDENTIFIER_RE = re.compile(
    r"^/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/]+)$",
    re.IGNORECASE,
)
TOKEN_RE = re.compile(r"\S+\s*", re.UNICODE)
SKIP_SECTION_CHILDREN = {"num", "heading", "sourceCredit", "notes", "toc"}


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def natural_title_key(value: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d+)([A-Za-z]?)", value)
    if not match:
        return (10**9, value.lower())
    return (int(match.group(1)), match.group(2).lower())


def title_filename(title: str) -> str:
    match = re.fullmatch(r"(\d+)([A-Za-z]?)", str(title))
    if not match:
        raise ValueError(f"Unsupported U.S. Code title number: {title!r}")
    number, suffix = match.groups()
    return f"usc{int(number):02d}{suffix.lower()}.xml"


def section_key(title: str, section: str) -> str:
    return f"{title.lower()}:{section.lower()}"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def public_law_targets(payload: dict) -> dict[str, set[str]]:
    """Return title -> section targets supported by the published codification index."""
    targets: dict[str, set[str]] = defaultdict(set)
    for law in payload.get("laws", []):
        candidates = list(law.get("targets") or [])
        for action in law.get("actions") or []:
            candidates.extend(action.get("targets") or [])
            if action.get("target"):
                candidates.append(action["target"])
        for target in candidates:
            title = str(target.get("title") or "").lstrip("0") or "0"
            section = str(target.get("section") or "").strip()
            if title and section:
                targets[title].add(section)
    return targets


def direct_text(element, name: str) -> str:
    child = element.find(Q(name))
    return clean("".join(child.itertext())) if child is not None else ""


def operative_element_text(element) -> str:
    """Flatten one operative block while retaining readable subdivision spacing."""
    local = etree.QName(element).localname
    if local == "content":
        pieces = [operative_element_text(child) for child in element]
        pieces = [piece for piece in pieces if piece]
        return " ".join(pieces) if pieces else clean("".join(element.itertext()))

    structured = {
        "subsection",
        "paragraph",
        "subparagraph",
        "clause",
        "subclause",
        "item",
    }
    if local not in structured:
        return clean("".join(element.itertext()))

    pieces: list[str] = []
    for name in ("num", "heading"):
        value = direct_text(element, name)
        if value:
            pieces.append(value)
    for child in element:
        child_local = etree.QName(child).localname
        if child_local in {"num", "heading", "sourceCredit", "notes"}:
            continue
        value = operative_element_text(child)
        if value:
            pieces.append(value)
    return " ".join(pieces).strip()


def statutory_body(section) -> str:
    """Flatten operative section text while excluding source/history metadata."""
    blocks: list[str] = []
    for child in section:
        local = etree.QName(child).localname
        if local in SKIP_SECTION_CHILDREN:
            continue
        if local == "content":
            content_children = list(child)
            if content_children:
                for item in content_children:
                    text = operative_element_text(item)
                    if text:
                        blocks.append(text)
            else:
                text = operative_element_text(child)
                if text:
                    blocks.append(text)
            continue
        text = operative_element_text(child)
        if text:
            blocks.append(text)
    return "\n\n".join(blocks).strip()


def section_record(section, *, expected_title: str | None = None) -> dict | None:
    identifier = section.get("identifier", "")
    match = SECTION_IDENTIFIER_RE.fullmatch(identifier)
    if not match:
        return None
    title = match.group("title").lstrip("0") or "0"
    if expected_title and title.lower() != expected_title.lower():
        return None
    number = match.group("section")
    heading = direct_text(section, "heading")
    body = statutory_body(section)
    display = f"§ {number}. {heading}".strip()
    if body:
        display += f"\n\n{body}"
    return {
        "title": title,
        "section": number,
        "identifier": identifier,
        "heading": heading,
        "body": body,
        "text": display,
    }


def extract_sections(xml_bytes: bytes, *, expected_title: str | None = None) -> dict[str, dict]:
    parser = etree.XMLParser(
        huge_tree=True,
        recover=False,
        remove_blank_text=False,
        resolve_entities=False,
    )
    root = etree.fromstring(xml_bytes, parser=parser)
    records: dict[str, dict] = {}
    for section in root.xpath("//*[local-name()='section'][@identifier]"):
        record = section_record(section, expected_title=expected_title)
        if not record:
            continue
        records[record["section"].lower()] = record
    return records


def git_output(args: list[str], *, input_bytes: bytes | None = None) -> bytes:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{' '.join(args)} failed: {stderr}")
    return completed.stdout


def baseline_file_bytes(baseline: str, relative_path: str) -> bytes:
    raw = git_output(["git", "show", f"{baseline}:{relative_path}"])
    if raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
        # The workflow fetches the baseline Title 42 LFS object before this
        # builder runs. Smudge materializes that object from the local LFS cache.
        raw = git_output(["git", "lfs", "smudge"], input_bytes=raw)
        if raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise RuntimeError(f"Baseline LFS object is unavailable for {relative_path}")
    return raw


def token_diff(before: str, after: str) -> list[dict[str, str]]:
    before_tokens = TOKEN_RE.findall(before)
    after_tokens = TOKEN_RE.findall(after)
    matcher = difflib.SequenceMatcher(None, before_tokens, after_tokens, autojunk=False)
    operations: list[dict[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            pieces = [("equal", "".join(before_tokens[i1:i2]))]
        elif tag == "delete":
            pieces = [("delete", "".join(before_tokens[i1:i2]))]
        elif tag == "insert":
            pieces = [("insert", "".join(after_tokens[j1:j2]))]
        else:
            pieces = [
                ("delete", "".join(before_tokens[i1:i2])),
                ("insert", "".join(after_tokens[j1:j2])),
            ]
        for operation, text in pieces:
            if not text:
                continue
            if operations and operations[-1]["op"] == operation:
                operations[-1]["text"] += text
            else:
                operations.append({"op": operation, "text": text})
    return operations


def reconstruct_diff(operations: list[dict[str, str]], side: str) -> str:
    if side not in {"baseline", "current"}:
        raise ValueError(side)
    allowed = {"equal", "delete"} if side == "baseline" else {"equal", "insert"}
    return "".join(item["text"] for item in operations if item["op"] in allowed)


def comparison_record(
    title: str,
    section: str,
    baseline: dict | None,
    current: dict | None,
    baseline_commit: str,
) -> dict | None:
    if baseline is None and current is None:
        return None

    if baseline is None:
        status = "added"
    elif current is None:
        status = "removed"
    elif baseline["text"] == current["text"]:
        return None
    else:
        status = "amended"

    before_text = baseline["text"] if baseline else ""
    after_text = current["text"] if current else ""
    operations = token_diff(before_text, after_text)

    if reconstruct_diff(operations, "baseline") != before_text:
        raise RuntimeError(f"Diff baseline reconstruction failed for {title} U.S.C. § {section}")
    if reconstruct_diff(operations, "current") != after_text:
        raise RuntimeError(f"Diff current reconstruction failed for {title} U.S.C. § {section}")

    return {
        "schema_version": SCHEMA_VERSION,
        "title": title,
        "section": section,
        "citation": f"{title} U.S.C. § {section}",
        "status": status,
        "comparison_scope": "repository-baseline-to-current",
        "baseline": {
            "commit": baseline_commit,
            "present": baseline is not None,
            "heading": baseline["heading"] if baseline else None,
            "text": before_text if baseline else None,
            "sha256": sha256_text(before_text) if baseline else None,
        },
        "current": {
            "present": current is not None,
            "heading": current["heading"] if current else None,
            "text": after_text if current else None,
            "sha256": sha256_text(after_text) if current else None,
        },
        "diff": operations,
    }


def baseline_metadata(baseline: str) -> dict:
    try:
        committed_at = git_output(["git", "show", "-s", "--format=%cI", baseline]).decode("utf-8").strip()
    except RuntimeError:
        committed_at = None
    return {
        "commit": baseline,
        "committed_at": committed_at or None,
        "label": "Codification repository baseline",
    }


def build(*, baseline: str, output_dir: Path, public_laws_path: Path) -> dict:
    payload = load_json(public_laws_path)
    targets = public_law_targets(payload)
    if not targets:
        raise RuntimeError("Public-law index contains no section targets.")

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_sections: dict[str, dict] = {}
    counts = Counter()
    unavailable_titles: dict[str, str] = {}

    for title in sorted(targets, key=natural_title_key):
        filename = title_filename(title)
        current_path = USC_DIR / filename
        if not current_path.is_file():
            unavailable_titles[title] = f"Current source missing: usc/{filename}"
            continue

        try:
            current_sections = extract_sections(current_path.read_bytes(), expected_title=title)
            baseline_sections = extract_sections(
                baseline_file_bytes(baseline, f"usc/{filename}"), expected_title=title
            )
        except (RuntimeError, etree.XMLSyntaxError) as exc:
            unavailable_titles[title] = str(exc)
            continue

        for requested_section in sorted(targets[title], key=lambda value: value.lower()):
            baseline_section = baseline_sections.get(requested_section.lower())
            current_section = current_sections.get(requested_section.lower())
            record = comparison_record(
                title,
                requested_section,
                baseline_section,
                current_section,
                baseline,
            )
            counts["tracked_targets"] += 1
            if record is None:
                counts["unchanged"] += 1
                continue

            status = record["status"]
            counts[status] += 1
            counts["changed"] += 1

            relative_path = Path("data") / "section-history" / title.lower() / f"{requested_section}.json"
            destination = ROOT / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            manifest_sections[section_key(title, requested_section)] = {
                "title": title,
                "section": requested_section,
                "citation": record["citation"],
                "status": status,
                "path": relative_path.as_posix(),
            }

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "comparison_scope": "repository-baseline-to-current",
        "baseline": baseline_metadata(baseline),
        "source_index": public_laws_path.relative_to(ROOT).as_posix(),
        "counts": {
            "target_titles": len(targets),
            "tracked_targets": counts["tracked_targets"],
            "changed": counts["changed"],
            "amended": counts["amended"],
            "added": counts["added"],
            "removed": counts["removed"],
            "unchanged": counts["unchanged"],
            "unavailable_titles": len(unavailable_titles),
        },
        "unavailable_titles": unavailable_titles,
        "sections": dict(sorted(manifest_sections.items())),
        "limitations": [
            "Comparisons show the fixed repository codification baseline against the current published section.",
            "Public Law records identify enactments associated with a section but are not represented as reconstructed intermediate text versions.",
            "Source credits, statutory notes, and historical notes are excluded from the substantive text comparison.",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default=DEFAULT_BASELINE)
    parser.add_argument("--output", default=str(OUTPUT_DIR))
    parser.add_argument("--public-laws", default=str(PUBLIC_LAWS))
    args = parser.parse_args()

    manifest = build(
        baseline=args.baseline,
        output_dir=Path(args.output).resolve(),
        public_laws_path=Path(args.public_laws).resolve(),
    )
    counts = manifest["counts"]
    print(
        "Built verified section history: "
        f"{counts['changed']} changed "
        f"({counts['amended']} amended, {counts['added']} added, {counts['removed']} removed); "
        f"{counts['unchanged']} tracked targets unchanged."
    )
    if manifest["unavailable_titles"]:
        print(
            "History unavailable for title(s): "
            + ", ".join(sorted(manifest["unavailable_titles"], key=natural_title_key))
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
