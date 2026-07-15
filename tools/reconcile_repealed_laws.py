#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, re, subprocess, sys
from collections import defaultdict
from pathlib import Path
from lxml import etree

ROOT=Path(__file__).resolve().parents[1]
REPEALED=ROOT/'legal-data/repealed-public-laws.json'
RESULTS=ROOT/'audit/xml-integration-results.json'
OVERRIDES=ROOT/'legal-data/repealed-law-overrides.json'
OUT_JSON=ROOT/'audit/repealed-law-reconciliation.json'
OUT_MD=ROOT/'audit/repealed-law-reconciliation.md'
NS='http://xml.house.gov/schemas/uslm/1.0'
PARSER=etree.XMLParser(remove_blank_text=False,huge_tree=True,recover=False)

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def dump(p,v): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def anum(a):
 m=re.search(r'(\d+)$',a.get('action_id',''));return int(m.group(1)) if m else 10**9
def xp(v):
 if not v:return None
 v=v.replace('\\','/')
 return v if v.startswith('usc/') else ('usc/'+v if v.startswith('usc') and v.endswith('.xml') else v)
def ids(a):
 for k,op in [('actual_node_ids_added','added'),('actual_node_ids_changed','changed'),('actual_node_ids_removed','removed')]:
  for n in a.get(k) or []:
   if n:yield str(n),op
def prefix(law): return 'rp-pl'+''.join(re.findall(r'\d+',law))
def find(t,n):
 x=t.xpath('//*[@id=$n]',n=n);return x[0] if x else None
def parse(b): return etree.ElementTree(etree.fromstring(b,parser=PARSER))
def show(c,p): return subprocess.check_output(['git','show',f'{c}:{p}'],cwd=ROOT)
def depth(n):
 d=0
 while n.getparent() is not None:d+=1;n=n.getparent()
 return d
def rewrite(note,row):
 for c in list(note):note.remove(c)
 note.text=None
 etree.SubElement(note,f'{{{NS}}}heading').text='Repeal Status'
 etree.SubElement(note,f'{{{NS}}}p').text=(f"{row['title']}. Pub. L. {row['public_law']} was repealed. It is retained solely as historical repeal material and has no current operative effect.")
