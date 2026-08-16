import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { test } from "node:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const comparisonJs = path.join(root, "assets/js/section-comparison.js");
const comparisonCss = path.join(root, "assets/css/section-comparison.css");
const bootstrap = path.join(root, "assets/js/site-bootstrap.js");

test("section comparison enhancement is wired into the Code viewer", () => {
  const bootstrapText = fs.readFileSync(bootstrap, "utf8");
  assert.match(bootstrapText, /assets\/js\/section-comparison\.js/);
  assert.ok(fs.existsSync(comparisonJs));
  assert.ok(fs.existsSync(comparisonCss));
});

test("section comparison JavaScript passes syntax validation", () => {
  const result = spawnSync(process.execPath, ["--check", comparisonJs], {
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
});

test("comparison UI exposes verified redline and side-by-side modes", () => {
  const source = fs.readFileSync(comparisonJs, "utf8");
  assert.match(source, /Verified baseline comparison/);
  assert.match(source, /Compare versions/);
  assert.match(source, /Redline/);
  assert.match(source, /Side by side/);
  assert.match(source, /does not yet reconstruct a separate text snapshot/);
});
