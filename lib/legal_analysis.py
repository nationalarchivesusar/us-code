from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .codebase import CodeIndex
from .common import LAW_RE, law_sort_key, normalize_whitespace, parse_law_id, sha256_text, tokenize, unique_preserve
from .model import CodeCitation, Dependency, LawAnalysis, LawCard, Operation, SourceRecord


CITATION_PATTERNS = [
    re.compile(
        r"(?P<section_word>section|sections)\s+"
        r"(?P<section>[0-9A-Za-z][0-9A-Za-z.\-]*)\s+of\s+title\s+"
        r"(?P<title>\d{1,2})\s*,?\s*(?:of\s+the\s+)?United\s+States\s+Code",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<title>\d{1,2})\s+U\.?\s*S\.?\s*C\.?\s*"
        r"(?:§+|sections?|secs?\.?|s\.)?\s*(?P<section>[0-9A-Za-z][0-9A-Za-z.\-]*)",
        re.IGNORECASE,
    ),
    re.compile(
        r"title\s+(?P<title>\d{1,2})\s*,?\s*(?:United\s+States\s+Code|U\.?S\.?C\.?)"
        r"\s*,?\s*section\s+(?P<section>[0-9A-Za-z][0-9A-Za-z.\-]*)",
        re.IGNORECASE,
    ),
]

TARGET_PATTERN = re.compile(
    r"(?:"
    r"section\s+(?P<section1>[0-9A-Za-z][0-9A-Za-z.\-]*)"
    r"(?P<subdivision1>(?:\([A-Za-z0-9ivxIVX]+\))*)\s+of\s+title\s+"
    r"(?P<title1>\d{1,2})\s*,?\s*(?:of\s+the\s+)?United\s+States\s+Code"
    r"|"
    r"(?P<title2>\d{1,2})\s+U\.?\s*S\.?\s*C\.?\s*§+\s*"
    r"(?P<section2>[0-9A-Za-z][0-9A-Za-z.\-]*)"
    r"(?P<subdivision2>(?:\([A-Za-z0-9ivxIVX]+\))*)"
    r")",
    re.IGNORECASE,
)

CHAPTER_ADD_PATTERN = re.compile(
    r"chapter\s+(?P<chapter>[0-9A-Za-z.-]+)\s+of\s+title\s+"
    r"(?P<title>\d{1,2})\s*,?\s*(?:of\s+the\s+)?United\s+States\s+Code"
    r"(?P<body>.{0,1200}?)(?:adding|add)\s+(?:at\s+the\s+end\s+)?"
    r"(?:the\s+following|a\s+new\s+section)",
    re.IGNORECASE | re.DOTALL,
)

NEW_SECTION_LINE = re.compile(
    r"(?:§+\s*|SEC(?:TION)?\.?\s+)(?P<section>[0-9A-Za-z][0-9A-Za-z.-]*)\s*[.\-—:]\s*(?P<heading>[^\n]{1,180})",
    re.IGNORECASE,
)

QUOTE_PAIR = r"[\"“](.*?)[\"”]"


