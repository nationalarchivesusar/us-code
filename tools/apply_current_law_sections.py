#!/usr/bin/env python3
"""Classify permanent USAR enactments into substantive U.S. Code sections."""
from __future__ import annotations
import argparse, base64, gzip, json, re
from pathlib import Path
from lxml import etree as ET

NS="http://xml.house.gov/schemas/uslm/1.0"
PARTS="current-law-sections.json.gz.b64.part*"
def q(x): return f"{{{NS}}}{x}"

def load_manifest(directory=Path("legal-data")):
    parts=sorted(directory.glob(PARTS))
    if not parts: raise SystemExit(f"missing current-law data parts matching {PARTS}")
    packed="".join("".join(p.read_text(encoding="ascii").split()) for p in parts)
    data=json.loads(gzip.decompress(base64.b64decode(packed)).decode())
    if data.get("schema_version")!="1.0": raise SystemExit("unsupported manifest schema")
    return data

def title_path(t): return Path("usc")/f"usc{t:02d}.xml"
def parse_title(p): return ET.parse(str(p),ET.XMLParser(remove_blank_text=False,resolve_entities=False,huge_tree=True))

def find_identifier(root,ident):
    found=root.xpath("//*[@identifier=$x]",x=ident)
    if len(found)>1:
        if ident==root.get("identifier"):
            titles=[x for x in found if x.tag==q("title")]
            if len(titles)==1:return titles[0]
        managed=[x for x in found if x.get("id","").startswith("rp-2026-")]
        if len(managed)==1:return managed[0]
        raise RuntimeError(f"duplicate identifier {ident}")
    return found[0] if found else None

def layout(parent):
    node=parent
    while node is not None:
        toc=node.find(q("toc")); out=toc.find(q("layout")) if toc is not None else None
        if out is not None:return out
        node=node.getparent()
    raise RuntimeError(f"no TOC on {parent.get('identifier')} or its ancestors")

def tailnum(s):
    m=re.search(r"(\d+)$",s or ""); return int(m.group(1)) if m else None

def toc_href(item):
    r=item.find(f".//{q('ref')}"); return r.get("href","") if r is not None else ""

def insert_toc(lay,item,n,kind):
    token="/ch" if kind=="chapter" else "/s"
    candidates=[x for x in lay.findall(q("tocItem")) if token in toc_href(x)]
    lower=[(tailnum(toc_href(x)),x) for x in candidates if tailnum(toc_href(x)) is not None and tailnum(toc_href(x))<n]
    if lower:
        _,x=max(lower,key=lambda z:z[0]); lay.insert(lay.index(x)+1,item); return
    for x in candidates:
        m=tailnum(toc_href(x))
        if m is not None and m>n: lay.insert(lay.index(x),item); return
    lay.append(item)

def chapter_toc(t,ident,ch,heading,first):
    x=ET.Element(q("tocItem"),id=f"rp-2026-t{t}-ch{ch}-toc")
    a=ET.SubElement(x,q("column"),style="-uslm-lc:I07",**{"class":"threeColumnLeft"}); ET.SubElement(a,q("ref"),href=ident).text=f"{ch}."
    ET.SubElement(x,q("column"),style="-uslm-lc:I08",**{"class":"threeColumnMiddle"}).text=heading.title()
    b=ET.SubElement(x,q("column"),style="-uslm-lc:I09",**{"class":"threeColumnRight"}); ET.SubElement(b,q("ref"),href=f"/us/usc/t{t}/s{first}").text=str(first)
    return x

def section_toc(t,n,heading):
    x=ET.Element(q("tocItem"),id=f"rp-2026-t{t}-s{n}-toc")
    a=ET.SubElement(x,q("column"),style="-uslm-lc:I20",**{"class":"twoColumnLeft"}); ET.SubElement(a,q("ref"),href=f"/us/usc/t{t}/s{n}").text=f"{n}."
    ET.SubElement(x,q("column"),style="-uslm-lc:I46",**{"class":"twoColumnRight"}).text=heading+"."
    return x

