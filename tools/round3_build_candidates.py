#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, re
from pathlib import Path
try:
    from lxml import etree
except ImportError as exc:
    raise SystemExit("lxml is required: py -3 -m pip install lxml") from exc

from common import load_registry, get_element, sha256_text, make_id, NS_URI, X

def section_sort_key(s):
    m = re.match(r"\d+", s)
    return (int(m.group()) if m else 999999, s)

def load_inventory(repo):
    p = repo / "codification" / "reports" / "round3-source-inventory.json"
    return {x["law_id"]: x for x in json.loads(p.read_text(encoding="utf-8"))["laws"]}

def full_text(repo, law_id):
    return (repo / "codification" / "round3" / "sources" / "text" / f"{law_id}.txt").read_text(encoding="utf-8")

def selected_text(repo, law):
    include = law["candidate_classification"].get("included_sections", [])
    if "ALL_OPERATIVE" in include:
        return full_text(repo, law["law_id"])
    parts = []
    secroot = repo / "codification" / "round3" / "sections" / law["law_id"]
    for no in include:
        p = secroot / f"section-{no}.txt"
        if not p.exists():
            raise ValueError(f"{law['law_id']}: required source section {no} not found")
        parts.append(f"SECTION {no}.\n{p.read_text(encoding='utf-8').strip()}")
    return "\n\n".join(parts) + "\n"

def append_note(fragment, law, source_text):
    parser = etree.XMLParser(huge_tree=True, recover=False)
    el = etree.fromstring(fragment.encode("utf-8"), parser)
    marker = f"Pub. L. {law['public_law'].replace('-', '–')}"
    existing = " ".join(el.itertext())
    if marker in existing and law["title"] in existing:
        raise ValueError(f"{law['law_id']}: candidate note already appears present")

    notes = el.find(f"{X}notes")
    if notes is None:
        notes = etree.Element(f"{X}notes", type="uscNote", id=make_id(law["law_id"], el.get("identifier",""), "notes"))
        el.append(notes)

    note = etree.SubElement(
        notes, f"{X}note", style="-uslm-lc:I74", topic="miscellaneous",
        id=make_id(law["law_id"], el.get("identifier",""), "statutory-note")
    )
    heading = etree.SubElement(note, f"{X}heading", **{"class": "centered smallCaps"})
    heading.text = f"USAR Statutory Note—{law['title']}"
    lead = etree.SubElement(note, f"{X}p", style="-uslm-lc:I21", **{"class": "indent0"})
    ref = etree.SubElement(lead, f"{X}ref", href=f"/us/pl/{law['public_law'].replace('-', '/')}")
    ref.text = marker
    ref.tail = f", enacted the following provisions of general and permanent application:"
    # Preserve exact extracted source text without editorial rewriting.
    for idx, block in enumerate(re.split(r"\n\s*\n", source_text.strip()), 1):
        if not block.strip():
            continue
        p = etree.SubElement(note, f"{X}p", style="-uslm-lc:I21", **{"class": "indent0"})
        p.text = block.strip()

    return etree.tostring(el, encoding="unicode", pretty_print=False)

def decision_memo(law, inv, plan_name=None):
    known = "\n".join(f"- {x}" for x in law.get("known_effects", []))
    cls = law.get("candidate_classification", {})
    target = cls.get("target_identifier", "none")
    return f"""# {law['law_id']} — {law['title']}

## Source authentication

- Extracted source SHA-256: `{inv['sha256']}`
- Source phrase gate: **{'PASS' if inv['gates_passed'] else 'FAIL'}**
- Matched phrases: {', '.join(inv['matched_phrases']) or 'none'}
- Sections detected: {', '.join(inv['sections']) or 'none'}

## Known net effect

{known}

## Candidate classification

- Method: `{cls.get('method', 'none')}`
- Target: `{target}`
- Plan: `{plan_name or 'none; audit only'}`

This is an editorial classification for review. It does not rewrite the enacted
text and does not become operative until the draft plan is expressly promoted
and applied through the existing transactional codifier.
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    reg = load_registry(repo)
    inv = load_inventory(repo)
    draft = repo / "codification" / "plans" / "draft"
    fragments = repo / "codification" / "plans" / "draft"
    decisions = repo / "codification" / "decisions"
    draft.mkdir(parents=True, exist_ok=True)
    decisions.mkdir(parents=True, exist_ok=True)

    generated = []
    for law in reg["laws"]:
        info = inv[law["law_id"]]
        cls = law.get("candidate_classification", {})
        if not info["gates_passed"]:
            raise SystemExit(f"{law['law_id']}: source gate failed; refusing candidate generation")

        if cls.get("method") == "survival_audit_only":
            (decisions / f"{law['law_id']}.md").write_text(decision_memo(law, info), encoding="utf-8")
            continue

        title = cls["title"]
        target = cls["target_identifier"]
        xml_path = repo / "usc" / f"usc{int(title):02d}.xml"
        xml = xml_path.read_text(encoding="utf-8")
        raw = get_element(xml, target)
        source_text = selected_text(repo, law)
        replacement = append_note(raw, law, source_text)

        fragment_name = f"{law['law_id']}-candidate-fragment.xml"
        (fragments / fragment_name).write_text(replacement, encoding="utf-8")
        plan_name = f"{law['law_id']}.json"
        plan = {
            "schema_version": 1,
            "law_id": law["law_id"],
            "public_law": law["public_law"],
            "law_section": "",
            "status": "draft",
            "summary": (
                f"Source-gated candidate classification of {law['title']} as a statutory note "
                f"attached to {title} U.S.C. {target.rsplit('s',1)[-1]}. "
                "The candidate preserves the authenticated extracted text without rewriting it."
            ),
            "source_sha256": info["sha256"],
            "operations": [{
                "op": "replace_element_xml",
                "title": title,
                "target_identifier": target,
                "expected_sha256": sha256_text(raw),
                "fragment_file": fragment_name
            }]
        }
        (draft / plan_name).write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        (decisions / f"{law['law_id']}.md").write_text(decision_memo(law, info, plan_name), encoding="utf-8")
        generated.append(plan_name)
        print(f"[DRAFT] {plan_name}")

    manifest = {
        "generated_draft_plans": generated,
        "live_xml_modified": False,
        "state_json_modified": False
    }
    (repo / "codification" / "reports" / "round3-candidate-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

if __name__ == "__main__":
    main()
