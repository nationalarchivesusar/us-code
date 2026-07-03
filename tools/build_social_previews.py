#!/usr/bin/env python3
"""Generate static Open Graph/Twitter preview pages for US Code sections."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import quote
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parents[1]
USC_DIR = REPO_ROOT / "usc"
DEFAULT_SITE_ROOT = REPO_ROOT
DEFAULT_BASE_URL = "https://nationalarchivesusar.github.io/us-code/"
SOCIAL_IMAGE = "assets/images/social-card.png"
SITE_NAME = "US Code Library"
NS = {
    "uslm": "http://xml.house.gov/schemas/uslm/1.0",
    "dc": "http://purl.org/dc/elements/1.1/",
}
ROOT_TAGS = {
    f"{{{NS['uslm']}}}title",
    f"{{{NS['uslm']}}}appendix",
    f"{{{NS['uslm']}}}division",
    f"{{{NS['uslm']}}}subtitle",
}


def clean(text: str | None) -> str:
    if text is None:
        return ""
    return " ".join(text.split())


def section_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def title_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def identifier_section_key(identifier: str, title: str) -> str | None:
    match = re.fullmatch(rf"/us/usc/t{re.escape(title)}/s([^/\s]+)", identifier)
    if not match:
        return None
    return section_key(match.group(1))


def direct_child_text(element: ET.Element, name: str) -> str:
    for child in list(element):
        if child.tag == f"{{{NS['uslm']}}}{name}":
            return clean("".join(child.itertext()))
    return ""


def extract_title_metadata(xml_path: Path) -> dict[str, str] | None:
    with xml_path.open("r", encoding="utf-8") as text_fh:
        first_line = text_fh.readline().strip()
        if first_line.startswith("version https://git-lfs.github.com"):
            return None

    identifier = ""
    number = ""
    short_heading = ""
    long_heading = ""
    watching_root = False

    with xml_path.open("rb") as fh:
        context = ET.iterparse(fh, events=("start", "end"))
        for event, elem in context:
            tag = elem.tag
            if event == "start":
                if tag == f"{{{NS['uslm']}}}uscDoc" and not identifier:
                    identifier = elem.get("identifier", "")
                elif tag in ROOT_TAGS and not long_heading:
                    current_id = elem.get("identifier", "")
                    watching_root = True
                    if current_id.startswith("/us/usc/") and not identifier:
                        identifier = current_id
            elif event == "end":
                if tag == f"{{{NS['dc']}}}title" and not short_heading:
                    short_heading = clean(elem.text)
                elif tag == f"{{{NS['uslm']}}}docNumber" and not number:
                    number = clean(elem.text)
                elif watching_root and tag == f"{{{NS['uslm']}}}heading" and not long_heading:
                    long_heading = clean("".join(elem.itertext()))
                elif watching_root and tag in ROOT_TAGS:
                    watching_root = False
                elem.clear()
            if short_heading and number and long_heading:
                break

    heading = long_heading if long_heading else short_heading
    return {
        "number": number,
        "heading": heading,
        "label": short_heading or heading,
        "identifier": identifier,
    }


def iter_sections(xml_path: Path) -> Iterable[dict[str, str]]:
    context = ET.iterparse(xml_path, events=("end",))
    for _event, elem in context:
        if elem.tag == f"{{{NS['uslm']}}}section":
            number = direct_child_text(elem, "num")
            heading = direct_child_text(elem, "heading")
            key = section_key(number)
            if key:
                yield {
                    "number": number,
                    "key": key,
                    "heading": heading,
                    "identifier": elem.get("identifier", ""),
                }
            elem.clear()


def build_base_url(value: str) -> str:
    return value.rstrip("/") + "/"


def route_url(base_url: str, title: str, section: str) -> str:
    return f"{base_url}cite/{quote(title)}/{quote(section)}/"


def app_url(base_url: str, title: str, section: str) -> str:
    return f"{base_url}?t={quote(title)}&s={quote(section)}"


def citation_label(title: str, section_number: str) -> str:
    cleaned = clean(section_number).replace("§", "").replace(".", "").strip()
    return f"{title} U.S. Code § {cleaned}"


def render_preview_page(
    *,
    base_url: str,
    title: str,
    section: str,
    section_number: str,
    section_heading: str,
) -> str:
    route = route_url(base_url, title, section)
    target = app_url(base_url, title, section)
    citation = citation_label(title, section_number)
    page_title = f"{citation} - {section_heading}" if section_heading else citation
    description = f"View {citation} in the {SITE_NAME}."
    image_url = f"{base_url}{SOCIAL_IMAGE}"
    target_json = json.dumps(target)

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html.escape(page_title)}</title>
    <meta name="description" content="{html.escape(description)}" />
    <link rel="canonical" href="{html.escape(route)}" />
    <meta property="og:title" content="{html.escape(page_title)}" />
    <meta property="og:description" content="{html.escape(description)}" />
    <meta property="og:type" content="article" />
    <meta property="og:site_name" content="{html.escape(SITE_NAME)}" />
    <meta property="og:url" content="{html.escape(route)}" />
    <meta property="og:image" content="{html.escape(image_url)}" />
    <meta property="og:image:type" content="image/png" />
    <meta property="og:image:width" content="400" />
    <meta property="og:image:height" content="400" />
    <meta property="og:image:alt" content="Great Seal of the United States, United States Code Library branding." />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content="{html.escape(page_title)}" />
    <meta name="twitter:description" content="{html.escape(description)}" />
    <meta name="twitter:image" content="{html.escape(image_url)}" />
    <meta name="twitter:image:alt" content="Great Seal of the United States, United States Code Library branding." />
    <script>
      (() => {{
        const target = new URL({target_json});
        const params = new URLSearchParams(window.location.search);
        const pinpoint = params.get("p") || params.get("pinpoint");
        if (pinpoint) target.searchParams.set("p", pinpoint);
        window.location.replace(target.toString());
      }})();
    </script>
  </head>
  <body>
    <p><a href="{html.escape(target)}">View {html.escape(citation)} in the {html.escape(SITE_NAME)}.</a></p>
  </body>
</html>
"""


