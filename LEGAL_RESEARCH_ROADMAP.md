# U.S. Code Legal Research Roadmap

This file is the recovery/continuation record for the USAR U.S. Code legal-research project. Read it before resuming the work in another chat, coding agent, or development session.

## Project map

- **Repository:** `nationalarchivesusar/us-code`
- **Production:** `https://nationalarchivesusar.github.io/us-code/`
- **Courts repository:** `nationalarchivesusar/courts`
- **Courts production:** `https://nationalarchivesusar.github.io/courts/`
- **Constitution publication source:** NARA HackMD note `CDCV7p2_Sca6O0FrEJyaIQ`
- **Fixed codification comparison baseline:** `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`
- **Existing Criminal Law API:** `data/api/v1/criminal-law/` — do not break or silently reshape this contract.

The intended research ecosystem is:

1. **United States Code** — what the law currently says.
2. **Public Laws** — how statutory law got there.
3. **Code Changes / History** — verified text states and recorded codification actions.
4. **Constitution** — constitutional text published from the NARA source copy with provenance.
5. **United States Courts** — judicial interpretation/research.
6. **Public APIs** — machine-readable access without scraping the research UI.

Keep these surfaces deeply linked but conceptually distinct.

---

# Production foundation

## PR #13 — verified baseline redlines

PR #13 was merged into `main` at:

`3e3d869d66cef16b8b411268aa8cd7098e225192`

It established the first defensible statutory-history layer:

- `tools/build_section_history.py`
- `data/section-history/manifest.json`
- `data/section-history/<title>/<section>.json`
- `assets/js/section-comparison.js`
- `assets/css/section-comparison.css`

The comparison is strictly:

> **fixed repository baseline → current published Code**

It compares section heading + operative statutory body while excluding source credits and statutory/history notes so metadata-only changes are not represented as statutory amendments.

PR #13 corpus result:

- **254** Public-Law-linked section targets examined
- **97 verified substantive changes**
  - 84 added
  - 3 amended
  - 10 absent from current source
- **157 substantively unchanged**
- **0 unavailable titles**

Representative amended sections included 5 U.S.C. § 552, 6 U.S.C. § 101, and 18 U.S.C. § 205. New provisions such as 40 U.S.C. § 9701 correctly appeared as added.

Permanent rule:

> A Public Law being associated with a section does **not** prove the exact statutory text immediately after that enactment.

Never manufacture intermediate statutory text.

---

# Phase II — comprehensive legal research suite

## Branch / PR

- **Branch:** `feature/research-suite-phase-2`
- **Pull request:** PR #14 — `Build legal research suite phase II`

### Integration status

First full PR Pages run: **31983091723**.

That run successfully completed:

- source checkout and Git LFS materialization;
- fixed historical baseline fetch;
- Constitution fetch/validation;
- current-law overlays;
- Public Law integration;
- browser data build;
- all new Phase II corpus builders;
- tracked Criminal Law API regeneration/verification;
- the complete existing + new validation test suite.

Actual corpus results from that run:

- baseline/current section history: **97 changed / 254 tracked targets**;
- exact repository-state version history: **50 sections across 3 historical snapshots**;
- statutory reference graph: **2,163 connected sections / 1,941 verified directed edges**;
- general Code index: **54 titles / 59,010 sections**;
- existing Criminal Law API hardening and final-surface validation: **passed**.

The first run failed **only** at static-site assembly because the initial general API duplicated the full statutory body into JSON for all 59,010 sections. Static publication reached **1,059,220,115 bytes (~1010.2 MiB)**, above the GitHub Pages **900 MiB** project guard.

That was treated as an architecture defect, not a reason to weaken the guard. The general API was redesigned as a compact index that points to the already-published USLM XML instead of republishing a second full copy of the Code. A new full-head CI run must pass before merge.

**Current release status: not merged and not deployed until the compact-API head receives clean full Pages CI.**

---

## 1. Homepage/search consolidation

Files:

- `assets/js/homepage-search.js`
- `assets/css/homepage-search.css`

Problem fixed: the homepage had a separate pink **Jump to a legal citation** card under the main search form, duplicating citation search and creating large unnecessary whitespace.

Behavior:

- legacy `#quick-citation-form` is removed/hidden;
- the main Citation search is the single citation surface;
- section field becomes **Section or citation**;
- ordinary Title + Section input still works;
- full forms such as `18 U.S.C. § 1752(a)(1)` work;
- Public Law forms such as `Pub. L. 41-271` work;
- subsection pinpoints continue through `?p=`;
- Keyword mode remains unchanged.

