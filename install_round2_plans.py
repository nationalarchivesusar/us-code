#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from lxml import etree
except ImportError as exc:
    raise SystemExit("lxml is required. Run: py -3 -m pip install lxml") from exc

NS_URI = "http://xml.house.gov/schemas/uslm/1.0"
X = f"{{{NS_URI}}}"
PACKAGE = Path(__file__).resolve().parent
PAYLOAD = PACKAGE / "payload"


def find_repo(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend([Path.cwd(), PACKAGE.parent, PACKAGE])
    for candidate in candidates:
        candidate = candidate.resolve()
        if (candidate / "usc" / "usc10.xml").exists() and (candidate / "usc" / "usc18.xml").exists() and (candidate / "codification").exists():
            return candidate
    raise SystemExit("Could not locate repository root. Pass --repo D:\\us-code")


def element_span(xml: str, identifier: str) -> tuple[int, int, str]:
    ident = re.escape(identifier)
    start_match = re.search(
        rf'<(?P<tag>[A-Za-z0-9_:.-]+)\b(?=[^>]*\bidentifier="{ident}")[^>]*>',
        xml,
        flags=re.DOTALL,
    )
    if not start_match:
        raise ValueError(f"Identifier not found: {identifier}")
    tag = start_match.group("tag")
    token_re = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.DOTALL)
    depth = 0
    for token in token_re.finditer(xml, start_match.start()):
        value = token.group(0)
        if value.startswith(f"</{tag}"):
            depth -= 1
            if depth == 0:
                return start_match.start(), token.end(), tag
        elif value.endswith("/>"):
            if depth == 0:
                return start_match.start(), token.end(), tag
        else:
            depth += 1
    raise ValueError(f"Could not find closing tag for {identifier}")


def get_element(xml: str, identifier: str) -> str:
    start, end, _ = element_span(xml, identifier)
    return xml[start:end]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_fragment(fragment: str):
    wrapper = f'<wrapper xmlns="{NS_URI}">{fragment}</wrapper>'
    root = etree.fromstring(wrapper.encode("utf-8"), parser=etree.XMLParser(huge_tree=True))
    if len(root) != 1:
        raise ValueError("Fragment must contain exactly one root element")
    return root[0]

def heading_text(fragment: str) -> str:
    el = parse_fragment(fragment)
    h = el.find(f"{X}heading")
    return " ".join(h.itertext()).strip() if h is not None else ""


def make_id(law_id: str, target: str, suffix: str) -> str:
    digest = hashlib.sha1(f"{law_id}|{target}|{suffix}".encode()).hexdigest()[:20]
    return f"rp-{digest}"


def clean_repealed_fragment(fragment: str, section_no: int) -> str:
    sec = parse_fragment(fragment)
    ident = sec.get("identifier") or f"/us/usc/t18/s{section_no}"

    heading = sec.find(f"{X}heading")
    if heading is None:
        heading = etree.Element(f"{X}heading")
        num = sec.find(f"{X}num")
        insert_at = 1 if num is not None else 0
        sec.insert(insert_at, heading)
    for child in list(heading):
        heading.remove(child)
    heading.text = " [Repealed]"

    protected = {f"{X}num", f"{X}heading", f"{X}sourceCredit", f"{X}notes"}
    for child in list(sec):
        if child.tag not in protected:
            sec.remove(child)

    insert_at = len(sec)
    for i, child in enumerate(sec):
        if child.tag in {f"{X}sourceCredit", f"{X}notes"}:
            insert_at = i
            break
    content = etree.Element(f"{X}content")
    p = etree.SubElement(content, f"{X}p", style="-uslm-lc:I11", **{"class": "indent0"})
    p.text = "[Repealed]"
    sec.insert(insert_at, content)

    notes = sec.find(f"{X}notes")
    if notes is None:
        notes = etree.Element(f"{X}notes", type="uscNote", id=make_id("PL-038-266", ident, "notes"))
        sec.append(notes)
    marker = "Pub. L. 38–266"
    if marker not in " ".join(notes.itertext()):
        note = etree.SubElement(notes, f"{X}note", style="-uslm-lc:I74", topic="amendments", id=make_id("PL-038-266", ident, "amendment-note"))
        h = etree.SubElement(note, f"{X}heading", **{"class": "centered smallCaps"})
        h.text = "USAR Amendments"
        p2 = etree.SubElement(note, f"{X}p", style="-uslm-lc:I21", **{"class": "indent0"})
        ref = etree.SubElement(p2, f"{X}ref", href="/us/pl/38/266/s2/b")
        ref.text = "Pub. L. 38–266, § 2(b)"
        ref.tail = f", repealed former section {section_no} as part of the repeal and replacement of chapter 208."

    return etree.tostring(sec, encoding="unicode", pretty_print=False)


