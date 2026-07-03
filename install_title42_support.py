#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path.cwd()
app=ROOT/'assets/js/app.js'; indexer=ROOT/'tools/build_index.py'; html=ROOT/'index.html'
for p in (app,indexer):
    if not p.exists(): raise SystemExit(f'Missing {p}')

def replace_once(text, old, new, label):
    if new in text: return text
    if old not in text: raise SystemExit(f'Could not find patch point: {label}')
    return text.replace(old,new,1)

s=app.read_text(encoding='utf-8')
s=replace_once(s,'  xmlCache: new Map(),\n','  xmlCache: new Map(),\n  chunkCache: new Map(),\n','state cache')
old='''  if (metadata.pointer) {
    elements.message.textContent =
      "This title uses Git LFS storage. Fetch the source XML locally to view its content.";
    return;
  }

  try {
    const { doc } = await fetchTitleDocument(metadata);
    const nav = buildNavigation(metadata, doc);
    state.navigation.set(file, nav);
    renderTitle(metadata, nav);
    setTocCollapsed(false);
  } catch (error) {
'''
new='''  if (metadata.pointer) {
    elements.message.textContent =
      "This title source is unavailable in the published site.";
    return;
  }

  try {
    let nav;
    if (metadata.chunked) {
      const manifest = await fetchChunkManifest(metadata);
      const index = new Map();
      buildIndex(manifest.root, [], index);
      nav = { metadata, root: manifest.root, index, manifest };
    } else {
      const { doc } = await fetchTitleDocument(metadata);
      nav = buildNavigation(metadata, doc);
    }
    state.navigation.set(file, nav);
    renderTitle(metadata, nav);
    setTocCollapsed(false);
  } catch (error) {
'''
s=replace_once(s,old,new,'loadTitle chunk branch')
marker='''function findStructuralRoot(element) {'''
helpers='''async function fetchChunkManifest(metadata) {
  if (state.chunkCache.has(metadata.file)) {
    return state.chunkCache.get(metadata.file);
  }
  const response = await fetch(metadata.file);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${metadata.file}`);
  }
  const manifest = await response.json();
  state.chunkCache.set(metadata.file, manifest);
  return manifest;
}

async function fetchChunkSection(sectionNode) {
  if (!sectionNode?.file) {
    throw new Error("Chunked section file is missing from the manifest.");
  }
  const cacheKey = `section:${sectionNode.file}`;
  if (state.chunkCache.has(cacheKey)) {
    return state.chunkCache.get(cacheKey);
  }
  const response = await fetch(sectionNode.file);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${sectionNode.file}`);
  }
  const text = await response.text();
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.getElementsByTagName("parsererror").length) {
    throw new Error("Unable to parse chunked section XML.");
  }
  const section = doc.documentElement;
  state.chunkCache.set(cacheKey, section);
  return section;
}

'''+marker
s=replace_once(s,marker,helpers,'chunk helpers')
old='''    const { doc } = await fetchTitleDocument(nav.metadata);
    const sectionElement = findSectionElement(doc, sectionNode.identifier, sectionNode.number);
'''
new='''    const sectionElement = nav.metadata.chunked
      ? await fetchChunkSection(sectionNode)
      : findSectionElement(
          (await fetchTitleDocument(nav.metadata)).doc,
          sectionNode.identifier,
          sectionNode.number,
        );
'''
s=replace_once(s,old,new,'displaySection chunk branch')
s=s.replace('if (metadata.pointer) {\n      skippedTitles.push(metadata);','if (metadata.pointer || metadata.chunked) {\n      skippedTitles.push(metadata);')
app.write_text(s,encoding='utf-8')

s=indexer.read_text(encoding='utf-8')
s=replace_once(s,'import json\n','import json\n','json import')
old='''def extract_title_metadata(xml_path: Path) -> Dict[str, str]:
    with xml_path.open("r", encoding="utf-8") as text_fh:
'''
new='''def extract_title_metadata(xml_path: Path) -> Dict[str, str]:
    if xml_path.stem.lower() == "usc42":
        manifest_path = REPO_ROOT / "data" / "title-42" / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            metadata = manifest.get("metadata", {})
            return {
                "file": "data/title-42/manifest.json",
                "identifier": metadata.get("identifier", "/us/usc/t42"),
                "number": metadata.get("number", "42"),
                "heading": metadata.get("heading", "The Public Health and Welfare"),
                "label": metadata.get("label", "The Public Health and Welfare"),
                "chunked": True,
            }

    with xml_path.open("r", encoding="utf-8") as text_fh:
'''
s=replace_once(s,old,new,'index manifest metadata')
indexer.write_text(s,encoding='utf-8')

if html.exists():
    s=html.read_text(encoding='utf-8')
    s=s.replace('Some large titles require Git LFS content before they can be rendered locally.','Large titles are loaded section by section for faster browsing.')
    html.write_text(s,encoding='utf-8')
print('Installed chunked Title 42 browser support.')
