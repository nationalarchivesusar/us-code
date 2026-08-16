const APP_BASE_URL = new URL("../../", import.meta.url);
const MANIFEST_URL = new URL("data/section-history/manifest.json", APP_BASE_URL);
const STYLE_URL = new URL("assets/css/section-comparison.css", APP_BASE_URL);

let manifestPromise = null;
let enhancementSerial = 0;

function ensureStylesheet() {
  if (document.querySelector('link[data-section-comparison="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.sectionComparison = "true";
  document.head.appendChild(link);
}

function normalizeSection(value) {
  return String(value || "")
    .replace(/^\s*§+\s*/, "")
    .replace(/[.\s]+$/, "")
    .trim();
}

function normalizeTitle(value) {
  const match = String(value || "").match(/\bTitle\s+([0-9]+[A-Za-z]?)\b/i);
  const raw = match ? match[1] : String(value || "").trim();
  return raw.replace(/^0+(?=\d)/, "");
}

function comparisonKey(title, section) {
  return `${normalizeTitle(title).toLowerCase()}:${normalizeSection(section).toLowerCase()}`;
}

function currentSectionContext() {
  const sectionContent = document.getElementById("section-content");
  const numberElement = sectionContent?.querySelector(".section-number");
  if (!sectionContent || sectionContent.hidden || !numberElement) return null;

  const relativePath = window.location.pathname
    .slice(APP_BASE_URL.pathname.length)
    .replace(/^\/+|\/+$/g, "");
  const routeParts = relativePath.split("/").filter(Boolean);
  let routeTitle = null;
  let routeSection = null;
  if (routeParts[0] === "cite" && routeParts.length >= 3) {
    try {
      routeTitle = decodeURIComponent(routeParts[1]);
      routeSection = decodeURIComponent(routeParts[2]);
    } catch {
      routeTitle = null;
      routeSection = null;
    }
  }

  const activeTitle = document.querySelector(".title-item.active");
  const titleLabel = activeTitle?.querySelector(".title-item__label")?.textContent || "";
  const title = routeTitle || normalizeTitle(titleLabel);
  const section = routeSection || normalizeSection(numberElement.textContent);
  if (!title || !section) return null;

  return {
    title: normalizeTitle(title),
    section: normalizeSection(section),
    citation: `${normalizeTitle(title)} U.S.C. § ${normalizeSection(section)}`,
    sectionContent,
  };
}

async function loadManifest() {
  if (!manifestPromise) {
    manifestPromise = fetch(MANIFEST_URL, { cache: "no-cache" }).then(async (response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      if (payload.schema_version !== "1.0" || !payload.sections) {
        throw new Error("Unsupported section-history manifest.");
      }
      return payload;
    });
  }
  return manifestPromise;
}

async function comparisonEntry(context) {
  const manifest = await loadManifest();
  return {
    manifest,
    entry: manifest.sections[comparisonKey(context.title, context.section)] || null,
  };
}

function statusLabel(status) {
  if (status === "added") return "Added since baseline";
  if (status === "removed") return "Removed since baseline";
  return "Amended since baseline";
}

function shortCommit(value) {
  return String(value || "").slice(0, 12);
}

function makeViewButton(label, view, onSelect) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "section-comparison__view-button";
  button.dataset.view = view;
  button.textContent = label;
  button.setAttribute("aria-pressed", view === "redline" ? "true" : "false");
  button.addEventListener("click", () => onSelect(view));
  return button;
}

function renderDiff(container, operations) {
  container.replaceChildren();
  (operations || []).forEach((operation) => {
    const text = document.createTextNode(operation.text || "");
    if (operation.op === "insert") {
      const ins = document.createElement("ins");
      ins.appendChild(text);
      container.appendChild(ins);
    } else if (operation.op === "delete") {
      const del = document.createElement("del");
      del.appendChild(text);
      container.appendChild(del);
    } else {
      container.appendChild(text);
    }
  });
}

function makeVersionColumn(label, version, emptyText) {
  const column = document.createElement("section");
  column.className = "section-comparison__version";

  const heading = document.createElement("h4");
  heading.textContent = label;
  column.appendChild(heading);

  const text = document.createElement("div");
  text.className = "section-comparison__version-text";
  if (version?.present && version.text) {
    text.textContent = version.text;
  } else {
    text.classList.add("section-comparison__version-text--empty");
    text.textContent = emptyText;
  }
  column.appendChild(text);
  return column;
}

function openSourceLawHistory(context) {
  const history = context.sectionContent.querySelector(".section-history");
  if (history instanceof HTMLDetailsElement) history.open = true;
  history?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function insertComparisonPanel(context, panel) {
  const existing = context.sectionContent.querySelector(".section-comparison");
  existing?.remove();

  const history = context.sectionContent.querySelector(".section-history");
  if (history) {
    history.before(panel);
    return;
  }
  const panels = context.sectionContent.querySelector(".section-panels");
  const pager = context.sectionContent.querySelector(".section-pagination");
  if (pager) {
    pager.before(panel);
  } else if (panels) {
    panels.after(panel);
  } else {
    context.sectionContent.appendChild(panel);
  }
}

function buildComparisonPanel(context, manifest, detail) {
  const details = document.createElement("details");
  details.className = "section-comparison";
  details.open = true;
  details.dataset.title = context.title;
  details.dataset.section = context.section;

  const summary = document.createElement("summary");
  const summaryTitle = document.createElement("span");
  summaryTitle.textContent = "Version comparison";
  const badge = document.createElement("span");
  badge.className = `section-comparison__status section-comparison__status--${detail.status}`;
  badge.textContent = statusLabel(detail.status);
  summary.append(summaryTitle, badge);
  details.appendChild(summary);

  const body = document.createElement("div");
  body.className = "section-comparison__body";

  const eyebrow = document.createElement("p");
  eyebrow.className = "section-comparison__eyebrow";
  eyebrow.textContent = "Verified baseline comparison";
  body.appendChild(eyebrow);

  const intro = document.createElement("p");
  intro.className = "section-comparison__intro";
  const baselineCommit = detail.baseline?.commit || manifest.baseline?.commit || "";
  intro.append(
    document.createTextNode(
      `Compares ${context.citation} at the codification repository baseline `,
    ),
  );
  const code = document.createElement("code");
  code.textContent = shortCommit(baselineCommit);
  intro.append(code);
  intro.append(
    document.createTextNode(
      " with the current published statutory text. Source credits and statutory/history notes are excluded from this substantive-text comparison.",
    ),
  );
  body.appendChild(intro);

  const limitation = document.createElement("p");
  limitation.className = "section-comparison__limitation";
  limitation.textContent =
    "Public Law records below identify enactments associated with this section; this view does not yet reconstruct a separate text snapshot after each individual enactment.";
  body.appendChild(limitation);

  const controls = document.createElement("div");
  controls.className = "section-comparison__controls";
  controls.setAttribute("aria-label", "Comparison view");

  const redline = document.createElement("div");
  redline.className = "section-comparison__redline";
  redline.dataset.comparisonView = "redline";
  renderDiff(redline, detail.diff);

  const sideBySide = document.createElement("div");
  sideBySide.className = "section-comparison__side-by-side";
  sideBySide.dataset.comparisonView = "side-by-side";
  sideBySide.hidden = true;
  sideBySide.append(
    makeVersionColumn(
      "Repository baseline",
      detail.baseline,
      "This section was not present in the codification baseline.",
    ),
    makeVersionColumn(
      "Current published text",
      detail.current,
      "This section is not present in the current published Code.",
    ),
  );

  const selectView = (view) => {
    const showRedline = view === "redline";
    redline.hidden = !showRedline;
    sideBySide.hidden = showRedline;
    controls.querySelectorAll(".section-comparison__view-button").forEach((button) => {
      button.setAttribute("aria-pressed", button.dataset.view === view ? "true" : "false");
    });
  };
  controls.append(
    makeViewButton("Redline", "redline", selectView),
    makeViewButton("Side by side", "side-by-side", selectView),
  );
  body.append(controls, redline, sideBySide);

  const footer = document.createElement("div");
  footer.className = "section-comparison__footer";

  const sourceButton = document.createElement("button");
  sourceButton.type = "button";
  sourceButton.className = "section-comparison__source-button";
  sourceButton.textContent = "Open source-law history";
  sourceButton.addEventListener("click", () => openSourceLawHistory(context));
  footer.appendChild(sourceButton);

  const hashes = document.createElement("span");
  hashes.className = "section-comparison__verification";
  const beforeHash = detail.baseline?.sha256 ? detail.baseline.sha256.slice(0, 10) : "not-present";
  const afterHash = detail.current?.sha256 ? detail.current.sha256.slice(0, 10) : "not-present";
  hashes.textContent = `Text verification ${beforeHash} → ${afterHash}`;
  footer.appendChild(hashes);
  body.appendChild(footer);

  details.appendChild(body);
  return details;
}

async function openComparison(context, entry, manifest, button) {
  const existing = context.sectionContent.querySelector(".section-comparison");
  if (
    existing?.dataset.title === context.title &&
    existing?.dataset.section === context.section
  ) {
    if (existing instanceof HTMLDetailsElement) existing.open = true;
    existing.scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }

  const originalText = button.textContent;
  button.disabled = true;
  button.textContent = "Loading comparison…";
  try {
    const response = await fetch(new URL(entry.path, APP_BASE_URL), { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const detail = await response.json();
    if (
      detail.schema_version !== "1.0" ||
      comparisonKey(detail.title, detail.section) !== comparisonKey(context.title, context.section)
    ) {
      throw new Error("Comparison record does not match the current section.");
    }
    const panel = buildComparisonPanel(context, manifest, detail);
    insertComparisonPanel(context, panel);
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    console.error("Unable to load section comparison", error);
    button.textContent = "Comparison unavailable";
    window.setTimeout(() => {
      if (button.isConnected) button.textContent = originalText;
    }, 1800);
  } finally {
    button.disabled = false;
    if (button.textContent === "Loading comparison…") button.textContent = originalText;
  }
}

function placeCompareButton(toolbar, button) {
  const sourceLaws = Array.from(toolbar.querySelectorAll(".research-toolbar__button")).find(
    (item) => (item.textContent || "").trim() === "Source laws",
  );
  if (sourceLaws) sourceLaws.after(button);
  else toolbar.appendChild(button);
}

async function enhanceCurrentSection() {
  const context = currentSectionContext();
  if (!context) return;
  const serial = ++enhancementSerial;
  const toolbar = context.sectionContent.querySelector(".research-toolbar");
  if (!toolbar) return;

  const existingButton = toolbar.querySelector('[data-section-comparison-button="true"]');
  if (
    existingButton?.dataset.title === context.title &&
    existingButton?.dataset.section === context.section
  ) {
    return;
  }
  existingButton?.remove();

  try {
    const { manifest, entry } = await comparisonEntry(context);
    if (serial !== enhancementSerial || !toolbar.isConnected || !entry || entry.status === "removed") {
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "research-toolbar__button research-toolbar__button--compare";
    button.dataset.sectionComparisonButton = "true";
    button.dataset.title = context.title;
    button.dataset.section = context.section;
    button.textContent = "Compare versions";
    button.title = `${statusLabel(entry.status)} — compare verified repository baseline with current text`;
    button.addEventListener("click", () => openComparison(context, entry, manifest, button));
    placeCompareButton(toolbar, button);
  } catch (error) {
    // A missing comparison index should not interfere with ordinary Code browsing.
    console.error("Unable to initialize section comparisons", error);
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
      enhanceCurrentSection();
    });
  };

  const observer = new MutationObserver(schedule);
  observer.observe(sectionContent, { childList: true, subtree: true });
  schedule();
}

initialize();
