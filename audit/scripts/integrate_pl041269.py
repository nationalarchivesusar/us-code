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

    pl24_note = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl024173-codification"><heading class="centered smallCaps">'
        'Federal Enhancement Against Foreign Intrusion Act—Pub. L. 24–173</heading>'
        '<p><b>Status.</b> Current, as amended by <ref href="/us/pl/41/269">Pub. L. 41–269</ref>; retained as an '
        'uncodified statutory note because the enactment regulates categories of Federal officials without assigning '
        'a permanent numbered Code section.</p>'
        '<p><b>Section III, elected officials.</b> As amended by <ref href="/us/pl/41/269/s2">Pub. L. 41–269, § 2</ref>, '
        'no elected official of the United States may knowingly hold employment, command authority, or formal affiliation '
        'with a foreign government or foreign military group while serving in office. An elected official alleged to be '
        'in violation is subject to referral to the appropriate chamber of Congress for investigation and disciplinary '
        'proceedings, investigation by appropriate ethics, oversight, or law-enforcement authorities, and such further '
        'action as may be authorized. Nothing in the amended section authorizes automatic removal from office or '
        'establishes additional qualifications for elected office beyond those prescribed by the Constitution.</p>'
        '<p><b>Section V, disclosure and enforcement.</b> As added by <ref href="/us/pl/41/269/s3">Pub. L. 41–269, § 3</ref>, '
        'an individual subject to the Act shall disclose any past or present employment, affiliation, advisory role, or '
        'command relationship with a foreign government or foreign military group. A knowing or willful failure to '
        'disclose, concealment, or materially false statement or omission concerning such affiliation is subject to '
        'enforcement under <ref href="/us/usc/t22/s618">section 618 of title 22</ref>.</p></note>'
    )
    pl41_note = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl041269-codification"><heading class="centered smallCaps">'
        'Federal Enhancement Against Foreign Intrusion Amendments Act of 2026—Pub. L. 41–269</heading>'
        '<p><b>Status.</b> Current amendment to Pub. L. 24–173.</p>'
        '<p><b>Codification.</b> Section 2 replaced section III of Pub. L. 24–173 with a foreign-affiliation prohibition, '
        'referral/investigation procedure, anti-automatic-removal rule, and constitutional-qualifications savings clause. '
        'Section 3 inserted section V requiring disclosure of foreign affiliations and routing enforcement to '
        '<ref href="/us/usc/t22/s618">22 U.S.C. 618</ref>. The amended text is reflected in the Pub. L. 24–173 '
        'statutory note.</p><p><b>Authenticated text.</b> Source SHA-256 '
        'b3dab35ee5fabfbebffc2f0347df9f7fffaa8618c2ab1f4bf57d921bef77d5d4.</p></note>'
    )

    text = replace_note(text, "rp-pl024173-codification", pl24_note)
    text = replace_note(text, "rp-pl041269-codification", pl41_note)
    xml_path.write_text(text, encoding="utf-8", newline="\n")
    ET.parse(xml_path)

    results_path = Path("audit/xml-integration-results.json")
    data = json.loads(results_path.read_text(encoding="utf-8"))
    common = {
        "result_status": "applied",
        "baseline_commit": BASELINE,
        "xml_file_after": "usc50.xml",
        "source_file": "codification/laws/laws/PL-041-269/law.txt",
        "actual_node_ids_added": [],
        "actual_node_ids_changed": ["rp-pl024173-codification", "rp-pl041269-codification"],
        "actual_node_ids_removed": [],
        "source_credit_change": "No numbered Code-section source credit required; the statutory notes cite Pub. L. 41-269.",
        "amendment_note_change": "Replaced stale PL-024-173 and PL-041-269 boilerplate notes with amended statutory-note text.",
        "toc_change": "No TOC change required for uncodified foreign-affiliation statutory notes.",
        "validation_result": "Working usc50.xml contains the amended PL-024-173/PL-041-269 statutory-note text and parses after the writer pass.",
        "baseline_proof": None,
    }
    update_result(
        data,
        "ACTION-0887",
        **common,
        final_section_or_subsection_identifier="/us/usc/t50/s1/note/rp-pl024173-codification/section-III",
        exact_enacted_text_applied=(
            "Amended the Pub. L. 24-173 Title 50 statutory note to replace section III with the Pub. L. 41-269 "
            "foreign-affiliation prohibition, referral/investigation procedure, anti-automatic-removal rule, and "
            "constitutional-qualifications savings clause."
        ),
        source_quotation=(
            "SEC 2... Section III of Public Law 24-173 is amended to read as follows: No elected official... shall "
            "knowingly hold employment, command authority, or formal affiliation with a foreign government or foreign "
            "military group..."
        ),
    )
    update_result(
        data,
        "ACTION-0888",
        **common,
        final_section_or_subsection_identifier="/us/usc/t50/s1/note/rp-pl024173-codification/section-V",
        exact_enacted_text_applied=(
            "Amended the Pub. L. 24-173 Title 50 statutory note to add section V requiring disclosure of past or "
            "present foreign employment, affiliation, advisory role, or command relationship, with knowing or willful "
            "nondisclosure or false statements subject to enforcement under 22 U.S.C. 618."
        ),
        source_quotation=(
            "SEC 3... inserting after Section IV... SECTION V. DISCLOSURE OF FOREIGN AFFILIATION... shall disclose "
            "any past or present employment, affiliation, advisory role, or command relationship..."
        ),
    )
    results_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("Integrated PL-041-269 actions 0887-0888")


if __name__ == "__main__":
    main()
