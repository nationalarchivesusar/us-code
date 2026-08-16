const THEME_STORAGE_KEY = "usc-theme";
const APP_BASE_URL = new URL("../../", import.meta.url);
const SOURCE_URL = new URL("data/constitution.txt", APP_BASE_URL);

const elements = {
  document: document.getElementById("constitution-document"),
  loading: document.getElementById("constitution-loading"),
  toc: document.getElementById("constitution-toc-list"),
  tocContainer: document.querySelector(".constitution-toc"),
  tocToggle: document.getElementById("constitution-toc-toggle"),
  searchForm: document.getElementById("constitution-search-form"),
  search: document.getElementById("constitution-search"),
  searchStatus: document.getElementById("constitution-search-status"),
  themeButtons: document.querySelectorAll("[data-theme-choice]"),
};

const prefersDark = window.matchMedia("(prefers-color-scheme: dark)");
let themeChoice = "system";
let searchMatches = [];
let searchIndex = -1;

function resolveTheme(choice) {
  if (choice === "system") return prefersDark.matches ? "dark" : "light";
  return choice === "dark" ? "dark" : "light";
}

function applyTheme(choice) {
  const normalized = ["system", "light", "dark"].includes(choice) ? choice : "system";
  themeChoice = normalized;
  document.documentElement.dataset.theme = resolveTheme(normalized);
  elements.themeButtons.forEach((button) => {
    const active = button.dataset.themeChoice === normalized;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function initializeTheme() {
  let saved = "system";
  try {
    saved = localStorage.getItem(THEME_STORAGE_KEY) || "system";
  } catch {
    saved = "system";
  }
  applyTheme(saved);
  elements.themeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const choice = button.dataset.themeChoice || "system";
      try {
        localStorage.setItem(THEME_STORAGE_KEY, choice);
      } catch {
        // Storage restrictions should not block theme switching.
      }
      applyTheme(choice);
    });
  });
  prefersDark.addEventListener("change", () => {
    if (themeChoice === "system") applyTheme("system");
  });
}

