from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]

TITLE = '''<?xml version="1.0" encoding="UTF-8"?>
<uscDoc xmlns="http://xml.house.gov/schemas/uslm/1.0" identifier="/us/usc/t{title}">
<meta><docNumber>{title}</docNumber></meta><main><title identifier="/us/usc/t{title}">
<num value="{title}">Title {title}</num><heading>TEST</heading>{chapters}</title></main></uscDoc>'''

CHAPTER = '''<chapter identifier="/us/usc/t{title}/ch{chapter}" id="ch-{title}-{chapter}">
<num value="{chapter}">CHAPTER {chapter}</num><heading>TEST</heading>
<toc><layout>{toc}</layout></toc>{sections}</chapter>'''

SECTION = '''<section identifier="/us/usc/t{title}/s{section}" id="s-{title}-{section}">
<num value="{section}">§ {section}.</num><heading>{heading}</heading>
<chapeau><p>{body}</p></chapeau><sourceCredit><p>Original source.</p></sourceCredit></section>'''


class LargeCorpusTest(unittest.TestCase):
    def test_205_law_transaction(self):
        root = Path(tempfile.mkdtemp(prefix="mass-corpus-205-"))
        try:
            repo = root / "repo"
            (repo / "usc").mkdir(parents=True)
            (repo / "tools").mkdir()
            sections18 = []
            toc18 = []
            for number in range(1001, 1006):
                sections18.append(SECTION.format(
                    title=18, section=number, heading=f"Offense {number}",
                    body=f"A person committing offense {number} shall be fined.",
                ))
                toc18.append(f'<tocItem><column><ref href="/us/usc/t18/s{number}">{number}</ref></column></tocItem>')
            sections18.append(SECTION.format(
                title=18, section=3551, heading="Authorized sentences",
                body="A defendant shall be sentenced in accordance with law.",
            ))
            toc18.append('<tocItem><column><ref href="/us/usc/t18/s3551">3551</ref></column></tocItem>')
            title18 = TITLE.format(title=18, chapters=CHAPTER.format(
                title=18, chapter=47, toc="".join(toc18), sections="".join(sections18)
            ))
            title5 = TITLE.format(title=5, chapters=CHAPTER.format(
                title=5, chapter=3,
                toc='<tocItem><column><ref href="/us/usc/t5/s301">301</ref></column></tocItem>',
                sections=SECTION.format(
                    title=5, section=301, heading="Departmental regulations",
                    body="The head of an Executive department may prescribe regulations.",
                ),
            ))
            title1 = TITLE.format(title=1, chapters=CHAPTER.format(
                title=1, chapter=1,
                toc='<tocItem><column><ref href="/us/usc/t1/s1">1</ref></column></tocItem>',
                sections=SECTION.format(title=1, section=1, heading="General provisions", body="General law."),
            ))
            for title, text in ((1, title1), (5, title5), (18, title18)):
                (repo / "usc" / f"usc{title:02d}.xml").write_text(text, encoding="utf-8")

            lists = [{"id": "active", "name": "Active Public Laws"}]
            cards = []
            law_number = 1
            # Five exact direct amendments.
            for section in range(1001, 1006):
                desc = (
                    f"Public Law 50-{law_number}. Be it enacted. Section {section} of title 18, "
                    f"United States Code, is amended by striking \"shall be fined\" and inserting "
                    f"\"shall be fined or imprisoned\". The Attorney General shall issue guidance "
                    f"and shall preserve an implementation record."
                )
                cards.append(self.card(law_number, f"Offense {section} Amendment Act", desc))
                law_number += 1
            # Five express new sections.
            for section in range(1101, 1106):
                desc = (
                    f"Public Law 50-{law_number}. Be it enacted. Chapter 47 of title 18, United States "
                    f"Code, is amended by adding at the end the following new section: “§ {section}. "
                    f"Modern offense {section}\n(a) Whoever commits modern offense {section} shall be "
                    f"fined. The Attorney General shall publish enforcement guidance.”"
                )
                cards.append(self.card(law_number, f"Modern Offense {section} Act", desc))
                law_number += 1
            # One hundred seventy-five general and permanent freestanding laws.
            for index in range(175):
                desc = (
                    f"Public Law 50-{law_number}. Be it enacted. There is established in each executive "
                    f"department a Records Standards Office number {index}. The Office shall maintain "
                    f"public records, shall issue binding administrative standards, and shall publish "
                    f"an annual compliance statement. Each department head shall provide the Office "
                    f"the information necessary to carry out this Act."
                )
                cards.append(self.card(law_number, f"Records Standards Act {index}", desc))
                law_number += 1
            # Twenty valid enactments that do not belong in the permanent Code.
            for index in range(20):
                desc = (
                    f"Public Law 50-{law_number}. Be it enacted. Supplemental appropriation for fiscal "
                    f"year 2026. There is appropriated, out of the Treasury, $10{index:03d} for the "
                    f"specific ceremony. Funds shall remain available for that ceremony and shall "
                    f"expire immediately after the event."
                )
                cards.append(self.card(law_number, f"Ceremony Appropriation {index}", desc))
                law_number += 1

            board = {"lists": lists, "cards": cards}
            board_path = root / "board.json"
            board_path.write_text(json.dumps(board), encoding="utf-8")
            proc = subprocess.run(
                [
                    sys.executable, str(PACKAGE / "mass_codifier.py"),
                    "--repo", str(repo), "--board-json", str(board_path),
                    "--apply", "--minimum-decisions", "100", "--max-source-holds", "0",
                ],
                text=True, capture_output=True, timeout=240,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + "\n" + proc.stderr)
            reports = repo / "codification" / "mass_migration" / "latest" / "reports"
            gate = json.loads((reports / "COMPLETENESS-GATE.json").read_text(encoding="utf-8"))
            inventory = json.loads((reports / "MASTER-INVENTORY.json").read_text(encoding="utf-8"))
            self.assertTrue(gate["passed"])
            self.assertEqual(gate["actionable"], 205)
            self.assertEqual(len(inventory["laws"]), 205)
            title18_after = (repo / "usc" / "usc18.xml").read_text(encoding="utf-8")
            title5_after = (repo / "usc" / "usc05.xml").read_text(encoding="utf-8")
            for section in range(1101, 1106):
                self.assertIn(f'/us/usc/t18/s{section}', title18_after)
            self.assertIn("shall be fined or imprisoned", title18_after)
            self.assertGreaterEqual(title5_after.count("USAR Public Law"), 175)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    @staticmethod
    def card(number: int, title: str, description: str) -> dict:
        return {
            "id": f"card-{number}", "shortLink": f"L{number}",
            "name": f"Public Law 50-{number} | {title}", "desc": description,
            "idList": "active", "labels": [], "closed": False,
            "dateLastActivity": "2026-07-01T00:00:00Z", "attachments": [],
            "url": f"https://trello.com/c/L{number}",
        }


if __name__ == "__main__":
    unittest.main()
