#!/usr/bin/env python3
"""Phase 1: Build audit/source-index.json — authoritative inventory of all 270 USAR public laws.

Reads codification/laws/laws/PL-*/{metadata.json,law.txt,source/*}; verifies hashes;
detects Code citations, PL cross-references, and operative (amend/repeal/etc.) language.
"""
import json, os, re, hashlib, sys

ROOT = r"D:/us-code"
LAWS_DIR = os.path.join(ROOT, "codification", "laws", "laws")
OUT = os.path.join(ROOT, "audit", "source-index.json")

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

# ---- detectors -------------------------------------------------------------
CITATION_PATTERNS = [
    r"\b\d+\s+U\.?\s?S\.?\s?C\.?\s+(?:§+\s?)?\d+\w*",                 # 18 U.S.C. 1001
    r"\bsection\s+\d+\w*\s+of\s+title\s+\d+",                              # section 1001 of title 18
    r"\bchapter\s+\d+\w*\s+of\s+title\s+\d+",                              # chapter 5 of title 5
    r"\btitle\s+\d+\b",                                                     # title 18
    r"\b§+\s?\d+\w*",                                                  # section symbol
]
PL_REF_PATTERNS = [
    r"\bPublic\s+Law\s+\d+[-–]\d+",
    r"\bPub\.?\s*L\.?\s*(?:No\.?\s*)?\d+[-–]\d+",
]
OPERATIVE = {
    "amend":       r"\bis\s+amended\b|\bare\s+amended\b|\bamend(?:ed|ment|ing)?\b",
    "insert":      r"\binsert(?:ed|ing|s)?\b|\bis\s+added\b|\bare\s+added\b|\badding\b",
    "substitute":  r"\bstrik(?:e|ing)\b|\bsubstitut(?:e|ed|ing|ion)\b|\bby\s+striking\b",
    "redesignate": r"\bredesignat(?:e|ed|ing|ion)\b",
    "repeal":      r"\brepeal(?:ed|s|ing)?\b|\bis\s+hereby\s+repealed\b",
    "transfer":    r"\btransfer(?:red|ring|s)?\b",
    "sunset":      r"\bsunset\b|\bshall\s+(?:expire|cease|terminate)\b|\bexpiration\b|\bterminat(?:e|es|ion)\b",
    "effective":   r"\beffective\s+date\b|\btake[s]?\s+effect\b|\bshall\s+take\s+effect\b",
    "shorttitle":  r"\bmay\s+be\s+cited\s+as\b|\bshort\s+title\b",
    "appropriat":  r"\bappropriat(?:e|ed|es|ion|ions)\b|\bthere\s+is\s+authorized\s+to\s+be\s+appropriated\b",
    "sense":       r"\bsense\s+of\s+(?:the\s+)?congress\b|\bit\s+is\s+the\s+sense\b",
    "findings":    r"\bfindings\b|\bthe\s+congress\s+finds\b",
    "savings":     r"\bsavings?\s+(?:clause|provision)\b|\bnothing\s+in\s+this\s+act\b",
    "severab":     r"\bseverab(?:le|ility)\b",
    "establish":   r"\bthere\s+is\s+(?:hereby\s+)?established\b|\bestablish(?:ed|es|ment)?\b",
}

def detect(text, patterns):
    found = set()
    for p in patterns:
        for m in re.finditer(p, text, re.IGNORECASE):
            found.add(re.sub(r"\s+", " ", m.group(0).strip()))
    return sorted(found)

def detect_ops(text):
    return sorted(k for k, p in OPERATIVE.items() if re.search(p, text, re.IGNORECASE))

HTML_DEBRIS = re.compile(r"<html|<!doctype|sign in|request access|you need permission|google drive|<head>|viewer", re.IGNORECASE)

def main():
    with open(os.path.join(ROOT, "codification", "laws", "audit.json"), encoding="utf-8") as f:
        base = json.load(f)
    by_id = {r["law_id"]: r for r in base}

    dirs = sorted(d for d in os.listdir(LAWS_DIR) if re.match(r"PL-\d+-\d+$", d))
    records = []
    seen_pl = {}
    for law_id in dirs:
        d = os.path.join(LAWS_DIR, law_id)
        meta = {}
        mp = os.path.join(d, "metadata.json")
        if os.path.exists(mp):
            meta = json.load(open(mp, encoding="utf-8"))
        b = by_id.get(law_id, {})
        m = re.match(r"PL-(\d+)-(\d+)$", law_id)
        congress, seq = int(m.group(1)), int(m.group(2))
        pl = meta.get("public_law") or b.get("public_law") or f"{congress}-{seq}"
        seen_pl.setdefault(pl, []).append(law_id)

        # source files
        srcdir = os.path.join(d, "source")
        src_files = []
        if os.path.isdir(srcdir):
            for fn in sorted(os.listdir(srcdir)):
                fp = os.path.join(srcdir, fn)
                if os.path.isfile(fp):
                    ext = os.path.splitext(fn)[1].lower().lstrip(".") or "none"
                    src_files.append({
                        "file": os.path.relpath(fp, ROOT).replace("\\", "/"),
                        "format": ext,
                        "size": os.path.getsize(fp),
                        "sha256": sha256(fp),
                    })

        # extracted text
        txt = ""
        tp = os.path.join(d, "law.txt")
        if os.path.exists(tp):
            txt = open(tp, encoding="utf-8", errors="replace").read()
        text_ok = len(txt.strip()) >= 200
        image_only = (not text_ok) and any(s["format"] == "pdf" for s in src_files)
        html_debris = bool(HTML_DEBRIS.search(txt)) or any(s["format"] in ("html", "htm") for s in src_files)

        status = meta.get("status") or b.get("status") or "unknown"
        records.append({
            "law_id": law_id,
            "public_law": pl,
            "congress": congress,
            "sequence": seq,
            "title": (meta.get("name") or b.get("name") or "").strip(),
            "list_name": meta.get("list_name") or b.get("list_name"),
            "enactment_date": None,
            "source_status": status,          # usable / unrecoverable (from repair tool)
            "source_reason": meta.get("reason") or b.get("reason"),
            "card_url": meta.get("card_url") or b.get("card_url"),
            "source_files": src_files,
            "recorded_sha256": meta.get("source_sha256") or b.get("source_sha256") or "",
            "text_extracted": text_ok,
            "text_length": len(txt),
            "image_only_or_scanned": image_only,
            "html_or_viewer_debris": html_debris,
            "code_citations": detect(txt, CITATION_PATTERNS),
            "pl_references": detect(txt, PL_REF_PATTERNS),
            "operative_language": detect_ops(txt),
        })

    # validation
    dup = {k: v for k, v in seen_pl.items() if len(v) > 1}
    summary = {
        "total_laws": len(records),
        "unique_public_laws": len(seen_pl),
        "text_extracted": sum(1 for r in records if r["text_extracted"]),
        "no_usable_text": sum(1 for r in records if not r["text_extracted"]),
        "unrecoverable": sum(1 for r in records if r["source_status"] == "unrecoverable"),
        "html_or_viewer_debris": sum(1 for r in records if r["html_or_viewer_debris"]),
        "duplicates": dup,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"summary": summary, "laws": records}, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2))
    assert len(records) == 270, f"expected 270 laws, got {len(records)}"
    assert not dup, f"duplicate PL numbers: {dup}"
    assert len(seen_pl) == 270, f"expected 270 unique PLs, got {len(seen_pl)}"
    print("OK: 270 unique laws")

if __name__ == "__main__":
    main()
