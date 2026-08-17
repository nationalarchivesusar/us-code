# U.S. Code Legal Research Roadmap

This is the recovery/continuation file for the USAR U.S. Code legal-research project. Read it first if work resumes in another chat, coding session, or AI agent.

## Project map

- **Repository:** `nationalarchivesusar/us-code`
- **Production:** `https://nationalarchivesusar.github.io/us-code/`
- **Courts repository:** `nationalarchivesusar/courts`
- **Courts production:** `https://nationalarchivesusar.github.io/courts/`
- **Constitution publication source:** NARA HackMD note `CDCV7p2_Sca6O0FrEJyaIQ`
- **Fixed codification comparison baseline:** `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`
- **Existing Criminal Law API:** `data/api/v1/criminal-law/` — its public contract must remain unchanged unless explicitly requested.

The intended research ecosystem is:

1. **U.S. Code** — what the law currently says.
2. **Public Laws** — how the statutory law got there.
3. **Code Changes / History** — verified textual state changes and recorded codification actions.
4. **Constitution** — constitutional text published from the NARA source copy, with provenance.
5. **United States Courts** — what the judiciary has said about statutes/constitutional provisions.
6. **Public APIs** — machine-readable access without forcing consumers to scrape the research UI.

These sites/surfaces should be deeply linked while remaining visually and conceptually distinct.

---

# Production foundation already merged

## PR #13 — verified baseline redlines

PR **#13 — Add verified U.S. Code section redlines** was merged into `main` at:

`3e3d869d66cef16b8b411268aa8cd7098e225192`

That release established the first defensible textual-history layer:

- `tools/build_section_history.py`
- `data/section-history/manifest.json`
- `data/section-history/<title>/<section>.json`
- `assets/js/section-comparison.js`
- `assets/css/section-comparison.css`

The fixed comparison is:

> **repository baseline → current published Code**

The build compares section heading + operative statutory body, excluding source credits and historical/statutory notes so metadata-only changes do not masquerade as statutory amendments.

The clean PR artifact examined **254** unique Public-Law-linked targets and produced:

- **97 verified substantive changes**
  - 84 added
  - 3 amended
  - 10 removed from the current source
- **157 substantively unchanged tracked targets**
- **0 unavailable titles** in that build

Representative amended sections included 5 U.S.C. § 552, 6 U.S.C. § 101, and 18 U.S.C. § 205. Newly created provisions such as 40 U.S.C. § 9701 correctly appeared as added.

The key reliability rule remains permanent:

> A Public Law being associated with a section does **not** prove the exact statutory text immediately after that enactment.

Never manufacture an intermediate version.

---

# Phase II implementation

## Working branch

`feature/research-suite-phase-2`

This branch is the comprehensive legal-research expansion requested after PR #13. At the time this roadmap revision was written, it had **not yet been merged**. Full Pages CI and production deployment must be completed before changing this status.

## 1. Homepage/search consolidation

Problem addressed: the homepage had a second pink **“Jump to a legal citation”** block below the real search form, creating unnecessary whitespace and duplicating the same research function.

New files:

- `assets/js/homepage-search.js`
- `assets/css/homepage-search.css`

Behavior:

- the legacy `#quick-citation-form` is removed/hidden;
- the main Citation search remains the one search surface;
- its section field becomes **Section or citation**;
- it accepts ordinary title + section input as before;
- it also accepts full citations such as `18 U.S.C. § 1752(a)(1)`;
- it accepts Public Law forms such as `Pub. L. 41-271`;
- subsection pinpoints continue to route through `?p=`;
- keyword mode remains the existing keyword search.

The goal is a compact legal-research homepage, not a dashboard full of replacement cards.

## 2. Exact repository-state version history

Primary builder:

- `tools/build_version_history.py`

Generated output:

- `data/version-history/manifest.json`
- `data/version-history/<title>/<section>.json`

Configured verified repository states:

1. `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46` — **Codification repository baseline**
2. `21e483ef2f71762f954f20c48a9a207898848645` — **Public-law corpus reconciled**
3. `6ece679f3e504db46d27fbd06a48980850a056f1` — **2026 enactments integrated**
4. current published working tree — **Current published Code**

Important semantics:

