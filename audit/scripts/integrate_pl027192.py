import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

BASELINE = "00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46"
SOURCE = "codification/laws/laws/PL-027-192/law.txt"


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def replace_between(text, start_pat, end_marker, replacement):
    m = re.search(start_pat, text)
    if not m:
        raise SystemExit(f"start pattern not found: {start_pat}")
    end = text.find(end_marker, m.start())
    if end == -1:
        raise SystemExit(f"end marker not found after {start_pat}: {end_marker}")
    end += len(end_marker)
    return text[: m.start()] + replacement + text[end:]


def insert_before_regex(text, start_pat, addition):
    m = re.search(start_pat, text)
    if not m:
        raise SystemExit(f"regex insertion point not found: {start_pat}")
    return text[: m.start()] + addition + text[m.start() :]


def insert_after(text, needle, addition):
    idx = text.find(needle)
    if idx == -1:
        raise SystemExit(f"needle not found: {needle[:120]}")
    idx += len(needle)
    return text[:idx] + addition + text[idx:]


def replace_note_by_id(text, note_id, replacement):
    pat = re.compile(r'<note\b[^>]*\bid="' + re.escape(note_id) + r'"[^>]*>.*?</note>', re.S)
    text2, n = pat.subn(replacement, text, count=1)
    if n != 1:
        raise SystemExit(f"note id not replaced exactly once: {note_id} ({n})")
    return text2


def update_result(results, action_id, **fields):
    for row in results["results"]:
        if row.get("action_id") == action_id:
            row.update(fields)
            return
    raise SystemExit(f"result not found: {action_id}")


def integrate_title18():
    path = "usc/usc18.xml"
    text = read(path)

    old_a = re.compile(
        r'<subsection[^>]+identifier="/us/usc/t18/s2071/a"[^>]*>.*?</subsection>',
        re.S,
    )
    new_a = (
        '<subsection style="-uslm-lc:I11" class="indent0" id="id0e9a93b6-0975-11f0-92da-b5363bbf1875" '
        'identifier="/us/usc/t18/s2071/a"><num value="a">(a)</num><content> Whoever willfully and unlawfully '
        'conceals, removes, mutilates, obliterates, or destroys, or attempts to do so, or, with intent to do so '
        'takes and carries away any record, proceeding, map, book, paper, document, or other thing, filed or '
        'deposited with any clerk or officer of any court of the United States, or in any public office, or with '
        'any judicial or public officer of the United States, shall be fined under this title to no more than '
        '$10,000 or imprisoned not more than ten days, or both.</content>\n</subsection>'
    )
    text, n = old_a.subn(new_a, text, count=1)
    if n != 1:
        raise SystemExit("18 U.S.C. 2071(a) replacement failed")

    old_b = re.compile(
        r'<subsection[^>]+identifier="/us/usc/t18/s2071/b"[^>]*>.*?</subsection>',
        re.S,
    )
    new_b = (
        '<subsection style="-uslm-lc:I11" class="indent0" id="id0e9a93b7-0975-11f0-92da-b5363bbf1875" '
        'identifier="/us/usc/t18/s2071/b"><num value="b">(b)</num><content> Whoever, having the custody of any '
        'such record, proceeding, map, book, document, paper, or other thing, willfully and unlawfully conceals, '
        'removes, mutilates, obliterates, falsifies, or destroys the same, shall be fined under this title to no '
        'more than $10,000 or imprisoned not more than 10 days, or both; and shall forfeit his office and be '
        'disqualified from holding any office under the United States for three months. As used in this subsection, '
        'the term “office” does include the office held by any person as a retired officer of the Armed Forces of '
        'the United States.</content>\n</subsection>'
    )
    text, n = old_b.subn(new_b, text, count=1)
    if n != 1:
        raise SystemExit("18 U.S.C. 2071(b) replacement failed")

    old_credit = re.compile(
        r'<sourceCredit id="id0e9a93b8-0975-11f0-92da-b5363bbf1875">.*?</sourceCredit>',
        re.S,
    )
    new_credit = (
        '<sourceCredit id="id0e9a93b8-0975-11f0-92da-b5363bbf1875">(<ref href="/us/act/1948-06-25/ch645">'
        'June 25, 1948, ch. 645</ref>, <ref href="/us/stat/62/795">62 Stat. 795</ref>; '
        '<ref href="/us/pl/101/510/dA/tV/s552/a">Pub. L. 101–510, div. A, title V, § 552(a)</ref>, '
        '<date date="1990-11-05">Nov. 5, 1990</date>, <ref href="/us/stat/104/1566">104 Stat. 1566</ref>; '
        '<ref href="/us/pl/103/322/tXXXIII/s330016/1/I">Pub. L. 103–322, title XXXIII, § 330016(1)(I)</ref>, '
        '<date date="1994-09-13">Sept. 13, 1994</date>, <ref href="/us/stat/108/2147">108 Stat. 2147</ref>; '
        '<ref href="/us/pl/27/192/sIII">Pub. L. 27–192, § III</ref>.)</sourceCredit>'
    )
    text, n = old_credit.subn(new_credit, text, count=1)
    if n != 1 and "/us/pl/27/192/sIII" not in text:
        raise SystemExit("18 U.S.C. 2071 source credit replacement failed")

    amendments_note = (
        '<p style="-uslm-lc:I21" class="indent0">2024—Subsecs. (a), (b). '
        '<ref href="/us/pl/27/192/sIII">Pub. L. 27–192, § III</ref>, substituted penalties of a fine under this '
        'title to no more than $10,000 or imprisonment not more than ten days for the prior three-year imprisonment '
        'language, added a three-month disqualification period in subsec. (b), and provided that “office” includes '
        'the office held by a retired officer of the Armed Forces.</p>\n'
    )
    marker = (
        '<note style="-uslm-lc:I74" topic="amendments" id="id0e9a93bc-0975-11f0-92da-b5363bbf1875">'
        '<heading class="centered smallCaps">Amendments</heading>'
    )
    if "Pub. L. 27–192, § III" not in text:
        text = insert_after(text, marker, amendments_note)

    write(path, text)


