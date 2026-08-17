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
  "assets/js/constitution-research.js",
  "assets/js/site-bootstrap.js",
];

test("phase II JavaScript passes syntax validation", () => {
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

test("shared bootstrap wires legal research suite", () => {
  const bootstrap = read("assets/js/site-bootstrap.js");
  for (const expected of [
    "assets/js/homepage-search.js",
    "assets/js/research-tools.js",
    "assets/js/section-comparison.js",
    "assets/js/section-research.js",
    "assets/js/court-bridge.js",
    "changes.html",
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

test("Code Changes page distinguishes verified comparisons from recorded actions", () => {
  const page = read("changes.html");
  const script = read("assets/js/code-changes.js");
  assert.match(page, /Changes to the United States Code/);
  assert.match(page, /verified text change/i);
  assert.match(page, /recorded action/i);
  assert.match(script, /Verified amended/);
  assert.match(script, /Verified added/);
  assert.match(script, /Verified removed/);
  assert.match(script, /not necessarily the isolated effect of this one Public Law/);
});

test("general Code API stays separate and does not duplicate the statutory corpus", () => {
  const page = read("api.html");
  const builder = read("tools/build_code_api.py");
  assert.match(page, /data\/api\/v1\/code\/index\.json/);
  assert.match(page, /does not replace or reshape the existing Criminal Law API/);
  assert.match(page, /source_xml/);
  assert.match(page, /does not duplicate the entire statutory corpus/i);
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
  const page = read("constitution.html");
  assert.match(builder, /constitution-meta\.json/);
  assert.match(builder, /does not itself establish that a constitutional/);
  assert.match(script, /Copy citation/);
  assert.match(script, /Publication provenance/);
  assert.match(script, /U\.S\. Const\. amend\./);
  assert.match(page, /constitution-research\.js/);
});

test("scheduled Constitution refresh dispatches the main Pages workflow", () => {
  const workflow = read(".github/workflows/constitution-refresh.yml");
  assert.match(workflow, /cron: "17 \* \* \* \*"/);
  assert.match(workflow, /workflow_dispatch/);
  assert.match(workflow, /jekyll-gh-pages\.yml/);
  assert.match(workflow, /ref: 'main'/);
});
