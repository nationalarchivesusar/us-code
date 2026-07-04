from __future__ import annotations

import csv
import datetime as dt
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from .common import law_sort_key, write_json
from .model import LawAnalysis, LawCard, SourceRecord


WEBSITE_BASE = "https://nationalarchivesusar.github.io/us-code"


def _escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def build_trello_comment(analysis: LawAnalysis, card: LawCard, source: SourceRecord) -> str:
    marker = f"[USC-CODIFICATION:{analysis.law_id}:{(analysis.source_sha256 or 'NO-SOURCE')[:12]}]"
    lines = [marker, "", f"**U.S. Code codification disposition: {analysis.disposition.replace('_', ' ').title()}**", ""]
    lines.append(analysis.rationale)
    lines.append("")
    if analysis.operations:
        lines.append("**Code treatment**")
        for operation in analysis.operations:
            target = ""
            if operation.title and operation.section:
                target = f"{operation.title} U.S.C. § {operation.section}"
            elif operation.title:
                target = f"Title {operation.title}"
            lines.append(
                f"- `{operation.kind}`{f' at {target}' if target else ''} — "
                f"{operation.rationale}"
            )
    elif analysis.already_incorporated_locations:
        lines.append("**Verified existing locations**")
        for location in analysis.already_incorporated_locations:
            lines.append(f"- `{location}`")
    else:
        lines.append("No Code text was changed for this law.")

    links = analysis.citation_links
    if links:
        lines += ["", "**Public Code citations**"]
        for link in links:
            lines.append(f"- {link}")

    lines += ["", "**Source record**"]
    lines.append(f"- Trello card: {card.url}")
    if source.selected_url:
        lines.append(f"- Enactment source: {source.selected_url}")
    if source.sha256:
        lines.append(f"- Source SHA-256: `{source.sha256}`")
    lines.append("- Repository commit: https://github.com/nationalarchivesusar/us-code/commit/{{COMMIT_SHA}}")
    lines.append("- Local audit report: `codification/mass_migration/latest/reports/MASTER-CODIFICATION-REPORT.md`")
    return "\n".join(lines)


