const APP_BASE_URL = new URL("../../", import.meta.url);
const REFERENCES_URL = new URL("data/research/references.json", APP_BASE_URL);
const PUBLIC_LAWS_URL = new URL("data/public-laws.json", APP_BASE_URL);
const HISTORY_MANIFEST_URL = new URL("data/section-history/manifest.json", APP_BASE_URL);
const STYLE_URL = new URL("assets/css/section-research.css", APP_BASE_URL);
const COURTS_BASE = "https://nationalarchivesusar.github.io/courts/";

let referencesPromise;
let lawsPromise;
let historyPromise;
let serial = 0;

function ensureStylesheet() {
  if (document.querySelector('link[data-section-research="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.sectionResearch = "true";
  document.head.appendChild(link);
}

function normalizeSection(value) {
  return String(value || "").replace(/^\s*§+\s*/, "").replace(/[.\s]+$/, "").trim();
}

function normalizeTitle(value) {
  const match = String(value || "").match(/\bTitle\s+([0-9]+[A-Za-z]?)\b/i);
  const raw = match ? match[1] : String(value || "").trim();
  return raw.replace(/^0+(?=\d)/, "");
}

function key(title, section) {
  return `${normalizeTitle(title).toLowerCase()}:${normalizeSection(section).toLowerCase()}`;
}

function currentContext() {
  const sectionContent = document.getElementById("section-content");
  const number = sectionContent?.querySelector(".section-number");
  if (!sectionContent || sectionContent.hidden || !number) return null;

  const relative = window.location.pathname.slice(APP_BASE_URL.pathname.length).replace(/^\/+|\/+$/g, "");
  const parts = relative.split("/").filter(Boolean);
  let routeTitle = null;
  let routeSection = null;
  if (parts[0] === "cite" && parts.length >= 3) {
    try {
      routeTitle = decodeURIComponent(parts[1]);
      routeSection = decodeURIComponent(parts[2]);
    } catch {
      routeTitle = null;
      routeSection = null;
    }
  }

  const activeTitle = document.querySelector(".title-item.active");
  const label = activeTitle?.querySelector(".title-item__label")?.textContent || "";
  const title = routeTitle || normalizeTitle(label);
  const section = routeSection || normalizeSection(number.textContent);
  if (!title || !section) return null;
  return {
    title: normalizeTitle(title),
    section: normalizeSection(section),
    citation: `${normalizeTitle(title)} U.S.C. § ${normalizeSection(section)}`,
    sectionContent,
  };
}

function loadJson(url) {
  return fetch(url, { cache: "no-cache" }).then((response) => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  });
}

function loadReferences() {
  if (!referencesPromise) referencesPromise = loadJson(REFERENCES_URL);
  return referencesPromise;
}

function loadLaws() {
  if (!lawsPromise) lawsPromise = loadJson(PUBLIC_LAWS_URL);
  return lawsPromise;
}

function loadHistory() {
  if (!historyPromise) historyPromise = loadJson(HISTORY_MANIFEST_URL);
  return historyPromise;
}

function actionTargets(action) {
  if (Array.isArray(action?.targets)) return action.targets;
  return action?.target ? [action.target] : [];
}

function targetMatches(target, context) {
  return String(target?.title || "").toLowerCase() === context.title.toLowerCase()
    && String(target?.section || "").toLowerCase() === context.section.toLowerCase();
}

function lawsForSection(payload, context) {
  return (payload?.laws || []).filter((law) => {
    if ((law.targets || []).some((target) => targetMatches(target, context))) return true;
    return (law.actions || []).some((action) => actionTargets(action).some((target) => targetMatches(target, context)));
  });
}

function relationshipLink(item) {
  const link = document.createElement("a");
  link.className = "section-relations__link";
  link.href = new URL(item.url, APP_BASE_URL).toString();
  const citation = document.createElement("span");
  citation.className = "section-relations__citation";
  citation.textContent = item.citation;
  link.appendChild(citation);
  if (item.heading) {
    const heading = document.createElement("span");
    heading.className = "section-relations__heading";
    heading.textContent = item.heading;
    link.appendChild(heading);
  }
  return link;
}

function relationshipColumn(title, items, emptyText) {
  const section = document.createElement("section");
  section.className = "section-relations__column";
  const heading = document.createElement("h4");
  heading.textContent = `${title} (${items.length})`;
  section.appendChild(heading);
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "section-relations__empty";
    empty.textContent = emptyText;
    section.appendChild(empty);
    return section;
  }
  const list = document.createElement("ul");
  items.forEach((item) => {
    const li = document.createElement("li");
    li.appendChild(relationshipLink(item));
    list.appendChild(li);
  });
  section.appendChild(list);
  return section;
}

