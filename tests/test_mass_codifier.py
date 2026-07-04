from __future__ import annotations

import json
import shutil
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from lib.apply_engine import MassApplier
from lib.codebase import CodeIndex, validate_xml
from lib.legal_analysis import LegalAnalyzer
from lib.model import Attachment, LawCard, SourceRecord
from lib.reports import write_all_reports
from lib.sources import SourceManager
from lib.trello import canonicalize_cards, parse_cards


TITLE_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<uscDoc xmlns="http://xml.house.gov/schemas/uslm/1.0" identifier="/us/usc/t{title}">
<meta><docNumber>{title}</docNumber></meta>
<main><title identifier="/us/usc/t{title}"><num value="{title}">Title {title}</num><heading>TEST</heading>
{chapters}
</title></main></uscDoc>
'''

CHAPTER = '''<chapter identifier="/us/usc/t{title}/ch{chapter}" id="ch-{title}-{chapter}">
<num value="{chapter}">CHAPTER {chapter}</num><heading>TEST CHAPTER</heading>
<toc><layout>{toc}</layout></toc>{sections}</chapter>'''

SECTION = '''<section identifier="/us/usc/t{title}/s{section}" id="s-{title}-{section}">
<num value="{section}">§ {section}.</num><heading>{heading}</heading>
<chapeau><p>{body}</p></chapeau>
<sourceCredit><p>Original source.</p></sourceCredit>
</section>'''


def card(law_id: str, title: str, description: str, status: str = "active") -> LawCard:
    congress, number = [int(x) for x in law_id.replace("PL-", "").split("-")]
    return LawCard(
        card_id=law_id,
        short_link=law_id,
        name=f"Public Law {congress}-{number} | {title}",
        description=description,
        list_name="Active Public Laws" if status == "active" else status.title(),
        labels=[] if status == "active" else [status.title()],
        url=f"https://trello.com/c/{law_id}",
        closed=False,
        last_activity="2026-01-01T00:00:00Z",
        attachments=[],
        law_id=law_id,
        congress=congress,
        law_number=number,
        title=title,
        status=status,
    )


class MassCodifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="mass-codifier-test-"))
        self.repo = self.temp / "repo"
        (self.repo / "usc").mkdir(parents=True)
        (self.repo / "tools").mkdir()
        (self.repo / "codification").mkdir()

        title1 = TITLE_TEMPLATE.format(
            title=1,
            chapters=CHAPTER.format(
                title=1,
                chapter=1,
                toc='<tocItem><column><ref href="/us/usc/t1/s1">1</ref></column></tocItem>',
                sections=SECTION.format(title=1, section="1", heading="Words denoting number", body="General law."),
            ),
        )
        title5 = TITLE_TEMPLATE.format(
            title=5,
            chapters=CHAPTER.format(
                title=5,
                chapter=3,
                toc='<tocItem><column><ref href="/us/usc/t5/s301">301</ref></column></tocItem>',
                sections=SECTION.format(title=5, section="301", heading="Departmental regulations", body="The head of an Executive department may prescribe regulations."),
            ),
        )
        already_note = (
            '<notes type="uscNote"><note id="rp-existing"><p>'
            '<ref href="/us/pl/40/6">Pub. L. 40–6</ref> existing.'
            '</p></note></notes>'
        )
        sections18 = (
            SECTION.format(title=18, section="1001", heading="Statements or entries generally", body="whoever knowingly makes a false statement shall be fined")
            + SECTION.format(title=18, section="3551", heading="Authorized sentences", body="A defendant shall be sentenced in accordance with this chapter.").replace("</section>", already_note + "</section>")
        )
        title18 = TITLE_TEMPLATE.format(
            title=18,
            chapters=CHAPTER.format(
                title=18,
                chapter=47,
                toc=(
                    '<tocItem><column><ref href="/us/usc/t18/s1001">1001</ref></column></tocItem>'
                    '<tocItem><column><ref href="/us/usc/t18/s3551">3551</ref></column></tocItem>'
                ),
                sections=sections18,
            ),
        )
        for title, value in [(1, title1), (5, title5), (18, title18)]:
            path = self.repo / "usc" / f"usc{title:02d}.xml"
            path.write_text(value, encoding="utf-8")
            validate_xml(path)

        self.workspace = self.repo / "codification" / "mass_migration" / "latest"
        (self.workspace / "sources" / "text").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.temp)

    def source(self, law_id: str, text: str) -> SourceRecord:
        path = self.workspace / "sources" / "text" / f"{law_id}.txt"
        path.write_text(text, encoding="utf-8")
        return SourceRecord(
            law_id=law_id,
            selected_path=str(path),
            selected_url=f"https://example.test/{law_id}",
            selected_name=f"{law_id}.txt",
            text_path=str(path),
            sha256="a" * 64,
            characters=len(text),
            score=100,
        )


    def test_board_canonicalization_and_description_source(self):
        board = {
            "lists": [
                {"id": "active", "name": "Active Public Laws"},
                {"id": "repealed", "name": "Repealed"},
            ],
            "cards": [
                {
                    "id": "a1", "shortLink": "A1",
                    "name": "Public Law 41-7 | Accurate Records Act",
                    "desc": "Public Law 41-7 active canonical record; enactment text is retained on the older duplicate card.",
                    "idList": "active", "labels": [], "closed": False,
                    "dateLastActivity": "2026-01-02T00:00:00Z", "attachments": [],
                },
                {
                    "id": "a2", "shortLink": "A2",
                    "name": "Public Law 41-7 | Old Duplicate",
                    "desc": "Public Law 41-7. Be it enacted. SECTION 1. There is established a records office. The office shall preserve public records. SECTION 2. The office shall issue annual reports and may promulgate regulations necessary to carry out this Act.",
                    "idList": "repealed", "labels": [{"name": "Repealed"}], "closed": False,
                    "dateLastActivity": "2026-02-02T00:00:00Z", "attachments": [],
                },
            ],
        }
        parsed = parse_cards(board)
        canonical, duplicates = canonicalize_cards(parsed)
        self.assertEqual(len(canonical), 1)
        self.assertEqual(canonical[0].status, "active")
        self.assertEqual(canonical[0].law_id, "PL-041-007")
        self.assertIn("PL-041-007", duplicates)
        manager = SourceManager(self.workspace)
        record = manager.process(canonical[0])
        self.assertFalse(record.error)
        self.assertGreater(record.characters, 100)
        self.assertIn("public-law number", record.identity_matches)
        self.assertTrue(record.selected_name.startswith("Duplicate card description:"))
        analysis = LegalAnalyzer(self.repo, PACKAGE, CodeIndex(self.repo)).analyze(canonical[0], record)
        write_all_reports(
            self.workspace,
            {canonical[0].law_id: canonical[0]},
            {canonical[0].law_id: record},
            [analysis],
        )
        comments = json.loads(
            (self.workspace / "reports" / "TRELLO-COMMENTS.json").read_text(encoding="utf-8")
        )["comments"]
        self.assertEqual(len(comments), 2)
        self.assertEqual(comments[0]["record_type"], "canonical")
        self.assertEqual(comments[1]["record_type"], "duplicate")
        self.assertTrue((self.workspace / "reports" / "DUPLICATE-CARD-REGISTER.md").exists())


    def test_full_cli_pipeline_and_repository_repair(self):
        (self.repo / "README.md").write_text("# Final Public-Law Implementation\nwrong readme\n", encoding="utf-8")
        (self.repo / "FINISH_PUBLIC_LAWS.bat").write_text("old package", encoding="utf-8")
        (self.repo / ".gitignore").write_text("/codification/\n", encoding="utf-8")
        board = {
            "lists": [{"id": "active", "name": "Active Public Laws"}],
            "cards": [
                {
                    "id": "c1", "shortLink": "C1",
                    "name": "Public Law 42-1 | Executive Records Office Act",
                    "desc": (
                        "Public Law 42-1. Be it enacted. There is established in the executive branch "
                        "an Executive Records Office. The Office shall preserve records, issue regulations, "
                        "and submit an annual public report. This Act shall apply to every executive department."
                    ),
                    "idList": "active", "labels": [], "closed": False,
                    "dateLastActivity": "2026-01-01T00:00:00Z", "attachments": [],
                }
            ],
        }
        board_path = self.temp / "board.json"
        board_path.write_text(json.dumps(board), encoding="utf-8")
        proc = subprocess.run(
            [
                sys.executable, str(PACKAGE / "mass_codifier.py"),
                "--repo", str(self.repo),
                "--board-json", str(board_path),
                "--apply", "--repair-repo",
                "--minimum-decisions", "1",
                "--max-source-holds", "0",
            ],
            text=True, capture_output=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)
        report_root = self.repo / "codification" / "mass_migration" / "latest" / "reports"
        self.assertTrue((report_root / "MASTER-CODIFICATION-REPORT.md").exists())
        for name in (
            "SOURCE-AUDIT.csv", "OPERATION-REGISTER.csv", "CODE-LOCATION-REGISTER.csv",
            "NON-CODE-REGISTER.md", "NONOPERATIVE-REGISTER.md",
            "ALREADY-INCORPORATED-REGISTER.md", "DUPLICATE-CARD-REGISTER.md",
            "TRELLO-COMMENTS.json", "APPLIED-MANIFEST.json",
        ):
            self.assertTrue((report_root / name).exists(), name)
        self.assertFalse((self.repo / "FINISH_PUBLIC_LAWS.bat").exists())
        self.assertTrue((self.repo / "README.md").read_text(encoding="utf-8").startswith("# United States Code Library"))
        self.assertIn("Executive Records Office Act", (self.repo / "usc" / "usc05.xml").read_text(encoding="utf-8"))

    def test_classification_and_application(self):
        cards = {
            "PL-040-001": card(
                "PL-040-001",
                "Truthful Statements Act",
                'Public Law 40-1. Be it enacted. Section 1001 of title 18, United States Code, is amended by striking "shall be fined" and inserting "shall be fined or imprisoned".',
            ),
            "PL-040-002": card(
                "PL-040-002",
                "New Fraud Offense Act",
                'Public Law 40-2. Chapter 47 of title 18, United States Code, is amended by adding at the end the following new section: “§ 1002. New fraud offense\n(a) Whoever commits new fraud shall be fined.”',
            ),
            "PL-040-003": card(
                "PL-040-003",
                "Department Standards Act",
                "Public Law 40-3. Be it enacted. There is established in each executive department a standards officer. The officer shall issue binding regulations and shall report annually.",
            ),
            "PL-040-004": card(
                "PL-040-004",
                "Fiscal Year Appropriation Act",
                "Public Law 40-4. Supplemental appropriation for fiscal year 2026. There is appropriated, out of the Treasury, $500,000 for operations.",
            ),
            "PL-040-005": card(
                "PL-040-005",
                "Old Act",
                "Public Law 40-5. Old law.",
                status="repealed",
            ),
            "PL-040-006": card(
                "PL-040-006",
                "Existing Act",
                "Public Law 40-6. Existing law.",
            ),
        }
        sources = {law_id: self.source(law_id, c.description) for law_id, c in cards.items()}
        analyzer = LegalAnalyzer(self.repo, PACKAGE, CodeIndex(self.repo))
        analyses = [analyzer.analyze(c, sources[law_id]) for law_id, c in cards.items()]
        by_id = {analysis.law_id: analysis for analysis in analyses}

        self.assertEqual(by_id["PL-040-001"].disposition, "DIRECT_CODE_AMENDMENT")
        self.assertEqual(by_id["PL-040-002"].disposition, "DIRECT_CODE_AMENDMENT")
        self.assertEqual(by_id["PL-040-003"].disposition, "STATUTORY_NOTE")
        self.assertEqual(by_id["PL-040-004"].disposition, "NON_CODE")
        self.assertEqual(by_id["PL-040-005"].disposition, "NONOPERATIVE_OR_REPEALED")
        self.assertEqual(by_id["PL-040-006"].disposition, "ALREADY_INCORPORATED")

        applier = MassApplier(
            self.repo,
            self.workspace,
            CodeIndex(self.repo),
            cards,
            sources,
            analyses,
        )
        manifest = applier.apply()
        title18 = (self.repo / "usc" / "usc18.xml").read_text(encoding="utf-8")
        title5 = (self.repo / "usc" / "usc05.xml").read_text(encoding="utf-8")
        self.assertIn("shall be fined or imprisoned", title18)
        self.assertIn('/us/usc/t18/s1002', title18)
        self.assertIn("Department Standards Act", title5)
        self.assertNotIn("Fiscal Year Appropriation Act", title18 + title5)
        self.assertGreaterEqual(len(manifest["laws"]), 6)


if __name__ == "__main__":
    unittest.main()