def serial(t,orig):
 b=etree.tostring(t,encoding='UTF-8',xml_declaration=orig.lstrip().startswith(b'<?xml'),pretty_print=False)
 return b+b'\n' if orig.endswith(b'\n') and not b.endswith(b'\n') else b

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');args=ap.parse_args()
 rd=load(REPEALED); rows={x['law_id']:x for x in rd['laws']}; rep=set(rows)
 data=load(RESULTS); acts=sorted(data['results'],key=anum); base=data.get('baseline_commit') or '00ea0e9b430e4a2eb2253a77d35e6fb125ba5f46'
 ovs=(load(OVERRIDES).get('nodes',{}) if OVERRIDES.exists() else {})
 bylaw=defaultdict(list); events=defaultdict(list)
 for i,a in enumerate(acts):
  law=a.get('law_id','');bylaw[law].append(a);f=xp(a.get('xml_file_after') or a.get('xml_file_before'));target=a.get('final_section_or_subsection_identifier') or ''
  if f:
   for n,op in ids(a):events[(f,n)].append({'i':i,'law':law,'op':op,'action':a.get('action_id'),'target':target})
 R={l:{'law_id':l,'public_law':r['public_law'],'title':r['title'],'actions':len(bylaw[l]),'files':set(),'remove':set(),'restore':set(),'rewrite':set(),'retained':{},'removed_effects_left':set(),'absent':set(),'conflicts':[],'errors':[]} for l,r in rows.items()}
 rem=defaultdict(set);res=defaultdict(set);rew=defaultdict(dict);keep=defaultdict(set)
 for law,r in R.items():
  p=prefix(law)
  for a in bylaw[law]:
   f=xp(a.get('xml_file_after') or a.get('xml_file_before'))
   if not f:continue
   r['files'].add(f)
   for n,op in ids(a):
    o=ovs.get(f'{f}::{n}',{}).get('decision')
    if o=='remove':rem[f].add(n);continue
    if o=='restore-baseline':res[f].add(n);continue
    if o=='retain-active':keep[f].add(n);r['retained'][n]=ovs[f'{f}::{n}'].get('reason','manual override');continue
    if o=='rewrite-repeal-note':rew[f][n]=law;continue
    if n==p+'-codification':rew[f][n]=law;continue
    ev=events[(f,n)]; own_i=min((e['i'] for e in ev if e['law']==law),default=-1); active=[e for e in ev if e['law'] not in rep]
    later=[e for e in active if e['i']>own_i]
    if later:keep[f].add(n);r['retained'][n]=later[-1]['law'];continue
    if active:r['conflicts'].append({'file':f,'node':n,'reason':'mixed repealed/non-repealed ownership','events':ev});continue
    if op=='removed':r['removed_effects_left'].add(n)
    elif n.startswith(p) or op=='added':rem[f].add(n)
    else:res[f].add(n)
 for law,r in R.items():
  p=prefix(law)
  for f in list(r['files']):
   path=ROOT/f
   if not path.exists():continue
   try:t=etree.parse(str(path),parser=PARSER)
   except Exception as e:r['errors'].append(f'parse {f}: {e}');continue
   for n in t.xpath('//*[@id and starts-with(@id,$p)]',p=p):
    nid=n.get('id')
    if nid in keep[f]:continue
    if nid==p+'-codification':rew[f][nid]=law
    else:rem[f].add(nid)
 changed=[]; files=set(rem)|set(res)|set(rew)|set(keep); bcache={}
 for f in sorted(files):
  path=ROOT/f
  if not path.exists():
   for r in R.values():
    if f in r['files']:r['errors'].append('missing '+f)
   continue
  orig=path.read_bytes();t=parse(orig)
  if res[f]:
   try:bt=bcache.setdefault(f,parse(show(base,f)))
   except Exception as e:bt=None
   for n in sorted(res[f]):
    owners=[r for l,r in R.items() if any(n==x for a in bylaw[l] for x,_ in ids(a))]
    cur=find(t,n);old=find(bt,n) if bt is not None else None
    if cur is None:
     for r in owners:r['absent'].add(n)
    elif old is None:
     for r in owners:r['conflicts'].append({'file':f,'node':n,'reason':'no baseline counterpart'})
    else:
     cur.getparent().replace(cur,copy.deepcopy(old))
     for r in owners:r['restore'].add(n)
  nodes=[]
  for n in rem[f]:
   el=find(t,n)
   if el is not None:nodes.append((depth(el),n,el))
   else:
    for e in events[(f,n)]:
     if e['law'] in R:R[e['law']]['absent'].add(n)
  for _,n,el in sorted(nodes):
   par=el.getparent()
   if par is not None:
    par.remove(el)
    for law,r in R.items():
     if n.startswith(prefix(law)) or any(e['law']==law for e in events[(f,n)]):r['remove'].add(n)
  for n,law in rew[f].items():
   el=find(t,n)
   if el is None:R[law]['conflicts'].append({'file':f,'node':n,'reason':'missing repeal-history note'})
   else:rewrite(el,rows[law]);R[law]['rewrite'].add(n)
  new=serial(t,orig)
  if new!=orig and not args.check:path.write_bytes(new);changed.append(f)
 for law,r in R.items():
  p=prefix(law);noteid=p+'-codification';found=False
  for f in r['files']:
   path=ROOT/f
   if not path.exists():continue
   try:t=etree.parse(str(path),parser=PARSER)
   except Exception as e:r['errors'].append(f'post-parse {f}: {e}');continue
   note=find(t,noteid)
   if note is not None:
    found=True;text=' '.join(''.join(note.itertext()).split()).lower()
    if 'repealed' not in text or 'no current operative effect' not in text:r['errors'].append(noteid+' lacks clear repeal status')
   for el in t.xpath('//*[@id and starts-with(@id,$p)]',p=p):
    n=el.get('id') or ''
    if n!=noteid and n not in keep[f]:r['errors'].append(f'operative project node remains: {f}::{n}')
  if r['actions'] and not found:r['errors'].append('no repeal-history note found')
 def disp(r):
  if r['errors']:return 'error'
  if r['conflicts']:return 'manual-review-required'
  if r['retained']:return 'repealed-with-later-active-replacement'
  return 'repealed-history-only'
 laws=[]
 for r in sorted(R.values(),key=lambda x:tuple(map(int,x['public_law'].split('-')))):
  laws.append({**{k:v for k,v in r.items() if k not in {'files','remove','restore','rewrite','removed_effects_left','absent'}},'disposition':disp(r),'files':sorted(r['files']),'nodes_removed':sorted(r['remove']),'nodes_restored':sorted(r['restore']),'notes_rewritten':sorted(r['rewrite']),'historical_removals_left_in_place':sorted(r['removed_effects_left']),'already_absent':sorted(r['absent'])})
 summary={'repealed_laws_checked':len(laws),'clean':sum(x['disposition'] not in {'error','manual-review-required'} for x in laws),'manual_review_required':sum(x['disposition']=='manual-review-required' for x in laws),'errors':sum(x['disposition']=='error' for x in laws),'nodes_removed':sum(len(x['nodes_removed']) for x in laws),'nodes_restored':sum(len(x['nodes_restored']) for x in laws),'notes_rewritten':sum(len(x['notes_rewritten']) for x in laws),'later_active_replacements':sum(len(x['retained']) for x in laws)}
 out={'source':rd['source'],'baseline_commit':base,'mode':'check' if args.check else 'apply','changed_xml_files':changed,'summary':summary,'laws':laws}
 if not args.check:
  dump(OUT_JSON,out);lines=['# Repealed Public-Law Reconciliation','',*[f'- {k.replace("_"," ").title()}: **{v}**' for k,v in summary.items()],'','| Public Law | Title | Disposition |','|---|---|---|']
  lines += [f"| {x['public_law']} | {x['title'].replace('|','\\|')} | {x['disposition']} |" for x in laws];OUT_MD.write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps(summary,indent=2));return 1 if summary['errors'] or summary['manual_review_required'] else 0
if __name__=='__main__':sys.exit(main())
