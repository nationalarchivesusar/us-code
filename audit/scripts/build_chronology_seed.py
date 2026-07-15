#!/usr/bin/env python3
"""Phase 5 seed: detect cross-law references and their verbs from source text.

For each law, find mentions of other public laws (Pub. L. X-Y / Public Law X-Y) and the
governing verb nearby (repeal/amend/supersede/revive/extend/reinstate). Emits
audit/chronology-seed.json — a directed graph the chronology pass reviews and finalizes.
"""
import json, os, re
ROOT = r"D:/us-code"
LAWS = os.path.join(ROOT, "codification", "laws", "laws")
si = json.load(open(os.path.join(ROOT, "audit", "source-index.json"), encoding="utf-8"))

PLREF = re.compile(r'(?:Public\s+Law|Pub\.?\s*L\.?)\s*(?:No\.?\s*)?(\d+)\s*[-–—]\s*(\d+)', re.I)
VERBS = {
    "repeal": r"repeal",
    "amend": r"amend",
    "supersede": r"supersed",
    "revive": r"reviv|reinstat|restor",
    "extend": r"extend|reauthoriz",
    "delay": r"delay|postpone|suspend",
}
def verb_near(text, pos, window=200):
    seg = text[max(0, pos-window):pos+window].lower()
    return sorted(k for k, p in VERBS.items() if re.search(p, seg))

edges = []
self_repeal = []
for r in si["laws"]:
    pl = r["public_law"]
    tp = os.path.join(LAWS, r["law_id"], "law.txt")
    if not os.path.exists(tp):
        continue
    text = open(tp, encoding="utf-8", errors="replace").read()
    # self-sunset / self-repeal detection
    if re.search(r"this\s+act\s+shall\s+(?:expire|terminate|cease|sunset)", text, re.I) or \
       re.search(r"sunset", text, re.I):
        self_repeal.append({"public_law": pl, "kind": "self-sunset-language"})
    for m in PLREF.finditer(text):
        tgt = f"{int(m.group(1))}-{int(m.group(2))}"
        if tgt == pl:
            continue
        edges.append({
            "from_pl": pl, "to_pl": tgt,
            "verbs": verb_near(text, m.start()),
            "context": re.sub(r"\s+", " ", text[max(0,m.start()-90):m.start()+90]).strip(),
        })

out = {
    "edge_count": len(edges),
    "laws_with_selfsunset": self_repeal,
    "edges": edges,
}
json.dump(out, open(os.path.join(ROOT, "audit", "chronology-seed.json"), "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
# quick console view: only edges that carry a repeal/supersede/revive verb
strong = [e for e in edges if any(v in e["verbs"] for v in ("repeal","supersede","revive"))]
print(f"total cross-refs: {len(edges)}; self-sunset laws: {len(self_repeal)}; strong(repeal/supersede/revive): {len(strong)}")
for e in strong[:40]:
    print(f"  {e['from_pl']} -> {e['to_pl']} {e['verbs']}")