class LegalAnalyzer:
    def __init__(self, repo: Path, package_root: Path, code_index: CodeIndex):
        self.repo = repo
        self.package_root = package_root
        self.code_index = code_index
        self.subject_map = json.loads((package_root / "config" / "subject_map.json").read_text(encoding="utf-8"))
        self.non_code_rules = json.loads((package_root / "config" / "non_code_rules.json").read_text(encoding="utf-8"))
        self.incorporated = code_index.incorporated_law_locations()

    def analyze(self, card: LawCard, source: SourceRecord) -> LawAnalysis:
        analysis = LawAnalysis(
            law_id=card.law_id,
            title=card.title,
            card_id=card.card_id,
            card_url=card.url,
            card_short_link=card.short_link,
            status=card.status,
            source_sha256=source.sha256,
            source_path=source.text_path,
            source_url=source.selected_url,
            source_characters=source.characters,
            duplicate_cards=card.duplicate_card_ids,
            warnings=list(source.warnings),
        )

        existing = self.incorporated.get(card.law_id, [])
        if existing:
            analysis.disposition = "ALREADY_INCORPORATED"
            analysis.confidence = "high"
            analysis.already_incorporated_locations = existing
            analysis.rationale = (
                "Project-generated U.S. Code material already contains this public law. "
                "The mass migration records and verifies the existing locations rather than duplicating it."
            )
            analysis.citation_links = [self.citation_url_from_identifier(value) for value in existing if self.citation_url_from_identifier(value)]
            # Still read the source when available.  A later law that is already
            # incorporated may expressly repeal or supersede an older unincorporated
            # law, and that relationship must participate in the dependency graph.
            if not source.error and source.text_path and Path(source.text_path).exists():
                existing_text = Path(source.text_path).read_text(encoding="utf-8")
                analysis.citations = self.extract_citations(existing_text)
                analysis.dependencies = self.extract_dependencies(card.law_id, existing_text)
                analysis.subject_tags, _ = self.subjects(card.title, existing_text)
            return analysis

        if card.status != "active":
            analysis.disposition = "NONOPERATIVE_OR_REPEALED"
            analysis.confidence = "high" if card.status in {"repealed", "rescinded", "failed", "expired", "superseded"} else "medium"
            analysis.rationale = (
                f"The canonical Trello record is classified as `{card.status}` based on "
                f"{'; '.join(card.status_evidence)}. It is not inserted as current Code text."
            )
            return analysis

        if source.error or not source.text_path:
            analysis.disposition = "SOURCE_UNAVAILABLE"
            analysis.confidence = "high"
            analysis.rationale = (
                "No readable authenticated enactment text could be recovered from the card, its attachments, "
                "or its description. The law is inventoried but cannot safely alter the Code."
            )
            analysis.warnings.append(source.error or "missing source text")
            return analysis

        text = Path(source.text_path).read_text(encoding="utf-8")
        analysis.citations = self.extract_citations(text)
        analysis.dependencies = self.extract_dependencies(card.law_id, text)
        analysis.subject_tags, subject_scores = self.subjects(card.title, text)
        scores = self.legal_character_scores(text)
        analysis.permanent_score = scores["permanent"]
        analysis.temporary_score = scores["temporary"]
        analysis.non_code_score = scores["non_code"]

        direct = self.parse_direct_operations(card, text)
        analysis.direct_amendment_score = sum(
            3 if operation.confidence == "high" else 2 if operation.confidence == "medium" else 1
            for operation in direct
        )

        non_code_category, non_code_evidence = self.non_code_category(card.title, text)
        mixed_appropriation = (
            non_code_category == "appropriation" and self.has_permanent_rider(text)
        )
        if non_code_category and not direct and not mixed_appropriation:
            analysis.disposition = "NON_CODE"
            analysis.confidence = "high" if non_code_category in {"constitutional", "appropriation", "appointment", "treaty", "private"} else "medium"
            analysis.rationale = (
                f"This enactment is classified as `{non_code_category}` rather than general and permanent U.S. Code material. "
                f"Evidence: {non_code_evidence}. It remains a public law but receives no Code insertion."
            )
            return analysis
        if mixed_appropriation:
            analysis.warnings.append(
                "The enactment contains concrete appropriations language and apparent permanent rider language; "
                "the complete enactment is preserved as a statutory note rather than discarding the rider."
            )

        # A freestanding enactment dominated by a definite sunset, expiration,
        # emergency window, or one-time implementation period ordinarily belongs
        # in the session-law archive rather than the general and permanent Code.
        if not direct and analysis.temporary_score >= max(8, analysis.permanent_score + 5):
            analysis.disposition = "NON_CODE"
            analysis.confidence = "medium"
            analysis.rationale = (
                "The enactment is predominantly temporary or self-expiring rather than general and permanent law "
                f"(temporary score {analysis.temporary_score}; permanent score {analysis.permanent_score}). "
                "It remains in the public-law archive and receives no Code insertion."
            )
            return analysis

        target_title, target_section, target_reason = self.choose_anchor(card, text, analysis.citations, subject_scores)
        analysis.target_title = target_title
        analysis.target_section = target_section

        if direct:
            analysis.operations.extend(direct)
            destructive = {"STRIKE_INSERT", "REPEAL_SECTION", "REPLACE_SECTION", "ADD_NEW_SECTION"}
            safe = [
                operation for operation in direct
                if operation.confidence == "high" and operation.kind in destructive
            ]
            unresolved = [
                operation for operation in direct
                if operation.confidence != "high" and operation.kind in destructive
            ]
            structural_notes = [operation for operation in direct if operation.kind == "APPEND_TEXT"]

            # Direct amendments do not necessarily exhaust an Act. Definitions,
            # effective dates, transition rules, severability clauses, and
            # freestanding duties can remain uncodified. Preserve the complete
            # authenticated enactment whenever those residual provisions are
            # likely, or whenever any destructive operation is not safely
            # executable.
            supplemental = self.needs_supplemental_note(text, direct) or bool(unresolved)
            if supplemental:
                analysis.operations.append(
                    self.note_operation(
                        card,
                        target_title,
                        target_section,
                        (
                            "The complete authenticated enactment is preserved as a statutory note so definitions, "
                            "effective dates, transition provisions, uncodified duties, and any non-executable "
                            "amendment instructions are not omitted from the consolidated record."
                        ),
                        confidence="high",
                    )
                )

            if supplemental or structural_notes or unresolved:
                analysis.disposition = "HYBRID_DIRECT_AMENDMENT_AND_STATUTORY_NOTE"
                analysis.confidence = "high"
                analysis.rationale = (
                    f"Detected {len(direct)} express Code operation(s): {len(safe)} safely executable text operation(s), "
                    f"{len(unresolved)} destructive operation(s) withheld from direct execution, and "
                    f"{len(structural_notes)} structurally ambiguous addition(s) preserved as targeted notes. "
                    f"The complete source is also preserved when necessary. Anchor selection: {target_reason}."
                )
            else:
                analysis.disposition = "DIRECT_CODE_AMENDMENT"
                analysis.confidence = "high"
                analysis.rationale = (
                    f"The enacted text contains {len(safe)} narrowly bounded, uniquely identifiable Code operation(s) "
                    "and no substantial residual provision requiring separate note treatment."
                )
            return analysis

        # General and permanent freestanding law. A statutory note is the correct
        # conservative classification when Congress did not assign a Code section.
        note = self.note_operation(
            card,
            target_title,
            target_section,
            (
                "The Act establishes continuing legal rights, duties, offices, procedures, or prohibitions but does not "
                "provide a uniquely executable positive-law placement. Its full operative text is classified as a statutory note."
            ),
            confidence="high" if analysis.permanent_score >= analysis.temporary_score else "medium",
        )
        analysis.operations.append(note)
        analysis.disposition = "STATUTORY_NOTE"
        analysis.confidence = note.confidence
        analysis.rationale = (
            f"No express, uniquely executable Code amendment was found. The enactment appears general and permanent "
            f"(permanent score {analysis.permanent_score}; temporary score {analysis.temporary_score}) and is therefore "
            f"preserved as a statutory note at {target_title} U.S.C. § {target_section}. Anchor selection: {target_reason}."
        )
        return analysis

    @staticmethod
    def needs_supplemental_note(text: str, operations: list[Operation]) -> bool:
        lower = text.lower()
        residual_markers = (
            "effective date", "definitions", "severability",
            "rule of construction", "applicability", "transition",
            "implementation", "authorization of appropriations",
            "report to congress", "regulations", "short title",
        )
        if any(marker in lower for marker in residual_markers):
            return True
        internal_sections = len(
            re.findall(r"(?im)^\s*(?:SEC(?:TION)?\.?)\s+\d+[A-Za-z]?\s*[.\-—:]", text)
        )
        represented = sum(
            len(operation.source_block) + len(operation.old_text) + len(operation.new_text)
            for operation in operations
        )
        if internal_sections > max(1, len(operations)):
            return True
        return len(text) > max(3500, represented + 1500)

    def extract_citations(self, text: str) -> list[CodeCitation]:
        found: list[CodeCitation] = []
        seen: set[tuple[int, str, int]] = set()
        for pattern in CITATION_PATTERNS:
            for match in pattern.finditer(text):
                title = int(match.group("title"))
                section = match.group("section").rstrip(".,;:)")
                key = (title, section, match.start())
                if key in seen:
                    continue
                seen.add(key)
                found.append(CodeCitation(title, section, match.group(0), match.start(), match.end()))
        found.sort(key=lambda value: value.start)
        return found

    def extract_dependencies(self, law_id: str, text: str) -> list[Dependency]:
        """Extract later-law relationships without treating a distant verb as dispositive.

        Public-law documents often discuss several enactments in the same
        paragraph.  A broad context search can therefore falsely conclude that
        one law repeals another.  The patterns below require the operative verb
        immediately before or after the cited law number.
        """
        dependencies: list[Dependency] = []
        seen: set[tuple[str, str]] = set()
        for match in LAW_RE.finditer(text):
            target = f"PL-{int(match.group('congress')):03d}-{int(match.group('number')):03d}"
            if target == law_id:
                continue
            before = normalize_whitespace(text[max(0, match.start() - 260) : match.start()])
            after = normalize_whitespace(text[match.end() : match.end() + 260])
            left = before.lower()
            right = after.lower()
            context = normalize_whitespace(before + " " + match.group(0) + " " + after)

            repeal_before = re.search(
                r"(?:hereby\s+)?(?:repeals?|repealing|repeal\s+of)"
                r"(?:\s+(?:all|the|title[s]?|section[s]?|provisions?|amendments?))*"
                r"(?:\s+(?:of|made\s+by|contained\s+in))*\s*$",
                left[-180:],
            )
            repeal_after = re.match(
                r"^\s*(?:,|;)?\s*(?:and\s+)?(?:is|are|shall\s+be)\s+"
                r"(?:hereby\s+)?repealed\b",
                right[:180],
            )
            supersede_before = re.search(
                r"(?:supersedes?|replaces?|replacement\s+for)\s*$", left[-120:]
            )
            supersede_after = re.match(
                r"^\s*(?:,|;)?\s*(?:is|are)\s+(?:hereby\s+)?"
                r"(?:superseded|replaced)\b",
                right[:160],
            )
            amend_before = re.search(
                r"(?:amends?|amending|amendment\s+to)\s*$", left[-120:]
            )
            amend_after = re.match(
                r"^\s*(?:,|;)?\s*(?:is|are)\s+(?:hereby\s+)?amended\b",
                right[:160],
            )
            override_before = re.search(
                r"notwithstanding(?:\s+any\s+provision\s+of)?\s*$", left[-160:]
            )

            if repeal_before or repeal_after:
                relation, confidence = "repeals", "high"
            elif supersede_before or supersede_after:
                relation, confidence = "supersedes", "high"
            elif amend_before or amend_after:
                relation, confidence = "amends", "medium"
            elif override_before:
                relation, confidence = "overrides", "medium"
            else:
                relation, confidence = "references", "low"

            key = (target, relation)
            if key not in seen:
                seen.add(key)
                dependencies.append(
                    Dependency(law_id, target, relation, context[:700], confidence)
                )
        return dependencies

    def subjects(self, title: str, text: str) -> tuple[list[str], dict[str, int]]:
        corpus = f"{title}\n{text[:16000]}".lower()
        scores: dict[str, int] = {}
        for subject, config in self.subject_map.items():
            score = 0
            for keyword in config.get("keywords", []):
                count = corpus.count(keyword.lower())
                if count:
                    score += min(12, count * (5 if " " in keyword else 3))
            if score:
                scores[subject] = score
        ordered = [name for name, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]
        return ordered[:8], scores

    def legal_character_scores(self, text: str) -> dict[str, int]:
        lower = text.lower()
        permanent = 0
        temporary = 0
        non_code = 0
        for phrase, weight in {
            "shall": 1,
            "may not": 3,
            "is prohibited": 4,
            "is established": 4,
            "there is established": 5,
            "shall have authority": 4,
            "offense": 2,
            "penalty": 2,
            "judicial review": 3,
            "cause of action": 4,
            "shall appoint": 2,
        }.items():
            permanent += min(20, lower.count(phrase) * weight)
        for phrase, weight in {
            "expires": 5,
            "sunset": 5,
            "fiscal year": 3,
            "for a period of": 2,
            "days after enactment": 2,
            "temporary": 3,
            "emergency period": 3,
            "until the date": 2,
        }.items():
            temporary += min(20, lower.count(phrase) * weight)
        for category, phrases in self.non_code_rules.items():
            for phrase in phrases:
                if phrase.lower() in lower:
                    non_code += 5
        return {"permanent": permanent, "temporary": temporary, "non_code": non_code}

    @staticmethod
    def has_permanent_rider(text: str) -> bool:
        lower = text.lower()
        strong = (
            "is established", "there is established", "may not", "is prohibited",
            "judicial review", "cause of action", "shall have authority",
            "united states code", "is amended", "shall promulgate regulations",
        )
        return sum(1 for marker in strong if marker in lower) >= 2

    def non_code_category(self, title: str, text: str) -> tuple[str, str]:
        lower = f"{title}\n{text}".lower()
        best = ("", "")
        for category, phrases in self.non_code_rules.items():
            matches = [phrase for phrase in phrases if phrase.lower() in lower]
            if matches:
                # Appropriations classification requires a concrete fiscal or money
                # indicator so a permanent program authorization is not discarded.
                if category == "appropriation" and not (
                    re.search(r"\$\s*\d", text) or "fiscal year" in lower or "appropriated, out of" in lower
                ):
                    continue
                return category, ", ".join(matches[:5])
        return best

    def parse_direct_operations(self, card: LawCard, text: str) -> list[Operation]:
        operations: list[Operation] = []
        occupied: set[tuple] = set()

        # Explicit creation of a section in a named Code chapter.  Internal Act
        # section numbers are never treated as Code section numbers unless this
        # chapter/title formula is present.
        for match in CHAPTER_ADD_PATTERN.finditer(text):
            title = int(match.group("title"))
            chapter = match.group("chapter")
            block = self._following_block(text, match.end(), 12000)
            section_match = NEW_SECTION_LINE.search(block)
            if not section_match:
                continue
            section = section_match.group("section").rstrip(".")
            heading = section_match.group("heading").strip(" .—-")
            source_block = block[section_match.start() :].strip()
            confidence = (
                "high"
                if self.code_index.chapter_exists(title, chapter)
                and not self.code_index.section_exists(title, section)
                and len(source_block) >= 40
                else "medium"
            )
            key = ("ADD_NEW_SECTION", title, section)
            if key not in occupied:
                occupied.add(key)
                operations.append(
                    Operation(
                        kind="ADD_NEW_SECTION",
                        title=title,
                        section=section,
                        chapter=chapter,
                        target_identifier=f"/us/usc/t{title}/ch{chapter}",
                        source_block=source_block,
                        new_text=heading,
                        rationale=(
                            f"The Act expressly directs that chapter {chapter} of title {title} be amended by adding "
                            f"new § {section}."
                        ),
                        confidence=confidence,
                        output_identifier=f"/us/usc/t{title}/s{section}",
                    )
                )

        for match in TARGET_PATTERN.finditer(text):
            title = int(match.group("title1") or match.group("title2"))
            section = (match.group("section1") or match.group("section2")).rstrip(".,;:")
            explicit_subdivision = match.group("subdivision1") or match.group("subdivision2") or ""
            identifier = f"/us/usc/t{title}/s{section}"
            window = text[match.start() : min(len(text), match.end() + 10000)]
            end_boundary = re.search(
                r"(?im)^\s*(?:SEC(?:TION)?\.?)\s+\d+[A-Za-z]?\s*[.\-—:]",
                window[100:],
            )
            if end_boundary:
                window = window[: 100 + end_boundary.start()]
            relative_end = match.end() - match.start()
            after_target = window[relative_end:]
            immediate = after_target[:700]

            # Require the target citation itself to be followed by the operative
            # amendatory verb.  Merely citing a section somewhere in a law cannot
            # authorize a text change.
            verb = re.search(
                r"^[^.;]{0,300}?\b(?P<verb>is|are)\s+(?:hereby\s+)?"
                r"(?P<action>amended|repealed)\b",
                immediate,
                re.IGNORECASE | re.DOTALL,
            )
            if not verb:
                continue

            prefix = immediate[: verb.start()]
            subdivision_target = bool(
                explicit_subdivision
                or re.search(
                    r"(?:^\s*\([A-Za-z0-9ivxIVX]+\)|\b(?:subsection|paragraph|subparagraph|clause|item)\b)",
                    prefix,
                    re.IGNORECASE,
                )
            )
            action = verb.group("action").lower()

            if action == "repealed":
                if subdivision_target:
                    key = ("APPEND_TEXT", title, section, "subdivision-repeal")
                    if key not in occupied:
                        occupied.add(key)
                        operations.append(
                            Operation(
                                kind="APPEND_TEXT",
                                title=title,
                                section=section,
                                target_identifier=identifier,
                                source_block=window.strip(),
                                rationale=(
                                    f"The Act expressly repeals a subdivision of {title} U.S.C. § {section}; "
                                    "flat source extraction does not prove the USLM nesting, so the exact instruction "
                                    "is preserved as a target-specific controlling note."
                                ),
                                confidence="medium",
                            )
                        )
                else:
                    key = ("REPEAL_SECTION", title, section)
                    if key not in occupied:
                        occupied.add(key)
                        operations.append(
                            Operation(
                                kind="REPEAL_SECTION",
                                title=title,
                                section=section,
                                target_identifier=identifier,
                                rationale=f"The Act expressly repeals {title} U.S.C. § {section}.",
                                confidence="high" if self.code_index.section_exists(title, section) else "medium",
                            )
                        )
                continue

            # Every exact quoted strike/insert pair can be independently applied
            # when its old phrase is unique in the target section.
            strike_matches = list(
                re.finditer(
                    r"striking\s+[\"“](?P<old>.*?)[\"”]\s+and\s+inserting\s+"
                    r"(?:in\s+lieu\s+thereof\s+)?[\"“](?P<new>.*?)[\"”]",
                    window,
                    re.IGNORECASE | re.DOTALL,
                )
            )
            for strike in strike_matches:
                old = normalize_whitespace(strike.group("old"))
                new_text = normalize_whitespace(strike.group("new"))
                if not old or len(old) > 4000 or len(new_text) > 8000:
                    continue
                key = ("STRIKE_INSERT", title, section, old, new_text)
                if key in occupied:
                    continue
                occupied.add(key)
                operations.append(
                    Operation(
                        kind="STRIKE_INSERT",
                        title=title,
                        section=section,
                        target_identifier=identifier,
                        old_text=old,
                        new_text=new_text,
                        rationale=f"The Act expressly directs a quoted strike-and-insert amendment to {title} U.S.C. § {section}.",
                        confidence="high" if self.code_index.section_exists(title, section) else "medium",
                    )
                )

            replace = re.search(
                r"\b(?:is\s+amended\s+)?(?:to\s+read|by\s+striking\s+.*?and\s+inserting)"
                r"\s+as\s+follows\s*[:—-]",
                window,
                re.IGNORECASE | re.DOTALL,
            )
            if replace and not subdivision_target:
                source_block = window[replace.end() :].strip().strip('\"“”')
                heading_match = NEW_SECTION_LINE.search(source_block[:700])
                heading_matches_target = bool(
                    heading_match
                    and heading_match.group("section").rstrip(".") == section
                )
                key = ("REPLACE_SECTION", title, section)
                if source_block and key not in occupied:
                    occupied.add(key)
                    operations.append(
                        Operation(
                            kind="REPLACE_SECTION",
                            title=title,
                            section=section,
                            target_identifier=identifier,
                            source_block=source_block,
                            rationale=f"The Act expressly restates {title} U.S.C. § {section} in full.",
                            confidence=(
                                "high"
                                if self.code_index.section_exists(title, section)
                                and heading_matches_target
                                and 80 <= len(source_block) <= 30000
                                else "medium"
                            ),
                        )
                    )
                continue

            # Added subsections/paragraphs are not flattened into guessed USLM.
            # Preserve the exact target-specific instruction as a controlling note.
            add = re.search(
                r"\bby\s+(?:adding|inserting)\s+(?:at\s+the\s+end\s+)?"
                r"(?:the\s+following|after\s+[^:]{1,300}\s+the\s+following)\s*[:—-]",
                window,
                re.IGNORECASE | re.DOTALL,
            )
            if add:
                source_block = window[add.end() :].strip().strip('\"“”')
                key = ("APPEND_TEXT", title, section, sha256_text(source_block)[:16])
                if source_block and key not in occupied:
                    occupied.add(key)
                    operations.append(
                        Operation(
                            kind="APPEND_TEXT",
                            title=title,
                            section=section,
                            target_identifier=identifier,
                            source_block=source_block,
                            rationale=f"The Act expressly adds text to {title} U.S.C. § {section}.",
                            confidence="medium",
                        )
                    )

        return operations

    @staticmethod
    def _following_block(text: str, start: int, limit: int) -> str:
        block = text[start : min(len(text), start + limit)]
        boundary = re.search(r"(?im)^\s*(?:SEC(?:TION)?\.?)\s+\d+[A-Za-z]?\s*[.\-—:]", block[120:])
        if boundary:
            block = block[: 120 + boundary.start()]
        return block.strip().strip('"“”')

    def choose_anchor(
        self,
        card: LawCard,
        text: str,
        citations: list[CodeCitation],
        subject_scores: dict[str, int],
    ) -> tuple[int, str, str]:
        counts: Counter[tuple[int, str]] = Counter()
        for citation in citations:
            if self.code_index.section_exists(citation.title, citation.section):
                counts[(citation.title, citation.section)] += 1
        if counts:
            (title, section), count = counts.most_common(1)[0]
            return title, section, f"the Act expressly cites this existing Code section {count} time(s)"

        ranked_subjects = sorted(subject_scores.items(), key=lambda item: item[1], reverse=True)
        query = f"{card.title}\n{text[:12000]}"
        for subject, score in ranked_subjects:
            config = self.subject_map[subject]
            if config.get("non_code"):
                continue
            for title in config.get("titles", []):
                if not self.code_index.title_exists(int(title)):
                    continue
                best = self.code_index.best_section(int(title), query, [str(value) for value in config.get("defaults", [])])
                if best:
                    return int(title), best["section"], f"subject classification `{subject}` (score {score}) and closest existing section heading `{best['heading']}`"

        # An uncited general federal statute is placed under Title 1's first
        # available section rather than inventing a positive-law section number.
        best = self.code_index.best_section(1, query, ["1"])
        if best:
            return 1, best["section"], "general federal-law fallback; no more specific title was supported"
        # Every normal U.S. Code repository has Title 1, but retain a deterministic
        # last resort for damaged corpora.
        for title in range(1, 55):
            if self.code_index.title_exists(title):
                sections = self.code_index.index_title(title)
                if sections:
                    return title, sections[0]["section"], "first available Code section fallback"
        raise RuntimeError("No U.S. Code sections were available for statutory-note placement")

    @staticmethod
    def note_operation(
        card: LawCard,
        title: int,
        section: str,
        rationale: str,
        confidence: str = "high",
    ) -> Operation:
        return Operation(
            kind="STATUTORY_NOTE",
            title=title,
            section=section,
            target_identifier=f"/us/usc/t{title}/s{section}",
            rationale=rationale,
            confidence=confidence,
        )

    @staticmethod
    def citation_url_from_identifier(identifier: str) -> str:
        match = re.search(r"/us/usc/t(\d+)/s([^/]+)", identifier)
        if not match:
            return ""
        return f"https://nationalarchivesusar.github.io/us-code/cite/{int(match.group(1))}/{match.group(2)}/"


