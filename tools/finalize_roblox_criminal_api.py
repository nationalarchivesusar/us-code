#!/usr/bin/env python3
"""Finalize the public surface of the Roblox criminal-law API.

The full source enactments already live on the ordinary Public Laws website and
must not be exposed through the booking API. This pass removes the generated
source-document endpoint and its manifest discovery entry after the charge-only
safety hardening step has completed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "api" / "v1" / "criminal-law"
MANIFEST = BASE / "manifest.json"
DOCUMENTS = BASE / "documents.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def finalize() -> None:
    manifest = load(MANIFEST)
    endpoints = manifest.setdefault("endpoints", {})
    endpoints.pop("source_documents", None)
    endpoints.pop("documents", None)

    roblox = manifest.setdefault("roblox", {})
    roblox["public_surface"] = {
        "advertised": False,
        "charge_catalog_only": True,
        "source_documents_exposed": False,
        "note": "The JSON surface exists only for the game/reference implementation and is not advertised as a public developer API.",
    }
    write(MANIFEST, manifest)

    if DOCUMENTS.exists():
        DOCUMENTS.unlink()

    check()
    print("Roblox criminal API finalized: source-document endpoint removed and API discovery surface reduced.")


def check() -> None:
    manifest = load(MANIFEST)
    endpoints = manifest.get("endpoints") or {}
    if "source_documents" in endpoints or "documents" in endpoints:
        raise RuntimeError("Manifest still exposes a source-document endpoint")
    if DOCUMENTS.exists():
        raise RuntimeError("documents.json still exists in the Roblox-facing API")
    surface = (manifest.get("roblox") or {}).get("public_surface") or {}
    if surface.get("charge_catalog_only") is not True:
        raise RuntimeError("Manifest does not declare a charge-only public surface")
    if surface.get("source_documents_exposed") is not False:
        raise RuntimeError("Manifest does not explicitly disable source-document exposure")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
        print("Roblox criminal API final-surface check passed.")
    else:
        finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