- these are **repository-state versions**, not automatically one version per enactment;
- exact statutory text is extracted from the actual XML at each retrievable state;
- consecutive identical statutory states are collapsed and recorded through `also_represents`;
- every unique text carries SHA-256 verification;
- token redlines are precomputed for every pair of unique versions;
- Public Law numbers are attached to a repository state only when the commit message explicitly names that law **and** the law is associated with the section;
- associated Public Laws remain section-history evidence, not proof of exact per-enactment text.

Shallow CI handling:

- `ensure_commit()` fetches a known snapshot SHA on demand if it is absent from the checkout;
- historical Git LFS XML is smudged/materialized;
- unavailable snapshots/titles are recorded explicitly rather than silently replaced with current text;
- the builder fails if no historical snapshot can be verified at all.

This is a major improvement over only baseline/current because a researcher can compare any preserved unique repository states without pretending the repository preserved a perfect legislative chronology.

## 3. Statutory References / Referenced By graph

Primary builder:

- `tools/build_reference_graph.py`

Generated output:

- `data/references/manifest.json`
- `data/references/<title>/<section>.json`

Reliability rule:

> Only explicit USLM `<ref>` `href`/`identifier` links count as statutory references.

There is **no fuzzy text matching** and no browser-side crawl of the Code.

The graph stores:

- outgoing **References**;
- incoming **Referenced by**;
- canonical citation;
- heading;
- compact manifest counts/path for lazy loading.

The full Pages build must prove that the actual current XML corpus yields nonzero verified edges before merge.

## 4. Richer section research interface

Primary files:

- `assets/js/section-research.js`
- `assets/css/section-research.css`
- `assets/js/court-bridge.js`
- `assets/js/site-bootstrap.js`

A current section gains a restrained research summary rather than a heavy dashboard. Depending on available verified data it can show:

- **Current law**
- source-law count
- verified version count
- outgoing references
- incoming references
- **Search case law ↗**

### Version History panel

Lazy-loaded per section and supports:

- choose any earlier/later verified repository state;
- **Redline** view;
- **Side by side** view;
- repository-state timeline;
- commit/date metadata;
- explicit Public Law commit associations where support exists;
- clear disclaimer that repository snapshots are not fabricated per-enactment versions.

### Statutory References panel

Lazy-loaded per section and shows:

- **References**
- **Referenced by**

Each existing target links directly to its `/cite/<title>/<section>/` route.

### Courts bridge

The Courts site already has a Case Law Search page at permanent route `/caselaw/`. Its own `assets/case-search.js` reads the `q` URL parameter and automatically executes a Supreme Court-only CourtListener search.

`court-bridge.js` therefore rewrites the section's Courts link to:

`https://nationalarchivesusar.github.io/courts/caselaw/?q="<citation>"`

Example conceptually:

`/courts/caselaw/?q="18 U.S.C. § 1752"`

This is a genuine cross-site research handoff. The Code site does **not** display an invented case count. If a future Courts dataset exposes structured statute-citation metadata, exact Code-section → decision counts can be built later.

## 5. Changes to the Code

New page/files:

- `changes.html`
- `assets/js/code-changes.js`
- `assets/css/code-changes.css`

Purpose: connect Public Laws to affected Code sections without confusing codification records with independently verified textual change.

Filters:

- search term;
- U.S.C. title;
- active/repealed Public Law status;
- verified added/amended/removed;
- recorded action.

Evidence labels are deliberately distinct:

- **Verified amended / added / removed** — the fixed baseline → current textual classification from `data/section-history/manifest.json`.
- **Recorded action** — the Public Law codification index says the law/action affected that section, but the site is not claiming that action by itself equals an independently reconstructed text snapshot.

The page explicitly warns that a baseline/current verified classification is not necessarily the isolated effect of the displayed Public Law.

Do not invent enactment dates if the source dataset does not preserve trustworthy dates.

## 6. General U.S. Code API v1

Primary builder:

- `tools/build_code_api.py`

Documentation:

- `api.html`
- `assets/css/api.css`

Namespace:

`data/api/v1/code/`

This is intentionally **separate** from:

`data/api/v1/criminal-law/`

The existing Criminal Law API must not be renamed, reshaped, or replaced.

General API layout:

- `data/api/v1/code/index.json`
- `data/api/v1/code/titles/<title>/manifest.json`
- `data/api/v1/code/titles/<title>/chunk-NNN.json`

A title manifest includes `section_to_chunk`, allowing a client to locate one section without downloading an entire large title.

Current v1 section object fields:

- `section`
- `citation`
- `identifier`
- `heading`
- `body`
- `web_url`

