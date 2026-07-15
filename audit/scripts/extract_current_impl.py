#!/usr/bin/env python3
"""Phase 1b: Extract every USAR codification note/section already injected into usc/*.xml.

Produces audit/current-implementation.json keyed by public-law number, plus a flat list.
Captures: file, note id, PL number, heading, placement (nearest enclosing identifier),
presence of quotedContent full-text dump, trello/archive links, sha reference,
declared status/codification language, and note length. Also flags duplicates.
"""
import json, os, re, glob

ROOT = r"D:/us-code"
USC = os.path.join(ROOT, "usc")
OUT = os.path.join(ROOT, "audit", "current-implementation.json")

# Injected note start: <note ... id="rp-plNNNMMM-codification" ...>
NOTE_START = re.compile(r'<note\b[^>]*\bid="(rp-pl(\d{3})(\d{3})[^"]*)"[^>]*>')
IDENT = re.compile(r'\bidentifier="(/us/usc/[^"]+)"')
HEADING = re.compile(r'<heading[^>]*>(.*?)</heading>', re.DOTALL)
TRELLO = re.compile(r'https://trello\.com/[^\s<"]+')
SHA = re.compile(r'SHA-?256\s+([0-9a-fA-F]{64})')
QUOTED = re.compile(r'<quotedContent\b', re.IGNORECASE)
PLNUM = re.compile(r'Pub\.?\s*L\.?\s*(\d+)[–—-](\d+)')

def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

def find_enclosing_identifier(text, pos):
    """Nearest identifier= before pos that belongs to a structural element (section/chapter/title)."""
    best = None
    for m in IDENT.finditer(text, 0, pos):
        best = m.group(1)
    return best

def main():
    all_notes = []
    for path in sorted(glob.glob(os.path.join(USC, "usc*.xml"))):
        fname = os.path.basename(path)
        text = open(path, encoding="utf-8", errors="replace").read()
        for m in NOTE_START.finditer(text):
            start = m.start()
            note_id = m.group(1)
            congress = int(m.group(2))
            seq = int(m.group(3))
            end = text.find("</note>", m.end())
            body = text[m.end():end] if end != -1 else text[m.end():m.end()+4000]
            full = text[start: (end + len("</note>")) if end != -1 else start+4000]
            hm = HEADING.search(full)
            heading = strip_tags(hm.group(1)) if hm else ""
            # id-derived congress-seq is authoritative; heading citation kept separately
            pl = f"{congress}-{seq}"
            plm = PLNUM.search(heading)
            heading_cited_pl = f"{plm.group(1)}-{plm.group(2)}" if plm else None
            placement = find_enclosing_identifier(text, start)
            trello = TRELLO.findall(full)
            shas = SHA.findall(full)
            has_quoted = bool(QUOTED.search(full))
            # crude status-language capture
            status_line = ""
            sm = re.search(r'<b>\s*Status\.?\s*</b>\s*([^<]+)', full)
            if sm:
                status_line = sm.group(1).strip()
            codif_line = ""
            cm = re.search(r'<b>\s*Codification\.?\s*</b>\s*([^<]+)', full)
            if cm:
                codif_line = cm.group(1).strip()
            all_notes.append({
                "file": fname,
                "note_id": note_id,
                "public_law": pl,
                "congress_from_id": congress,
                "seq_from_id": seq,
                "heading_cited_pl": heading_cited_pl,
                "heading": heading,
                "placement_identifier": placement,
                "declared_status": status_line,
                "declared_codification": codif_line,
                "has_quoted_content_dump": has_quoted,
                "trello_links": trello,
                "sha_references": shas,
                "note_char_length": len(full),
            })

    # group by PL
    by_pl = {}
    for n in all_notes:
        by_pl.setdefault(n["public_law"], []).append(n)

    duplicates = {pl: [n["file"] for n in ns] for pl, ns in by_pl.items() if len(ns) > 1}
    with_dump = [n["note_id"] for n in all_notes if n["has_quoted_content_dump"]]
    with_trello = [n["note_id"] for n in all_notes if n["trello_links"]]

    summary = {
        "total_injected_notes": len(all_notes),
        "distinct_public_laws_represented": len(by_pl),
        "notes_with_fulltext_dump": len(with_dump),
        "notes_with_trello_link": len(with_trello),
        "duplicate_public_laws": duplicates,
        "files_touched": sorted({n["file"] for n in all_notes}),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"summary": summary, "by_public_law": by_pl, "notes": all_notes},
              open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2)[:2000])

if __name__ == "__main__":
    main()
