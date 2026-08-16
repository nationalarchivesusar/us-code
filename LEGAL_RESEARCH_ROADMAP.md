# U.S. Code Legal Research Roadmap

This file is the recovery and continuation plan for the legal-research features on the USAR U.S. Code website.

## Core architecture

- **Repository:** `nationalarchivesusar/us-code`
- **Production:** `https://nationalarchivesusar.github.io/us-code/`
- **Courts site:** `https://nationalarchivesusar.github.io/courts/`
- **Constitution source:** NARA HackMD note `CDCV7p2_Sca6O0FrEJyaIQ`
- **Public Law source/codification ledger:** repository audit/legal-data inputs compiled into `data/public-laws.json`
- **Codification comparison baseline:** commit `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`
- **Criminal Law API:** `data/api/v1/criminal-law/` — preserve its public contract unless a change is explicitly requested.

The intended research model is:

1. **U.S. Code** — what the law currently says.
2. **Public Laws** — how the Code got there.
3. **Constitution** — the controlling constitutional text published from the NARA HackMD source.
4. **Courts** — what the judiciary has said about the law.

These surfaces should be tightly linked without being visually identical.

## Completed foundation

### Shared research tools

Implemented in the legal-research feature work:

- U.S. Code citation jumper, including subsection pinpoints.
- Public Law citation jumper.
- Section toolbar with copy citation, copy link, source laws, XML source, and print.
- Code-to-Public-Law source history backed by `data/public-laws.json`.
- Public-Law-to-Code affected-section links.
- Deep links into individual Code sections and subsection pinpoints.

Primary files:

- `assets/js/research-tools.js`
- `assets/css/research-tools.css`
- `tools/build_public_laws_index.py`

### Constitution

Implemented:

- Dedicated Constitution page.
- Search and sticky table of contents.
- Article, Amendment, and Section permalinks.
- Light/dark theme support and print styling.
- Build-time synchronization from the NARA HackMD source.
- Validation that rejects a truncated or malformed source.
- Preservation of HackMD legal-document hierarchy so Articles, Amendments, and Sections render correctly.
- Tolerant structural recognition of source wording such as `Section 1.`, `Section. 1.`, and the existing `Secton. 1.` typo without rewriting the constitutional text.

Important legal/source rule: **editing the HackMD changes the website publication source, but does not itself establish that a constitutional amendment was legally adopted.** Legal validity still depends on the RP constitutional amendment/ratification process.

Primary files:

- `constitution.html`
- `assets/js/constitution.js`
- `assets/css/constitution.css`
- `tools/build_constitution.py`
- `tests/test_constitution_build.py`

## Current work: verified section redlines

### Goal

Give a researcher an accurate answer to: **“What changed in this U.S. Code section compared with the codification baseline?”**

### Reliability rule

The repository currently preserves two different kinds of evidence:

- `data/public-laws.json` identifies Public Laws/actions associated with a Code section.
- Git commit `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46` preserves an actual earlier Code text baseline.

Therefore the first version of the feature must make only the claim the data supports:

> **Verified repository baseline → current published text.**

It must **not** fabricate intermediate versions after each Public Law. A Public Law can be listed as associated history without claiming that a generated text snapshot represents the Code immediately after that enactment.

### Data model

Builder: `tools/build_section_history.py`

Output:

- `data/section-history/manifest.json`
- `data/section-history/<title>/<section>.json`

The manifest is a small lazy-loading index. Detailed comparison files contain:

- title and section;
- citation;
- comparison status: `amended`, `added`, or `removed`;
- baseline commit and baseline text/hash;
- current text/hash;
- build-time token diff operations (`equal`, `insert`, `delete`).

Only sections actually referenced by the Public Law codification index are comparison candidates. Only verified changes get detailed output files.

### Statutory-text scope

Redlines compare the substantive section text and heading. The comparison intentionally excludes:

- source credits;
- statutory notes;
- historical/amendment notes;
- TOC metadata.

Those remain available through the normal Code presentation and Public Law history. This prevents a note-only metadata change from appearing as if Congress changed the operative statutory text.

### UI design

`assets/js/research-tools.js` should:

1. lazily load `data/section-history/manifest.json`;
2. show **Compare versions** only when the current section has a verified comparison record;
3. lazily fetch that section's detail JSON when opened;
4. provide two views:
   - **Redline** — deletions and insertions inline;
   - **Side by side** — baseline and current text in separate columns;
5. identify the view as a **Verified baseline comparison**;
6. state clearly that associated Public Laws do not yet represent reconstructed intermediate text versions;
7. retain links to the existing Source laws & section history panel.

Mobile: side-by-side columns must stack. Print: comparison should remain legible and research controls should not clutter output.

### Build/deployment integration

The Pages workflow must:

