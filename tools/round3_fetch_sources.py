#!/usr/bin/env python3
from __future__ import annotations
import argparse, http.cookiejar, json, mimetypes, re, urllib.parse, urllib.request
from pathlib import Path
from common import load_registry, sha256_bytes, safe_slug

UA = "Mozilla/5.0 USAR-Codification-Workbench/1.0"

def opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPRedirectHandler()
    )

def request_bytes(op, url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with op.open(req, timeout=90) as r:
        data = r.read()
        return data, dict(r.headers), r.geturl()

def ext_from(headers, data):
    cd = headers.get("Content-Disposition", "")
    m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)', cd, re.I)
    if m:
        name = urllib.parse.unquote(m.group(1)).strip('"')
        suffix = Path(name).suffix
        if suffix:
            return suffix.lower()
    ct = headers.get("Content-Type", "").split(";")[0].strip()
    mapping = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt",
        "text/html": ".html",
        "application/rtf": ".rtf"
    }
    return mapping.get(ct, ".bin")

def fetch_google_doc(op, doc_id, out):
    urls = {
        "txt": f"https://docs.google.com/document/d/{doc_id}/export?format=txt",
        "docx": f"https://docs.google.com/document/d/{doc_id}/export?format=docx",
    }
    results = []
    for label, url in urls.items():
        data, headers, final = request_bytes(op, url)
        if data.lstrip().lower().startswith(b"<!doctype html") and b"accounts.google" in data[:5000].lower():
            raise RuntimeError("Google Doc requires authentication or is not publicly exportable")
        path = out / f"source.{label}"
        path.write_bytes(data)
        results.append({"path": path.name, "bytes": len(data), "sha256": sha256_bytes(data), "url": final})
    return results

def fetch_drive_file(op, file_id, out):
    candidates = [
        f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t",
        f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t",
    ]
    last = None
    for url in candidates:
        try:
            data, headers, final = request_bytes(op, url)
            last = (data, headers, final)
            low = data[:10000].lower()
            if b"virus scan warning" in low or b"download-form" in low:
                token = None
                for pattern in [rb'name="confirm" value="([^"]+)"', rb'confirm=([0-9A-Za-z_-]+)']:
                    m = re.search(pattern, data)
                    if m:
                        token = m.group(1).decode()
                        break
                if token:
                    url2 = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm={urllib.parse.quote(token)}"
                    data, headers, final = request_bytes(op, url2)
            if data[:4] == b"%PDF" or data[:2] == b"PK" or headers.get("Content-Type","").split(";")[0] not in {"text/html","text/plain"}:
                ext = ext_from(headers, data)
                path = out / f"source{ext}"
                path.write_bytes(data)
                return [{"path": path.name, "bytes": len(data), "sha256": sha256_bytes(data), "url": final}]
        except Exception as exc:
            last = exc
    if isinstance(last, tuple):
        data, headers, final = last
        (out / "download-response.html").write_bytes(data)
    raise RuntimeError(f"Could not download Drive file {file_id}; verify sharing is set to anyone with the link")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    reg = load_registry(repo)
    raw_root = repo / "codification" / "round3" / "sources" / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    op = opener()
    manifest = {"schema_version": 1, "sources": []}
    failures = []

    for law in reg["laws"]:
        out = raw_root / law["law_id"]
        out.mkdir(parents=True, exist_ok=True)
        try:
            src = law["source"]
            if src["kind"] == "google_doc":
                files = fetch_google_doc(op, src["document_id"], out)
            elif src["kind"] == "drive_file":
                files = fetch_drive_file(op, src["file_id"], out)
            else:
                raise ValueError(f"Unknown source kind: {src['kind']}")
            entry = {
                "law_id": law["law_id"], "title": law["title"],
                "archived_url": src["archived_url"], "files": files
            }
            (out / "source-metadata.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
            manifest["sources"].append(entry)
            print(f"[OK] {law['law_id']}: {', '.join(f['path'] for f in files)}")
        except Exception as exc:
            failures.append({"law_id": law["law_id"], "error": str(exc)})
            print(f"[FAIL] {law['law_id']}: {exc}")

    manifest["failures"] = failures
    mp = repo / "codification" / "reports" / "round3-source-download-manifest.json"
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if failures:
        raise SystemExit("One or more authenticated sources could not be downloaded; no candidates will be built.")

if __name__ == "__main__":
    main()