def integrate_title44():
    path = "usc/usc44.xml"
    text = read(path)

    ch21_toc_marker = (
        '<tocItem>\n<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t44/s2120">2120.</ref>'
        '</column><column style="-uslm-lc:I46" class="twoColumnRight">Online access of founding fathers documents.'
        '</column>\n</tocItem>'
    )
    ch21_toc_add = (
        '\n<tocItem>\n<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t44/s2121">2121.</ref>'
        '</column><column style="-uslm-lc:I46" class="twoColumnRight">Public record notices and maintained boards.'
        '</column>\n</tocItem>\n<tocItem>\n<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t44/s2122">'
        '2122.</ref></column><column style="-uslm-lc:I46" class="twoColumnRight">Executive records management boards.'
        '</column>\n</tocItem>'
    )
    if "/us/usc/t44/s2121" not in text:
        text = insert_after(text, ch21_toc_marker, ch21_toc_add)

    ch22_toc_marker = (
        '<tocItem>\n<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t44/s2209">2209.</ref>'
        '</column><column style="-uslm-lc:I46" class="twoColumnRight">Disclosure requirement for official business '
        'conducted using non-official electronic messaging accounts.</column>\n</tocItem>'
    )
    ch22_toc_add = (
        '\n<tocItem>\n<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t44/s2210">2210.</ref>'
        '</column><column style="-uslm-lc:I46" class="twoColumnRight">Presidential libraries and public access boards.'
        '</column>\n</tocItem>'
    )
    if "/us/usc/t44/s2210" not in text:
        text = insert_after(text, ch22_toc_marker, ch22_toc_add)

    sec2121 = '''\n<section style="-uslm-lc:I80" id="rp-pl027192-s2121" identifier="/us/usc/t44/s2121"><num value="2121">§ 2121.</num><heading> Public record notices and maintained boards</heading>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2121-a" identifier="/us/usc/t44/s2121/a"><num value="a">(a)</num><heading> <inline class="small-caps">Presidential Notice of Legislation</inline>.—</heading><content>The President shall notify the National Archives and Records Administration of all legislation signed or vetoed by the President not more than 1 hour after the signature or veto of the legislation. The President shall notify the Speaker of the House of Representatives and the President pro tempore of the Senate, in writing, of the signature or veto of any legislation passed by Congress. Failure to comply with this subsection shall be punishable by a fine of $1,000 for each legislation for which notice was not provided, to be paid to the Archivist of the United States.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2121-b" identifier="/us/usc/t44/s2121/b"><num value="b">(b)</num><heading> <inline class="small-caps">Congressional Documents and Boards</inline>.—</heading><content>Both Houses of Congress shall be the sole body to update and maintain all congressional-related documents and boards, including all legislation submitted, with the supervision of the National Archives and Records Administration. The Speaker of the House of Representatives and the President pro tempore of the Senate shall delegate these duties to the Clerk of the House of Representatives and the Secretary of the Senate, respectively, if those positions are filled. The ownership of all congressional Trello boards shall be solely held by the National Archives and Records Administration.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2121-c" identifier="/us/usc/t44/s2121/c"><num value="c">(c)</num><heading> <inline class="small-caps">Judicial Documents and Boards</inline>.—</heading><content>All judicial courts existing in the United States shall each update and maintain all judicial documents and boards, including records of all civil and criminal cases, with the supervision of the National Archives and Records Administration. The ownership of all judicial Trello boards shall be solely held by the National Archives and Records Administration.</content>
</subsection>
<sourceCredit id="rp-pl027192-s2121-source">(<ref href="/us/pl/27/192/sII">Pub. L. 27–192, § II</ref>.)</sourceCredit>
</section>'''

    sec2122 = '''\n<section style="-uslm-lc:I80" id="rp-pl027192-s2122" identifier="/us/usc/t44/s2122"><num value="2122">§ 2122.</num><heading> Executive records management boards</heading>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2122-a" identifier="/us/usc/t44/s2122/a"><num value="a">(a)</num><heading> <inline class="small-caps">Public Records</inline>.—</heading><content>All Federal departments, agencies, and offices under the Executive Branch shall create, update, and maintain all public records, including all documents, memorandums, and orders, in a publicly accessible Trello board of which the National Archives and Records Administration shall have sole ownership.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2122-b" identifier="/us/usc/t44/s2122/b"><num value="b">(b)</num><heading> <inline class="small-caps">Required Contents</inline>.—</heading><content>Each Trello board shall have an updated leadership roster, updated documents about policies and regulations, press releases, and any other public Government records.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2122-c" identifier="/us/usc/t44/s2122/c"><num value="c">(c)</num><heading> <inline class="small-caps">Penalty</inline>.—</heading><content>Failure to comply with this section shall be punishable by a fine of $1,000 for each document that was not updated as prescribed, to be paid to the Archivist of the United States.</content>
</subsection>
<sourceCredit id="rp-pl027192-s2122-source">(<ref href="/us/pl/27/192/sIV">Pub. L. 27–192, § IV</ref>.)</sourceCredit>
</section>'''

    if 'identifier="/us/usc/t44/s2121"' not in text:
        text = insert_before_regex(
            text,
            r'<chapter\b[^>]*identifier="/us/usc/t44/ch22"',
            sec2121 + sec2122 + "\n",
        )

    sec2210 = '''\n<section style="-uslm-lc:I80" id="rp-pl027192-s2210" identifier="/us/usc/t44/s2210"><num value="2210">§ 2210.</num><heading> Presidential libraries and public access boards</heading>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2210-a" identifier="/us/usc/t44/s2210/a"><num value="a">(a)</num><heading> <inline class="small-caps">Assistance</inline>.—</heading><content>Upon enactment of this section, the National Archives and Records Administration shall assist each President in setting up Presidential libraries.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2210-b" identifier="/us/usc/t44/s2210/b"><num value="b">(b)</num><heading> <inline class="small-caps">Public Access Board</inline>.—</heading><content>Each Presidential library shall contain any and all public records, including all executive orders, memorandums, nominations, and any other documents from the administration of each President, and those records shall be made publicly available through a Trello board.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2210-c" identifier="/us/usc/t44/s2210/c"><num value="c">(c)</num><heading> <inline class="small-caps">Ownership and Management</inline>.—</heading><content>The Trello board of each Presidential library shall be owned solely by the National Archives and Records Administration and shall be managed by a designee from the Presidential library. The designee shall be chosen by the former President who is the subject of the Presidential library.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2210-d" identifier="/us/usc/t44/s2210/d"><num value="d">(d)</num><heading> <inline class="small-caps">Former Presidents</inline>.—</heading><content>Each former President shall be obligated by the National Archives and Records Administration to open a Presidential library, but shall not be compelled to directly manage that Presidential library. If a former President refuses to manage a Presidential library, the National Archives and Records Administration shall also take responsibility for managing the records.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2210-e" identifier="/us/usc/t44/s2210/e"><num value="e">(e)</num><heading> <inline class="small-caps">Removed Public Documents</inline>.—</heading><content>If any public document is removed from public viewing on the Trello board of the Presidential library, the Department of Justice, in cooperation with the National Archives and Records Administration, shall proceed with any legal actions prescribed under section 2071 of title 18.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl027192-s2210-f" identifier="/us/usc/t44/s2210/f"><num value="f">(f)</num><heading> <inline class="small-caps">Roblox Game</inline>.—</heading><content>Each former President may open any Roblox game hosting the former President's Presidential library with all the artifacts and documents under that President's presidency.</content>
</subsection>
<sourceCredit id="rp-pl027192-s2210-source">(<ref href="/us/pl/27/192/sV">Pub. L. 27–192, § V</ref>.)</sourceCredit>
</section>'''

    if 'identifier="/us/usc/t44/s2210"' not in text:
        text = insert_before_regex(
            text,
            r'<chapter\b[^>]*identifier="/us/usc/t44/ch23"',
            sec2210 + "\n",
        )

    replacement_note = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl027192-codification"><heading class="centered smallCaps">'
        'Presidential Libraries and Better Public Records Management Act—Pub. L. 27–192</heading>'
        '<p><b>Status.</b> Current; operative text has been codified in sections 2121, 2122, and 2210 of this title and '
        'section 2071 of title 18.</p><p><b>Codification.</b> Section II amended the NARA Act public-record duties; '
        'section IV added executive-records management duties; section V added Presidential-library public-access duties. '
        'Section III amended <ref href="/us/usc/t18/s2071">section 2071 of title 18</ref>.</p></note>'
    )
    text = replace_note_by_id(text, "rp-pl027192-codification", replacement_note)
    write(path, text)


