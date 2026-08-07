#!/usr/bin/env python3
import json
import re
import subprocess
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

LAWS = {
    "PL-041-271": ("https://trello.com/c/o7wxcBGl/879-public-law-41-271-the-great-change-act-of-2026", "Great Change Act of 2026", "41–271"),
    "PL-042-272": ("https://trello.com/c/9HaboxAG/934-public-law-42-272-metropolitan-police-department-public-safety-and-property-reform-act", "Metropolitan Police Department Public Safety and Property Reform Act", "42–272"),
    "PL-042-273": ("https://trello.com/c/iMCN5XiL/935-public-law-42-273-homeland-security-coordination-act", "Homeland Security Coordination Act", "42–273"),
}


def section_note(path, identifier, note):
    text = Path(path).read_text(encoding="utf-8")
    if f'id="{note_id(note)}"' in text:
        raise SystemExit(f"duplicate note {note_id(note)} in {path}")
    pat = re.compile(r'(<section\b[^>]*\bidentifier="' + re.escape(identifier) + r'"[^>]*>.*?)(</section>)', re.S)
    m = pat.search(text)
    if not m:
        raise SystemExit(f"anchor {identifier} not found in {path}")
    text = text[:m.start()] + m.group(1) + note + m.group(2) + text[m.end():]
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def note_id(note):
    m = re.search(r'\bid="([^"]+)"', note)
    if not m:
        raise ValueError("note lacks id")
    return m.group(1)


def append_to_note(path, nid, addendum, required=True):
    text = Path(path).read_text(encoding="utf-8")
    pat = re.compile(r'(<note\b[^>]*\bid="' + re.escape(nid) + r'"[^>]*>.*?)(</note>)', re.S)
    m = pat.search(text)
    if not m:
        if required:
            raise SystemExit(f"note {nid} not found in {path}")
        return False
    if addendum in m.group(1):
        return True
    text = text[:m.start()] + m.group(1) + addendum + m.group(2) + text[m.end():]
    Path(path).write_text(text, encoding="utf-8", newline="\n")
    return True


def replace_status_in_note(path, nid, status):
    text = Path(path).read_text(encoding="utf-8")
    pat = re.compile(r'(<note\b[^>]*\bid="' + re.escape(nid) + r'"[^>]*>.*?<p><b>Status\.</b>).*?(</p>)', re.S)
    text2, n = pat.subn(r'\1 ' + status + r'\2', text, count=1)
    if n != 1:
        raise SystemExit(f"status paragraph for {nid} not found in {path}")
    Path(path).write_text(text2, encoding="utf-8", newline="\n")


def clean_text(text):
    text = text.replace("\f", "\n")
    out = []
    blanks = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s == "– Printed on Recycled paper –" or re.fullmatch(r"Page \d+ of \d+", s):
            blanks += 1
            if blanks <= 1:
                out.append("")
            continue
        if s in {"○", "Loading…", "Back", "Transcript", "Close side sheet"}:
            continue
        blanks = 0
        out.append(line.rstrip())
    return "\n".join(out).strip() + "\n"


