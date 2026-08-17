const APP_BASE_URL = new URL("../../", import.meta.url);
const PUBLIC_LAWS_URL = new URL("data/public-laws.json", APP_BASE_URL);
const HISTORY_MANIFEST_URL = new URL("data/section-history/manifest.json", APP_BASE_URL);

const elements = {
  form: document.getElementById("changes-filters"),
  search: document.getElementById("changes-search"),
  title: document.getElementById("changes-title"),
  status: document.getElementById("changes-status"),
  type: document.getElementById("changes-type"),
  clear: document.getElementById("changes-clear"),
  summary: document.getElementById("changes-summary"),
  results: document.getElementById("changes-results"),
  themeButtons: document.querySelectorAll("[data-theme-choice]"),
};

let records = [];

function sectionKey(title, section) {
  return `${String(title).toLowerCase()}:${String(section).toLowerCase()}`;
}

function lawKey(value) {
  const match = String(value || "").match(/^(\d+)-(\d+)$/);
  return match ? [Number(match[1]), Number(match[2])] : [-1, -1];
}

function compareLawsDesc(a, b) {
  const ak = lawKey(a.publicLaw);
  const bk = lawKey(b.publicLaw);
  return bk[0] - ak[0] || bk[1] - ak[1];
}

function actionTargets(action) {
  if (Array.isArray(action?.targets)) return action.targets;
  return action?.target ? [action.target] : [];
}

function targetIdentity(target) {
  return `${target?.title || ""}:${target?.section || ""}`.toLowerCase();
}

function bestActionForTarget(law, target) {
  const identity = targetIdentity(target);
  return (law.actions || []).find((action) =>
    actionTargets(action).some((candidate) => targetIdentity(candidate) === identity),
  ) || null;
}

function normalizedVerifiedStatus(meta) {
  if (!meta?.status) return null;
  return ["amended", "added", "removed"].includes(meta.status) ? meta.status : null;
}

function labelFor(record) {
  if (record.verifiedStatus === "amended") return "Verified amended";
  if (record.verifiedStatus === "added") return "Verified added";
  if (record.verifiedStatus === "removed") return "Verified removed";
  return record.effectLabel || "Recorded action";
}

function buildRecords(publicLaws, historyManifest) {
  const result = [];
  for (const law of publicLaws.laws || []) {
    const seen = new Set();
    const candidates = [...(law.targets || [])];
    for (const action of law.actions || []) candidates.push(...actionTargets(action));

    for (const target of candidates) {
      if (!target?.section) continue;
      const identity = targetIdentity(target);
      if (!identity || seen.has(identity)) continue;
      seen.add(identity);
      const action = bestActionForTarget(law, target);
      const meta = historyManifest.sections?.[sectionKey(target.title, target.section)] || null;
      const verifiedStatus = normalizedVerifiedStatus(meta);
      result.push({
        publicLaw: law.public_law,
        lawTitle: law.title || "",
        lawStatus: law.status || "active",
        lawStatusLabel: law.status_label || law.status || "Active",
        lawSummary: law.summary || "",
        target,
        action,
        effectLabel: action?.effect_label || action?.result_label || null,
        description: action?.description || "",
        provision: action?.provision || "",
        verifiedStatus,
        comparisonPath: meta?.path || null,
      });
    }
  }
  return result.sort(compareLawsDesc);
}

function matches(record) {
  const query = String(elements.search?.value || "").trim().toLowerCase();
  const title = String(elements.title?.value || "").trim().toLowerCase();
  const status = elements.status?.value || "all";
  const type = elements.type?.value || "all";

  if (title && String(record.target.title || "").toLowerCase() !== title) return false;
  if (status !== "all" && record.lawStatus !== status) return false;
  if (type === "recorded" && record.verifiedStatus) return false;
  if (["amended", "added", "removed"].includes(type) && record.verifiedStatus !== type) return false;

  if (query) {
    const haystack = [
      record.publicLaw,
      record.lawTitle,
      record.lawSummary,
      record.target.citation,
      record.target.title,
      record.target.section,
      record.effectLabel,
      record.description,
      record.provision,
    ].join(" ").toLowerCase();
    if (!haystack.includes(query)) return false;
  }
  return true;
}

function createBadge(record) {
  const badge = document.createElement("span");
  badge.className = `changes-record__badge ${record.verifiedStatus ? `changes-record__badge--${record.verifiedStatus}` : "changes-record__badge--recorded"}`;
  badge.textContent = labelFor(record);
  badge.title = record.verifiedStatus
    ? "Verified against the fixed repository baseline and current published statutory text."
    : "Recorded in the Public Law codification index; not an independently reconstructed text snapshot.";
  return badge;
}

