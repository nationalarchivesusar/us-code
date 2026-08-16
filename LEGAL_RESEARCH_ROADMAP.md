# U.S. Code Legal Research Roadmap

This file is the recovery and continuation plan for the legal-research features on the USAR U.S. Code website. Read it first if work resumes in another chat or coding session.

## Core architecture

- **Repository:** `nationalarchivesusar/us-code`
- **Production:** `https://nationalarchivesusar.github.io/us-code/`
- **Courts site:** `https://nationalarchivesusar.github.io/courts/`
- **Constitution source:** NARA HackMD note `CDCV7p2_Sca6O0FrEJyaIQ`
- **Public Law/codification index:** repository audit/legal-data inputs compiled into `data/public-laws.json`
- **Codification comparison baseline:** `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`
- **Criminal Law API:** `data/api/v1/criminal-law/` — preserve its public contract unless a change is explicitly requested.

The intended research model is:

1. **U.S. Code** — what the law currently says.
2. **Public Laws** — how the Code got there.
3. **Constitution** — the controlling constitutional text published from the NARA HackMD source.
4. **Courts** — what the judiciary has said about the law.

These surfaces should be tightly linked without being visually identical.

---

## Completed foundation

### Shared Code research tools

Implemented:

- U.S. Code citation jumper, including subsection pinpoints.
- Public Law citation jumper.
- Section toolbar with copy citation, copy link, source laws, XML source, and print.
- Code → Public Law source history backed by `data/public-laws.json`.
- Public Law → Code affected-section links.
- Stable `/cite/<title>/<section>/` routes and subsection pinpoint behavior.

Primary files:

- `assets/js/research-tools.js`
- `assets/css/research-tools.css`
- `tools/build_public_laws_index.py`
- `tools/filter_public_laws_for_publication.py`

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

---

## Current implementation: verified section redlines

### Goal

Give a researcher a defensible answer to:

> **What changed in this U.S. Code section compared with the codification repository baseline?**

### Reliability boundary

The repository preserves two different kinds of evidence:

- `data/public-laws.json` identifies Public Laws/actions associated with a Code section.
- Baseline commit `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46` preserves actual earlier Code text.

Therefore the current feature makes only the claim the evidence supports:

> **Verified repository baseline → current published text.**

It must **not** fabricate an intermediate text version after each Public Law. Public Laws may be identified as associated section history without claiming that the site has reconstructed the exact Code text immediately after each enactment.

### Branch / pull request

- Feature branch: `feature/section-redlines`
- Pull request: **#13 — Add verified U.S. Code section redlines**

If PR #13 has already been merged or closed when this file is read, continue from the latest `main`; do not recreate obsolete branch work blindly.

### Build-time comparison engine

Primary builder: `tools/build_section_history.py`

The builder:

1. reads the finalized public-law dataset;
2. identifies section targets actually referenced by that codification index;
3. loads the current U.S. Code XML section;
4. loads the same title from the fixed baseline commit;
5. compares substantive section text;
6. emits a record only where a verified substantive difference exists;
7. verifies that its diff operations reconstruct both the baseline and current text exactly.

Generated output:

- `data/section-history/manifest.json`
- `data/section-history/<title>/<section>.json`

The manifest is intentionally small so the browser can determine whether a current section has a comparison without downloading the entire history corpus.

Per-section records contain:

- schema version;
- title, section, and citation;
- comparison status: `amended`, `added`, or `removed`;
- baseline commit, text, heading, presence flag, and SHA-256;
- current text, heading, presence flag, and SHA-256;
- build-time diff operations: `equal`, `insert`, and `delete`.

### Statutory-text scope

Redlines compare the section heading and substantive statutory body. They intentionally exclude:

- source credits;
- statutory notes;
- historical/amendment notes;
- table-of-contents metadata.

Those remain available through the normal Code presentation and Public Law history. This prevents a source-credit or note-only change from being displayed as though the operative statutory text changed.

### Publication pipeline

The normal Pages pipeline already:

1. checks out current XML/LFS content;
2. fetches baseline commit `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`;
3. applies current-law overlays;
4. builds the initial Public Law index;
5. runs `tools/filter_public_laws_for_publication.py` to finalize/validate public-facing targets.

The redline build is hooked into the **end of `tools/filter_public_laws_for_publication.py`**, after `data/public-laws.json` has been finalized. That step invokes `tools/build_section_history.py` against the fixed baseline while the current XML corpus is still present.

This ordering matters: comparison candidates must come from the cleaned, public-facing section targets rather than raw internal codification identifiers.

Title 42 is Git LFS-managed. `tools/build_section_history.py` detects an LFS pointer in baseline material and smudges/materializes the historical object. CI must demonstrate that Title 42 history can be handled without silently substituting current text.

The normal static-site step copies the entire `data/` tree into `_site`, so generated `data/section-history/` files are published without adding a second copy mechanism.

### Browser UI

The comparison UI is deliberately isolated from the existing research toolbar implementation.

Primary files:

- `assets/js/section-comparison.js`
- `assets/css/section-comparison.css`
- `assets/js/site-bootstrap.js`

Behavior:

1. `site-bootstrap.js` loads both `research-tools.js` and `section-comparison.js` on Code viewer pages.
2. `section-comparison.js` waits for the ordinary section toolbar.
3. It lazily loads `data/section-history/manifest.json`.
4. **Compare versions** appears only where the current section has a verified comparison record.
5. The detailed per-section JSON is fetched only after the user opens the comparison.
6. The comparison panel provides:
   - **Redline** — inline insertions and deletions;
   - **Side by side** — baseline and current text in separate columns.
7. The panel is explicitly labeled **Verified baseline comparison**.
8. The panel states that Public Law history does **not yet** represent reconstructed per-enactment text snapshots.
9. A control opens the existing **Source laws & section history** panel so textual change and enactment history remain connected.
10. Baseline/current text hashes are surfaced as a verification aid.

