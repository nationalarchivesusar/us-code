from __future__ import annotations

import json
from pathlib import Path


BASELINE = "00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46"
SOURCE_FILE = "codification/laws/laws/PL-017-128/law.txt"


def write_utf8(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Could not find {label}")
    return text.replace(old, new, 1)


def update_title_2() -> None:
    path = Path("usc/usc02.xml")
    text = path.read_text(encoding="utf-8")

    old_note = '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl017128-codification"><heading class="centered smallCaps">Impeachment Procedures and Protocols Act (IPPA&#8212;Pub. L. 17&#8211;128</heading><p><b>Status.</b> Repealed or superseded; retained solely as statutory history.</p><p><b>Codification.</b> This generally applicable enactment is classified as a statutory note at the closest subject-matter Code anchor.</p></note>'
    new_note = '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl017128-codification"><heading class="centered smallCaps">Impeachment Procedures and Protocols Act&#8212;Pub. L. 17&#8211;128</heading><p><b>Status.</b> Current or not wholly repealed in the supplied public-law archive.</p><p><b>Codification.</b> Sections 4 through 8 and 10 through 11 are integrated in chapter 6 of this title as congressional-procedure text. Section 9 amends <ref href="/us/usc/t28/s1365">section 1365 of Title 28</ref>.</p></note>'
    if old_note in text:
        text = text.replace(old_note, new_note, 1)
    elif 'id="rp-pl017128-codification"' not in text:
        raise SystemExit("PL-017-128 note not found")

    if 'identifier="/us/usc/t2/s200"' in text:
        write_utf8(path, text)
        return

    ch6_start = text.find("<chapter", text.find('identifier="/us/usc/t2/ch6"') - 500)
    ch6_end = text.find("<chapter", ch6_start + 20)
    if ch6_start < 0 or ch6_end < 0:
        raise SystemExit("Could not locate Title 2 chapter 6")

    ch6 = text[ch6_start:ch6_end]
    toc_insert = """<tocItem>
<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t2/s200">200.</ref></column><column style="-uslm-lc:I46" class="twoColumnRight">Impeachment inquiries, articles, managers, and Senate trials.</column>
</tocItem>
<tocItem>
<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t2/s200a">200a.</ref></column><column style="-uslm-lc:I46" class="twoColumnRight">Compliance with congressional subpoenas; rule of construction.</column>
</tocItem>
"""
    ch6 = replace_once(ch6, "</layout>\n</toc>", toc_insert + "</layout>\n</toc>", "Title 2 chapter 6 TOC")

    sections = """<section style="-uslm-lc:I80" id="rp-pl017128-s200" identifier="/us/usc/t2/s200"><num value="200">&#167;&#8239;200.</num><heading> Impeachment inquiries, articles, managers, and Senate trials</heading>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s200-a" identifier="/us/usc/t2/s200/a"><num value="a">(a)</num><heading> Definitions</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-a-1" identifier="/us/usc/t2/s200/a/1"><num value="1">(1)</num><content> In this section, the term &#8220;public office&#8221; means a position of authority or service involving responsibility to the public, especially within the government.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-a-2" identifier="/us/usc/t2/s200/a/2"><num value="2">(2)</num><content> The term &#8220;public official&#8221; means an officer or employee, or a person acting for or on behalf of the United States, any department, agency, or branch of Government thereof, or the District of Columbia, in any official function, under or by authority of any such department, agency, or branch of Government.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-a-3" identifier="/us/usc/t2/s200/a/3"><num value="3">(3)</num><content> The term &#8220;impeachment&#8221; means the proceeding taken by Congress to bring charges against a public official for alleged misconduct with a penalty of removal.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-a-4" identifier="/us/usc/t2/s200/a/4"><num value="4">(4)</num><content> The term &#8220;to impeach&#8221; means to charge a public official with a crime or misconduct.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-a-5" identifier="/us/usc/t2/s200/a/5"><num value="5">(5)</num><content> The term &#8220;impeachment inquiry&#8221; means the investigation into a public official for misconduct by a congressional committee.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-a-6" identifier="/us/usc/t2/s200/a/6"><num value="6">(6)</num><content> The term &#8220;conviction&#8221;, and the term &#8220;to convict&#8221;, mean a formal declaration by verdict of the Senate that a person is guilty of a criminal offense.</content></paragraph>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s200-b" identifier="/us/usc/t2/s200/b"><num value="b">(b)</num><heading> Impeachment inquiries</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-b-1" identifier="/us/usc/t2/s200/b/1"><num value="1">(1)</num><content> Any request to start an impeachment inquiry shall include the Roblox username and employment of the sender, the Roblox username and employment of the public official requested to be impeached, and a credible accusation.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-b-2" identifier="/us/usc/t2/s200/b/2"><num value="2">(2)</num><content> Any request to start an impeachment inquiry into the conduct or actions of any public official shall be written in a formal letter, made publicly accessible, and transmitted to the Speaker of the House, the President pro tempore, and the chair of the committee to which the public official is accountable.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-b-3" identifier="/us/usc/t2/s200/b/3"><num value="3">(3)</num><content> Upon transmission of at least 2 requests for an impeachment inquiry, the chair of the committee to which the accused public official is accountable shall, within 48 hours of the requests, consult with fellow committee members and decide whether to open an impeachment inquiry.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-b-4" identifier="/us/usc/t2/s200/b/4"><num value="4">(4)</num><content> If the committee decides against opening an impeachment inquiry, it shall issue a public letter explaining why it decided against opening the inquiry, whether any other actions will be taken by the committee, and the letter shall be signed by every member of the committee. If the committee decides to open an impeachment inquiry, it shall issue a public letter announcing the inquiry, explaining why it is opening the inquiry, and the letter shall be signed by every member of the committee.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-b-5" identifier="/us/usc/t2/s200/b/5"><num value="5">(5)</num><content> Once the impeachment inquiry begins, the committee, when necessary for the discharge of its duties, shall have authority to issue subpoenas to compel witnesses to appear and testify and to produce books, papers, correspondence, memoranda, documents, or other relevant records. A subpoena shall contain the username of the subpoenaed individual, the name of the committee, the time and place, what is needed, and shall be issued under the signature of the Speaker of the House and the committee chairperson. In certain instances, executive privilege may protect the President, the Vice President, and their key advisers from producing documents or testifying.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-b-6" identifier="/us/usc/t2/s200/b/6"><num value="6">(6)</num><content> The accused public official shall have the right to testify before the committee at any moment during the impeachment inquiry, but may waive that right unless subpoenaed by the committee.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-b-7" identifier="/us/usc/t2/s200/b/7"><num value="7">(7)</num><content> Once the inquiry is finished, the committee shall vote on whether to proceed to an impeachment. For the articles of impeachment to pass the committee, they need a simple majority of the committee members present. The committee shall publish its findings and recommendations on how to go forward, including unclassified documents, evidence, testimony, and relevant laws, except that certain testimony, evidence, or documents may be withheld to protect the identity of whistleblowers or preserve the integrity of certain aspects of the inquiry.</content></paragraph>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s200-c" identifier="/us/usc/t2/s200/c"><num value="c">(c)</num><heading> House impeachment procedures</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-c-1" identifier="/us/usc/t2/s200/c/1"><num value="1">(1)</num><content> Once the impeachment inquiry has been discharged from the committee to which the public official is accountable and the committee has decided to go forward, the chairperson of the committee shall submit articles of impeachment to the House floor, with the members voting in favor of impeachment being cosponsors.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-c-2" identifier="/us/usc/t2/s200/c/2"><num value="2">(2)</num><content> Once the impeachment inquiry report has been published, all Members of the House shall be given at least 5 hours to review the report and the articles of impeachment before voting on them.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-c-3" identifier="/us/usc/t2/s200/c/3"><num value="3">(3)</num><content> Upon submission of the articles of impeachment to the House floor, the House shall vote on the articles within 2 sessions, and the articles shall take priority.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-c-4" identifier="/us/usc/t2/s200/c/4"><num value="4">(4)</num><content> During the session in which the House votes on the articles of impeachment, only the Speaker of the House, Speaker pro tempore, or another entitled individual serving in either such office in an acting capacity may preside; two-thirds of the House of Representatives must be present; debate for the articles of impeachment shall occur; and the session shall be open for spectators.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-c-5" identifier="/us/usc/t2/s200/c/5"><num value="5">(5)</num><content> Once the requirements of paragraph (4) are fulfilled, the House of Representatives shall vote on the articles of impeachment, with a simple majority required for passage.</content></paragraph>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s200-d" identifier="/us/usc/t2/s200/d"><num value="d">(d)</num><heading> Impeachment managers</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-d-1" identifier="/us/usc/t2/s200/d/1"><num value="1">(1)</num><content> When articles of impeachment have been approved by the House of Representatives and an impeachment ordered, a board of managers shall be appointed by the Speaker of the House of Representatives, with the advice and consent of the House of Representatives, from its own Members, to prosecute the accused individual within 7 hours upon passage of the articles of impeachment. The board of managers shall have at least 1 member and not more than 6 members.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-d-2" identifier="/us/usc/t2/s200/d/2"><num value="2">(2)</num><content> Each impeachment manager must submit an affidavit, under oath, declaring that the manager holds no special interest in the impeachment of the accused public official, holds no ill will or bias against the accused public official, and will faithfully execute the manager's responsibilities and duties as an impeachment manager, to the House of Representatives and Senate upon confirmation.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-d-3" identifier="/us/usc/t2/s200/d/3"><num value="3">(3)</num><content> Impeachment managers shall act as prosecutors of the crimes alleged in the articles of impeachment. They shall present the articles of impeachment, evidence, and testimony to the Senate before the Senate votes to convict.</content></paragraph>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s200-e" identifier="/us/usc/t2/s200/e"><num value="e">(e)</num><heading> Senate trial and conviction</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-e-1" identifier="/us/usc/t2/s200/e/1"><num value="1">(1)</num><content> Upon passage of the articles of impeachment by the House of Representatives, the Senate shall immediately start the process of the impeachment trial and the articles of impeachment shall take priority. If the impeached public official is the President, the Chief Justice of the Supreme Court shall preside. If the impeached public official is any other public official with a Senate-consented position, the President pro tempore shall preside. The Vice President is prohibited from presiding over any impeachment trial.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-e-2" identifier="/us/usc/t2/s200/e/2"><num value="2">(2)</num><content> After the Senate is presented with the evidence and testimony, and with the arguments from both sides, the Senate shall review the evidence and arguments for at least 5 hours.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-e-3" identifier="/us/usc/t2/s200/e/3"><num value="3">(3)</num><content> After the 5 hours have passed, the Senate shall return to its chamber to debate and vote on the articles of impeachment. The Senate must reach two-thirds of the votes in the Senate for the articles of impeachment to pass.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200-e-4" identifier="/us/usc/t2/s200/e/4"><num value="4">(4)</num><content> Upon conviction by the Senate, the public official shall immediately cease to hold office. Congress may, within 3 days of passage of the articles and conviction, pass a resolution barring the individual from holding an office of profit or trust under the United States.</content></paragraph>
</subsection>
<sourceCredit id="rp-pl017128-s200-source-credit">(Added <ref href="/us/pl/17/128/s4">Pub. L. 17&#8211;128, &#167;&#8239;&#167; 4&#8211;8</ref>.)</sourceCredit>
</section>
<section style="-uslm-lc:I80" id="rp-pl017128-s200a" identifier="/us/usc/t2/s200a"><num value="200a">&#167;&#8239;200a.</num><heading> Compliance with congressional subpoenas; rule of construction</heading>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s200a-a" identifier="/us/usc/t2/s200a/a"><num value="a">(a)</num><heading> Compliance</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200a-a-1" identifier="/us/usc/t2/s200a/a/1"><num value="1">(1)</num><content> Any recipient of a subpoena from a congressional committee or subcommittee shall appear and testify, produce, or otherwise disclose information in a manner consistent with the subpoena and this section.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200a-a-2" identifier="/us/usc/t2/s200a/a/2"><num value="2">(2)</num><content> Unless required by the Constitution or by Federal statute, no claim of privilege or protection from disclosure shall be a ground for withholding information responsive to the subpoena or required by this section.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s200a-a-3" identifier="/us/usc/t2/s200a/a/3"><num value="3">(3)</num><content> In the case of information that is withheld, in whole or in part, by the subpoena recipient, the recipient shall, without delay, provide a log containing an express assertion and description of the ground asserted for withholding the information; the type of information; the general subject matter; the date, author, and addressee; the relationship of the author and addressee to each other; the custodian of the information; and any other descriptive information that may be produced or disclosed regarding the information that will enable the congressional committee or subcommittee issuing the subpoena to assess the ground asserted for withholding the information.</content></paragraph>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s200a-b" identifier="/us/usc/t2/s200a/b"><num value="b">(b)</num><heading> Rule of construction</heading><content> Nothing in this Act may be interpreted to limit or constrain Congress's inherent authority or foreclose any other means for enforcing compliance with congressional subpoenas, nor may anything in this Act be interpreted to establish or recognize any ground for noncompliance with a congressional subpoena. Both chambers of Congress may establish further rules, regulations, and protocols surrounding impeachments for their respective chambers.</content>
</subsection>
<sourceCredit id="rp-pl017128-s200a-source-credit">(Added <ref href="/us/pl/17/128/s10">Pub. L. 17&#8211;128, &#167;&#8239;&#167; 10&#8211;11</ref>.)</sourceCredit>
</section>
"""
    ch6 = replace_once(ch6, "</chapter>", sections + "</chapter>", "Title 2 chapter 6 close")
    text = text[:ch6_start] + ch6 + text[ch6_end:]
    write_utf8(path, text)


def update_title_28() -> None:
    path = Path("usc/usc28.xml")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t28/s1365">1365.</ref></column><column style="-uslm-lc:I46" class="twoColumnRight">Senate actions.</column>',
        '<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t28/s1365">1365.</ref></column><column style="-uslm-lc:I46" class="twoColumnRight">Congressional actions.</column>',
        1,
    )
    if 'rp-pl017128-s1365-b' in text:
        write_utf8(path, text)
        return

    start = text.find("<section", text.find('identifier="/us/usc/t28/s1365"') - 200)
    end = text.find("<section", start + 10)
    if start < 0 or end < 0:
        raise SystemExit("Could not locate 28 U.S.C. 1365")

    section = """<section style="-uslm-lc:I80" id="id885a6953-67ea-11f0-9eeb-e997de6427b9" identifier="/us/usc/t28/s1365"><num value="1365">&#167;&#8239;1365.</num><heading> Congressional actions</heading><subsection style="-uslm-lc:I11" class="indent0" id="id885a6954-67ea-11f0-9eeb-e997de6427b9" identifier="/us/usc/t28/s1365/a"><num value="a">(a)</num><heading> Jurisdiction</heading><content> The United States District Court for the District of Columbia shall have original jurisdiction, without regard to the amount in controversy, over any civil action brought by a chamber of Congress or any authorized committee or subcommittee thereof to enforce, to secure a declaratory judgment concerning the validity of, or to prevent a threatened refusal or failure to comply with, any subpoena or order issued by either chamber of Congress or its committee or subcommittee to any entity acting or purporting to act under color or authority of law or to any natural person to secure the production of documents or other materials of any kind, the answering of any deposition or interrogatory, testimony, or any combination thereof. This section shall not apply to an action to enforce, to secure a declaratory judgment concerning the validity of, or to prevent a threatened refusal to comply with, any subpoena or order issued to an officer or employee of the executive branch of the Federal Government acting within his or her official capacity, except that this section shall apply if the refusal to comply is based on the assertion of a personal privilege or objection and is not based on a governmental privilege or objection the assertion of which has been authorized by the executive branch of the Federal Government.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s1365-b" identifier="/us/usc/t28/s1365/b"><num value="b">(b)</num><heading> Civil action; expedition</heading><paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s1365-b-1" identifier="/us/usc/t28/s1365/b/1"><num value="1">(1)</num><content> Either chamber of Congress or a committee or subcommittee thereof may bring a civil action against the recipient of a subpoena issued by a congressional committee or subcommittee to enforce compliance with the subpoena.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s1365-b-2" identifier="/us/usc/t28/s1365/b/2"><num value="2">(2)</num><content> The action shall be filed in the District Court for the District of Columbia.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s1365-b-3" identifier="/us/usc/t28/s1365/b/3"><num value="3">(3)</num><content> Notwithstanding <ref href="/us/usc/t28/s1657">section 1657 of this title</ref>, it shall be the duty of every court of the United States to expedite to the greatest possible extent the disposition of any such action and appeal. Upon a showing by the plaintiff of undue delay, other irreparable harm, or good cause, a court to which an appeal of the action may be taken shall issue any necessary and appropriate writs and orders to ensure compliance with this paragraph.</content></paragraph>
<paragraph style="-uslm-lc:I12" class="indent1" id="rp-pl017128-s1365-b-4" identifier="/us/usc/t28/s1365/b/4"><num value="4">(4)</num><content> The complaint shall be accompanied by certification that the party bringing the action has in good faith conferred or attempted to confer with the recipient of the subpoena to secure compliance with the subpoena without court action.</content></paragraph>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s1365-c" identifier="/us/usc/t28/s1365/c"><num value="c">(c)</num><heading> Monetary penalties for agency noncompliance</heading><content> The court may impose monetary penalties directly against each head of a Government agency and the head of each component thereof held to have knowingly failed to comply with any part of a congressional subpoena, unless the President instructed the official not to comply and the President, or the head of the agency or component thereof, submits to the court a letter confirming such instruction and the basis for such instruction.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s1365-d" identifier="/us/usc/t28/s1365/d"><num value="d">(d)</num><heading> Waiver of noncompliance grounds</heading><content> Any ground for noncompliance asserted by the recipient of a congressional subpoena shall be deemed to have been waived as to any particular information withheld from production.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s1365-e" identifier="/us/usc/t28/s1365/e"><num value="e">(e)</num><heading> Rules of procedure</heading><content> The Supreme Court of the United States shall prescribe rules of procedure to ensure the expeditious treatment of actions described in this section. Such rules shall be prescribed and submitted to Congress. The rules shall include procedures for expeditiously considering any assertion of constitutional or Federal statutory privilege made in connection with testimony by any recipient of a subpoena from a congressional committee or subcommittee. The Supreme Court shall transmit such rules to Congress within 2 months after the effective date of this section.</content>
</subsection>
<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017128-s1365-f" identifier="/us/usc/t28/s1365/f"><num value="f">(f)</num><heading> Orders; contempt; adjournment</heading><content> Upon application by either chamber of Congress or any authorized committee or subcommittee, the district court shall issue an order to an entity or person refusing, failing to comply with, or threatening to refuse or not to comply with, a subpoena or order of either chamber of Congress or any committee or subcommittee, requiring the entity or person to comply forthwith. Any refusal or failure to obey a lawful order of the district court issued pursuant to this section may be held by such court to be a contempt thereof. A contempt proceeding shall be commenced by an order to show cause before the court why the entity or person refusing or failing to obey the court order should not be held in contempt of court. Such contempt proceeding shall be tried by the court and shall be summary in manner. The purpose of sanctions imposed as a result of such contempt proceeding shall be to compel obedience to the order of the court. Nothing in this section shall confer upon such court jurisdiction to affect by injunction or otherwise the issuance or effect of any subpoena or order of either chamber of Congress or any committee or subcommittee or to review, modify, suspend, terminate, or set aside any such subpoena or order. An action, contempt proceeding, or sanction brought or imposed pursuant to this section shall not abate upon adjournment sine die by either chamber of Congress at the end of a Congress if either chamber of Congress or any committee or subcommittee of the Senate which issued the subpoena or order certifies to the court that it maintains its interest in securing the documents, answers, or testimony during such adjournment.</content>
</subsection>
<sourceCredit id="id885a695a-67ea-11f0-9eeb-e997de6427b9">(Added <ref href="/us/pl/95/521/tVII/s705/f/1">Pub. L. 95&#8211;521, title VII, &#167;&#8239;705(f)(1)</ref>, <date date="1978-10-26">Oct. 26, 1978</date>, <ref href="/us/stat/92/1879">92 Stat. 1879</ref>, &#167;&#8239;1364; amended <ref href="/us/pl/98/620/tIV/s402/29/D">Pub. L. 98&#8211;620, title IV, &#167;&#8239;402(29)(D)</ref>, <date date="1984-11-08">Nov. 8, 1984</date>, <ref href="/us/stat/98/3359">98 Stat. 3359</ref>; renumbered &#167;&#8239;1365, <ref href="/us/pl/99/336/s6/a/1/B">Pub. L. 99&#8211;336, &#167;&#8239;6(a)(1)(B)</ref>, <date date="1986-06-19">June 19, 1986</date>, <ref href="/us/stat/100/638">100 Stat. 638</ref>; <ref href="/us/pl/104/292/s4">Pub. L. 104&#8211;292, &#167;&#8239;4</ref>, <date date="1996-10-11">Oct. 11, 1996</date>, <ref href="/us/stat/110/3460">110 Stat. 3460</ref>; <ref href="/us/pl/17/128/s9">Pub. L. 17&#8211;128, &#167;&#8239;9</ref>.)</sourceCredit>
<notes type="uscNote" id="id885a695b-67ea-11f0-9eeb-e997de6427b9">
<note style="-uslm-lc:I74" role="crossHeading" topic="editorialNotes" id="id885a695c-67ea-11f0-9eeb-e997de6427b9"><heading class="centered"><b>Editorial Notes</b></heading></note>
<note style="-uslm-lc:I74" topic="amendments" id="id885a695d-67ea-11f0-9eeb-e997de6427b9"><heading class="centered smallCaps">Amendments</heading><p style="-uslm-lc:I21" class="indent0">2023&#8212;<ref href="/us/pl/17/128/s9">Pub. L. 17&#8211;128</ref> amended section generally, substituting provisions governing actions by either chamber of Congress or any authorized committee or subcommittee thereof for provisions governing Senate actions.</p>
<p style="-uslm-lc:I21" class="indent0">1996&#8212;Subsec. (a). <ref href="/us/pl/104/292">Pub. L. 104&#8211;292</ref> substituted &#8220;executive branch of the Federal Government acting within his or her official capacity, except that this section shall apply if the refusal to comply is based on the assertion of a personal privilege or objection and is not based on a governmental privilege or objection the assertion of which has been authorized by the executive branch of the Federal Government&#8221; for &#8220;Federal Government acting within his official capacity&#8221;.</p>
<p style="-uslm-lc:I21" class="indent0">1984&#8212;Subsec. (c). <ref href="/us/pl/98/620">Pub. L. 98&#8211;620</ref> struck out subsec. (c) which provided that in any civil action or contempt proceeding brought pursuant to this section, the court had to assign the action or proceeding for hearing at the earliest practicable date and cause the action or proceeding in every way to be expedited, and that any appeal or petition for review from any order or judgment in such action or proceeding had to be expedited in the same manner.</p>
</note>
<note style="-uslm-lc:I74" role="crossHeading" topic="statutoryNotes" id="id885a695e-67ea-11f0-9eeb-e997de6427b9"><heading class="centered"><b>Statutory Notes and Related Subsidiaries</b></heading></note>
<note style="-uslm-lc:I74" topic="effectiveDateOfAmendment" id="rp-pl017128-s1365-effective-date"><heading class="centered smallCaps">Effective Date of 2023 Amendment</heading><p style="-uslm-lc:I21" class="indent0"><ref href="/us/pl/17/128/s3">Pub. L. 17&#8211;128, &#167;&#8239;3</ref>, provided that the amendment by <ref href="/us/pl/17/128/s9">section 9 of Pub. L. 17&#8211;128</ref> was effective upon passage and signature of the President.</p></note>
<note style="-uslm-lc:I74" topic="effectiveDateOfAmendment" id="id885a695f-67ea-11f0-9eeb-e997de6427b9"><heading class="centered smallCaps">Effective Date of 1984 Amendment</heading><p style="-uslm-lc:I21" class="indent0">Amendment by <ref href="/us/pl/98/620">Pub. L. 98&#8211;620</ref> not applicable to cases pending on <date date="1984-11-08">Nov. 8, 1984</date>, see <ref href="/us/pl/98/620/s403">section 403 of Pub. L. 98&#8211;620</ref>, set out as an Effective Date note under <ref href="/us/usc/t28/s1657">section 1657 of this title</ref>.</p>
</note>
<note style="-uslm-lc:I74" topic="effectiveDate" id="id885a6960-67ea-11f0-9eeb-e997de6427b9"><heading class="centered smallCaps">Effective Date</heading><p style="-uslm-lc:I21" class="indent0">Section effective <date date="1979-01-03">Jan. 3, 1979</date>, see <ref href="/us/pl/95/521/s717">section 717 of Pub. L. 95&#8211;521</ref>, set out as a note under <ref href="/us/usc/t2/s288">section 288 of Title 2</ref>, The Congress.</p>
</note>
</notes>
</section>
"""
    text = text[:start] + section + text[end:]
    write_utf8(path, text)


