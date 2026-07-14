import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

BASELINE = "00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46"


def replace_note(text, note_id, replacement):
    pat = re.compile(r'<note\b[^>]*\bid="' + re.escape(note_id) + r'"[^>]*>.*?</note>', re.S)
    text2, n = pat.subn(replacement, text, count=1)
    if n != 1:
        raise SystemExit(f"expected one replacement for {note_id}, got {n}")
    return text2


def update_result(data, action_id, **fields):
    for row in data["results"]:
        if row.get("action_id") == action_id:
            row.update(fields)
            return
    raise SystemExit(f"missing result row {action_id}")


def main():
    xml_path = Path("usc/usc50.xml")
    text = xml_path.read_text(encoding="utf-8")

    pl27_note = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl027196-codification"><heading class="centered smallCaps">'
        'National Commission on Judicial Activity, Efficiency and Accountability Act—Pub. L. 27–196</heading>'
        '<p><b>Status.</b> Current temporary commission statute, as amended by '
        '<ref href="/us/pl/28/197/sII">Pub. L. 28–197, § II</ref>; retained as an uncodified statutory note because '
        'it creates and governs a time-limited National Commission on Judicial Activity, Efficiency and Accountability.</p>'
        '<p><b>Final report.</b> Section VI(b), as amended, requires the Commission to submit its final report to the '
        'President and Congress not later than <date date="2025-01-21">January 21, 2025</date>. The date may be '
        'extended to not later than <date date="2025-02-01">February 1, 2025</date> by formal request of a majority '
        'of the Commission and joint approval by the Speaker of the House and the President pro tempore of the Senate.</p>'
        '<p><b>Codification.</b> No freestanding permanent Code section is inserted; this note records the controlling '
        'amended reporting deadline for Pub. L. 27–196.</p></note>'
    )
    pl28_note = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl028197-codification"><heading class="centered smallCaps">'
        'Amending Public Law 27-196—Pub. L. 28–197</heading>'
        '<p><b>Status.</b> Current amendment to Pub. L. 27–196.</p>'
        '<p><b>Codification.</b> Section II amended the final-report deadline in section VI(b) of Pub. L. 27–196 to '
        '<date date="2025-01-21">January 21, 2025</date>, with extension permitted to '
        '<date date="2025-02-01">February 1, 2025</date>. The amended deadline is reflected in the Pub. L. 27–196 '
        'statutory note.</p></note>'
    )

    text = replace_note(text, "rp-pl027196-codification", pl27_note)
    text = replace_note(text, "rp-pl028197-codification", pl28_note)
    xml_path.write_text(text, encoding="utf-8", newline="\n")
    ET.parse(xml_path)

    results_path = Path("audit/xml-integration-results.json")
    data = json.loads(results_path.read_text(encoding="utf-8"))
    update_result(
        data,
        "ACTION-0600",
        result_status="applied",
        baseline_commit=BASELINE,
        xml_file_after="usc50.xml",
        final_section_or_subsection_identifier="/us/usc/t50/s1/note/rp-pl027196-codification",
        actual_node_ids_added=[],
        actual_node_ids_changed=["rp-pl027196-codification", "rp-pl028197-codification"],
        actual_node_ids_removed=[],
        exact_enacted_text_applied=(
            "Amended the Title 50 statutory notes for Pub. L. 27-196/Pub. L. 28-197 to state that section VI(b) "
            "requires the Commission's final report not later than January 21, 2025, and permits extension to "
            "February 1, 2025 by formal majority request and joint approval of the Speaker and President pro tempore."
        ),
        source_file="codification/laws/laws/PL-028-197/law.txt",
        source_quotation=(
            "SECTION II... Section VI(b) of Public Law 27-196 shall be amended... Not later than January 21st, 2025... "
            "This date can be extended to not later than February 1st, 2025..."
        ),
        source_credit_change="No Code-section source credit required; the current statutory-note text cites Pub. L. 28-197, sec. II.",
        amendment_note_change="Replaced stale PL-027-196 and PL-028-197 boilerplate notes with a concise amended-deadline statutory note.",
        toc_change="No TOC change required for uncodified commission-report deadline note.",
        validation_result="Working usc50.xml contains the amended PL-027-196 reporting deadline note and parses after the writer pass.",
        baseline_proof=None,
    )
    results_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("Integrated PL-028-197 ACTION-0600")


if __name__ == "__main__":
    main()
