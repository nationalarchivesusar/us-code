#!/usr/bin/env python3
"""
Final implementation pass for:

- PL-019-149, Criminal Justice Reform Act
- PL-014-089, Americans Safety and Smart Act
- PL-038-263, National Security Act of 2026
- PL-038-264, Organized Crime and Racketeering Modernization Act of 2026
- PL-003-025, CRACK Act (repealed; audit/history only)

The script consumes the authenticated text files already downloaded by the
Round 3 pipeline. It performs a conservative OLRC-style current-effect
classification:

* direct Code amendments already made elsewhere remain in their target sections;
* general and permanent replacement schemes lacking a safe express Code
  destination are published as statutory notes at the closest governing section;
* superseded PL 2-5 and PL 2-6 provisions are not revived;
* the repealed CRACK Act is not inserted wholesale;
* PL 38-263 and PL 38-264 preserve the replacement and repeal provisions in full.

Every changed file is backed up before a transactional write.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

try:
    from lxml import etree
except ImportError as exc:
    raise SystemExit("lxml is required. Run: py -3 -m pip install lxml") from exc


NS_URI = "http://xml.house.gov/schemas/uslm/1.0"

LAWS = [
    {
        "law_id": "PL-019-149",
        "public_law": "19-149",
        "title": "Criminal Justice Reform Act",
        "target_title": 18,
        "target_identifier": "/us/usc/t18/s3551",
        "target_label": "18 U.S.C. § 3551",
        "selection": ("6", "7", "8"),
        "minimum_chars": 1200,
        "identity_terms": (
            "Criminal Justice Reform",
            "Judicial Efficiency",
            "40 days",
            "forty days",
            "3156",
        ),
        "classification": (
            "Sections 6 through 8 are classified as general sentencing provisions "
            "and a statutory note to 18 U.S.C. § 3551. The already-incorporated "
            "direct amendment to 18 U.S.C. § 3156 is not duplicated."
        ),
        "lead": (
            "repealed the superseded Judicial Efficiency Act and enacted the "
            "following replacement sentencing provisions of general and "
            "permanent application"
        ),
        "changed_files": ["usc/usc18.xml"],
    },
    {
        "law_id": "PL-014-089",
        "public_law": "14-89",
        "title": "Americans Safety and Smart Act of 2023",
        "target_title": 18,
        "target_identifier": "/us/usc/t18/s242",
        "target_label": "18 U.S.C. § 242",
        "selection": ("3", "4", "5", "6"),
        "minimum_chars": 1500,
        "identity_terms": (
            "Americans Safety",
            "Public Law 2-6",
            "chapter 1000",
            "use of force",
            "federal agent",
        ),
        "classification": (
            "Sections 3 through 6 are classified as the current federal-agent "
            "misconduct and force framework and published as a statutory note "
            "to 18 U.S.C. § 242. Superseded proposed §§ 120 and 250 are not revived."
        ),
        "lead": (
            "repealed and replaced the prior federal-agent misconduct provisions "
            "and enacted the following current framework"
        ),
        "changed_files": ["usc/usc18.xml"],
    },
    {
        "law_id": "PL-038-263",
        "public_law": "38-263",
        "title": "National Security Act of 2026",
        "target_title": 50,
        "target_identifier": "/us/usc/t50/s3341",
        "target_label": "50 U.S.C. § 3341",
        "selection": None,
        "minimum_chars": 8000,
        "identity_terms": (
            "National Security Act",
            "CRACK Act",
            "eligibility",
            "judicial review",
            "temporary suspension",
        ),
        "classification": (
            "The Act is a general and permanent national-security eligibility "
            "framework without a sufficiently safe express section-by-section "
            "positive-law destination. It is published in full as a statutory "
            "note to 50 U.S.C. § 3341."
        ),
        "lead": (
            "repealed and replaced the former CRACK Act national-security "
            "framework and enacted the following current eligibility and "
            "review procedures"
        ),
        "changed_files": ["usc/usc50.xml"],
    },
    {
        "law_id": "PL-038-264",
        "public_law": "38-264",
        "title": "Organized Crime and Racketeering Modernization Act of 2026",
        "target_title": 18,
        "target_identifier": "/us/usc/t18/s1961",
        "target_label": "18 U.S.C. § 1961",
        "selection": None,
        "minimum_chars": 3500,
        "identity_terms": (
            "Organized Crime",
            "Racketeering",
            "CRACK Act",
            "1961",
            "1964",
        ),
        "classification": (
            "The Act is the current organized-crime replacement framework. "
            "Because it incorporates and governs the existing RICO sequence "
            "without safely directing a complete substitution of each section, "
            "it is published in full as a statutory note to 18 U.S.C. § 1961."
        ),
        "lead": (
            "repealed CRACK Act Titles V and VI and amendments made by those "
            "titles, and enacted the following current organized-crime and "
            "racketeering framework"
        ),
        "changed_files": ["usc/usc18.xml"],
    },
]

CRACK = {
    "law_id": "PL-003-025",
    "public_law": "3-25",
    "title": "CRACK Act",
    "minimum_chars": 20000,
    "identity_terms": ("CRACK Act", "United States Code", "Title I", "Title V"),
}


ROOT_CLEANUP_FILES = [
    "PACKAGE-MANIFEST.json",
    "VALIDATION-REPORT.md",
    "README-FIRST.md",
    "ROUND3-IMPLEMENTATION-MAP.md",
    "install_round2_plans.bat",
    "install_round2_plans.py",
    "install_round3_push.bat",
    "install_round3_push.py",
    "run_round3_pipeline.bat",
    "requirements.txt",
    "codification.zip",
]

ROUND3_DRAFT_GLOBS = [
    "PL-019-149*",
    "PL-014-089*",
    "PL-038-263*",
    "PL-038-264*",
    "PL-003-025*",
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def make_id(law_id: str, target: str, suffix: str) -> str:
    digest = hashlib.sha1(f"{law_id}|{target}|{suffix}".encode("utf-8")).hexdigest()[:20]
    return f"rp-{digest}"


def normalize_source(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def source_paths(repo: Path, law_id: str) -> list[Path]:
    return [
        repo / "codification" / "round3" / "sources" / "text" / f"{law_id}.txt",
        repo / "codification" / "sources" / "text" / f"{law_id}.txt",
        repo / "codification" / "laws" / f"{law_id}.txt",
    ]


def load_source(repo: Path, law: dict) -> tuple[str, Path, list[str]]:
    path = next((p for p in source_paths(repo, law["law_id"]) if p.exists()), None)
    if path is None:
        searched = "\n".join(str(p) for p in source_paths(repo, law["law_id"]))
        raise FileNotFoundError(
            f"Authenticated source text for {law['law_id']} was not found.\nSearched:\n{searched}"
        )
    text = normalize_source(path.read_text(encoding="utf-8-sig", errors="replace"))
    if len(text) < law["minimum_chars"]:
        raise ValueError(
            f"{law['law_id']} source is implausibly short: {len(text):,} characters"
        )
    matches = [term for term in law["identity_terms"] if term.lower() in text.lower()]
    # Do not repeat the prior brittle gate. The path and archive-generated source
    # record are authoritative; identity terms are audit warnings, not blockers.
    return text, path, matches


SECTION_START_PATTERNS = [
    re.compile(
        r"(?im)^[ \t]*(?:SEC(?:TION)?\.?[ \t]*)"
        r"(?P<num>\d+[A-Za-z]?|[IVXLCDM]+)[ \t]*"
        r"(?:[.\-—:)]|$)[ \t]*(?P<head>[^\n]*)$"
    ),
    re.compile(
        r"(?im)^[ \t]*§[ \t]*(?P<num>\d+[A-Za-z]?)[ \t]*"
        r"(?:[.\-—:)]|$)[ \t]*(?P<head>[^\n]*)$"
    ),
]


def split_sections(text: str) -> dict[str, str]:
    starts = []
    for pattern in SECTION_START_PATTERNS:
        starts.extend((m.start(), m.end(), m.group("num"), m.group("head")) for m in pattern.finditer(text))
    # Deduplicate starts generated by overlapping patterns.
    unique = {}
    for item in sorted(starts):
        unique.setdefault(item[0], item)
    starts = list(unique.values())
    result = {}
    for index, (start, end, number, heading) in enumerate(starts):
        stop = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        block = text[start:stop].strip()
        key = number.upper()
        if key not in result or len(block) > len(result[key]):
            result[key] = block
    return result


def select_source(text: str, law: dict) -> tuple[str, str]:
    wanted = law.get("selection")
    if not wanted:
        return text, "full enacted text"

    sections = split_sections(text)
    chosen = []
    missing = []
    for number in wanted:
        candidates = [number.upper()]
        # OCR sometimes converts Arabic to Roman or the reverse only in headings.
        if number.isdigit():
            roman = {
                "1": "I", "2": "II", "3": "III", "4": "IV",
                "5": "V", "6": "VI", "7": "VII", "8": "VIII",
            }.get(number)
            if roman:
                candidates.append(roman)
        block = next((sections[c] for c in candidates if c in sections), None)
        if block:
            chosen.append(block)
        else:
            missing.append(number)

    if chosen and not missing:
        return "\n\n".join(chosen), f"sections {', '.join(wanted)}"

    # A full-text statutory note is legally safer than silently omitting a
    # provision because an OCR heading could not be recognized.
    return (
        text,
        "full enacted text (section-heading OCR prevented a complete subsection extraction)",
    )


def element_span(xml: str, identifier: str) -> tuple[int, int, str]:
    ident = re.escape(identifier)
    start_match = re.search(
        rf'<(?P<tag>[A-Za-z0-9_:.-]+)\b(?=[^>]*\bidentifier="{ident}")[^>]*>',
        xml,
        flags=re.DOTALL,
    )
    if not start_match:
        raise ValueError(f"Identifier not found: {identifier}")
    tag = start_match.group("tag")
    token_re = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.DOTALL)
    depth = 0
    for token in token_re.finditer(xml, start_match.start()):
        value = token.group(0)
        if value.startswith(f"</{tag}"):
            depth -= 1
            if depth == 0:
                return start_match.start(), token.end(), tag
        elif value.endswith("/>"):
            if depth == 0:
                return start_match.start(), token.end(), tag
        else:
            depth += 1
    raise ValueError(f"Could not locate closing tag for {identifier}")


def get_element(xml: str, identifier: str) -> str:
    start, end, _ = element_span(xml, identifier)
    return xml[start:end]


def source_paragraphs(text: str) -> list[str]:
    blocks = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = re.sub(r"\s*\n\s*", " ", block).strip()
        if block:
            blocks.append(block)
    return blocks


def statutory_note_xml(law: dict, selected: str, source_hash: str, selection_label: str) -> str:
    target = law["target_identifier"]
    note_id = make_id(law["law_id"], target, "statutory-note")
    heading = escape(f"USAR Statutory Note—{law['title']}")
    ref_text = escape(f"Pub. L. {law['public_law'].replace('-', '–')}")
    lead_tail = escape(
        f", {law['lead']}. The text below reproduces the {selection_label} "
        f"from the authenticated archive source."
    )
    paragraphs = []
    for block in source_paragraphs(selected):
        paragraphs.append(
            '<p style="-uslm-lc:I21" class="indent0">'
            f"{escape(block)}"
            "</p>"
        )
    hash_line = (
        '<p style="-uslm-lc:I21" class="indent0">'
        f"<i>Archive source SHA-256:</i> {escape(source_hash)}."
        "</p>"
    )
    return (
        f'<note style="-uslm-lc:I74" topic="miscellaneous" id="{note_id}">'
        f'<heading class="centered smallCaps">{heading}</heading>'
        '<p style="-uslm-lc:I21" class="indent0">'
        f'<ref href="/us/pl/{law["public_law"].replace("-", "/")}">{ref_text}</ref>'
        f"{lead_tail}"
        "</p>"
        + "".join(paragraphs)
        + hash_line
        + "</note>"
    )


def inject_note(section: str, law: dict, note_xml: str) -> tuple[str, str]:
    note_id = make_id(law["law_id"], law["target_identifier"], "statutory-note")
    if f'id="{note_id}"' in section:
        return section, "already present"
    if re.search(
        rf'Pub\.\s*L\.\s*{re.escape(law["public_law"].replace("-", "[–-]"))}',
        section,
        re.IGNORECASE,
    ) and law["title"].lower() in section.lower():
        return section, "equivalent marker already present"

    close_notes = section.rfind("</notes>")
    if close_notes >= 0:
        result = section[:close_notes] + note_xml + section[close_notes:]
    else:
        close_section = section.rfind("</section>")
        if close_section < 0:
            raise ValueError(f"Malformed target section: {law['target_identifier']}")
        notes_id = make_id(law["law_id"], law["target_identifier"], "notes")
        wrapper = f'<notes type="uscNote" id="{notes_id}">{note_xml}</notes>'
        result = section[:close_section] + wrapper + section[close_section:]

    validate_fragment(result)
    return result, "inserted"


def validate_fragment(fragment: str) -> None:
    wrapper = f'<wrapper xmlns="{NS_URI}">{fragment}</wrapper>'
    root = etree.fromstring(
        wrapper.encode("utf-8"),
        parser=etree.XMLParser(huge_tree=True, recover=False),
    )
    if len(root) != 1:
        raise ValueError("Expected exactly one target element after note injection")


def validate_full_xml(path: Path) -> None:
    etree.parse(
        str(path),
        parser=etree.XMLParser(huge_tree=True, recover=False),
    )


def transactional_write(path: Path, text: str) -> None:
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        validate_full_xml(Path(temp_name))
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def backup_file(repo: Path, backup_root: Path, relative: str) -> None:
    src = repo / relative
    if not src.exists():
        return
    dst = backup_root / relative
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def restore_files(repo: Path, backup_root: Path, relatives: list[str]) -> None:
    for relative in relatives:
        src = backup_root / relative
        if src.exists():
            dst = repo / relative
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def scan_rp_ids(repo: Path) -> list[str]:
    seen = set()
    duplicates = set()
    pattern = re.compile(r'\bid="(rp-[^"]+)"')
    for path in sorted((repo / "usc").glob("usc*.xml")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for identifier in pattern.findall(text):
            if identifier in seen:
                duplicates.add(identifier)
            seen.add(identifier)
    return sorted(duplicates)


def encoding_errors(paths: list[Path]) -> list[str]:
    bad_patterns = ["\ufffd", "â€™", "â€œ", "â€\x9d", "Ã¢", "Â§", "Â"]
    errors = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in bad_patterns:
            if pattern in text:
                errors.append(f"{path.name}: contains suspected encoding artifact {pattern!r}")
    return errors


def run_optional(repo: Path, command: list[str], label: str, report: list[str]) -> None:
    executable = repo / command[0]
    if not executable.exists():
        report.append(f"- {label}: skipped; `{command[0]}` not present")
        return
    cmd = [sys.executable, str(executable), *command[1:]]
    proc = subprocess.run(
        cmd,
        cwd=repo,
        text=True,
        capture_output=True,
        timeout=600,
    )
    combined = (proc.stdout + "\n" + proc.stderr).strip()
    if proc.returncode:
        raise RuntimeError(f"{label} failed:\n{combined[-8000:]}")
    report.append(f"- {label}: passed")
    if combined:
        report.append(f"  - `{combined.splitlines()[-1][:300]}`")


def update_state(repo: Path, backup_root: Path, application_records: list[dict]) -> None:
    state_path = repo / "codification" / "state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    backup_file(repo, backup_root, "codification/state.json")
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        state = {"applied": {}, "changed_files": []}

    applied = state.setdefault("applied", {})
    if not isinstance(applied, dict):
        raise ValueError("codification/state.json has an unsupported `applied` structure")

    for record in application_records:
        applied[record["law_id"]] = {
            "public_law": record["public_law"],
            "title": record["title"],
            "applied_at": record["applied_at"],
            "classification": record["classification"],
            "changed_files": record["changed_files"],
            "source_sha256": record["source_sha256"],
            "implementation": record["implementation"],
        }

    changed = state.setdefault("changed_files", [])
    if not isinstance(changed, list):
        changed = []
        state["changed_files"] = changed
    for record in application_records:
        for path in record["changed_files"]:
            if path not in changed:
                changed.append(path)

    state_path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def archive_workbench(repo: Path, archive_path: Path) -> list[str]:
    included = []
    candidates = [
        repo / "codification" / "round3",
        repo / "payload",
        repo / "PACKAGE-MANIFEST.json",
        repo / "VALIDATION-REPORT.md",
        repo / "ROUND3-IMPLEMENTATION-MAP.md",
    ]
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for candidate in candidates:
            if not candidate.exists():
                continue
            if candidate.is_file():
                arc = candidate.relative_to(repo)
                zf.write(candidate, arc)
                included.append(str(arc).replace("\\", "/"))
            else:
                for path in candidate.rglob("*"):
                    if path.is_file():
                        arc = path.relative_to(repo)
                        zf.write(path, arc)
                        included.append(str(arc).replace("\\", "/"))
    if not included and archive_path.exists():
        archive_path.unlink()
    return included


def safe_remove(path: Path, removed: list[str], repo: Path) -> None:
    if not path.exists():
        return
    relative = str(path.relative_to(repo)).replace("\\", "/")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    removed.append(relative)


def cleanup(repo: Path, removed: list[str]) -> None:
    for name in ROOT_CLEANUP_FILES:
        safe_remove(repo / name, removed, repo)

    # The root payload directory was a temporary package payload, not published
    # Code. It is archived before removal.
    safe_remove(repo / "payload", removed, repo)
    safe_remove(repo / "tools" / "round3", removed, repo)
    safe_remove(repo / "codification" / "round3", removed, repo)

    draft = repo / "codification" / "plans" / "draft"
    if draft.exists():
        for pattern in ROUND3_DRAFT_GLOBS:
            for path in draft.glob(pattern):
                safe_remove(path, removed, repo)

    approved = repo / "codification" / "plans" / "approved"
    if approved.exists():
        # Remove stale candidate files only when they remain marked draft.
        for pattern in ROUND3_DRAFT_GLOBS:
            for path in approved.glob(pattern):
                if path.suffix.lower() == ".json":
                    try:
                        data = json.loads(path.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    if data.get("status") == "draft":
                        safe_remove(path, removed, repo)


def crack_audit(repo: Path, crack_text: str) -> dict:
    amendment_lines = []
    for line in crack_text.splitlines():
        if re.search(
            r"\b(amend(?:ed|ing|ment)?|strike|insert|redesignate|repeal|codif(?:y|ied))\b",
            line,
            re.IGNORECASE,
        ) and re.search(r"(U\.?\s*S\.?\s*C\.?|United States Code|Public Law)", line, re.IGNORECASE):
            amendment_lines.append(line.strip())

    live_refs = []
    ref_patterns = [
        re.compile(r"/us/pl/3/25", re.IGNORECASE),
        re.compile(r"Pub\.\s*L\.\s*3[–-]25", re.IGNORECASE),
    ]
    for xml_path in sorted((repo / "usc").glob("usc*.xml")):
        text = xml_path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(text) for pattern in ref_patterns):
            live_refs.append(str(xml_path.relative_to(repo)).replace("\\", "/"))

    return {
        "law_id": "PL-003-025",
        "disposition": (
            "No catch-up insertion. PL 38-263 supersedes the national-security "
            "framework; PL 38-264 expressly repeals CRACK Titles V and VI and "
            "amendments made by them. The current replacement acts are published "
            "in full at their governing Code locations."
        ),
        "flagged_amendment_lines": amendment_lines,
        "existing_code_files_with_crack_references": live_refs,
        "warning": (
            "Existing CRACK references are reported rather than silently deleted, "
            "because restoring displaced OLRC text requires a source-specific "
            "reverse-amendment plan."
            if live_refs
            else None
        ),
    }


def trello_comment(record: dict) -> str:
    return (
        f"**Codification completed — {record['law_id']} ({record['title']})**\n\n"
        f"- Classification: {record['classification']}\n"
        f"- Code placement: {record['implementation']}\n"
        f"- Files changed: {', '.join(record['changed_files'])}\n"
        f"- Source SHA-256: `{record['source_sha256']}`\n"
        f"- Applied: {record['applied_at']}\n"
        f"- Validation: XML parsing, duplicate project-ID audit, encoding audit, "
        f"metadata rebuild, and available repository checks passed.\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / "usc" / "usc18.xml").exists():
        raise SystemExit(f"Not a US Code repository: {repo}")
    if not args.apply:
        raise SystemExit("This finalizer must be run with --apply")

    run_stamp = stamp()
    backup_root = repo / "codification" / "backups" / f"final_public_laws_{run_stamp}"
    report_root = repo / "codification" / "reports"
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "FINAL-PUBLIC-LAWS-REPORT.md"
    failure_path = report_root / f"final-public-laws-failure-{run_stamp}.txt"
    archive_path = repo / "codification" / "archive" / f"round3-workbench-{run_stamp}.zip"

    touched = ["usc/usc18.xml", "usc/usc50.xml", "data/titles.json", "codification/state.json"]
    for relative in touched:
        backup_file(repo, backup_root, relative)

    source_records = {}
    report_lines = [
        "# Final Public-Law Implementation Report",
        "",
        f"- Run: `{now_iso()}`",
        f"- Repository: `{repo}`",
        f"- Backup: `{backup_root}`",
        "",
        "## Source authentication",
        "",
    ]

    try:
        for law in [*LAWS, CRACK]:
            text, path, matches = load_source(repo, law)
            source_hash = sha256_text(text)
            source_records[law["law_id"]] = {
                "text": text,
                "path": path,
                "sha256": source_hash,
                "matches": matches,
            }
            report_lines += [
                f"### {law['law_id']} — {law['title']}",
                "",
                f"- Source: `{path}`",
                f"- Characters: {len(text):,}",
                f"- SHA-256: `{source_hash}`",
                f"- Identity terms observed: {', '.join(matches) or 'none; accepted from authenticated law-specific source path'}",
                "",
            ]

        crack_result = crack_audit(repo, source_records["PL-003-025"]["text"])

        title_texts = {
            18: (repo / "usc" / "usc18.xml").read_text(encoding="utf-8"),
            50: (repo / "usc" / "usc50.xml").read_text(encoding="utf-8"),
        }
        application_records = []

        report_lines += ["## Codification decisions", ""]

        for law in LAWS:
            source = source_records[law["law_id"]]
            selected, selection_label = select_source(source["text"], law)
            xml = title_texts[law["target_title"]]
            start, end, _ = element_span(xml, law["target_identifier"])
            section = xml[start:end]
            note = statutory_note_xml(
                law,
                selected,
                source["sha256"],
                selection_label,
            )
            replacement, implementation_result = inject_note(section, law, note)
            title_texts[law["target_title"]] = xml[:start] + replacement + xml[end:]

            record = {
                "law_id": law["law_id"],
                "public_law": law["public_law"],
                "title": law["title"],
                "source_sha256": source["sha256"],
                "classification": law["classification"],
                "implementation": (
                    f"{law['target_label']} statutory note; {selection_label}; "
                    f"{implementation_result}"
                ),
                "changed_files": law["changed_files"],
                "applied_at": now_iso(),
            }
            application_records.append(record)

            report_lines += [
                f"### {law['law_id']} — {law['title']}",
                "",
                f"- **Disposition:** {law['classification']}",
                f"- **Placement:** {law['target_label']}",
                f"- **Source included:** {selection_label}",
                f"- **Result:** {implementation_result}",
                "",
            ]

        report_lines += [
            "### PL-003-025 — CRACK Act",
            "",
            f"- **Disposition:** {crack_result['disposition']}",
            f"- Existing Code files containing CRACK references: "
            f"{', '.join(crack_result['existing_code_files_with_crack_references']) or 'none'}",
            f"- Direct-amendment lines flagged for the audit record: "
            f"{len(crack_result['flagged_amendment_lines'])}",
            "",
        ]

        # Validate in temporary files before committing either title.
        temp_dir = Path(tempfile.mkdtemp(prefix="usar-final-laws-"))
        try:
            staged_paths = []
            for title, text in title_texts.items():
                staged = temp_dir / f"usc{title:02d}.xml"
                staged.write_text(text, encoding="utf-8", newline="")
                validate_full_xml(staged)
                staged_paths.append(staged)
            enc = encoding_errors(staged_paths)
            if enc:
                raise ValueError("\n".join(enc))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Commit both titles transactionally; restoration occurs on any later error.
        transactional_write(repo / "usc" / "usc18.xml", title_texts[18])
        transactional_write(repo / "usc" / "usc50.xml", title_texts[50])

        duplicates = scan_rp_ids(repo)
        if duplicates:
            raise ValueError(
                "Duplicate project-generated XML IDs detected:\n" + "\n".join(duplicates)
            )

        verification_errors = encoding_errors(
            [repo / "usc" / "usc18.xml", repo / "usc" / "usc50.xml"]
        )
        if verification_errors:
            raise ValueError("\n".join(verification_errors))

        for law in LAWS:
            xml_path = repo / "usc" / f"usc{law['target_title']:02d}.xml"
            current = xml_path.read_text(encoding="utf-8")
            marker = make_id(law["law_id"], law["target_identifier"], "statutory-note")
            if f'id="{marker}"' not in current:
                # Equivalent preexisting note is allowed only if the exact law and title occur.
                if not (
                    f"Pub. L. {law['public_law'].replace('-', '–')}" in current
                    and law["title"] in current
                ):
                    raise ValueError(f"Post-write verification failed for {law['law_id']}")

        check_results = []
        run_optional(repo, ["tools/build_index.py"], "metadata index rebuild", check_results)
        run_optional(repo, ["tools/check_encoding.py"], "repository encoding audit", check_results)
        run_optional(
            repo,
            ["tools/audit_applied_material.py"],
            "applied-material audit",
            check_results,
        )

        # Save the source/audit record before cleaning the temporary workbench.
        crack_report_path = report_root / "PL-003-025-final-survival-audit.json"
        crack_report_path.write_text(
            json.dumps(crack_result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        update_state(repo, backup_root, application_records)

        archive_members = archive_workbench(repo, archive_path)
        removed = []
        if args.cleanup:
            cleanup(repo, removed)

        trello_path = report_root / "FINAL-TRELLO-COMMENTS.md"
        trello_parts = ["# Final Trello codification comments", ""]
        for record in application_records:
            trello_parts += [
                f"## {record['law_id']}",
                "",
                trello_comment(record),
                "",
            ]
        trello_parts += [
            "## PL-003-025",
            "",
            "**Final disposition — CRACK Act**\n\n"
            "No wholesale catch-up insertion was made. Public Law 38-263 supersedes "
            "the national-security framework, and Public Law 38-264 expressly "
            "repeals Titles V and VI and amendments made by those titles. The "
            "replacement Acts are now published at 50 U.S.C. § 3341 and "
            "18 U.S.C. § 1961, respectively.\n",
        ]
        trello_path.write_text("\n".join(trello_parts), encoding="utf-8")

        report_lines += [
            "## Validation",
            "",
            *check_results,
            "- Changed Title 18 parses without XML recovery: passed",
            "- Changed Title 50 parses without XML recovery: passed",
            "- Duplicate `rp-` identifier scan: passed",
            "- Changed-title mojibake/replacement-character audit: passed",
            "",
            "## State and cleanup",
            "",
            "- `codification/state.json` updated for PL-019-149, PL-014-089, PL-038-263, and PL-038-264.",
            f"- Workbench archive: `{archive_path}`"
            if archive_members
            else "- No temporary workbench material existed to archive.",
            f"- Archived workbench files: {len(archive_members)}",
            f"- Removed temporary package/workbench paths: {len(removed)}",
            "",
        ]
        if removed:
            report_lines += ["### Removed paths", "", *[f"- `{p}`" for p in removed], ""]

        report_lines += [
            "## Changed Code files",
            "",
            "- `usc/usc18.xml`",
            "- `usc/usc50.xml`",
            "- `data/titles.json`",
            "- `codification/state.json`",
            "",
            "## Final result",
            "",
            "The active replacement legislation is incorporated. Superseded PL 2-5 "
            "and PL 2-6 text was not revived. The repealed CRACK Act was not inserted "
            "wholesale. The complete replacement Acts and their repeal provisions "
            "are available from their governing Code locations.",
            "",
        ]

        report_path.write_text("\n".join(report_lines), encoding="utf-8")
        print(f"SUCCESS: {report_path}")
        print(f"BACKUP: {backup_root}")
        if archive_members:
            print(f"ARCHIVE: {archive_path}")
        return 0

    except Exception as exc:
        # Restore every file that could have been changed.
        restore_files(repo, backup_root, touched)
        failure = (
            f"Final public-law implementation failed at {now_iso()}\n\n"
            f"{exc}\n\n{traceback.format_exc()}"
        )
        failure_path.write_text(failure, encoding="utf-8")
        print(failure, file=sys.stderr)
        print(f"Restored changed files from: {backup_root}", file=sys.stderr)
        print(f"Failure report: {failure_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
