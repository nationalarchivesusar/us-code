#!/usr/bin/env python3
"""Cross-check source-index PLs vs current-implementation PLs. Emits audit/coverage.json."""
import json, os
ROOT = r"D:/us-code"
si = json.load(open(os.path.join(ROOT, "audit", "source-index.json"), encoding="utf-8"))
ci = json.load(open(os.path.join(ROOT, "audit", "current-implementation.json"), encoding="utf-8"))

src = {r["public_law"]: r for r in si["laws"]}
# normalize source PL to canonical "C-S"
def norm(pl): return pl.strip()
src_pls = set(norm(p) for p in src)
xml_pls = set(ci["by_public_law"].keys())

in_src_not_xml = sorted(src_pls - xml_pls)
in_xml_not_src = sorted(xml_pls - src_pls)
both = sorted(src_pls & xml_pls)

# also map by law_id-derived congress-seq to catch PL vs id mismatches
out = {
    "source_pl_count": len(src_pls),
    "xml_pl_count": len(xml_pls),
    "covered_both": len(both),
    "in_source_not_in_xml": in_src_not_xml,
    "in_xml_not_in_source": in_xml_not_src,
}
json.dump(out, open(os.path.join(ROOT, "audit", "coverage.json"), "w"), indent=2)
print(json.dumps(out, indent=2))
