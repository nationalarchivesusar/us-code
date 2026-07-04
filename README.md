# United States Code Library

This repository contains a USAR-adapted United States Code: United States Legislative Markup (USLM) XML for the U.S. Code, amended to incorporate enacted public laws of the United States of America Roblox (USAR), together with a static website that renders the Code in a reader-friendly format.

## Repository contents

- `usc/usc*.xml` — authoritative title XML files.
- `assets/` and `index.html` — browser-based Code reader.
- `data/titles.json` — generated title metadata used by the website.
- `data/title-42/` — generated publication chunks for Title 42.
- `tools/` — repository validation and publication utilities.
- `tests/` — automated validation tests.

Local codification workbenches, source archives, implementation plans, credentials, and temporary installers are not part of the public repository. The public repository should contain the resulting amended Code XML and the tooling required to validate and publish it.

## Building the title index

```bash
python tools/build_index.py
```

Rebuild `data/titles.json` whenever title XML is changed.

## Title 42 and Git LFS

`usc/usc42.xml` is stored through Git LFS. Obtain the complete object before editing or validating Title 42:

```bash
git lfs install
git lfs pull
python tools/build_title42_chunks.py
python tools/check_title42_build.py
```

The generated Title 42 chunks are publication artifacts; `usc/usc42.xml` remains the authoritative editing source.

## Validation

Run the checks available in the repository after codification changes:

```bash
python tools/build_index.py
python tools/check_encoding.py
python tools/audit_applied_material.py
python tools/build_title42_chunks.py
python tools/check_title42_build.py
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/test_usar_notes.mjs tests/test_citation_routing.mjs
```

## USAR-added material

Project-added USLM nodes use deterministic identifiers beginning with `rp-`. The website uses that prefix to distinguish USAR amendment and statutory notes from preexisting editorial notes without changing the underlying XML order.
