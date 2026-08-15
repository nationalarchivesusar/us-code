import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";


const read = (path) => fs.readFileSync(new URL(`../${path}`, import.meta.url), "utf8");


test("criminal-law UI explains the FCC exclusion and offers no duplicate source", () => {
  const html = read("criminal-law.html");
  const script = read("assets/js/criminal-law.js");

  assert.match(html, /all 66 FCC offenses duplicate D\.C\. Criminal Code offenses/);
  assert.doesNotMatch(html, /option value="federal-criminal-code-2025"/);
  assert.doesNotMatch(script, /fetchJson\("federal-code\.json"\)/);
  assert.doesNotMatch(script, /"federal-criminal-code-2025": "Federal Criminal Code"/);
});


test("API and permanent-route builders do not publish an FCC endpoint", () => {
  const apiBuilder = read("tools/build_criminal_law_api.py");
  const routeBuilder = read("tools/build_criminal_law_routes.py");

  assert.match(apiBuilder, /assert_fcc_offenses_are_duplicated/);
  assert.match(apiBuilder, /excluded_sources/);
  assert.doesNotMatch(apiBuilder, /write_json\(OUT \/ "federal-code\.json"/);
  assert.doesNotMatch(routeBuilder, /criminal\/fcc/);
});