The schema intentionally avoids duplicating a separate `text` field because clients can concatenate `heading` + `body`; this keeps the static publication smaller.

Compatibility rule:

- additive fields may be introduced inside v1;
- incompatible structural changes should use a new API version.

## 7. Constitution provenance and research controls

Updated builder:

- `tools/build_constitution.py`

New generated metadata:

- `data/constitution-meta.json`

It records:

- NARA HackMD source URL/note ID;
- UTC fetch timestamp;
- SHA-256 of exactly the text being published;
- character count;
- publication-role description;
- explicit legal-validity caveat.

The legal/source distinction must always remain explicit:

> HackMD is the website publication source. Editing it changes what the site imports on a build; editing it does **not by itself** prove that a constitutional amendment or revision was legally adopted under the Constitution.

New UI:

- `assets/js/constitution-research.js`
- `assets/css/constitution-research.css`

Features:

- Copy constitutional citation;
- Copy permalink;
- article citations such as `U.S. Const. art. II`;
- section citations such as `U.S. Const. art. II, § I`;
- amendment citations such as `U.S. Const. amend. XXIV, § 2`;
- active TOC highlighting while scrolling;
- collapsible **Publication provenance** block with source/hash/fetch information.

The underlying constitutional wording is never silently corrected by this presentation layer.

## 8. Automatic Constitution publication refresh

New workflow:

- `.github/workflows/constitution-refresh.yml`

Schedule:

- hourly at minute 17 UTC (`17 * * * *`)
- manual `workflow_dispatch` also available.

The scheduled task dispatches the normal `jekyll-gh-pages.yml` workflow on `main`. The normal Pages build then fetches/validates the HackMD Constitution and republishes it.

This means a valid HackMD publication edit can propagate without an unrelated repository commit, subject to GitHub Actions scheduling delay.

If Actions permissions prevent the dispatch after merge, move the schedule trigger directly into `jekyll-gh-pages.yml`; do not replace the validation/build path with a weaker updater.

## 9. Static publication changes

The existing Pages workflow copies selected root HTML files rather than blindly publishing every root page. To make the new research pages deploy without duplicating the whole workflow, `tools/build_social_routes.py` now also publishes:

- `changes.html`
- `api.html`

into `_site` before validating social metadata and generating citation routes.

Both pages must have the same required canonical/OpenGraph/Twitter metadata contract as existing public pages.

## 10. Build pipeline integration

`tools/filter_public_laws_for_publication.py` remains the post-codification publication gate. After it finalizes/validates `data/public-laws.json`, Phase II now invokes:

1. existing `build_section_history()`;
2. `build_version_history()`;
3. `build_reference_graph()`;
4. `build_code_api()`.

This ordering is intentional. Research data should be generated from the already-cleaned public-facing Public Law targets and current finalized Code XML.

The builder fails publication if:

- no verified section-history changes exist;
- no exact version-history sections exist;
- the explicit reference graph yields no verified edges;
- the general Code API yields no sections.

Existing Criminal Law API generation/hardening remains in its established workflow steps.

---

# Tests and validation

Existing important tests remain:

- `tests/test_section_history.py`
- `tests/test_section_comparison.mjs`
- all current-law/codification tests;
- Public Law dataset validation;
- Title 42/LFS checks;
- Criminal Law API hardening/final-surface tests;
- static Pages/social-route tests.

New Phase II integration test:

- `tests/test_research_suite.mjs`

It checks:

- Node syntax for all new JS modules;
- single-surface homepage citation behavior;
- bootstrap wiring;
- version-history/references UI contract;
- Courts citation-search bridge;
- Changes-page evidence distinctions;
- separate general Code API namespace;
- Constitution provenance/legal-validity caveat;
- hourly Constitution refresh workflow.

The **real full Pages build is the integration test** for the corpus builders. Unit tests alone are not sufficient because historical Git/LFS materialization and actual USLM reference structure must work against the repository corpus.

---

# Mandatory pre-merge verification for Phase II

Do not merge `feature/research-suite-phase-2` until all of the following are true:

1. Full GitHub Pages build/validation succeeds.
2. `data/version-history/manifest.json` has nonzero verified versioned sections and at least one historical snapshot.
3. `data/references/manifest.json` has nonzero verified explicit statutory edges.
4. `data/api/v1/code/index.json` has a plausible title/section count.
5. `data/constitution-meta.json` exists and validates against the published Constitution text.
6. `changes.html` and `api.html` are present in the Pages artifact.
7. Representative exact version records look legally sensible:
   - 18 U.S.C. § 205
   - 5 U.S.C. § 552
   - a newly added section such as 40 U.S.C. § 9701
