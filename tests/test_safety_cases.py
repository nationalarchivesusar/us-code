from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lib.apply_engine import MassApplier
from lib.codebase import CodeIndex, validate_xml
from lib.legal_analysis import LegalAnalyzer, apply_dependency_overrides
from lib.model import LawCard, SourceRecord

PACKAGE = Path(__file__).resolve().parents[1]


def section(title: int, number: str, body: str, notes: str = "") -> str:
    return (
        f'<section xmlns="http://xml.house.gov/schemas/uslm/1.0" '
        f'identifier="/us/usc/t{title}/s{number}" id="s-{title}-{number}">'
        f'<num value="{number}">§ {number}.</num><heading>Test {number}</heading>'
        f'<chapeau><p>{body}</p></chapeau><sourceCredit><p>Original.</p></sourceCredit>'
        f'{notes}</section>'
    ).replace(' xmlns="http://xml.house.gov/schemas/uslm/1.0"', '', 1)


def make_title(title: int, sections: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<uscDoc xmlns="http://xml.house.gov/schemas/uslm/1.0" identifier="/us/usc/t{title}">
<meta><docNumber>{title}</docNumber></meta><main><title identifier="/us/usc/t{title}">
<num value="{title}">Title {title}</num><heading>TEST</heading>
<chapter identifier="/us/usc/t{title}/ch1" id="ch-{title}-1"><num value="1">CHAPTER 1</num>
<heading>TEST</heading><toc><layout/></toc>{sections}</chapter></title></main></uscDoc>'''


def card(law_id: str, title: str, text: str, status: str = "active") -> LawCard:
    congress, number = [int(value) for value in law_id.replace("PL-", "").split("-")]
    return LawCard(
        card_id=law_id, short_link=law_id, name=f"Public Law {congress}-{number} | {title}",
        description=text, list_name="Active Public Laws", labels=[],
        url=f"https://trello.com/c/{law_id}", closed=False,
        last_activity="2026-01-01T00:00:00Z", law_id=law_id,
        congress=congress, law_number=number, title=title, status=status,
    )


class SafetyCases(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="mass-safety-"))
        self.repo = self.root / "repo"
        (self.repo / "usc").mkdir(parents=True)
        (self.repo / "tools").mkdir()
        (self.repo / "codification").mkdir()
        title1 = make_title(1, section(1, "1", "General law."))
        # Primary PL 50-20 note mentions PL 10-1 in reproduced source text.  The
        # older referenced law must not be mistaken for already incorporated.
        note = (
            '<notes type="uscNote"><note id="rp-primary">'
            '<p><ref href="/us/pl/50/20">Pub. L. 50–20</ref> repeals Public Law 10-1.</p>'
            '</note></notes>'
        )
        title18 = make_title(
            18,
            section(18, "1001", "A person shall be fined.", note)
            + section(18, "1002", "A person shall be imprisoned."),
        )
        for title, text in ((1, title1), (18, title18)):
            path = self.repo / "usc" / f"usc{title:02d}.xml"
            path.write_text(text, encoding="utf-8")
            validate_xml(path)
        self.workspace = self.repo / "codification" / "mass_migration" / "latest"
        (self.workspace / "sources" / "text").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def source(self, law_id: str, text: str) -> SourceRecord:
        path = self.workspace / "sources" / "text" / f"{law_id}.txt"
        path.write_text(text, encoding="utf-8")
        return SourceRecord(
            law_id=law_id, selected_url=f"https://example.test/{law_id}",
            selected_name=f"{law_id}.txt", text_path=str(path), sha256="b" * 64,
            characters=len(text), score=100,
        )

    def test_primary_incorporation_reference_only(self):
        locations = CodeIndex(self.repo).incorporated_law_locations()
        self.assertIn("PL-050-020", locations)
        self.assertNotIn("PL-010-001", locations)

    def test_already_incorporated_later_law_suppresses_older(self):
        older = card(
            "PL-010-001", "Old Framework Act",
            "Public Law 10-1. Be it enacted. There is established a continuing framework. The agency shall act and shall report.",
        )
        later = card(
            "PL-050-020", "Replacement Act",
            "Public Law 50-20. Be it enacted. Public Law 10-1 is hereby repealed. The agency shall implement replacement rules and shall publish guidance.",
        )
        sources = {
            older.law_id: self.source(older.law_id, older.description),
            later.law_id: self.source(later.law_id, later.description),
        }
        analyzer = LegalAnalyzer(self.repo, PACKAGE, CodeIndex(self.repo))
        analyses = [analyzer.analyze(older, sources[older.law_id]), analyzer.analyze(later, sources[later.law_id])]
        self.assertEqual(analyses[1].disposition, "ALREADY_INCORPORATED")
        apply_dependency_overrides(analyses)
        self.assertEqual(analyses[0].disposition, "SUPERSEDED_BEFORE_CODIFICATION")

    def test_subdivision_repeal_is_not_section_repeal(self):
        law = card(
            "PL-050-021", "Limited Repeal Act",
            "Public Law 50-21. Be it enacted. Section 1002(a) of title 18, United States Code, is repealed. The Attorney General shall publish notice and shall preserve records.",
        )
        source = self.source(law.law_id, law.description)
        analysis = LegalAnalyzer(self.repo, PACKAGE, CodeIndex(self.repo)).analyze(law, source)
        self.assertTrue(any(op.kind == "APPEND_TEXT" for op in analysis.operations))
        self.assertFalse(any(op.kind == "REPEAL_SECTION" for op in analysis.operations))
        applier = MassApplier(
            self.repo, self.workspace, CodeIndex(self.repo), {law.law_id: law},
            {law.law_id: source}, [analysis],
        )
        applier.apply()
        updated = (self.repo / "usc" / "usc18.xml").read_text(encoding="utf-8")
        self.assertIn("A person shall be imprisoned.", updated)
        self.assertIn("USAR Targeted Amendment", updated)

    def test_repository_check_failure_restores_title_and_new_state(self):
        law = card(
            "PL-050-022", "Records Duty Act",
            "Public Law 50-22. Be it enacted. There is established a records duty. The agency shall preserve records and shall publish reports.",
        )
        source = self.source(law.law_id, law.description)
        analysis = LegalAnalyzer(self.repo, PACKAGE, CodeIndex(self.repo)).analyze(law, source)
        before = (self.repo / "usc" / "usc01.xml").read_text(encoding="utf-8")
        # Required-if-present repository check deliberately fails after titles and
        # state have been written, exercising the rollback path.
        (self.repo / "tools" / "check_encoding.py").write_text(
            "raise SystemExit(7)\n", encoding="utf-8"
        )
        applier = MassApplier(
            self.repo, self.workspace, CodeIndex(self.repo), {law.law_id: law},
            {law.law_id: source}, [analysis],
        )
        with self.assertRaises(RuntimeError):
            applier.apply()
        self.assertEqual(before, (self.repo / "usc" / "usc01.xml").read_text(encoding="utf-8"))
        self.assertFalse((self.repo / "codification" / "state.json").exists())


if __name__ == "__main__":
    unittest.main()