def update_results() -> None:
    path = Path("audit/xml-integration-results.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    updates = {
        "ACTION-0399": {
            "result_status": "applied",
            "xml_file_before": "usc02.xml",
            "xml_file_after": "usc02.xml",
            "final_section_or_subsection_identifier": "/us/usc/t2/s200",
            "actual_node_ids_added": ["rp-pl017128-s200"],
            "actual_node_ids_changed": ["rp-pl017128-codification"],
            "exact_enacted_text_applied": "Added 2 U.S.C. 200, integrating Pub. L. 17-128 sections 4 through 8 as congressional-procedure text for definitions, impeachment inquiries, House impeachment procedures, impeachment managers, and Senate trial and conviction procedures.",
            "source_file": SOURCE_FILE,
            "source_quotation": "SEC4. DEFINITIONS... SEC5. IMPEACHMENT INQUIRIES... SEC6. IMPEACHMENT... SEC7. IMPEACHMENT MANAGERS... SEC8. CONVICTION...",
            "source_credit_change": "Added source credit to 2 U.S.C. 200 for Pub. L. 17-128, secs. 4-8.",
            "amendment_note_change": "Replaced stale historical-only PL-017-128 project note with concise current-status cross-placement note.",
            "toc_change": "Added Title 2 chapter 6 TOC entry for 2 U.S.C. 200.",
        },
        "ACTION-0400": {
            "result_status": "applied",
            "xml_file_before": "usc28.xml",
            "xml_file_after": "usc28.xml",
            "final_section_or_subsection_identifier": "/us/usc/t28/s1365",
            "actual_node_ids_added": ["rp-pl017128-s1365-b", "rp-pl017128-s1365-c", "rp-pl017128-s1365-d", "rp-pl017128-s1365-e", "rp-pl017128-s1365-f", "rp-pl017128-s1365-effective-date"],
            "actual_node_ids_changed": ["id885a6953-67ea-11f0-9eeb-e997de6427b9", "id885a6954-67ea-11f0-9eeb-e997de6427b9", "id885a695a-67ea-11f0-9eeb-e997de6427b9", "id885a695d-67ea-11f0-9eeb-e997de6427b9"],
            "exact_enacted_text_applied": "Amended 28 U.S.C. 1365 generally as Congressional actions, providing District Court jurisdiction, civil subpoena-enforcement actions and expedition, monetary penalties for agency noncompliance, waiver of noncompliance grounds, Supreme Court procedural rules, compliance orders, contempt, and adjournment survival.",
            "source_file": SOURCE_FILE,
            "source_quotation": "SEC9. ENFORCEMENT OF CONGRESSIONAL SUBPOENAS 28 U.S.Code 1365 shall now read as - 28 U.S.Code 1365 - Congressional actions...",
            "source_credit_change": "Added Pub. L. 17-128, sec. 9 to the 28 U.S.C. 1365 source credit.",
            "amendment_note_change": "Added 2023 amendment note and effective-date note for Pub. L. 17-128, sec. 9.",
            "toc_change": "Changed Title 28 chapter 85 TOC item for section 1365 from Senate actions to Congressional actions.",
        },
        "ACTION-0401": {
            "result_status": "applied",
            "xml_file_before": "usc02.xml",
            "xml_file_after": "usc02.xml",
            "final_section_or_subsection_identifier": "/us/usc/t2/s200a",
            "actual_node_ids_added": ["rp-pl017128-s200a"],
            "actual_node_ids_changed": ["rp-pl017128-codification"],
            "exact_enacted_text_applied": "Added 2 U.S.C. 200a, integrating Pub. L. 17-128 sections 10 and 11 as congressional-procedure text requiring subpoena recipients to comply, limiting privilege or protection claims to constitutional or Federal statutory grounds, requiring withholding logs, and preserving congressional inherent authority and chamber rules.",
            "source_file": SOURCE_FILE,
            "source_quotation": "SEC10. COMPLYING WITH CONGRESSIONAL SUBPOENAS... SEC11. RULE OF CONSTRUCTION. Nothing in this Act may be interpreted to limit or constrain Congress inherent authority...",
            "source_credit_change": "Added source credit to 2 U.S.C. 200a for Pub. L. 17-128, secs. 10-11.",
            "amendment_note_change": "Replaced stale historical-only PL-017-128 project note with concise current-status cross-placement note.",
            "toc_change": "Added Title 2 chapter 6 TOC entry for 2 U.S.C. 200a.",
        },
    }
    for record in data["results"]:
        patch = updates.get(record.get("action_id"))
        if not patch:
            continue
        record.update(patch)
        record["baseline_commit"] = BASELINE
        record["actual_node_ids_removed"] = []
        record["validation_result"] = "XML parse pending after PL-017-128 writer pass; action tied to actual XML diff after baseline."
        record["baseline_proof"] = None

    summary = data.get("summary")
    if isinstance(summary, dict):
        counts: dict[str, int] = {}
        for record in data["results"]:
            status = record.get("result_status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        summary["result_status_counts"] = counts
        summary["blocked_actions"] = counts.get("blocked", 0)
        summary["pending_actions"] = counts.get("pending-xml-implementation", 0)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    update_title_2()
    update_title_28()
    update_results()
    print("Integrated PL-017-128 actions ACTION-0399, ACTION-0400, ACTION-0401")


if __name__ == "__main__":
    main()