def replace_placeholders(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, list):
        return [replace_placeholders(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: replace_placeholders(v, mapping) for k, v in value.items()}
    return value


def copy_or_backup(src: Path, dst: Path, backup_root: Path) -> None:
    if dst.exists():
        rel = dst.relative_to(dst.parents[2]) if "codification" in dst.parts else Path(dst.name)
        backup = backup_root / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, backup)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def build_plans(repo: Path, outdir: Path) -> list[Path]:
    xml10 = (repo / "usc" / "usc10.xml").read_text(encoding="utf-8")
    xml18 = (repo / "usc" / "usc18.xml").read_text(encoding="utf-8")

    # Semantic guards: abort rather than install against an unexpected baseline.
    s7594 = get_element(xml10, "/us/usc/t10/s7594")
    if "Furnishing of heraldic services" not in heading_text(s7594):
        raise ValueError("10 U.S.C. 7594 no longer has the expected heraldic-services heading")
    s205 = get_element(xml10, "/us/usc/t10/s205")
    try:
        get_element(xml10, "/us/usc/t10/s206")
    except ValueError:
        pass
    else:
        raise ValueError("10 U.S.C. 206 already exists; refusing to create a duplicate")

    expected_headings = {
        3161: "Time limits and exclusions",
        3162: "Sanctions",
        3163: "Effective dates",
    }
    raw18: dict[int, str] = {}
    for n in range(3161, 3175):
        raw18[n] = get_element(xml18, f"/us/usc/t18/s{n}")
        if n in expected_headings and expected_headings[n].lower() not in heading_text(raw18[n]).lower():
            raise ValueError(f"18 U.S.C. {n} has an unexpected heading: {heading_text(raw18[n])!r}")
    ch = get_element(xml18, "/us/usc/t18/ptII/ch208")
    if "SPEEDY TRIAL" not in heading_text(ch).upper():
        raise ValueError("18 U.S.C. chapter 208 no longer has the expected SPEEDY TRIAL heading")

    outdir.mkdir(parents=True, exist_ok=True)
    # Copy static fragments.
    for src in sorted((PAYLOAD / "fragments").glob("*.xml")):
        shutil.copy2(src, outdir / src.name)
    # Generate repealed placeholders from the actual current XML, preserving historical notes.
    for n in range(3164, 3175):
        text = clean_repealed_fragment(raw18[n], n)
        (outdir / f"PL-038-266-t18-s{n}-repealed-fragment.xml").write_text(text, encoding="utf-8")

    mapping = {
        "__AUTO_S7594__": sha(s7594),
        "__AUTO_S205__": sha(s205),
    }
    for n, raw in raw18.items():
        mapping[f"__AUTO_S{n}__"] = sha(raw)

    outputs = []
    for template in sorted((PAYLOAD / "plans").glob("*.json.template")):
        data = json.loads(template.read_text(encoding="utf-8"))
        data = replace_placeholders(data, mapping)
        out = outdir / template.name.removesuffix(".template")
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        outputs.append(out)
    return outputs


