#!/usr/bin/env python3
"""Finalize and defensively re-audit the Roblox criminal-law API.

The primary hardener positively identifies charges and applies the main Roblox
content screen. This pass independently checks alternate restricted wording and
versions the final API surface.

Important invariant: a legitimate charge is not deleted merely because its full
statutory body contains a restricted reference. If the displayed charge metadata
is safe, the charge remains bookable and only its body/search text is withheld.
Unsafe displayed metadata, non-charges, and explicitly excluded sections remain
excluded.
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
FILTER_VERSION = "roblox-safe-charge-only-v5"

WITHHELD_TEXT = (
    "Full statutory text is not displayed in this Roblox-facing reference. "
    "The charge citation and name remain available for booking."
)

# Defense-in-depth patterns. The primary hardener already blocks the main
# categories; these catch alternate wording and adjacent restricted categories.
# Keep explicit category vocabulary out of public API metadata so the audit
# itself cannot reintroduce words it is designed to remove.
SECONDARY_BLOCKED: tuple[re.Pattern[str], ...] = (
    # Alternate age/youth formulations.
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
    re.compile(r"\b(?:young\s+persons?|adolescents?|prepubescent|pubescent)\b", re.I),

    # Alternate adult-content terminology.
    re.compile(
        r"\b(?:carnal|fornication|adultery|lascivious|masturbat(?:e|ed|es|ing|ion)|"
        r"bestiality|incest(?:uous)?|voyeur(?:ism|istic)?|sextortion|"
        r"explicit\s+sexual|sexually\s+explicit|sexual\s+abuse|sexual\s+exploitation|"
        r"sexual\s+activity|sexual\s+act|sexual\s+contact)\b",
        re.I,
    ),

    # Alternate controlled/intoxicating substance terminology.
    re.compile(
        r"\b(?:amphetamine|barbiturate|hallucinogen|psychoactive|ketamine|psilocybin|"
        r"ghb|rohypnol|phencyclidine|steroid|steroids|syringe|syringes|"
        r"drug\s+paraphernalia|smoking\s+paraphernalia)\b",
        re.I,
    ),

    # Gambling aliases not caught by the primary wording.
    re.compile(
        r"\b(?:gaming\s+establishments?|casino|casinos|slot\s+machines?|poker|"
        r"pari[- ]mutuel|games?\s+of\s+chance|sportsbooks?|sports\s+books?)\b",
        re.I,
    ),

    # Exploitation / coercion categories.
    re.compile(
        r"\b(?:human\s+trafficking|trafficking\s+in\s+persons|forced\s+labor|"
        r"involuntary\s+servitude|peonage|slavery)\b",
        re.I,
    ),

    # Extremism and related organization/activity references.
    re.compile(
        r"\b(?:terrorism|terrorist|terrorists|extremism|extremist|extremists)\b",
        re.I,
    ),

    # Harassment/discrimination categories.
    re.compile(
        r"\b(?:harassment|harass(?:ed|ing)?|stalking|stalker|bullying|"
        r"discrimination|discriminatory|hate\s+crimes?)\b",
        re.I,
    ),

    # Additional self-injury / disordered-behavior language.
    re.compile(
        r"\b(?:eating\s+disorder|anorexia|bulimia|self[- ]?starvation|"
        r"depression|depressive|self[- ]?mutilation|cutting\s+oneself)\b",
        re.I,
    ),

    # Strong profanity.
    re.compile(
        r"\b(?:fuck|fucking|shit|bullshit|bitch|asshole|cunt)\b",
        re.I,
    ),
)

DISPLAY_METADATA_KEYS = {
    "id", "source", "citation", "formal_citation", "section", "label",
    "heading", "part", "chapter", "chapter_heading", "status",
    "offense_class", "sentencing_mode", "sentencing_reason",
    "charge_classification", "classification_status", "class_display",
}


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


def displayed_metadata(record: dict) -> dict:
    return {key: record.get(key) for key in DISPLAY_METADATA_KEYS if key in record}


def metadata_safe(record: dict) -> bool:
    return secondary_safe(displayed_metadata(record))


def withhold_unsafe_body(record: dict) -> tuple[dict, bool]:
    """Keep a safe charge but neutralize body text that fails this screen."""
    result = dict(record)
    if result.get("text_withheld") is True:
        # The primary pass already replaced the body with the same neutral text.
        result["text"] = WITHHELD_TEXT
        result["text_display_scope"] = "withheld_for_platform_safety"
        return result, True

    text = str(result.get("text") or "")
    if text and not secondary_safe(text):
        result["text"] = WITHHELD_TEXT
        result["text_withheld"] = True
        result["text_display_scope"] = "withheld_for_platform_safety"
        return result, True

    result["text_withheld"] = False
    return result, False


def safe_search_text(item: dict) -> str:
    chapter = item.get("chapter") or {}
    values = [item.get("citation"), item.get("heading")]
    if isinstance(chapter, dict):
        values.extend([chapter.get("number"), chapter.get("heading")])
    return " ".join(str(value) for value in values if value)


def filter_local_sections(sections: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for sec in sections:
        if sec.get("is_offense") is not True or not metadata_safe(sec):
            continue
        safe_sec, _ = withhold_unsafe_body(sec)
        kept.append(safe_sec)
    return kept


def apply_secondary_filter() -> None:
    dc_path = BASE / "dc-code.json"
    title18_index_path = BASE / "title18-index.json"
    title18_search_path = BASE / "title18-search.json"

    dc = load(dc_path)
    title18_index = load(title18_index_path)
    title18_search = load(title18_search_path)
    charges = load(CHARGES)

    # Local code: unsafe metadata still removes an offense, but unsafe body text
    # is withheld instead of deleting the otherwise safe charge.
    dc["sections"] = filter_local_sections(dc.get("sections", []))
    allowed_dc = {sec["id"] for sec in dc["sections"]}
    local_by_id = {
        sec["id"]: sec
        for sec in dc["sections"]
    }

    # Title 18: apply the same metadata/body distinction to each detail record.
    allowed_title18_details: dict[str, dict] = {}
    for path in sorted(TITLE18_DIR.glob("*.json")):
        detail = load(path)
        if detail.get("is_charge") is not True or not metadata_safe(detail):
            path.unlink()
            continue
        detail, _ = withhold_unsafe_body(detail)
        write(path, detail)
        allowed_title18_details[str(detail["id"])] = detail

    old_index_by_id = {
        str(item.get("id") or ""): item
        for item in title18_index.get("sections", [])
    }
    safe_index: list[dict] = []
    for charge_id, detail in allowed_title18_details.items():
        old = dict(old_index_by_id.get(charge_id) or {})
        if not old or old.get("is_charge") is not True or not metadata_safe(old):
            continue
        old["text_withheld"] = bool(detail.get("text_withheld"))
        safe_index.append(old)

    safe_index.sort(
        key=lambda item: (
            int(item["section"]) if str(item.get("section", "")).isdigit() else 10**9,
            str(item.get("section", "")),
        )
    )
    title18_index["sections"] = safe_index
    allowed_title18 = {str(item["id"]) for item in safe_index}

    # Search entries can contain the entire statutory body. Whenever either
    # safety layer withheld the body, rebuild search text from safe metadata.
    old_search_by_id = {
        str(item.get("id") or ""): item
        for item in title18_search.get("entries", [])
    }
    safe_search: list[dict] = []
    for item in safe_index:
        charge_id = str(item["id"])
        old = dict(old_search_by_id.get(charge_id) or {})
        if not old:
            old = {"id": charge_id}
        detail = allowed_title18_details[charge_id]
        if detail.get("text_withheld") or not secondary_safe(old):
            old = {"id": charge_id, "search_text": safe_search_text(item)}
        if secondary_safe(old):
            safe_search.append(old)

    title18_search["entries"] = safe_search
    title18_search["count"] = len(safe_search)
    title18_index["counts"] = {
        "sections": len(safe_index),
        "charges": len(safe_index),
        "filtered_out": None,
        "text_withheld": sum(bool(item.get("text_withheld")) for item in safe_index),
    }

    allowed_ids = allowed_dc | allowed_title18
    safe_charges: list[dict] = []
    for item in charges.get("charges", []):
        charge_id = str(item.get("id") or "")
        if charge_id not in allowed_ids or item.get("is_charge") is not True:
            continue
        if not metadata_safe(item):
            continue
        copy = dict(item)
        if copy.get("source") == "title18":
            copy["text_withheld"] = bool(
                allowed_title18_details[charge_id].get("text_withheld")
            )
        else:
            copy["text_withheld"] = bool(local_by_id[charge_id].get("text_withheld"))
        safe_charges.append(copy)

    charges["charges"] = safe_charges
    charges["counts"] = {
        "total": len(safe_charges),
        "dc_code": sum(
            item.get("source") == "dc-criminal-code-federalized"
            for item in safe_charges
        ),
        "title18": sum(item.get("source") == "title18" for item in safe_charges),
    }

    write(dc_path, dc)
    write(title18_index_path, title18_index)
    write(title18_search_path, title18_search)
    write(CHARGES, charges)


def hardened_revision() -> str:
    digest = hashlib.sha256()
    digest.update(FILTER_VERSION.encode("utf-8"))
    for name in (
        "charges.json",
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
    endpoints.pop("federal_code", None)
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
        "preserve_safe_charge_metadata_when_body_withheld": True,
        "note": (
            "The JSON surface exists only for the game/reference implementation and "
            "is not advertised as a public developer API. Restricted body text is "
            "withheld without deleting safely named criminal charges."
        ),
    }

    write(CHARGES, charges)
    write(MANIFEST, manifest)

    check()
    print(
        "Roblox criminal API finalized with charge-preserving two-layer screening: "
        f"revision={revision}, charges={len(charges.get('charges', []))}."
    )


def check() -> None:
    manifest = load(MANIFEST)
    charges = load(CHARGES)
    dc = load(BASE / "dc-code.json")
    title18 = load(BASE / "title18-index.json")
    title18_search = load(BASE / "title18-search.json")
    endpoints = manifest.get("endpoints") or {}

    if "federal_code" in endpoints or (BASE / "federal-code.json").exists():
        raise RuntimeError("Duplicative Federal Criminal Code API surface still exists")
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
    if surface.get("preserve_safe_charge_metadata_when_body_withheld") is not True:
        raise RuntimeError("Manifest does not declare charge-preserving body withholding")
    if (manifest.get("roblox") or {}).get("filter_version") != FILTER_VERSION:
        raise RuntimeError("Manifest filter version is missing or stale")

    revision = manifest.get("revision")
    if not isinstance(revision, str) or len(revision) != 16:
        raise RuntimeError("Manifest hardened revision is invalid")
    if charges.get("revision") != revision:
        raise RuntimeError("Manifest and charge catalog revisions do not match")

    if not all(
        sec.get("is_offense") is True and metadata_safe(sec) and secondary_safe(sec)
        for sec in dc.get("sections", [])
    ):
        raise RuntimeError("D.C.-code endpoint contains a secondary-screen failure or non-offense")
    if not all(
        sec.get("is_charge") is True and metadata_safe(sec) and secondary_safe(sec)
        for sec in title18.get("sections", [])
    ):
        raise RuntimeError("Title 18 index contains a secondary-screen failure or non-charge")
    if not all(secondary_safe(item) for item in title18_search.get("entries", [])):
        raise RuntimeError("Title 18 search index contains a secondary-screen failure")
    if not all(
        item.get("is_charge") is True and metadata_safe(item) and secondary_safe(item)
        for item in charges.get("charges", [])
    ):
        raise RuntimeError("Charge catalog contains a secondary-screen failure or non-charge")
    if any(
        item.get("source") == "federal-criminal-code-2025"
        for item in charges.get("charges", [])
    ):
        raise RuntimeError("Charge catalog contains a duplicative FCC charge")
    excluded = {
        item.get("id"): item.get("reason", "")
        for item in manifest.get("excluded_sources", [])
    }
    if "duplicat" not in excluded.get("federal-criminal-code-2025", "").lower():
        raise RuntimeError("Manifest does not explain the FCC duplication exclusion")

    # No detail may survive unless its charge survived both metadata screens;
    # after body withholding, no blocked secondary text may remain anywhere.
    title_ids = {str(item["id"]) for item in title18.get("sections", [])}
    for path in TITLE18_DIR.glob("*.json"):
        detail = load(path)
        if (
            str(detail.get("id") or "") not in title_ids
            or detail.get("is_charge") is not True
            or not metadata_safe(detail)
            or not secondary_safe(detail)
        ):
            raise RuntimeError(f"Unapproved Title 18 detail survived: {path.name}")

    search_ids = {str(item.get("id") or "") for item in title18_search.get("entries", [])}
    if search_ids != title_ids:
        raise RuntimeError("Title 18 search/index IDs diverged after secondary screening")


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
