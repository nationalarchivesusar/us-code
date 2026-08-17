const APP_BASE_URL = new URL("../../", import.meta.url);
const PUBLIC_LAWS_URL = new URL("data/public-laws.json", APP_BASE_URL);
const HISTORY_URL = new URL("data/section-history/manifest.json", APP_BASE_URL);

const elements = {
  summary: document.getElementById("changes-summary"),
  query: document.getElementById("changes-query"),
  title: document.getElementById("changes-title"),
  effect: document.getElementById("changes-effect"),
  reset: document.getElementById("changes-reset"),
  count: document.getElementById("changes-count"),
  list: document.getElementById("changes-list"),
  empty: document.getElementById("changes-empty"),
  themeButtons: document.querySelectorAll("[data-theme-choice]"),
};

let records = [];
let historyManifest = { sections: {} };

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function targetKey(target) {
  return `${normalize(target?.title)}:${normalize(target?.section)}`;
}

function lawKey(value) {
  const match = String(value || "").match(/^(\d+)-(\d+)$/);
  return match ? [Number(match[1]), Number(match[2])] : [0, 0];
}

function actionTargets(action) {
  if (Array.isArray(action?.targets) && action.targets.length) return action.targets;
  return action?.target ? [action.target] : [];
}

function normalizeEffect(action, law, target) {
  const verified = historyManifest.sections?.[targetKey(target)]?.status;
  if (verified === "added" || verified === "amended" || verified === "removed") return verified;
  const haystack = `${action?.effect || ""} ${action?.effect_label || ""} ${action?.description || ""}`.toLowerCase();
  if (/add|enact|insert|new section|create/.test(haystack)) return "added";
  if (/amend|revise|replace|modify/.test(haystack)) return "amended";
  if (/repeal|remove|strike|historical/.test(haystack) || law.status === "repealed") return "removed";
  return "recorded";
}

function effectLabel(effect) {
  if (effect === "added") return "Added";
  if (effect === "amended") return "Amended";
  if (effect === "removed") return "Removed / historical";
  return "Recorded action";
}

function buildRecords(payload) {
  const output = [];
  (payload.laws || []).forEach((law) => {
    const seen = new Set();
    (law.actions || []).forEach((action, actionIndex) => {
      const targets = actionTargets(action);
      targets.forEach((target) => {
        if (!target?.title || !target?.section) return;
        const dedupe = `${targetKey(target)}:${action.provision || actionIndex}`;
        if (seen.has(dedupe)) return;
        seen.add(dedupe);
        output.push({
          law,
          action,
          target,
          effect: normalizeEffect(action, law, target),
          verified: historyManifest.sections?.[targetKey(target)] || null,
        });
      });
    });

    (law.targets || []).forEach((target) => {
      if (!target?.title || !target?.section) return;
      const dedupe = `${targetKey(target)}:fallback`;
      if ([...seen].some((item) => item.startsWith(`${targetKey(target)}:`))) return;
      seen.add(dedupe);
      output.push({
        law,
        action: null,
        target,
        effect: normalizeEffect(null, law, target),
        verified: historyManifest.sections?.[targetKey(target)] || null,
      });
    });
  });
  output.sort((a, b) => {
    const ak = lawKey(a.law.public_law);
    const bk = lawKey(b.law.public_law);
    return bk[0] - ak[0]
      || bk[1] - ak[1]
      || Number(a.target.title) - Number(b.target.title)
      || String(a.target.section).localeCompare(String(b.target.section), undefined, { numeric: true });
  });
  return output;
}

function populateTitles() {
  const titles = [...new Set(records.map((record) => String(record.target.title)))].sort((a, b) => Number(a) - Number(b) || a.localeCompare(b));
  titles.forEach((title) => {
    const option = document.createElement("option");
    option.value = title;
    option.textContent = `Title ${title}`;
    elements.title.appendChild(option);
  });
}

function matches(record) {
  const query = normalize(elements.query.value);
  const title = elements.title.value;
  const effect = elements.effect.value;
  if (title && String(record.target.title) !== title) return false;
  if (effect && record.effect !== effect) return false;
  if (!query) return true;
  const haystack = [
    record.law.public_law,
    record.law.title,
    record.law.summary,
    record.action?.provision,
    record.action?.effect_label,
    record.action?.description,
    record.target.title,
    record.target.section,
  ].join(" ").toLowerCase();
  return haystack.includes(query);
}

