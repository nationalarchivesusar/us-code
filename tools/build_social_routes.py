#!/usr/bin/env python3
"""Prepare static research pages and compact crawler-friendly metadata routes."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
USLM_NS = "http://xml.house.gov/schemas/uslm/1.0"
NS = f"{{{USLM_NS}}}"
SECTION_RE = re.compile(r"^/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/]+)$", re.I)
BASE_URL = "https://nationalarchivesusar.github.io/us-code/"
IMAGE_URL = BASE_URL + "assets/images/social-card.png"
SITE_NAME = "US Code Library"
STATIC_RESEARCH_PAGES = ("changes.html", "api.html")

# Full public pages retain the richer Twitter-specific metadata. Generated citation
# shells are deliberately tiny: X/Twitter can fall back to the equivalent Open
# Graph title/description/image when twitter:card is present, avoiding three large
# duplicated strings across ~59,000 crawler-only files.
BASE_SOCIAL_MARKERS = (
    'rel="canonical"',
    'property="og:title"',
    'property="og:description"',
    'property="og:url"',
    'property="og:image"',
    'name="twitter:card"',
    'name="twitter:title"',
    'name="twitter:description"',
    'name="twitter:image"',
)
ROUTE_SOCIAL_MARKERS = (
    'rel="canonical"',
    'property="og:title"',
    'property="og:description"',
    'property="og:url"',
    'property="og:image"',
    'name="twitter:card"',
)
MAX_ROUTE_BYTES = 1_500


def compact(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip(" ,;:-") + "…"


def direct_text(section: ET.Element, child_name: str) -> str:
    child = section.find(NS + child_name)
    return " ".join(child.itertext()).strip() if child is not None else ""


def iter_sections(path: Path):
    for _event, element in ET.iterparse(path, events=("end",)):
        if element.tag != NS + "section":
            continue
        match = SECTION_RE.match(element.get("identifier", ""))
        if match:
            yield (
                match.group("title").lower(),
                match.group("section"),
                direct_text(element, "heading"),
            )
        element.clear()


def redirect_script() -> str:
    # /us-code/ is nine characters. Every generated shell lives under that base,
    # so we can avoid repeating the longer compatibility parser on 59k pages.
    return (
        "location.replace('/us-code/?redirect='+encodeURIComponent("
        "location.pathname.slice(9)+location.search+location.hash))"
    )


def render_page(*, canonical: str, page_title: str, description: str, og_type: str) -> str:
    """Return a minimal valid HTML shell for crawlers and deep-link redirects.

    The shell intentionally contains no duplicated visible site chrome or legal
    text. Humans are immediately redirected into the canonical SPA route; social
    crawlers receive canonical/Open Graph metadata without executing JavaScript.
    """
    escape = html.escape
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<title>{escape(page_title)}</title>'
        f'<meta name="description" content="{escape(description, quote=True)}">'
        f'<link rel="canonical" href="{escape(canonical, quote=True)}">'
        f'<meta property="og:title" content="{escape(page_title, quote=True)}">'
        f'<meta property="og:description" content="{escape(description, quote=True)}">'
        f'<meta property="og:type" content="{og_type}">'
        f'<meta property="og:url" content="{escape(canonical, quote=True)}">'
        f'<meta property="og:image" content="{IMAGE_URL}">'
        '<meta name="twitter:card" content="summary">'
        f'<script>{redirect_script()}</script>'
        '</head><body><noscript><a href="/us-code/">United States Code</a></noscript></body></html>\n'
    )


def publish_static_research_pages(site: Path) -> None:
    for relative in STATIC_RESEARCH_PAGES:
        source = ROOT / relative
        if not source.is_file():
            raise SystemExit(f"Required research page is missing: {relative}")
        shutil.copy2(source, site / relative)


def validate_base_pages(site: Path) -> None:
    for relative in ("index.html", "public-laws.html", "404.html", *STATIC_RESEARCH_PAGES):
        text = (site / relative).read_text(encoding="utf-8")
        missing = [marker for marker in BASE_SOCIAL_MARKERS if marker not in text]
        if missing:
            raise SystemExit(f"{relative} is missing social metadata: {missing}")


def validate_route(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in ROUTE_SOCIAL_MARKERS if marker not in text]
    if missing:
        raise SystemExit(f"Generated route {path} is missing metadata: {missing}")
    size = path.stat().st_size
    if size > MAX_ROUTE_BYTES:
        raise SystemExit(
            f"Generated crawler shell is unexpectedly large ({size} bytes > {MAX_ROUTE_BYTES}): {path}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-dir", type=Path, required=True)
    args = parser.parse_args()
    site = args.site_dir.resolve()

    publish_static_research_pages(site)
    validate_base_pages(site)
    titles_payload = json.loads((site / "data" / "titles.json").read_text(encoding="utf-8"))
    title_meta = {str(item["number"]).lower(): item for item in titles_payload["titles"]}
    route_root = site / "cite"
    route_root.mkdir(parents=True, exist_ok=True)

    title_routes = 0
    route_bytes = 0
    max_route_bytes = 0
    for title, metadata in title_meta.items():
        encoded_title = quote(title, safe="")
        canonical = f"{BASE_URL}cite/{encoded_title}/"
        label = metadata.get("label") or f"Title {title}"
        heading = compact(metadata.get("heading", ""), 100)
        page_title = compact(
            f"{label} — {heading} | {SITE_NAME}" if heading else f"{label} | {SITE_NAME}",
            150,
        )
        description = compact(
            f"Browse {label}, {heading}, in the United States Code."
            if heading
            else f"Browse {label} of the United States Code.",
            180,
        )
        destination = route_root / encoded_title / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render_page(
                canonical=canonical,
                page_title=page_title,
                description=description,
                og_type="website",
            ),
            encoding="utf-8",
        )
        size = destination.stat().st_size
        route_bytes += size
        max_route_bytes = max(max_route_bytes, size)
        title_routes += 1

    section_routes = 0
    seen: set[tuple[str, str]] = set()
    sources = sorted((site / "usc").glob("usc*.xml"))
    sources.extend(sorted((site / "data" / "title-42" / "sections").glob("*.xml")))

    for source in sources:
        for title, section, heading in iter_sections(source):
            key = (title, section)
            if key in seen:
                continue
            seen.add(key)
            encoded_title = quote(title, safe="")
            encoded_section = quote(section, safe="")
            canonical = f"{BASE_URL}cite/{encoded_title}/{encoded_section}/"
            citation = f"{title.upper()} U.S.C. § {section}"
            heading = compact(heading, 100)
            page_title = compact(
                f"{citation} — {heading} | {SITE_NAME}"
                if heading
                else f"{citation} | {SITE_NAME}",
                150,
            )
            description = compact(
                f"Read {citation}, {heading}, in the United States Code."
                if heading
                else f"Read {citation} in the United States Code.",
                180,
            )
            destination = route_root / encoded_title / encoded_section / "index.html"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                render_page(
                    canonical=canonical,
                    page_title=page_title,
                    description=description,
                    og_type="article",
                ),
                encoding="utf-8",
            )
            size = destination.stat().st_size
            route_bytes += size
            max_route_bytes = max(max_route_bytes, size)
            section_routes += 1

    if section_routes < 59_000:
        raise SystemExit(f"Too few citation embed routes generated: {section_routes}")
    if title_routes < 50:
        raise SystemExit(f"Too few title embed routes generated: {title_routes}")

    samples = (
        route_root / "18" / "111" / "index.html",
        route_root / "28" / "530B" / "index.html",
        route_root / "42" / "1983" / "index.html",
    )
    for sample in samples:
        if not sample.is_file():
            raise SystemExit(f"Expected citation route was not generated: {sample}")
        validate_route(sample)

    manifest = {
        "title_routes": title_routes,
        "section_routes": section_routes,
        "base_url": BASE_URL,
        "social_image": IMAGE_URL,
        "static_research_pages": list(STATIC_RESEARCH_PAGES),
        "route_bytes": route_bytes,
        "max_route_bytes": max_route_bytes,
        "max_allowed_route_bytes": MAX_ROUTE_BYTES,
    }
    (site / "data" / "social-routes.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Generated {section_routes} section embed routes, {title_routes} title embed routes, "
        f"and published {len(STATIC_RESEARCH_PAGES)} static research pages; "
        f"crawler shells total {route_bytes:,} bytes (max {max_route_bytes:,} bytes)."
    )


if __name__ == "__main__":
    main()