Keep the homepage sparse. Do not replace the removed whitespace with dashboard clutter.

---

## 2. Exact repository-state statutory history

Builder:

- `tools/build_version_history.py`

Output:

- `data/version-history/manifest.json`
- `data/version-history/<title>/<section>.json`

Configured repository states:

1. `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46` — **Codification repository baseline**
2. `21e483ef2f71762f954f20c48a9a207898848645` — **Public-law corpus reconciled**
3. `6ece679f3e504db46d27fbd06a48980850a056f1` — **2026 enactments integrated**
4. current working tree — **Current published Code**

Semantics:

- these are repository-state versions, not automatically one version per enactment;
- exact statutory text comes from actual XML at each retrievable state;
- consecutive identical states collapse through `also_represents`;
- each unique text has SHA-256 verification;
- pairwise token redlines are precomputed;
- a Public Law number is attached to a repository state only when the commit message explicitly names it **and** that law is associated with the section;
- associated Public Laws remain section-history evidence, not proof of exact per-enactment text.

Shallow-CI handling:

- `ensure_commit()` fetches a known historical SHA when absent;
- historical Git LFS XML is materialized;
- unavailable snapshots/titles are recorded explicitly;
- no history is silently replaced with current text;
- build fails if no historical snapshot can be verified.

Real Phase II corpus result: **50 sections with verified multi-state history across 3 historical snapshots**.

---

## 3. Statutory References / Referenced By graph

Builder:

- `tools/build_reference_graph.py`

Output:

- `data/references/manifest.json`
- `data/references/<title>/<section>.json`

Reliability rule:

> Only explicit USLM `<ref>` `href`/`identifier` links count as statutory references.

No fuzzy text matching is used.

Graph records:

- outgoing **References**;
- incoming **Referenced by**;
- canonical citation;
- heading;
- compact lazy-load path/count metadata.

Real corpus result: **2,163 connected sections and 1,941 verified directed reference edges**.

---

## 4. Richer Code-section research interface

Files:

- `assets/js/section-research.js`
- `assets/css/section-research.css`
- `assets/js/court-bridge.js`
- `assets/js/site-bootstrap.js`

A current section gets a restrained research summary, depending on available verified data:

- **Current law**
- source-law count
- verified-version count
- outgoing references
- incoming references
- **Search case law ↗**

### Version History panel

Lazy-loaded and supports:

- choose any preserved earlier/later repository state;
- **Redline** view;
- **Side by side** view;
- repository-state timeline;
- commit/date metadata;
- explicit Public Law commit associations when supported;
- clear caveat that repository snapshots are not fabricated per-enactment versions.

### Statutory References panel

Lazy-loaded and shows:

- **References**
- **Referenced by**

Targets deep-link through `/cite/<title>/<section>/`.

### Courts bridge

The Courts site has a permanent Case Law Search page at `/caselaw/`. Its own search script reads a `q` query parameter and automatically runs a Supreme Court CourtListener search.

Code sections therefore hand off the exact citation to:

`https://nationalarchivesusar.github.io/courts/caselaw/?q="<citation>"`

Example:

`/courts/caselaw/?q="18 U.S.C. § 1752"`

Do not invent a judicial citation count. A structured Code-section → cases graph should only be built if Courts later exposes reliable citation metadata.

---

## 5. Changes to the Code

Files:

- `changes.html`
- `assets/js/code-changes.js`
- `assets/css/code-changes.css`

Purpose: connect Public Laws to affected sections without confusing codification records with independently verified text changes.

Filters:

- search term;
- U.S.C. title;
- active/repealed Public Law status;
- verified added/amended/removed;
- recorded action.

Evidence labels:

- **Verified amended / added / removed** — fixed baseline → current textual classification from `data/section-history/manifest.json`.
- **Recorded action** — Public Law codification index says a law/action affected that section, but the site does not claim that action itself equals an independently reconstructed text snapshot.

The page explicitly warns that a baseline/current classification is not necessarily the isolated effect of the displayed Public Law.

Do not invent enactment dates when trustworthy dates are absent from the source dataset.

---

## 6. General U.S. Code API v1 — compact index model

Builder:

- `tools/build_code_api.py`

Documentation:

- `api.html`
- `assets/css/api.css`

Namespace:

`data/api/v1/code/`

This is intentionally separate from the established:

`data/api/v1/criminal-law/`