function codeLink(record) {
  const citation = record.target.citation || `${record.target.title} U.S.C. § ${record.target.section}`;
  if (!record.target.href) {
    const text = document.createElement("strong");
    text.textContent = citation;
    return text;
  }
  const link = document.createElement("a");
  link.href = new URL(record.target.href, APP_BASE_URL).toString();
  link.textContent = citation;
  return link;
}

function renderRecord(record) {
  const item = document.createElement("article");
  item.className = "changes-record";

  const header = document.createElement("div");
  header.className = "changes-record__header";
  const citation = codeLink(record);
  const badge = createBadge(record);
  header.append(citation, badge);
  item.appendChild(header);

  const meta = document.createElement("p");
  meta.className = "changes-record__meta";
  meta.textContent = [record.provision, record.effectLabel].filter(Boolean).join(" · ");
  if (meta.textContent) item.appendChild(meta);

  if (record.description) {
    const description = document.createElement("p");
    description.className = "changes-record__description";
    description.textContent = record.description;
    item.appendChild(description);
  }

  if (record.verifiedStatus) {
    const note = document.createElement("p");
    note.className = "changes-record__evidence";
    note.textContent = "Verified text classification describes baseline → current Code, not necessarily the isolated effect of this one Public Law.";
    item.appendChild(note);
  }
  return item;
}

function renderLawGroup(publicLaw, group) {
  const law = group[0];
  const section = document.createElement("section");
  section.className = "changes-law";

  const heading = document.createElement("header");
  heading.className = "changes-law__header";
  const titleWrap = document.createElement("div");
  const lawLink = document.createElement("a");
  const lawUrl = new URL("public-laws.html", APP_BASE_URL);
  lawUrl.hash = `pl-${publicLaw}`;
  lawLink.href = lawUrl.toString();
  lawLink.className = "changes-law__number";
  lawLink.textContent = `Pub. L. ${publicLaw}`;
  const h3 = document.createElement("h3");
  h3.textContent = law.lawTitle || "Public Law";
  titleWrap.append(lawLink, h3);

  const status = document.createElement("span");
  status.className = `changes-law__status changes-law__status--${law.lawStatus}`;
  status.textContent = law.lawStatusLabel;
  heading.append(titleWrap, status);
  section.appendChild(heading);

  const entries = document.createElement("div");
  entries.className = "changes-law__entries";
  group.forEach((record) => entries.appendChild(renderRecord(record)));
  section.appendChild(entries);
  return section;
}

function render() {
  const filtered = records.filter(matches);
  const groups = new Map();
  for (const record of filtered) {
    if (!groups.has(record.publicLaw)) groups.set(record.publicLaw, []);
    groups.get(record.publicLaw).push(record);
  }

  elements.results.replaceChildren();
  for (const [publicLaw, group] of groups) {
    elements.results.appendChild(renderLawGroup(publicLaw, group));
  }
  if (!filtered.length) {
    const empty = document.createElement("p");
    empty.className = "changes-empty";
    empty.textContent = "No recorded Code changes match these filters.";
    elements.results.appendChild(empty);
  }
  elements.summary.textContent = `${groups.size} Public Law${groups.size === 1 ? "" : "s"} · ${filtered.length} affected-section record${filtered.length === 1 ? "" : "s"}`;
}

function setTheme(theme) {
  const allowed = new Set(["system", "light", "dark"]);
  if (!allowed.has(theme)) theme = "system";
  try { localStorage.setItem("usc-theme", theme); } catch { /* storage unavailable */ }
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  elements.themeButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.themeChoice === theme));
}

async function initialize() {
  try {
    const [publicLaws, historyManifest] = await Promise.all([
      fetch(PUBLIC_LAWS_URL, { cache: "no-cache" }).then((response) => {
        if (!response.ok) throw new Error(`Public Laws HTTP ${response.status}`);
        return response.json();
      }),
      fetch(HISTORY_MANIFEST_URL, { cache: "no-cache" }).then((response) => {
        if (!response.ok) throw new Error(`Section history HTTP ${response.status}`);
        return response.json();
      }),
    ]);
    records = buildRecords(publicLaws, historyManifest);
    render();
  } catch (error) {
    elements.summary.textContent = "Code-change research data could not be loaded.";
    console.error(error);
  }
}

[elements.search, elements.title, elements.status, elements.type].forEach((control) => {
  control?.addEventListener("input", render);
  control?.addEventListener("change", render);
});
elements.clear?.addEventListener("click", () => {
  elements.form?.reset();
  render();
});
elements.themeButtons.forEach((button) => button.addEventListener("click", () => setTheme(button.dataset.themeChoice)));
let storedTheme = "system";
try { storedTheme = localStorage.getItem("usc-theme") || "system"; } catch { /* storage unavailable */ }
setTheme(storedTheme);
initialize();
