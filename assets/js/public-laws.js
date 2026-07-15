const THEME_STORAGE_KEY = "usc-theme";

const state = {
  laws: [],
  filtered: [],
  query: "",
  status: "all",
  effect: "all",
  theme: "light",
};

const elements = {
  search: document.getElementById("law-search"),
  status: document.getElementById("status-filter"),
  effect: document.getElementById("effect-filter"),
  list: document.getElementById("public-law-list"),
  resultSummary: document.getElementById("result-summary"),
  loading: document.getElementById("loading-message"),
  empty: document.getElementById("empty-message"),
  total: document.getElementById("count-total"),
  active: document.getElementById("count-active"),
  repealed: document.getElementById("count-repealed"),
  actions: document.getElementById("count-actions"),
  themeButtons: document.querySelectorAll("[data-theme-choice]"),
};

const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");

function resolveTheme(choice) {
  if (choice === "system") return prefersDark.matches ? "dark" : "light";
  return choice === "dark" ? "dark" : "light";
}

function applyTheme(choice) {
  const normalized = ["system", "light", "dark"].includes(choice)
    ? choice
    : "system";
  state.theme = normalized;
  document.documentElement.dataset.theme = resolveTheme(normalized);
  elements.themeButtons.forEach((button) => {
    const active = button.dataset.themeChoice === normalized;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function initializeTheme() {
  const saved = localStorage.getItem(THEME_STORAGE_KEY) || "system";
  applyTheme(saved);
  elements.themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const choice = button.dataset.themeChoice || "system";
      localStorage.setItem(THEME_STORAGE_KEY, choice);
      applyTheme(choice);
    });
  });
  prefersDark.addEventListener("change", () => {
    if (state.theme === "system") applyTheme("system");
  });
}

