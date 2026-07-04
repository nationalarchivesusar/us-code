#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, re, shutil, subprocess, sys, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from common import load_registry, sha256_text

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def extract_docx(path):
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = []
    for p in root.iter(W + "p"):
        parts = []
        for node in p.iter():
            if node.tag == W + "t" and node.text:
                parts.append(node.text)
            elif node.tag == W + "tab":
                parts.append("\t")
            elif node.tag == W + "br":
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paras.append(text)
    return "\n\n".join(paras)

def extract_pdf(path):
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except ImportError:
        exe = shutil.which("pdftotext")
        if not exe:
            raise RuntimeError("PDF source requires `py -3 -m pip install pypdf` or the pdftotext utility")
        proc = subprocess.run([exe, "-layout", str(path), "-"], text=True, capture_output=True)
        if proc.returncode:
            raise RuntimeError(proc.stderr[-2000:])
        return proc.stdout

def extract_html(path):
    s = path.read_text(encoding="utf-8", errors="replace")
    s = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return html.unescape(s)

def normalize(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    reg = load_registry(repo)
    raw_root = repo / "codification" / "round3" / "sources" / "raw"
    txt_root = repo / "codification" / "round3" / "sources" / "text"
    txt_root.mkdir(parents=True, exist_ok=True)
    failures = []

    for law in reg["laws"]:
        raw = raw_root / law["law_id"]
        candidates = list(raw.glob("source.txt")) + list(raw.glob("source.docx")) + list(raw.glob("source.pdf")) + list(raw.glob("source.html"))
        if not candidates:
            failures.append((law["law_id"], "no source file"))
            continue
        # Prefer exported plain text, then DOCX, then PDF.
        candidates.sort(key=lambda p: {".txt":0, ".docx":1, ".pdf":2, ".html":3}.get(p.suffix.lower(), 9))
        src = candidates[0]
        try:
            if src.suffix.lower() == ".txt":
                text = src.read_text(encoding="utf-8-sig", errors="replace")
            elif src.suffix.lower() == ".docx":
                text = extract_docx(src)
            elif src.suffix.lower() == ".pdf":
                text = extract_pdf(src)
            else:
                text = extract_html(src)
            text = normalize(text)
            if len(text) < 200:
                raise RuntimeError("extracted text is implausibly short")
            out = txt_root / f"{law['law_id']}.txt"
            out.write_text(text, encoding="utf-8")
            (txt_root / f"{law['law_id']}.sha256").write_text(sha256_text(text) + "\n", encoding="ascii")
            print(f"[OK] {law['law_id']}: {len(text):,} characters")
        except Exception as exc:
            failures.append((law["law_id"], str(exc)))
            print(f"[FAIL] {law['law_id']}: {exc}")
    if failures:
        raise SystemExit("Source extraction failed: " + "; ".join(f"{a}: {b}" for a,b in failures))

if __name__ == "__main__":
    main()
