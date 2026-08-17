# Phase III — Visual Polish and Enactment History

Status: active development.

## Scope

1. Perform a source-level visual/UX audit across the public U.S. Code site and consolidate remaining spacing, hierarchy, utility-control, panel, and responsive inconsistencies.
2. Build a conservative enactment-history layer from the repository's existing codification audit evidence.
3. Publish individual Public Law enactment events only when the repository contains sufficient evidence to identify the affected Code target and applied operation. Exact text snapshots must not be fabricated from summaries.
4. Preserve the existing verified repository-state history as a separate concept from enactment events.
5. Preserve all existing public routes and both API contracts, especially `data/api/v1/criminal-law/`.

## Reliability rule

An enactment event may describe the Public Law, provision, target, treatment/operation, source quotation, and verified implementation evidence. It may expose exact before/after statutory text only where that text is independently recoverable and validated from repository state or deterministic codification evidence. Audit summaries are never promoted into statutory text.

## Recovery checklist

- Inspect `audit/provision-ledger.json` and `audit/xml-integration-results.json` for validated law-to-Code actions.
- Generate `data/enactment-history/manifest.json` and per-section records from only eligible section/subsection targets.
- Add enactment-history UI under the existing section research surface without replacing repository-state history.
- Add shared visual polish CSS and regression checks.
- Add workflow build/validation hooks.
- Run the complete Pages build, inspect generated counts, merge only on green CI, then confirm production Pages deployment.
