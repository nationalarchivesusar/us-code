const APP_BASE_URL = new URL("../../", import.meta.url);
const PUBLIC_LAWS_URL = new URL("data/public-laws.json", APP_BASE_URL);
const STYLE_URL = new URL("assets/css/research-tools.css", APP_BASE_URL);

function ensureStylesheet() {
  if (document.querySelector('link[data-research-tools="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.researchTools = "true";
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
  return match ? match[1] : String(value || "").trim();
}

function pinpointFromParentheticals(value) {
  const parts = Array.from(String(value || "").matchAll(/\(([^()]+)\)/g), (match) => match[1].trim())
    .filter(Boolean);
  return parts.length ? parts.join(".") : null;
}

export function parseLegalCitation(input) {
  const raw = String(input || "").trim();
  if (!raw) return null;

  const publicLaw = raw.match(
    /^(?:public\s+law|pub\.?\s*l\.?|pl)\s*0*(\d+)\s*[-–—]\s*0*(\d+)\s*$/i,
  );
  if (publicLaw) {
    return {
      type: "public-law",
      publicLaw: `${Number(publicLaw[1])}-${Number(publicLaw[2])}`,
    };
  }

  const usc = raw.match(
    /^(\d+[A-Za-z]?)\s*(?:U\.?\s*S\.?\s*C\.?|USC)\s*(?:§{1,2}|sec(?:tion)?\.?\s*)?\s*([0-9A-Za-z.-]+)\s*(.*)$/i,
  );
  if (usc) {
    return {
      type: "usc",
      title: usc[1],
      section: usc[2],
      pinpoint: pinpointFromParentheticals(usc[3]),
    };
  }

  return null;
}

function navigateCitation(parsed) {
  if (!parsed) return false;
  if (parsed.type === "public-law") {
    const url = new URL("public-laws.html", APP_BASE_URL);
    url.hash = `pl-${parsed.publicLaw}`;
    window.location.assign(url.toString());
    return true;
  }
  if (parsed.type === "usc") {
    const url = new URL(
      `cite/${encodeURIComponent(parsed.title)}/${encodeURIComponent(parsed.section)}/`,
      APP_BASE_URL,
    );
    if (parsed.pinpoint) url.searchParams.set("p", parsed.pinpoint);
    window.location.assign(url.toString());
    return true;
  }
  return false;
}

function initializeQuickCitation() {
  const searchInner = document.querySelector(".search-band__inner");
  if (!searchInner || document.getElementById("quick-citation-form")) return;

  const wrapper = document.createElement("form");
  wrapper.id = "quick-citation-form";
  wrapper.className = "quick-citation";
  wrapper.autocomplete = "off";
  wrapper.innerHTML = `
    <label for="quick-citation-input">Jump to a legal citation</label>
    <div class="quick-citation__row">
      <input
        id="quick-citation-input"
        type="search"
        spellcheck="false"
        placeholder="18 U.S.C. § 1752(a)(1) or Pub. L. 41-271"
        aria-describedby="quick-citation-help quick-citation-message"
      />
      <button type="submit" class="button">Go</button>
    </div>
    <p id="quick-citation-help" class="quick-citation__help">Accepts U.S. Code citations and USAR Public Law numbers.</p>
    <p id="quick-citation-message" class="quick-citation__message" role="status" aria-live="polite"></p>
  `;
  searchInner.appendChild(wrapper);

  wrapper.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = wrapper.querySelector("#quick-citation-input");
    const message = wrapper.querySelector("#quick-citation-message");
    const parsed = parseLegalCitation(input?.value || "");
    if (!parsed) {
      message.textContent = "Enter a citation such as 18 U.S.C. § 1752 or Public Law 41-271.";
      return;
    }
    message.textContent = "Opening citation…";
    navigateCitation(parsed);
  });
}

async function copyText(value) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Fall through to the legacy copy path.
    }
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
    copied = false;
  }
  textarea.remove();
  return copied;
}