def update_results():
    path = Path("audit/xml-integration-results.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    common = {
        "baseline_commit": BASELINE,
        "source_file": SOURCE,
        "validation_result": "Working XML contains the applied PL-027-192 text and is tied to actual XML diffs after baseline; XML parse checked by the writer pass.",
        "baseline_proof": None,
    }
    update_result(
        data,
        "ACTION-0577",
        **common,
        result_status="applied",
        xml_file_after="usc44.xml",
        final_section_or_subsection_identifier="/us/usc/t44/s2121",
        actual_node_ids_added=["rp-pl027192-s2121"],
        actual_node_ids_changed=["rp-pl027192-codification"],
        actual_node_ids_removed=[],
        exact_enacted_text_applied="Added 44 U.S.C. 2121 to codify Pub. L. 27-192 section II: one-hour presidential notice to NARA, written notice to congressional officers, $1,000 notice penalties, congressional records and boards under NARA supervision, NARA ownership of congressional boards, judicial records and boards under NARA supervision, and NARA ownership of judicial boards.",
        source_quotation="SECTION II... Section II shall be amended and read as... notify the National Archives and Records Administration... not more than 1 hour... Section III shall be added... Both Houses of Congress... Section IV shall be added... judicial courts...",
        source_credit_change="Added source credit to 44 U.S.C. 2121 for Pub. L. 27-192, sec. II.",
        amendment_note_change="Replaced obsolete PL-027-192 boilerplate note with concise codification note cross-referencing 44 U.S.C. 2121, 2122, 2210, and 18 U.S.C. 2071.",
        toc_change="Added Title 44 chapter 21 TOC entry for 44 U.S.C. 2121.",
    )
    update_result(
        data,
        "ACTION-0578",
        **common,
        result_status="applied",
        xml_file_after="usc18.xml",
        final_section_or_subsection_identifier="/us/usc/t18/s2071/a | /us/usc/t18/s2071/b",
        actual_node_ids_added=[],
        actual_node_ids_changed=["id0e9a93b6-0975-11f0-92da-b5363bbf1875", "id0e9a93b7-0975-11f0-92da-b5363bbf1875", "id0e9a93b8-0975-11f0-92da-b5363bbf1875"],
        actual_node_ids_removed=[],
        exact_enacted_text_applied="Amended 18 U.S.C. 2071(a) and (b) to impose a fine under title 18 to no more than $10,000 or imprisonment not more than ten/10 days, or both; amended subsection (b) to impose a three-month disqualification period and to state that office includes a retired Armed Forces officer's office.",
        source_quotation="SECTION III. 18 U.S. CODE §2071 AMENDMENT... shall be fined under this title to no more than $10,000 or imprisoned not more than ten days... shall forfeit his office and be disqualified... for three months... office does include...",
        source_credit_change="Added Pub. L. 27-192, sec. III, to the source credit for 18 U.S.C. 2071.",
        amendment_note_change="Added 2024 amendment note for Pub. L. 27-192, sec. III, under 18 U.S.C. 2071.",
        toc_change="No TOC change required; existing 18 U.S.C. 2071 remains the target.",
    )
    update_result(
        data,
        "ACTION-0579",
        **common,
        result_status="applied",
        xml_file_after="usc44.xml",
        final_section_or_subsection_identifier="/us/usc/t44/s2122",
        actual_node_ids_added=["rp-pl027192-s2122"],
        actual_node_ids_changed=["rp-pl027192-codification"],
        actual_node_ids_removed=[],
        exact_enacted_text_applied="Added 44 U.S.C. 2122 to codify Pub. L. 27-192 section IV: executive departments, agencies, and offices must maintain public records in a publicly accessible NARA-owned Trello board, keep leadership rosters/policies/press releases/other public records current, and pay $1,000 per nonupdated document.",
        source_quotation="SECTION IV. EXECUTIVE RECORDS MANAGEMENT... all federal departments, agencies and offices under the Executive Branch shall create, update and maintain all public records... Each Trello Board shall have an updated leadership roster...",
        source_credit_change="Added source credit to 44 U.S.C. 2122 for Pub. L. 27-192, sec. IV.",
        amendment_note_change="Replaced obsolete PL-027-192 boilerplate note with concise codification note.",
        toc_change="Added Title 44 chapter 21 TOC entry for 44 U.S.C. 2122.",
    )
    update_result(
        data,
        "ACTION-0580",
        **common,
        result_status="applied",
        xml_file_after="usc44.xml",
        final_section_or_subsection_identifier="/us/usc/t44/s2210",
        actual_node_ids_added=["rp-pl027192-s2210"],
        actual_node_ids_changed=["rp-pl027192-codification"],
        actual_node_ids_removed=[],
        exact_enacted_text_applied="Added 44 U.S.C. 2210 to codify Pub. L. 27-192 section V: NARA assistance for Presidential libraries, public board access to Presidential records, NARA ownership and designee management, former-President obligations and NARA backup management, DOJ/NARA action for removed public documents, and Roblox-game authorization.",
        source_quotation="SECTION V. PRESIDENTIAL LIBRARIES ESTABLISHMENT... National Archives and Records Administration shall assist each President... Each Presidential Library shall contain... public records... Trello Board... owned solely by the National Archives...",
        source_credit_change="Added source credit to 44 U.S.C. 2210 for Pub. L. 27-192, sec. V.",
        amendment_note_change="Replaced obsolete PL-027-192 boilerplate note with concise codification note.",
        toc_change="Added Title 44 chapter 22 TOC entry for 44 U.S.C. 2210.",
    )
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main():
    integrate_title18()
    integrate_title44()
    for file in ["usc/usc18.xml", "usc/usc44.xml"]:
        ET.parse(file)
    update_results()
    print("Integrated PL-027-192 actions 0577-0580")


if __name__ == "__main__":
    main()
