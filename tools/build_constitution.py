#!/usr/bin/env python3
"""Fetch the USAR Constitution from its NARA HackMD copy for publication."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import requests
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "constitution.txt"
META_OUTPUT = ROOT / "data" / "constitution-meta.json"
NOTE_ID = "CDCV7p2_Sca6O0FrEJyaIQ"
SOURCE_URL = f"https://hackmd.io/{NOTE_ID}?view"
DOWNLOAD_URL = f"https://hackmd.io/{NOTE_ID}/download"

REQUIRED_MARKERS = (
    "The Constitution of The United States of America",
    "Article I - The Congress",
    "Article III - The Judiciary",
    "Amendment XXIV - Occupation of Multiple Offices",
    "Amendment XXVII - Commerce Regulation Authority",
)


def clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip() + "\n"


def valid_constitution(value: str) -> bool:
    return len(value) > 10000 and all(marker in value for marker in REQUIRED_MARKERS)


def append_blank(lines: list[str]) -> None:
    if lines and lines[-1] != "":
        lines.append("")


def strip_inline_markdown(value: str) -> str:
    return value.replace("**", "").replace("__", "").strip()


def strip_markdown(markdown: str) -> str:
    """Convert HackMD Markdown to stable plain text without losing legal structure.

    Headings are deliberately surrounded by blank lines. The browser renderer uses
    those boundaries to distinguish Articles, Amendments, and Sections from the body
    text. The importer preserves wording and only removes Markdown presentation syntax.
    """

    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    cleaned: list[str] = []
    in_frontmatter = False
    frontmatter_seen = False

    for index, raw in enumerate(lines):
        line = raw.rstrip()
        if index == 0 and line.strip() == "---":
            in_frontmatter = True
            frontmatter_seen = True
            continue
        if in_frontmatter:
            if line.strip() == "---":
                in_frontmatter = False
            continue
        if frontmatter_seen and not cleaned and not line.strip():
            continue

        stripped = line.strip()
        if stripped == "---":
            append_blank(cleaned)
            continue

        heading_match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if heading_match:
            append_blank(cleaned)
            cleaned.append(strip_inline_markdown(heading_match.group(1)))
            append_blank(cleaned)
            continue

        line = re.sub(r"^>\s?", "", line)
        line = strip_inline_markdown(line)
        cleaned.append(line)

    return clean_text("\n".join(cleaned))


def fetch_download() -> str | None:
    response = requests.get(
        DOWNLOAD_URL,
        timeout=30,
        headers={"User-Agent": "USAR-NARA-Code-Library/1.0"},
    )
    if not response.ok:
        return None
    content_type = (response.headers.get("content-type") or "").lower()
    body = response.text
    if "html" in content_type or body.lstrip().lower().startswith("<!doctype html"):
        return None
    candidate = strip_markdown(body)
    return candidate if valid_constitution(candidate) else None


def fetch_rendered_page() -> str:
    response = requests.get(
        SOURCE_URL,
        timeout=30,
        headers={"User-Agent": "USAR-NARA-Code-Library/1.0"},
    )
    response.raise_for_status()
    tree = html.fromstring(response.text)
    candidates = tree.xpath('//*[@id="doc"]')
    if not candidates:
        candidates = tree.xpath(
            '//*[contains(concat(" ", normalize-space(@class), " "), " markdown-body ")]'
        )
    if not candidates:
        raise SystemExit("Unable to locate rendered HackMD document body.")

    doc = candidates[0]
    lines: list[str] = []
    for element in doc.xpath(".//h1 | .//h2 | .//h3 | .//h4 | .//p"):
        text = " ".join(part.strip() for part in element.itertext() if part.strip())
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            lines.append(text)
            lines.append("")

    candidate = clean_text("\n".join(lines))
    if not valid_constitution(candidate):
        raise SystemExit("Fetched HackMD content did not pass Constitution validation.")
    return candidate


def write_metadata(text: str) -> None:
    metadata = {
        "schema_version": "1.0",
        "source": SOURCE_URL,
        "source_note_id": NOTE_ID,
        "fetched_at": datetime.now(UTC).isoformat(),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "character_count": len(text),
        "publication_role": "NARA source copy used to publish this constitutional text",
        "legal_validity_note": (
            "Publication from this source records the text displayed by the website. "
            "Editing the publication source does not itself establish that a constitutional "
            "amendment or revision was legally adopted under the Constitution."
        ),
    }
    META_OUTPUT.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    text = fetch_download()
    if text is None:
        text = fetch_rendered_page()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    write_metadata(text)
    print(
        f"Wrote {OUTPUT.relative_to(ROOT)} and {META_OUTPUT.relative_to(ROOT)} "
        f"({len(text)} characters) from {SOURCE_URL}"
    )


if __name__ == "__main__":
    main()