def write_preview(
    *,
    site_root: Path,
    base_url: str,
    title: str,
    section: str,
    section_number: str,
    section_heading: str,
) -> Path:
    out_dir = site_root / "cite" / title / section
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(
        render_preview_page(
            base_url=base_url,
            title=title,
            section=section,
            section_number=section_number,
            section_heading=section_heading,
        ),
        encoding="utf-8",
    )
    return out_path


def generate_previews(
    *,
    site_root: Path,
    base_url: str,
    only_title: str | None,
    only_section: str | None,
) -> int:
    count = 0
    skipped_ambiguous = 0
    for xml_path in sorted(USC_DIR.glob("usc*.xml")):
        metadata = extract_title_metadata(xml_path)
        if not metadata:
            continue
        title = title_key(metadata["number"])
        if only_title and title != title_key(only_title):
            continue
        eligible_sections: list[dict[str, str]] = []
        route_counts: dict[str, int] = {}
        for section in iter_sections(xml_path):
            identifier_key = identifier_section_key(section["identifier"], title)
            if identifier_key != section["key"]:
                continue
            if only_section and section["key"] != section_key(only_section):
                continue
            eligible_sections.append(section)
            route_counts[section["key"]] = route_counts.get(section["key"], 0) + 1
        for section in eligible_sections:
            if route_counts[section["key"]] > 1:
                skipped_ambiguous += 1
                continue
            write_preview(
                site_root=site_root,
                base_url=base_url,
                title=title,
                section=section["key"],
                section_number=section["number"],
                section_heading=section["heading"],
            )
            count += 1
    if skipped_ambiguous:
        print(f"Skipped {skipped_ambiguous} sections with ambiguous preview routes.")
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-root", type=Path, default=DEFAULT_SITE_ROOT)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--title", help="Generate previews for one title, e.g. 18.")
    parser.add_argument("--section", help="Generate previews for one section key, e.g. 1113.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    count = generate_previews(
        site_root=args.site_root,
        base_url=build_base_url(args.base_url),
        only_title=args.title,
        only_section=args.section,
    )
    print(f"Wrote {count} social preview page{'s' if count != 1 else ''} to {args.site_root / 'cite'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
