#!/usr/bin/env python3
from __future__ import annotations

import json
import argparse
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]
UNRESOLVED = ROOT / "audit" / "unresolved.json"
MANIFEST_DIR = ROOT / "audit" / "manifests"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def chunk_evenly(items: List[Dict[str, Any]], parts: int) -> List[List[Dict[str, Any]]]:
    base = len(items) // parts
    extra = len(items) % parts
    groups: List[List[Dict[str, Any]]] = []
    start = 0
    for i in range(parts):
        size = base + (1 if i < extra else 0)
        groups.append(items[start:start + size])
        start += size
    return groups


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=33)
    args = parser.parse_args()

    data = read_json(UNRESOLVED)
    laws = data.get("laws", [])
    groups = chunk_evenly(laws, 6)
    for offset, group in enumerate(groups, start=args.start):
        manifest = {
            "reviewer": f"review-repair-{offset}",
            "group_index": 100 + offset,
            "law_count": len(group),
            "output_path": f"audit/review/review-{offset}.json",
            "laws": [
                {
                    "law_id": law["law_id"],
                    "public_law": law["public_law"],
                    "title": law["title"],
                    "primary_report_path": law["review_report"].replace("audit/review/", "audit/primary/"),
                    "source_review_path": f"audit/review/review-{offset}.json",
                    "source_status": "unresolved",
                    "validation_status": law["issues"][0] if law.get("issues") else "missing chronology conclusion",
                }
                for law in group
            ],
        }
        write_json(MANIFEST_DIR / f"manifest-{offset}.json", manifest)


if __name__ == "__main__":
    main()
