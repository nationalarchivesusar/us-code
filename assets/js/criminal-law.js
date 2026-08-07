const THEME_STORAGE_KEY = "usc-theme";
const API_BASE = "data/api/v1/criminal-law/";

const state = {
  theme: "system",
  query: "",
  source: "all",
  records: [],
  filtered: [],
  manifest: null,
  title18Details: new Map(),
  title18SearchReady: false,
  title18SearchPromise: null,
};

const elements = {
  themeButtons: document.querySelectorAll("[data-theme-choice]"),
  query: document.getElementById("criminal-query"),
  source: document.getElementById("criminal-source"),
  results: document.getElementById("criminal-law-results"),
  loading: document.getElementById("criminal-loading"),
  empty: document.getElementById("criminal-empty"),
  summary: document.getElementById("result-summary"),
  revision: document.getElementById("api-revision"),
  statTitle18: document.getElementById("stat-title18"),
  statFcc: document.getElementById("stat-fcc"),
  statDc: document.getElementById("stat-dc"),
  statCharges: document.getElementById("stat-charges"),
};

const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");

function resolveTheme(choice) {
  if (choice === "system") return prefersDark.matches ? "dark" : "light";
  return choice === "dark" ? "dark" : "light";
}

function applyTheme(choice) {
  const normalized = ["system", "light", "dark"].includes(choice) ? choice : "system";
  state.theme = normalized;
  document.documentElement.dataset.theme = resolveTheme(normalized);
  elements.themeButtons.forEach((button) => {
    const active = button.dataset.themeChoice === normalized;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function initializeTheme() {
  applyTheme(localStorage.getItem(THEME_STORAGE_KEY) || "system");
  elements.themeButtons.forEach((button) => button.addEventListener("click", () => {
    const choice = button.dataset.themeChoice || "system";
    localStorage.setItem(THEME_STORAGE_KEY, choice);
    applyTheme(choice);
  }));
  prefersDark.addEventListener("change", () => {
    if (state.theme === "system") applyTheme("system");
  });
}

function normalize(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[§.,;:()[\]{}'“”‘’]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function sourceLabel(source) {
  return {
    "federal-criminal-code-2025": "Federal Criminal Code",
    "dc-criminal-code-federalized": "Federalized D.C. Code",
    title18: "Title 18 U.S.C.",
  }[source] || source;
}

function prepareRecord(record) {
  record.haystack = normalize([
    record.citation,
    record.formalCitation,
    record.heading,
    record.text,
    record.chapterHeading,
    record.sourceLabel,
    record.status,
    record.offenseClass ? `class ${record.offenseClass}` : "",
  ].filter(Boolean).join(" "));
  return record;
}

function makeLocalRecords(payload, source) {
  const isFederal = source === "federal-criminal-code-2025";
  return (payload.sections || [])
    .filter((section) => section.is_offense === true)
    .map((section) => prepareRecord({
      id: section.id || `${source}-${section.section}`,
      source,
      sourceLabel: sourceLabel(source),
      citation: isFederal ? `FCC § ${section.section}` : `D.C. Criminal Code § ${section.section}`,
      formalCitation: section.citation,
      section: section.section,
      heading: section.heading,
      chapter: section.chapter,
      chapterHeading: section.chapter_heading,
      offenseClass: section.offense_class,
      classRule: section.class_rule,
      status: "current",
      text: section.text,
      webUrl: section.web_url || `criminal/${isFederal ? "fcc" : "dc"}/${section.section}/`,
      publicLawUrl: isFederal ? "public-laws.html#pl-37-261" : "public-laws.html#pl-36-260",
      anchor: isFederal ? `fcc-${section.section}` : `dcc-${section.section}`,
    }));
}

function makeTitle18Records(payload) {
  return (payload.sections || [])
    .filter((section) => section.is_charge === true)
    .map((section) => prepareRecord({
      id: section.id,
      source: "title18",
      sourceLabel: sourceLabel("title18"),
      citation: section.citation,
      section: section.section,
      heading: section.heading,
      chapter: section.chapter?.number || "",
      chapterHeading: section.chapter?.heading || "",
      part: section.part,
      status: section.status || "current",
      detailsUrl: section.details_url,
      citeUrl: section.cite_url,
      webUrl: section.web_url || `criminal/title18/${section.section}/`,
      text: "",
      anchor: `usc18-${section.section}`,
    }));
}

function matches(record) {
  if (state.source !== "all" && record.source !== state.source) return false;
  const query = normalize(state.query);
  if (!query) return true;
  return record.haystack.includes(query);
}

function sentenceText(record) {
  if (!record.classRule) return "";
  const r = record.classRule;
  return `Class ${record.offenseClass}: initial arrest ${r.initial_min_minutes}–${r.initial_max_minutes} minutes; court maximum ${r.court_max_days} days; citation maximum $${Number(r.citation_max).toLocaleString()}.`;
}

async function loadTitle18Text(record, body, textNode) {
  if (!record.detailsUrl) return;
  try {
    let detail = state.title18Details.get(record.section);
    if (!detail) {
      const response = await fetch(record.detailsUrl, { cache: "force-cache" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      detail = await response.json();
      if (detail.is_charge !== true || detail.display_scope !== "roblox_safe_charge") {
        throw new Error("section is not available in the charge catalog");
      }
      state.title18Details.set(record.section, detail);
    }
    record.text = detail.text || "No operative text was extracted for this charge.";
    textNode.textContent = record.text;
    body.dataset.loaded = "true";
  } catch (error) {
    textNode.textContent = `This charge text could not be loaded: ${error.message}`;
  }
}

async function ensureTitle18Search() {
  if (state.title18SearchReady) return;
  if (state.title18SearchPromise) return state.title18SearchPromise;

  const previousSummary = elements.summary.textContent;
  elements.summary.textContent = "Loading the Title 18 charge text index…";
  state.title18SearchPromise = fetchJson("title18-search.json")
    .then((payload) => {
      const byId = new Map((payload.entries || []).map((entry) => [entry.id, entry.search_text || ""]));
      state.records.forEach((record) => {
        if (record.source !== "title18") return;
        const fullText = byId.get(record.id);
        if (fullText) record.haystack = `${record.haystack} ${normalize(fullText)}`.trim();
      });
      state.title18SearchReady = true;
      state.title18SearchPromise = null;
      render();
    })
    .catch((error) => {
      console.error("Title 18 charge-text index could not be loaded", error);
      state.title18SearchPromise = null;
      elements.summary.textContent = previousSummary;
    });
  return state.title18SearchPromise;
}

function appendToolbarLink(container, href, label) {
  if (!href) return;
  const link = document.createElement("a");
  link.href = href;
  link.textContent = label;
  container.appendChild(link);
}

function createResult(record) {
  const card = document.createElement("details");
  card.className = "law-result";
  card.id = record.anchor;

  const summary = document.createElement("summary");
  const heading = document.createElement("span");
  heading.className = "result-heading";
  const citation = document.createElement("span");
  citation.className = "result-citation";
  citation.textContent = record.citation;
  const title = document.createElement("span");
  title.className = "result-title";
  title.textContent = record.heading;
  heading.append(citation, title);

  const meta = document.createElement("span");
  meta.className = "result-meta";
  const source = document.createElement("span");
  source.className = "result-badge";
  source.textContent = record.sourceLabel;
  meta.appendChild(source);
  if (record.offenseClass) {
    const cls = document.createElement("span");
    cls.className = "result-badge result-badge--class";
    cls.textContent = `Class ${record.offenseClass}`;
    meta.appendChild(cls);
  }
  if (record.chapterHeading) {
    const chapter = document.createElement("span");
    chapter.className = "result-badge";
    chapter.textContent = record.chapter ? `Ch. ${record.chapter} · ${record.chapterHeading}` : record.chapterHeading;
    meta.appendChild(chapter);
  }
  heading.appendChild(meta);
  summary.appendChild(heading);
  card.appendChild(summary);

  const body = document.createElement("div");
  body.className = "result-body";
  const toolbar = document.createElement("div");
  toolbar.className = "result-body__toolbar";
  const provenance = document.createElement("span");
  provenance.textContent = record.formalCitation || record.sourceLabel;
  toolbar.appendChild(provenance);

  const links = document.createElement("span");
  links.className = "result-body__links";
  appendToolbarLink(links, record.webUrl, "Permanent charge page");
  if (record.citeUrl) appendToolbarLink(links, record.citeUrl, "U.S. Code viewer");
  if (record.publicLawUrl) appendToolbarLink(links, record.publicLawUrl, "Source Public Law");
  if (links.childElementCount) toolbar.appendChild(links);
  body.appendChild(toolbar);

  const text = document.createElement("p");
  text.textContent = record.source === "title18" ? "Open this charge to load the statutory text…" : record.text;
  body.appendChild(text);
  const sentence = sentenceText(record);
  if (sentence) {
    const note = document.createElement("div");
    note.className = "result-sentence";
    note.textContent = sentence;
    body.appendChild(note);
  }
  card.appendChild(body);

  card.addEventListener("toggle", () => {
    if (!card.open) return;
    history.replaceState(null, "", `#${card.id}`);
    if (record.source === "title18" && body.dataset.loaded !== "true") {
      loadTitle18Text(record, body, text);
    }
  });
  return card;
}

function render() {
  const allMatches = state.records.filter(matches);
  state.filtered = allMatches.slice(0, 250);
  elements.results.replaceChildren();
  elements.empty.hidden = state.filtered.length !== 0;
  elements.summary.textContent = allMatches.length > 250
    ? `Showing first 250 of ${allMatches.length} charges`
    : `${allMatches.length} matching charges`;
  const fragment = document.createDocumentFragment();
  state.filtered.forEach((record) => fragment.appendChild(createResult(record)));
  elements.results.appendChild(fragment);

  const requested = decodeURIComponent(window.location.hash.replace(/^#/, ""));
  if (requested) {
    const target = document.getElementById(requested);
    if (target instanceof HTMLDetailsElement) {
      target.open = true;
      target.scrollIntoView({ block: "start" });
    }
  }
}

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`, { cache: "no-cache" });
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

async function loadCatalog() {
  try {
    const [manifest, charges, federal, dc, title18] = await Promise.all([
      fetchJson("manifest.json"),
      fetchJson("charges.json"),
      fetchJson("federal-code.json"),
      fetchJson("dc-code.json"),
      fetchJson("title18-index.json"),
    ]);

    if (manifest.roblox?.display_contract?.charge_only !== true ||
        charges.display_contract?.charge_only !== true ||
        charges.display_contract?.roblox_safe_only !== true) {
      throw new Error("catalog safety contract is missing");
    }

    state.manifest = manifest;
    state.records = [
      ...makeLocalRecords(federal, "federal-criminal-code-2025"),
      ...makeTitle18Records(title18),
      ...makeLocalRecords(dc, "dc-criminal-code-federalized"),
    ];

    const allowedIds = new Set((charges.charges || []).filter((item) => item.is_charge === true).map((item) => item.id));
    state.records = state.records.filter((record) => allowedIds.has(record.id));

    elements.revision.textContent = `Revision ${manifest.revision}`;
    elements.statTitle18.textContent = Number(charges.counts?.title18 || 0).toLocaleString();
    elements.statFcc.textContent = Number(charges.counts?.federal_code || 0).toLocaleString();
    elements.statDc.textContent = Number(charges.counts?.dc_code || 0).toLocaleString();
    elements.statCharges.textContent = Number(charges.counts?.total || 0).toLocaleString();
    elements.loading.hidden = true;
    render();
  } catch (error) {
    elements.loading.textContent = `The criminal charge catalog could not be loaded: ${error.message}`;
    elements.loading.classList.add("is-error");
    elements.summary.textContent = "Catalog unavailable";
  }
}

elements.query.addEventListener("input", (event) => {
  state.query = event.target.value;
  if (state.query.trim()) ensureTitle18Search();
  render();
});
elements.source.addEventListener("change", (event) => {
  state.source = event.target.value;
  render();
});

initializeTheme();
loadCatalog();
