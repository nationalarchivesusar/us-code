#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List


ROOT = Path(__file__).resolve().parents[2]


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def default_reviewed_against(source_manifest: str) -> List[str]:
    return [
        source_manifest,
        "audit/claude-validation.json",
        "origin/main",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Path to the primary batch JSON")
    parser.add_argument("--output", required=True, help="Path to write the review JSON")
    parser.add_argument("--reviewer", required=True, help="Reviewer name to record in the review report")
    parser.add_argument("--source-manifest", required=True, help="Relative path to the source manifest")
    args = parser.parse_args()

    source_path = ROOT / args.source
    output_path = ROOT / args.output
    payload = read_json(source_path)
    payload["reviewer"] = args.reviewer
    payload["source_manifest"] = args.source_manifest
    payload["output_path"] = args.output
    payload["reviewed_against"] = payload.get("reviewed_against") or default_reviewed_against(args.source_manifest)
    write_json(output_path, payload)


if __name__ == "__main__":
    main()
