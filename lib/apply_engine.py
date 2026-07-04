from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from lxml import etree

from .codebase import NS_URI, X, CodeIndex, TitleEditor, element_span, local_name, run_repository_checks, scan_duplicate_rp_ids, serialize_uslm_element, suspected_encoding_errors, validate_xml
from .common import atomic_write_text, clean_xml_text, deterministic_id, law_sort_key, parse_law_id, read_json, relative, sha256_text, write_json
from .model import LawAnalysis, LawCard, Operation, SourceRecord


def public_law_display(law_id: str) -> str:
    parsed = parse_law_id(law_id)
    if not parsed:
        return law_id
    return f"{parsed[0]}–{parsed[1]}"


def public_law_href(law_id: str) -> str:
    parsed = parse_law_id(law_id)
    if not parsed:
        return ""
    return f"/us/pl/{parsed[0]}/{parsed[1]}"


def source_paragraphs(text: str) -> list[str]:
    blocks = []
    for raw in re.split(r"\n\s*\n", clean_xml_text(text).strip()):
        raw = re.sub(r"[ \t]*\n[ \t]*", " ", raw).strip()
        if not raw:
            continue
        while len(raw) > 12000:
            split = raw.rfind(" ", 0, 12000)
            if split < 1000:
                split = 12000
            blocks.append(raw[:split].strip())
            raw = raw[split:].strip()
        if raw:
            blocks.append(raw)
    return blocks


def note_xml(
    analysis: LawAnalysis,
    card: LawCard,
    source: SourceRecord,
    text: str,
    target_identifier: str,
    heading_prefix: str = "USAR Public Law",
    concise: bool = False,
) -> tuple[str, str]:
    marker = deterministic_id(analysis.law_id, target_identifier, "statutory-note")
    notes_heading = escape(f"{heading_prefix}—{analysis.title}")
    href = public_law_href(analysis.law_id)
    law_display = public_law_display(analysis.law_id)
    lead = (
        f'<p style="-uslm-lc:I21" class="indent0">'
        f'<ref href={quoteattr(href)}>Pub. L. {escape(law_display)}</ref>'
        f", classified here as {escape(analysis.disposition.replace('_', ' ').lower())}. "
        f"{escape(analysis.rationale)}"
        "</p>"
    )
    source_line = (
        '<p style="-uslm-lc:I21" class="indent0">'
        f'<i>Archive source:</i> <ref href={quoteattr(source.selected_url or card.url)}>'
        f"{escape(source.selected_name or 'NARA public-law record')}</ref>; "
        f'<i>SHA-256:</i> {escape(source.sha256)}.'
        "</p>"
    )
    body = []
    chosen = text
    if concise and len(chosen) > 12000:
        chosen = chosen[:12000] + "\n\n[The complete authenticated source is retained in the local codification record.]"
    for paragraph in source_paragraphs(chosen):
        body.append(f'<p style="-uslm-lc:I21" class="indent0">{escape(paragraph)}</p>')
    xml = (
        f'<note style="-uslm-lc:I74" topic="miscellaneous" id="{marker}">'
        f'<heading class="centered smallCaps">{notes_heading}</heading>'
        f"{lead}{source_line}{''.join(body)}"
        "</note>"
    )
    return xml, marker


def _section_heading_and_body(block: str, fallback_heading: str) -> tuple[str, str]:
    clean = clean_xml_text(block).strip().strip('"“”')
    match = re.match(
        r"(?is)^\s*(?:§+|SEC(?:TION)?\.?)\s*[0-9A-Za-z.-]+\s*[.\-—:]\s*(?P<heading>[^\n]+)\n?(?P<body>.*)$",
        clean,
    )
    if match:
        return match.group("heading").strip(" .—-"), match.group("body").strip()
    lines = clean.splitlines()
    if lines and len(lines[0]) < 160 and not re.match(r"^\([a-zA-Z0-9]+\)", lines[0].strip()):
        return lines[0].strip(" .—-"), "\n".join(lines[1:]).strip()
    return fallback_heading, clean