def add_notes(sec,notes,prefix):
    if not notes:return
    box=ET.SubElement(sec,q("notes"),type="uscNote",id=prefix+"-notes")
    for i,s in enumerate(notes,1):
        n=ET.SubElement(box,q("note"),style="-uslm-lc:I74",topic="statutoryNotes",id=f"{prefix}-note-{i}")
        ET.SubElement(n,q("heading"),**{"class":"centered smallCaps"}).text=s["heading"]
        ET.SubElement(n,q("p"),style="-uslm-lc:I21",**{"class":"indent0"}).text=s["text"]

def make_section(t,s,notes=()):
    n=str(s["section"]); ident=f"/us/usc/t{t}/s{n}"; prefix=f"rp-2026-t{t}-s{n}"
    sec=ET.Element(q("section"),style="-uslm-lc:I80",id=prefix,identifier=ident)
    ET.SubElement(sec,q("num"),value=n).text=f"§\u202f{n}."; ET.SubElement(sec,q("heading")).text=" "+s["heading"]
    content=ET.SubElement(sec,q("content"))
    for i,text in enumerate(s.get("paragraphs",[]),1): ET.SubElement(content,q("p"),style="-uslm-lc:I11",**{"class":"indent0"},id=f"{prefix}-p{i}").text=text
    credit=ET.SubElement(sec,q("sourceCredit"),id=prefix+"-source")
    if s.get("source")=="Pub. L. 41–271":
        credit.text="("; r=ET.SubElement(credit,q("ref"),href=f"/us/pl/41/271/s{s.get('source_section','')}"); r.text=f"Pub. L. 41–271, §\u202f{s.get('source_section','')}"; r.tail=".)"
    else: credit.text=f"({s.get('source','')}, § {s.get('source_section','')}.)"
    add_notes(sec,notes,prefix); return sec

def add_chapter(tree,s):
    root=tree.getroot(); t=int(s["title"]); ch=str(s["chapter"]); ident=f"{s['parent_identifier']}/ch{ch}"
    old=find_identifier(root,ident)
    if old is not None:
        if old.get("id")!=f"rp-2026-t{t}-ch{ch}":raise RuntimeError(f"chapter collision at {ident}")
        old.getparent().remove(old)
    for x in root.xpath("//*[@id=$x]",x=f"rp-2026-t{t}-ch{ch}-toc"):x.getparent().remove(x)
    parent=find_identifier(root,s["parent_identifier"]); tp=find_identifier(root,s.get("toc_parent_identifier",s["parent_identifier"]))
    if parent is None or tp is None:raise RuntimeError(f"missing chapter parent for title {t}, chapter {ch}")
    node=ET.Element(q("chapter"),style="-uslm-lc:I81",id=f"rp-2026-t{t}-ch{ch}",identifier=ident)
    ET.SubElement(node,q("num"),value=ch).text=f"CHAPTER {ch}—"; ET.SubElement(node,q("heading")).text=s["heading"]
    toc=ET.SubElement(node,q("toc"),role="twoColumnTOC",id=f"rp-2026-t{t}-ch{ch}-section-toc"); lay=ET.SubElement(toc,q("layout")); h=ET.SubElement(lay,q("header"),style="-uslm-lc:I70",role="tocColumnHeader"); ET.SubElement(h,q("column"),**{"class":"tocHeaderLeft"}).text="Sec."
    first=s["sections"][0]["section"]; insert_toc(layout(tp),chapter_toc(t,ident,ch,s["heading"],first),int(ch),"chapter")
    for i,sec in enumerate(s["sections"]):
        collision=find_identifier(root,f"/us/usc/t{t}/s{sec['section']}")
        if collision is not None and not collision.get("id","").startswith("rp-2026-"):raise RuntimeError(f"section collision at /us/usc/t{t}/s{sec['section']}")
        node.append(make_section(t,sec,s.get("chapter_notes",[]) if i==0 else ())); insert_toc(lay,section_toc(t,str(sec["section"]),sec["heading"]),int(sec["section"]),"section")
    for x in list(parent):
        if x.tag==q("chapter"):
            num=x.find(q("num")); v=tailnum(num.get("value")) if num is not None else None
            if v is not None and v>int(ch):parent.insert(parent.index(x),node);break
    else:parent.append(node)