Security/presentation detail: statutory comparison text is inserted as DOM text nodes and `<ins>/<del>` elements rather than interpolated into unsafe HTML.

Responsive behavior:

- side-by-side comparison stacks on narrow screens;
- normal theme variables support light/dark mode;
- print output keeps comparison text legible while suppressing unnecessary controls.

### Tests

`tests/test_section_history.py` covers:

- U.S. Code title filename normalization;
- Public Law target deduplication;
- exclusion of source credits and notes from substantive comparison text;
- note-only changes producing no redline;
- amended text producing reversible diff operations;
- newly added sections being marked `added`.

`tests/test_section_comparison.mjs` covers:

- comparison module/CSS wiring into `site-bootstrap.js`;
- actual Node syntax validation of `section-comparison.js`;
- presence of the verified-baseline, Redline, Side-by-side, and no-fabricated-intermediate-version UI contract.

Before merge, the full existing Pages CI must also pass, including:

- current-law overlay tests;
- Public Law dataset validation;
- all Python tests;
- all Node/static-site tests;
- Title 42 build checks;
- Criminal Law API hardening/final-surface checks;
- static Pages artifact assembly.

### Required spot checks before/after publication

Verify at least:

- one **amended** existing section;
- one **newly added** section;
- one Public-Law-linked section whose substantive text is unchanged and therefore has no Compare versions button;
- at least one Title 42 target to verify historical LFS handling;
- mobile layout;
- dark-mode layout;
- production `data/section-history/manifest.json` after deployment.

---

## Next phase: true per-enactment historical versions

This is intentionally **not** part of the verified-baseline MVP unless sufficient evidence is available.

Desired eventual capability:

- original/baseline text;
- snapshot after Public Law A;
- snapshot after Public Law B;
- current text;
- comparison between any two verified states.

### Correct implementation path

1. Establish an ordered enactment/action timeline for each affected section.
2. Preserve or recover exact enacted amendment instructions/text for each action.
3. Replay actions deterministically against the correct predecessor version.
4. Store a hash for every reconstructed snapshot.
5. Validate that replaying all applicable actions produces text identical to the current published section.
6. Mark actions that cannot be deterministically replayed as unavailable rather than guessing.
7. Distinguish an official/preserved historical text from a site reconstruction in UI metadata.

**Never label an inferred or approximate reconstruction as authoritative historical text.**

---

## Later research phases

### 1. Cited by / References graph

Build a lazy build-time reference graph from USLM `<ref>` links and identifiers:

- **References** — statutes this section cites.
- **Referenced by** — statutes that cite this section.
- Direct navigation between related provisions.
- Optional visual relationship graph where it adds value.

Do not scan the full XML corpus in every user's browser.

### 2. Changes to the Code page

Create a dedicated chronological/legal-change research page showing, where supported:

- Public Law number and title;
- affected Code sections;
- added / amended / repealed classification;
- direct links to Public Law, current section, and verified redline.

Do not invent enactment dates when source data does not reliably preserve them.

### 3. Constitution research controls

Add Code-quality controls to constitutional provisions:

- Copy constitutional citation.
- Copy permalink.
- Active TOC highlighting while scrolling.
- Citation forms such as `U.S. Const. art. II, § I` and `U.S. Const. amend. XXIV, § 2`.
- Refined print view.

Preserve exact source text, including source typos, unless the authoritative Constitution source itself is changed.

### 4. Automatic Constitution refresh

The Constitution is fetched from HackMD on every Pages build. A scheduled workflow trigger can make HackMD publication edits propagate even when no repository commit occurs.

A scheduled rebuild changes publication synchronization only; it does not decide whether a constitutional amendment was legally adopted.

### 5. Courts integration

Cross-link Code and Courts data only where reliable case metadata exists:

- Code section → cases interpreting/citing it.
- Case → statutes and constitutional provisions cited.
- Prefer explicit case metadata/citations over fuzzy text matching.

---

## Non-negotiable safeguards

1. **Do not break or silently reshape the Criminal Law API.**
2. **Do not manufacture legal history.** If an intermediate version is unsupported, say so.
3. **Preserve source wording.** Parsing may recognize inconsistent labels but must not silently rewrite legal text.
4. **Keep history lazy-loaded.** Ordinary section browsing must not download the entire historical corpus.
5. **Fail closed on comparison integrity.** A diff that cannot reproduce baseline/current text exactly must not be published as verified.
6. **Separate substantive text from metadata.** A note/source-credit change is not automatically a statutory-body amendment.
7. **Keep permanent deep links stable.** Existing `/cite/<title>/<section>/` and subsection pinpoint behavior must remain intact.
8. **Do not use Public Law association alone as proof of an exact intermediate statutory text.**

---

## Recovery / continuation checklist

If work resumes elsewhere:

1. Read this file first.
2. Inspect latest `main` and PR #13 / `feature/section-redlines` if still present.
3. Confirm the fixed comparison baseline remains `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`.
4. Inspect `tools/build_section_history.py`, `assets/js/section-comparison.js`, and `tools/filter_public_laws_for_publication.py` before changing architecture.
5. Run/inspect full Pages CI, not only isolated unit tests.
6. Record actual generated history counts and any `unavailable_titles` from CI.
7. Spot-check amended, added, unchanged, and Title 42 targets.
8. Verify mobile/dark-mode comparison presentation.
9. Merge only after a clean full build.
10. After merge, verify the production Pages deployment and production history manifest.

## Status note

At the time this revision was written, the implementation was under review in **PR #13** on `feature/section-redlines`; isolated Python and Node comparison tests were passing, while the full Pages integration run was still being validated.
