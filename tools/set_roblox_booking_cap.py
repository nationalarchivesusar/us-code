#!/usr/bin/env python3
"""Apply the Roblox booking-time cap without altering the enacted legal ceiling.

Public Law 39-267 § 9 sets a 30-minute maximum for multi-charge non-court
sentencing. The Roblox booking API intentionally uses a stricter 20-minute
product/gameplay cap. Keep the statutory value intact in sentencing.rules so
legal-source data remains accurate, while exposing 20 minutes through the
Roblox-facing policy fields consumed by the game.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "api" / "v1" / "criminal-law"
BOOKING_CAP_MINUTES = 20


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def apply() -> None:
    sentencing_path = BASE / "sentencing.json"
    charges_path = BASE / "charges.json"
    manifest_path = BASE / "manifest.json"

    sentencing = load(sentencing_path)
    charges = load(charges_path)
    manifest = load(manifest_path)

    rules = sentencing.get("rules") or {}
    statutory_cap = rules.get("multi_charge_max_minutes")
    if not isinstance(statutory_cap, (int, float)):
        raise RuntimeError("Sentencing data does not expose the statutory multi-charge cap")
    if BOOKING_CAP_MINUTES > statutory_cap:
        raise RuntimeError("Roblox booking cap may not exceed the statutory ceiling")

    charges_policy = charges.setdefault("sentencing_policy", {})
    charges_policy["multi_charge_max_minutes"] = BOOKING_CAP_MINUTES
    charges_policy["statutory_multi_charge_max_minutes"] = statutory_cap
    charges_policy["booking_cap_basis"] = (
        "Roblox booking policy uses a stricter 20-minute cap; Public Law 39-267 § 9 "
        "continues to state a 30-minute statutory ceiling for multi-charge non-court sentencing."
    )

    roblox = manifest.setdefault("roblox", {})
    roblox["multi_charge_max_minutes"] = BOOKING_CAP_MINUTES
    roblox["statutory_multi_charge_max_minutes"] = statutory_cap
    roblox["booking_cap_basis"] = charges_policy["booking_cap_basis"]

    sentencing["roblox_booking_policy"] = {
        "multi_charge_max_minutes": BOOKING_CAP_MINUTES,
        "statutory_multi_charge_max_minutes": statutory_cap,
        "scope": "Roblox booking API/gameplay only",
        "basis": charges_policy["booking_cap_basis"],
    }

    write(sentencing_path, sentencing)
    write(charges_path, charges)
    write(manifest_path, manifest)


def check() -> None:
    sentencing = load(BASE / "sentencing.json")
    charges = load(BASE / "charges.json")
    manifest = load(BASE / "manifest.json")

    statutory_cap = (sentencing.get("rules") or {}).get("multi_charge_max_minutes")
    if statutory_cap != 30:
        raise RuntimeError(
            f"Expected Public Law 39-267 statutory ceiling to remain 30 minutes, got {statutory_cap!r}"
        )

    policy = charges.get("sentencing_policy") or {}
    roblox = manifest.get("roblox") or {}
    booking_policy = sentencing.get("roblox_booking_policy") or {}

    if policy.get("multi_charge_max_minutes") != BOOKING_CAP_MINUTES:
        raise RuntimeError("charges.json does not expose the 20-minute Roblox booking cap")
    if roblox.get("multi_charge_max_minutes") != BOOKING_CAP_MINUTES:
        raise RuntimeError("manifest.json does not expose the 20-minute Roblox booking cap")
    if booking_policy.get("multi_charge_max_minutes") != BOOKING_CAP_MINUTES:
        raise RuntimeError("sentencing.json does not expose the 20-minute Roblox booking cap")

    for value in (
        policy.get("statutory_multi_charge_max_minutes"),
        roblox.get("statutory_multi_charge_max_minutes"),
        booking_policy.get("statutory_multi_charge_max_minutes"),
    ):
        if value != statutory_cap:
            raise RuntimeError("Roblox API lost the separate 30-minute statutory ceiling metadata")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
        print("Roblox booking cap check passed: gameplay/API=20 minutes, statutory ceiling=30 minutes.")
    else:
        apply()
        check()
        print("Applied Roblox booking cap: gameplay/API=20 minutes, statutory ceiling preserved at 30 minutes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
