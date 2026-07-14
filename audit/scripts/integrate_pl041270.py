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
    xml_path = Path("usc/usc40.xml")
    text = xml_path.read_text(encoding="utf-8")

    pl34_note = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl034249-codification"><heading class="centered smallCaps">'
        'Washington Diplomacy Complex Act 2025—Pub. L. 34–249</heading>'
        '<p><b>Status.</b> Current, as amended by <ref href="/us/pl/41/270">Pub. L. 41–270</ref>; retained as an '
        'uncodified statutory note because it concerns a particular diplomatic complex and associated local security '
        'authority in the District of Columbia.</p>'
        '<p><b>Definitions.</b> As amended by <ref href="/us/pl/41/270/s2">Pub. L. 41–270, § 2</ref>, “Complex” means '
        'the Washington Diplomacy Complex and all buildings, enclosed grounds, interior facilities, controlled access '
        'points, barriers, security installations, and Department-controlled property directly associated with the '
        'Complex; “Restricted Security Area” means any adjacent roadway, sidewalk, pedestrian pathway, bollard perimeter, '
        'parking area, or surrounding zone temporarily or permanently designated by the Department of State or the '
        'Diplomatic Security Service for protective, operational, counterintelligence, emergency, or national security '
        'purposes pursuant to the Act; “Department” means the United States Department of State; and “United Nations '
        'Secretariat” means the executive arm and administrative body of the United Nations, as defined under the '
        'United Nations Charter.</p>'
        '<p><b>Jurisdiction, security, and control.</b> As amended by <ref href="/us/pl/41/270/s3">Pub. L. 41–270, § 3</ref>, '
        'the Department maintains full jurisdiction, control, administration, and security authority over the Complex, '
        'including enclosed grounds, structures, internal accessways, barriers, controlled perimeters, and '
        'Department-controlled property. Adjacent sidewalks, roadways, and pedestrian or vehicle accessways are not '
        'permanently closed or absorbed into the Complex solely by proximity, but may be designated as Restricted '
        'Security Areas when necessary for diplomatic protection, national security, counterintelligence, emergency '
        'response, foreign-official protection, or operational necessity. Such areas are subject, for the duration and '
        'scope of the designation, to Department security regulations, access restrictions, lawful orders, temporary '
        'closures, screening requirements, and protective enforcement measures. The Department, acting through the '
        'Diplomatic Security Service, may regulate access control, credentialing, physical security, temporary closures, '
        'restricted access zones, lockdown systems, emergency procedures, and protective operations; may restrict, '
        'regulate, condition, or prohibit entry when reasonably necessary for the listed security purposes; and may deny '
        'entry to, remove, detain pending transfer to appropriate authorities, or issue lawful trespass orders against '
        'individuals who knowingly violate duly designated restrictions or lawful directives, obstruct protective '
        'functions, or willfully and knowingly violate regulations or lawful orders. Conduct may be referred for '
        'prosecution under sections 1752, 111, or 1505 of title 18, other Federal law, or District of Columbia law. '
        'The Act does not permanently extinguish lawful public access to unrestricted public rights-of-way except where '
        'lawfully restricted, temporarily closed, or otherwise regulated for security, safety, or operational purposes.</p>'
        '<p><b>United Nations access.</b> As amended by <ref href="/us/pl/41/270/s4">Pub. L. 41–270, § 4</ref>, the prior '
        'unrestricted-access formulation is replaced with access consistent with Department security regulations, lawful '
        'restrictions, and protective measures. Access privileges may be suspended, conditioned, or revoked where the '
        'Department determines that continued access presents a credible security, counterintelligence, operational, or '
        'national security threat.</p></note>'
    )
    pl41_note = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl041270-codification"><heading class="centered smallCaps">'
        'Washington Diplomacy Complex Corrections Act of 2026—Pub. L. 41–270</heading>'
        '<p><b>Status.</b> Current corrective amendment to the Washington Diplomacy Complex Act 2025.</p>'
        '<p><b>Codification.</b> Sections 2 through 4 replaced the definitions, jurisdiction/security/control, and '
        'United Nations access provisions of Pub. L. 34–249. The controlling amended text is reflected in the Pub. '
        'L. 34–249 statutory note. Section 5 redesignated section 6 as “SEC. 6. Implementing Regulations” and corrected '
        'duplicate titles, numbering inconsistencies, clerical errors, and conflicting provisions to conform with Pub. '
        'L. 41–270.</p><p><b>Authenticated text.</b> Source SHA-256 '
        'd0d610d8de9f97e4580c0dd7ed2feebbf01796e1dcdc7e5baed2091aed00d77e.</p></note>'
    )

    text = replace_note(text, "rp-pl034249-codification", pl34_note)
    text = replace_note(text, "rp-pl041270-codification", pl41_note)
    xml_path.write_text(text, encoding="utf-8", newline="\n")
    ET.parse(xml_path)

    results_path = Path("audit/xml-integration-results.json")
    data = json.loads(results_path.read_text(encoding="utf-8"))
    common = {
        "result_status": "applied",
        "baseline_commit": BASELINE,
        "xml_file_after": "usc40.xml",
        "source_file": "codification/laws/laws/PL-041-270/law.txt",
        "actual_node_ids_added": [],
        "actual_node_ids_changed": ["rp-pl034249-codification", "rp-pl041270-codification"],
        "actual_node_ids_removed": [],
        "source_credit_change": "No numbered Code-section source credit required; the statutory notes cite Pub. L. 41-270.",
        "amendment_note_change": "Replaced stale PL-034-249 and PL-041-270 boilerplate notes with controlling amended statutory-note text.",
        "toc_change": "No TOC change required for uncodified Washington Diplomacy Complex statutory notes.",
        "validation_result": "Working usc40.xml contains the amended Washington Diplomacy Complex statutory-note text and parses after the writer pass.",
        "baseline_proof": None,
    }
    update_result(
        data,
        "ACTION-0891",
        **common,
        final_section_or_subsection_identifier="/us/usc/t40/s101/note/rp-pl034249-codification/section-3",
        exact_enacted_text_applied=(
            "Amended the Pub. L. 34-249 Title 40 statutory note to replace section 3 with definitions of Complex, "
            "Restricted Security Area, Department, and United Nations Secretariat from Pub. L. 41-270, sec. 2."
        ),
        source_quotation=(
            "SEC 2... Section 3... is amended to read as follows... The term Complex means... The term Restricted "
            "Security Area means... The term Department means... The term United Nations Secretariat means..."
        ),
    )
    update_result(
        data,
        "ACTION-0892",
        **common,
        final_section_or_subsection_identifier="/us/usc/t40/s101/note/rp-pl034249-codification/section-4",
        exact_enacted_text_applied=(
            "Amended the Pub. L. 34-249 Title 40 statutory note to replace section 4 with expanded Department/DSS "
            "jurisdiction, restricted-security-area designation authority, access restrictions, enforcement measures, "
            "referral language, public-rights-of-way savings language, and event-protection coordination authority."
        ),
        source_quotation=(
            "SEC 3... Section 4... is amended to read as follows... JURISDICTION, SECURITY, AND CONTROL... The "
            "Department shall maintain full jurisdiction... Restricted Security Area... may deny entry to, remove, "
            "detain pending transfer..."
        ),
    )
    update_result(
        data,
        "ACTION-0893",
        **common,
        final_section_or_subsection_identifier="/us/usc/t40/s101/note/rp-pl034249-codification/section-5",
        exact_enacted_text_applied=(
            "Amended the Pub. L. 34-249 Title 40 statutory note to replace 'free and full access' with access consistent "
            "with Department security regulations, lawful restrictions, and protective measures, and to replace subsection "
            "(c) with authority to suspend, condition, or revoke access for credible security, counterintelligence, "
            "operational, or national security threats."
        ),
        source_quotation=(
            "SEC. 4... Section 5... by striking 'free and full access' and inserting 'access consistent with Department "
            "security regulations, lawful restrictions, and protective measures'... Access privileges... may be suspended..."
        ),
    )
    results_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("Integrated PL-041-270 actions 0891-0893")


if __name__ == "__main__":
    main()
