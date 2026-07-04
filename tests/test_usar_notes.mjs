// Regression tests for the USAR-note detection, badge labeling, and
// display-ordering logic in assets/js/app.js (Phase 4 of the post-
// codification cleanup). Run with: node --test tests/test_usar_notes.mjs
//
// app.js is written to run in a browser and is not a module, so it is
// loaded here with Node's vm module against a minimal fake DOM that only
// implements what app.js touches at parse time (a no-op
// document.addEventListener("DOMContentLoaded", ...) registration) and
// what the functions under test need at call time (nodeType constants,
// getAttribute). This avoids adding a browser/DOM test dependency (e.g.
// jsdom) to a project that otherwise has no JS package manifest.
import assert from "node:assert/strict";
import { test } from "node:test";
import vm from "node:vm";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const APP_JS = fs.readFileSync(path.join(ROOT, "assets", "js", "app.js"), "utf-8");

function loadAppContext() {
  const sandbox = {
    document: {
      addEventListener() {},
      getElementById() { return null; },
      querySelectorAll() { return []; },
      querySelector() { return null; },
      documentElement: { dataset: {} },
    },
    window: {},
    location: { href: "http://localhost/index.html" },
    localStorage: { getItem() { return null; }, setItem() {} },
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
    Node: { ELEMENT_NODE: 1, TEXT_NODE: 3 },
    URL,
    console,
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(APP_JS, sandbox, { filename: "assets/js/app.js" });
  return sandbox;
}

const USLM_NS = "http://xml.house.gov/schemas/uslm/1.0";

function fakeNote({ id, topic }) {
  return {
    nodeType: 1,
    namespaceURI: USLM_NS,
    localName: "note",
    getAttribute(name) {
      if (name === "id") return id;
      if (name === "topic") return topic || "";
      return null;
    },
  };
}

function fakeOrdinaryNode(localName = "note") {
  return {
    nodeType: 1,
    namespaceURI: USLM_NS,
    localName,
    getAttribute(name) {
      if (name === "id") return "id7abea487-76ce-11f0-b9ee-f4c4e6720c71";
      return null;
    },
  };
}

test("isUsarNoteElement is true only for note elements with an rp- id", () => {
  const ctx = loadAppContext();
  assert.equal(ctx.isUsarNoteElement(fakeNote({ id: "rp-abc123" })), true);
  assert.equal(ctx.isUsarNoteElement(fakeOrdinaryNode()), false);
});

test("isUsarNoteElement never flags real OLRC GUID-style ids", () => {
  const ctx = loadAppContext();
  // Real OLRC note ids look like "id7abea487-76ce-11f0-b9ee-f4c4e6720c71" --
  // never "rp-" prefixed, since that prefix is exclusive to this project's
  // codification tooling (tools/rp_codifier.py's make_id()).
  const realNote = fakeNote({ id: "id7abea487-76ce-11f0-b9ee-f4c4e6720c71" });
  assert.equal(ctx.isUsarNoteElement(realNote), false);
});

test("isUsarNoteElement ignores non-note elements and non-element nodes", () => {
  const ctx = loadAppContext();
  assert.equal(ctx.isUsarNoteElement(fakeOrdinaryNode("heading")), false);
  assert.equal(ctx.isUsarNoteElement({ nodeType: 3 }), false);
  assert.equal(ctx.isUsarNoteElement(null), false);
});

test("usarNoteBadgeLabel maps known topics to specific badge text", () => {
  const ctx = loadAppContext();
  assert.equal(ctx.usarNoteBadgeLabel(fakeNote({ id: "rp-x", topic: "amendments" })), "USAR Amendment Note");
  assert.equal(ctx.usarNoteBadgeLabel(fakeNote({ id: "rp-x", topic: "miscellaneous" })), "USAR Statutory Note");
  assert.equal(ctx.usarNoteBadgeLabel(fakeNote({ id: "rp-x", topic: "transfer" })), "USAR Transfer Note");
  assert.equal(ctx.usarNoteBadgeLabel(fakeNote({ id: "rp-x", topic: "priorProvisions" })), "USAR Prior-Provisions Note");
  assert.equal(ctx.usarNoteBadgeLabel(fakeNote({ id: "rp-x", topic: "removalDescription" })), "USAR Removal Note");
});

test("usarNoteBadgeLabel falls back to a generic label for unknown topics", () => {
  const ctx = loadAppContext();
  assert.equal(ctx.usarNoteBadgeLabel(fakeNote({ id: "rp-x", topic: "somethingNew" })), "USAR Public Law Note");
  assert.equal(ctx.usarNoteBadgeLabel(fakeNote({ id: "rp-x" })), "USAR Public Law Note");
});

test("orderNotesForDisplay puts USAR notes first, preserving relative order in each group", () => {
  const ctx = loadAppContext();
  const ordinary1 = fakeOrdinaryNode();
  const usar1 = fakeNote({ id: "rp-1", topic: "amendments" });
  const ordinary2 = fakeOrdinaryNode();
  const usar2 = fakeNote({ id: "rp-2", topic: "amendments" });
  const ordinary3 = fakeOrdinaryNode();

  const result = ctx.orderNotesForDisplay([ordinary1, usar1, ordinary2, usar2, ordinary3]);

  assert.deepEqual(result, [usar1, usar2, ordinary1, ordinary2, ordinary3]);
});

test("orderNotesForDisplay leaves an all-ordinary notes list unchanged in order", () => {
  const ctx = loadAppContext();
  const a = fakeOrdinaryNode();
  const b = fakeOrdinaryNode();
  const c = fakeOrdinaryNode();
  assert.deepEqual(ctx.orderNotesForDisplay([a, b, c]), [a, b, c]);
});

test("orderNotesForDisplay handles a notes list with only USAR notes", () => {
  const ctx = loadAppContext();
  const usar1 = fakeNote({ id: "rp-1" });
  const usar2 = fakeNote({ id: "rp-2" });
  assert.deepEqual(ctx.orderNotesForDisplay([usar1, usar2]), [usar1, usar2]);
});

// Regression coverage for a rendering defect found while spot-checking
// cleaned reserved sections (Phase 7): repealed sections' own <num> text
// already starts with a literal "[" (e.g. "[§ 792.", a real, pre-existing
// OLRC print convention -- see 28 U.S.C. 792/793 status="repealed"), which
// the document-title/share-label builders used to fail to strip alongside
// the "§" symbol, producing a doubled "§ [§ 792." instead of "§ 792.".

const SECTION_SIGN = String.fromCodePoint(0x00a7);
const NARROW_NBSP = String.fromCodePoint(0x202f);

function expectedCitation(titleNumber, sectionNumber) {
  return `${titleNumber} U.S. Code ${SECTION_SIGN}${NARROW_NBSP}${sectionNumber}.`;
}

test("formatSectionPageTitle strips a leading bracket on repealed section numbers", () => {
  const ctx = loadAppContext();
  const metadata = { number: "28" };
  const sectionNode = { number: `[${SECTION_SIGN} 792.`, heading: "[Reserved]" };
  assert.equal(
    ctx.formatSectionPageTitle(metadata, sectionNode),
    `${expectedCitation("28", "792")}
[Reserved].`,
  );
});

test("formatSectionPageTitle strips a plain leading § with no bracket", () => {
  const ctx = loadAppContext();
  const metadata = { number: "28" };
  const sectionNode = { number: `${SECTION_SIGN} 791.`, heading: "[Reserved]" };
  assert.equal(
    ctx.formatSectionPageTitle(metadata, sectionNode),
    `${expectedCitation("28", "791")}
[Reserved].`,
  );
});

test("formatSectionShareLabel strips a leading bracket on repealed section numbers", () => {
  const ctx = loadAppContext();
  const sectionNode = { number: "[§ 792.", heading: "[Reserved]" };
  assert.equal(ctx.formatSectionShareLabel(sectionNode), "Section 792 — [Reserved]");
});
