#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from datetime import datetime

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--law", required=True)
    ap.add_argument("--approve-source-hash", help="Optional exact source SHA-256 confirmation")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    draft = repo / "codification" / "plans" / "draft" / f"{args.law}.json"
    if not draft.exists():
        raise SystemExit(f"Draft plan not found: {draft}")
    data = json.loads(draft.read_text(encoding="utf-8"))
    if data.get("status") != "draft":
        raise SystemExit("Plan is not in draft status")
    if not data.get("summary") or not data.get("operations"):
        raise SystemExit("Refusing to promote a plan with blank summary or no operations")
    if args.approve_source_hash and args.approve_source_hash != data.get("source_sha256"):
        raise SystemExit("Source hash confirmation does not match")

    approved = repo / "codification" / "plans" / "approved"
    approved.mkdir(parents=True, exist_ok=True)
    data["status"] = "approved"
    data["approved_at"] = datetime.now().isoformat()
    target = approved / draft.name
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    for op in data["operations"]:
        frag = draft.parent / op.get("fragment_file", "")
        if frag.exists():
            shutil.copy2(frag, approved / frag.name)
    print(f"Promoted {args.law} to approved.")
    print("Next: use the existing BAT to apply ONE approved plan, then validate and inspect the diff.")

if __name__ == "__main__":
    main()
