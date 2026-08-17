import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");

test("Phase III browser code passes syntax validation", () => {
  const script = path.join(root, "assets/js/enactment-history.js");
  const result = spawnSync(process.execPath, ["--check", script], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr || result.stdout);
});

test("shared bootstrap loads visual polish and enactment history", () => {
  const bootstrap = read("assets/js/site-bootstrap.js");
  assert.match(bootstrap, /assets\/css\/site-polish\.css/);
  assert.match(bootstrap, /assets\/js\/enactment-history\.js/);
  assert.match(bootstrap, /phase-three-polish/);
});

test("enactment UI distinguishes audit events from exact statutory versions", () => {
  const script = read("assets/js/enactment-history.js");
  const builder = read("tools/build_enactment_history.py");
  assert.match(script, /Verified enactment history/);
  assert.match(script, /not a fabricated version archive/i);
  assert.match(script, /audit summaries and source quotations are evidence/i);
  assert.match(script, /Verified version history/);
  assert.match(builder, /"exact_text_snapshot_available": False/);
  assert.match(builder, /"exact_text_snapshot": None/);
});

test("Phase III polish removes duplicate research-toolbar rule and keeps legal hierarchy", () => {
  const css = read("assets/css/site-polish.css");
  assert.match(css, /section-research-summary \+ \.research-toolbar/);
  assert.match(css, /border-top:\s*0/);
  assert.match(css, /legislative-view-tabs/);
  assert.match(css, /criminal-hero__inner/);
  assert.match(css, /constitution-document/);
});

test("enactment generator cannot modify or generate the Criminal Law API", () => {
  const builder = read("tools/build_enactment_history.py");
  assert.match(builder, /data" \/ "enactment-history"/);
  assert.doesNotMatch(builder, /data" \/ "api" \/ "v1" \/ "criminal-law"/);
  assert.doesNotMatch(builder, /criminal-law\/manifest/);
  assert.match(builder, /does not fabricate an exact intermediate U\.S\. Code text snapshot/);
});
