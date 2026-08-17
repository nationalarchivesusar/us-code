import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

const jsFiles = [
  "assets/js/homepage-search.js",
  "assets/js/section-research.js",
  "assets/js/court-bridge.js",
  "assets/js/code-changes.js",
  "assets/js/public-law-views.js",
  "assets/js/constitution-research.js",
  "assets/js/site-bootstrap.js",
];

test("research-suite JavaScript passes syntax validation", () => {
  for (const relative of jsFiles) {
    const result = spawnSync(process.execPath, ["--check", path.join(root, relative)], {
      encoding: "utf8",
    });
    assert.equal(result.status, 0, `${relative}: ${result.stderr || result.stdout}`);
  }
});

test("homepage uses one citation search surface", () => {
  const homepage = read("assets/js/homepage-search.js");
  const homepageCss = read("assets/css/homepage-search.css");
  assert.match(homepage, /quick-citation-form/);
  assert.match(homepage, /Section or citation/);
  assert.match(homepage, /Public Law number/);
  assert.match(homepage, /18 U\.S\.C\. § 1752\(a\)\(1\)/);
  assert.match(homepageCss, /\.quick-citation\s*\{\s*display:\s*none\s*!important/);
});

test("global navigation contains only real destinations", () => {
  const bootstrap = read("assets/js/site-bootstrap.js");
  for (const label of ["U.S. Code", "Public Laws", "Constitution", "Criminal Law", "United States Courts"]) {
    assert.ok(bootstrap.includes(`label: "${label}"`), `missing primary destination ${label}`);
  }
  assert.doesNotMatch(bootstrap, /label: "Search Code"/);
  assert.doesNotMatch(bootstrap, /label: "Code Titles"/);
  assert.doesNotMatch(bootstrap, /label: "Code Changes"/);
  assert.doesNotMatch(bootstrap, /label: "API"/);
  assert.match(bootstrap, /label: "Developer API"/);
  assert.match(bootstrap, /primary-nav__toggle/);
  assert.match(read("assets/css/navigation.css"), /data-menu-ready/);
});

test("shared bootstrap wires legal research suite", () => {
  const bootstrap = read("assets/js/site-bootstrap.js");
  for (const expected of [
    "assets/js/homepage-search.js",
    "assets/js/research-tools.js",
    "assets/js/section-comparison.js",
    "assets/js/section-research.js",
    "assets/js/court-bridge.js",
    "constitution.html",
    "api.html",
  ]) {
    assert.match(bootstrap, new RegExp(expected.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});

test("section research exposes verified history, statutory references, and Courts search", () => {
  const sectionResearch = read("assets/js/section-research.js");
  const courts = read("assets/js/court-bridge.js");
  assert.match(sectionResearch, /Verified repository-state history/);
  assert.match(sectionResearch, /does not invent a separate text version/);
  assert.match(sectionResearch, /Built only from explicit USLM statutory reference links/);
  assert.match(sectionResearch, /Version history/);
  assert.match(sectionResearch, /References/);
  assert.match(courts, /courts\/caselaw\//);
  assert.match(courts, /searchParams\.set\("q"/);
});

test("Code Changes is a local Public Laws view and old route remains compatible", () => {
  const page = read("public-laws.html");
  const alias = read("changes.html");
  const viewScript = read("assets/js/public-law-views.js");
  const changesScript = read("assets/js/code-changes.js");
  assert.match(page, /data-public-law-view="laws"/);
  assert.match(page, /data-public-law-view="changes"/);
  assert.match(page, /id="public-laws-view"/);
  assert.match(page, /id="code-changes-view"/);
  assert.match(page, /verified text change/i);
  assert.match(page, /recorded action/i);
  assert.match(viewScript, /searchParams\.set\("view", "changes"\)/);
  assert.match(alias, /public-laws\.html\?view=changes/);
  assert.match(changesScript, /Verified amended/);
  assert.match(changesScript, /Verified added/);
  assert.match(changesScript, /Verified removed/);
  assert.match(changesScript, /not necessarily the isolated effect of this one Public Law/);
});

test("Criminal Law is search-first and permanent indexes are secondary", () => {
  const page = read("criminal-law.html");
  const searchIndex = page.indexOf('id="criminal-search"');
  const aboutIndex = page.indexOf('class="criminal-about"');
  const permanentIndex = page.indexOf('href="criminal/"');
  assert.ok(searchIndex >= 0, "charge search must exist");
  assert.ok(aboutIndex > searchIndex, "catalog explanation must follow charge search");
  assert.ok(permanentIndex > aboutIndex, "permanent index link must be demoted inside catalog explanation");
  assert.match(page, /About this criminal-law catalog/);
  const generator = read("tools/build_criminal_law_routes.py");
  assert.match(generator, /For ordinary research and booking, use the Criminal Law search page/);
  assert.match(generator, /Developer API/);
});

test("general Code API stays separate and does not duplicate the statutory corpus", () => {
  const page = read("api.html");
  const builder = read("tools/build_code_api.py");
  assert.match(page, /data\/api\/v1\/code\/index\.json/);
  assert.match(page, /does not replace or reshape the existing Criminal Law API/);
  assert.match(page, /source_xml/);
  assert.match(page, /does not duplicate the entire statutory corpus/i);
  assert.match(page, /Developer Utility/);
  assert.match(builder, /data" \/ "api" \/ "v1" \/ "code"/);
  assert.match(builder, /criminal_law_api_unchanged/);
  assert.match(builder, /source_xml/);
  assert.match(builder, /compact section metadata with authoritative USLM source pointers/);
  assert.doesNotMatch(builder, /"body"\s*:\s*record\["body"\]/);
  assert.doesNotMatch(builder, /"text"\s*:\s*record\["text"\]/);
  assert.doesNotMatch(builder, /data" \/ "api" \/ "v1" \/ "criminal-law"/);
});

test("Constitution enhancements publish provenance and legal-validity caveat", () => {
  const builder = read("tools/build_constitution.py");
  const script = read("assets/js/constitution-research.js");
  const css = read("assets/css/constitution-research.css");
  const page = read("constitution.html");
  assert.match(builder, /constitution-meta\.json/);
  assert.match(builder, /does not itself establish that a constitutional/);
  assert.match(script, /Copy citation/);
  assert.match(script, /Publication provenance/);
  assert.match(script, /U\.S\. Const\. amend\./);
  assert.match(page, /constitution-research\.js/);
  assert.match(css, /grid-template-columns:\s*minmax\(0, 1fr\) auto auto/);
  assert.match(css, /\.constitution-heading-actions[\s\S]*grid-column:\s*2/);
  assert.match(css, /\.constitution-permalink[\s\S]*grid-column:\s*3/);
});

test("scheduled Constitution refresh dispatches the main Pages workflow", () => {
  const workflow = read(".github/workflows/constitution-refresh.yml");
  assert.match(workflow, /cron: "17 \* \* \* \*"/);
  assert.match(workflow, /workflow_dispatch/);
  assert.match(workflow, /jekyll-gh-pages\.yml/);
  assert.match(workflow, /ref: 'main'/);
});
