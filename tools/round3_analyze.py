#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from common import load_registry, sha256_text

SECTION_RE = re.compile(
    r"(?im)^(?:\s*)(?:SEC(?:TION)?\.?\s*)?(\d+[A-Za-z]?)\s*[.\-—:]\s*(.*?)(?=^(?:\s*)(?:SEC(?:TION)?\.?\s*)?\d+[A-Za-z]?\s*[.\-—:]|\Z)",
    re.DOTALL
)
CITE_RE = re.compile(r"\b(\d+)\s+U\.?\s*S\.?\s*C\.?\s*(?:§+\s*)?([0-9A-Za-z.-]+)", re.I)
AMEND_RE = re.compile(r"\b(amend(?:ed|ing|ment)?|strike|insert|repeal|redesignate|add(?:ed|ing)?|codif(?:y|ied))\b", re.I)

def sections(text):
    out = {}
    for m in SECTION_RE.finditer(text):
        no = m.group(1)
        body = (m.group(2) + "\n").strip()
        out[no] = body
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    reg = load_registry(repo)
    text_root = repo / "codification" / "round3" / "sources" / "text"
    report_root = repo / "codification" / "reports"
    report_root.mkdir(parents=True, exist_ok=True)

    inventory = {"schema_version": 1, "laws": []}
    md = ["# Round 3 source inventory", ""]
    dep = ["# Round 3 dependency and net-effect report", ""]

    for law in reg["laws"]:
        path = text_root / f"{law['law_id']}.txt"
        text = path.read_text(encoding="utf-8")
        secs = sections(text)
        phrases = law["source_gates"]["phrases"]
        matches = [p for p in phrases if p.lower() in text.lower()]
        gates_pass = len(matches) >= law["source_gates"]["minimum_matches"]
        cites = sorted({f"{a} U.S.C. {b}" for a,b in CITE_RE.findall(text)})
        amendment_lines = []
        for line in text.splitlines():
            if AMEND_RE.search(line) and (CITE_RE.search(line) or "Public Law" in line or "CRACK" in line):
                amendment_lines.append(line.strip())
        entry = {
            "law_id": law["law_id"], "title": law["title"],
            "sha256": sha256_text(text), "characters": len(text),
            "sections": sorted(secs.keys(), key=lambda x: (int(re.match(r"\d+", x).group()), x)),
            "gates_passed": gates_pass, "matched_phrases": matches,
            "usc_citations": cites, "amendment_lines": amendment_lines[:100]
        }
        inventory["laws"].append(entry)
        md += [
            f"## {law['law_id']} — {law['title']}", "",
            f"- SHA-256: `{entry['sha256']}`",
            f"- Extracted characters: {len(text):,}",
            f"- Sections found: {', '.join(entry['sections']) or 'none'}",
            f"- Source gate: {'PASS' if gates_pass else 'FAIL'} ({len(matches)}/{len(phrases)} phrases)",
            f"- U.S. Code citations: {', '.join(cites) or 'none detected'}", ""
        ]
        dep += [f"## {law['law_id']} — {law['title']}", ""]
        for k in law.get("known_effects", []):
            dep.append(f"- {k}")
        dep += [
            f"- Dependencies: {', '.join(law.get('dependencies', [])) or 'none'}",
            f"- Candidate treatment: `{law.get('candidate_classification', {}).get('method', 'none')}`",
            ""
        ]

        secdir = repo / "codification" / "round3" / "sections" / law["law_id"]
        secdir.mkdir(parents=True, exist_ok=True)
        for no, body in secs.items():
            (secdir / f"section-{no}.txt").write_text(body + "\n", encoding="utf-8")

    (report_root / "round3-source-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    (report_root / "round3-source-inventory.md").write_text("\n".join(md), encoding="utf-8")
    (report_root / "round3-dependency-report.md").write_text("\n".join(dep), encoding="utf-8")
    print("Wrote source inventory and dependency report.")

if __name__ == "__main__":
    main()
