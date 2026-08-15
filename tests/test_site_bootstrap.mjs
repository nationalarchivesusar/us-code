import assert from "node:assert/strict";
import { test } from "node:test";
import vm from "node:vm";
import fs from "node:fs";

const SCRIPT = fs.readFileSync(new URL("../assets/js/site-bootstrap.js", import.meta.url), "utf8");
const ORIGIN = "https://nationalarchivesusar.github.io";
const BASE = `${ORIGIN}/us-code/`;

function makeAnchor(href) {
  return {
    rawHref: href,
    href,
    getAttribute(name) {
      return name === "href" ? this.rawHref : null;
    },
  };
}

function runBootstrap(href, { storedTheme = null, prefersDark = false, anchors = [] } = {}) {
  let current = new URL(href);
  const historyLog = [];
  const replaceLog = [];
  const listeners = new Map();
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
      currentScript: { src: `${BASE}assets/js/site-bootstrap.js` },
      documentElement: { dataset: {} },
      addEventListener(name, callback) { listeners.set(name, callback); },
      querySelectorAll() { return anchors; },
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
  return { sandbox, current, historyLog, replaceLog, storage, listeners, anchors };
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

test("header and footer page links are rooted at the app while hash-only links are left alone", () => {
  const criminal = makeAnchor("criminal-law.html");
  const publicLaws = makeAnchor("public-laws.html");
  const footerHome = makeAnchor("./");
  const home = makeAnchor("./");
  const hash = makeAnchor("#search");
  const result = runBootstrap(`${BASE}cite/18/111/`, {
    anchors: [criminal, publicLaws, footerHome, home, hash],
  });
  result.listeners.get("DOMContentLoaded")();
  assert.equal(criminal.href, `${BASE}criminal-law.html`);
  assert.equal(publicLaws.href, `${BASE}public-laws.html`);
  assert.equal(footerHome.href, BASE);
  assert.equal(home.href, BASE);
  assert.equal(hash.href, "#search");
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
