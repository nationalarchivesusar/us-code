#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, shutil
from pathlib import Path
from lxml import etree

USLM='http://xml.house.gov/schemas/uslm/1.0'
DC='http://purl.org/dc/elements/1.1/'
Q=lambda n:f'{{{USLM}}}{n}'
STRUCT={'division','subtitle','title','part','subpart','chapter','subchapter','article','section','appendix','compiledAct','subpart1'}

def clean(s): return ' '.join((s or '').split())
def direct(el,name):
    x=el.find(Q(name)); return clean(''.join(x.itertext())) if x is not None else ''
def section_key(s): return re.sub(r'[^a-z0-9]','',s.lower())
def safe_file(identifier, number, index):
    base = identifier.rsplit('/',1)[-1] if identifier else section_key(number)
    base=re.sub(r'[^A-Za-z0-9_.-]+','_',base).strip('._') or f'section-{index:05d}'
    return f'{index:05d}-{base}.xml'

def node(el, sections_dir, counter):
    kind=etree.QName(el).localname
    if kind not in STRUCT: return None
    obj={'type':kind,'identifier':el.get('identifier',''),'number':direct(el,'num'),'heading':direct(el,'heading'),'children':[]}
    if kind=='section':
        counter[0]+=1
        name=safe_file(obj['identifier'],obj['number'],counter[0])
        (sections_dir/name).write_bytes(etree.tostring(el, encoding='utf-8', xml_declaration=True))
        obj['file']=f'data/title-42/sections/{name}'
        return obj
    for child in el:
        c=node(child,sections_dir,counter)
        if c: obj['children'].append(c)
    return obj

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',default='usc/usc42.xml'); ap.add_argument('--output',default='data/title-42')
    a=ap.parse_args(); root=Path.cwd(); src=(root/a.source).resolve(); out=(root/a.output).resolve(); sections=out/'sections'
    if not src.exists(): raise SystemExit(f'Missing {src}')
    first=src.open('rb').read(80)
    if first.startswith(b'version https://git-lfs.github.com'):
        raise SystemExit('usc42.xml is still an LFS pointer. Fetch the LFS object before building.')
    shutil.rmtree(out,ignore_errors=True); sections.mkdir(parents=True)
    parser=etree.XMLParser(huge_tree=True, recover=False, remove_blank_text=False)
    tree=etree.parse(str(src),parser); doc=tree.getroot()
    identifier=doc.get('identifier','')
    number=clean(''.join(doc.find('.//'+Q('docNumber')).itertext())) if doc.find('.//'+Q('docNumber')) is not None else '42'
    dc_title=doc.find('.//{'+DC+'}title'); label=clean(''.join(dc_title.itertext())) if dc_title is not None else 'The Public Health and Welfare'
    main_el=doc.find('.//'+Q('main'))
    structural=None
    for el in main_el.iter() if main_el is not None else doc.iter():
        if etree.QName(el).localname in STRUCT:
            structural=el; break
    if structural is None: raise SystemExit('No structural root found')
    counter=[0]; root_node=node(structural,sections,counter)
    heading=root_node.get('heading') or label
    manifest={'generated_from':a.source,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'metadata':{'identifier':identifier,'number':number,'heading':heading,'label':label},'section_count':counter[0],'root':root_node}
    (out/'manifest.json').write_text(json.dumps(manifest,separators=(',',':'),ensure_ascii=False),encoding='utf-8')
    print(f'Wrote {counter[0]} Title 42 sections to {out.relative_to(root)}')
if __name__=='__main__': main()
