from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Attachment:
    id: str = ""
    name: str = ""
    url: str = ""
    mime_type: str = ""
    date: str = ""
    is_upload: bool = False
    source: str = "board"


@dataclass
class LawCard:
    card_id: str
    short_link: str
    name: str
    description: str
    list_name: str
    labels: list[str]
    url: str
    closed: bool
    last_activity: str
    attachments: list[Attachment] = field(default_factory=list)
    law_id: str = ""
    congress: int | None = None
    law_number: int | None = None
    title: str = ""
    status: str = "unknown"
    status_evidence: list[str] = field(default_factory=list)
    duplicate_card_ids: list[str] = field(default_factory=list)
    duplicate_card_records: list[dict[str, str]] = field(default_factory=list)
    alternate_descriptions: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceRecord:
    law_id: str
    selected_path: str = ""
    selected_url: str = ""
    selected_name: str = ""
    text_path: str = ""
    sha256: str = ""
    characters: int = 0
    score: float = 0.0
    identity_matches: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CodeCitation:
    title: int
    section: str
    raw: str
    start: int = 0
    end: int = 0

    @property
    def identifier(self) -> str:
        return f"/us/usc/t{self.title}/s{self.section}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Dependency:
    source_law_id: str
    target_law_id: str
    relation: str
    evidence: str
    confidence: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Operation:
    kind: str
    title: int | None = None
    section: str = ""
    chapter: str = ""
    target_identifier: str = ""
    old_text: str = ""
    new_text: str = ""
    source_block: str = ""
    rationale: str = ""
    confidence: str = "medium"
    status: str = "planned"
    output_identifier: str = ""
    citation_url: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LawAnalysis:
    law_id: str
    title: str
    card_id: str
    card_url: str
    card_short_link: str
    status: str
    disposition: str = "UNANALYZED"
    rationale: str = ""
    confidence: str = "low"
    source_sha256: str = ""
    source_path: str = ""
    source_url: str = ""
    source_characters: int = 0
    citations: list[CodeCitation] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    operations: list[Operation] = field(default_factory=list)
    target_title: int | None = None
    target_section: str = ""
    subject_tags: list[str] = field(default_factory=list)
    permanent_score: int = 0
    temporary_score: int = 0
    non_code_score: int = 0
    direct_amendment_score: int = 0
    already_incorporated_locations: list[str] = field(default_factory=list)
    duplicate_cards: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    applied: bool = False
    changed_files: list[str] = field(default_factory=list)
    citation_links: list[str] = field(default_factory=list)
    trello_comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data