def add_existing(tree,s):
    root=tree.getroot();t=int(s["title"]);ch=find_identifier(root,s["chapter_identifier"])
    if ch is None:raise RuntimeError(f"missing existing chapter {s['chapter_identifier']}")
    lay=layout(ch)
    for sec in s["sections"]:
        n=str(sec["section"]); ident=f"/us/usc/t{t}/s{n}"; old=find_identifier(root,ident)
        if old is not None:
            if not old.get("id","").startswith("rp-2026-"):raise RuntimeError(f"section collision at {ident}")
            old.getparent().remove(old)
        for x in root.xpath("//*[@id=$x]",x=f"rp-2026-t{t}-s{n}-toc"):x.getparent().remove(x)
        node=make_section(t,sec); placed=False
        for x in list(ch):
            if x.tag==q("section") and (tailnum(x.get("identifier")) or 0)>int(n):ch.insert(ch.index(x),node);placed=True;break
        if not placed:
            notes=ch.find(q("notes")); ch.insert(ch.index(notes),node) if notes is not None else ch.append(node)
        insert_toc(lay,section_toc(t,n,sec["heading"]),int(n),"section")

def add_subsections(tree,s):
    root=tree.getroot();t=int(s["title"]);sec=find_identifier(root,s["section_identifier"])
    if sec is None:raise RuntimeError(f"missing target section {s['section_identifier']}")
    for sub in s["subsections"]:
        lab=sub["label"];ident=f"{s['section_identifier']}/{lab}";old=find_identifier(root,ident)
        if old is not None:
            if not old.get("id","").startswith("rp-2026-"):raise RuntimeError(f"subsection collision at {ident}")
            old.getparent().remove(old)
        n=ET.Element(q("subsection"),style="-uslm-lc:I11",**{"class":"indent0"},id=f"rp-2026-t{t}-s205-{lab}",identifier=ident);ET.SubElement(n,q("num"),value=lab).text=f"({lab})";ET.SubElement(n,q("heading"),**{"class":"bold"}).text=" "+sub["heading"]
        c=ET.SubElement(n,q("content"));[ET.SubElement(c,q("p"),style="-uslm-lc:I12",**{"class":"indent1"},id=f"rp-2026-t{t}-s205-{lab}-p{i}").__setattr__("text",txt) for i,txt in enumerate(sub.get("paragraphs",[]),1)]
        pos=next((i for i,x in enumerate(list(sec)) if x.tag in {q("sourceCredit"),q("notes")}),len(sec));sec.insert(pos,n)
    notes=sec.find(q("notes"))
    if notes is None:notes=ET.SubElement(sec,q("notes"),type="uscNote",id="rp-2026-t18-s205-notes")
    for x in list(notes):
        if x.get("id")=="rp-2026-t18-s205-amendment":notes.remove(x)
    for a in s.get("notes",[]):
        n=ET.SubElement(notes,q("note"),style="-uslm-lc:I74",topic="amendments",id="rp-2026-t18-s205-amendment");ET.SubElement(n,q("heading"),**{"class":"centered smallCaps"}).text=a["heading"];ET.SubElement(n,q("p"),style="-uslm-lc:I21",**{"class":"indent0"}).text=a["text"]

def replace_note(tree,s):
    root=tree.getroot();found=root.xpath("//*[@id=$x]",x=s["note_id"])
    if len(found)!=1:raise RuntimeError(f"expected exactly one note {s['note_id']}, found {len(found)}")
    old=found[0];parent=old.getparent();i=parent.index(old);n=ET.Element(q("note"),style="-uslm-lc:I74",topic=s.get("topic","statutoryNotes"),id=s["note_id"]);ET.SubElement(n,q("heading"),**{"class":"centered smallCaps"}).text=s["heading"]
    for txt in s.get("paragraphs",[]):ET.SubElement(n,q("p"),style="-uslm-lc:I21",**{"class":"indent0"}).text=txt
    parent.remove(old);parent.insert(i,n)