let toastTimer = null;
function showToast(message) {
  let toast = document.getElementById("research-tools-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "research-tools-toast";
    toast.className = "research-tools-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 1600);
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
    title,
    section,
    citation: `${title} U.S.C. § ${section}`,
    sectionContent,
    activeTitle,
  };
}

function actionTargets(action) {
  if (Array.isArray(action?.targets)) return action.targets;
  return action?.target ? [action.target] : [];
}

function targetMatches(target, title, section) {
  return (
    String(target?.title || "").toLowerCase() === String(title).toLowerCase() &&
    String(target?.section || "").toLowerCase() === String(section).toLowerCase()
  );
}

function lawSortKey(law) {
  const match = String(law.public_law || "").match(/^(\d+)-(\d+)$/);
  if (!match) return [Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER, law.public_law || ""];
  return [Number(match[1]), Number(match[2]), law.public_law];
}

function compareLaws(a, b) {
  const ak = lawSortKey(a.law);
  const bk = lawSortKey(b.law);
  return ak[0] - bk[0] || ak[1] - bk[1] || String(ak[2]).localeCompare(String(bk[2]));
}

let publicLawIndexPromise = null;
async function loadPublicLawIndex() {
  if (!publicLawIndexPromise) {
    publicLawIndexPromise = fetch(PUBLIC_LAWS_URL, { cache: "no-cache" })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((payload) => payload.laws || []);
  }
  return publicLawIndexPromise;
}

async function historyForSection(title, section) {
  const laws = await loadPublicLawIndex();
  const records = [];
  laws.forEach((law) => {
    let matchedAction = false;
    (law.actions || []).forEach((action) => {
      if (actionTargets(action).some((target) => targetMatches(target, title, section))) {
        records.push({ law, action });
        matchedAction = true;
      }
    });
    if (!matchedAction && (law.targets || []).some((target) => targetMatches(target, title, section))) {
      records.push({ law, action: null });
    }
  });
  records.sort(compareLaws);
  return records;
}

function makeToolButton(label, handler) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "research-toolbar__button";
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function buildToolbar(context) {
  const toolbar = document.createElement("div");
  toolbar.className = "research-toolbar";
  toolbar.setAttribute("aria-label", "Section research tools");

  toolbar.appendChild(
    makeToolButton("Copy citation", async () => {
      const copied = await copyText(context.citation);
      showToast(copied ? "Citation copied" : "Unable to copy citation");
    }),
  );

  toolbar.appendChild(
    makeToolButton("Copy link", async () => {
      const url = new URL(window.location.href);
      url.searchParams.delete("redirect");
      const copied = await copyText(url.toString());
      showToast(copied ? "Section link copied" : "Unable to copy link");
    }),
  );

  toolbar.appendChild(
    makeToolButton("Source laws", () => {
      const history = context.sectionContent.querySelector(".section-history");
      if (history instanceof HTMLDetailsElement) history.open = true;
      history?.scrollIntoView({ behavior: "smooth", block: "start" });
    }),
  );

  const sourceFile = context.activeTitle?.dataset.titleId || "";
  if (sourceFile.endsWith(".xml")) {
    const xmlLink = document.createElement("a");
    xmlLink.className = "research-toolbar__button";
    xmlLink.href = new URL(sourceFile, APP_BASE_URL).toString();
    xmlLink.target = "_blank";
    xmlLink.rel = "noreferrer";
    xmlLink.textContent = "XML source";
    toolbar.appendChild(xmlLink);
  }

  toolbar.appendChild(makeToolButton("Print", () => window.print()));
  return toolbar;
}