1. fetch baseline commit `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`;
2. fetch the baseline Title 42 LFS object because `usc42.xml` is LFS-managed;
3. build current-law overlays and `data/public-laws.json` first;
4. run `python tools/build_section_history.py` while the current XML corpus is still present;
5. validate `data/section-history/manifest.json`;
6. publish the generated `data/section-history/` directory through the normal `data` copy into `_site`.

### Tests

`tests/test_section_history.py` covers:

- title filename normalization;
- Public Law target deduplication;
- exclusion of source credits and notes from substantive comparisons;
- note-only changes producing no redline;
- amended text producing reversible diff operations;
- newly added sections being marked `added`.

CI should also syntax-check `tools/build_section_history.py` and `assets/js/research-tools.js` and verify the generated manifest exists.

## Next phase: true per-enactment historical versions

This is intentionally **not** part of the baseline-redline MVP unless the necessary source evidence is available.

Desired eventual capability:

- Original/baseline text.
- Snapshot after Public Law A.
- Snapshot after Public Law B.
- Current text.
- A version selector and comparison between any two known states.

### Correct implementation path

1. Establish an ordered enactment/action timeline for each affected section.
2. Preserve or recover exact enacted amendment instructions/text for each action.
3. Replay actions deterministically against the correct predecessor version.
4. Store a hash for each reconstructed snapshot.
5. Add validation proving each final reconstructed section equals the current published section.
6. Mark any action that cannot be deterministically replayed as unavailable rather than guessing.

Never label an inferred or approximate reconstruction as authoritative historical text.

## Later research phases

### 1. Cited by / references graph

Build a lazy reference graph from USLM `<ref>` links and identifiers:

- **References** — statutes this section cites.
- **Referenced by** — statutes that cite this section.
- Direct navigation between related provisions.
- Eventually a visual relationship graph where useful.

Prefer a build-time JSON index rather than scanning all XML in the browser.

### 2. Changes to the Code page

Create a dedicated chronological research page showing codification changes, for example:

- Public Law number and title.
- Affected Code sections.
- Added / amended / repealed classification where verified.
- Direct links to Public Law, current section, and redline.

Do not invent enactment dates when the source ledger does not reliably preserve them; use only supported chronology/metadata.

### 3. Constitution research controls

Add Code-quality research controls to constitutional provisions:

- Copy constitutional citation.
- Copy permalink.
- Active TOC highlighting while scrolling.
- Citation forms such as `U.S. Const. art. II, § I` and `U.S. Const. amend. XXIV, § 2`.
- Refined print view.

Preserve the exact source text, including source typos, unless the authoritative Constitution source itself is amended/corrected.

### 4. Automatic Constitution refresh

The Constitution is fetched from HackMD on every Pages build. Add a scheduled workflow trigger if automatic propagation of HackMD publication edits is desired even when no repository commit occurs.

A scheduled rebuild changes publication synchronization only; it does not decide whether a constitutional change was legally adopted.

### 5. Courts integration

Cross-link the Code and Courts sites where reliable case metadata exists:

- Code section → cases interpreting/citing it.
- Case → statutes/constitutional provisions cited.
- Prefer explicit case metadata/citations over fuzzy text matching.

## Non-negotiable safeguards

1. **Do not break or silently reshape the Criminal Law API.**
2. **Do not manufacture legal history.** If an intermediate version is not supported by source evidence, say so.
3. **Preserve source wording.** Formatting/parsing may recognize inconsistent labels, but must not silently rewrite legal text.
4. **Keep history lazy-loaded.** Do not force every section visit to download the entire historical corpus.
5. **Fail closed on build integrity.** Missing baseline material, malformed XML, or failed diff reconstruction should be surfaced by validation rather than silently published as authoritative.
6. **Separate substantive text from metadata.** A source-credit or note edit is not automatically a statutory-body amendment.
7. **Keep permanent deep links stable.** Existing `/cite/<title>/<section>/` routes and subsection pinpoint behavior should remain intact.

## Recovery / continuation checklist

If work resumes in another chat or coding session:

1. Read this file first.
2. Inspect the latest `main` and any open branch/PR named around `section-redlines` or `legal-research`.
3. Confirm the fixed baseline commit remains `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46` before generating comparisons.
4. Run or inspect CI for:
   - current-law overlays;
   - Public Law index generation;
   - `tools/build_section_history.py`;
   - all Python tests;
   - JS syntax/static-site tests;
   - existing Criminal Law API hardening checks.
5. Spot-check at least:
   - one **amended** existing section;
   - one **newly added** section;
   - one Public-Law-linked section whose substantive text is unchanged;
   - a Title 42 target to verify baseline LFS handling.
6. Verify mobile and dark-mode presentation of the comparison panel.
7. Merge only after a clean Pages build/validation run.

## Current branch at creation of this roadmap

- Feature branch: `feature/section-redlines`

If that branch has already been merged or deleted, continue from the latest `main`; do not recreate obsolete work blindly.
