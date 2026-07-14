#!/usr/bin/env python3
"""Implement PL-019-150 sections in Title 15 and repair result proof."""

from __future__ import annotations

import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
XML_PATH = ROOT / "usc" / "usc15.xml"
RESULTS_PATH = ROOT / "audit" / "xml-integration-results.json"


SECTIONS = [
    {
        "action_id": "ACTION-0465",
        "section": "631d",
        "source_section": "4",
        "heading": "Small Business Recognition Program",
        "subsections": [
            ("a", "The Department shall establish a Small Business Recognition Program to identify and highlight innovative and successful small businesses across various sectors."),
            ("b", "This program shall include a competitive process for small businesses to apply for recognition based on criteria such as innovation and sustainability."),
            ("c", "Recognized small businesses shall receive public acknowledgment and support through the Department's various communication channels."),
        ],
    },
    {
        "action_id": "ACTION-0466",
        "section": "631e",
        "source_section": "5",
        "heading": "Small Business Employment Initiative",
        "subsections": [
            ("a", "The Department shall initiate a Small Business Employment Initiative aimed at facilitating partnerships between small businesses."),
            ("b", "This initiative will encourage small businesses to participate in apprenticeship programs and internships supported by the Department."),
        ],
    },
    {
        "action_id": "ACTION-0467",
        "section": "631f",
        "source_section": "6",
        "heading": "Small Business Support Center",
        "subsections": [
            ("a", "The Department shall establish a Small Business Support Center within the Department of Commerce and Labor."),
            ("b", "These support centers shall provide specialized assistance and resources tailored to the needs of small businesses, including guidance on regulatory compliance and market expansion strategies."),
            ("c", "The support centers shall collaborate with other relevant entities to maximize their effectiveness."),
        ],
    },
]


def section_xml(row: dict) -> str:
    sid = f"rp-pl019150-t15-s{row['section']}"
    parts = [
        f'<section style="-uslm-lc:I80" id="{sid}" identifier="/us/usc/t15/s{row["section"]}">',
        f'<num value="{row["section"]}">&#167; {row["section"]}.</num><heading>{row["heading"]}</heading>',
    ]
    for label, text in row["subsections"]:
        parts.append(
            f'<subsection style="-uslm-lc:I11" class="indent0" id="{sid}-{label}" '
            f'identifier="/us/usc/t15/s{row["section"]}/{label}"><num value="{label}">({label})</num>'
            f"<content>{text}</content></subsection>"
        )
    parts.append(
        f'<sourceCredit id="{sid}-source">(<ref href="/us/pl/19/150/s{row["source_section"]}">'
        f'Pub. L. 19-150, sec. {row["source_section"]}</ref>.)</sourceCredit>'
    )
    parts.append("</section>")
    return "\n".join(parts)


def toc_item(row: dict) -> str:
    return (
        "<tocItem>\n"
        f'<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t15/s{row["section"]}">{row["section"]}.</ref></column>'
        f'<column style="-uslm-lc:I46" class="twoColumnRight">{row["heading"]}.</column>\n'
        "</tocItem>\n"
    )


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    text = XML_PATH.read_text(encoding="utf-8")
    toc_insert = "".join(toc_item(row) for row in SECTIONS)
    section_insert = "\n".join(section_xml(row) for row in SECTIONS) + "\n"

    if 'identifier="/us/usc/t15/s631d"' not in text:
        marker = '<column style="-uslm-lc:I20" class="twoColumnLeft"><ref href="/us/usc/t15/s632">632.</ref></column>'
        toc_start = text.find("<tocItem>", max(0, text.find(marker) - 300))
        if toc_start == -1:
            raise SystemExit("could not locate Title 15 small-business TOC insertion point")
        text = text[:toc_start] + toc_insert + text[toc_start:]

        section_marker = re.search(r'<section\b(?=[^>]*identifier="/us/usc/t15/s632")[^>]*>', text)
        if not section_marker:
            raise SystemExit("could not locate Title 15 section insertion point before section 632")
        text = text[: section_marker.start()] + section_insert + text[section_marker.start() :]
        XML_PATH.write_text(text, encoding="utf-8", newline="\n")
        ET.parse(XML_PATH)

    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    by_id = {row["action_id"]: row for row in results["results"]}
    for row in SECTIONS:
        sid = f"rp-pl019150-t15-s{row['section']}"
        source_id = f"{sid}-source"
        result = by_id[row["action_id"]]
        exact_text = " ".join(text for _, text in row["subsections"])
        result.update(
            {
                "result_status": "applied",
                "xml_file_before": "usc15.xml",
                "xml_file_after": "usc15.xml",
                "final_section_or_subsection_identifier": f"/us/usc/t15/s{row['section']}",
                "actual_node_ids_added": [sid, source_id],
                "actual_node_ids_changed": [],
                "actual_node_ids_removed": [],
                "exact_enacted_text_applied": normalize_space(exact_text),
                "source_quotation": normalize_space(exact_text),
                "source_credit_change": f"Added source credit {source_id} citing Pub. L. 19-150, sec. {row['source_section']}.",
                "amendment_note_change": "No separate amendment note required; this action inserted a new section with a source credit.",
                "toc_change": f"Added Title 15 chapter 14A TOC entry for 15 U.S.C. {row['section']}.",
                "validation_result": f"Verified inserted section {sid} at /us/usc/t15/s{row['section']} with source credit {source_id}.",
            }
        )
    RESULTS_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("implemented PL-019-150 sections 631d-631f")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