function makeLink(href, text, className = "") {
  const link = document.createElement("a");
  link.href = href;
  link.textContent = text;
  if (className) link.className = className;
  return link;
}

function renderRecord(record) {
  const li = document.createElement("li");
  li.className = `change-card change-card--${record.effect}`;

  const header = document.createElement("div");
  header.className = "change-card__header";
  const lawUrl = new URL("public-laws.html", APP_BASE_URL);
  lawUrl.hash = `pl-${record.law.public_law}`;
  header.appendChild(makeLink(lawUrl.toString(), `Pub. L. ${record.law.public_law}`, "change-card__law"));

  const effect = document.createElement("span");
  effect.className = `change-card__effect change-card__effect--${record.effect}`;
  effect.textContent = effectLabel(record.effect);
  header.appendChild(effect);

  if (record.verified) {
    const verified = document.createElement("span");
    verified.className = "change-card__verified";
    verified.textContent = "Verified comparison";
    verified.title = "A baseline-to-current statutory text comparison is available for this section.";
    header.appendChild(verified);
  }
  li.appendChild(header);

  const title = document.createElement("h3");
  const sectionUrl = new URL(`cite/${record.target.title}/${encodeURIComponent(record.target.section)}/`, APP_BASE_URL);
  title.appendChild(makeLink(sectionUrl.toString(), `${record.target.title} U.S.C. § ${record.target.section}`));
  li.appendChild(title);

  if (record.law.title) {
    const lawTitle = document.createElement("p");
    lawTitle.className = "change-card__law-title";
    lawTitle.textContent = record.law.title;
    li.appendChild(lawTitle);
  }

  const details = [record.action?.provision, record.action?.effect_label].filter(Boolean);
  if (details.length) {
    const meta = document.createElement("p");
    meta.className = "change-card__meta";
    meta.textContent = details.join(" · ");
    li.appendChild(meta);
  }

  const description = record.action?.description || record.law.summary;
  if (description) {
    const p = document.createElement("p");
    p.className = "change-card__description";
    p.textContent = description;
    li.appendChild(p);
  }

  const actions = document.createElement("div");
  actions.className = "change-card__actions";
  actions.append(
    makeLink(sectionUrl.toString(), "Open Code section"),
    makeLink(lawUrl.toString(), "Open source law"),
  );
  li.appendChild(actions);
  return li;
}

function render() {
  const filtered = records.filter(matches);
  elements.list.replaceChildren(...filtered.map(renderRecord));
  elements.count.textContent = `${filtered.length} recorded codification action${filtered.length === 1 ? "" : "s"}.`;
  elements.empty.hidden = filtered.length !== 0;
}

function initializeThemeButtons() {
  const stored = localStorage.getItem("usc-theme") || "system";
  elements.themeButtons.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.themeChoice === stored);
    button.setAttribute("aria-pressed", button.dataset.themeChoice === stored ? "true" : "false");
    button.addEventListener("click", () => {
      const choice = button.dataset.themeChoice;
      localStorage.setItem("usc-theme", choice);
      const dark = choice === "dark" || (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      elements.themeButtons.forEach((item) => {
        item.classList.toggle("is-active", item === button);
        item.setAttribute("aria-pressed", item === button ? "true" : "false");
      });
    });
  });
}

async function initialize() {
  initializeThemeButtons();
  try {
    const [laws, history] = await Promise.all([
      fetch(PUBLIC_LAWS_URL, { cache: "no-cache" }).then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      }),
      fetch(HISTORY_URL, { cache: "no-cache" }).then((response) => response.ok ? response.json() : { sections: {}, counts: {} }),
    ]);
    historyManifest = history;
    records = buildRecords(laws);
    populateTitles();
    const verifiedCount = Object.keys(history.sections || {}).length;
    elements.summary.textContent = `${records.length} recorded actions across ${laws.counts?.total || laws.laws?.length || 0} Public Laws · ${verifiedCount} sections with verified baseline changes`;
    render();
  } catch (error) {
    console.error(error);
    elements.summary.textContent = "Codification history could not be loaded.";
    elements.count.textContent = "Unable to load the published Public Law index.";
  }

  [elements.query, elements.title, elements.effect].forEach((control) => control.addEventListener("input", render));
  elements.reset.addEventListener("click", () => {
    elements.query.value = "";
    elements.title.value = "";
    elements.effect.value = "";
    render();
  });
}

initialize();
