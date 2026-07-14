from __future__ import annotations

import json
import re
from pathlib import Path


BASELINE = "00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46"
SOURCE_FILE = "codification/laws/laws/PL-017-127/law.txt"


def write_utf8(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def replace_section(text: str, identifier: str, replacement: str) -> str:
    pos = text.find(f'identifier="{identifier}"')
    if pos < 0:
        raise SystemExit(f"Missing section {identifier}")
    start = text.rfind("<section", 0, pos)
    if start < 0:
        raise SystemExit(f"Could not bound section {identifier}")
    depth = 0
    end = -1
    for match in re.finditer(r"<section\b|</section>", text[start:]):
        token = match.group(0)
        if token.startswith("<section"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                end = start + match.end()
                break
    if end < 0:
        raise SystemExit(f"Could not find closing section for {identifier}")
    return text[:start] + replacement + text[end:]


def section_1101() -> str:
    defs = [
        ("1", 'The terms "Roblox group" and "United States" refer to the United States of America Roblox owned by Jecxb.I. https://www.roblox.com/groups/12238375/United-States-f-America-Roblox#!/about'),
        ("2", 'The term "advocates" includes, but is not limited to, advises, recommends, furthers by overt act, and admits belief in.'),
        ("3", 'The term "alien" means any person not a citizen or national of the United States.'),
        ("4", 'The term "doctrine" includes, but is not limited to, policies, practices, purposes, aims, or procedures.'),
        ("5", 'The term "application for admission" means an individual request to the Roblox group.'),
        ("6", 'The term "Attorney General" means the Attorney General of the United States.'),
        ("7", 'The term "Secretary" means the Secretary of Homeland Security.'),
        ("8", 'The term "removal judge" means the district court judge designated by the Chief Justice to hear applications for removal.'),
        ("9", 'The term "foreign state" includes outlying possessions of a foreign state, but self-governing dominions or territories under mandate or trusteeship shall be regarded as separate foreign states.'),
        ("10", 'The term "classified information" means information which, for reasons of national security, is specifically designated by a United States Government agency for limited or restricted dissemination or distribution.'),
        ("11", 'The terms "admission" and "admitted" mean, with respect to an alien, the lawful entry of the alien into the United States by accepting the request to join the group and ranking the alien American Citizen after inspection and authorization by an immigration officer.'),
        ("12", 'The term "immigration officer" means any employee or class of employees of the Service or of the United States designated by the Secretary of Homeland Security, individually or by regulation, to perform the functions of an immigration officer specified by this chapter or any section of this title.'),
        ("13", 'The term "national" means a person in the Roblox group, ranked American Citizen or higher.'),
        ("14", 'The term "national security" means the national defense, foreign relations, or economic interests of the United States.'),
        ("15", 'The term "Service" means the Citizenship and Immigration Service, under the Department of Homeland Security.'),
        ("16", 'The term "Director" means the Director of the Citizenship and Immigration Service, under the Department of Homeland Security.'),
        ("17", 'The term "terrorist activity" means violent criminal acts committed by individuals or groups who are inspired by, or associated with, designated foreign terrorist organizations or nations.'),
        ("18", 'The term "alien terrorist" means any alien who has engaged in terrorist activity; whom a consular officer, the Attorney General, or the Secretary of Homeland Security knows, or has reasonable ground to believe, is engaged in or is likely to engage after entry in any terrorist activity; who is a representative of a terrorist organization or of a political, social, or other group that endorses or espouses terrorist activity; or who is a member of a designated terrorist organization, and is inadmissible for entry into the United States unless the alien did not reasonably know of the actions of such terrorist organization.'),
        ("19", 'The term "organization" means, but is not limited to, an organization, corporation, company, partnership, association, trust, foundation, or fund, and includes a group of persons, whether or not incorporated, permanently or temporarily associated together with joint action on any subject or subjects.'),
        ("20", 'The term "immigrant" means every alien except an alien who is an ambassador, public minister, or career diplomatic or consular officer accredited by a foreign government recognized de jure by the United States and accepted by the President or Secretary of State, and, on a basis of reciprocity, other accredited officials and employees accepted by the Secretary of State.'),
    ]
    body = "\n".join(
        f'<paragraph style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1101-a-{n}" identifier="/us/usc/t8/s1101/a/{n}"><num value="{n}">({n})</num><content> {txt}</content></paragraph>'
        for n, txt in defs
    )
    return f"""<section style="-uslm-lc:I80" id="rp-pl017127-s1101" identifier="/us/usc/t8/s1101"><num value="1101">&#167;&#8239;1101.</num><heading> Definitions</heading><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1101-a" identifier="/us/usc/t8/s1101/a"><num value="a">(a)</num><chapeau> As used in this chapter:</chapeau>{body}
</subsection><sourceCredit id="rp-pl017127-s1101-source-credit">(Amended generally <ref href="/us/pl/17/127/s6">Pub. L. 17&#8211;127, &#167;&#8239;6</ref>.)</sourceCredit></section>
"""


def simple_section(num: str, heading: str, body: str, sec: str) -> str:
    return f"""<section style="-uslm-lc:I80" id="rp-pl017127-s{num}" identifier="/us/usc/t8/s{num}"><num value="{num}">&#167;&#8239;{num}.</num><heading> {heading}</heading>{body}<sourceCredit id="rp-pl017127-s{num}-source-credit">(Amended generally <ref href="/us/pl/17/127/s{sec}">Pub. L. 17&#8211;127, &#167;&#8239;{sec}</ref>.)</sourceCredit></section>
"""


def update_title_8() -> None:
    path = Path("usc/usc08.xml")
    text = path.read_text(encoding="utf-8")
    if "rp-pl017127-s1534-j" in text:
        return

    text = replace_section(text, "/us/usc/t8/s1101", section_1101())
    text = replace_section(
        text,
        "/us/usc/t8/s1551",
        simple_section(
            "1551",
            "Citizenship and Immigration Service",
            '<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1551-a" identifier="/us/usc/t8/s1551/a"><num value="a">(a)</num><content> Under the Department of Homeland Security there shall be an agency known as the Citizenship and Immigration Service.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1551-b" identifier="/us/usc/t8/s1551/b"><num value="b">(b)</num><content> The head of the Citizenship and Immigration Service shall be the Director of the Citizenship and Immigration Service, who shall report directly to the Secretary or other designated persons as established by this Act or other policy.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1551-c" identifier="/us/usc/t8/s1551/c"><num value="c">(c)</num><content> The Service shall administer the United States naturalization and immigration system, adhering to all applicable laws and regulations.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1551-d" identifier="/us/usc/t8/s1551/d"><num value="d">(d)</num><content> Immigration officers shall have the power to accept or deny applications of admission by accepting or denying requests to join the Roblox group and ranking them American Citizen.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1551-e" identifier="/us/usc/t8/s1551/e"><num value="e">(e)</num><content> The Service shall be led by the Secretary, Director, and Deputy Director.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1551-f" identifier="/us/usc/t8/s1551/f"><num value="f">(f)</num><content> The Director of the Service shall establish policies for functions transferred to or otherwise vested in the Director by law; oversee administration of such policies; advise the Secretary on policies or operations affecting other agencies or departments; establish national immigration services policies and priorities; and send reports to the Committees on the Judiciary of the House of Representatives and the Senate describing internal affairs operations at Citizenship and Immigration Services.</content></subsection>',
            "7",
        ),
    )
    # Later PL 31-227 keeps section 1102 in repeal-history/reserved posture, so do not revive it here.
    text = replace_section(
        text,
        "/us/usc/t8/s1103",
        simple_section(
            "1103",
            "Powers and duties of the Secretary",
            '<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1103-a" identifier="/us/usc/t8/s1103/a"><num value="a">(a)</num><content> The Secretary of Homeland Security shall be charged with the administration and enforcement of this chapter and all other laws relating to the immigration and naturalization of aliens, except insofar as this chapter or such laws relate to powers, functions, and duties conferred upon the President, Attorney General, Secretary of State, officers of the Department of State, or diplomatic or consular officers; provided, however, that determination and ruling by the Attorney General with respect to all questions of law shall be controlling.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1103-b" identifier="/us/usc/t8/s1103/b"><num value="b">(b)</num><content> The Secretary shall have control, direction, and supervision of all employees and files and records of the Service.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1103-c" identifier="/us/usc/t8/s1103/c"><num value="c">(c)</num><content> The Secretary shall establish regulations, prescribe forms of bond, reports, entries, and other papers, issue instructions, and perform other acts necessary for carrying out authority under this chapter.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1103-d" identifier="/us/usc/t8/s1103/d"><num value="d">(d)</num><content> The Secretary may require or authorize any employee of the Service or Department of Justice to perform or exercise any power, privilege, or duty conferred or imposed by this chapter or regulations upon any other employee of the Service.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1103-e" identifier="/us/usc/t8/s1103/e"><num value="e">(e)</num><content> The Secretary may confer or impose upon any employee of the United States, with the consent of the head of the department or independent establishment under whose jurisdiction the employee is serving, any power, privilege, or duty conferred or imposed by this chapter or regulations upon officers or employees of the Service.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1103-f" identifier="/us/usc/t8/s1103/f"><num value="f">(f)</num><content> The Secretary shall have the power and duty to control and guard the boundaries and borders of the United States against illegal entry of aliens and shall appoint such employees of the Service as are necessary and proper for that purpose.</content></subsection>',
            "9",
        ),
    )
    text = replace_section(
        text,
        "/us/usc/t8/s1105",
        simple_section(
            "1105",
            "Matters pertaining to internal security; data exchange",
            '<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1105-a" identifier="/us/usc/t8/s1105/a"><num value="a">(a)</num><content> The Director shall have authority to maintain direct and continuous liaison with the Directors of the Federal Bureau of Investigation and the Central Intelligence Agency and with other internal security officers of the Government for obtaining and exchanging information for use in enforcing this chapter in the interest of the internal and border security of the United States.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1105-b" identifier="/us/usc/t8/s1105/b"><num value="b">(b)</num><content> The Attorney General and the Director of the Federal Bureau of Investigation shall provide the Department of Homeland Security and the Service access to criminal history record information in the National Crime Information Center, the Wanted Persons File, and other mutually agreed NCIC files for determining whether an applicant for admission has a criminal history record indexed in any such file.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1105-c" identifier="/us/usc/t8/s1105/c"><num value="c">(c)</num><content> Before receiving access to NCIC data, and not later than 2 weeks after enactment of this Act, the Department of Homeland Security shall promulgate final regulations to limit dissemination of such information; ensure that it is used solely to determine whether to admit an alien; ensure the security, confidentiality, and destruction of such information; and protect privacy rights of individuals who are subjects of such information.</content></subsection>',
            "10",
        ),
    )
    text = replace_section(
        text,
        "/us/usc/t8/s1182",
        simple_section(
            "1182",
            "Qualifications for admission of aliens",
            '<chapeau style="-uslm-lc:I11" class="indent0">Except as otherwise provided in this chapter, aliens who are inadmissible under the following paragraphs are ineligible to be admitted to the United States:</chapeau><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1182-a" identifier="/us/usc/t8/s1182/a"><num value="a">(a)</num><heading> Alternative accounts</heading><content> In determining the legitimacy of an alien account status, immigration officers shall consider account age, including whether the account was created within the last 120 days; acquaintances, including whether any friends have known homeland-security concerns or are flagged in the NCIC database; and possessions of the alien, including clothing and accessories.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1182-b" identifier="/us/usc/t8/s1182/b"><num value="b">(b)</num><heading> Association with foreign terrorist organizations or enemies of the United States</heading><content> Voluntarily performing any terrorist activity before, or while having, a pending application for admission is a ground of inadmissibility.</content></subsection>',
            "11",
        ),
    )
    text = replace_section(
        text,
        "/us/usc/t8/s1189",
        simple_section(
            "1189",
            "Designation of foreign terrorist organizations",
            '<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1189-a" identifier="/us/usc/t8/s1189/a"><num value="a">(a)</num><content> The Secretary is authorized to designate an organization as a foreign terrorist organization if the Secretary finds that the organization is foreign; engages in terrorist activity, or retains the capability and intent to engage in terrorist activity or terrorism; and the terrorist activity or terrorism threatens the security of United States nationals or the national security of the United States.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1189-b" identifier="/us/usc/t8/s1189/b"><num value="b">(b)</num><content> Seven days before making a designation, the Secretary shall, by classified communication, notify the Speaker and Minority Leader of the House of Representatives, the President pro tempore, Majority Leader, and Minority Leader of the Senate, and members of relevant committees, in writing, of the intent to designate the organization, the findings, and the factual basis.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1189-c" identifier="/us/usc/t8/s1189/c"><num value="c">(c)</num><content> Any designation under this section shall cease upon a congressional joint resolution disapproving the designation.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1189-d" identifier="/us/usc/t8/s1189/d"><num value="d">(d)</num><content> The Secretary may consider classified information in making a designation. Classified information shall not be subject to disclosure while it remains classified, except that it may be disclosed to a court ex parte and in camera for judicial review.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1189-e" identifier="/us/usc/t8/s1189/e"><num value="e">(e)</num><content> Any designation shall be effective for all purposes until revoked.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1189-f" identifier="/us/usc/t8/s1189/f"><num value="f">(f)</num><content> The Secretary may revoke a designation at any time.</content></subsection>',
            "12",
        ),
    )
    text = replace_section(
        text,
        "/us/usc/t8/s1532",
        simple_section(
            "1532",
            "Establishment of removal court",
            '<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1532-a" identifier="/us/usc/t8/s1532/a"><num value="a">(a)</num><content> The Chief Justice of the United States shall publicly designate 1 district court judge from the United States District Court for the District of Columbia who shall constitute a court with jurisdiction to conduct all removal proceedings.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1532-b" identifier="/us/usc/t8/s1532/b"><num value="b">(b)</num><content> Each judge designated by the Chief Justice shall serve until another judge is designated.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1532-c" identifier="/us/usc/t8/s1532/c"><num value="c">(c)</num><content> The Chief Judge of the District Court shall promulgate rules to facilitate the functioning of the removal court and assign consideration of cases to the judge on the removal court.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1532-d" identifier="/us/usc/t8/s1532/d"><num value="d">(d)</num><content> The removal court may provide for designation of a panel of attorneys who have security clearances for classified information, have signed nondisclosure agreements with the United States Government, and have agreed to represent aliens with respect to classified information.</content></subsection>',
            "13",
        ),
    )
    text = replace_section(
        text,
        "/us/usc/t8/s1533",
        simple_section(
            "1533",
            "Removal court procedure",
            '<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1533-a" identifier="/us/usc/t8/s1533/a"><num value="a">(a)</num><content> In any case in which the Secretary has classified information that an alien is an alien terrorist, the Secretary may transmit a request to the Attorney General to seek removal by filing an application with the removal court containing the identity of the Department of Justice attorney making the application, an affidavit by the Attorney General or Deputy Attorney General, the alien identity by Roblox username and Discord if applicable, and facts and circumstances establishing probable cause that the alien is an alien terrorist, is in the United States, and poses a risk to national security.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1533-b" identifier="/us/usc/t8/s1533/b"><num value="b">(b)</num><content> An application shall be submitted ex parte and in a sealed channel.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1533-c" identifier="/us/usc/t8/s1533/c"><num value="c">(c)</num><content> The Attorney General may dismiss a removal action at any stage of the proceeding.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1533-d" identifier="/us/usc/t8/s1533/d"><num value="d">(d)</num><content> In determining whether to grant an application, the removal judge may consider ex parte and in the sealed channel other information, including classified information presented under oath or affirmation, and testimony received in a hearing of which a verbatim record is kept.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1533-e" identifier="/us/usc/t8/s1533/e"><num value="e">(e)</num><content> The judge shall grant the application if there is probable cause to believe that the alien has been correctly identified and is an alien terrorist present in the United States and that the alien poses a risk to national security.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1533-f" identifier="/us/usc/t8/s1533/f"><num value="f">(f)</num><content> Upon granting the application, the alien shall be placed in the custody of the Federal Bureau of Prisons for the duration of the trial.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1533-g" identifier="/us/usc/t8/s1533/g"><num value="g">(g)</num><content> If the judge denies the requested order, the judge shall prepare a written statement of reasons for denial, taking precautions not to disclose classified information in the Government application.</content></subsection>',
            "13",
        ),
    )
    text = replace_section(
        text,
        "/us/usc/t8/s1534",
        simple_section(
            "1534",
            "Removal hearing",
            '<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-a" identifier="/us/usc/t8/s1534/a"><num value="a">(a)</num><content> In any case in which an application for an order is approved, a removal hearing shall be conducted as expeditiously as practicable to determine whether the alien should be removed from the United States on the ground that the alien is an alien terrorist.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-b" identifier="/us/usc/t8/s1534/b"><num value="b">(b)</num><content> The removal hearing may be open to the public unless classified information will be used as evidence.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-c" identifier="/us/usc/t8/s1534/c"><num value="c">(c)</num><content> The alien shall receive reasonable notice of the nature of the charges, including a general account of the basis for the charges, and the time and place of the hearing.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-e" identifier="/us/usc/t8/s1534/e"><num value="e">(e)</num><content> The alien shall have the right to be represented by the attorney panel under section 1532(d) and a reasonable opportunity to introduce evidence on the alien own behalf.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-f" identifier="/us/usc/t8/s1534/f"><num value="f">(f)</num><content> Nothing in this subchapter prevents the United States from seeking protective orders and asserting privileges ordinarily available to protect classified information, including military and State secrets privileges.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-g" identifier="/us/usc/t8/s1534/g"><num value="g">(g)</num><content> Following receipt of evidence, the Government and alien shall have fair opportunity to present arguments. The Government shall open, the alien may reply, and the Government may reply in rebuttal.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-h" identifier="/us/usc/t8/s1534/h"><num value="h">(h)</num><content> The Government bears the burden to prove by a preponderance of the evidence that the alien is subject to removal because the alien is an alien terrorist.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-i" identifier="/us/usc/t8/s1534/i"><num value="i">(i)</num><content> The Federal Rules of Evidence shall not apply in a removal hearing.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1534-j" identifier="/us/usc/t8/s1534/j"><num value="j">(j)</num><content> At the time of issuing a decision, the judge shall prepare a written order containing findings of fact and conclusions of law. Any portion revealing the substance or source of information received in sealed and ex parte communications shall not be made available to the alien or public.</content></subsection>',
            "13",
        ),
    )
    text = replace_section(
        text,
        "/us/usc/t8/s1481",
        simple_section(
            "1481",
            "Loss of nationality by voluntary action",
            '<subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1481-a" identifier="/us/usc/t8/s1481/a"><num value="a">(a)</num><content> A person who is a national of the United States shall lose nationality by voluntarily performing, with intent to relinquish United States nationality, naturalization in a foreign state; an oath or declaration of allegiance to a foreign state; service in foreign armed forces engaged in hostilities against the United States or as a commissioned or noncommissioned officer; service in or employment under a foreign government or political subdivision while having or acquiring that nationality; service in a foreign office requiring an oath or declaration of allegiance; formal renunciation before a United States diplomatic or consular officer abroad; or treason, attempted overthrow, bearing arms against the United States, violation or conspiracy under section 2383 of title 18, or seditious conspiracy under section 2384 of title 18, upon conviction by court martial or a court of competent jurisdiction.</content></subsection><subsection style="-uslm-lc:I11" class="indent0" id="rp-pl017127-s1481-b" identifier="/us/usc/t8/s1481/b"><num value="b">(b)</num><content> The Attorney General and Secretary may submit an application for removal of a United States national to the removal courts, which shall follow the same process as established in sections 1533 and 1534 of this title.</content></subsection>',
            "13",
        ),
    )
    write_utf8(path, text)


def update_results() -> None:
    path = Path("audit/xml-integration-results.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    patches = {
        "ACTION-0395": {
            "final_section_or_subsection_identifier": "/us/usc/t8/s1101 | /us/usc/t8/s1551 | /us/usc/t8/s1103 | /us/usc/t8/s1105",
            "actual_node_ids_added": ["rp-pl017127-s1101", "rp-pl017127-s1551", "rp-pl017127-s1103", "rp-pl017127-s1105"],
            "exact_enacted_text_applied": "Replaced Title 8 definitions, Citizenship and Immigration Service, Secretary powers, and internal-security/data-exchange sections with PL-017-127 sections 6, 7, 9, and 10 text. Section 1102 was not revived because later PL-031-227 leaves the section in repeal-history/reserved posture.",
            "source_quotation": "SEC6. DEFINITIONS... SEC7. ESTABLISHING OF THE SERVICE... SEC9. POWERS AND DUTIES OF THE SECRETARY... SEC10. MATTER PERTAINING TO INTERNAL SECURITY; DATA EXCHANGE...",
        },
        "ACTION-0396": {
            "final_section_or_subsection_identifier": "/us/usc/t8/s1182 | /us/usc/t8/s1189",
            "actual_node_ids_added": ["rp-pl017127-s1182", "rp-pl017127-s1189"],
            "exact_enacted_text_applied": "Replaced 8 U.S.C. 1182 with PL-017-127 admission-qualification grounds and 8 U.S.C. 1189 with PL-017-127 foreign-terrorist-organization designation procedures.",
            "source_quotation": "SEC11. QUALIFICATIONS FOR ADMISSION OF ALIENS... SEC 12. DESIGNATION OF FOREIGN TERRORIST ORGANISATIONS...",
        },
        "ACTION-0397": {
            "final_section_or_subsection_identifier": "/us/usc/t8/s1532 | /us/usc/t8/s1533 | /us/usc/t8/s1534 | /us/usc/t8/s1481",
            "actual_node_ids_added": ["rp-pl017127-s1532", "rp-pl017127-s1533", "rp-pl017127-s1534", "rp-pl017127-s1481"],
            "exact_enacted_text_applied": "Replaced alien-terrorist removal court sections 1532 through 1534 and nationality-loss section 1481 with PL-017-127 section 13 text.",
            "source_quotation": "SEC13. ALIEN TERRORIST REMOVAL... 8 U.S.Code 1532 shall now read as... 8 U.S.Code 1533 shall now read as... 8 U.S.Code 1534 shall now read as... 8 U.S.Code 1481 shall now read as...",
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
                "xml_file_before": "usc08.xml",
                "xml_file_after": "usc08.xml",
                "actual_node_ids_changed": ["rp-pl017127-codification"],
                "actual_node_ids_removed": [],
                "source_file": SOURCE_FILE,
                "source_credit_change": "Added Pub. L. 17-127 source credits to the affected Title 8 replacement sections.",
                "amendment_note_change": "Retained concise PL-017-127 repeal-or-conflict history note; operative replacement text is now in affected Title 8 sections.",
                "toc_change": "No separate TOC update required by plan; affected section identifiers remain existing Title 8 sections.",
                "validation_result": "XML parse pending after PL-017-127 writer pass; action tied to actual XML diff after baseline.",
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
    update_title_8()
    update_results()
    print("Integrated PL-017-127 actions ACTION-0395, ACTION-0396, ACTION-0397")


if __name__ == "__main__":
    main()