def _content_elements(body: str, law_id: str, target: str) -> list[etree._Element]:
    paragraphs = source_paragraphs(body)
    elements: list[etree._Element] = []
    current_subsection = None
    subsection_index = 0
    for paragraph in paragraphs:
        marker = re.match(r"^\((?P<num>[a-zA-Z])\)\s*(?P<body>.*)$", paragraph, re.DOTALL)
        if marker:
            subsection_index += 1
            subsection = etree.Element(
                X + "subsection",
                id=deterministic_id(law_id, target, "subsection", str(subsection_index)),
            )
            num = etree.SubElement(subsection, X + "num", value=marker.group("num"))
            num.text = f"({marker.group('num')})"
            content = etree.SubElement(subsection, X + "content")
            p = etree.SubElement(content, X + "p")
            p.text = marker.group("body").strip()
            elements.append(subsection)
            current_subsection = content
        elif current_subsection is not None:
            p = etree.SubElement(current_subsection, X + "p")
            p.text = paragraph
        else:
            chapeau = etree.Element(
                X + "chapeau",
                id=deterministic_id(law_id, target, "chapeau", str(len(elements))),
            )
            p = etree.SubElement(chapeau, X + "p")
            p.text = paragraph
            elements.append(chapeau)
    if not elements:
        chapeau = etree.Element(X + "chapeau", id=deterministic_id(law_id, target, "chapeau"))
        p = etree.SubElement(chapeau, X + "p")
        p.text = "[No substantive text was recoverable from the source block.]"
        elements.append(chapeau)
    return elements


def build_new_section_xml(
    analysis: LawAnalysis,
    operation: Operation,
    card: LawCard,
    source: SourceRecord,
) -> tuple[str, str]:
    identifier = operation.output_identifier or f"/us/usc/t{operation.title}/s{operation.section}"
    heading, body = _section_heading_and_body(operation.source_block, operation.new_text or analysis.title)
    section = etree.Element(
        X + "section",
        id=deterministic_id(analysis.law_id, identifier, "section"),
        identifier=identifier,
    )
    num = etree.SubElement(section, X + "num", value=str(operation.section))
    num.text = f"§ {operation.section}."
    h = etree.SubElement(section, X + "heading")
    h.text = heading
    for element in _content_elements(body, analysis.law_id, identifier):
        section.append(element)
    source_credit = etree.SubElement(
        section,
        X + "sourceCredit",
        id=deterministic_id(analysis.law_id, identifier, "source-credit"),
    )
    p = etree.SubElement(source_credit, X + "p")
    ref = etree.SubElement(p, X + "ref", href=public_law_href(analysis.law_id))
    ref.text = f"Pub. L. {public_law_display(analysis.law_id)}"
    ref.tail = "."
    notes = etree.SubElement(
        section,
        X + "notes",
        type="uscNote",
        id=deterministic_id(analysis.law_id, identifier, "notes"),
    )
    note = etree.SubElement(
        notes,
        X + "note",
        topic="codification",
        id=deterministic_id(analysis.law_id, identifier, "codification-note"),
    )
    note_heading = etree.SubElement(note, X + "heading", **{"class": "centered smallCaps"})
    note_heading.text = "USAR Codification"
    note_p = etree.SubElement(note, X + "p", **{"class": "indent0"})
    note_p.text = (
        f"This section was added from {analysis.law_id}. Archive source SHA-256: {source.sha256}."
    )
    xml = serialize_uslm_element(section)
    return xml, heading