function buildHistoryEntry(record) {
  const item = document.createElement("li");
  item.className = `section-history__entry section-history__entry--${record.law.status || "active"}`;

  const heading = document.createElement("div");
  heading.className = "section-history__entry-heading";
  const lawLink = document.createElement("a");
  const lawUrl = new URL("public-laws.html", APP_BASE_URL);
  lawUrl.hash = `pl-${record.law.public_law}`;
  lawLink.href = lawUrl.toString();
  lawLink.textContent = `Pub. L. ${record.law.public_law}`;
  heading.appendChild(lawLink);

  const title = document.createElement("span");
  title.className = "section-history__law-title";
  title.textContent = record.law.title || "";
  heading.appendChild(title);

  const status = document.createElement("span");
  status.className = `section-history__status section-history__status--${record.law.status || "active"}`;
  status.textContent = record.law.status_label || record.law.status || "Recorded";
  heading.appendChild(status);
  item.appendChild(heading);

  if (record.action) {
    const meta = document.createElement("p");
    meta.className = "section-history__meta";
    const pieces = [record.action.provision, record.action.effect_label].filter(Boolean);
    meta.textContent = pieces.join(" · ");
    item.appendChild(meta);

    if (record.action.description) {
      const description = document.createElement("p");
      description.textContent = record.action.description;
      item.appendChild(description);
    }
  } else if (record.law.summary) {
    const summary = document.createElement("p");
    summary.textContent = record.law.summary;
    item.appendChild(summary);
  }

  return item;
}

async function buildHistoryPanel(context) {
  const details = document.createElement("details");
  details.className = "section-history";
  details.dataset.title = context.title;
  details.dataset.section = context.section;

  const summary = document.createElement("summary");
  summary.innerHTML = `<span>Source laws & section history</span><span class="section-history__count">Loading…</span>`;
  details.appendChild(summary);

  const body = document.createElement("div");
  body.className = "section-history__body";
  const intro = document.createElement("p");
  intro.className = "section-history__intro";
  intro.textContent = "Recorded USAR public-law actions affecting this U.S. Code section.";
  body.appendChild(intro);
  details.appendChild(body);

  try {
    const records = await historyForSection(context.title, context.section);
    const count = summary.querySelector(".section-history__count");
    if (count) count.textContent = `${records.length} record${records.length === 1 ? "" : "s"}`;
    if (!records.length) {
      const empty = document.createElement("p");
      empty.className = "section-history__empty";
      empty.textContent = "No USAR public-law action is recorded for this section in the codification index.";
      body.appendChild(empty);
      return details;
    }

    const list = document.createElement("ol");
    list.className = "section-history__list";
    records.forEach((record) => list.appendChild(buildHistoryEntry(record)));
    body.appendChild(list);
  } catch (error) {
    const count = summary.querySelector(".section-history__count");
    if (count) count.textContent = "Unavailable";
    const failure = document.createElement("p");
    failure.className = "section-history__empty";
    failure.textContent = "The public-law history index could not be loaded.";
    body.appendChild(failure);
    console.error(error);
  }
  return details;
}

let enhancementToken = 0;
async function enhanceCurrentSection() {
  const context = currentSectionContext();
  if (!context) return;
  const token = ++enhancementToken;
  const header = context.sectionContent.querySelector(".section-header");
  if (!header) return;

  if (!header.querySelector(".research-toolbar")) {
    header.appendChild(buildToolbar(context));
  }

  const existing = context.sectionContent.querySelector(".section-history");
  if (
    existing?.dataset.title === context.title &&
    existing?.dataset.section === context.section
  ) {
    return;
  }
  existing?.remove();

  const panel = await buildHistoryPanel(context);
  if (token !== enhancementToken) return;
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

function initializeSectionEnhancements() {
  const sectionContent = document.getElementById("section-content");
  if (!sectionContent) return;
  const observer = new MutationObserver(() => {
    queueMicrotask(() => enhanceCurrentSection());
  });
  observer.observe(sectionContent, { childList: true, subtree: true });
  enhanceCurrentSection();
}

ensureStylesheet();
initializeQuickCitation();
initializeSectionEnhancements();
