#!/usr/bin/env python3
"""Phase 2 setup: split 270 laws into 9 numeric batches of 30 and write self-contained manifests.

Each manifest embeds, per law: source-index record + current XML note(s), and the law.txt path.
Agents read law.txt directly (full source) and analyze against embedded current implementation.
"""
import json, os
ROOT = r"D:/us-code"
si = json.load(open(os.path.join(ROOT, "audit", "source-index.json"), encoding="utf-8"))
ci = json.load(open(os.path.join(ROOT, "audit", "current-implementation.json"), encoding="utf-8"))
by_pl_notes = ci["by_public_law"]

laws = sorted(si["laws"], key=lambda r: (r["congress"], r["sequence"]))
assert len(laws) == 270

os.makedirs(os.path.join(ROOT, "audit", "manifests"), exist_ok=True)
for b in range(9):
    chunk = laws[b*30:(b+1)*30]
    items = []
    for r in chunk:
        law_txt = os.path.join("codification", "laws", "laws", r["law_id"], "law.txt")
        items.append({
            "law_id": r["law_id"],
            "public_law": r["public_law"],
            "title": r["title"],
            "list_name": r["list_name"],
            "source_status": r["source_status"],
            "source_reason": r["source_reason"],
            "law_txt_path": law_txt.replace("\\", "/"),
            "text_extracted": r["text_extracted"],
            "text_length": r["text_length"],
            "image_only_or_scanned": r["image_only_or_scanned"],
            "html_or_viewer_debris": r["html_or_viewer_debris"],
            "source_files": r["source_files"],
            "detected_code_citations": r["code_citations"],
            "detected_pl_references": r["pl_references"],
            "detected_operative_language": r["operative_language"],
            "current_xml_notes": by_pl_notes.get(r["public_law"], []),
        })
    manifest = {
        "batch": b+1,
        "auditor": f"law-auditor-{b+1:02d}",
        "report_path": f"audit/primary/batch-{b+1:02d}.json",
        "law_count": len(items),
        "laws": items,
    }
    p = os.path.join(ROOT, "audit", "manifests", f"batch-{b+1:02d}.json")
    json.dump(manifest, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"batch-{b+1:02d}: {len(items)} laws  {chunk[0]['public_law']}..{chunk[-1]['public_law']}")