The existing Criminal Law API must not be renamed, reshaped, or replaced.

Layout:

- `data/api/v1/code/index.json`
- `data/api/v1/code/titles/<title>/manifest.json`
- `data/api/v1/code/titles/<title>/chunk-NNN.json`

The API initially duplicated each section's complete operative body. That caused the first Phase II artifact to exceed the GitHub Pages size guard. Before first release, it was redesigned into a **compact statutory index**.

Current section metadata fields:

- `section`
- `citation`
- `identifier`
- `heading`
- `web_url`

Each title manifest provides:

- `source_xml`
- `source_format: "USLM XML"`
- `section_to_chunk`
- compact chunk metadata.

A client wanting full statutory text should:

1. locate section metadata through the compact API;
2. read the exact USLM `identifier`;
3. fetch the title manifest's already-published `source_xml`;
4. locate that section in the XML.

This avoids publishing the statutory corpus twice and keeps the USLM XML as the single complete-text source.

Real corpus index count remains **54 titles / 59,010 sections**; only duplicated body text was removed.

Compatibility rule:

- additive v1 fields are allowed;
- incompatible structural changes require a new API version.

---

## 7. Constitution provenance and research controls

Updated builder:

- `tools/build_constitution.py`

Generated metadata:

- `data/constitution-meta.json`

It records:

- HackMD source URL/note ID;
- UTC fetch timestamp;
- SHA-256 of exactly the text published;
- character count;
- publication-role description;
- legal-validity caveat.

Permanent distinction:

> HackMD is the website publication source. Editing it changes what the site imports on a build; editing it does **not by itself** prove that a constitutional amendment or revision was legally adopted under the Constitution.

UI files:

- `assets/js/constitution-research.js`
- `assets/css/constitution-research.css`

Features:

- Copy constitutional citation;
- Copy permalink;
- article citations such as `U.S. Const. art. II`;
- article section citations such as `U.S. Const. art. II, § I`;
- amendment citations such as `U.S. Const. amend. XXIV, § 2`;
- active TOC highlighting while scrolling;
- collapsible **Publication provenance** block with source/hash/fetch information.

Never silently correct the underlying constitutional wording in the presentation layer.

---

## 8. Automatic Constitution publication refresh

Workflow:

- `.github/workflows/constitution-refresh.yml`

Schedule:

- hourly at minute 17 UTC: `17 * * * *`
- manual `workflow_dispatch` also available.

It dispatches normal `jekyll-gh-pages.yml` on `main`; the normal build then fetches, validates, and republishes the Constitution.

If Actions permissions prevent this dispatch after merge, move the schedule trigger directly into the Pages workflow. Do not bypass the normal validation path.

---

## 9. Static publication / navigation

`tools/build_social_routes.py` publishes and validates the new static research pages:

- `changes.html`
- `api.html`

Shared navigation adds:

- Code Changes
- Constitution
- API in footer
- Courts as related external research site.

Existing permanent citation routes and subsection pinpoints must remain stable.

---

## 10. Build pipeline integration

`tools/filter_public_laws_for_publication.py` remains the post-codification publication gate. After finalizing `data/public-laws.json`, Phase II invokes:

1. existing `build_section_history()`;
2. `build_version_history()`;
3. `build_reference_graph()`;
4. `build_code_api()`.

The build fails if:

- no verified baseline/current history exists;
- no exact repository-state history exists;
- explicit statutory graph yields no verified edges;
- general Code API yields no sections.

Existing Criminal Law API generation and hardening remain separate and unchanged.

---

# Tests / verification

Existing important tests remain in force, including:

- `tests/test_section_history.py`
- `tests/test_section_comparison.mjs`
- current-law/codification tests
- Public Law dataset validation
- Title 42 / LFS validation
- Criminal Law API hardening/final-surface tests
- static Pages/social-route checks.

New integration suite:

- `tests/test_research_suite.mjs`

It checks:

- JS syntax for new modules;
- one-surface homepage citation behavior;
- bootstrap wiring;
- version-history/references UI contract;
- Courts citation-search bridge;
- Changes-page evidence distinctions;
- separate general Code API namespace;
- Constitution provenance/legal-validity caveat;
- automatic Constitution refresh workflow.

The full GitHub Pages workflow is the real corpus integration test. Unit tests alone are insufficient because historical Git/LFS retrieval, current USLM links, artifact size, and static assembly must all work against the full repository.

---

# Mandatory pre-merge checklist for PR #14

Do not merge until all are true:

1. Final-head full Pages build/validation succeeds.
2. `data/version-history/manifest.json` reports verified versioned sections and historical snapshots.
3. `data/references/manifest.json` reports verified explicit statutory edges.
4. `data/api/v1/code/index.json` reports a plausible title/section count.
5. `data/constitution-meta.json` exists and matches the published Constitution text.
6. `changes.html` and `api.html` are in the Pages artifact.
7. Spot-check exact history for 18 U.S.C. § 205 and 5 U.S.C. § 552, plus an added section such as 40 U.S.C. § 9701.
8. Spot-check statutory references for sensible outgoing/incoming links.
9. Homepage no longer shows the redundant pink quick-citation card after enhancement.
10. `/cite/<title>/<section>/` and subsection pinpoints still work.
11. Criminal Law API validation remains green and its public namespace/contracts are unchanged.
12. Static publication is below the 900 MiB guard after the compact API redesign.
13. Citation routes and static social metadata generation pass.
14. Pages artifact uploads successfully.

After merge:

1. record PR #14 merge SHA here;
2. watch the `main` Pages workflow through deployment;
3. verify live homepage, Code Changes, API docs/index, history manifest, reference manifest, Constitution metadata, and representative section research;
4. verify the scheduled Constitution-refresh workflow exists on `main`;
5. only then mark Phase II deployed.

---

# Future work after Phase II

## A. True enactment-by-enactment statutory history

Repository-state history is truthful but not necessarily every enacted intermediate state. Gold-standard chronology requires:

1. ordered enactment/action timeline per section;
2. preserved exact amendment instructions or enacted replacement text;
3. deterministic replay against the correct predecessor;
4. snapshot hash after every replayable action;
5. final replay must equal current Code exactly;
6. unsupported actions labeled unavailable, never guessed;
7. UI distinction between preserved source text and site-reconstructed text.

## B. Structured Courts citation graph

Current integration passes an exact Code citation into the Courts case-law search. Build exact counts/lists only when reliable structured case citation metadata exists.

## C. Constitution amendment chronology

If authoritative amendment/ratification metadata becomes available, build amendment history separately from publication provenance. Never treat the HackMD edit timestamp as the legal ratification/effective date.

## D. General API additive research links

Once v1 stabilizes, compact additive fields may expose pointers/counts for:

- source-law history;
- verified version history;
- statutory references;
- provenance hashes.

Keep large research payloads linked/lazy rather than duplicating them into every section object.

---

# Non-negotiable safeguards

1. **Do not break `data/api/v1/criminal-law/`.**
2. **Do not manufacture legal history.**
3. **A Public Law association alone is not proof of exact intermediate text.**
4. **Preserve statutory and constitutional source wording.**
5. **Use explicit references only for the verified statutory graph.**
6. **Keep large research data lazy-loaded.**
7. **Fail closed on history-integrity failures.**
8. **Keep permanent citation and pinpoint routes stable.**
9. **Do not invent enactment dates.**
10. **Do not invent Courts citation counts.**
11. **HackMD publication authority is not constitutional amendment authority.**
12. **Do not duplicate the complete Code corpus just to make an API convenient.**
13. **Full PR CI + production deployment verification are required before calling a release finished.**

---

# Recovery checklist

If another session takes over:

1. Read this file fully.
2. Inspect `main`, `feature/research-suite-phase-2`, and PR #14.
3. Confirm PR #13 production base `3e3d869d66cef16b8b411268aa8cd7098e225192` and history baseline `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`.
4. Inspect builders:
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
6. Inspect pages/workflows:
   - `changes.html`
   - `api.html`
   - `constitution.html`
   - `.github/workflows/constitution-refresh.yml`
7. Inspect latest PR #14 workflow. The old failed run `31983091723` is expected to show a size-only failure from the pre-compact API design; do not confuse that superseded run with the final head.
8. Require a new final-head full Pages run after compact API commits.
9. Pull/inspect the exact successful Pages artifact and record final size/counts.
10. Merge only after clean CI.
11. Watch post-merge Pages deployment to completion.
12. Verify public production URLs directly.
13. Update this status with PR #14 merge SHA and production workflow/deployment IDs.

## Current status

**PR #14 is implemented and corpus validation has already passed once. The only failure in run 31983091723 was the superseded full-body general API pushing static publication to ~1010.2 MiB. The API is now compact and a new final-head Pages run must prove the artifact is below the 900 MiB guard. Phase II is not yet deployed.**