function buildRelationsPanel(context, graphRecord) {
  const existing = context.sectionContent.querySelector(".section-relations");
  existing?.remove();

  const details = document.createElement("details");
  details.className = "section-relations";
  details.dataset.title = context.title;
  details.dataset.section = context.section;
  const summary = document.createElement("summary");
  summary.innerHTML = `<span>References & cited by</span><span>${graphRecord.references.length + graphRecord.cited_by.length} relationship${graphRecord.references.length + graphRecord.cited_by.length === 1 ? "" : "s"}</span>`;
  details.appendChild(summary);

  const body = document.createElement("div");
  body.className = "section-relations__body";
  body.append(
    relationshipColumn("References", graphRecord.references, "No explicit U.S. Code section references are encoded in this section."),
    relationshipColumn("Cited by", graphRecord.cited_by, "No other published U.S. Code section explicitly references this section."),
  );

  const note = document.createElement("p");
  note.className = "section-relations__note";
  note.textContent = "Relationships are derived from explicit USLM section-reference markup; plain-text citations are not inferred.";
  body.appendChild(note);
  details.appendChild(body);

  const history = context.sectionContent.querySelector(".section-history");
  if (history) history.after(details);
  else context.sectionContent.appendChild(details);
}

function badge(label, value, modifier = "") {
  const span = document.createElement("span");
  span.className = `section-metadata__item${modifier ? ` section-metadata__item--${modifier}` : ""}`;
  const strong = document.createElement("strong");
  strong.textContent = String(value);
  span.append(strong, document.createTextNode(` ${label}`));
  return span;
}

function buildMetadata(context, { lawCount, references, citedBy, comparison }) {
  context.sectionContent.querySelector(".section-metadata")?.remove();
  const meta = document.createElement("div");
  meta.className = "section-metadata";
  meta.dataset.title = context.title;
  meta.dataset.section = context.section;
  meta.appendChild(badge("Current", "", "current"));
  meta.appendChild(badge(lawCount === 1 ? "Public Law" : "Public Laws", lawCount));
  meta.appendChild(badge(references === 1 ? "reference" : "references", references));
  meta.appendChild(badge("cited by", citedBy));
  if (comparison) {
    const label = comparison.status === "added" ? "added since baseline" : comparison.status === "amended" ? "amended since baseline" : comparison.status;
    meta.appendChild(badge(label, "Verified", "history"));
  }

  const courtLink = document.createElement("a");
  courtLink.className = "section-metadata__courts";
  courtLink.href = new URL("docket/", COURTS_BASE).toString();
  courtLink.textContent = "Search court records ↗";
  courtLink.title = `Search United States Courts records for ${context.citation}`;
  meta.appendChild(courtLink);

  const header = context.sectionContent.querySelector(".section-header");
  if (header) header.after(meta);
  else context.sectionContent.prepend(meta);
}

async function enhance() {
  const context = currentContext();
  if (!context) return;
  const currentSerial = ++serial;

  try {
    const [graph, lawPayload, history] = await Promise.all([
      loadReferences().catch(() => ({ sections: {} })),
      loadLaws().catch(() => ({ laws: [] })),
      loadHistory().catch(() => ({ sections: {} })),
    ]);
    if (currentSerial !== serial || !context.sectionContent.isConnected) return;

    const graphRecord = graph.sections?.[key(context.title, context.section)] || {
      title: context.title,
      section: context.section,
      citation: context.citation,
      references: [],
      cited_by: [],
    };
    const laws = lawsForSection(lawPayload, context);
    const comparison = history.sections?.[key(context.title, context.section)] || null;

    buildMetadata(context, {
      lawCount: laws.length,
      references: graphRecord.references.length,
      citedBy: graphRecord.cited_by.length,
      comparison,
    });
    buildRelationsPanel(context, graphRecord);
  } catch (error) {
    console.error("Unable to enhance section research metadata", error);
  }
}

function initialize() {
  ensureStylesheet();
  const sectionContent = document.getElementById("section-content");
  if (!sectionContent) return;
  let queued = false;
  const schedule = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      enhance();
    });
  };
  new MutationObserver(schedule).observe(sectionContent, { childList: true, subtree: true });
  schedule();
}

initialize();
