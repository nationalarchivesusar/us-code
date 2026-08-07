import assert from "node:assert/strict";
import { test } from "node:test";
import vm from "node:vm";
import fs from "node:fs";

const SCRIPT = fs.readFileSync(new URL("../assets/js/site-bootstrap.js", import.meta.url), "utf8");
const ORIGIN = "https://nationalarchivesusar.github.io";
const BASE = `${ORIGIN}/us-code/`;

function runBootstrap(href, { storedTheme = null, prefersDark = false } = {}) {
  let current = new URL(href);
  const historyLog = [];
  const replaceLog = [];
  const storage = new Map();
  if (storedTheme !== null) storage.set("usc-theme", storedTheme);

  const location = {
    get href() { return current.href; },
    get pathname() { return current.pathname; },
    get search() { return current.search; },
    replace(url) {
      current = new URL(url, current);
      replaceLog.push(current.href);
    },
  };

  const sandbox = {
    document: {
      baseURI: BASE,
      documentElement: { dataset: {} },
    },
    window: null,
    location,
    history: {
      replaceState(_state, _title, url) {
        current = new URL(url, current);
        historyLog.push(current.href);
      },
    },
    localStorage: {
      getItem(key) { return storage.has(key) ? storage.get(key) : null; },
      setItem(key, value) { storage.set(key, value); },
    },
    matchMedia() { return { matches: prefersDark }; },
    URL,
    URLSearchParams,
    Set,
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(SCRIPT, sandbox, { filename: "site-bootstrap.js" });
  return { sandbox, current, historyLog, replaceLog, storage };
}

test("fresh visitors default to System and resolve the OS dark preference before CSS loads", () => {
  const result = runBootstrap(BASE, { prefersDark: true });
  assert.equal(result.storage.get("usc-theme"), "system");
  assert.equal(result.sandbox.document.documentElement.dataset.theme, "dark");
});

test("an explicit saved light preference wins over a dark OS preference", () => {
  const result = runBootstrap(BASE, { storedTheme: "light", prefersDark: true });
  assert.equal(result.storage.get("usc-theme"), "light");
  assert.equal(result.sandbox.document.documentElement.dataset.theme, "light");
});

test("title-only social routes normalize to the app's existing title query state", () => {
  const result = runBootstrap(`${BASE}?redirect=${encodeURIComponent("cite/18/")}`);
  assert.equal(result.current.href, `${BASE}?t=18`);
  assert.equal(result.historyLog.length, 1);
});

test("valid section citation redirects remain available for app.js to restore", () => {
  const redirect = encodeURIComponent("cite/18/111/?p=b#note-1");
  const result = runBootstrap(`${BASE}?redirect=${redirect}`);
  assert.equal(result.current.searchParams.get("redirect"), "cite/18/111/?p=b#note-1");
  assert.equal(result.historyLog.length, 0);
  assert.equal(result.replaceLog.length, 0);
});

test("legacy malformed nested navigation to Criminal Law escapes the citation route", () => {
  const redirect = encodeURIComponent("cite/18/111/criminal-law.html");
  const result = runBootstrap(`${BASE}?redirect=${redirect}`);
  assert.deepEqual(result.replaceLog, [`${BASE}criminal-law.html`]);
});

test("unknown extra citation path segments are rejected instead of reopening the old section", () => {
  const redirect = encodeURIComponent("cite/18/111/not-a-route");
  const result = runBootstrap(`${BASE}?redirect=${redirect}`);
  assert.equal(result.current.href, BASE);
  assert.equal(result.historyLog.length, 1);
});
