#!/usr/bin/env python3
"""Finalize and defensively re-audit the Roblox criminal-law API.

This runs after the primary hardening pass. It intentionally applies a second,
independent conservative screen for alternate wording and additional Roblox
Community Standards categories, then removes the source-document endpoint and
versions the final hardened output for client cache invalidation.

False negatives are preferred to false positives: if a section is questionable,
it is removed from the Roblox-facing catalog while the underlying legal source
remains available elsewhere in the repository/site.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "api" / "v1" / "criminal-law"
MANIFEST = BASE / "manifest.json"
CHARGES = BASE / "charges.json"
DOCUMENTS = BASE / "documents.json"
TITLE18_DIR = BASE / "title18"
FILTER_VERSION = "roblox-safe-charge-only-v3"

# Defense-in-depth patterns. The primary hardener already blocks the main
# categories; these catch alternate youth/age wording and additional categories
# that can be problematic under Roblox Community Standards. Keep wording out of
# public API metadata so the audit cannot reintroduce the terms it removes.
SECONDARY_BLOCKED: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:has|have|had)\s+not\s+attained\s+(?:the\s+)?age\s+of\s+"
        r"(?:16|17|18|sixteen|seventeen|eighteen)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:less\s+than|younger\s+than)\s+"
        r"(?:16|17|18|sixteen|seventeen|eighteen)\b",
        re.I,
    ),
    re.compile(r"\b(?:16|17|18)\s+years?\s+of\s+age\b", re.I),
    re.compile(
        r"\b(?:human\s+trafficking|trafficking\s+in\s+persons|forced\s+labor|"
        r"involuntary\s+servitude|peonage|slavery)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:terrorism|terrorist|terrorists|extremism|extremist|extremists)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:harassment|harass(?:ed|ing)?|stalking|stalker|bullying|"
        r"discrimination|discriminatory|hate\s+crimes?)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:eating\s+disorder|anorexia|bulimia|self[- ]?starvation|"
        r"depression|depressive)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:steroid|steroids|syringe|syringes|drug\s+paraphernalia|"
        r"smoking\s+paraphernalia)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:fuck|fucking|shit|bullshit|bitch|asshole|cunt)\b",
        re.I,
    ),
)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def iter_strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)


def secondary_safe(value: Any) -> bool:
    return not any(
        pattern.search(text)
        for text in iter_strings(value)
        for pattern in SECONDARY_BLOCKED
    )


def apply_secondary_filter() -> None:
    federal_path = BASE / "federal-code.json"
    dc_path = BASE / "dc-code.json"
    title18_index_path = BASE / "title18-index.json"
    title18_search_path = BASE / "title18-search.json"

    federal = load(federal_path)
    dc = load(dc_path)
    title18_index = load(title18_index_path)
    title18_search = load(title18_search_path)
    charges = load(CHARGES)

    federal["sections"] = [
        sec for sec in federal.get("sections", [])
        if sec.get("is_offense") is True and secondary_safe(sec)
    ]
    dc["sections"] = [
        sec for sec in dc.get("sections", [])
        if sec.get("is_offense") is True and secondary_safe(sec)
    ]
    allowed_federal = {sec["id"] for sec in federal["sections"]}
    allowed_dc = {sec["id"] for sec in dc["sections"]}

    # Remove any surviving Title 18 detail whose alternate wording trips the
    # secondary screen. The detail file itself is the authoritative safety test.
    allowed_title18 = set()
    for path in sorted(TITLE18_DIR.glob("*.json")):
        detail = load(path)
        if detail.get("is_charge") is True and secondary_safe(detail):
            allowed_title18.add(detail["id"])
        else:
            path.unlink()

    title18_index["sections"] = [
        item for item in title18_index.get("sections", [])
        if item.get("id") in allowed_title18 and item.get("is_charge") is True
        and secondary_safe(item)
    ]
    allowed_title18 = {item["id"] for item in title18_index["sections"]}
    title18_search["entries"] = [
        item for item in title18_search.get("entries", [])
        if item.get("id") in allowed_title18 and secondary_safe(item)
    ]
    title18_search["count"] = len(title18_search["entries"])
    title18_index["counts"] = {
        "sections": len(title18_index["sections"]),
        "charges": len(title18_index["sections"]),
        "filtered_out": None,
    }

    allowed_ids = allowed_federal | allowed_dc | allowed_title18
    charges["charges"] = [
        item for item in charges.get("charges", [])
        if item.get("id") in allowed_ids
        and item.get("is_charge") is True
        and secondary_safe(item)
    ]
    charges["counts"] = {
        "total": len(charges["charges"]),
        "federal_code": sum(
            item.get("source") == "federal-criminal-code-2025"
            for item in charges["charges"]
        ),
        "dc_code": sum(
            item.get("source") == "dc-criminal-code-federalized"
            for item in charges["charges"]
        ),
        "title18": sum(
            item.get("source") == "title18"
            for item in charges["charges"]
        ),
    }

    write(federal_path, federal)
    write(dc_path, dc)
    write(title18_index_path, title18_index)
    write(title18_search_path, title18_search)
    write(CHARGES, charges)


def hardened_revision() -> str:
    digest = hashlib.sha256()
    digest.update(FILTER_VERSION.encode("utf-8"))
    for name in (
        "charges.json",
        "federal-code.json",
        "dc-code.json",
        "title18-index.json",
        "title18-search.json",
        "sentencing.json",
    ):
        digest.update(name.encode("utf-8"))
        digest.update((BASE / name).read_bytes())
    return digest.hexdigest()[:16]


def finalize() -> None:
    apply_secondary_filter()

    manifest = load(MANIFEST)
    charges = load(CHARGES)
    endpoints = manifest.setdefault("endpoints", {})
    endpoints.pop("source_documents", None)
    endpoints.pop("documents", None)

    if DOCUMENTS.exists():
        DOCUMENTS.unlink()

    revision = hardened_revision()
    manifest["revision"] = revision
    charges["revision"] = revision

    roblox = manifest.setdefault("roblox", {})
    roblox["filter_version"] = FILTER_VERSION
    roblox["public_surface"] = {
        "advertised": False,
        "charge_catalog_only": True,
        "source_documents_exposed": False,
        "defense_in_depth": True,
        "note": "The JSON surface exists only for the game/reference implementation and is not advertised as a public developer API.",
    }

    write(CHARGES, charges)
    write(MANIFEST, manifest)

    check()
    print(
        "Roblox criminal API finalized with two-layer content screening: "
        f"revision={revision}, charges={len(charges.get('charges', []))}."
    )


def check() -> None:
    manifest = load(MANIFEST)
    charges = load(CHARGES)
    federal = load(BASE / "federal-code.json")
    dc = load(BASE / "dc-code.json")
    title18 = load(BASE / "title18-index.json")
    title18_search = load(BASE / "title18-search.json")
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
    if surface.get("defense_in_depth") is not True:
        raise RuntimeError("Secondary safety screen is not declared")
    if (manifest.get("roblox") or {}).get("filter_version") != FILTER_VERSION:
        raise RuntimeError("Manifest filter version is missing or stale")

    revision = manifest.get("revision")
    if not isinstance(revision, str) or len(revision) != 16:
        raise RuntimeError("Manifest hardened revision is invalid")
    if charges.get("revision") != revision:
        raise RuntimeError("Manifest and charge catalog revisions do not match")

    if not all(sec.get("is_offense") is True and secondary_safe(sec) for sec in federal.get("sections", [])):
        raise RuntimeError("Federal-code endpoint contains a secondary-screen failure or non-offense")
    if not all(sec.get("is_offense") is True and secondary_safe(sec) for sec in dc.get("sections", [])):
        raise RuntimeError("D.C.-code endpoint contains a secondary-screen failure or non-offense")
    if not all(sec.get("is_charge") is True and secondary_safe(sec) for sec in title18.get("sections", [])):
        raise RuntimeError("Title 18 index contains a secondary-screen failure or non-charge")
    if not all(secondary_safe(item) for item in title18_search.get("entries", [])):
        raise RuntimeError("Title 18 search index contains a secondary-screen failure")
    if not all(item.get("is_charge") is True and secondary_safe(item) for item in charges.get("charges", [])):
        raise RuntimeError("Charge catalog contains a secondary-screen failure or non-charge")

    # No Title 18 detail may exist unless it survived both screens.
    title_ids = {item["id"] for item in title18.get("sections", [])}
    for path in TITLE18_DIR.glob("*.json"):
        detail = load(path)
        if detail.get("id") not in title_ids or detail.get("is_charge") is not True or not secondary_safe(detail):
            raise RuntimeError(f"Unapproved Title 18 detail survived: {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
        print("Roblox criminal API final-surface and secondary-safety check passed.")
    else:
        finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
