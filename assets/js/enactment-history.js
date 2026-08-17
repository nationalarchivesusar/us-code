const APP_BASE_URL = new URL("../../", import.meta.url);
const MANIFEST_URL = new URL("data/enactment-history/manifest.json", APP_BASE_URL);
const STYLE_URL = new URL("assets/css/enactment-history.css", APP_BASE_URL);

const cache = new Map();
let token = 0;

function ensureStyles() {
  if (document.querySelector('link[data-enactment-history="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.enactmentHistory = "true";
  document.head.appendChild(link);
}

async function loadJson(url) {
  const key = url.toString();
  if (!cache.has(key)) {
    cache.set(key, fetch(url, { cache: "no-cache" }).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status} for ${key}`);
      return response.json();
    }));
  }
  return cache.get(key);
}

function normalizeSection(value) {
  return String(value || "").replace(/^\s*§+\s*/, "").replace(/[.\s]+$/, "").trim();
}

function normalizeTitle(value) {
  const match = String(value || "").match(/\bTitle\s+([0-9]+[A-Za-z]?)\b/i);
  return match ? match[1] : String(value || "").trim();
}

function currentContext() {
  const content = document.getElementById("section-content");
  const number = content?.querySelector(".section-number");
  if (!content || content.hidden || !number) return null;

  const relative = window.location.pathname.slice(APP_BASE_URL.pathname.length).replace(/^\/+|\/+$/g, "");
  const parts = relative.split("/").filter(Boolean);
  let title = null;
  let section = null;
  if (parts[0] === "cite" && parts.length >= 3) {
    try {
      title = decodeURIComponent(parts[1]);
      section = decodeURIComponent(parts[2]);
    } catch {
      title = null;
      section = null;
    }
  }
  if (!title) {
    const active = document.querySelector(".title-item.active .title-item__label");
    title = normalizeTitle(active?.textContent || "");
  }
  if (!section) section = normalizeSection(number.textContent);
  if (!title || !section) return null;
  return {
    title,
    section,
    key: `${title.toLowerCase()}:${section.toLowerCase()}`,
    citation: `${title} U.S.C. § ${section}`,
    content,
  };
}

function openPanel(content) {
  const panel = content.querySelector(".enactment-history-panel");
  if (panel instanceof HTMLDetailsElement) panel.open = true;
  panel?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function addMetric(summary, meta, context) {
  if (summary.querySelector(".enactment-history__metric")) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "section-research-summary__metric enactment-history__metric";
  const exact = Number(meta.exact_enactment_pair_count || 0);
  button.textContent = exact
    ? `${meta.event_count} enactment event${meta.event_count === 1 ? "" : "s"} · ${exact} exact pair${exact === 1 ? "" : "s"}`
    : `${meta.event_count} enactment event${meta.event_count === 1 ? "" : "s"}`;
  button.addEventListener("click", () => openPanel(context.content));
  const caseLaw = summary.querySelector("a.section-research-summary__metric");
  if (caseLaw) caseLaw.before(button);
  else summary.appendChild(button);
}

function addToolbarButton(toolbar, context) {
  if (toolbar.querySelector(".enactment-history__toolbar-button")) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "research-toolbar__button enactment-history__toolbar-button";
  button.textContent = "Enactment history";
  button.addEventListener("click", () => openPanel(context.content));
  toolbar.appendChild(button);
}

function makeSummary(meta) {
  const summary = document.createElement("summary");
  const left = document.createElement("span");
  left.textContent = "Verified enactment history";
  const right = document.createElement("span");
  right.className = "section-research-panel__count";
  const exact = Number(meta.exact_enactment_pair_count || 0);
  right.textContent = exact
    ? `${meta.event_count} event${meta.event_count === 1 ? "" : "s"} · ${exact} exact pair${exact === 1 ? "" : "s"}`
    : `${meta.event_count} event${meta.event_count === 1 ? "" : "s"}`;
  summary.append(left, right);
  return summary;
}

function compactEvidence(value, max = 260) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1).trimEnd()}…`;
}

function eventHeading(event) {
  const wrapper = document.createElement("div");
  wrapper.className = "enactment-event__heading";
  const citation = event.url ? document.createElement("a") : document.createElement("strong");
  if (event.url) {
    citation.href = event.url;
    citation.target = "_blank";
    citation.rel = "noreferrer";
  }
  citation.textContent = event.citation || `Pub. L. ${event.public_law}`;
  wrapper.appendChild(citation);
  if (event.title) {
    const title = document.createElement("span");
    title.textContent = event.title;
    wrapper.appendChild(title);
  }
  return wrapper;
}

function renderExactPair(event) {
  const snapshot = event.exact_text_snapshot;
  if (!event.exact_text_snapshot_available || !snapshot) return null;

  const details = document.createElement("details");
  details.className = "enactment-event__exact-pair";
  const summary = document.createElement("summary");
  summary.textContent = "Exact before / after statutory text";

  const note = document.createElement("p");
  note.className = "enactment-event__exact-note";
  note.textContent = "High-confidence attribution: this Public Law is the sole verified substantive enactment event and sole published Public Law associated with the section between the fixed baseline and current repository states.";

  const grid = document.createElement("div");
  grid.className = "enactment-event__exact-grid";
  const states = [
    ["Before enactment", snapshot.baseline],
    ["After enactment", snapshot.current],
  ];
  for (const [label, state] of states) {
    const column = document.createElement("section");
    const heading = document.createElement("h5");
    heading.textContent = label;
    const text = document.createElement("div");
    text.className = "enactment-event__exact-text";
    text.textContent = state?.present === false
      ? "[Section not present in this verified repository state]"
      : state?.text || "[Verified text unavailable]";
    const hash = document.createElement("div");
    hash.className = "enactment-event__exact-hash";
    hash.textContent = state?.sha256 ? `SHA-256 ${state.sha256}` : "";
    column.append(heading, text);
    if (hash.textContent) column.appendChild(hash);
    grid.appendChild(column);
  }
  details.append(summary, note, grid);
  return details;
}

function renderVerification(event) {
  const details = document.createElement("details");
  details.className = "enactment-event__verification";
  const summary = document.createElement("summary");
  summary.textContent = "Verification details";

  const facts = document.createElement("dl");
  facts.className = "enactment-event__verification-facts";
  const rows = [
    ["Audit action", (event.audit_action_ids || []).join(", ")],
    ["Changed XML nodes", String((event.changed_node_ids || []).length)],
    ["Evidence hash", event.evidence_sha256 || ""],
  ].filter(([, value]) => value);
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    facts.append(dt, dd);
  }
  details.append(summary, facts);
  return details;
}

function eventCard(event) {
  const item = document.createElement("li");
  item.className = "enactment-event";
  item.appendChild(eventHeading(event));

  const labels = document.createElement("div");
  labels.className = "enactment-event__labels";
  for (const label of event.change_labels || []) {
    const badge = document.createElement("span");
    badge.textContent = label;
    labels.appendChild(badge);
  }
  if (event.exact_text_snapshot_available) {
    const badge = document.createElement("span");
    badge.className = "enactment-event__label--exact";
    badge.textContent = "exact text pair";
    labels.appendChild(badge);
  }
  item.appendChild(labels);

  const facts = document.createElement("dl");
  facts.className = "enactment-event__facts";
  const rows = [
    ["Source provision", (event.source_provisions || []).join("; ")],
    ["Codification action", (event.operations || []).join("; ")],
    ["Affected subsection", (event.subsection_paths || []).join(", ")],
  ].filter(([, value]) => value);
  for (const [label, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    facts.append(dt, dd);
  }
  if (rows.length) item.appendChild(facts);

  const quotation = compactEvidence(event.source_quotations?.[0]);
  if (quotation) {
    const source = document.createElement("p");
    source.className = "enactment-event__source";
    const label = document.createElement("strong");
    label.textContent = "Source evidence: ";
    source.append(label, document.createTextNode(quotation));
    item.appendChild(source);
  }

  const exact = renderExactPair(event);
  if (exact) item.appendChild(exact);
  item.appendChild(renderVerification(event));
  return item;
}

function populatePanel(panel, record) {
  const body = panel.querySelector(".section-research-panel__body");
  body.replaceChildren();

  const intro = document.createElement("p");
  intro.className = "section-research-panel__intro";
  intro.textContent = "Validated law-by-law codification events for this section. These events identify what Public Law acted on the Code and how the codification audit verified that operation.";

  const warning = document.createElement("p");
  warning.className = "section-research-panel__note enactment-history__limitation";
  warning.textContent = "Audit summaries and source quotations are evidence, not statutory text. Exact before/after text appears only where one Public Law is uniquely attributable under both the audit timeline and finalized Public Law crosswalk; otherwise use Verified version history for exact repository-state text.";

  const list = document.createElement("ol");
  list.className = "enactment-history__timeline";
  for (const event of record.events || []) list.appendChild(eventCard(event));
  body.append(intro, warning, list);
}

function createPanel(context, meta) {
  const panel = document.createElement("details");
  panel.className = "section-research-panel enactment-history-panel";
  panel.dataset.title = context.title;
  panel.dataset.section = context.section;
  panel.appendChild(makeSummary(meta));
  const body = document.createElement("div");
  body.className = "section-research-panel__body";
  body.textContent = "Open to load verified enactment events…";
  panel.appendChild(body);

  let loaded = false;
  panel.addEventListener("toggle", async () => {
    if (!panel.open || loaded) return;
    loaded = true;
    try {
      const record = await loadJson(new URL(meta.path, APP_BASE_URL));
      populatePanel(panel, record);
    } catch (error) {
      body.textContent = "Enactment history could not be loaded.";
      console.error(error);
    }
  });
  return panel;
}

function placePanel(context, panel) {
  const references = context.content.querySelector(".statutory-references-panel");
  const pager = context.content.querySelector(".section-pagination");
  if (references) references.before(panel);
  else if (pager) pager.before(panel);
  else context.content.appendChild(panel);
}

async function enhance() {
  const context = currentContext();
  if (!context) return;
  const currentToken = ++token;
  const header = context.content.querySelector(".section-header");
  const toolbar = header?.querySelector(".research-toolbar");
  const summary = header?.querySelector(".section-research-summary");
  if (!header || !toolbar || !summary) return;
  if (context.content.querySelector(`.enactment-history-panel[data-title="${CSS.escape(context.title)}"][data-section="${CSS.escape(context.section)}"]`)) return;

  try {
    const manifest = await loadJson(MANIFEST_URL);
    if (currentToken !== token) return;
    const meta = manifest.sections?.[context.key];
    if (!meta) return;
    addMetric(summary, meta, context);
    addToolbarButton(toolbar, context);
    placePanel(context, createPanel(context, meta));
  } catch (error) {
    console.error("Unable to load enactment history metadata", error);
  }
}

function initialize() {
  const content = document.getElementById("section-content");
  if (!content) return;
  const observer = new MutationObserver(() => queueMicrotask(enhance));
  observer.observe(content, { childList: true, subtree: true });
  enhance();
}

ensureStyles();
initialize();
