import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workflow = fs.readFileSync(path.join(root, ".github/workflows/jekyll-gh-pages.yml"), "utf8");

test("Pages build regenerates every public legal-research dataset", () => {
  for (const builder of [
    "tools/build_section_history.py",
    "tools/build_version_history.py",
    "tools/build_reference_graph.py",
    "tools/build_code_api.py",
  ]) {
    assert.ok(workflow.includes(`python ${builder}`), `missing ${builder} from Pages build`);
  }

  for (const output of [
    "data/section-history/manifest.json",
    "data/version-history/manifest.json",
    "data/references/manifest.json",
    "data/api/v1/code/index.json",
  ]) {
    assert.ok(workflow.includes(output), `Pages workflow does not assert ${output}`);
  }
});

test("Pages artifact publishes secondary legal-research routes", () => {
  assert.match(
    workflow,
    /cp index\.html 404\.html public-laws\.html criminal-law\.html constitution\.html api\.html changes\.html _site\//,
  );
  assert.match(workflow, /test -s _site\/api\.html/);
  assert.match(workflow, /test -s _site\/changes\.html/);
});

test("Criminal Law API safety checks remain in the repaired workflow", () => {
  assert.match(workflow, /tools\/harden_roblox_criminal_api\.py --check/);
  assert.match(workflow, /tools\/finalize_roblox_criminal_api\.py --check/);
  assert.match(workflow, /test ! -e _site\/data\/api\/v1\/criminal-law\/documents\.json/);
  assert.match(workflow, /test ! -e _site\/data\/api\/v1\/criminal-law\/federal-code\.json/);
});