def write_all_reports(
    workspace: Path,
    cards: dict[str, LawCard],
    sources: dict[str, SourceRecord],
    analyses: list[LawAnalysis],
    manifest: dict | None = None,
) -> dict[str, str]:
    report_root = workspace / "reports"
    laws_root = report_root / "laws"
    plans_root = workspace / "plans"
    report_root.mkdir(parents=True, exist_ok=True)
    laws_root.mkdir(parents=True, exist_ok=True)
    plans_root.mkdir(parents=True, exist_ok=True)

    analyses = sorted(analyses, key=lambda item: law_sort_key(item.law_id))
    counts = Counter(analysis.disposition for analysis in analyses)
    source_errors = sum(1 for analysis in analyses if analysis.disposition == "SOURCE_UNAVAILABLE")
    applied = sum(1 for analysis in analyses if analysis.applied)

    inventory_csv = report_root / "MASTER-INVENTORY.csv"
    fields = [
        "law_id", "title", "status", "disposition", "confidence", "card_url",
        "source_url", "source_sha256", "source_characters", "target_title",
        "target_section", "operation_count", "applied", "changed_files",
        "citation_links", "rationale", "warnings",
    ]
    with inventory_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for analysis in analyses:
            writer.writerow(
                {
                    "law_id": analysis.law_id,
                    "title": analysis.title,
                    "status": analysis.status,
                    "disposition": analysis.disposition,
                    "confidence": analysis.confidence,
                    "card_url": analysis.card_url,
                    "source_url": analysis.source_url,
                    "source_sha256": analysis.source_sha256,
                    "source_characters": analysis.source_characters,
                    "target_title": analysis.target_title or "",
                    "target_section": analysis.target_section,
                    "operation_count": len(analysis.operations),
                    "applied": analysis.applied,
                    "changed_files": " | ".join(analysis.changed_files),
                    "citation_links": " | ".join(analysis.citation_links),
                    "rationale": analysis.rationale,
                    "warnings": " | ".join(analysis.warnings),
                }
            )

    source_audit_csv = report_root / "SOURCE-AUDIT.csv"
    with source_audit_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        fields_source = [
            "law_id", "title", "status", "selected_name", "selected_url",
            "source_sha256", "characters", "score", "identity_matches",
            "warnings", "error", "candidate_count",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields_source)
        writer.writeheader()
        for analysis in analyses:
            source = sources.get(analysis.law_id, SourceRecord(law_id=analysis.law_id))
            writer.writerow(
                {
                    "law_id": analysis.law_id,
                    "title": analysis.title,
                    "status": analysis.status,
                    "selected_name": source.selected_name,
                    "selected_url": source.selected_url,
                    "source_sha256": source.sha256,
                    "characters": source.characters,
                    "score": source.score,
                    "identity_matches": " | ".join(source.identity_matches),
                    "warnings": " | ".join(source.warnings),
                    "error": source.error,
                    "candidate_count": len(source.candidates),
                }
            )

    operations_csv = report_root / "OPERATION-REGISTER.csv"
    with operations_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        fields_operation = [
            "law_id", "title", "disposition", "operation_index", "kind",
            "target_title", "target_section", "target_identifier", "confidence",
            "execution_status", "citation_url", "changed_files", "rationale", "warnings",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields_operation)
        writer.writeheader()
        for analysis in analyses:
            if not analysis.operations:
                writer.writerow(
                    {
                        "law_id": analysis.law_id, "title": analysis.title,
                        "disposition": analysis.disposition, "operation_index": 0,
                        "kind": "NO_CODE_OPERATION", "changed_files": " | ".join(analysis.changed_files),
                        "rationale": analysis.rationale,
                    }
                )
                continue
            for index, operation in enumerate(analysis.operations, 1):
                writer.writerow(
                    {
                        "law_id": analysis.law_id,
                        "title": analysis.title,
                        "disposition": analysis.disposition,
                        "operation_index": index,
                        "kind": operation.kind,
                        "target_title": operation.title or "",
                        "target_section": operation.section,
                        "target_identifier": operation.target_identifier,
                        "confidence": operation.confidence,
                        "execution_status": operation.status,
                        "citation_url": operation.citation_url,
                        "changed_files": " | ".join(analysis.changed_files),
                        "rationale": operation.rationale,
                        "warnings": " | ".join(operation.warnings),
                    }
                )

    locations_csv = report_root / "CODE-LOCATION-REGISTER.csv"
    with locations_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        fields_location = [
            "law_id", "title", "disposition", "location_type", "title_number",
            "section", "identifier", "public_citation", "changed_file",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields_location)
        writer.writeheader()
        for analysis in analyses:
            wrote = False
            for operation in analysis.operations:
                if not operation.title or not operation.section:
                    continue
                writer.writerow(
                    {
                        "law_id": analysis.law_id, "title": analysis.title,
                        "disposition": analysis.disposition, "location_type": operation.kind,
                        "title_number": operation.title, "section": operation.section,
                        "identifier": operation.output_identifier or operation.target_identifier,
                        "public_citation": operation.citation_url,
                        "changed_file": f"usc/usc{int(operation.title):02d}.xml",
                    }
                )
                wrote = True
            for identifier in analysis.already_incorporated_locations:
                parts = identifier.split("/s", 1)
                title_match = identifier.split("/t", 1)[-1].split("/", 1)[0] if "/t" in identifier else ""
                section_value = parts[1] if len(parts) == 2 else ""
                writer.writerow(
                    {
                        "law_id": analysis.law_id, "title": analysis.title,
                        "disposition": analysis.disposition, "location_type": "EXISTING",
                        "title_number": title_match, "section": section_value,
                        "identifier": identifier,
                        "public_citation": next((link for link in analysis.citation_links if f"/{section_value}/" in link), ""),
                        "changed_file": f"usc/usc{int(title_match):02d}.xml" if title_match.isdigit() else "",
                    }
                )
                wrote = True
            if not wrote:
                writer.writerow(
                    {
                        "law_id": analysis.law_id, "title": analysis.title,
                        "disposition": analysis.disposition, "location_type": "NO_CODE_LOCATION",
                    }
                )

    write_json(
        report_root / "MASTER-INVENTORY.json",
        {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "summary": {
                "total": len(analyses),
                "applied": applied,
                "source_unavailable": source_errors,
                "dispositions": dict(counts),
            },
            "laws": [analysis.to_dict() for analysis in analyses],
        },
    )

    dependencies = []
    for analysis in analyses:
        dependencies.extend(dependency.to_dict() for dependency in analysis.dependencies)
    write_json(report_root / "DEPENDENCY-GRAPH.json", {"edges": dependencies})

    lines = [
        "# Master Public-Law Codification Report",
        "",
        f"Generated: `{dt.datetime.now(dt.timezone.utc).isoformat()}`",
        "",
        "## Executive summary",
        "",
        f"- Canonical public-law records analyzed: **{len(analyses)}**",
        f"- Laws producing Code changes in this run: **{applied}**",
        f"- Laws already incorporated: **{counts.get('ALREADY_INCORPORATED', 0)}**",
        f"- Freestanding statutory notes: **{counts.get('STATUTORY_NOTE', 0)}**",
        f"- Direct or hybrid amendments: **{counts.get('DIRECT_CODE_AMENDMENT', 0) + counts.get('HYBRID_DIRECT_AMENDMENT_AND_STATUTORY_NOTE', 0)}**",
        f"- Non-Code enactments: **{counts.get('NON_CODE', 0)}**",
        f"- Repealed, failed, expired, or superseded records: **{counts.get('NONOPERATIVE_OR_REPEALED', 0) + counts.get('SUPERSEDED_BEFORE_CODIFICATION', 0)}**",
        f"- Sources unavailable: **{source_errors}**",
        "",
        "## Disposition standards",
        "",
        "- **Direct Code amendment:** used only when the enactment identifies an existing title and section and the operation is uniquely executable.",
        "- **New Code section:** used only when the enactment expressly adds a numbered section to a named U.S. Code chapter.",
        "- **Statutory note:** used for general and permanent law lacking a safe positive-law placement, or to preserve unresolved amendatory language without corrupting Code text.",
        "- **Non-Code:** used for constitutional amendments, concrete appropriations, appointments, treaty ratifications, commemorative or private measures, and similar enactments not normally codified.",
        "- **No revival:** repealed, rescinded, expired, failed, and superseded laws are inventoried but not inserted as current law.",
        "",
        "## Disposition counts",
        "",
    ]
    for disposition, count in sorted(counts.items()):
        lines.append(f"- `{disposition}`: {count}")

    lines += [
        "",
        "## Master table",
        "",
        "| Public law | Title | Status | Disposition | Code location | Confidence |",
        "|---|---|---|---|---|---|",
    ]
    for analysis in analyses:
        locations = []
        for operation in analysis.operations:
            if operation.title and operation.section:
                locations.append(f"{operation.title} U.S.C. § {operation.section}")
        if not locations:
            locations = analysis.already_incorporated_locations
        lines.append(
            f"| [{analysis.law_id}]({analysis.card_url}) | {_escape_md(analysis.title)} | "
            f"{analysis.status} | `{analysis.disposition}` | {_escape_md('; '.join(locations) or '—')} | {analysis.confidence} |"
        )

    lines += ["", "## Per-law memoranda", ""]
    for analysis in analyses:
        lines.append(f"- [`{analysis.law_id}`](laws/{analysis.law_id}.md) — {analysis.title}")
    (report_root / "MASTER-CODIFICATION-REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    comments_payload = []
    comments_md = ["# Trello-ready codification comments", ""]
    for analysis in analyses:
        card = cards[analysis.law_id]
        source = sources.get(analysis.law_id, SourceRecord(law_id=analysis.law_id))
        comment = build_trello_comment(analysis, card, source)
        analysis.trello_comment = comment
        comments_payload.append(
            {
                "law_id": analysis.law_id,
                "card_id": card.card_id,
                "card_short_link": card.short_link,
                "card_url": card.url,
                "comment": comment,
                "marker": comment.splitlines()[0],
                "record_type": "canonical",
            }
        )
        comments_md += [f"## {analysis.law_id} — {analysis.title}", "", comment, ""]
        for duplicate in card.duplicate_card_records:
            duplicate_notice = (
                comment.splitlines()[0]
                + "\n\n**Duplicate public-law card.** This archive card duplicates the canonical "
                + f"record at {card.url}. The codification disposition below applies to this law number.\n\n"
                + "\n".join(comment.splitlines()[2:])
            )
            comments_payload.append(
                {
                    "law_id": analysis.law_id,
                    "card_id": duplicate.get("card_id", ""),
                    "card_short_link": duplicate.get("short_link", ""),
                    "card_url": duplicate.get("card_url", ""),
                    "comment": duplicate_notice,
                    "marker": comment.splitlines()[0],
                    "record_type": "duplicate",
                    "canonical_card_url": card.url,
                }
            )
            comments_md += [
                f"### Duplicate card — {duplicate.get('card_name', duplicate.get('card_id', 'unknown'))}",
                "", duplicate_notice, ""
            ]
        comments_md += ["---", ""]

        memo = [
            f"# {analysis.law_id} — {analysis.title}",
            "",
            "## Final disposition",
            "",
            f"- Status: `{analysis.status}`",
            f"- Disposition: `{analysis.disposition}`",
            f"- Confidence: `{analysis.confidence}`",
            f"- Trello card: {analysis.card_url}",
            f"- Trello list: `{card.list_name}`",
            f"- Trello labels: {', '.join(card.labels) or 'none'}",
            f"- Status evidence: {'; '.join(card.status_evidence) or 'none recorded'}",
            f"- Duplicate card IDs: {', '.join(card.duplicate_card_ids) or 'none'}",
            f"- Duplicate card URLs: {', '.join(item.get('card_url', '') for item in card.duplicate_card_records) or 'none'}",
            f"- Source: {analysis.source_url or 'unavailable'}",
            f"- Source name: {source.selected_name or 'unavailable'}",
            f"- Source SHA-256: `{analysis.source_sha256 or 'unavailable'}`",
            f"- Source characters: {source.characters}",
            f"- Source-selection score: {source.score}",
            f"- Source identity matches: {', '.join(source.identity_matches) or 'none'}",
            f"- Source candidates evaluated: {len(source.candidates)}",
            "",
            "## Legal and editorial rationale",
            "",
            analysis.rationale,
            "",
            "## Subject and character analysis",
            "",
            f"- Subject tags: {', '.join(analysis.subject_tags) or 'none'}",
            f"- Permanent-law score: {analysis.permanent_score}",
            f"- Temporary-law score: {analysis.temporary_score}",
            f"- Non-Code score: {analysis.non_code_score}",
            f"- Direct-amendment score: {analysis.direct_amendment_score}",
            "",
            "## Express U.S. Code citations detected",
            "",
            *([f"- `{citation.title} U.S.C. § {citation.section}` — {citation.raw}" for citation in analysis.citations] or ["No express Code citation was detected."]),
            "",
            "## Operations",
            "",
        ]
        if analysis.operations:
            for index, operation in enumerate(analysis.operations, 1):
                memo += [
                    f"### Operation {index}: `{operation.kind}`",
                    "",
                    f"- Target: `{operation.target_identifier or 'none'}`",
                    f"- Confidence: `{operation.confidence}`",
                    f"- Execution status: `{operation.status}`",
                    f"- Rationale: {operation.rationale}",
                    f"- Public citation: {operation.citation_url or 'generated after application'}",
                    "",
                ]
                if operation.warnings:
                    memo += ["Warnings:", *[f"- {warning}" for warning in operation.warnings], ""]
        else:
            memo += ["No Code operation was authorized.", ""]

        if analysis.dependencies:
            memo += ["## Dependencies and later-law effects", ""]
            for dependency in analysis.dependencies:
                memo.append(
                    f"- `{dependency.relation}` `{dependency.target_law_id}` ({dependency.confidence}): "
                    f"{dependency.evidence}"
                )
            memo.append("")
        if source.candidates:
            memo += ["## Source candidate audit", ""]
            for index, candidate in enumerate(source.candidates, 1):
                memo += [
                    f"### Candidate {index}: {candidate.get('name') or candidate.get('path') or 'unnamed'}",
                    "",
                    f"- URL: {candidate.get('source_url') or 'none'}",
                    f"- Characters: {candidate.get('characters', 0)}",
                    f"- Score: {candidate.get('score', 'unscored')}",
                    f"- Identity matches: {', '.join(candidate.get('identity_matches', [])) or 'none'}",
                    f"- Warnings: {'; '.join(candidate.get('warnings', [])) or 'none'}",
                    "",
                ]
        if analysis.warnings:
            memo += ["## Warnings", "", *[f"- {warning}" for warning in analysis.warnings], ""]
        (laws_root / f"{analysis.law_id}.md").write_text("\n".join(memo) + "\n", encoding="utf-8")
        write_json(plans_root / f"{analysis.law_id}.json", analysis.to_dict())

    write_json(report_root / "TRELLO-COMMENTS.json", {"comments": comments_payload})
    (report_root / "TRELLO-COMMENTS.md").write_text("\n".join(comments_md) + "\n", encoding="utf-8")

    unresolved = [analysis for analysis in analyses if analysis.disposition in {"SOURCE_UNAVAILABLE"} or analysis.warnings]
    unresolved_lines = ["# Unresolved and warning register", ""]
    if unresolved:
        for analysis in unresolved:
            unresolved_lines += [
                f"## {analysis.law_id} — {analysis.title}",
                "",
                f"- Disposition: `{analysis.disposition}`",
                f"- Warnings: {'; '.join(analysis.warnings) or 'source unavailable'}",
                f"- Card: {analysis.card_url}",
                "",
            ]
    else:
        unresolved_lines.append("No unresolved sources or warnings were recorded.")
    (report_root / "UNRESOLVED-REGISTER.md").write_text("\n".join(unresolved_lines) + "\n", encoding="utf-8")

    overrides = [
        analysis
        for analysis in analyses
        if any(dep.relation in {"repeals", "supersedes", "overrides", "amends"} for dep in analysis.dependencies)
        or analysis.disposition == "SUPERSEDED_BEFORE_CODIFICATION"
    ]
    override_lines = ["# Overrides, amendments, repeals, and supersession register", ""]
    for analysis in overrides:
        override_lines += [f"## {analysis.law_id} — {analysis.title}", ""]
        if analysis.dependencies:
            for dep in analysis.dependencies:
                override_lines.append(f"- `{dep.relation}` `{dep.target_law_id}`: {dep.evidence}")
        else:
            override_lines.append(f"- {analysis.rationale}")
        override_lines.append("")
    (report_root / "OVERRIDES-AND-REPEALS.md").write_text("\n".join(override_lines) + "\n", encoding="utf-8")

    register_specs = [
        (
            "NON-CODE-REGISTER.md",
            "Non-Code public laws",
            [analysis for analysis in analyses if analysis.disposition == "NON_CODE"],
        ),
        (
            "NONOPERATIVE-REGISTER.md",
            "Repealed, rescinded, expired, failed, and superseded laws",
            [analysis for analysis in analyses if analysis.disposition in {"NONOPERATIVE_OR_REPEALED", "SUPERSEDED_BEFORE_CODIFICATION"}],
        ),
        (
            "ALREADY-INCORPORATED-REGISTER.md",
            "Public laws already present in the Code",
            [analysis for analysis in analyses if analysis.disposition == "ALREADY_INCORPORATED"],
        ),
    ]
    for filename, heading, entries in register_specs:
        register = [f"# {heading}", ""]
        if not entries:
            register.append("No laws received this disposition.")
        for analysis in entries:
            register += [
                f"## {analysis.law_id} — {analysis.title}",
                "",
                f"- Card: {analysis.card_url}",
                f"- Disposition: `{analysis.disposition}`",
                f"- Rationale: {analysis.rationale}",
                f"- Code locations: {', '.join(analysis.already_incorporated_locations or analysis.citation_links) or 'none'}",
                "",
            ]
        (report_root / filename).write_text("\n".join(register) + "\n", encoding="utf-8")

    duplicate_register = ["# Duplicate Trello card register", ""]
    duplicate_count = 0
    for analysis in analyses:
        card = cards[analysis.law_id]
        if not card.duplicate_card_records:
            continue
        duplicate_count += len(card.duplicate_card_records)
        duplicate_register += [
            f"## {analysis.law_id} — {analysis.title}",
            "",
            f"- Canonical card: {card.url}",
            f"- Final disposition: `{analysis.disposition}`",
        ]
        for duplicate in card.duplicate_card_records:
            duplicate_register.append(
                f"- Duplicate: {duplicate.get('card_url', '')} — "
                f"{duplicate.get('card_name', '')} "
                f"(list `{duplicate.get('list_name', '')}`, inferred status `{duplicate.get('status', '')}`)"
            )
        duplicate_register.append("")
    if not duplicate_count:
        duplicate_register.append("No duplicate public-law cards were identified.")
    (report_root / "DUPLICATE-CARD-REGISTER.md").write_text(
        "\n".join(duplicate_register) + "\n", encoding="utf-8"
    )

    _write_dashboard(report_root / "MASTER-DASHBOARD.html", analyses)

    return {
        "master_report": str(report_root / "MASTER-CODIFICATION-REPORT.md"),
        "inventory_csv": str(inventory_csv),
        "source_audit_csv": str(source_audit_csv),
        "operations_csv": str(operations_csv),
        "locations_csv": str(locations_csv),
        "comments": str(report_root / "TRELLO-COMMENTS.md"),
        "dashboard": str(report_root / "MASTER-DASHBOARD.html"),
    }


def _write_dashboard(path: Path, analyses: list[LawAnalysis]) -> None:
    rows = []
    for analysis in analyses:
        location = ", ".join(
            f"{operation.title} U.S.C. § {operation.section}"
            for operation in analysis.operations
            if operation.title and operation.section
        )
        rows.append(
            "<tr>"
            f"<td><a href='{html.escape(analysis.card_url)}'>{html.escape(analysis.law_id)}</a></td>"
            f"<td>{html.escape(analysis.title)}</td>"
            f"<td>{html.escape(analysis.status)}</td>"
            f"<td>{html.escape(analysis.disposition)}</td>"
            f"<td>{html.escape(location or '—')}</td>"
            f"<td>{html.escape(analysis.confidence)}</td>"
            f"<td>{'Yes' if analysis.applied else 'No'}</td>"
            "</tr>"
        )
    content = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>USAR Public-Law Codification Dashboard</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;margin:2rem;line-height:1.45}}
input{{padding:.65rem;width:min(40rem,90%);margin-bottom:1rem}}
table{{border-collapse:collapse;width:100%;font-size:.92rem}}
th,td{{border:1px solid #ccc;padding:.45rem;vertical-align:top;text-align:left}}
th{{position:sticky;top:0;background:#f3f3f3}}
tr:nth-child(even){{background:#fafafa}}
</style>
</head>
<body>
<h1>USAR Public-Law Codification Dashboard</h1>
<p>{len(analyses)} canonical law records.</p>
<input id='filter' placeholder='Filter by law, title, status, disposition, or location'>
<table id='laws'>
<thead><tr><th>Law</th><th>Title</th><th>Status</th><th>Disposition</th><th>Location</th><th>Confidence</th><th>Applied</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<script>
const input=document.getElementById('filter');
input.addEventListener('input',()=>{{const q=input.value.toLowerCase();for(const row of document.querySelectorAll('#laws tbody tr')){{row.hidden=!row.textContent.toLowerCase().includes(q);}}}});
</script>
</body></html>"""
    path.write_text(content, encoding="utf-8")
