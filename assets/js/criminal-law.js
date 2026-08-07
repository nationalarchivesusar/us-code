const THEME_STORAGE_KEY = "usc-theme";
const API_BASE = "data/api/v1/criminal-law/";

const state = {
  theme: "system",
  query: "",
  source: "all",
  kind: "all",
  records: [],
  filtered: [],
  federalCode: null,
  dcCode: null,
  manifest: null,
  title18Details: new Map(),
};

const elements = {
  themeButtons: document.querySelectorAll("[data-theme-choice]"),
  query: document.getElementById("criminal-query"),
  source: document.getElementById("criminal-source"),
  kind: document.getElementById("criminal-kind"),
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
  return String(value || "").toLowerCase().replace(/[§.,]/g, " ").replace(/\s+/g, " ").trim();
}

function sourceLabel(source) {
  return {
    "federal-criminal-code-2025": "Federal Criminal Code",
    "dc-criminal-code-federalized": "Federalized D.C. Code",
    title18: "Title 18 U.S.C.",
    "source-law": "Source Public Law",
  }[source] || source;
}

function searchableText(record) {
  return normalize([
    record.citation,
    record.formalCitation,
    record.heading,
    record.text,
    record.chapterHeading,
    record.sourceLabel,
    record.offenseClass ? `class ${record.offenseClass}` : "",
  ].filter(Boolean).join(" "));
}

function makeLocalRecords(payload, source) {
  return (payload.sections || []).map((section) => ({
    id: `${source}-${section.section}`,
    source,
    sourceLabel: sourceLabel(source),
    kind: section.is_offense ? "offense" : "provision",
    citation: source === "federal-criminal-code-2025" ? `FCC § ${section.section}` : `D.C. Code § ${section.section}`,
    formalCitation: section.citation,
    section: section.section,
    heading: section.heading,
    chapter: section.chapter,
    chapterHeading: section.chapter_heading,
    offenseClass: section.offense_class,
    classRule: section.class_rule,
    text: section.text,
    anchor: source === "federal-criminal-code-2025" ? `fcc-${section.section}` : `dcc-${section.section}`,
  }));
}

function makeTitle18Records(payload) {
  return (payload.sections || []).map((section) => ({
    id: section.id,
    source: "title18",
    sourceLabel: sourceLabel("title18"),
    kind: section.charge_candidate ? "offense" : "provision",
    citation: section.citation,
    section: section.section,
    heading: section.heading,
    chapter: section.chapter?.number || "",
    chapterHeading: section.chapter?.heading || "",
    part: section.part,
    detailsUrl: section.details_url,
    citeUrl: section.cite_url,
    text: "",
    anchor: `usc18-${section.section}`,
  }));
}

function makeSourceLawRecords(payload) {
  return (payload.documents || []).flatMap((doc) => (doc.sections || []).map((section) => ({
    id: `${doc.id}-${section.number}`,
    source: "source-law",
    sourceLabel: doc.citation,
    kind: "provision",
    citation: `${doc.citation} § ${section.number}`,
    section: section.number,
    heading: section.heading,
    text: section.text,
    publicLawUrl: doc.public_law_url,
    anchor: `${doc.id}-${section.number}`,
  })));
}

function matches(record) {
  if (state.source !== "all" && record.source !== state.source) return false;
  if (state.kind !== "all" && record.kind !== state.kind) return false;
  if (!state.query) return true;
  return searchableText(record).includes(normalize(state.query));
}

function sentenceText(record) {
  if (!record.classRule) return "";
  const r = record.classRule;
  return `Federal Criminal Code class ${record.offenseClass}: initial arrest ${r.initial_min_minutes}–${r.initial_max_minutes} minutes; court maximum ${r.court_max_days} days; citation maximum $${Number(r.citation_max).toLocaleString()}. Public Law 39-267 is published separately because no express class crosswalk was supplied.`;
}

async function loadTitle18Text(record, body, textNode) {
  if (!record.detailsUrl) return;
  try {
    let detail = state.title18Details.get(record.section);
    if (!detail) {
      const response = await fetch(record.detailsUrl, { cache: "force-cache" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      detail = await response.json();
      state.title18Details.set(record.section, detail);
    }
    record.text = detail.text || "No operative text was extracted for this section.";
    textNode.textContent = record.text;
    body.dataset.loaded = "true";
  } catch (error) {
    textNode.textContent = `The Title 18 section text could not be loaded: ${error.message}`;
  }
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
  if (record.citeUrl || record.publicLawUrl) {
    const link = document.createElement("a");
    link.href = record.citeUrl || record.publicLawUrl;
    link.textContent = record.citeUrl ? "Open in U.S. Code viewer" : "Open source Public Law";
    toolbar.appendChild(link);
  }
  body.appendChild(toolbar);
  const text = document.createElement("p");
  text.textContent = record.source === "title18" ? "Open this section to load the current statutory text…" : record.text;
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
  state.filtered = state.records.filter(matches).slice(0, 250);
  elements.results.replaceChildren();
  elements.empty.hidden = state.filtered.length !== 0;
  const totalMatched = state.records.filter(matches).length;
  elements.summary.textContent = totalMatched > 250 ? `Showing first 250 of ${totalMatched} matches` : `${totalMatched} matching records`;
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
    const [manifest, charges, federal, dc, title18, documents] = await Promise.all([
      fetchJson("manifest.json"),
      fetchJson("charges.json"),
      fetchJson("federal-code.json"),
      fetchJson("dc-code.json"),
      fetchJson("title18-index.json"),
      fetchJson("documents.json"),
    ]);
    state.manifest = manifest;
    state.federalCode = federal;
    state.dcCode = dc;
    state.records = [
      ...makeLocalRecords(federal, "federal-criminal-code-2025"),
      ...makeTitle18Records(title18),
      ...makeLocalRecords(dc, "dc-criminal-code-federalized"),
      ...makeSourceLawRecords(documents),
    ];
    elements.revision.textContent = `API v${manifest.schema_version} · revision ${manifest.revision}`;
    elements.statTitle18.textContent = Number(title18.counts?.sections || 0).toLocaleString();
    elements.statFcc.textContent = federal.sections.filter((section) => section.is_offense).length.toLocaleString();
    elements.statDc.textContent = dc.sections.length.toLocaleString();
    elements.statCharges.textContent = Number(charges.counts?.total || 0).toLocaleString();
    elements.loading.hidden = true;
    render();
  } catch (error) {
    elements.loading.textContent = `The criminal-law catalog could not be loaded: ${error.message}`;
    elements.loading.classList.add("is-error");
    elements.summary.textContent = "Catalog unavailable";
  }
}

elements.query.addEventListener("input", (event) => { state.query = event.target.value; render(); });
elements.source.addEventListener("change", (event) => { state.source = event.target.value; render(); });
elements.kind.addEventListener("change", (event) => { state.kind = event.target.value; render(); });

initializeTheme();
loadCatalog();
