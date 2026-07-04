# United States Code Library

This repository contains a USAR-adapted United States Code: real United States
Legislative Markup (USLM) XML for the U.S. Code, into which a set of fictional
public laws approved for the United States of America Roblox (USAR) community
have been codified directly into the XML, the same way the Office of the Law
Revision Counsel (OLRC) incorporates real public laws into the real Code. A
lightweight static website renders the material in a reader-friendly format,
designed to run on GitHub Pages from the repository root and mirroring the
structured browsing experience of Cornell Law's legal information pages.

## USAR codification

Approved USAR public laws are incorporated as amendments directly into the
`usc/usc*.xml` title files -- new/amended sections, amendment notes, and
statutory notes are added to the XML in the same positions and structural
style OLRC uses for real amendments. `codification/state.json` tracks which
laws have been applied and to which files; the codification tooling itself
(`tools/rp_codifier.py`, `codify_us_code.bat`, the `codification/` plan and
packet data) is local workbench tooling and is **not** included in the public
repository (see `.gitignore`) -- only its output, the amended XML, is
published.

Content added by this process is tagged with a deterministic `id="rp-..."`
prefix (see `tools/rp_codifier.py`'s `make_id()`), which the front end uses to
give USAR-added notes distinct treatment -- see "USAR notes vs. ordinary
notes" below.

## Getting started

1. Install the Python dependencies that ship with the standard library (no extra
   packages are required).
2. Generate the lightweight metadata index used by the front-end:

   ```bash
   tools/build_index.py
   ```

   The command creates `data/titles.json`, which the web application uses to
   populate the title list. Re-run it whenever XML files are updated.
3. Generate static social preview pages when preparing a Pages artifact:

   ```bash
   tools/build_social_previews.py --site-root _site
   ```

   The deploy workflow runs this after Jekyll so Discord, X/Twitter, and other
   link preview crawlers can read per-section metadata at URLs like
   `/cite/18/1113/`.
4. Open `index.html` in your browser or push the repository to GitHub with Pages
   enabled (serving from the repository root) to browse the code.

## Title 42 and Git LFS

Title 42 (`usc/usc42.xml`) is large enough that it is stored in Git LFS rather
than served directly to the published site. Instead, the publish workflow
(`.github/workflows/jekyll-gh-pages.yml`) generates a chunked representation
of Title 42 ahead of the Jekyll build:

```bash
git lfs install
git lfs pull
tools/build_title42_chunks.py
```

This writes `data/title-42/manifest.json` (a navigation tree covering every
Title 42 section) plus one small XML file per section under
`data/title-42/sections/`. The workflow then deletes `usc/usc42.xml` before
publishing, since the full title is no longer needed once the chunks exist.
The front end (`assets/js/app.js`) detects Title 42's `chunked: true` metadata
entry and loads only the manifest plus whichever individual section a reader
opens -- it never fetches `usc/usc42.xml` and never downloads all sections at
once. `tools/check_title42_build.py` validates the chunked build (manifest
present, section count, every manifest entry resolves to a real file, the
front end never references the deleted `usc42.xml`, a representative section
loads, and citation routing resolves correctly).

Every other title is small enough to ship as a single XML file and is loaded
in full by the front end.

## USAR notes vs. ordinary notes

The Notes panel on a section page can contain both real, pre-existing OLRC
editorial/historical notes (yellow) and notes added by USAR codification
(green, badged e.g. "USAR Amendment Note"). The distinction is made
deterministically from the `id="rp-..."` prefix on the `<note>` element
(never by guessing from text, and never by public-law Congress-number ranges,
since real historical public laws can overlap those numerically with USAR's
fictional ones) -- see `isUsarNoteElement()` in `assets/js/app.js`. USAR notes
are displayed first in the panel, then ordinary notes, each group keeping its
original relative order; the underlying XML order is never changed, only the
on-page display order. The relevant CSS lives in `assets/css/main.css` under
`.usc-note--usar` / `.usc-note__badge`.

## Development notes

* `assets/js/app.js` fetches XML files on demand and converts the USLM markup to
  rich HTML in the browser.
* `tools/build_social_previews.py` creates tiny generated HTML pages containing
  Open Graph/Twitter metadata and redirects readers back into the main app.
* Styling lives in `assets/css/main.css` and aims to provide a modern, accessible
  reading experience with responsive layout.
* `tools/check_encoding.py` audits the XML for Unicode replacement characters
  and known mojibake patterns, and is worth re-running after any future
  codification or manual edit.
* Local codification/workbench tooling (`tools/rp_codifier.py`,
  `codify_us_code.bat`, `codification/`, and a few of the test files under
  `tests/` that exercise them) is excluded from the public repository via
  `.gitignore`. The XML source is not "untouched" -- approved USAR public
  laws are codified directly into it -- but all such changes go through that
  local, plan-driven tooling rather than ad hoc manual edits, so every change
  has a corresponding plan, source law text, and audit trail on the machine
  that applied it.
