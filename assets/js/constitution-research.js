const APP_BASE_URL = new URL("../../", import.meta.url);
const META_URL = new URL("data/constitution-meta.json", APP_BASE_URL);
const STYLE_URL = new URL("assets/css/constitution-research.css", APP_BASE_URL);

function ensureStyles() {
  if (document.querySelector('link[data-constitution-research="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.constitutionResearch = "true";
  document.head.appendChild(link);
}

function citationForId(id) {
  let match = String(id || "").match(/^article-([ivxlcdm]+)-section-([ivxlcdm]+)$/i);
  if (match) return `U.S. Const. art. ${match[1].toUpperCase()}, § ${match[2].toUpperCase()}`;
  match = String(id || "").match(/^article-([ivxlcdm]+)$/i);
  if (match) return `U.S. Const. art. ${match[1].toUpperCase()}`;
  match = String(id || "").match(/^amendment-([ivxlcdm]+)-section-(\d+)$/i);
  if (match) return `U.S. Const. amend. ${match[1].toUpperCase()}, § ${match[2]}`;
  match = String(id || "").match(/^amendment-([ivxlcdm]+)$/i);
  if (match) return `U.S. Const. amend. ${match[1].toUpperCase()}`;
  return null;
}

async function copyText(value) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      // Fall through.
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
  try { copied = document.execCommand("copy"); } catch { copied = false; }
  textarea.remove();
  return copied;
}

let toastTimer;
function toast(message) {
  let node = document.getElementById("constitution-research-toast");
  if (!node) {
    node = document.createElement("div");
    node.id = "constitution-research-toast";
    node.className = "constitution-research-toast";
    node.setAttribute("role", "status");
    node.setAttribute("aria-live", "polite");
    document.body.appendChild(node);
  }
  node.textContent = message;
  node.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("is-visible"), 1500);
}

function enhanceHeadingRows() {
  document.querySelectorAll(".constitution-heading-row").forEach((row) => {
    if (row.dataset.researchEnhanced === "true") return;
    const heading = row.querySelector("h2[id], h3[id]");
    if (!heading) return;
    const citation = citationForId(heading.id);
    if (!citation) return;

    row.dataset.researchEnhanced = "true";
    const actions = document.createElement("div");
    actions.className = "constitution-heading-actions";

    const copyCitation = document.createElement("button");
    copyCitation.type = "button";
    copyCitation.textContent = "Copy citation";
    copyCitation.title = citation;
    copyCitation.addEventListener("click", async () => {
      toast((await copyText(citation)) ? "Constitution citation copied" : "Unable to copy citation");
    });

    const copyLink = document.createElement("button");
    copyLink.type = "button";
    copyLink.textContent = "Copy link";
    copyLink.addEventListener("click", async () => {
      const url = new URL(window.location.href);
      url.hash = heading.id;
      toast((await copyText(url.toString())) ? "Constitution link copied" : "Unable to copy link");
    });

    actions.append(copyCitation, copyLink);
    row.appendChild(actions);
  });
}

function initializeActiveToc() {
  if (typeof IntersectionObserver !== "function") return;
  const headings = Array.from(document.querySelectorAll(".constitution-document h2[id], .constitution-document h3[id]"));
  const tocLinks = new Map(
    Array.from(document.querySelectorAll(".constitution-toc__link[href^='#']")).map((link) => [link.getAttribute("href").slice(1), link]),
  );
  if (!headings.length || !tocLinks.size) return;

  let active = null;
  function setActive(id) {
    if (!id || active === id) return;
    active = id;
    tocLinks.forEach((link, key) => {
      const current = key === id;
      link.classList.toggle("is-active", current);
      if (current) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  }

  const observer = new IntersectionObserver((entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
    if (visible[0]) setActive(visible[0].target.id);
  }, { rootMargin: "-18% 0px -68% 0px", threshold: [0, 1] });
  headings.forEach((heading) => observer.observe(heading));
}

function formatTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value || "Unknown";
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(date);
}

async function addProvenance() {
  const shell = document.querySelector(".constitution-shell");
  const controls = document.querySelector(".constitution-controls");
  if (!shell || !controls || document.querySelector(".constitution-provenance")) return;

  const details = document.createElement("details");
  details.className = "constitution-provenance";
  const summary = document.createElement("summary");
  summary.innerHTML = "<span>Publication provenance</span><span>Source & verification</span>";
  const body = document.createElement("div");
  body.className = "constitution-provenance__body";
  body.textContent = "Loading provenance…";
  details.append(summary, body);
  controls.after(details);

  try {
    const response = await fetch(META_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const meta = await response.json();
    body.replaceChildren();

    const grid = document.createElement("dl");
    grid.className = "constitution-provenance__grid";
    const rows = [
      ["Publication source", meta.publication_role],
      ["Fetched", formatTimestamp(meta.fetched_at)],
      ["Published text SHA-256", meta.sha256],
      ["Characters", String(meta.character_count ?? "")],
    ];
    for (const [label, value] of rows) {
      const dt = document.createElement("dt");
      dt.textContent = label;
      const dd = document.createElement("dd");
      dd.textContent = value || "—";
      grid.append(dt, dd);
    }
    body.appendChild(grid);

    const note = document.createElement("p");
    note.className = "constitution-provenance__note";
    note.textContent = meta.legal_validity_note || "";
    body.appendChild(note);

    const source = document.createElement("a");
    source.href = meta.source;
    source.target = "_blank";
    source.rel = "noreferrer";
    source.textContent = "Open NARA source copy ↗";
    body.appendChild(source);
  } catch (error) {
    body.textContent = "Publication provenance could not be loaded.";
    console.error(error);
  }
}

function waitForDocument() {
  const documentNode = document.getElementById("constitution-document");
  if (!documentNode) return;
  let tocInitialized = false;

  function enhance() {
    const headings = documentNode.querySelectorAll("h2[id], h3[id]");
    if (!headings.length) return;
    enhanceHeadingRows();
    if (!tocInitialized && document.querySelector(".constitution-toc__link")) {
      tocInitialized = true;
      initializeActiveToc();
    }
  }

  const observer = new MutationObserver(() => queueMicrotask(enhance));
  observer.observe(documentNode, { childList: true, subtree: true });
  enhance();
}

ensureStyles();
addProvenance();
waitForDocument();
