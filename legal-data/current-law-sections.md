# 2026 Substantive Current-Law Codification

This register documents the editorial U.S. Code classification applied at build time for three enacted USAR laws. Congress's failure to supply a U.S. Code section number is not treated as a reason to leave general and permanent law uncodified. The assigned Code numbers below are editorial classifications; the source credits identify the enactment and source section.

## Homeland Security Coordination Act — H.R. 9, 42d Congress

Classified to **Title 6, chapter 7, Federal Law Enforcement Communications and Coordination**:

- 6 U.S.C. § 1801 — Definitions (source § 2)
- 6 U.S.C. § 1802 — Federal Law Enforcement Communications Center (source § 3)
- 6 U.S.C. § 1803 — Director (source § 4)
- 6 U.S.C. § 1804 — Required use for joint-agency events, patrols, and operations (source § 5)
- 6 U.S.C. § 1805 — Participating agencies and liaisons (source § 6)
- 6 U.S.C. § 1806 — Incident notifications, common operating picture, and deconfliction (source § 7)
- 6 U.S.C. § 1807 — National Special Security Events and protective operations (source § 8)
- 6 U.S.C. § 1808 — Communications standards, training, exercises, and interoperability (source § 9)
- 6 U.S.C. § 1809 — Records, logs, situation reports, and after-action reviews (source § 10)
- 6 U.S.C. § 1810 — Limitations on command authority and agency jurisdiction (source § 11)
- 6 U.S.C. § 1811 — Information security (source § 12)
- 6 U.S.C. § 1812 — Prohibited conduct, interference, and misuse (source § 13)
- 6 U.S.C. § 1813 — Oversight, compliance, and congressional notification (source § 14)
- 6 U.S.C. § 1814 — Supersession of inconsistent executive-order provisions (source § 15)
- 6 U.S.C. § 1815 — Rule of construction (source § 16)

Source §§ 1, 17, and 18 are retained as short-title, severability, and effective-date notes at § 1801.

## Metropolitan Police Department Public Safety and Property Reform Act — H.R. 2, 42d Congress

Classified to **Title 40, subtitle II, part D, chapter 97, Metropolitan Police Public Safety and Property Authority**:

- 40 U.S.C. § 9701 — Definitions (source § 2)
- 40 U.S.C. § 9702 — General MPD authority (source § 3)
- 40 U.S.C. § 9703 — D.C. parks and public grounds (source § 4)
- 40 U.S.C. § 9704 — Towing and impoundment (source § 5)
- 40 U.S.C. § 9705 — Abandoned vehicles (source § 6)
- 40 U.S.C. § 9706 — Vehicle release procedures (source § 7)
- 40 U.S.C. § 9707 — Impoundment and tow appeals (source § 8)
- 40 U.S.C. § 9708 — Closures, evacuation orders, curfews, and emergency restrictions (source § 9)
- 40 U.S.C. § 9709 — Police perimeters and barricades (source § 10)
- 40 U.S.C. § 9710 — Special-event security (source § 11)
- 40 U.S.C. § 9711 — Administrative warrants (source § 12)
- 40 U.S.C. § 9712 — Homeland Security Bureau (source § 13)
- 40 U.S.C. § 9713 — Records, notices, and publication (source § 14)
- 40 U.S.C. § 9714 — Regulations and relationship to other agencies (source § 15)
- 40 U.S.C. § 9715 — Prohibited abuse of authority (source § 16)
- 40 U.S.C. § 9716 — Conforming and savings clause (source § 17)

Source §§ 1, 18, and 19 are retained as short-title, severability, and effective-date notes at § 9701. The source's § 18 heading is treated according to its operative severability text.

## Great Change Act of 2026 — Pub. L. 41–271

### Title II — National security eligibility
Classified to **Title 50, chapter 99, National Security Eligibility and Access**:

- 50 U.S.C. §§ 5001–5007 correspond to source §§ 201–207.

### Title III — Commerce, trade, intellectual property, and labor functions
Classified to **Title 15, chapter 124, Transferred Commerce, Trade, Intellectual Property, and Labor Functions**:

- 15 U.S.C. §§ 10001–10011 correspond to source §§ 301–311.

### Title IV — Conflicts of interest
Consolidated into **18 U.S.C. § 205**. Existing project subsections (a) and (j) remain in force; source §§ 403–406 are classified as new subsections **(k)–(n)**, with amendment/effective-date history retained in the section notes.

### Title V — Commissioned service staffing
Classified to **Title 5, part III, subpart A, chapter 25, Commissioned Service Staffing and Continuity**:

- 5 U.S.C. §§ 2501–2504 correspond to source §§ 501–504.

### Title VI — Whistleblower and oversight protections
Classified in **Title 5, chapter 23, Merit System Principles**:

- 5 U.S.C. §§ 2308–2314 correspond to source §§ 601–607.

### Repeals and transition
Title I's express repeals of Pub. L. 28–206 (Washington Diplomacy Complex Boundary Act), Pub. L. 27–196 (National Commission on Judicial Activity, Efficiency and Accountability Act), and Pub. L. 17–130 (Oath and Offices Protection) remain historical rather than operative law. Great Change transition, savings, severability, and effective-date provisions remain as statutory history/notes where appropriate.

## Implementation

`tools/apply_current_law_sections.py` applies these classifications to the working USLM title XML during the Pages build. The ordered `current-law-sections.json.gz.b64.part*` files contain a compressed structured manifest of the section text used by the overlay. The pass is deterministic and idempotent, rejects collisions with non-managed Code sections, and validates duplicate IDs/identifiers before the site build continues. Maintenance normalization may consolidate the manifest into a single canonical part without changing its decoded contents.