def is_managed(e):return e.get("id","").startswith("rp-2026-")
def validate(tree,t):
    root=tree.getroot();ids={};idents={};title_ident=f"/us/usc/t{t}"
    for e in root.iter():
        eid=e.get("id");ident=e.get("identifier")
        if eid:
            prev=ids.get(eid)
            if prev is not None and (is_managed(prev) or is_managed(e)):raise RuntimeError(f"duplicate managed id in title {t}: {eid}")
            ids.setdefault(eid,e)
        if ident:
            prev=idents.get(ident)
            if prev is not None:
                title_pair=ident==title_ident and {prev.tag,e.tag}=={q("uscDoc"),q("title")}
                if not title_pair and (is_managed(prev) or is_managed(e)):raise RuntimeError(f"duplicate managed identifier in title {t}: {ident}")
            idents.setdefault(ident,e)
    for sec in root.xpath("//*[starts-with(@id,'rp-2026-t') and local-name()='section']"):
        if len(" ".join("".join(sec.itertext()).split()))<40:raise RuntimeError(f"managed section too short: {sec.get('identifier')}")

def affected(m):return sorted({int(x["title"]) for k in ("chapters","existing_chapter_sections","section_subsections","replacement_notes") for x in m.get(k,[])})
def apply(m,write=True):
    trees={t:parse_title(title_path(t)) for t in affected(m)}
    for s in m.get("chapters",[]):add_chapter(trees[int(s["title"])],s)
    for s in m.get("existing_chapter_sections",[]):add_existing(trees[int(s["title"])],s)
    for s in m.get("section_subsections",[]):add_subsections(trees[int(s["title"])],s)
    for s in m.get("replacement_notes",[]):replace_note(trees[int(s["title"])],s)
    for t,tree in trees.items():
        validate(tree,t)
        if write:tree.write(str(title_path(t)),encoding="UTF-8",xml_declaration=True,pretty_print=False)
    return list(trees)
def verify(m):
    trees={t:parse_title(title_path(t)) for t in affected(m)}
    for s in m.get("chapters",[]):
        root=trees[int(s["title"])].getroot();ch=find_identifier(root,f"{s['parent_identifier']}/ch{s['chapter']}")
        if ch is None or ch.get("id")!=f"rp-2026-t{s['title']}-ch{s['chapter']}":raise RuntimeError("missing managed chapter")
        for x in s["sections"]:
            if find_identifier(root,f"/us/usc/t{s['title']}/s{x['section']}") is None:raise RuntimeError("missing managed section")
    for s in m.get("existing_chapter_sections",[]):
        root=trees[int(s["title"])].getroot()
        for x in s["sections"]:
            n=find_identifier(root,f"/us/usc/t{s['title']}/s{x['section']}")
            if n is None or not n.get("id","").startswith("rp-2026-"):raise RuntimeError("missing managed section")
    for s in m.get("section_subsections",[]):
        root=trees[int(s["title"])].getroot()
        for x in s["subsections"]:
            if find_identifier(root,f"{s['section_identifier']}/{x['label']}") is None:raise RuntimeError("missing managed subsection")
    for s in m.get("replacement_notes",[]):
        if len(trees[int(s["title"])].getroot().xpath("//*[@id=$x]",x=s["note_id"]))!=1:raise RuntimeError("missing replacement note")
    for t,tree in trees.items():validate(tree,t)
    return list(trees)

def main():
    p=argparse.ArgumentParser();p.add_argument("--check",action="store_true");a=p.parse_args();m=load_manifest();titles=verify(m) if a.check else apply(m);print(("Verified" if a.check else "Applied")+" substantive current-law codification in titles: "+", ".join(map(str,titles)))
if __name__=="__main__":main()
