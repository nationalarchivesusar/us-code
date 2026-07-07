#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as fh:
        return json.load(fh)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queue", default="audit/high-risk-queue.json")
    parser.add_argument("--output-dir", default="audit/review")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=60)
    parser.add_argument("--group-size", type=int, default=10)
    parser.add_argument("--group-offset", type=int, default=0)
    args = parser.parse_args()

    queue_path = ROOT / args.queue
    out_dir = ROOT / args.output_dir
    queue = read_json(queue_path)["queue"]
    slice_ = queue[args.start : args.start + args.count]
    if len(slice_) < args.count:
        raise SystemExit(f"Requested {args.count} queue entries but only {len(slice_)} available from start {args.start}.")

    groups = [slice_[i : i + args.group_size] for i in range(0, len(slice_), args.group_size)]
    if any(len(g) == 0 for g in groups):
        raise SystemExit("Encountered an empty review group.")

    for idx, group in enumerate(groups, start=1 + args.group_offset):
        manifest = {
            "reviewer": f"reviewer-{idx:02d}",
            "group_index": idx,
            "law_count": len(group),
            "output_path": f"audit/review/review-{idx:02d}.json",
            "laws": group,
        }
        write_json(out_dir / f"manifest-{idx:02d}.json", manifest)


if __name__ == "__main__":
    main()
