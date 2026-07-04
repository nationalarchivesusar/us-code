#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests


def git_head(repo: Path) -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, text=True, capture_output=True)
    if proc.returncode:
        raise RuntimeError("Could not determine repository commit SHA")
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=repo,
        text=True,
        capture_output=True,
    )
    if dirty.stdout.strip():
        raise RuntimeError(
            "Tracked repository changes are not committed. Commit and push the codification before posting Trello comments."
        )
    return proc.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--comments-json")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    comments_path = (
        Path(args.comments_json).resolve()
        if args.comments_json
        else repo / "codification" / "mass_migration" / "latest" / "reports" / "TRELLO-COMMENTS.json"
    )
    payload = json.loads(comments_path.read_text(encoding="utf-8"))
    comments = payload.get("comments", [])
    if args.limit:
        comments = comments[: args.limit]
    sha = git_head(repo)

    if not args.post:
        print(f"Validated {len(comments)} comment records for commit {sha}.")
        print("Use --post and set TRELLO_KEY and TRELLO_TOKEN to publish them.")
        return 0

    key = os.environ.get("TRELLO_KEY", "")
    token = os.environ.get("TRELLO_TOKEN", "")
    if not key or not token:
        raise SystemExit("Set TRELLO_KEY and TRELLO_TOKEN before using --post")

    session = requests.Session()
    posted = 0
    skipped = 0
    failures = []
    for index, item in enumerate(comments, 1):
        card_id = item["card_id"]
        marker = item["marker"]
        comment = item["comment"].replace("{{COMMIT_SHA}}", sha)
        try:
            existing = session.get(
                f"https://api.trello.com/1/cards/{card_id}/actions",
                params={
                    "key": key,
                    "token": token,
                    "filter": "commentCard",
                    "fields": "data",
                    "limit": 1000,
                },
                timeout=60,
            )
            existing.raise_for_status()
            actions = existing.json()
            if any(marker in ((action.get("data") or {}).get("text") or "") for action in actions):
                skipped += 1
                print(f"[{index}/{len(comments)}] SKIP {item['law_id']} (marker already present)")
                continue
            response = session.post(
                f"https://api.trello.com/1/cards/{card_id}/actions/comments",
                params={"key": key, "token": token, "text": comment},
                timeout=60,
            )
            response.raise_for_status()
            posted += 1
            print(f"[{index}/{len(comments)}] POSTED {item['law_id']}")
            time.sleep(0.35)
        except Exception as exc:  # noqa: BLE001
            failures.append({"law_id": item["law_id"], "card_id": card_id, "error": str(exc)})
            print(f"[{index}/{len(comments)}] FAILED {item['law_id']}: {exc}", file=sys.stderr)
            time.sleep(2)

    result = {
        "commit": sha,
        "posted": posted,
        "skipped": skipped,
        "failures": failures,
    }
    result_path = comments_path.with_name("TRELLO-POST-RESULT.json")
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
