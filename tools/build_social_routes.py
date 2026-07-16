#!/usr/bin/env python3
"""Generate crawler-friendly social metadata pages for every published citation route."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

USLM_NS = "http://xml.house.gov/schemas/uslm/1.0"
NS = f"{{{USLM_NS}}}"
SECTION_RE = re.compile(r"^/us/usc/t(?P<title>\d+[A-Za-z]?)/s(?P<section>[^/]+)$", re.I)
BASE_URL = "https://nationalarchivesusar.github.io/us-code/"
IMAGE_URL = BASE_URL + "assets/images/social-card.png"
SITE_NAME = "US Code Library"
REQUIRED_SOCIAL_MARKERS = (
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
    return (
        "(function(){var b='/us-code/';var l=window.location;"
        "var p=l.pathname.indexOf(b)===0?l.pathname.slice(b.length):"
        "l.pathname.replace(/^\\/+/, '');var s=p+l.search+l.hash;"
        "window.location.replace(b+'?redirect='+encodeURIComponent(s));})();"
    )


def render_page(*, canonical: str, page_title: str, description: str, og_type: str) -> str:
    escape = html.escape
    # Deliberately compact: this file is generated roughly 60,000 times.
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(page_title)}</title>'
        f'<meta name="description" content="{escape(description, quote=True)}">'
        f'<link rel="canonical" href="{escape(canonical, quote=True)}">'
        f'<meta property="og:title" content="{escape(page_title, quote=True)}">'
        f'<meta property="og:description" content="{escape(description, quote=True)}">'
        f'<meta property="og:type" content="{og_type}">'
        f'<meta property="og:site_name" content="{SITE_NAME}">'
        f'<meta property="og:url" content="{escape(canonical, quote=True)}">'
        f'<meta property="og:image" content="{IMAGE_URL}">'
        f'<meta property="og:image:secure_url" content="{IMAGE_URL}">'
        '<meta property="og:image:type" content="image/png">'
        '<meta property="og:image:width" content="400">'
        '<meta property="og:image:height" content="400">'
        '<meta property="og:image:alt" content="Great Seal of the United States and United States Code Library branding.">'
        '<meta name="twitter:card" content="summary">'
        f'<meta name="twitter:title" content="{escape(page_title, quote=True)}">'
        f'<meta name="twitter:description" content="{escape(description, quote=True)}">'
        f'<meta name="twitter:image" content="{IMAGE_URL}">'
        '<meta name="twitter:image:alt" content="Great Seal of the United States and United States Code Library branding.">'
        '<meta name="theme-color" content="#8b1e1e">'
        f'<script>{redirect_script()}</script></head>'
        f'<body><p><a href="{escape(canonical, quote=True)}">Open this U.S. Code page</a></p></body></html>\n'
    )


def validate_base_pages(site: Path) -> None:
    for relative in ("index.html", "public-laws.html", "404.html"):
        text = (site / relative).read_text(encoding="utf-8")
        missing = [marker for marker in REQUIRED_SOCIAL_MARKERS if marker not in text]
        if missing:
            raise SystemExit(f"{relative} is missing social metadata: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-dir", type=Path, required=True)
    args = parser.parse_args()
    site = args.site_dir.resolve()

    validate_base_pages(site)
    titles_payload = json.loads((site / "data" / "titles.json").read_text(encoding="utf-8"))
    title_meta = {str(item["number"]).lower(): item for item in titles_payload["titles"]}
    route_root = site / "cite"
    route_root.mkdir(parents=True, exist_ok=True)

    title_routes = 0
    for title, metadata in title_meta.items():
        encoded_title = quote(title, safe="")
        canonical = f"{BASE_URL}cite/{encoded_title}/"
        label = metadata.get("label") or f"Title {title}"
        heading = compact(metadata.get("heading", ""), 120)
        page_title = compact(
            f"{label} — {heading} | {SITE_NAME}" if heading else f"{label} | {SITE_NAME}",
            180,
        )
        description = compact(
            f"Browse {label}, {heading}, in the United States Code."
            if heading
            else f"Browse {label} of the United States Code.",
            240,
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
            heading = compact(heading, 120)
            page_title = compact(
                f"{citation} — {heading} | {SITE_NAME}"
                if heading
                else f"{citation} | {SITE_NAME}",
                180,
            )
            description = compact(
                f"Read {citation}, {heading}, in the United States Code."
                if heading
                else f"Read {citation} in the United States Code.",
                240,
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
            section_routes += 1

    # The current corpus contains 59,536 unique routable section identifiers.
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
        text = sample.read_text(encoding="utf-8")
        missing = [marker for marker in REQUIRED_SOCIAL_MARKERS if marker not in text]
        if missing:
            raise SystemExit(f"Generated route {sample} is missing metadata: {missing}")

    manifest = {
        "title_routes": title_routes,
        "section_routes": section_routes,
        "base_url": BASE_URL,
        "social_image": IMAGE_URL,
    }
    (site / "data" / "social-routes.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {section_routes} section embed routes and {title_routes} title embed routes.")


if __name__ == "__main__":
    main()
