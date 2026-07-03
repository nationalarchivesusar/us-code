# United States Code Library

This repository contains the raw United States Code XML files along with a lightweight
static website that renders the material in a reader-friendly format for the United
States of America Roblox (USAR) community. The website is designed to run on GitHub
Pages from the repository root and mirrors the structured browsing experience of
Cornell Law's legal information pages.

## Getting started

1. Install the Python dependencies that ship with the standard library (no extra
   packages are required).
2. Generate the lightweight metadata index used by the front-end:

   ```bash
   tools/build_index.py
   ```

   The command creates `data/titles.json`, which the web application uses to
   populate the title list. Re-run it whenever XML files are updated.
3. Open `index.html` in your browser or push the repository to GitHub with Pages
   enabled (serving from the repository root) to browse the code.

## Working with Git LFS titles

Several large titles (for example, Title 42) are stored in Git LFS. The website can
only render these sections when the full XML files are present locally. If you see a
message indicating that the content is stored in Git LFS, run the following commands
before regenerating the index:

```bash
git lfs install
git lfs pull
```

## Development notes

* `assets/js/app.js` fetches XML files on demand and converts the USLM markup to
  rich HTML in the browser.
* Styling lives in `assets/css/main.css` and aims to provide a modern, accessible
  reading experience with responsive layout.
* The repository intentionally keeps the XML source untouched; all enhancements occur
  in the static site layer.
