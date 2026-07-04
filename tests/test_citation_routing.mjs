// Deterministic tests for the GitHub Pages SPA fallback (Issue 1):
// direct-citation URL parsing (getCitationPathState/getUrlState) and the
// 404.html handoff restoration logic (restoreRedirectedPath) in
// assets/js/app.js. Run with: node --test tests/test_citation_routing.mjs
//
// Loaded the same way as tests/test_usar_notes.mjs: via Node's vm module
// against a minimal fake DOM/browser environment, so this project does not
// need a browser/DOM test dependency (e.g. jsdom, playwright) just to
// cover pure URL-parsing logic.
import assert from "node:assert/strict";
import { test } from "node:test";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APP_JS = fs.readFileSync(path.join(ROOT, "assets", "js", "app.js"), "utf-8");

const SITE_ORIGIN = "https://nationalarchivesusar.github.io";
const BASE_PATH = "/us-code/";

function makeLocation(href) {
  const url = new URL(href);
  return {
    href: url.href,
    pathname: url.pathname,
    search: url.search,
    hash: url.hash,
    get url() {
      return url;
    },
  };
}

// vm.createContext gives every object created inside the sandbox a
// prototype chain rooted in that sandbox's own realm, so plain objects
// returned from sandboxed functions (e.g. getUrlState()'s `{ title,
// section, pinpoint }` literal) are not reference-equal to same-shaped
// objects created in this file's realm, even though their contents match.
// Round-tripping through JSON strips that cross-realm identity so
// assert.deepEqual compares plain data instead of prototypes.
function plain(value) {
  return JSON.parse(JSON.stringify(value));
}

function loadAppContext(initialHref) {
  const location = makeLocation(initialHref);
  const historyLog = [];

  const sandbox = {
    document: {
      addEventListener() {},
      getElementById() {
        return null;
      },
      querySelectorAll() {
        return [];
      },
      querySelector(selector) {
        if (selector === 'script[src$="assets/js/app.js"]') {
          return { src: `${SITE_ORIGIN}${BASE_PATH}assets/js/app.js` };
        }
        return null;
      },
      documentElement: { dataset: {} },
    },
    window: {},
    location,
    history: {
      replaceState(stateObj, title, url) {
        const resolved = new URL(url, location.href);
        location.href = resolved.href;
        location.pathname = resolved.pathname;
        location.search = resolved.search;
        location.hash = resolved.hash;
        historyLog.push({ method: "replaceState", url: resolved.href });
      },
      pushState(stateObj, title, url) {
        const resolved = new URL(url, location.href);
        location.href = resolved.href;
        location.pathname = resolved.pathname;
        location.search = resolved.search;
        location.hash = resolved.hash;
        historyLog.push({ method: "pushState", url: resolved.href });
      },
    },
    localStorage: {
      getItem() {
        return null;
      },
      setItem() {},
    },
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
    Node: { ELEMENT_NODE: 1, TEXT_NODE: 3 },
    URL,
    URLSearchParams,
    console,
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(APP_JS, sandbox, { filename: "assets/js/app.js" });
  return { ctx: sandbox, location, historyLog };
}

test("getCitationPathState parses a chunked Title 42 citation (/cite/42/1983/)", () => {
  const { ctx } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}cite/42/1983/`);
  assert.deepEqual(plain(ctx.getCitationPathState()), { title: "42", section: "1983" });
});

test("getCitationPathState parses an ordinary-title citation (/cite/5/552/)", () => {
  const { ctx } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}cite/5/552/`);
  assert.deepEqual(plain(ctx.getCitationPathState()), { title: "5", section: "552" });
});

test("getUrlState preserves a pinpoint query parameter alongside a path citation", () => {
  const { ctx } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}cite/42/1983/?p=b`);
  assert.deepEqual(plain(ctx.getUrlState()), { title: "42", section: "1983", pinpoint: "b" });
});

test("getCitationPathState returns nulls for a non-citation path (title list / home)", () => {
  const { ctx } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}`);
  assert.deepEqual(plain(ctx.getCitationPathState()), { title: null, section: null });
});

test("getUrlState still returns whatever title/section string the URL names even if that title turns out not to exist -- existence is checked later by findTitleByLocationParam, not by URL parsing", () => {
  const { ctx } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}cite/9999/1/`);
  assert.deepEqual(plain(ctx.getUrlState()), { title: "9999", section: "1", pinpoint: null });
});

test("getUrlState still returns whatever section string the URL names even if that section turns out not to exist in the title", () => {
  const { ctx } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}cite/5/999999999/`);
  assert.deepEqual(plain(ctx.getUrlState()), { title: "5", section: "999999999", pinpoint: null });
});

test("restoreRedirectedPath restores the exact original path, query, and hash from a 404.html handoff", () => {
  const redirectValue = encodeURIComponent("cite/42/1983/?p=b#note-1");
  const { ctx, location, historyLog } = loadAppContext(
    `${SITE_ORIGIN}${BASE_PATH}?redirect=${redirectValue}`,
  );
  ctx.restoreRedirectedPath();

  assert.equal(location.pathname, `${BASE_PATH}cite/42/1983/`);
  assert.equal(location.search, "?p=b");
  assert.equal(location.hash, "#note-1");
  assert.equal(historyLog.length, 1);
  assert.equal(historyLog[0].method, "replaceState");

  // The corrected URL must parse the same way ordinary direct navigation
  // to /cite/42/1983/?p=b would.
  assert.deepEqual(plain(ctx.getUrlState()), { title: "42", section: "1983", pinpoint: "b" });
});

test("restoreRedirectedPath is a no-op when there is no redirect param (ordinary direct navigation)", () => {
  const { ctx, historyLog } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}cite/42/1983/`);
  ctx.restoreRedirectedPath();
  assert.equal(historyLog.length, 0);
});

test("restoreRedirectedPath never loops: after it runs once, the redirect param is gone, so a second call is a no-op", () => {
  const redirectValue = encodeURIComponent("cite/42/1983/");
  const { ctx, historyLog } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}?redirect=${redirectValue}`);

  ctx.restoreRedirectedPath();
  assert.equal(historyLog.length, 1, "first call performs exactly one replaceState");

  ctx.restoreRedirectedPath();
  assert.equal(historyLog.length, 1, "second call must not fire another replaceState -- no loop");
});

test("restoreRedirectedPath ignores a malformed redirect value instead of throwing", () => {
  const { ctx, historyLog } = loadAppContext(`${SITE_ORIGIN}${BASE_PATH}?redirect=%`);
  assert.doesNotThrow(() => ctx.restoreRedirectedPath());
  assert.equal(historyLog.length, 0);
});
