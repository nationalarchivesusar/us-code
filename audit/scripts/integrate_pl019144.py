from __future__ import annotations

import json
import re
from pathlib import Path


BASELINE = "00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46"
SOURCE_FILE = "codification/laws/laws/PL-019-144/law.txt"


def write_utf8(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def section_bounds(text: str, identifier: str) -> tuple[int, int]:
    pos = text.find(f'identifier="{identifier}"')
    if pos < 0:
        raise SystemExit(f"missing {identifier}")
    start = text.rfind("<section", 0, pos)
    depth = 0
    for match in re.finditer(r"<section\b|</section>", text[start:]):
        if match.group(0).startswith("<section"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return start, start + match.end()
    raise SystemExit(f"unclosed {identifier}")


def update_xml() -> None:
    path = Path("usc/usc54.xml")
    text = path.read_text(encoding="utf-8")
    if 'identifier="/us/usc/t54/s100101a"' in text:
        return
    toc_marker = '<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t54/s100102">100102.</ref></column><column style="-uslm-lc:I46" class="twoColumnRight">Definitions.</column>'
    toc_insert = '<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t54/s100101a">100101a.</ref></column><column style="-uslm-lc:I46" class="twoColumnRight">Public-area closure authority in the District of Columbia.</column>\n</tocItem>\n<tocItem>\n<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t54/s100101b">100101b.</ref></column><column style="-uslm-lc:I46" class="twoColumnRight">Public-area closure reasons, limits, and access.</column>\n</tocItem>\n<tocItem>\n' + toc_marker
    text = text.replace(toc_marker, toc_insert, 1)
    _, end = section_bounds(text, "/us/usc/t54/s100101")
    new_sections = """<section style="-uslm-lc:I80" id="rp-pl019144-s100101a" identifier="/us/usc/t54/s100101a"><num value="100101a">&#167;&#8239;100101a.</num><heading> Public-area closure authority in the District of Columbia</heading>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl019144-s100101a-a" identifier="/us/usc/t54/s100101a/a"><num value="a">(a)</num><heading> Definitions</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-a-1" identifier="/us/usc/t54/s100101a/a/1"><num value="1">(1)</num><content> The term "district" means the District of Columbia.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-a-2" identifier="/us/usc/t54/s100101a/a/2"><num value="2">(2)</num><content> The term "public road" means any road or street under the jurisdiction of the United States Government and open to public travel.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-a-3" identifier="/us/usc/t54/s100101a/a/3"><num value="3">(3)</num><content> The term "private road" means any road or street under the jurisdiction of the United States Government and closed to public travel, available only to authorized personnel.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-a-4" identifier="/us/usc/t54/s100101a/a/4"><num value="4">(4)</num><content> The term "armed forces" means the Army, Navy, Air Force, Marine Corps, Space Force, and Coast Guard.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-a-5" identifier="/us/usc/t54/s100101a/a/5"><num value="5">(5)</num><content> The term "National Guard" means the Army National Guard and the Air National Guard.</content></paragraph></subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl019144-s100101a-b" identifier="/us/usc/t54/s100101a/b"><num value="b">(b)</num><heading> Closure authority</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-1" identifier="/us/usc/t54/s100101a/b/1"><num value="1">(1)</num><content> When deployed in the district by the President, the armed forces may close public roads, private roads, and sidewalks, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-2" identifier="/us/usc/t54/s100101a/b/2"><num value="2">(2)</num><content> When federalized or deployed in the district, the National Guard may close public roads, private roads, and sidewalks, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-3" identifier="/us/usc/t54/s100101a/b/3"><num value="3">(3)</num><content> The Secret Service may close public roads, private roads, and sidewalks surrounding the White House, including Constitution Avenue NW, 17th Street NW, New York Avenue NW, and E Street NW, and may close public roads, private roads, and sidewalks that one of its protectees is on, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-4" identifier="/us/usc/t54/s100101a/b/4"><num value="4">(4)</num><content> The Capitol Police may close the entire Capitol complex, private or public roads and sidewalks, including the Capitol Building, congressional offices, Capitol Police headquarters, 3rd Street SW, and Independence Avenue SW, and may close public roads and sidewalks that one of its protectees is on, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-5" identifier="/us/usc/t54/s100101a/b/5"><num value="5">(5)</num><content> The Federal Protective Service may close any public road or sidewalk surrounding the main entrance of a Federal building under its protection, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-6" identifier="/us/usc/t54/s100101a/b/6"><num value="6">(6)</num><content> The United States Marshals Service and the Federal Bureau of Investigation may close any public road and sidewalk while executing a warrant for anyone wanted by the United States Government, and the Federal Bureau of Investigation may do so for a sensitive investigation requiring examination by agents, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-7" identifier="/us/usc/t54/s100101a/b/7"><num value="7">(7)</num><content> The Diplomatic Security Service may close the sidewalk in front of the Harry S Truman Building, the Department of State Building, embassies, consulates, and premises of diplomatic missions to the United States, and may close an area up to 20 feet away from any protectee or foreign delegation during a state visit, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-8" identifier="/us/usc/t54/s100101a/b/8"><num value="8">(8)</num><content> The District of Columbia Fire and Emergency Medical Services may close any sidewalk or public road directly leading up to a fire or medical emergency, and may be assisted by law enforcement, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-9" identifier="/us/usc/t54/s100101a/b/9"><num value="9">(9)</num><content> The Metropolitan Police Department and Federal Protective Service may close any sidewalk or public road while protecting an event permitted by the Department of Commerce and Labor under Public Law 17-126, subject to sections 100101a and 100101b of this title.</content></paragraph><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl019144-s100101a-b-10" identifier="/us/usc/t54/s100101a/b/10"><num value="10">(10)</num><content> No public road or sidewalk surrounding the gun store may be closed to any citizen of the United States.</content></paragraph></subsection>
<sourceCredit id="rp-pl019144-s100101a-source-credit">(Added <ref href="/us/pl/19/144/s5">Pub. L. 19&#8211;144, &#167;&#8239;&#167; 5&#8211;6</ref>.)</sourceCredit></section>
<section style="-uslm-lc:I80" id="rp-pl019144-s100101b" identifier="/us/usc/t54/s100101b"><num value="100101b">&#167;&#8239;100101b.</num><heading> Public-area closure reasons, limits, and access</heading><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl019144-s100101b-a" identifier="/us/usc/t54/s100101b/a"><num value="a">(a)</num><heading> Closure reasons</heading><content> Any road closure shall be made in the interest of public health, safety, national security, or other reasons in the interest of the American people. A law enforcement agency tasked by law or order of the President with protection of an individual may close an area up to 10 feet away from the protectee when there is adequate threat or need to do so.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl019144-s100101b-b" identifier="/us/usc/t54/s100101b/b"><num value="b">(b)</num><heading> Closure limitations</heading><content> Any American Citizen, upon being searched and if it is safe and practicable to do so, may enter a closed public road or sidewalk. No closure of a private road, public road, or sidewalk may last longer than 24 hours unless otherwise authorized by law.</content></subsection><sourceCredit id="rp-pl019144-s100101b-source-credit">(Added <ref href="/us/pl/19/144/s7">Pub. L. 19&#8211;144, &#167;&#8239;&#167; 7&#8211;8</ref>.)</sourceCredit></section>
"""
    text = text[:end] + "\n" + new_sections + text[end:]
    write_utf8(path, text)


def update_results() -> None:
    path = Path("audit/xml-integration-results.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    patches = {
        "ACTION-0439": {
            "final_section_or_subsection_identifier": "/us/usc/t54/s100101a",
            "actual_node_ids_added": ["rp-pl019144-s100101a"],
            "exact_enacted_text_applied": "Added 54 U.S.C. 100101a for District public-area closure definitions and closure authority for armed forces, National Guard, Secret Service, Capitol Police, Federal Protective Service, Marshals Service, FBI, Diplomatic Security Service, District fire/EMS, Metropolitan Police, and the gun-store closure bar.",
            "source_quotation": "SEC6. CLOSURE AUTHORITY... No public road or sidewalk surrounding the gun store may be closed to any citizen of the United States.",
            "toc_change": "Added Title 54 chapter 1001 TOC entry for 54 U.S.C. 100101a.",
        },
        "ACTION-0440": {
            "final_section_or_subsection_identifier": "/us/usc/t54/s100101b",
            "actual_node_ids_added": ["rp-pl019144-s100101b"],
            "exact_enacted_text_applied": "Added 54 U.S.C. 100101b for permitted road-closure reasons, protectee-area closure authority, citizen re-entry after search when safe and practicable, and the 24-hour closure limit unless otherwise authorized by law.",
            "source_quotation": "SEC7. CLOSURE REASONS... SEC8. CLOSURE LIMITATIONS...",
            "toc_change": "Added Title 54 chapter 1001 TOC entry for 54 U.S.C. 100101b.",
        },
    }
    for record in data["results"]:
        patch = patches.get(record.get("action_id"))
        if not patch:
            continue
        record.update(
            {
                "result_status": "applied",
                "baseline_commit": BASELINE,
                "xml_file_before": "usc54.xml",
                "xml_file_after": "usc54.xml",
                "actual_node_ids_changed": ["rp-pl019144-codification"],
                "actual_node_ids_removed": [],
                "source_file": SOURCE_FILE,
                "source_credit_change": "Added Pub. L. 19-144 source credits to new Title 54 sections.",
                "amendment_note_change": "Retained concise PL-019-144 repeal-or-conflict history note; operative closure text is now codified in new Title 54 sections.",
                "validation_result": "XML parse pending after PL-019-144 writer pass; action tied to actual XML diff after baseline.",
                "baseline_proof": None,
            }
        )
        record.update(patch)
    summary = data.get("summary")
    if isinstance(summary, dict):
        counts: dict[str, int] = {}
        for record in data["results"]:
            status = record.get("result_status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        summary["result_status_counts"] = counts
        summary["blocked_actions"] = counts.get("blocked", 0)
        summary["pending_actions"] = counts.get("pending-xml-implementation", 0)
    write_utf8(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    update_xml()
    update_results()
    print("Integrated PL-019-144 actions ACTION-0439 and ACTION-0440")


if __name__ == "__main__":
    main()
