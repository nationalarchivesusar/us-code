# U.S. Code Site — Phase III Visual / UX Audit

This audit covers the public research surfaces after the information-architecture rebuild. It is intentionally about visual hierarchy, density, consistency, responsive behavior, and task flow—not a new redesign language.

## Governing principle

The site should read like an institutional legal publication first and a web application second. Controls should be visually subordinate to law text, and global navigation, local navigation, research utilities, filters, and document text must remain visibly distinct.

## Findings and dispositions

### Shared masthead and navigation

**Finding:** The masthead remained slightly tall relative to the now-simplified five-destination navigation.

**Disposition:** Reduced masthead/logo height modestly while preserving the institutional seal, kicker, title, and theme controls. Primary navigation keeps the existing IA and active-state treatment.

### U.S. Code home/search

**Finding:** The earlier duplicate citation box was already removed, but the search band still behaved somewhat like a marketing hero because of its vertical scale.

**Disposition:** Tightened search-band vertical rhythm. No new homepage cards or dashboard content were added.

### Code section pages

**Finding:** The section metadata summary already drew a horizontal rule, and the research toolbar immediately drew another one. Utility buttons were individually boxed, creating a dense row of form-like controls directly above statutory text/research panels.

**Disposition:** Removed the duplicate toolbar rule when the metadata summary is present. Converted toolbar actions to quieter legal-research utilities with separators and hover/focus treatment. Kept all existing functionality and labels.

**Finding:** Source-law history, version history, references, and related panels used a succession of equally strong boxed containers.

**Disposition:** Standardized closed panels to a lighter document-rule treatment and reserve the tinted summary/body separation for an opened panel. Tightened panel spacing and count labels.

### Historical research

**Finding:** Repository-state version history and Public Law source history were useful but did not expose a conservative law-by-law codification timeline.

**Disposition:** Added a separate `Verified enactment history` surface generated only from applied codification-audit records tied to concrete U.S. Code section/subsection targets and concrete XML node changes. This is deliberately separate from exact repository-state version history.

### Public Laws / Code Changes

**Finding:** The local `Public Laws | Code Changes` switcher still looked close to a second global navigation bar.

**Disposition:** Restyled it as a local tab strip with a single bottom rule and active underline. The global five-destination navigation remains visually stronger.

### Criminal Law

**Finding:** The IA rebuild correctly made charge search the first substantive task, but the retained hero still consumed more vertical space than necessary for an operational lookup page.

**Disposition:** Reduced hero scale and shell/search padding without removing identity, status, or explanatory content.

### Constitution

**Finding:** Heading utility alignment was fixed separately in PR #16. Remaining controls should continue to stay subordinate to the constitutional text.

**Disposition:** Tightened controls/provenance spacing and document line-height slightly. No constitutional wording, heading structure, anchors, or citation behavior was changed.

### Responsive behavior

**Finding:** Research toolbar utilities switched into a two-column button grid on small screens, which made lightweight actions visually heavier than they are on desktop.

**Disposition:** Keep them as wrapping inline utilities on mobile. Public Law local tabs may horizontally adapt without becoming stacked global navigation.

### Accessibility and overflow

**Disposition:** Added consistent visible focus treatment for interactive elements and defensive wrapping/min-width rules for dense legal metadata. Print behavior remains controlled by the existing page-specific print rules.

## Explicit non-goals

- No change to statutory or constitutional text.
- No change to canonical citation URLs or subsection pinpoints.
- No change to the global information architecture.
- No change to the Criminal Law API or general Code API contracts.
- No decorative dashboard content added simply to fill whitespace.
- No fabricated historical statutory text.

## Files implementing this audit

- `assets/css/site-polish.css`
- `assets/css/enactment-history.css`
- `assets/js/enactment-history.js`
- `tools/build_enactment_history.py`
- `tests/test_enactment_history.py`
- `tests/test_phase_iii.mjs`

The existing component styles remain the primary design system; `site-polish.css` is a deliberately small final hierarchy/rhythm layer loaded by `site-bootstrap.js`.