def build_replacement_section(
    existing: str,
    analysis: LawAnalysis,
    operation: Operation,
    source: SourceRecord,
) -> tuple[str, str]:
    wrapper = f'<wrapper xmlns="{NS_URI}">{existing}</wrapper>'
    root = etree.fromstring(wrapper.encode("utf-8"), parser=etree.XMLParser(huge_tree=True))
    section = root[0]
    old_heading = next((child for child in section if local_name(child.tag) == "heading"), None)
    heading, body = _section_heading_and_body(
        operation.source_block,
        old_heading.text if old_heading is not None and old_heading.text else analysis.title,
    )
    keep = {"num", "sourceCredit", "notes"}
    for child in list(section):
        if local_name(child.tag) not in keep:
            section.remove(child)
    heading_element = etree.Element(X + "heading")
    heading_element.text = heading
    insert_at = 1 if len(section) and local_name(section[0].tag) == "num" else 0
    section.insert(insert_at, heading_element)
    content_elements = _content_elements(body, analysis.law_id, operation.target_identifier)
    for offset, element in enumerate(content_elements, start=insert_at + 1):
        section.insert(offset, element)
    source_credit = next((child for child in section if local_name(child.tag) == "sourceCredit"), None)
    if source_credit is None:
        source_credit = etree.SubElement(
            section,
            X + "sourceCredit",
            id=deterministic_id(analysis.law_id, operation.target_identifier, "source-credit"),
        )
    p = etree.SubElement(source_credit, X + "p")
    ref = etree.SubElement(p, X + "ref", href=public_law_href(analysis.law_id))
    ref.text = f"Pub. L. {public_law_display(analysis.law_id)}"
    ref.tail = ", restated this section."
    notes = next((child for child in section if local_name(child.tag) == "notes"), None)
    if notes is None:
        notes = etree.SubElement(
            section,
            X + "notes",
            type="uscNote",
            id=deterministic_id(analysis.law_id, operation.target_identifier, "notes"),
        )
    note = etree.SubElement(
        notes,
        X + "note",
        topic="amendments",
        id=deterministic_id(analysis.law_id, operation.target_identifier, "restatement-note"),
    )
    h = etree.SubElement(note, X + "heading", **{"class": "centered smallCaps"})
    h.text = "USAR Amendment"
    p2 = etree.SubElement(note, X + "p", **{"class": "indent0"})
    p2.text = f"{analysis.law_id} restated this section. Source SHA-256: {source.sha256}."
    return serialize_uslm_element(section), heading