def apply_dependency_overrides(analyses: list[LawAnalysis]) -> None:
    by_id = {analysis.law_id: analysis for analysis in analyses}
    for analysis in sorted(analyses, key=lambda item: law_sort_key(item.law_id), reverse=True):
        if analysis.status != "active" or analysis.disposition in {"NONOPERATIVE_OR_REPEALED", "SOURCE_UNAVAILABLE"}:
            continue
        for dependency in analysis.dependencies:
            if dependency.relation not in {"repeals", "supersedes"}:
                continue
            target = by_id.get(dependency.target_law_id)
            if not target:
                continue
            if law_sort_key(analysis.law_id) <= law_sort_key(target.law_id):
                analysis.warnings.append(
                    f"Ignored apparent {dependency.relation} relationship to {target.law_id} because the cited law is not earlier in enactment order."
                )
                continue
            if target.disposition == "ALREADY_INCORPORATED":
                target.warnings.append(
                    f"Later {analysis.law_id} {dependency.relation} this already-incorporated law; reversal audit required."
                )
                continue
            target.disposition = "SUPERSEDED_BEFORE_CODIFICATION"
            target.confidence = dependency.confidence
            target.rationale = (
                f"No current Code insertion is made because {analysis.law_id} {dependency.relation} this law. "
                f"Evidence: {dependency.evidence}"
            )
            target.operations.clear()
