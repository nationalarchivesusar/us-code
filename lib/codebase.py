from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from lxml import etree

from .common import atomic_write_text, deterministic_id, normalize_whitespace, relative, sha256_text, tokenize, unique_preserve


NS_URI = "http://xml.house.gov/schemas/uslm/1.0"
X = f"{{{NS_URI}}}"

SECTION_ID_RE = re.compile(r"^/us/usc/t(?P<title>\d+)/s(?P<section>[^/]+)$")
CHAPTER_ID_RE = re.compile(r"^/us/usc/t(?P<title>\d+)/ch(?P<chapter>[^/]+)$")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def strip_tags(value: str) -> str:
    return normalize_whitespace(html.unescape(re.sub(r"(?s)<[^>]+>", " ", value)))


def element_span(xml: str, identifier: str) -> tuple[int, int, str]:
    escaped = re.escape(identifier)
    start_match = re.search(
        rf'<(?P<tag>[A-Za-z0-9_:.-]+)\b(?=[^>]*\bidentifier="{escaped}")[^>]*>',
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
    raise ValueError(f"Closing tag not found for {identifier}")


def validate_xml(path: Path) -> None:
    etree.parse(str(path), parser=etree.XMLParser(huge_tree=True, recover=False))


def serialize_uslm_element(element: etree._Element) -> str:
    """Serialize a detached USLM element using the repository's default namespace style."""
    value = etree.tostring(element, encoding="unicode")
    value = value.replace(f' xmlns:ns0="{NS_URI}"', "")
    value = value.replace("<ns0:", "<").replace("</ns0:", "</")
    return value


class CodeIndex:
    def __init__(self, repo: Path):
        self.repo = repo
        self.usc = repo / "usc"
        self.sections_by_title: dict[int, list[dict]] = {}
        self.section_numbers_by_title: dict[int, set[str]] = {}
        self.chapters_by_title: dict[int, set[str]] = {}
        self._law_locations: dict[str, list[str]] | None = None

    def title_path(self, title: int) -> Path:
        return self.usc / f"usc{title:02d}.xml"

    def title_exists(self, title: int) -> bool:
        return self.title_path(title).exists()

    def section_exists(self, title: int, section: str) -> bool:
        if title not in self.section_numbers_by_title:
            self.index_title(title)
        return str(section) in self.section_numbers_by_title.get(title, set())

    def chapter_exists(self, title: int, chapter: str) -> bool:
        if title not in self.chapters_by_title:
            path = self.title_path(title)
            if not path.exists():
                self.chapters_by_title[title] = set()
            else:
                text = path.read_text(encoding="utf-8", errors="replace")
                pattern = re.compile(
                    rf'identifier="/us/usc/t{title}/ch(?P<chapter>[^"/]+)"'
                )
                self.chapters_by_title[title] = {
                    match.group("chapter") for match in pattern.finditer(text)
                }
        return str(chapter) in self.chapters_by_title.get(title, set())

    def index_title(self, title: int) -> list[dict]:
        if title in self.sections_by_title:
            return self.sections_by_title[title]
        path = self.title_path(title)
        if not path.exists():
            self.sections_by_title[title] = []
            self.section_numbers_by_title[title] = set()
            return []
        text = path.read_text(encoding="utf-8", errors="replace")
        opening = re.compile(
            rf'<section\b[^>]*\bidentifier="(?P<identifier>/us/usc/t{title}/s(?P<section>[^"/]+))"[^>]*>',
            re.DOTALL,
        )
        results = []
        for match in opening.finditer(text):
            sample = text[match.end() : match.end() + 6000]
            heading_match = re.search(r"(?s)<heading\b[^>]*>(.*?)</heading>", sample)
            heading = strip_tags(heading_match.group(1)) if heading_match else ""
            if heading.lower() in {"repealed", "reserved", "[repealed]", "[reserved]"}:
                reserved = True
            else:
                reserved = False
            results.append(
                {
                    "title": title,
                    "section": match.group("section"),
                    "identifier": match.group("identifier"),
                    "heading": heading,
                    "tokens": tokenize(heading),
                    "reserved": reserved,
                }
            )
        self.sections_by_title[title] = results
        self.section_numbers_by_title[title] = {item["section"] for item in results}
        return results

    def best_section(self, title: int, query: str, default_sections: list[str] | None = None) -> dict | None:
        sections = self.index_title(title)
        if not sections:
            return None
        query_tokens = Counter(tokenize(query))
        best = None
        best_score = -10**9
        for item in sections:
            if item["reserved"]:
                continue
            heading_tokens = Counter(item["tokens"])
            overlap = sum(min(query_tokens[token], count) for token, count in heading_tokens.items())
            score = overlap * 12
            for token in heading_tokens:
                if token in query_tokens:
                    score += min(5, len(token) / 2)
            if item["heading"]:
                phrase = item["heading"].lower()
                if phrase in query.lower() or query.lower() in phrase:
                    score += 20
            if default_sections and item["section"] in default_sections:
                score += 3
            if score > best_score:
                best = item
                best_score = score
        if best is None and default_sections:
            for default in default_sections:
                candidate = next((item for item in sections if item["section"] == default), None)
                if candidate:
                    return candidate
        return best or sections[0]

    def incorporated_law_locations(self) -> dict[str, list[str]]:
        if self._law_locations is not None:
            return self._law_locations
        locations: dict[str, set[str]] = defaultdict(set)
        law_patterns = [
            re.compile(r"/us/pl/(?P<c>\d{1,3})/(?P<n>\d{1,4})", re.IGNORECASE),
            re.compile(r"Pub\.\s*L\.\s*(?P<c>\d{1,3})[–—-](?P<n>\d{1,4})", re.IGNORECASE),
        ]
        for path in sorted(self.usc.glob("usc*.xml")):
            current_section = ""
            stack: list[str] = []
            try:
                context = etree.iterparse(
                    str(path), events=("start", "end"), huge_tree=True, recover=False
                )
                rp_depth = 0
                rp_root = None
                rp_section = ""
                for event, elem in context:
                    name = local_name(elem.tag)
                    if event == "start":
                        if name == "section":
                            stack.append(str(elem.get("identifier", "")))
                            current_section = stack[-1]
                        if rp_depth:
                            rp_depth += 1
                        elif str(elem.get("id", "")).startswith("rp-"):
                            rp_depth = 1
                            rp_root = elem
                            rp_section = current_section
                    elif event == "end":
                        if rp_depth:
                            if rp_depth == 1 and elem is rp_root:
                                serialized = etree.tostring(elem, encoding="unicode")
                                # An rp element may reproduce an entire Act and
                                # therefore mention older laws that it repeals or
                                # amends.  Only the first source-credit/public-law
                                # reference identifies the law that created this
                                # project element; later references are dependencies,
                                # not evidence that those laws were incorporated.
                                primary = None
                                for pattern in law_patterns:
                                    match = pattern.search(serialized)
                                    if match:
                                        primary = match
                                        # Prefer an href source credit over plain
                                        # text when both are present.
                                        if pattern is law_patterns[0]:
                                            break
                                if primary:
                                    law_id = f"PL-{int(primary.group('c')):03d}-{int(primary.group('n')):03d}"
                                    locations[law_id].add(rp_section or relative(path, self.repo))
                                rp_root = None
                                rp_section = ""
                            rp_depth -= 1
                        if name == "section" and stack:
                            stack.pop()
                            current_section = stack[-1] if stack else ""
                        if rp_depth == 0:
                            elem.clear()
            except etree.XMLSyntaxError:
                # Validation later will surface malformed XML; a regex fallback still
                # recovers project-generated references for inventory purposes.
                text = path.read_text(encoding="utf-8", errors="replace")
                for rp in re.finditer(r'(?s)<[^>]+\bid="rp-[^"]+"[^>]*>.*?</[^>]+>', text):
                    block = rp.group(0)
                    primary = None
                    for pattern in law_patterns:
                        match = pattern.search(block)
                        if match:
                            primary = match
                            if pattern is law_patterns[0]:
                                break
                    if primary:
                        law_id = f"PL-{int(primary.group('c')):03d}-{int(primary.group('n')):03d}"
                        locations[law_id].add(relative(path, self.repo))
        self._law_locations = {key: sorted(value) for key, value in locations.items()}
        return self._law_locations


class TitleEditor:
    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8")
        title_match = re.search(r"<docNumber>(\d+)</docNumber>", self.text)
        self.title = int(title_match.group(1)) if title_match else int(re.search(r"usc(\d+)\.xml", path.name).group(1))
        self.changed = False
        self.change_log: list[dict] = []

    def has_identifier(self, identifier: str) -> bool:
        return f'identifier="{identifier}"' in self.text

    def element(self, identifier: str) -> str:
        start, end, _ = element_span(self.text, identifier)
        return self.text[start:end]

    def replace_element(self, identifier: str, replacement: str, reason: str) -> None:
        start, end, _ = element_span(self.text, identifier)
        self.text = self.text[:start] + replacement + self.text[end:]
        self.changed = True
        self.change_log.append({"kind": "replace_element", "identifier": identifier, "reason": reason})

    def append_note(self, identifier: str, note_xml: str, marker_id: str, reason: str) -> str:
        start, end, tag = element_span(self.text, identifier)
        fragment = self.text[start:end]
        if f'id="{marker_id}"' in fragment:
            return "already-present"
        close_notes = fragment.rfind("</notes>")
        if close_notes >= 0:
            replacement = fragment[:close_notes] + note_xml + fragment[close_notes:]
        else:
            closing = fragment.rfind(f"</{tag}>")
            if closing < 0:
                raise ValueError(f"Malformed target element {identifier}")
            notes_id = deterministic_id(marker_id, identifier, "notes")
            wrapper = f'<notes type="uscNote" id="{notes_id}">{note_xml}</notes>'
            replacement = fragment[:closing] + wrapper + fragment[closing:]
        self._validate_fragment(replacement)
        self.text = self.text[:start] + replacement + self.text[end:]
        self.changed = True
        self.change_log.append({"kind": "append_note", "identifier": identifier, "reason": reason})
        return "inserted"

    def strike_insert(self, identifier: str, old_text: str, new_text: str, reason: str) -> str:
        start, end, _ = element_span(self.text, identifier)
        fragment = self.text[start:end]
        # Do not satisfy a strike instruction from an editorial or historical
        # note that merely quotes the old language.  Code text ordinarily
        # precedes sourceCredit/notes; if inline USLM prevents an exact match,
        # the caller safely falls back to a controlling amendment note.
        boundaries = [
            position for position in (fragment.find("<sourceCredit"), fragment.find("<notes"))
            if position >= 0
        ]
        operative_end = min(boundaries) if boundaries else len(fragment)
        operative = fragment[:operative_end]
        suffix = fragment[operative_end:]
        old_variants = unique_preserve(
            [
                old_text,
                escape(old_text),
                old_text.replace("“", '"').replace("”", '"'),
                escape(old_text.replace("“", '"').replace("”", '"')),
            ]
        )
        matches: list[tuple[str, int]] = []
        for variant in old_variants:
            count = operative.count(variant)
            if count:
                matches.append((variant, count))
        exact = next(((variant, count) for variant, count in matches if count == 1), None)
        if exact is None:
            return "not-uniquely-executable"
        variant, _ = exact
        replacement_text = escape(new_text)
        updated = operative.replace(variant, replacement_text, 1) + suffix
        self._validate_fragment(updated)
        self.text = self.text[:start] + updated + self.text[end:]
        self.changed = True
        self.change_log.append(
            {
                "kind": "strike_insert",
                "identifier": identifier,
                "old_text": old_text,
                "new_text": new_text,
                "reason": reason,
            }
        )
        return "executed"

    def update_toc_heading(self, identifier: str, heading: str) -> int:
        """Update every table-of-contents item that points to a section.

        USLM title/chapter TOCs use several column-class variants.  The method
        finds the column containing the target ref and updates the following
        column without assuming a particular class name.
        """
        matches = list(re.finditer(r"(?s)<tocItem\b[^>]*>.*?</tocItem>", self.text))
        replacements: list[tuple[int, int, str]] = []
        for match in matches:
            block = match.group(0)
            if f'href="{identifier}"' not in block:
                continue
            wrapper = f'<wrapper xmlns="{NS_URI}">{block}</wrapper>'
            root = etree.fromstring(
                wrapper.encode("utf-8"),
                parser=etree.XMLParser(huge_tree=True, recover=False),
            )
            toc = root[0]
            columns = [child for child in toc if local_name(child.tag) == "column"]
            target_index = None
            for index, column in enumerate(columns):
                if any(
                    local_name(node.tag) == "ref" and node.get("href") == identifier
                    for node in column.iter()
                ):
                    target_index = index
                    break
            if target_index is None or target_index + 1 >= len(columns):
                continue
            target_column = columns[target_index + 1]
            for child in list(target_column):
                target_column.remove(child)
            target_column.text = heading
            replacements.append((match.start(), match.end(), serialize_uslm_element(toc)))
        for start, end, replacement in reversed(replacements):
            self.text = self.text[:start] + replacement + self.text[end:]
        if replacements:
            self.changed = True
        return len(replacements)

    def repeal_section(self, identifier: str, law_id: str, public_law: str, reason: str) -> str:
        start, end, _ = element_span(self.text, identifier)
        fragment = self.text[start:end]
        wrapper = f'<wrapper xmlns="{NS_URI}">{fragment}</wrapper>'
        root = etree.fromstring(wrapper.encode("utf-8"), parser=etree.XMLParser(huge_tree=True))
        section = root[0]
        marker = deterministic_id(law_id, identifier, "repeal")
        if any(elem.get("id") == marker for elem in section.iter()):
            return "already-present"

        keep_names = {"num", "sourceCredit", "notes"}
        for child in list(section):
            if local_name(child.tag) not in keep_names:
                section.remove(child)
        heading = etree.Element(X + "heading")
        heading.text = "Repealed"
        insert_at = 1 if len(section) and local_name(section[0].tag) == "num" else 0
        section.insert(insert_at, heading)
        chapeau = etree.Element(X + "chapeau", id=deterministic_id(law_id, identifier, "repealed-content"))
        paragraph = etree.SubElement(chapeau, X + "p")
        paragraph.text = f"[Repealed by Pub. L. {public_law}.]"
        section.insert(insert_at + 1, chapeau)
        notes = next((child for child in section if local_name(child.tag) == "notes"), None)
        if notes is None:
            notes = etree.SubElement(section, X + "notes", type="uscNote", id=deterministic_id(law_id, identifier, "notes"))
        note = etree.SubElement(notes, X + "note", topic="amendments", id=marker)
        h = etree.SubElement(note, X + "heading", **{"class": "centered smallCaps"})
        h.text = "USAR Repeal"
        p = etree.SubElement(note, X + "p", **{"class": "indent0"})
        p.text = f"Pub. L. {public_law} repealed this section."
        replacement = serialize_uslm_element(section)
        self.text = self.text[:start] + replacement + self.text[end:]
        self.changed = True
        toc_updates = self.update_toc_heading(identifier, "Repealed")
        self.change_log.append({
            "kind": "repeal_section", "identifier": identifier,
            "reason": reason, "toc_updates": toc_updates,
        })
        return "executed"

    def insert_new_section(
        self,
        chapter_identifier: str,
        section_identifier: str,
        section_number: str,
        heading: str,
        section_xml: str,
        law_id: str,
        reason: str,
    ) -> str:
        if self.has_identifier(section_identifier):
            return "section-already-exists"
        start, end, _ = element_span(self.text, chapter_identifier)
        chapter = self.text[start:end]
        href = section_identifier
        if href in chapter:
            return "toc-entry-already-exists"
        toc_item = (
            '<tocItem>'
            f'<column class="tocItemLeft"><ref href="{escape(href)}">{escape(section_number)}</ref></column>'
            f'<column class="tocItemMiddle">{escape(heading)}</column>'
            '<column class="tocItemRight"/>'
            '</tocItem>'
        )
        # Insert into the chapter table of contents if one exists.
        toc_close = chapter.find("</layout>")
        if toc_close >= 0:
            chapter = chapter[:toc_close] + toc_item + chapter[toc_close:]
        else:
            toc_close = chapter.find("</toc>")
            if toc_close >= 0:
                chapter = chapter[:toc_close] + toc_item + chapter[toc_close:]
        chapter_close = chapter.rfind("</chapter>")
        if chapter_close < 0:
            raise ValueError(f"Malformed chapter {chapter_identifier}")
        chapter = chapter[:chapter_close] + section_xml + chapter[chapter_close:]
        self._validate_fragment(chapter)
        self.text = self.text[:start] + chapter + self.text[end:]
        self.changed = True
        self.change_log.append(
            {
                "kind": "new_section",
                "identifier": section_identifier,
                "chapter": chapter_identifier,
                "reason": reason,
            }
        )
        return "executed"

    @staticmethod
    def _validate_fragment(fragment: str) -> None:
        wrapper = f'<wrapper xmlns="{NS_URI}">{fragment}</wrapper>'
        etree.fromstring(wrapper.encode("utf-8"), parser=etree.XMLParser(huge_tree=True, recover=False))

    def write(self, target: Path | None = None) -> None:
        target = target or self.path
        atomic_write_text(target, self.text, validate_xml)


def scan_duplicate_rp_ids(paths: Iterable[Path]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    pattern = re.compile(r'\bid="(rp-[^"]+)"')
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for identifier in pattern.findall(text):
            if identifier in seen:
                duplicates.add(identifier)
            seen.add(identifier)
    return sorted(duplicates)


def suspected_encoding_errors(paths: Iterable[Path]) -> list[str]:
    patterns = ["\ufffd", "â€™", "â€œ", "â€\x9d", "Ã¢", "Â§"]
    errors = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            if pattern in text:
                errors.append(f"{path.name}: contains suspected encoding artifact {pattern!r}")
    return errors


def run_repository_checks(repo: Path, title42_changed: bool = False) -> list[dict]:
    commands: list[tuple[str, list[str], bool]] = [
        ("Build metadata index", ["tools/build_index.py"], True),
        ("Encoding audit", ["tools/check_encoding.py"], True),
        ("Applied-material audit", ["tools/audit_applied_material.py"], True),
    ]
    if title42_changed:
        commands.extend(
            [
                ("Build Title 42 chunks", ["tools/build_title42_chunks.py"], True),
                ("Validate Title 42 chunks", ["tools/check_title42_build.py"], True),
            ]
        )
    results = []
    for label, command, required_if_present in commands:
        script = repo / command[0]
        if not script.exists():
            results.append({"label": label, "status": "skipped", "detail": f"{command[0]} not present"})
            continue
        proc = subprocess.run(
            [sys.executable, str(script), *command[1:]],
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=1800,
        )
        detail = (proc.stdout + "\n" + proc.stderr).strip()
        results.append(
            {
                "label": label,
                "status": "passed" if proc.returncode == 0 else "failed",
                "detail": detail[-8000:],
            }
        )
        if proc.returncode != 0 and required_if_present:
            raise RuntimeError(f"{label} failed:\n{detail[-8000:]}")
    return results