def acquire_source(law_id, card_url):
    dest = Path("codification/laws/laws") / law_id
    dest.mkdir(parents=True, exist_ok=True)
    short = card_url.split("/c/", 1)[1].split("/", 1)[0]
    req = urllib.request.Request(f"https://trello.com/c/{short}.json", headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        card = json.load(r)
    (dest / "card.json").write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    atts = card.get("attachments") or []
    pdfs = [a for a in atts if str(a.get("name","")).lower().endswith(".pdf") or a.get("mimeType") == "application/pdf"]
    if not pdfs:
        raise SystemExit(f"No PDF attachment found for {law_id}")
    att = max(pdfs, key=lambda a: int(a.get("bytes") or 0))
    url = att.get("url")
    if not url:
        raise SystemExit(f"Attachment URL missing for {law_id}")
    pdf = dest / "law.pdf"
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, pdf.open("wb") as f:
        f.write(r.read())
    txt = dest / "law.txt"
    subprocess.run(["pdftotext", "-layout", str(pdf), str(txt)], check=True)
    txt.write_text(clean_text(txt.read_text(encoding="utf-8", errors="replace")), encoding="utf-8", newline="\n")


def p(txt):
    return "<p>" + txt + "</p>"


def main():
    for law_id, (url, _title, _pl) in LAWS.items():
        acquire_source(law_id, url)

    links_path = Path("codification/laws/trello_links.json")
    links = json.loads(links_path.read_text(encoding="utf-8"))
    for law_id, (url, _title, _pl) in LAWS.items():
        links[law_id] = url
    links_path.write_text(json.dumps(links, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Pub. L. 41-271: omnibus act.  Preserve the full authenticated source and place a
    # comprehensive codification note at the general-law anchor; amend predecessor notes
    # so the current-law presentation does not leave superseded enactments looking current.
    great = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl041271-codification">'
        '<heading class="centered smallCaps">Great Change Act of 2026—Pub. L. 41–271</heading>'
        + p('<b>Status.</b> Current omnibus enactment; effective immediately except as otherwise provided. Full enacted text is preserved at <ref href="/us/pl/41/271">Pub. L. 41–271</ref>.')
        + p('<b>Title I—Repeals and cleanup.</b> Sections 101 and 107 repeal the Washington Diplomacy Complex Boundary Act and the Oath and Offices Protection Act in their entirety; section 102 repeals and terminates the National Commission on Judicial Activity, Efficiency and Accountability Act and Commission. Sections 103–106 govern supersession, preservation of valid final actions, technical corrections, and nonrevival of repealed authorities.')
        + p('<b>Title II—National security eligibility.</b> Sections 201–207 abolish automatic security clearances and automatic SCI/SAP or other compartmented access by virtue of office; amend the Streamlining and Protecting American Security Act and National Security Act of 2026; prescribe individualized adjudication, need-to-know, emergency-suspension safeguards, expedited access, Inspector General and congressional oversight, anti-retaliation protections, and classification safeguards.')
        + p('<b>Title III—Commerce, labor, and administrative functions.</b> Sections 301–311 amend the Commerce Dispersal Act. They establish a Bureau of Commerce and Intellectual Property within the Department of State; transfer foreign-trade and administrative intellectual-property/business functions to State; transfer the Solicitor of Labor, FCC, FTC, NLRB labor, and general enforcement functions described by the Act to the Department of Justice; place specified commerce and intellectual-property disputes in the United States District Court for the District of Columbia; transfer copyright administration to State; and preserve existing licenses, registrations, rights, and pending matters.')
        + p('<b>Title IV—18 U.S.C. 205 and legal practice.</b> Sections 401–406 replace the amendments made by section IV of H.R. 2206 to subsections (a) and (j) of section 205 of title 18, define principal officer, employee, covered matter, nonpublic government information, and proper discharge of official duties, and preserve authorized government legal work and lawful bar/public-defender/government-counsel functions. The amendment is controlling over the earlier H.R. 2206 formulation.')
        + p('<b>Title V—Commissioned-service staffing.</b> Sections 501–504 reduce statutory minimum commissioned-officer requirements as stated in the Act, separately require not fewer than five commissioned officers unless a lower number is otherwise authorized, authorize renewable thirty-day written waivers, preserve appointment and command authority, and protect otherwise-lawful actions from invalidity based solely on staffing noncompliance. The enacted four/five wording is preserved without editorial harmonization.')
        + p('<b>Title VI—Whistleblowers and accountability.</b> Sections 601–604 add protected-disclosure, anti-retaliation, burden-of-proof/remedy, and identity-confidentiality provisions to the Whistleblower Protections Act of 2023. Sections 605–607 establish generally applicable duties concerning compliance with lawful oversight and orders, supervisory responsibility, referrals, and periodic Inspector General reporting.')
        + p('<b>Title VII.</b> Section 701 supplies successor-office and conforming-reference rules for functions, offices, authorities, and security-access concepts amended, repealed, transferred, renamed, or superseded by the Act.')
        + '</note>'
    )
    section_note("usc/usc01.xml", "/us/usc/t1/s1", great)

    # Update the principal predecessor notes affected by Pub. L. 41-271.
    replace_status_in_note("usc/usc40.xml", "rp-pl028206-codification", "Repealed in its entirety by <ref href=\"/us/pl/41/271/s101\">Pub. L. 41–271, § 101</ref>; retained solely as statutory history.")
    replace_status_in_note("usc/usc50.xml", "rp-pl017130-codification", "Repealed in its entirety by <ref href=\"/us/pl/41/271/s107\">Pub. L. 41–271, § 107</ref>; retained solely as statutory history.")
    replace_status_in_note("usc/usc50.xml", "rp-pl027196-codification", "Repealed and the Commission terminated by <ref href=\"/us/pl/41/271/s102\">Pub. L. 41–271, § 102</ref>; retained solely as statutory history.")
    append_to_note("usc/usc18.xml", "rp-pl022164-codification", p('<b>2026 amendment.</b> <ref href="/us/pl/41/271/s201">Pub. L. 41–271, § 201</ref> repealed the automatic-clearance provision and replaced it with individualized clearance, vetting, need-to-know, access-approval, review, suspension, limitation, and revocation requirements; expedited review is permitted but does not constitute automatic clearance.'))
    append_to_note("usc/usc50.xml", "rp-pl038263-codification", p('<b>2026 amendment.</b> <ref href="/us/pl/41/271/s202">Pub. L. 41–271, § 202</ref> removed the phrase “RaymondLWeston was here”; added clearance, compartmented-access, need-to-know, and eligibility definitions; limited who may initiate determinations; added emergency-suspension and disclosure oversight safeguards; enlarged the judicial-review filing period from 7 to 14 days; and prohibited procedures authorizing automatic clearance/access or eligibility restrictions inconsistent with the amended Act.'))
    append_to_note("usc/usc15.xml", "rp-pl036256-codification", p('<b>2026 amendment.</b> Title III of <ref href="/us/pl/41/271">Pub. L. 41–271</ref> comprehensively amended the Commerce Dispersal Act. The controlling transfers and successor functions are described in the Pub. L. 41–271 codification note and full source text.'))
    append_to_note("usc/usc18.xml", "rp-pl022160-codification", p('<b>2026 amendment.</b> Sections 401–406 of <ref href="/us/pl/41/271">Pub. L. 41–271</ref> replace the H.R. 2206 amendments to 18 U.S.C. 205(a) and (j), define controlling terms, and preserve authorized federal legal work and lawful legal-practice functions.'))
    append_to_note("usc/usc18.xml", "rp-pl015094-codification", p('<b>2026 amendment.</b> Sections 601–604 of <ref href="/us/pl/41/271">Pub. L. 41–271</ref> add sections 4 through 7 governing protected disclosures, prohibited retaliation, burden of proof and remedies, and confidentiality of whistleblower identity.'))

    # Pub. L. 42-272 is a permanent local District of Columbia/MPD enactment.  Following
    # the repository's treatment of the MPD Relocation Act, retain it as a complete special-law
    # statutory note rather than fabricating positive-law section numbers.
    mpd = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl042272-codification">'
        '<heading class="centered smallCaps">Metropolitan Police Department Public Safety and Property Reform Act—Pub. L. 42–272</heading>'
        + p('<b>Status.</b> Current permanent District of Columbia public-safety enactment; effective immediately. Full enacted text is preserved at <ref href="/us/pl/42/272">Pub. L. 42–272</ref>.')
        + p('<b>Codification.</b> Because this Act principally governs the Metropolitan Police Department and District public property rather than amending a numbered title of the United States Code, it is retained as an uncodified statutory note consistent with the repository treatment of other MPD-specific enactments.')
        + p('<b>Operative subjects.</b> Sections 2–17 define covered terms and govern MPD general authority; District parks and public grounds; towing, impoundment, abandoned vehicles, releases and appeals; closures, evacuations, curfews and emergency orders; police perimeters and barricades; special-event security; administrative warrants; the MPD Homeland Security Bureau and its Assistant Chief; records, notices and publication; regulations and interagency coordination; prohibited abuse; and savings/conforming rules. Section 18 is a severability clause notwithstanding its enacted heading “EFFECTIVE DATE”; section 19 makes the Act effective immediately.')
        + p('<b>Interagency limitation.</b> The Act preserves the lawful jurisdiction of DHS, D.C. Fire and EMS, USSS, USCP, USMS, FBI and other agencies, and expressly prevents MPD from superseding agencies exercising the exclusive authorities identified in section 15(h).')
        + '</note>'
    )
    section_note("usc/usc01.xml", "/us/usc/t1/s1", mpd)

    # Pub. L. 42-273 creates and codifies a DHS operational center.  Its permanent law is
    # classified to Title 6 as a statutory note because Congress did not assign a Code section.
    hsca = (
        '<note style="-uslm-lc:I74" topic="statutoryNotes" id="rp-pl042273-codification">'
        '<heading class="centered smallCaps">Homeland Security Coordination Act—Pub. L. 42–273</heading>'
        + p('<b>Status.</b> Current permanent homeland-security enactment; effective immediately. Full enacted text is preserved at <ref href="/us/pl/42/273">Pub. L. 42–273</ref>.')
        + p('<b>Federal Law Enforcement Communications Center.</b> Sections 2–4 codify and continue the Federal Law Enforcement Communications Center within DHS, define its operational communications, notification, alerting, deconfliction and public-safety mission, establish a presidentially appointed and Senate-confirmed Director, and prescribe extensive administrative, neutrality, recordkeeping, reporting, continuity, acting-service and removal provisions. The Center is not an independent law-enforcement or command agency.')
        + p('<b>Mandatory coordination.</b> Sections 5–8 require participating agencies to use the Center for covered joint-agency events, patrols and operations; prescribe agency-liaison/contact duties; establish incident notifications, alerts, common operating-picture and operational-deconfliction rules; and govern support for National Special Security Events, protective operations and special events while preserving the command authority and legal responsibilities of participating agencies.')
        + p('<b>Standards, records and safeguards.</b> Sections 9–14 govern communications standards, training, exercises, professionalism, records and logs, situation reports, after-action review, limitations on command authority, information security, prohibited interference or misuse, compliance, Inspector General oversight and congressional notification.')
        + p('<b>Supersession and construction.</b> Section 15 supersedes inconsistent executive orders and specifically disclaims codification or ratification of the Presidential Commission on Law Enforcement established by Executive Order 32-4; Executive Orders 26-2 and 32-4 remain effective only to the extent consistent with the Act. Section 16 preserves agency jurisdiction, chains of command, direct communications, lawful information restrictions, emergency action and oversight while prohibiting partisan or unrelated intelligence use of the Center. Sections 17 and 18 provide severability and immediate effectiveness.')
        + '</note>'
    )
    section_note("usc/usc06.xml", "/us/usc/t6/s1", hsca)

    # XML well-formedness is mandatory.
    for f in ["usc/usc01.xml", "usc/usc06.xml", "usc/usc15.xml", "usc/usc18.xml", "usc/usc40.xml", "usc/usc50.xml"]:
        ET.parse(f)

    # The one-shot workflow and integration helper are implementation machinery, not part
    # of the resulting Code branch.
    Path(".github/workflows/integrate-new-public-laws.yml").unlink(missing_ok=True)
    Path(__file__).unlink(missing_ok=True)
    print("Integrated Pub. L. 41-271, 42-272, and 42-273")


if __name__ == "__main__":
    main()
