# Legal Research Phase III

Status: implementation in progress on `feature/production-qa-phase3`.

This file is a recovery checkpoint for the legal-research work that follows the information-architecture rebuild. It supplements `LEGAL_RESEARCH_ROADMAP.md`.

## Release objective

Phase III begins by making the already-built legal-research features durable in production, then adds only historical claims that can be supported by exact repository evidence.

The governing rule remains: **never manufacture an intermediate statutory version merely because a Public Law is associated with a section.**

## Production QA findings

The post-IA audit found that the Pages workflow had drifted away from the Phase II research suite. Source files for the features remained in the repository, but the production workflow was not regenerating or packaging all of their data.

The affected outputs were:

- `data/section-history/`
- `data/version-history/`
- `data/references/`
- `data/api/v1/code/`
- `api.html`
- the `changes.html` compatibility route

This branch repairs the workflow and adds regression coverage so future Pages changes cannot silently omit these surfaces.

The Criminal Law API remains a separate contract under `data/api/v1/criminal-law/` and must retain all of its existing hardening/fail-closed checks.

## QA polish in this release

- Hide the title-browser Git/LFS implementation note from the public homepage.
- Tighten the gap between the homepage search area and Code browser.
- Reduce excess vertical space in the Public Laws hero/statistics area.
- Simplify the Criminal Law search heading to one clear `Search charges` label.
- Preserve the five-destination global information architecture.

## Historical version evidence levels

### 1. Verified repository state

An exact section text recovered from a known repository commit. This is the base level of historical evidence.

It means the site can prove that the section text existed in that stored repository state. It does **not** by itself identify which enactment caused the state.

### 2. Direct Public Law repository link

Phase III adds a conservative direct-link marker.

A version may receive `direct_public_law_link` only when:

1. the snapshot commit message explicitly names one or more Public Laws;
2. the Public Law publication index associates those named laws with Code sections; and
3. for the section being displayed, exactly one of the laws named by the commit is associated with that section.

The emitted record contains the Public Law number/title, the evidence basis, and an express limitation.

This means the exact stored state has a direct repository association with that Public Law. It does **not** claim that:

- the repository commit establishes the law's legal effective date;
- the commit isolates every legal effect of that law;
- no unrelated cleanup occurred in the commit; or
- the site's Public Law target index independently proves the operative amendment text.

### 3. Future exact enactment delta

The next evidence tier should require the enactment instruction itself to be parsed and successfully replayed against the preceding verified statutory state.

Only then should the site label a state as an exact `after Pub. L. X` statutory version in the stronger legal-history sense.

## Snapshot set

The Phase III builder currently tracks:

- baseline `00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46`
- repeal reconciliation `21e483ef2f71762f954f20c48a9a207898848645`
- Public Laws 41-271 / 42-272 / 42-273 integration `6ece679f3e504db46d27fbd06a48980850a056f1`
- Public Law 42-274 integration `8461e76f47a7df89b4e03888aa6986460890b072`
- current published Code

Identical consecutive section texts remain collapsed so the UI does not pretend that an unchanged repository snapshot is a new statutory version.

## General Code API QA

The general Code API remains separate from the Roblox Criminal Law API.

A production-specific issue was found for Title 42: the Pages artifact intentionally removes monolithic `usc/usc42.xml` and publishes section-level USLM XML chunks. The general API must therefore not return the removed monolithic file as a full-text source.

Phase III changes title manifests to expose a production-valid `source` object:

- ordinary titles: `uslm-xml`
- Title 42: `uslm-section-manifest` at `data/title-42/manifest.json`

Compatibility fields `source_xml` and `source_manifest` remain available where appropriate.

## Required release checks

Before merging this phase:

- full Pages data generation succeeds;
- all Python tests pass, including `tests/test_version_history.py`;
- all Node tests pass, including publication-pipeline guards;
- section-history manifest exists and has verified changes;
- version-history manifest exists and has at least one direct Public Law link;
- statutory reference graph exists and has verified edges;
- general Code API exists and Title 42 points to its published manifest;
- `api.html` and `changes.html` exist in the Pages artifact;
- Criminal Law API hardening/finalization checks remain green;
- Pages artifact remains below the existing 900 MiB safety limit.

## Next Phase III work after this release

1. Build an amendment-instruction parser for Public Laws, starting with tightly structured commands such as `strike`, `insert`, `add`, `redesignate`, and `repeal`.
2. Replay only high-confidence amendment instructions against a verified prior text and compare the computed output to a later verified repository state.
3. Publish an enactment-specific version only when the replay exactly matches the verified state.
4. Preserve failed/ambiguous replays as audit records rather than guessing.
5. Extend the Courts site bridge so case records can expose Code citations and Code sections can display verified citing cases.
6. Continue production visual QA on representative desktop/mobile widths after every major research feature.

## Recovery checklist

If this chat is lost:

1. Open this file and `LEGAL_RESEARCH_ROADMAP.md`.
2. Inspect the latest merged PR after the information-architecture rebuild.
3. Confirm `.github/workflows/jekyll-gh-pages.yml` still invokes all four research builders.
4. Confirm the Criminal Law API namespace and hardening checks are unchanged.
5. Run the complete Pages workflow before merging any further history work.
6. Do not upgrade a repository association into a legal enactment claim without additional textual evidence.