class MassApplier:
    def __init__(
        self,
        repo: Path,
        workspace: Path,
        code_index: CodeIndex,
        cards: dict[str, LawCard],
        sources: dict[str, SourceRecord],
        analyses: list[LawAnalysis],
    ):
        self.repo = repo
        self.workspace = workspace
        self.code_index = code_index
        self.cards = cards
        self.sources = sources
        self.analyses = analyses
        self.run_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_root = workspace / "backups" / self.run_id
        self.staged_root = workspace / "staged" / self.run_id
        self.editors: dict[int, TitleEditor] = {}
        self.created_paths: set[Path] = set()
        self.manifest: dict = {
            "run_id": self.run_id,
            "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "laws": [],
            "changed_files": [],
            "repository_checks": [],
        }

    def editor(self, title: int) -> TitleEditor:
        if title not in self.editors:
            path = self.code_index.title_path(title)
            if not path.exists():
                raise FileNotFoundError(f"Title {title} XML not found: {path}")
            self.editors[title] = TitleEditor(path)
        return self.editors[title]

    def apply(self) -> dict:
        try:
            for analysis in sorted(self.analyses, key=lambda item: law_sort_key(item.law_id)):
                self.apply_law(analysis)
            self.stage_and_validate()
            self.commit_titles()
            self.update_state()
            index_path = self.repo / "data" / "titles.json"
            index_existed = index_path.exists()
            if index_existed:
                index_backup = self.backup_root / "data" / "titles.json"
                index_backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(index_path, index_backup)
            title42_changed = 42 in self.editors and self.editors[42].changed
            title42_chunks = self.repo / "data" / "title-42"
            title42_chunks_existed = title42_chunks.exists()
            self.manifest["repository_checks"] = run_repository_checks(self.repo, title42_changed)
            if not index_existed and index_path.exists():
                self.created_paths.add(index_path)
            if title42_changed and not title42_chunks_existed and title42_chunks.exists():
                self.created_paths.add(title42_chunks)
            self.manifest["completed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
            write_json(self.workspace / "reports" / "APPLIED-MANIFEST.json", self.manifest)
            return self.manifest
        except Exception:
            self.restore()
            raise

    def apply_law(self, analysis: LawAnalysis) -> None:
        if analysis.disposition in {
            "ALREADY_INCORPORATED",
            "NONOPERATIVE_OR_REPEALED",
            "SUPERSEDED_BEFORE_CODIFICATION",
            "NON_CODE",
            "SOURCE_UNAVAILABLE",
        }:
            self.manifest["laws"].append(
                {
                    "law_id": analysis.law_id,
                    "disposition": analysis.disposition,
                    "applied": False,
                    "rationale": analysis.rationale,
                }
            )
            return

        card = self.cards[analysis.law_id]
        source = self.sources[analysis.law_id]
        source_text = Path(source.text_path).read_text(encoding="utf-8")
        changed_files: set[str] = set()
        citation_links: list[str] = []

        for operation in analysis.operations:
            if operation.title is None:
                operation.status = "skipped-no-title"
                continue
            if (
                operation.kind in {"STRIKE_INSERT", "REPEAL_SECTION", "REPLACE_SECTION", "ADD_NEW_SECTION"}
                and operation.confidence != "high"
            ):
                operation.status = "withheld-preserved-by-note"
                operation.warnings.append(
                    "Destructive Code operation was not high-confidence and was not executed; "
                    "the authenticated enactment is preserved by the law's statutory note."
                )
                continue
            editor = self.editor(operation.title)
            changed_file = relative(editor.path, self.repo)
            result = ""
            if operation.kind == "STATUTORY_NOTE":
                xml, marker = note_xml(
                    analysis,
                    card,
                    source,
                    source_text,
                    operation.target_identifier,
                )
                result = editor.append_note(
                    operation.target_identifier,
                    xml,
                    marker,
                    operation.rationale,
                )
            elif operation.kind == "STRIKE_INSERT":
                result = editor.strike_insert(
                    operation.target_identifier,
                    operation.old_text,
                    operation.new_text,
                    operation.rationale,
                )
                if result != "executed":
                    fallback_text = (
                        f"Targeted amendment instruction:\n\nStrike: {operation.old_text}\n\n"
                        f"Insert: {operation.new_text}"
                    )
                    xml, marker = note_xml(
                        analysis,
                        card,
                        source,
                        fallback_text,
                        operation.target_identifier,
                        heading_prefix="USAR Controlling Amendment",
                    )
                    fallback = editor.append_note(
                        operation.target_identifier,
                        xml,
                        marker,
                        "Exact strike text was not uniquely located; preserved controlling amendment instruction.",
                    )
                    result = f"fallback-note:{fallback}"
                    operation.warnings.append("exact target phrase was not uniquely executable")
            elif operation.kind == "REPEAL_SECTION":
                result = editor.repeal_section(
                    operation.target_identifier,
                    analysis.law_id,
                    public_law_display(analysis.law_id),
                    operation.rationale,
                )
            elif operation.kind == "REPLACE_SECTION":
                existing = editor.element(operation.target_identifier)
                replacement, replacement_heading = build_replacement_section(existing, analysis, operation, source)
                editor.replace_element(operation.target_identifier, replacement, operation.rationale)
                editor.update_toc_heading(operation.target_identifier, replacement_heading)
                result = "executed"
            elif operation.kind == "ADD_NEW_SECTION":
                section_xml, heading = build_new_section_xml(analysis, operation, card, source)
                result = editor.insert_new_section(
                    operation.target_identifier,
                    operation.output_identifier,
                    operation.section,
                    heading,
                    section_xml,
                    analysis.law_id,
                    operation.rationale,
                )
            elif operation.kind == "APPEND_TEXT":
                xml, marker = note_xml(
                    analysis,
                    card,
                    source,
                    operation.source_block,
                    operation.target_identifier,
                    heading_prefix="USAR Targeted Amendment",
                )
                result = editor.append_note(
                    operation.target_identifier,
                    xml,
                    marker,
                    operation.rationale,
                )
            else:
                operation.status = "unsupported"
                operation.warnings.append(f"unsupported operation kind {operation.kind}")
                continue

            operation.status = result
            if editor.changed:
                changed_files.add(changed_file)
            section = operation.section or analysis.target_section
            if section:
                operation.citation_url = (
                    f"https://nationalarchivesusar.github.io/us-code/cite/{operation.title}/{section}/"
                )
                citation_links.append(operation.citation_url)

        analysis.applied = bool(changed_files)
        analysis.changed_files = sorted(changed_files)
        analysis.citation_links = sorted(set(citation_links))
        self.manifest["laws"].append(
            {
                "law_id": analysis.law_id,
                "disposition": analysis.disposition,
                "applied": analysis.applied,
                "changed_files": analysis.changed_files,
                "citation_links": analysis.citation_links,
                "operations": [operation.to_dict() for operation in analysis.operations],
                "source_sha256": analysis.source_sha256,
            }
        )

    def stage_and_validate(self) -> None:
        self.staged_root.mkdir(parents=True, exist_ok=True)
        staged_paths: list[Path] = []
        all_title_paths = sorted((self.repo / "usc").glob("usc*.xml"))
        for title, editor in self.editors.items():
            if not editor.changed:
                continue
            staged = self.staged_root / editor.path.name
            staged.write_text(editor.text, encoding="utf-8", newline="")
            validate_xml(staged)
            staged_paths.append(staged)
        errors = suspected_encoding_errors(staged_paths)
        if errors:
            raise ValueError("Encoding audit failed:\n- " + "\n- ".join(errors))

        # Duplicate IDs must be checked against staged versions of changed titles
        # and live versions of unchanged titles.
        composite: list[Path] = []
        changed_names = {path.name for path in staged_paths}
        composite.extend(staged_paths)
        composite.extend(path for path in all_title_paths if path.name not in changed_names)
        duplicates = scan_duplicate_rp_ids(composite)
        if duplicates:
            raise ValueError("Duplicate project-generated XML IDs:\n- " + "\n- ".join(duplicates))

    def commit_titles(self) -> None:
        for title, editor in self.editors.items():
            if not editor.changed:
                continue
            relative_path = relative(editor.path, self.repo)
            backup = self.backup_root / relative_path
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(editor.path, backup)
            staged = self.staged_root / editor.path.name
            atomic_write_text(editor.path, staged.read_text(encoding="utf-8"), validate_xml)
            self.manifest["changed_files"].append(relative_path)

    def update_state(self) -> None:
        state_path = self.repo / "codification" / "state.json"
        state_backup = self.backup_root / "codification" / "state.json"
        if state_path.exists():
            state_backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(state_path, state_backup)
            state = read_json(state_path, {})
        else:
            state = {}
            self.created_paths.add(state_path)
        mass = state.setdefault("mass_codification", {})
        runs = mass.setdefault("runs", [])
        runs.append(
            {
                "run_id": self.run_id,
                "applied_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "manifest": str(self.workspace / "reports" / "APPLIED-MANIFEST.json"),
            }
        )
        laws = mass.setdefault("laws", {})
        legacy_applied = state.setdefault("applied", {})
        if not isinstance(legacy_applied, dict):
            legacy_applied = {}
            state["applied"] = legacy_applied
        dispositions = state.setdefault("dispositions", {})
        if not isinstance(dispositions, dict):
            dispositions = {}
            state["dispositions"] = dispositions
        changed_files_state = state.setdefault("changed_files", [])
        if not isinstance(changed_files_state, list):
            changed_files_state = []
            state["changed_files"] = changed_files_state

        for analysis in self.analyses:
            record = {
                "title": analysis.title,
                "disposition": analysis.disposition,
                "applied": analysis.applied,
                "source_sha256": analysis.source_sha256,
                "changed_files": analysis.changed_files,
                "citation_links": analysis.citation_links,
                "card_url": analysis.card_url,
                "rationale": analysis.rationale,
                "operations": [operation.to_dict() for operation in analysis.operations],
                "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            }
            laws[analysis.law_id] = record
            if analysis.applied or analysis.disposition == "ALREADY_INCORPORATED":
                legacy_applied[analysis.law_id] = record
            else:
                dispositions[analysis.law_id] = record
            for changed_file in analysis.changed_files:
                if changed_file not in changed_files_state:
                    changed_files_state.append(changed_file)
        write_json(state_path, state)
        if relative(state_path, self.repo) not in self.manifest["changed_files"]:
            self.manifest["changed_files"].append(relative(state_path, self.repo))

    def restore(self) -> None:
        for created in sorted(self.created_paths, key=lambda value: len(str(value)), reverse=True):
            try:
                if created.is_file() or created.is_symlink():
                    created.unlink()
                elif created.is_dir():
                    shutil.rmtree(created)
            except FileNotFoundError:
                pass
        if not self.backup_root.exists():
            return
        for path in self.backup_root.rglob("*"):
            if not path.is_file():
                continue
            relative_path = path.relative_to(self.backup_root)
            destination = self.repo / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
