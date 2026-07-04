#!/usr/bin/env python3
"""Local dev server that mimics GitHub Pages' project-page + 404 behavior.

Plain `python -m http.server` cannot exercise the 404.html SPA fallback
(Issue 1): it serves everything from the filesystem root with no base path,
and returns its own generic error body (not 404.html) for missing paths.
GitHub Pages, by contrast, serves a *project* page under a path prefix
(e.g. /us-code/) and serves 404.html's content -- with a real 404 status,
and *without* changing the browser's address bar -- for any request that
doesn't resolve to a real file. This script reproduces both behaviors
against the current repository so the fallback can be exercised with an
ordinary browser exactly the way it will behave in production.

Usage:
    py -3 tools/serve_like_pages.py [--port 8322] [--base-path /us-code/]
"""
from __future__ import annotations

import argparse
import http.server
import mimetypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def make_handler(base_path: str):
    base_path = "/" + base_path.strip("/") + "/"

    class PagesLikeHandler(http.server.BaseHTTPRequestHandler):
        def _resolve(self, url_path: str) -> Path | None:
            if not url_path.startswith(base_path):
                return None
            rel = url_path[len(base_path):].split("?", 1)[0].split("#", 1)[0]
            rel = rel.lstrip("/")
            candidate = (ROOT / rel).resolve()
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                return None  # path escapes the repo root
            if candidate.is_dir():
                candidate = candidate / "index.html"
            return candidate if candidate.is_file() else None

        def _send_file(self, path: Path, status: int) -> None:
            data = path.read_bytes()
            content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 (stdlib override)
            resolved = self._resolve(self.path)
            if resolved is not None:
                self._send_file(resolved, 200)
                return
            not_found = ROOT / "404.html"
            if not_found.is_file():
                self._send_file(not_found, 404)
                return
            self.send_error(404, "Not Found")

        def log_message(self, fmt, *args):  # quieter default logging
            pass

    return PagesLikeHandler


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8322)
    ap.add_argument("--base-path", default="/us-code/")
    args = ap.parse_args()

    handler = make_handler(args.base_path)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Serving {ROOT} at http://127.0.0.1:{args.port}{args.base_path} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