function slug(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[’']/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function normalizedBlocks(text) {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split(/\n\s*\n/)
    .map((block) => block.replace(/\n+/g, " ").replace(/\s+/g, " ").trim())
    .filter(Boolean);
}

function headingWithPermalink(tagName, text, id, className) {
  const wrapper = document.createElement("div");
  wrapper.className = "constitution-heading-row";
  const heading = document.createElement(tagName);
  heading.id = id;
  heading.className = className;
  heading.textContent = text;
  wrapper.appendChild(heading);

  const link = document.createElement("a");
  link.className = "constitution-permalink";
  link.href = `#${id}`;
  link.setAttribute("aria-label", `Link to ${text}`);
  link.textContent = "¶";
  wrapper.appendChild(link);
  return wrapper;
}

function addTocLink(container, text, id, level = 1) {
  const link = document.createElement("a");
  link.href = `#${id}`;
  link.textContent = text;
  link.className = `constitution-toc__link constitution-toc__link--level-${level}`;
  container.appendChild(link);
}

function parseAndRender(text) {
  const blocks = normalizedBlocks(text);
  elements.document.replaceChildren();
  elements.toc.replaceChildren();

  let currentArticle = null;
  let currentAmendment = null;
  let titleRendered = false;
  let preambleStarted = false;

  blocks.forEach((block, index) => {
    const article = block.match(/^Article\s+([IVXLC]+)\s*-\s*(.+)$/i);
    const amendment = block.match(/^Amendment\s+([IVXLC]+)\s*-\s*(.+)$/i);
    const articleSection = block.match(/^Section\s+([IVXLC]+)$/i);
    const amendmentSection = block.match(/^(?:Section|Secton)\.?\s*(\d+)\.\s*(.*)$/i);

    if (!titleRendered && index === 0 && /Constitution/i.test(block)) {
      const title = document.createElement("h2");
      title.className = "constitution-document__title";
      title.textContent = block;
      elements.document.appendChild(title);
      titleRendered = true;
      return;
    }

    if (article) {
      currentArticle = article[1].toUpperCase();
      currentAmendment = null;
      const id = `article-${currentArticle.toLowerCase()}`;
      elements.document.appendChild(
        headingWithPermalink("h2", `Article ${currentArticle} — ${article[2]}`, id, "constitution-article"),
      );
      addTocLink(elements.toc, `Article ${currentArticle} — ${article[2]}`, id, 1);
      return;
    }

    if (amendment) {
      currentAmendment = amendment[1].toUpperCase();
      currentArticle = null;
      const id = `amendment-${currentAmendment.toLowerCase()}`;
      elements.document.appendChild(
        headingWithPermalink(
          "h2",
          `Amendment ${currentAmendment} — ${amendment[2]}`,
          id,
          "constitution-amendment",
        ),
      );
      addTocLink(elements.toc, `Amendment ${currentAmendment} — ${amendment[2]}`, id, 1);
      return;
    }

    if (currentArticle && articleSection) {
      const sectionRoman = articleSection[1].toUpperCase();
      const id = `article-${currentArticle.toLowerCase()}-section-${sectionRoman.toLowerCase()}`;
      elements.document.appendChild(
        headingWithPermalink("h3", `Section ${sectionRoman}`, id, "constitution-section"),
      );
      addTocLink(elements.toc, `Section ${sectionRoman}`, id, 2);
      return;
    }

    if (currentAmendment && amendmentSection) {
      const sectionNumber = amendmentSection[1];
      const id = `amendment-${currentAmendment.toLowerCase()}-section-${sectionNumber}`;
      elements.document.appendChild(
        headingWithPermalink("h3", `Section ${sectionNumber}`, id, "constitution-section"),
      );
      addTocLink(elements.toc, `Section ${sectionNumber}`, id, 2);
      if (amendmentSection[2]) {
        const p = document.createElement("p");
        p.className = "constitution-block";
        p.textContent = amendmentSection[2];
        elements.document.appendChild(p);
      }
      return;
    }

    const paragraph = document.createElement("p");
    paragraph.className = "constitution-block";
    if (!currentArticle && !currentAmendment && titleRendered && !preambleStarted) {
      paragraph.classList.add("constitution-preamble");
      preambleStarted = true;
    }
    paragraph.textContent = block;
    elements.document.appendChild(paragraph);
  });

  const hash = window.location.hash;
  if (hash) {
    requestAnimationFrame(() => {
      const target = document.getElementById(hash.slice(1));
      if (target) {
        target.scrollIntoView({ block: "start" });
        target.classList.add("constitution-anchor-highlight");
        setTimeout(() => target.classList.remove("constitution-anchor-highlight"), 1800);
      }
    });
  }
}

function clearSearchHighlights() {
  document
    .querySelectorAll(".constitution-search-match, .constitution-search-current")
    .forEach((node) => node.classList.remove("constitution-search-match", "constitution-search-current"));
  searchMatches = [];
  searchIndex = -1;
}

function runSearch(query) {
  clearSearchHighlights();
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    elements.searchStatus.textContent = "";
    return;
  }

  const candidates = elements.document.querySelectorAll(
    ".constitution-block, .constitution-article, .constitution-amendment, .constitution-section",
  );
  searchMatches = Array.from(candidates).filter((node) =>
    (node.textContent || "").toLowerCase().includes(normalized),
  );
  searchMatches.forEach((node) => node.classList.add("constitution-search-match"));

  if (!searchMatches.length) {
    elements.searchStatus.textContent = `No matches for “${query.trim()}”.`;
    return;
  }
  searchIndex = 0;
  focusSearchMatch();
}

function focusSearchMatch() {
  searchMatches.forEach((node) => node.classList.remove("constitution-search-current"));
  if (searchIndex < 0 || !searchMatches[searchIndex]) return;
  const current = searchMatches[searchIndex];
  current.classList.add("constitution-search-current");
  current.scrollIntoView({ behavior: "smooth", block: "center" });
  const query = elements.search.value.trim();
  elements.searchStatus.textContent = `${searchIndex + 1} of ${searchMatches.length} matches for “${query}”. Press Find again for the next match.`;
}

function initializeSearch() {
  elements.searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const query = elements.search.value.trim();
    if (
      query &&
      searchMatches.length &&
      searchMatches.every((node) => node.classList.contains("constitution-search-match"))
    ) {
      const currentText = searchMatches.some((node) =>
        (node.textContent || "").toLowerCase().includes(query.toLowerCase()),
      );
      if (currentText) {
        searchIndex = (searchIndex + 1) % searchMatches.length;
        focusSearchMatch();
        return;
      }
    }
    runSearch(query);
  });
  elements.search.addEventListener("input", () => {
    clearSearchHighlights();
    elements.searchStatus.textContent = "";
  });
}

function initializeToc() {
  elements.tocToggle.addEventListener("click", () => {
    const collapsed = elements.tocContainer.classList.toggle("is-collapsed");
    elements.tocToggle.textContent = collapsed ? "Expand" : "Collapse";
    elements.tocToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
  });
}

async function loadConstitution() {
  try {
    const response = await fetch(SOURCE_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const text = await response.text();
    parseAndRender(text);
  } catch (error) {
    elements.document.innerHTML = `
      <p class="constitution-loading constitution-loading--error">
        The constitutional text could not be loaded from the published NARA snapshot.
      </p>
    `;
    console.error(error);
  }
}

initializeTheme();
initializeSearch();
initializeToc();
loadConstitution();
