#!/usr/bin/env python3
"""Remove internal workflow language from the public-law website dataset."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "public-laws.json"


def public_no_code_description(treatment: str) -> str:
    treatment = (treatment or "").lower()
    if "already-incorporated" in treatment:
        return "No additional U.S. Code amendment was required because this effect was already reflected in the Code."
    if "source-limited-history" in treatment:
        return "No operative U.S. Code amendment was made; the available source supports historical treatment only."
    if "exclude-from-code" in treatment:
        return "This provision was not codified because it does not enact or amend permanent U.S. Code text."
    if "toc-update" in treatment:
        return "This provision affected organizational or table-of-contents treatment without adding operative Code text."
    if "no-code" in treatment:
        return "No direct U.S. Code amendment was required for this provision."
    return "No direct U.S. Code amendment was required for this provision."


def main() -> None:
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    for law in payload.get("laws", []):
        repealed = law.get("status") == "repealed"
        for action in law.get("actions", []):
            if repealed:
                action["result_label"] = "Historical disposition"

            description = action.get("description") or ""
            internal_no_code = (
                description.startswith("Documented non-operative disposition")
                or "The XML cleanup pass removed Trello URLs" in description
                or "full-law dumps" in description
                or "false source boilerplate" in description
            )
            if internal_no_code:
                action["description"] = public_no_code_description(
                    action.get("treatment") or ""
                )

    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    forbidden = (
        "Documented non-operative disposition",
        "The XML cleanup pass",
        "Trello URLs",
        "full-law dumps",
        "false source boilerplate",
    )
    hits = [phrase for phrase in forbidden if phrase in serialized]
    if hits:
        raise SystemExit(f"Public-law dataset still contains internal language: {hits}")

    DATA_FILE.write_text(serialized, encoding="utf-8")
    print("Filtered public-law dataset for publication.")


if __name__ == "__main__":
    main()