8. At least one reference record has both sensible outgoing/incoming statutory links where expected.
9. Homepage artifact no longer presents the redundant pink quick-citation block after JS enhancement.
10. Existing `/cite/<title>/<section>/` and subsection pinpoint routes still work.
11. Criminal Law API validation remains green and its namespace/contracts are unchanged.
12. Artifact size remains acceptable for GitHub Pages.

After merge, independently verify the `main` Pages workflow and the public production URLs before calling the work deployed.

---

# Future work after Phase II

## A. True enactment-by-enactment history

The repository-state history is truthful but does not necessarily represent every enacted intermediate state. The eventual gold-standard chronology requires:

1. ordered enactment/action timeline per section;
2. preserved exact amendment instructions or enacted replacement text;
3. deterministic replay against the correct predecessor version;
4. snapshot hash after every replayable action;
5. final replay must equal current published Code exactly;
6. unsupported actions must be labeled unavailable, never guessed;
7. UI must distinguish preserved text from site-reconstructed text.

## B. Structured Courts citation graph

The current bridge sends a Code citation into the Courts site's Supreme Court CourtListener search. Future richer integration should only be built if Courts has reliable explicit citation metadata:

- section → decisions citing/interpreting it;
- decision → statutes/constitutional provisions cited;
- exact counts and filtered decision lists.

Do not generate counts using naive text occurrence scans.

## C. Constitution amendment chronology

If authoritative ratification/amendment metadata becomes available, add an amendment-history layer separate from the publication-source provenance. The HackMD edit timestamp must never be mistaken for the amendment's legal ratification/effective date.

## D. API expansion

After the general API stabilizes, additive v1 extensions may expose:

- source-law history;
- verified version-history path/count;
- outgoing/incoming statutory references;
- provenance hashes.

Keep large research payloads as linked/lazy resources rather than duplicating them inside every API section object.

---

# Non-negotiable safeguards

1. **Do not break or silently reshape `data/api/v1/criminal-law/`.**
2. **Do not manufacture legal history.**
3. **Do not use a Public Law association alone as proof of exact intermediate text.**
4. **Preserve statutory and constitutional source wording.**
5. **Explicit references only** for the statutory reference graph unless a future inference layer is separately labeled.
6. **Keep large research data lazy-loaded.**
7. **Fail closed on history-integrity failures.**
8. **Keep `/cite/<title>/<section>/` and subsection pinpoints stable.**
9. **Do not invent enactment dates.**
10. **Do not invent Courts citation counts.**
11. **HackMD publication authority is not the same as constitutional legal-amendment authority.**
12. **Full Pages CI + production verification are required before calling a release finished.**

---

# Recovery checklist

If another session takes over:

1. Read this file fully.
2. Inspect latest `main` and `feature/research-suite-phase-2`.
3. Confirm PR #13 merge base `3e3d869d66cef16b8b411268aa8cd7098e225192` and fixed history baseline `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`.
4. Inspect:
   - `tools/filter_public_laws_for_publication.py`
   - `tools/build_section_history.py`
   - `tools/build_version_history.py`
   - `tools/build_reference_graph.py`
   - `tools/build_code_api.py`
   - `tools/build_constitution.py`
5. Inspect browser modules:
   - `assets/js/homepage-search.js`
   - `assets/js/research-tools.js`
   - `assets/js/section-comparison.js`
   - `assets/js/section-research.js`
   - `assets/js/court-bridge.js`
   - `assets/js/code-changes.js`
   - `assets/js/constitution-research.js`
   - `assets/js/site-bootstrap.js`
6. Inspect pages:
   - `changes.html`
   - `api.html`
   - `constitution.html`
7. Run/inspect all Python + Node tests and the full Pages workflow.
8. Pull the exact Pages artifact and inspect generated manifests/counts, not merely CI pass/fail.
9. Spot-check version history, references, Changes page, general API, Constitution metadata, and Criminal Law API.
10. Merge only after clean full CI.
11. Watch the post-merge `main` Pages run to completion.
12. Verify public production resources directly.
13. Update this status section with PR number, merge SHA, production run, and generated counts.

## Current status

**Phase II is implemented on `feature/research-suite-phase-2` and awaiting full integration CI/PR verification. It is not yet safe to describe as deployed.**
