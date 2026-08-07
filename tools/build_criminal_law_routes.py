#!/usr/bin/env python3
"""Generate static, crawlable criminal-law pages and a dedicated sitemap.

The interactive criminal-law.html page remains the primary research UI. These
routes give search engines, link unfurlers, Roblox users, and humans permanent
HTML URLs whose operative text does not depend on JavaScript.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote

BASE_URL = "https://nationalarchivesusar.github.io/us-code/"
SITE_NAME = "US Code Library"
IMAGE_URL = BASE_URL + "assets/images/social-card.png"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def compact(value: str | None, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip(" ,;:-") + "…"


def esc(value: object) -> str:
    return html.escape(str(value or ""))


def shell(*, title: str, description: str, canonical: str, body: str) -> str:
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{html.escape(description, quote=True)}">
  <link rel="canonical" href="{html.escape(canonical, quote=True)}">
  <meta property="og:title" content="{html.escape(title, quote=True)}">
  <meta property="og:description" content="{html.escape(description, quote=True)}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:url" content="{html.escape(canonical, quote=True)}">
  <meta property="og:image" content="{IMAGE_URL}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{html.escape(title, quote=True)}">
  <meta name="twitter:description" content="{html.escape(description, quote=True)}">
  <meta name="twitter:image" content="{IMAGE_URL}">
  <meta name="theme-color" content="#8b1e1e">
  <link rel="stylesheet" href="{BASE_URL}assets/css/main.css">
  <link rel="stylesheet" href="{BASE_URL}assets/css/criminal-law-static.css">
</head>
<body>
  <header class="static-law-header">
    <div class="static-law-header__inner">
      <a class="static-law-brand" href="{BASE_URL}">United States Code Library</a>
      <nav aria-label="Criminal law navigation">
        <a href="{BASE_URL}criminal-law.html">Criminal Law Search</a>
        <a href="{BASE_URL}criminal/">Permanent Index</a>
        <a href="{BASE_URL}public-laws.html">Public Laws</a>
      </nav>
    </div>
  </header>
  {body}
  <footer class="site-footer"><div class="site-footer__inner"><p>Maintained for the USAR community.</p><p>This permanent page is generated from the same structured legal data used by the website API.</p></div></footer>
</body>
</html>\n'''


def write_page(site: Path, relative: str, content: str) -> str:
    destination = site / relative / "index.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return BASE_URL + relative.strip("/") + "/"


def source_badge(source: str) -> str:
    return f'<span class="static-law-badge">{esc(source)}</span>'


def section_page(*, citation: str, heading: str, text: str, source: str,
                 canonical: str, meta: list[str] | None = None,
                 extra_html: str = "", source_link: str | None = None) -> str:
    description = compact(f"Read {citation}, {heading}. {text}", 260)
    page_title = compact(f"{citation} — {heading} | {SITE_NAME}", 180)
    badges = [source_badge(source)]
    for item in meta or []:
        if item:
            badges.append(source_badge(item))
    link_html = ""
    if source_link:
        link_html = f'<a class="static-law-source-link" href="{html.escape(source_link, quote=True)}">Open related source</a>'
    body = f'''
<main class="static-law-shell">
  <nav class="static-law-breadcrumbs" aria-label="Breadcrumb"><a href="{BASE_URL}criminal/">Criminal Law</a><span>›</span><span>{esc(source)}</span></nav>
  <article class="static-law-article">
    <p class="eyebrow">{esc(source)}</p>
    <h1>{esc(citation)}</h1>
    <h2>{esc(heading)}</h2>
    <div class="static-law-meta">{''.join(badges)}</div>
    {link_html}
    <div class="static-law-text">{esc(text)}</div>
    {extra_html}
  </article>
</main>'''
    return shell(title=page_title, description=description, canonical=canonical, body=body)


def list_page(*, title: str, description: str, canonical: str, eyebrow: str,
              intro: str, items: list[tuple[str, str, str]]) -> str:
    links = "\n".join(
        f'<li><a href="{html.escape(url, quote=True)}"><strong>{esc(citation)}</strong><span>{esc(heading)}</span></a></li>'
        for citation, heading, url in items
    )
    body = f'''
<main class="static-law-shell">
  <section class="static-law-index">
    <p class="eyebrow">{esc(eyebrow)}</p>
    <h1>{esc(title)}</h1>
    <p>{esc(intro)}</p>
    <ul class="static-law-index__list">{links}</ul>
  </section>
</main>'''
    return shell(title=f"{title} | {SITE_NAME}", description=description, canonical=canonical, body=body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-dir", type=Path, required=True)
    args = parser.parse_args()
    site = args.site_dir.resolve()
    api = site / "data" / "api" / "v1" / "criminal-law"

    federal = load(api / "federal-code.json")
    dc = load(api / "dc-code.json")
    title18_index = load(api / "title18-index.json")
    documents = load(api / "documents.json")
    sentencing = load(api / "sentencing.json")

    urls: list[str] = []

    # Federal Criminal Code.
    fcc_items = []
    for sec in federal["sections"]:
        number = str(sec["section"])
        relative = f"criminal/fcc/{quote(number, safe='')}"
        canonical = BASE_URL + relative + "/"
        cls = sec.get("offense_class")
        rule = sec.get("class_rule") or {}
        meta = []
        if cls:
            meta.append(f"Class {cls}")
        if sec.get("chapter"):
            meta.append(f"Chapter {sec['chapter']}: {sec.get('chapter_heading','')}")
        extra = ""
        if rule:
            extra = (
                '<aside class="static-law-note"><strong>Federal Criminal Code class schedule</strong>'
                f'<p>Initial arrest: {rule.get("initial_min_minutes")}–{rule.get("initial_max_minutes")} minutes. '
                f'Court maximum: {rule.get("court_max_days")} days. Citation maximum: ${int(rule.get("citation_max",0)):,}.</p>'
                '<p>Public Law 39-267 is published separately because the supplied enactments do not expressly cross-walk its felony/misdemeanor classes to the Code’s A–G classes.</p></aside>'
            )
        page = section_page(
            citation=f"FCC § {number}",
            heading=sec["heading"],
            text=sec["text"],
            source="Federal Criminal Code (Public Law 37-261)",
            canonical=canonical,
            meta=meta,
            extra_html=extra,
            source_link=BASE_URL + "public-laws.html#pl-37-261",
        )
        url = write_page(site, relative, page)
        urls.append(url)
        fcc_items.append((f"FCC § {number}", sec["heading"], url))

    fcc_index = BASE_URL + "criminal/fcc/"
    write_page(site, "criminal/fcc", list_page(
        title="Federal Criminal Code",
        description="Permanent section index for the Federal Criminal Code enacted by Public Law 37-261.",
        canonical=fcc_index,
        eyebrow="Public Law 37-261",
        intro="Permanent, crawlable section pages for the Federal Criminal Code used across the District of Columbia.",
        items=fcc_items,
    ))
    urls.append(fcc_index)

    # Federalized D.C. Criminal Code lineage.
    dc_items = []
    for sec in dc["sections"]:
        number = str(sec["section"])
        relative = f"criminal/dc/{quote(number, safe='')}"
        canonical = BASE_URL + relative + "/"
        cls = sec.get("offense_class")
        meta = [f"Class {cls}" if cls else "", f"Chapter {sec['chapter']}: {sec.get('chapter_heading','')}" if sec.get("chapter") else ""]
        page = section_page(
            citation=f"D.C. Criminal Code § {number}",
            heading=sec["heading"],
            text=sec["text"],
            source="Federalized D.C. Criminal Code (Public Law 36-260 § 10(b))",
            canonical=canonical,
            meta=meta,
            source_link=BASE_URL + "public-laws.html#pl-36-260",
        )
        url = write_page(site, relative, page)
        urls.append(url)
        dc_items.append((f"D.C. Criminal Code § {number}", sec["heading"], url))

    dc_index = BASE_URL + "criminal/dc/"
    write_page(site, "criminal/dc", list_page(
        title="Federalized D.C. Criminal Code",
        description="Permanent section index for the D.C. Criminal Code adopted as federal law by Public Law 36-260 § 10(b).",
        canonical=dc_index,
        eyebrow="Public Law 36-260 § 10(b)",
        intro="This preserves the D.C. Criminal Code adopted as federal law when the municipal government was dissolved, including the § 102(11) amendment directed by Public Law 36-260.",
        items=dc_items,
    ))
    urls.append(dc_index)

    # Title 18 full-text routes.
    title18_items = []
    for item in title18_index["sections"]:
        number = str(item["section"])
        detail_name = item["details_url"].rsplit("/", 1)[-1]
        detail = load(api / "title18" / detail_name)
        relative = f"criminal/title18/{quote(number, safe='')}"
        canonical = BASE_URL + relative + "/"
        status = item.get("status", "current")
        meta = [status.title()]
        chapter = item.get("chapter") or {}
        if chapter.get("number"):
            meta.append(f"Chapter {chapter['number']}: {chapter.get('heading','')}")
        page = section_page(
            citation=item["citation"],
            heading=item["heading"],
            text=detail.get("text", ""),
            source="Title 18 — Crimes and Criminal Procedure",
            canonical=canonical,
            meta=meta,
            source_link=item.get("cite_url"),
        )
        url = write_page(site, relative, page)
        urls.append(url)
        title18_items.append((item["citation"], item["heading"], url))

    title18_root = BASE_URL + "criminal/title18/"
    write_page(site, "criminal/title18", list_page(
        title="Title 18 — Crimes and Criminal Procedure",
        description="Permanent full-text index of Title 18 sections used by the criminal-law reference.",
        canonical=title18_root,
        eyebrow="United States Code",
        intro="Full-text permanent pages generated from the repository’s Title 18 USLM source. Repealed, omitted, and transferred sections remain available as historical statutory records but are excluded from the booking charge catalog.",
        items=title18_items,
    ))
    urls.append(title18_root)

    # Source public-law sections.
    pl_root_items = []
    for doc in documents["documents"]:
        law_number = doc["citation"].replace("Public Law ", "")
        law_slug = law_number.replace("-", "-")
        section_items = []
        for sec in doc["sections"]:
            number = str(sec["number"])
            relative = f"criminal/public-law/{law_slug}/{quote(number, safe='')}"
            canonical = BASE_URL + relative + "/"
            page = section_page(
                citation=f"{doc['citation']} § {number}",
                heading=sec["heading"],
                text=sec["text"],
                source=doc["title"],
                canonical=canonical,
                source_link=doc.get("public_law_url"),
            )
            url = write_page(site, relative, page)
            urls.append(url)
            section_items.append((f"§ {number}", sec["heading"], url))
        law_root = BASE_URL + f"criminal/public-law/{law_slug}/"
        write_page(site, f"criminal/public-law/{law_slug}", list_page(
            title=doc["citation"] + " — " + doc["title"],
            description=f"Permanent section index for {doc['citation']}, {doc['title']}.",
            canonical=law_root,
            eyebrow=doc["citation"],
            intro="Structured source text used by the criminal-law reference and API.",
            items=section_items,
        ))
        urls.append(law_root)
        pl_root_items.append((doc["citation"], doc["title"], law_root))

    public_law_root = BASE_URL + "criminal/public-law/"
    write_page(site, "criminal/public-law", list_page(
        title="Criminal-law source enactments",
        description="Permanent indexes for Public Laws 36-260, 37-261, and 39-267.",
        canonical=public_law_root,
        eyebrow="Source Enactments",
        intro="These enactments establish the local federal criminal-code lineage and current non-court sentencing rules.",
        items=pl_root_items,
    ))
    urls.append(public_law_root)

    root_items = [
        ("Federal Criminal Code", "Public Law 37-261 attached code", fcc_index),
        ("Title 18 U.S.C.", "Crimes and Criminal Procedure", title18_root),
        ("Federalized D.C. Criminal Code", "Public Law 36-260 § 10(b) source lineage", dc_index),
        ("Source enactments", "Public Laws 36-260, 37-261, and 39-267", public_law_root),
        ("Sentencing API", "Public Law 39-267 plus separately exposed Federal Criminal Code class schedule", API_BASE_SENTENCING),
    ]
    criminal_root = BASE_URL + "criminal/"
    write_page(site, "criminal", list_page(
        title="Criminal Law Permanent Index",
        description="Static, crawlable index for Title 18, the Federal Criminal Code, the federalized D.C. Criminal Code, and source enactments.",
        canonical=criminal_root,
        eyebrow="Permanent Legal Index",
        intro="Use the interactive Criminal Law Search for fast research, or follow these permanent pages for stable citations and full text without JavaScript.",
        items=root_items,
    ))
    urls.append(criminal_root)

    # Dedicated criminal-law sitemap, deliberately well below the 50,000 URL limit.
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in [BASE_URL, BASE_URL + "criminal-law.html", BASE_URL + "public-laws.html", *urls]:
        sitemap.append(f"  <url><loc>{html.escape(url)}</loc></url>")
    sitemap.append("</urlset>")
    (site / "sitemap-criminal.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")
    (site / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: " + BASE_URL + "sitemap-criminal.xml\n",
        encoding="utf-8",
    )

    # Build-level verification.
    required = [
        site / "criminal" / "fcc" / "201" / "index.html",
        site / "criminal" / "dc" / "102" / "index.html",
        site / "criminal" / "title18" / "1111" / "index.html",
        site / "criminal" / "public-law" / "39-267" / "6" / "index.html",
        site / "sitemap-criminal.xml",
        site / "robots.txt",
    ]
    for path in required:
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"Missing generated criminal-law route: {path}")

    d102 = (site / "criminal" / "dc" / "102" / "index.html").read_text(encoding="utf-8")
    if "United States Attorney" not in d102:
        raise SystemExit("Federalized D.C. § 102 page is missing the PL 36-260 integration amendment")
    print(f"Generated {len(urls)} permanent criminal-law URLs and sitemap-criminal.xml")


API_BASE_SENTENCING = BASE_URL + "data/api/v1/criminal-law/sentencing.json"

if __name__ == "__main__":
    main()
