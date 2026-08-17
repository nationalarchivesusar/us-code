const APP_BASE_URL = new URL("../../", import.meta.url);
const STYLE_URL = new URL("assets/css/section-research.css", APP_BASE_URL);
const VERSION_MANIFEST_URL = new URL("data/version-history/manifest.json", APP_BASE_URL);
const REFERENCE_MANIFEST_URL = new URL("data/references/manifest.json", APP_BASE_URL);
const PUBLIC_LAWS_URL = new URL("data/public-laws.json", APP_BASE_URL);
const COURTS_CASELAW_URL = "https://nationalarchivesusar.github.io/courts/caselaw/";

const cache = new Map();
let enhancementToken = 0;

function ensureStyles() {
  if (document.querySelector('link[data-section-research="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.sectionResearch = "true";
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

function actionTargets(action) {
  return Array.isArray(action?.targets) ? action.targets : action?.target ? [action.target] : [];
}

async function sourceLawCount(title, section) {
  const payload = await loadJson(PUBLIC_LAWS_URL);
  let count = 0;
  for (const law of payload.laws || []) {
    let matched = false;
    for (const action of law.actions || []) {
      if (actionTargets(action).some((target) => String(target?.title).toLowerCase() === title.toLowerCase() && String(target?.section).toLowerCase() === section.toLowerCase())) {
        matched = true;
        break;
      }
    }
    if (!matched && (law.targets || []).some((target) => String(target?.title).toLowerCase() === title.toLowerCase() && String(target?.section).toLowerCase() === section.toLowerCase())) {
      matched = true;
    }
    if (matched) count += 1;
  }
  return count;
}

function makeToolbarButton(label, className, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `research-toolbar__button ${className}`;
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function openPanel(content, selector) {
  const panel = content.querySelector(selector);
  if (panel instanceof HTMLDetailsElement) panel.open = true;
  panel?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric" }).format(date);
}

function addMetric(container, label, value, handler) {
  if (value == null) return;
  const button = document.createElement(handler ? "button" : "span");
  button.className = "section-research-summary__metric";
  if (handler) {
    button.type = "button";
    button.addEventListener("click", handler);
  }
  button.textContent = `${value} ${label}`;
  container.appendChild(button);
}

function buildSummary(context, lawCount, versionMeta, referenceMeta) {
  const summary = document.createElement("div");
  summary.className = "section-research-summary";
  summary.dataset.sectionResearchSummary = context.key;

  const current = document.createElement("span");
  current.className = "section-research-summary__current";
  current.textContent = "Current law";
  summary.appendChild(current);

  addMetric(summary, `source law${lawCount === 1 ? "" : "s"}`, lawCount, () => openPanel(context.content, ".section-history"));
  if (versionMeta) addMetric(summary, "verified versions", versionMeta.versions, () => openPanel(context.content, ".version-history-panel"));
  if (referenceMeta?.references) addMetric(summary, "references", referenceMeta.references, () => openPanel(context.content, ".statutory-references-panel"));
  if (referenceMeta?.cited_by) addMetric(summary, "cited by", referenceMeta.cited_by, () => openPanel(context.content, ".statutory-references-panel"));

  const caseLaw = document.createElement("a");
  caseLaw.className = "section-research-summary__metric";
  caseLaw.href = COURTS_CASELAW_URL;
  caseLaw.target = "_blank";
  caseLaw.rel = "noreferrer";
  caseLaw.textContent = "Case law ↗";
  caseLaw.title = `Open the United States Courts case-law research portal for ${context.citation}`;
  summary.appendChild(caseLaw);
  return summary;
}

function makePanelSummary(label, count) {
  const summary = document.createElement("summary");
  const left = document.createElement("span");
  left.textContent = label;
  summary.appendChild(left);
  if (count != null) {
    const right = document.createElement("span");
    right.className = "section-research-panel__count";
    right.textContent = count;
    summary.appendChild(right);
  }
  return summary;
}

function pairKey(left, right) {
  return left < right ? `${left}:${right}` : `${right}:${left}`;
}

function operationsFor(record, left, right) {
  if (left === right) return [{ op: "equal", text: record.versions[left]?.text || "" }];
  const operations = record.comparisons?.[pairKey(left, right)] || [];
  if (left < right) return operations;
  return operations.map((item) => ({
    op: item.op === "insert" ? "delete" : item.op === "delete" ? "insert" : item.op,
    text: item.text,
  }));
}

function renderRedline(target, operations) {
  target.replaceChildren();
  const pre = document.createElement("div");
  pre.className = "version-history__text";
  for (const item of operations) {
    const node = item.op === "insert" ? document.createElement("ins") : item.op === "delete" ? document.createElement("del") : document.createTextNode(item.text);
    if (node.nodeType === Node.ELEMENT_NODE) node.textContent = item.text;
    pre.appendChild(node);
  }
  target.appendChild(pre);
}

function renderSideBySide(target, before, after) {
  target.replaceChildren();
  const grid = document.createElement("div");
  grid.className = "version-history__side-by-side";
  for (const [label, value] of [["Earlier state", before], ["Later state", after]]) {
    const section = document.createElement("section");
    const heading = document.createElement("h4");
    heading.textContent = label;
    const pre = document.createElement("div");
    pre.className = "version-history__text";
    pre.textContent = value || "[Section not present in this repository state]";
    section.append(heading, pre);
    grid.appendChild(section);
  }
  target.appendChild(grid);
}

function buildVersionTimeline(record) {
  const list = document.createElement("ol");
  list.className = "version-history__timeline";
  record.versions.forEach((version) => {
    const item = document.createElement("li");
    const heading = document.createElement("strong");
    heading.textContent = version.label;
    item.appendChild(heading);
    const meta = document.createElement("span");
    const pieces = [formatDate(version.committed_at), version.commit ? version.commit.slice(0, 10) : null].filter(Boolean);
    meta.textContent = pieces.length ? ` — ${pieces.join(" · ")}` : "";
    item.appendChild(meta);
    if (version.named_public_laws?.length) {
      const laws = document.createElement("div");
      laws.className = "version-history__named-laws";
      laws.textContent = `Commit explicitly names Pub. L. ${version.named_public_laws.join(", Pub. L. ")}`;
      item.appendChild(laws);
    }
    if (version.also_represents?.length) {
      const aliases = document.createElement("div");
      aliases.className = "version-history__aliases";
      aliases.textContent = `Same text also persisted through: ${version.also_represents.map((state) => state.label).join("; ")}`;
      item.appendChild(aliases);
    }
    list.appendChild(item);
  });
  return list;
}

function populateVersionPanel(panel, record) {
  const body = panel.querySelector(".section-research-panel__body");
  body.replaceChildren();
  const intro = document.createElement("p");
  intro.className = "section-research-panel__intro";
  intro.textContent = "Verified repository-state history. These are exact stored statutory texts; the site does not invent a separate text version for an enactment unless evidence preserves one.";
  body.appendChild(intro);

  const controls = document.createElement("div");
  controls.className = "version-history__controls";
  const from = document.createElement("select");
  const to = document.createElement("select");
  from.setAttribute("aria-label", "Earlier version");
  to.setAttribute("aria-label", "Later version");
  record.versions.forEach((version, index) => {
    const label = `${version.label}${version.committed_at ? ` — ${formatDate(version.committed_at)}` : ""}`;
    from.add(new Option(label, String(index)));
    to.add(new Option(label, String(index)));
  });
  from.value = "0";
  to.value = String(record.versions.length - 1);
  const mode = document.createElement("div");
  mode.className = "version-history__mode";
  const redlineButton = document.createElement("button");
  redlineButton.type = "button";
  redlineButton.className = "is-active";
  redlineButton.textContent = "Redline";
  const sideButton = document.createElement("button");
  sideButton.type = "button";
  sideButton.textContent = "Side by side";
  mode.append(redlineButton, sideButton);
  controls.append(from, to, mode);
  body.appendChild(controls);

  const display = document.createElement("div");
  display.className = "version-history__display";
  body.appendChild(display);

  let displayMode = "redline";
  function update() {
    const left = Number(from.value);
    const right = Number(to.value);
    const before = record.versions[left]?.text || "";
    const after = record.versions[right]?.text || "";
    if (displayMode === "redline") renderRedline(display, operationsFor(record, left, right));
    else renderSideBySide(display, before, after);
  }
  from.addEventListener("change", update);
  to.addEventListener("change", update);
  redlineButton.addEventListener("click", () => {
    displayMode = "redline";
    redlineButton.classList.add("is-active");
    sideButton.classList.remove("is-active");
    update();
  });
  sideButton.addEventListener("click", () => {
    displayMode = "side";
    sideButton.classList.add("is-active");
    redlineButton.classList.remove("is-active");
    update();
  });
  update();

  const timelineHeading = document.createElement("h4");
  timelineHeading.textContent = "Verified repository states";
  body.append(timelineHeading, buildVersionTimeline(record));

  const limitation = document.createElement("p");
  limitation.className = "section-research-panel__note";
  limitation.textContent = record.limitations?.join(" ") || "";
  body.appendChild(limitation);
}

function createVersionPanel(context, meta) {
  const panel = document.createElement("details");
  panel.className = "section-research-panel version-history-panel";
  panel.dataset.title = context.title;
  panel.dataset.section = context.section;
  panel.appendChild(makePanelSummary("Verified version history", `${meta.versions} versions`));
  const body = document.createElement("div");
  body.className = "section-research-panel__body";
  body.textContent = "Open to load verified historical text…";
  panel.appendChild(body);
  let loaded = false;
  panel.addEventListener("toggle", async () => {
    if (!panel.open || loaded) return;
    loaded = true;
    try {
      const record = await loadJson(new URL(meta.path, APP_BASE_URL));
      populateVersionPanel(panel, record);
    } catch (error) {
      body.textContent = "Version history could not be loaded.";
      console.error(error);
    }
  });
  return panel;
}

function referenceList(title, records) {
  const section = document.createElement("section");
  const heading = document.createElement("h4");
  heading.textContent = title;
  section.appendChild(heading);
  if (!records.length) {
    const empty = document.createElement("p");
    empty.className = "section-research-panel__intro";
    empty.textContent = "None recorded through explicit USLM links.";
    section.appendChild(empty);
    return section;
  }
  const list = document.createElement("ul");
  list.className = "statutory-references__list";
  records.forEach((record) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = new URL(`cite/${encodeURIComponent(record.title)}/${encodeURIComponent(record.section)}/`, APP_BASE_URL);
    link.textContent = record.citation;
    item.appendChild(link);
    if (record.heading) item.appendChild(document.createTextNode(` — ${record.heading}`));
    list.appendChild(item);
  });
  section.appendChild(list);
  return section;
}

function populateReferencePanel(panel, record) {
  const body = panel.querySelector(".section-research-panel__body");
  body.replaceChildren();
  const intro = document.createElement("p");
  intro.className = "section-research-panel__intro";
  intro.textContent = "Built only from explicit USLM statutory reference links in the published Code. No fuzzy text matching is used.";
  const grid = document.createElement("div");
  grid.className = "statutory-references__grid";
  grid.append(referenceList("References", record.references || []), referenceList("Referenced by", record.cited_by || []));
  body.append(intro, grid);
}

function createReferencePanel(context, meta) {
  const panel = document.createElement("details");
  panel.className = "section-research-panel statutory-references-panel";
  panel.dataset.title = context.title;
  panel.dataset.section = context.section;
  panel.appendChild(makePanelSummary("Statutory references", `${meta.references} out · ${meta.cited_by} in`));
  const body = document.createElement("div");
  body.className = "section-research-panel__body";
  body.textContent = "Open to load statutory references…";
  panel.appendChild(body);
  let loaded = false;
  panel.addEventListener("toggle", async () => {
    if (!panel.open || loaded) return;
    loaded = true;
    try {
      const record = await loadJson(new URL(meta.path, APP_BASE_URL));
      populateReferencePanel(panel, record);
    } catch (error) {
      body.textContent = "Statutory references could not be loaded.";
      console.error(error);
    }
  });
  return panel;
}

function placePanel(context, panel) {
  const pager = context.content.querySelector(".section-pagination");
  if (pager) pager.before(panel);
  else context.content.appendChild(panel);
}

async function enhanceCurrentSection() {
  const context = currentContext();
  if (!context) return;
  const token = ++enhancementToken;
  const header = context.content.querySelector(".section-header");
  const toolbar = header?.querySelector(".research-toolbar");
  if (!header || !toolbar) return;
  if (header.querySelector(`[data-section-research-summary="${CSS.escape(context.key)}"]`)) return;

  try {
    const [versionManifest, referenceManifest, lawCount] = await Promise.all([
      loadJson(VERSION_MANIFEST_URL).catch(() => ({ sections: {} })),
      loadJson(REFERENCE_MANIFEST_URL).catch(() => ({ sections: {} })),
      sourceLawCount(context.title, context.section).catch(() => 0),
    ]);
    if (token !== enhancementToken) return;
    const versionMeta = versionManifest.sections?.[context.key] || null;
    const referenceMeta = referenceManifest.sections?.[context.key] || null;

    const summary = buildSummary(context, lawCount, versionMeta, referenceMeta);
    toolbar.before(summary);

    if (versionMeta) {
      const panel = createVersionPanel(context, versionMeta);
      placePanel(context, panel);
      toolbar.appendChild(makeToolbarButton("Version history", "section-research__versions-button", () => openPanel(context.content, ".version-history-panel")));
    }
    if (referenceMeta) {
      const panel = createReferencePanel(context, referenceMeta);
      placePanel(context, panel);
      toolbar.appendChild(makeToolbarButton("References", "section-research__references-button", () => openPanel(context.content, ".statutory-references-panel")));
    }
  } catch (error) {
    console.error("Unable to enhance section research metadata", error);
  }
}

function initialize() {
  const content = document.getElementById("section-content");
  if (!content) return;
  const observer = new MutationObserver(() => queueMicrotask(enhanceCurrentSection));
  observer.observe(content, { childList: true, subtree: true });
  enhanceCurrentSection();
}

ensureStyles();
initialize();
