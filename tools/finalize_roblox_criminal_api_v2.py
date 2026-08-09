#!/usr/bin/env python3
"""Finalize and defensively re-audit the Roblox criminal-law API.

This runs after the primary hardening pass. It applies an independent second
content screen, removes the source-document endpoint, and versions the final
hardened output for client cache invalidation.

A safe charge is not discarded merely because its statutory body contains a
secondary restricted reference. In that case the body is withheld while safe
charge metadata remains bookable. Unsafe displayed metadata still removes the
entry entirely.
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
    "id",
    "source",
    "citation",
    "formal_citation",
    "section",
    "label",
    "heading",
    "part",
    "chapter",
    "chapter_heading",
    "status",
    "offense_class",
    "sentencing_mode",
    "sentencing_reason",
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
    return {
        key: record.get(key)
        for key in DISPLAY_METADATA_KEYS
        if key in record
    }


def safe_metadata(record: dict) -> bool:
    return secondary_safe(displayed_metadata(record))


def withhold_unsafe_body(record: dict) -> dict:
    """Withhold only the body when secondary terms occur there."""
    copy = dict(record)
    if copy.get("text_withheld") is True:
        # The primary hardener already replaced this body with the same neutral
        # placeholder; preserve that decision.
        copy["text"] = WITHHELD_TEXT
        copy["text_display_scope"] = "withheld_for_platform_safety"
        return copy

    text = str(copy.get("text") or "")
    if text and not secondary_safe(text):
        copy["text"] = WITHHELD_TEXT
        copy["text_withheld"] = True
        copy["text_display_scope"] = "withheld_for_platform_safety"
    return copy


def safe_search_text(item: dict) -> str:
    chapter = item.get("chapter") or {}
    values = [item.get("citation"), item.get("heading")]
    if isinstance(chapter, dict):
        values.extend([chapter.get("number"), chapter.get("heading")])
    return " ".join(str(value) for value in values if value).lower()


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

    def harden_local(sections: list[dict]) -> list[dict]:
        kept: list[dict] = []
        for sec in sections:
            if sec.get("is_offense") is not True or not safe_metadata(sec):
                continue
            kept.append(withhold_unsafe_body(sec))
        return kept

    federal["sections"] = harden_local(federal.get("sections", []))
    dc["sections"] = harden_local(dc.get("sections", []))
    allowed_federal = {sec["id"] for sec in federal["sections"]}
    allowed_dc = {sec["id"] for sec in dc["sections"]}

    # Detail files contain the statutory body. Metadata failures remove the
    # charge; body-only failures are neutralized instead.
    allowed_title18: dict[str, dict] = {}
    for path in sorted(TITLE18_DIR.glob("*.json")):
        detail = load(path)
        if detail.get("is_charge") is not True or not safe_metadata(detail):
            path.unlink()
            continue
        detail = withhold_unsafe_body(detail)
        write(path, detail)
        allowed_title18[str(detail["id"])] = detail

    safe_index_sections: list[dict] = []
    for item in title18_index.get("sections", []):
        charge_id = str(item.get("id") or "")
        detail = allowed_title18.get(charge_id)
        if (
            detail is None
            or item.get("is_charge") is not True
            or not safe_metadata(item)
        ):
            continue
        copy = dict(item)
        copy["text_withheld"] = bool(detail.get("text_withheld"))
        safe_index_sections.append(copy)

    title18_index["sections"] = safe_index_sections
    title18_index["counts"] = {
        "sections": len(safe_index_sections),
        "charges": len(safe_index_sections),
        "filtered_out": None,
        "text_withheld": sum(
            bool(item.get("text_withheld")) for item in safe_index_sections
        ),
    }

    index_by_id = {str(item["id"]): item for item in safe_index_sections}
    search_by_id = {
        str(item.get("id") or ""): item
        for item in title18_search.get("entries", [])
    }
    safe_search_entries: list[dict] = []
    for charge_id, item in index_by_id.items():
        detail = allowed_title18[charge_id]
        old = dict(search_by_id.get(charge_id) or {})
        if (
            detail.get("text_withheld")
            or not old
            or not secondary_safe(old)
        ):
            old = {
                "id": charge_id,
                "search_text": safe_search_text(item),
            }
        if secondary_safe(old):
            safe_search_entries.append(old)

    title18_search["entries"] = safe_search_entries
    title18_search["count"] = len(safe_search_entries)

    allowed_title18_ids = set(index_by_id)
    safe_charges: list[dict] = []
    for item in charges.get("charges", []):
        source = item.get("source")
        charge_id = str(item.get("id") or "")
        allowed = (
            (
                source == "federal-criminal-code-2025"
                and charge_id in allowed_federal
            )
            or (
                source == "dc-criminal-code-federalized"
                and charge_id in allowed_dc
            )
            or (
                source == "title18"
                and charge_id in allowed_title18_ids
            )
        )
        if not allowed or item.get("is_charge") is not True or not safe_metadata(item):
            continue

        copy = dict(item)
        if source == "title18":
            copy["text_withheld"] = bool(
                allowed_title18[charge_id].get("text_withheld")
            )
        safe_charges.append(copy)

    charges["charges"] = safe_charges
    charges["counts"] = {
        "total": len(safe_charges),
        "federal_code": sum(
            item.get("source") == "federal-criminal-code-2025"
            for item in safe_charges
        ),
        "dc_code": sum(
            item.get("source") == "dc-criminal-code-federalized"
            for item in safe_charges
        ),
        "title18": sum(
            item.get("source") == "title18"
            for item in safe_charges
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
        "body_only_secondary_failures_are_withheld": True,
        "note": (
            "The JSON surface exists only for the game/reference implementation "
            "and is not advertised as a public developer API."
        ),
    }

    write(CHARGES, charges)
    write(MANIFEST, manifest)

    check()
    print(
        "Roblox criminal API finalized with charge-preserving two-layer "
        f"content screening: revision={revision}, "
        f"charges={len(charges.get('charges', []))}."
    )


def body_is_safe(record: dict) -> bool:
    text = str(record.get("text") or "")
    if record.get("text_withheld") is True:
        return (
            text == WITHHELD_TEXT
            and record.get("text_display_scope") == "withheld_for_platform_safety"
        )
    return secondary_safe(text)


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
    if surface.get("body_only_secondary_failures_are_withheld") is not True:
        raise RuntimeError("Secondary body-withholding policy is not declared")
    if (manifest.get("roblox") or {}).get("filter_version") != FILTER_VERSION:
        raise RuntimeError("Manifest filter version is missing or stale")

    revision = manifest.get("revision")
    if not isinstance(revision, str) or len(revision) != 16:
        raise RuntimeError("Manifest hardened revision is invalid")
    if charges.get("revision") != revision:
        raise RuntimeError("Manifest and charge catalog revisions do not match")

    for payload, name in ((federal, "federal-code"), (dc, "D.C.-code")):
        if not all(
            sec.get("is_offense") is True
            and safe_metadata(sec)
            and body_is_safe(sec)
            for sec in payload.get("sections", [])
        ):
            raise RuntimeError(
                f"{name} endpoint contains an unsafe, non-offense, or "
                "improperly withheld entry"
            )

    if not all(
        sec.get("is_charge") is True and safe_metadata(sec)
        for sec in title18.get("sections", [])
    ):
        raise RuntimeError("Title 18 index contains a metadata failure or non-charge")

    if not all(
        secondary_safe(item)
        for item in title18_search.get("entries", [])
    ):
        raise RuntimeError("Title 18 search index contains a secondary-screen failure")

    if not all(
        item.get("is_charge") is True and safe_metadata(item)
        for item in charges.get("charges", [])
    ):
        raise RuntimeError("Charge catalog contains a metadata failure or non-charge")

    # No Title 18 detail may exist unless it survived metadata screening; any
    # body-only restriction must be represented by the neutral placeholder.
    title_ids = {str(item["id"]) for item in title18.get("sections", [])}
    for path in TITLE18_DIR.glob("*.json"):
        detail = load(path)
        if (
            str(detail.get("id") or "") not in title_ids
            or detail.get("is_charge") is not True
            or not safe_metadata(detail)
            or not body_is_safe(detail)
        ):
            raise RuntimeError(f"Unapproved Title 18 detail survived: {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
        print(
            "Roblox criminal API final-surface and secondary-safety check passed."
        )
    else:
        finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