def scratch_test(repo: Path, staged: Path) -> None:
    engine = repo / "tools" / "rp_codifier.py"
    build_index = repo / "tools" / "build_index.py"
    if not engine.exists() or not build_index.exists():
        raise ValueError("Current tools/rp_codifier.py and tools/build_index.py are required")
    engine_text = engine.read_text(encoding="utf-8", errors="replace")
    for required in ["replace_element_xml", "insert_after_xml", "insert_toc_item_after", "apply-approved"]:
        if required not in engine_text:
            raise ValueError(f"Current codifier does not appear to support {required}")

    with tempfile.TemporaryDirectory(prefix="usar-round2-") as td:
        root = Path(td)
        (root / "usc").mkdir()
        (root / "tools").mkdir()
        (root / "xsd").mkdir()
        shutil.copy2(repo / "usc" / "usc10.xml", root / "usc" / "usc10.xml")
        shutil.copy2(repo / "usc" / "usc18.xml", root / "usc" / "usc18.xml")
        shutil.copy2(engine, root / "tools" / "rp_codifier.py")
        shutil.copy2(build_index, root / "tools" / "build_index.py")
        for src in (repo / "xsd").glob("*"):
            if src.is_file():
                shutil.copy2(src, root / "xsd" / src.name)
        approved = root / "codification" / "plans" / "approved"
        approved.mkdir(parents=True)
        for sub in ["applied", "draft", "rejected"]:
            (root / "codification" / "plans" / sub).mkdir(parents=True)
        for sub in ["backups", "logs", "laws", "packets"]:
            (root / "codification" / sub).mkdir(parents=True)
        (root / "codification" / "state.json").write_text('{"applied": {}, "changed_files": []}', encoding="utf-8")
        for src in staged.iterdir():
            if src.is_file():
                shutil.copy2(src, approved / src.name)
        proc = subprocess.run(
            [sys.executable, str(root / "tools" / "rp_codifier.py"), "apply-approved"],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=240,
        )
        if proc.returncode != 0:
            raise RuntimeError("Scratch application failed:\n" + proc.stdout[-6000:] + "\n" + proc.stderr[-3000:])

        parser = etree.XMLParser(huge_tree=True, recover=False)
        t10 = etree.parse(str(root / "usc" / "usc10.xml"), parser)
        t18 = etree.parse(str(root / "usc" / "usc18.xml"), etree.XMLParser(huge_tree=True, recover=False))
        ns = {"u": NS_URI}
        def h(doc, ident):
            els = doc.xpath(f'//*[@identifier="{ident}"]', namespaces=ns)
            if len(els) != 1:
                raise RuntimeError(f"Scratch verification expected one {ident}, found {len(els)}")
            he = els[0].find(f"{X}heading")
            return " ".join(he.itertext()).strip() if he is not None else ""
        if h(t10, "/us/usc/t10/s7594") != "[Reserved]":
            raise RuntimeError("Scratch result did not reserve 10 U.S.C. 7594")
        if h(t10, "/us/usc/t10/s206") != "Furnishing of heraldic services":
            raise RuntimeError("Scratch result did not add 10 U.S.C. 206")
        if h(t18, "/us/usc/t18/s3161") != "Time limits and exclusions":
            raise RuntimeError("Scratch result did not replace 18 U.S.C. 3161")
        if h(t18, "/us/usc/t18/s3162") != "Sanctions":
            raise RuntimeError("Scratch result did not replace 18 U.S.C. 3162")
        if h(t18, "/us/usc/t18/s3163") != "Deadlines":
            raise RuntimeError("Scratch result did not replace 18 U.S.C. 3163")
        # Preserve the enacted roman-numeral hierarchy rather than silently
        # renumbering the replacement provisions.
        if not t18.xpath('//*[@identifier="/us/usc/t18/s3161/b/i"]', namespaces=ns):
            raise RuntimeError("Scratch result lost enacted 3161(b)(i) numbering")
        if not t18.xpath('//*[@identifier="/us/usc/t18/s3161/c/iv/1/a"]', namespaces=ns):
            raise RuntimeError("Scratch result lost enacted 3161(c)(iv)(1)(a) numbering")
        if not t18.xpath('//*[@identifier="/us/usc/t18/s3162/b/v"]', namespaces=ns):
            raise RuntimeError("Scratch result lost enacted 3162(b)(v) numbering")
        toc3163 = t18.xpath('//u:tocItem[u:column[1]//u:ref[@href="/us/usc/t18/s3163"]]/u:column[2]', namespaces=ns)
        if len(toc3163) != 1 or " ".join(toc3163[0].itertext()).strip() != "Deadlines.":
            raise RuntimeError("Scratch result did not synchronize the 18 U.S.C. 3163 TOC heading")
        for n in range(3164, 3175):
            if h(t18, f"/us/usc/t18/s{n}") != "[Repealed]":
                raise RuntimeError(f"Scratch result did not repeal 18 U.S.C. {n}")
        state = json.loads((root / "codification" / "state.json").read_text(encoding="utf-8"))
        if set(state.get("applied", {})) != {"PL-004-036", "PL-038-266"}:
            raise RuntimeError(f"Unexpected scratch state: {state.get('applied', {}).keys()}")


def install(repo: Path) -> None:
    state_path = repo / "codification" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"applied": {}}
    already = set(state.get("applied", {})) & {"PL-004-036", "PL-038-266"}
    if already:
        raise SystemExit(f"Already applied according to state.json: {', '.join(sorted(already))}")

    with tempfile.TemporaryDirectory(prefix="usar-round2-stage-") as td:
        staged = Path(td)
        plans = build_plans(repo, staged)
        print("Generated current-hash plans:")
        for plan in plans:
            print("  ", plan.name)
        print("Running disposable scratch application...")
        scratch_test(repo, staged)
        print("Scratch application passed.")

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = repo / "codification" / "backups" / f"round2_plan_install_{stamp}"
        approved = repo / "codification" / "plans" / "approved"
        decisions = repo / "codification" / "decisions"
        reports = repo / "codification" / "reports"
        approved.mkdir(parents=True, exist_ok=True)
        decisions.mkdir(parents=True, exist_ok=True)
        reports.mkdir(parents=True, exist_ok=True)

        for src in staged.iterdir():
            if not src.is_file():
                continue
            dst = approved / src.name
            if dst.exists():
                b = backup_root / "plans" / "approved" / dst.name
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, b)
            shutil.copy2(src, dst)

        for src in (PAYLOAD / "decisions").glob("*.md"):
            dst = decisions / src.name
            if dst.exists():
                b = backup_root / "decisions" / dst.name
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, b)
            shutil.copy2(src, dst)

        shutil.copy2(PAYLOAD / "held-law-resolution-register.json", reports / "held-law-resolution-register-round2.json")
        manifest = {
            "installed_at": datetime.now().isoformat(),
            "approved_plans": [p.name for p in plans],
            "scratch_test": "passed",
            "live_xml_modified": False,
            "state_json_modified": False,
            "backup_directory": str(backup_root.relative_to(repo)) if backup_root.exists() else None,
        }
        (reports / "round2-plan-install.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nInstalled approved plans and memoranda. No live XML or state file was modified.")
    print("Next: run codify_us_code.bat, choose Apply all approved plans, then Validate and Status.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="repository root, e.g. D:\\us-code")
    args = ap.parse_args()
    repo = find_repo(args.repo)
    print(f"Repository: {repo}")
    install(repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