function normalize(value) {
  return String(value || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function actionTargets(action) {
  if (Array.isArray(action.targets)) return action.targets;
  return action.target ? [action.target] : [];
}

function matchesQuery(law, query) {
  if (!query) return true;
  const haystack = [
    law.public_law,
    law.law_id,
    law.title,
    law.status_label,
    law.summary,
    law.trello_url,
    ...law.targets.map((target) => target.citation),
    ...law.actions.flatMap((action) => [
      action.provision,
      action.effect_label,
      action.result_label,
      action.description,
      ...actionTargets(action).map((target) => target.citation),
    ]),
  ]
    .filter(Boolean)
    .join(" ");
  return normalize(haystack).includes(query);
}

function applyFilters() {
  const query = normalize(state.query);
  state.filtered = state.laws.filter((law) => {
    if (state.status !== "all" && law.status !== state.status) return false;
    if (state.effect !== "all" && !law.effect_categories.includes(state.effect)) {
      return false;
    }
    return matchesQuery(law, query);
  });
  render();
}

function createStatusBadge(law) {
  const badge = document.createElement("span");
  badge.className = `law-status law-status--${law.status}`;
  badge.textContent = law.status_label;
  return badge;
}

function createTarget(target) {
  const item = document.createElement(target.href ? "a" : "span");
  item.className = target.href
    ? "law-target law-target--link"
    : "law-target law-target--historical";
  item.textContent = target.citation;
  if (target.href) item.href = target.href;
  if (target.historical) {
    item.title = "Historical location; the law is repealed.";
  } else if (!target.section) {
    item.title = "Title-wide material; no individual section was recorded.";
  }
  return item;
}

function appendTargets(container, targets) {
  targets.forEach((target, index) => {
    if (index) container.append(document.createTextNode(" "));
    container.appendChild(createTarget(target));
  });
}

function createAction(action, law) {
  const row = document.createElement("li");
  row.className = "law-action";

  const header = document.createElement("div");
  header.className = "law-action__header";
  const provision = document.createElement("h4");
  provision.textContent = action.provision;
  header.appendChild(provision);
  const effect = document.createElement("span");
  effect.className = `effect-badge effect-badge--${action.effect_category}`;
  effect.textContent = action.effect_label;
  header.appendChild(effect);
  row.appendChild(header);

  const meta = document.createElement("div");
  meta.className = "law-action__meta";
  const targets = actionTargets(action);
  if (targets.length) {
    const targetLabel = document.createElement("span");
    targetLabel.className = "law-action__target";
    targetLabel.append(targets.length === 1 ? "Code location: " : "Code locations: ");
    appendTargets(targetLabel, targets);
    meta.appendChild(targetLabel);
  } else {
    const noTarget = document.createElement("span");
    noTarget.className = "law-action__target";
    noTarget.textContent = "No direct U.S. Code location";
    meta.appendChild(noTarget);
  }

  const result = document.createElement("span");
  result.className = "law-action__result";
  result.textContent = action.result_label;
  meta.appendChild(result);
  row.appendChild(meta);

  const description = document.createElement("p");
  description.textContent = action.description;
  row.appendChild(description);

  if (law.status === "repealed") {
    const historical = document.createElement("p");
    historical.className = "law-action__historical-note";
    historical.textContent =
      "Historical only. This provision is not displayed as current operative law.";
    row.appendChild(historical);
  }
  return row;
}

function createLawCard(law) {
  const card = document.createElement("details");
  card.className = `law-card law-card--${law.status}`;
  card.id = `pl-${law.public_law}`;
  card.dataset.status = law.status;

  const summary = document.createElement("summary");
  summary.className = "law-card__summary";
  const heading = document.createElement("span");
  heading.className = "law-card__heading";
  const number = document.createElement("span");
  number.className = "law-card__number";
  number.textContent = `Public Law ${law.public_law}`;
  heading.appendChild(number);
  const title = document.createElement("span");
  title.className = "law-card__title";
  title.textContent = law.title;
  heading.appendChild(title);
  summary.appendChild(heading);

  const badges = document.createElement("span");
  badges.className = "law-card__badges";
  badges.appendChild(createStatusBadge(law));
  const count = document.createElement("span");
  count.className = "law-card__count";
  count.textContent = `${law.action_count} action${law.action_count === 1 ? "" : "s"}`;
  badges.appendChild(count);
  summary.appendChild(badges);
  card.appendChild(summary);

  const body = document.createElement("div");
  body.className = "law-card__body";
  const intro = document.createElement("div");
  intro.className = "law-card__intro";
  const summaryText = document.createElement("p");
  summaryText.className = "law-card__description";
  summaryText.textContent = law.summary;
  intro.appendChild(summaryText);

  const trello = document.createElement("a");
  trello.className = "trello-link";
  trello.href = law.trello_url;
  trello.target = "_blank";
  trello.rel = "noreferrer";
  trello.textContent = "View Public Law on Trello";
  intro.appendChild(trello);
  body.appendChild(intro);

  const locations = document.createElement("section");
  locations.className = "law-card__locations";
  const locationHeading = document.createElement("h3");
  locationHeading.textContent =
    law.status === "repealed"
      ? "Former or historical Code locations"
      : "Affected Code sections";
  locations.appendChild(locationHeading);
  if (law.targets.length) {
    const targetList = document.createElement("div");
    targetList.className = "law-targets";
    appendTargets(targetList, law.targets);
    locations.appendChild(targetList);
  } else {
    const none = document.createElement("p");
    none.textContent = "No direct U.S. Code location was recorded.";
    locations.appendChild(none);
  }
  body.appendChild(locations);

  const actionSection = document.createElement("section");
  actionSection.className = "law-card__actions";
  const actionHeading = document.createElement("h3");
  actionHeading.textContent = "Section-by-section disposition";
  actionSection.appendChild(actionHeading);
  if (law.actions.length) {
    const actionList = document.createElement("ol");
    actionList.className = "law-actions";
    law.actions.forEach((action) =>
      actionList.appendChild(createAction(action, law)),
    );
    actionSection.appendChild(actionList);
  } else {
    const none = document.createElement("p");
    none.textContent = "No section-level actions were recorded.";
    actionSection.appendChild(none);
  }
  body.appendChild(actionSection);
  card.appendChild(body);

  card.addEventListener("toggle", () => {
    if (card.open) history.replaceState(null, "", `#${card.id}`);
  });
  return card;
}

function render() {
  elements.list.replaceChildren();
  elements.empty.hidden = state.filtered.length !== 0;
  elements.resultSummary.textContent =
    `${state.filtered.length} of ${state.laws.length} public laws shown`;
  const fragment = document.createDocumentFragment();
  state.filtered.forEach((law) => fragment.appendChild(createLawCard(law)));
  elements.list.appendChild(fragment);

  const requested = window.location.hash.replace(/^#/, "");
  if (requested) {
    const target = document.getElementById(requested);
    if (target instanceof HTMLDetailsElement) {
      target.open = true;
      target.scrollIntoView({ block: "start" });
    }
  }
}

async function loadPublicLaws() {
  try {
    const response = await fetch("data/public-laws.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.laws = payload.laws || [];
    elements.total.textContent = payload.counts?.total ?? state.laws.length;
    elements.active.textContent =
      payload.counts?.active ??
      state.laws.filter((law) => law.status === "active").length;
    elements.repealed.textContent =
      payload.counts?.repealed ??
      state.laws.filter((law) => law.status === "repealed").length;
    elements.actions.textContent = payload.counts?.actions ?? "—";
    elements.loading.hidden = true;
    applyFilters();
  } catch (error) {
    elements.loading.textContent =
      `The public-law index could not be loaded: ${error.message}`;
    elements.loading.classList.add("is-error");
  }
}

elements.search.addEventListener("input", (event) => {
  state.query = event.target.value;
  applyFilters();
});
elements.status.addEventListener("change", (event) => {
  state.status = event.target.value;
  applyFilters();
});
elements.effect.addEventListener("change", (event) => {
  state.effect = event.target.value;
  applyFilters();
});

initializeTheme();
loadPublicLaws();
