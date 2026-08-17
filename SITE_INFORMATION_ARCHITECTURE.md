# U.S. Code Site Information Architecture

This file records the canonical public-facing organization of `nationalarchivesusar/us-code`. Use it when adding pages or navigation so the site does not drift back into a mixture of destinations, in-page anchors, and specialized tools.

## Global navigation rule

Global navigation contains **destinations only**. A control does not belong in the site header merely because it is useful.

Canonical primary navigation:

1. **U.S. Code** — `/us-code/`
2. **Public Laws** — `/us-code/public-laws.html`
3. **Constitution** — `/us-code/constitution.html`
4. **Criminal Law** — `/us-code/criminal-law.html`
5. **United States Courts ↗** — related external research site

Do not add `Home`, `Search Code`, `Code Titles`, `Code Changes`, or `API` to the primary navigation.

The brand/seal already links to the U.S. Code root. Search and title browsing are functions of the U.S. Code page, not separate destinations.

## Secondary/footer navigation

The footer may expose utilities that are important but not primary legal-material destinations:

- U.S. Code
- Public Laws
- Constitution
- Criminal Law
- **Developer API** — `/us-code/api.html`
- United States Courts

## U.S. Code

The root page is the Code application. Its local hierarchy is:

- Search the Code
- Browse U.S. Code titles
- Title overview / contents
- Section page
- Section-local research controls such as statute/notes, source laws, version history, references, comparison, copy, print, and Courts case-law handoff

`Search Code` and `Code Titles` must remain page content rather than global navigation items.

Permanent citation routes under `/cite/<title>/<section>/` remain stable.

## Public Laws

Public Laws is the legislative-history destination. It contains two **local views of the same research domain**:

- **Public Laws** — law-oriented browsing and filtering
- **Code Changes** — affected-section/change-oriented browsing and filtering

The local switcher is intentionally not part of global navigation.

Legacy `/changes.html` remains a compatibility alias and redirects to:

`/public-laws.html?view=changes`

Existing `public-laws.html#pl-<number>` deep links remain law-oriented and must continue to open the relevant Public Law record.

## Constitution

The Constitution remains a separate top-level legal corpus. Its local tools include:

- constitutional search
- contents/TOC
- Article, Amendment, and Section deep links
- citation/permalink controls
- publication provenance

These are local research controls, not global destinations.

## Criminal Law

Criminal Law is an operational charge-search destination. The primary task must appear first:

1. charge search/filter
2. charge results
3. **About this criminal-law catalog** disclosure

The disclosure contains methodology/source lineage, catalog totals, sentencing caveats, and the permanent charge index link.

Generated `/criminal/`, `/criminal/title18/`, `/criminal/dc/`, and individual charge routes remain available for stable URLs, crawler/no-JavaScript access, and compatibility. They are not a second site-navigation hierarchy and should not be promoted in the global header.

The public Roblox-facing Criminal Law API contract under `data/api/v1/criminal-law/` is unaffected by information-architecture work.

## Developer API

`api.html` is developer documentation and is intentionally footer-level. The general Code API remains under `data/api/v1/code/` and must remain separate from the existing Criminal Law API.

## Shared shell implementation

`assets/js/site-bootstrap.js` is the runtime canonical source for primary/footer navigation and active-state behavior. It normalizes source and generated pages so navigation cannot silently diverge.

`assets/css/navigation.css` provides the responsive menu. On narrow screens the five-item global navigation collapses behind a Menu control instead of becoming a wall of two-column buttons.

Source HTML and generated permanent-route markup should still contain sensible no-JavaScript fallback navigation matching this document.

## Classification test for new UI

Before adding an item to global navigation, ask:

> Does this take the user to a distinct major legal-information destination?

If it only scrolls the current page, filters content, changes a view, opens a panel, selects a tab, or exposes a developer utility, it should remain local or secondary.

Examples:

- U.S. Code → Public Laws: **global**
- Public Laws → Constitution: **global**
- Public Laws → Code Changes: **local view**
- Search → Browse titles: **local page functionality**
- Statute → Notes: **local section control**
- Redline → Side by side: **local comparison control**
- API documentation: **footer utility**
- Contents entries: **TOC**

## Compatibility safeguards

Information-architecture changes must not break:

- `/cite/<title>/<section>/`
- subsection pinpoint query behavior
- `public-laws.html#pl-<number>`
- `/criminal/...` permanent charge URLs
- `data/api/v1/criminal-law/`
- `data/api/v1/code/`
- Constitution Article/Amendment/Section anchors
- Courts case-law citation handoff

Old navigational aliases may redirect, but stable legal/data contracts should not be repurposed silently.
