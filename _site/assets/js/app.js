const USLM_NS = "http://xml.house.gov/schemas/uslm/1.0";
const STRUCTURAL_TAGS = new Set([
  "division",
  "subtitle",
  "title",
  "part",
  "subpart",
  "chapter",
  "subchapter",
  "article",
  "section",
  "appendix",
  "compiledAct",
  "subpart1",
]);

const THEME_STORAGE_KEY = "usc-theme";
const state = {
  titles: [],
  xmlCache: new Map(),
  navigation: new Map(),
  selectedTitleId: null,
  selectedTitleMeta: null,
  selectedSectionId: null,
  tocCollapsed: false,
  theme: "light",
  searchMode: "citation",
  location: {
    title: null,
    section: null,
  },
};

const elements = {
  titleList: document.getElementById("title-list"),
  titleFilter: document.getElementById("title-filter"),
  documentViewer: document.getElementById("document-viewer"),
  message: document.getElementById("document-message"),
  breadcrumbs: document.getElementById("breadcrumbs"),
  titleOverview: document.getElementById("title-overview"),
  tocContainer: document.getElementById("toc-container"),
  toc: document.getElementById("toc"),
  sectionContent: document.getElementById("section-content"),
  citationForm: document.getElementById("citation-search"),
  citationTitle: document.getElementById("citation-title"),
  citationSection: document.getElementById("citation-section"),
  searchModeInputs: document.querySelectorAll('input[name="search-mode"]'),
  keywordInput: document.getElementById("keyword-search"),
  tocToggle: document.getElementById("toc-toggle"),
  themeButtons: document.querySelectorAll("[data-theme-choice]"),
  searchResults: document.getElementById("search-results"),
  searchResultsSummary: document.getElementById("search-results-summary"),
  searchResultsList: document.getElementById("search-results-list"),
  searchResultsNote: document.getElementById("search-results-note"),
};

const mediaQueries = {
  prefersDark: window.matchMedia("(prefers-color-scheme: dark)"),
};

const shareMetaElements = {
  description: document.querySelector('meta[name="description"]'),
  ogTitle: document.querySelector('meta[property="og:title"]'),
  ogDescription: document.querySelector('meta[property="og:description"]'),
  twitterTitle: document.querySelector('meta[name="twitter:title"]'),
  twitterDescription: document.querySelector('meta[name="twitter:description"]'),
};

const shareMetaDefaults = {
  documentTitle: document.title,
  description: shareMetaElements.description?.getAttribute("content") || "",
  ogTitle: shareMetaElements.ogTitle?.getAttribute("content") || document.title,
  ogDescription:
    shareMetaElements.ogDescription?.getAttribute("content") ||
    (shareMetaElements.description?.getAttribute("content") || ""),
  twitterTitle:
    shareMetaElements.twitterTitle?.getAttribute("content") || document.title,
  twitterDescription:
    shareMetaElements.twitterDescription?.getAttribute("content") ||
    (shareMetaElements.description?.getAttribute("content") || ""),
};

const SITE_NAME = "US Code Library";
const SEARCH_SNIPPET_RADIUS = 160;

function applyShareMetadata({ pageTitle, shareTitle, description }) {
  const resolvedPageTitle = pageTitle || shareMetaDefaults.documentTitle;
  const resolvedShareTitle = shareTitle || shareMetaDefaults.ogTitle;
  const resolvedDescription =
    description ?? shareMetaDefaults.description ?? "";

  document.title = resolvedPageTitle;

  if (shareMetaElements.description) {
    shareMetaElements.description.setAttribute("content", resolvedDescription);
  }
  if (shareMetaElements.ogTitle) {
    shareMetaElements.ogTitle.setAttribute("content", resolvedShareTitle);
  }
  if (shareMetaElements.ogDescription) {
    shareMetaElements.ogDescription.setAttribute(
      "content",
      resolvedDescription,
    );
  }
  if (shareMetaElements.twitterTitle) {
    shareMetaElements.twitterTitle.setAttribute(
      "content",
      resolvedShareTitle,
    );
  }
  if (shareMetaElements.twitterDescription) {
    shareMetaElements.twitterDescription.setAttribute(
      "content",
      resolvedDescription,
    );
  }
}

function resetShareMetadata() {
  applyShareMetadata({
    pageTitle: shareMetaDefaults.documentTitle,
    shareTitle: shareMetaDefaults.ogTitle,
    description: shareMetaDefaults.description,
  });
}

function hideSearchResults() {
  if (!elements.searchResults) return;
  elements.searchResults.hidden = true;
  if (elements.searchResultsSummary) {
    elements.searchResultsSummary.textContent = "";
  }
  if (elements.searchResultsList) {
    elements.searchResultsList.innerHTML = "";
  }
  if (elements.searchResultsNote) {
    elements.searchResultsNote.hidden = true;
    elements.searchResultsNote.innerHTML = "";
  }
}

function setSearchMode(mode) {
  if (!mode || !["citation", "keyword"].includes(mode)) {
    mode = "citation";
  }
  state.searchMode = mode;
  if (elements.searchModeInputs) {
    elements.searchModeInputs.forEach((input) => {
      const isActive = input.value === mode;
      input.checked = isActive;
      const label = input.closest(".citation-search__mode");
      if (label) {
        label.classList.toggle("is-active", isActive);
      }
    });
  }

  const disableCitation = mode === "keyword";
  if (elements.citationTitle) {
    elements.citationTitle.disabled = disableCitation;
    if (disableCitation) {
      elements.citationTitle.value = "";
    }
  }
  if (elements.citationSection) {
    elements.citationSection.disabled = disableCitation;
    if (disableCitation) {
      elements.citationSection.value = "";
    }
  }

  const disableKeyword = mode === "citation";
  if (elements.keywordInput) {
    elements.keywordInput.disabled = disableKeyword;
    if (disableKeyword) {
      elements.keywordInput.value = "";
    }
  }

  if (mode === "citation") {
    hideSearchResults();
  }
}

function cleanWhitespace(value) {
  return value ? value.replace(/\s+/g, " ").trim() : "";
}

function cleanSectionNumber(value) {
  if (!value) return "";
  return cleanWhitespace(
    value
      .replace(/\u202f/g, " ")
      .replace(/\s+—+$/, "")
      .replace(/[.\s]+$/, ""),
  );
}

function formatTitleShareLabel(metadata) {
  if (!metadata) return "";
  const base = metadata.number ? `Title ${cleanWhitespace(metadata.number)}` : "";
  const heading = cleanWhitespace(metadata.heading);
  const label = cleanWhitespace(metadata.label);
  if (base && heading) {
    return `${base} — ${heading}`;
  }
  if (base && label) {
    return `${base} — ${label}`;
  }
  return heading || label || base;
}

function formatSectionShareLabel(sectionNode) {
  if (!sectionNode) return "";
  const number = cleanSectionNumber(sectionNode.number || "");
  const numberLabel = number.replace(/^§\s*/, "Section ");
  const heading = cleanWhitespace(sectionNode.heading);
  if (numberLabel && heading) {
    return `${numberLabel} — ${heading}`;
  }
  return heading || numberLabel;
}

function applyTitleShareMetadata(metadata) {
  const titleLabel = formatTitleShareLabel(metadata);
  if (!titleLabel) {
    resetShareMetadata();
    return;
  }
  applyShareMetadata({
    pageTitle: `${titleLabel} | ${SITE_NAME}`,
    shareTitle: titleLabel,
    description: `Browse ${titleLabel} of the United States Code.`,
  });
}

function applySectionShareMetadata(metadata, sectionNode) {
  const titleLabel = formatTitleShareLabel(metadata);
  const sectionLabel = formatSectionShareLabel(sectionNode);
  if (!sectionLabel) {
    applyTitleShareMetadata(metadata);
    return;
  }
  const shareTitle = titleLabel
    ? `${titleLabel}, ${sectionLabel}`
    : sectionLabel;
  const description = titleLabel
    ? `View ${sectionLabel} within ${titleLabel} of the United States Code.`
    : `View ${sectionLabel} in the United States Code.`;
  applyShareMetadata({
    pageTitle: `${shareTitle} | ${SITE_NAME}`,
    shareTitle,
    description,
  });
}

function getUrlState() {
  const params = new URLSearchParams(window.location.search);
  const title = params.get("t") || params.get("title");
  const section = params.get("s") || params.get("section");
  return {
    title,
    section,
  };
}

function setLocationState(nextState, options = {}) {
  const { replace = false } = options;
  const desired = {
    title: nextState.title || null,
    section: nextState.section || null,
  };
  if (
    !replace &&
    state.location.title === desired.title &&
    state.location.section === desired.section
  ) {
    return;
  }

  const url = new URL(window.location.href);
  if (desired.title) {
    url.searchParams.set("t", desired.title);
  } else {
    url.searchParams.delete("t");
  }
  url.searchParams.delete("title");

  if (desired.section) {
    url.searchParams.set("s", desired.section);
  } else {
    url.searchParams.delete("s");
  }
  url.searchParams.delete("section");

  if (!url.searchParams.toString()) {
    url.search = "";
  }

  const method = replace ? "replaceState" : "pushState";
  if (typeof history[method] === "function") {
    history[method]({}, "", url);
  } else {
    window.location.assign(url);
    return;
  }
  state.location = desired;
}

function findTitleByLocationParam(value) {
  if (!value) return null;
  let match = state.titles.find((title) => title.identifier === value);
  if (match) return match;
  match = state.titles.find((title) => title.file === value);
  if (match) return match;
  return state.titles.find(
    (title) => normalizeTitleNumber(title.number) === normalizeTitleNumber(value),
  ) || null;
}

function getTitleLocationValue(metadata) {
  if (!metadata) return null;
  if (metadata.number) {
    const compact = metadata.number.replace(/\s+/g, "");
    if (compact) {
      return compact;
    }
  }
  return metadata.identifier || metadata.file || null;
}

async function restoreFromLocation() {
  const { title, section } = getUrlState();
  const rawState = {
    title: title || null,
    section: section || null,
  };

  if (!rawState.title) {
    state.location = rawState;
    resetViewer();
    return;
  }

  const metadata = findTitleByLocationParam(rawState.title);
  if (!metadata) {
    state.location = rawState;
    resetViewer();
    elements.message.textContent = "Requested title could not be found.";
    return;
  }

  const preserveSection = Boolean(rawState.section);
  state.location = {
    title: rawState.title,
    section: rawState.section,
  };

  await loadTitle(metadata.file, {
    skipHistoryUpdate: true,
    preserveSection,
  });

  let sectionRestored = false;
  if (rawState.section) {
    await displaySection(rawState.section, { skipHistoryUpdate: true });
    sectionRestored = Boolean(state.selectedSectionId);
    if (!sectionRestored) {
      state.location.section = null;
    }
  } else {
    state.location.section = null;
  }

  setLocationState(
    {
      title: state.location.title,
      section: sectionRestored ? state.location.section : null,
    },
    { replace: true },
  );
}

function resetViewer() {
  state.selectedTitleId = null;
  state.selectedTitleMeta = null;
  state.selectedSectionId = null;
  highlightTitle(null);
  elements.titleOverview.hidden = true;
  elements.titleOverview.innerHTML = "";
  elements.tocContainer.hidden = true;
  elements.toc.innerHTML = "";
  elements.sectionContent.hidden = true;
  elements.sectionContent.innerHTML = "";
  elements.breadcrumbs.innerHTML = "";
  elements.message.textContent = "Select a title to begin browsing the code.";
  setTocCollapsed(false);
  resetShareMetadata();
  hideSearchResults();
}

function handlePopState() {
  restoreFromLocation();
}

async function bootstrap() {
  const response = await fetch("data/titles.json");
  if (!response.ok) {
    elements.message.textContent = "Unable to load US Code metadata.";
    return;
  }
  const data = await response.json();
  state.titles = data.titles;
  renderTitleList(state.titles);
  elements.titleFilter.addEventListener("input", handleTitleFilter);
  elements.citationForm.addEventListener("submit", handleCitationSearch);
  if (elements.searchModeInputs) {
    elements.searchModeInputs.forEach((input) =>
      input.addEventListener("change", () => {
        if (input.checked) {
          setSearchMode(input.value);
        }
      }),
    );
  }
  elements.tocToggle.addEventListener("click", toggleToc);
  elements.themeButtons.forEach((button) =>
    button.addEventListener("click", () => setTheme(button.dataset.themeChoice)),
  );
  initializeTheme();
  setSearchMode(state.searchMode);
  window.addEventListener("popstate", handlePopState);
  await restoreFromLocation();
  if (!state.selectedTitleId) {
    elements.message.textContent = "Select a title to begin browsing the code.";
  }
}

function renderTitleList(titles) {
  elements.titleList.innerHTML = "";
  titles.forEach((title) => {
    const item = document.createElement("div");
    item.className = "title-item";
    item.dataset.titleId = title.file;

    const button = document.createElement("button");
    button.type = "button";
    button.addEventListener("click", () => loadTitle(title.file));

    const label = document.createElement("span");
    label.className = "title-item__label";
    label.textContent = title.label || `Title ${title.number}`;

    const heading = document.createElement("span");
    heading.className = "title-item__heading";
    heading.textContent = title.heading || title.label;

    button.append(label, heading);
    item.appendChild(button);
    elements.titleList.appendChild(item);
  });
}

function handleTitleFilter(event) {
  const query = event.target.value.trim().toLowerCase();
  Array.from(elements.titleList.children).forEach((item) => {
    const text = item.textContent.toLowerCase();
    item.hidden = query ? !text.includes(query) : false;
  });
}

async function loadTitle(file, options = {}) {
  const { skipHistoryUpdate = false, preserveSection = false } = options;
  const metadata = state.titles.find((title) => title.file === file);
  if (!metadata) return;
  state.selectedTitleId = file;
  state.selectedTitleMeta = metadata;
  state.selectedSectionId = null;

  elements.sectionContent.hidden = true;
  elements.tocContainer.hidden = true;
  elements.titleOverview.hidden = true;
  elements.breadcrumbs.innerHTML = "";
  elements.message.textContent = "Loading title...";
  hideSearchResults();

  highlightTitle(file);

  applyTitleShareMetadata(metadata);

  const titleParam = getTitleLocationValue(metadata);
  if (skipHistoryUpdate) {
    state.location.title = titleParam;
    if (!preserveSection) {
      state.location.section = null;
    }
  } else {
    setLocationState({ title: titleParam, section: null });
  }

  if (metadata.pointer) {
    elements.message.textContent =
      "This title uses Git LFS storage. Fetch the source XML locally to view its content.";
    return;
  }

  try {
    const { doc } = await fetchTitleDocument(metadata);
    const nav = buildNavigation(metadata, doc);
    state.navigation.set(file, nav);
    renderTitle(metadata, nav);
    setTocCollapsed(false);
  } catch (error) {
    console.error(error);
    elements.message.textContent = "Unable to parse the selected title.";
  }
}

function highlightTitle(file) {
  Array.from(elements.titleList.children).forEach((item) => {
    item.classList.toggle("active", item.dataset.titleId === file);
  });
}

async function fetchTitleDocument(metadata) {
  if (state.xmlCache.has(metadata.file)) {
    return state.xmlCache.get(metadata.file);
  }
  const response = await fetch(metadata.file);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${metadata.file}`);
  }
  const text = await response.text();
  if (text.startsWith("version https://git-lfs.github.com")) {
    throw new Error("XML content not available. Git LFS placeholder detected.");
  }
  const parser = new DOMParser();
  const doc = parser.parseFromString(text, "application/xml");
  if (doc.getElementsByTagName("parsererror").length) {
    throw new Error("Unable to parse XML document");
  }
  const payload = { doc, text };
  state.xmlCache.set(metadata.file, payload);
  return payload;
}

function findStructuralRoot(element) {
  if (!element) return null;
  if (STRUCTURAL_TAGS.has(element.localName)) {
    return element;
  }

  for (const child of Array.from(element.children)) {
    const structural = findStructuralRoot(child);
    if (structural) {
      return structural;
    }
  }

  return null;
}

function buildNavigation(metadata, doc) {
  const main = doc.getElementsByTagNameNS(USLM_NS, "main")[0];
  const rootElement = findStructuralRoot(main ?? doc.documentElement);
  if (!rootElement) {
    throw new Error("Unable to locate structural root in XML document");
  }

  const rootNode = parseStructure(rootElement);
  if (!rootNode) {
    throw new Error("Unable to parse structural navigation in XML document");
  }
  const index = new Map();
  buildIndex(rootNode, [], index);

  return { metadata, root: rootNode, index };
}

function parseStructure(element) {
  const type = element.localName;
  if (!STRUCTURAL_TAGS.has(type)) {
    return null;
  }
  const node = {
    type,
    identifier: element.getAttribute("identifier") || "",
    number: directChildText(element, "num"),
    heading: directChildText(element, "heading"),
    children: [],
  };

  const children = Array.from(element.children)
    .map((child) => parseStructure(child))
    .filter(Boolean);
  node.children = children;
  return node;
}

function buildIndex(node, parents, index) {
  if (!node) {
    return;
  }
  const path = [...parents, node];
  if (node.identifier) {
    index.set(node.identifier, path);
  }
  if (node.type === "section" && node.number) {
    index.set(sectionKey(node.number), path);
  }
  node.children.forEach((child) => buildIndex(child, path, index));
}

function sectionKey(value) {
  return value.replace(/[^a-z0-9]/gi, "").toLowerCase();
}

function getSectionLocationValue(node) {
  if (!node) return null;
  if (node.number) {
    const key = sectionKey(node.number);
    if (key) return key;
  }
  return node.identifier || null;
}

function directChildText(element, name) {
  const child = Array.from(element.children).find(
    (el) => el.namespaceURI === USLM_NS && el.localName === name,
  );
  return child ? child.textContent.trim() : "";
}

function renderTitle(metadata, nav) {
  elements.message.textContent = "";
  elements.titleOverview.hidden = false;
  elements.titleOverview.innerHTML = `
    <h2>${metadata.heading}</h2>
    <p class="overview-meta">Title ${metadata.number}</p>
  `;

  elements.tocContainer.hidden = false;
  elements.toc.innerHTML = "";
  elements.toc.appendChild(renderTree(nav.root));
  elements.tocToggle.setAttribute("aria-expanded", String(!state.tocCollapsed));
}

function renderTree(node) {
  if (!node) return document.createTextNode("");

  if (node.type === "section") {
    const button = document.createElement("button");
    button.className = "section-link";
    button.type = "button";
    button.textContent = formatNodeLabel(node);
    if (node.identifier) {
      button.dataset.identifier = node.identifier;
    }
    if (node.number) {
      button.dataset.number = node.number;
    }
    button.addEventListener("click", () => displaySection(node.identifier || node.number));
    return button;
  }

  const details = document.createElement("details");
  if (node.type === "title" || node.type === "appendix") {
    details.open = true;
  }
  const summary = document.createElement("summary");
  summary.textContent = formatNodeLabel(node);
  details.appendChild(summary);

  if (node.children.length) {
    const wrapper = document.createElement("div");
    wrapper.className = "toc-children";
    node.children.forEach((child) => {
      const childElement = renderTree(child);
      if (childElement) {
        wrapper.appendChild(childElement);
      }
    });
    details.appendChild(wrapper);
  }
  return details;
}

function formatNodeLabel(node) {
  const num = node.number ? node.number.replace(/—+$/, "").trim() : "";
  const heading = node.heading ? node.heading.trim() : "";
  if (num && heading) {
    return `${num} ${heading}`;
  }
  return heading || num || node.type.toUpperCase();
}

async function displaySection(identifierOrNumber, options = {}) {
  const { skipHistoryUpdate = false } = options;
  const titleId = state.selectedTitleId;
  if (!titleId) return;
  const nav = state.navigation.get(titleId);
  if (!nav) return;

  const lookupKey = identifierOrNumber.startsWith("/us/")
    ? identifierOrNumber
    : sectionKey(identifierOrNumber);
  const path = nav.index.get(lookupKey);
  if (!path) {
    elements.message.textContent = "Section could not be located in this title.";
    applyTitleShareMetadata(nav.metadata);
    return;
  }
  const sectionNode = path[path.length - 1];
  state.selectedSectionId = sectionNode.identifier || sectionNode.number;
  const sectionParam = getSectionLocationValue(sectionNode);

  try {
    const { doc } = await fetchTitleDocument(nav.metadata);
    const sectionElement = findSectionElement(doc, sectionNode.identifier, sectionNode.number);
    if (!sectionElement) {
      elements.message.textContent = "Section markup not found in XML.";
      applyTitleShareMetadata(nav.metadata);
      return;
    }
    renderBreadcrumbs(path);
    renderSection(sectionElement);
    highlightSectionLink(sectionNode);
    setTocCollapsed(true);
    applySectionShareMetadata(nav.metadata, sectionNode);
    const titleParam = getTitleLocationValue(nav.metadata);
    if (sectionParam) {
      if (skipHistoryUpdate) {
        state.location.title = titleParam;
        state.location.section = sectionParam;
      } else {
        setLocationState({ title: titleParam, section: sectionParam });
      }
    }
  } catch (error) {
    console.error(error);
    elements.message.textContent = "Unable to render section.";
    applyTitleShareMetadata(nav.metadata);
  }
}

function renderBreadcrumbs(path) {
  elements.breadcrumbs.innerHTML = "";
  path.forEach((node) => {
    if (!node.heading && !node.number) return;
    const span = document.createElement("span");
    span.textContent = formatNodeLabel(node);
    elements.breadcrumbs.appendChild(span);
  });
}

function findSectionElement(doc, identifier, number) {
  const sections = doc.getElementsByTagNameNS(USLM_NS, "section");
  const sectionList = Array.from(sections);
  if (identifier) {
    const match = sectionList.find((section) => section.getAttribute("identifier") === identifier);
    if (match) return match;
  }
  if (!number) return null;
  const targetKey = sectionKey(number);
  return sectionList.find((section) => sectionKey(directChildText(section, "num")) === targetKey) || null;
}

function renderSection(sectionElement) {
  elements.sectionContent.hidden = false;
  elements.sectionContent.innerHTML = "";

  const header = document.createElement("header");
  header.className = "section-header";

  const headingGroup = document.createElement("div");
  headingGroup.className = "section-heading-group";
  const number = directChildText(sectionElement, "num");
  const heading = directChildText(sectionElement, "heading");
  if (number) {
    const span = document.createElement("span");
    span.className = "section-number";
    span.textContent = number.replace(/—+$/, "").trim();
    headingGroup.appendChild(span);
  }
  if (heading) {
    const h2 = document.createElement("span");
    h2.className = "section-heading";
    h2.textContent = heading;
    headingGroup.appendChild(h2);
  }
  header.appendChild(headingGroup);

  const toggle = document.createElement("div");
  toggle.className = "section-toggle";
  const textButton = document.createElement("button");
  textButton.type = "button";
  textButton.className = "section-toggle__button is-active";
  textButton.textContent = "Statute";
  textButton.setAttribute("aria-pressed", "true");
  const notesButton = document.createElement("button");
  notesButton.type = "button";
  notesButton.className = "section-toggle__button";
  notesButton.textContent = "Notes";
  notesButton.setAttribute("aria-pressed", "false");
  toggle.append(textButton, notesButton);
  header.appendChild(toggle);

  elements.sectionContent.appendChild(header);

  const panels = document.createElement("div");
  panels.className = "section-panels";
  panels.dataset.view = "statute";

  const statutePanel = document.createElement("div");
  statutePanel.className = "section-panel section-panel--statute";
  statutePanel.id = "section-statute";
  textButton.setAttribute("aria-controls", statutePanel.id);

  const body = document.createElement("div");
  body.className = "usc-body";
  const content = directChild(sectionElement, "content");
  const contentNodes = content
    ? Array.from(content.childNodes)
    : Array.from(sectionElement.childNodes).filter((child) => {
        if (child.nodeType !== Node.ELEMENT_NODE) {
          return child.nodeType === Node.TEXT_NODE && child.textContent.trim().length;
        }
        if (child.namespaceURI !== USLM_NS) return true;
        return !["num", "heading", "notes", "sourceCredit"].includes(child.localName);
      });

  let hasContent = false;
  contentNodes.forEach((child) => {
    const rendered = renderNode(child);
    if (rendered) {
      body.appendChild(rendered);
      hasContent = true;
    }
  });

  if (hasContent) {
    statutePanel.appendChild(body);
  } else {
    const empty = document.createElement("p");
    empty.className = "section-empty";
    empty.textContent = "No statutory text is available for this section.";
    statutePanel.appendChild(empty);
  }

  panels.appendChild(statutePanel);

  const notesList = Array.from(sectionElement.children).filter(
    (child) => child.namespaceURI === USLM_NS && child.localName === "notes",
  );
  const notesPanel = document.createElement("div");
  notesPanel.className = "section-panel section-panel--notes";
  notesPanel.id = "section-notes";
  notesButton.setAttribute("aria-controls", notesPanel.id);
  if (notesList.length) {
    notesList.forEach((notes) => {
      const noteElement = renderNotes(notes);
      if (noteElement) {
        notesPanel.appendChild(noteElement);
      }
    });
  } else {
    const emptyNotes = document.createElement("p");
    emptyNotes.className = "section-empty";
    emptyNotes.textContent = "There are no editorial notes for this section.";
    notesPanel.appendChild(emptyNotes);
  }

  panels.appendChild(notesPanel);
  elements.sectionContent.appendChild(panels);

  const switchView = (view) => {
    panels.dataset.view = view;
    const showNotes = view === "notes";
    notesButton.classList.toggle("is-active", showNotes);
    textButton.classList.toggle("is-active", !showNotes);
    notesButton.setAttribute("aria-pressed", showNotes ? "true" : "false");
    textButton.setAttribute("aria-pressed", showNotes ? "false" : "true");
  };

  textButton.addEventListener("click", () => switchView("statute"));
  notesButton.addEventListener("click", () => switchView("notes"));

  scrollSectionIntoView();
}

function directChild(element, name) {
  return Array.from(element.children).find(
    (el) => el.namespaceURI === USLM_NS && el.localName === name,
  );
}

function highlightSectionLink(targetNode) {
  const targetIdentifier = targetNode.identifier || "";
  const targetNumberKey = targetNode.number ? sectionKey(targetNode.number) : "";
  const buttons = document.querySelectorAll(".section-link");
  buttons.forEach((button) => {
    const identifier = button.dataset.identifier || "";
    const numberKey = button.dataset.number ? sectionKey(button.dataset.number) : "";
    const isMatch =
      (targetIdentifier && identifier === targetIdentifier) ||
      (!targetIdentifier && targetNumberKey && numberKey === targetNumberKey);
    button.classList.toggle("active", Boolean(isMatch));
  });
}

function scrollSectionIntoView() {
  const rect = elements.sectionContent.getBoundingClientRect();
  const offset = window.scrollY + rect.top - 80;
  window.scrollTo({ top: Math.max(offset, 0), behavior: "smooth" });
}

function renderNode(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    const text = node.textContent.trim();
    return text ? document.createTextNode(text + " ") : null;
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return null;
  }

  switch (node.localName) {
    case "p":
      return renderParagraph(node);
    case "paragraph":
    case "subparagraph":
    case "subsection":
    case "clause":
    case "subclause":
    case "item":
    case "subitem":
      return renderStructuredBlock(node);
    case "note":
      return renderNote(node);
    case "quotedContent":
      return renderQuoted(node);
    case "list":
      return renderList(node);
    default:
      const fragment = document.createElement("div");
      fragment.className = `usc-${node.localName}`;
      node.childNodes.forEach((child) => {
        const rendered = renderNode(child);
        if (rendered) fragment.appendChild(rendered);
      });
      return fragment.childNodes.length ? fragment : null;
  }
}

function renderParagraph(node) {
  const p = document.createElement("p");
  node.childNodes.forEach((child) => {
    const rendered = renderInline(child);
    if (rendered) p.appendChild(rendered);
  });
  return p;
}

function renderInline(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    return document.createTextNode(node.textContent);
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return null;
  }
  switch (node.localName) {
    case "ref": {
      const a = document.createElement("a");
      a.href = node.getAttribute("href") || "#";
      a.textContent = node.textContent.trim();
      a.target = "_blank";
      a.rel = "noreferrer";
      return a;
    }
    case "emphasis": {
      const em = document.createElement("em");
      node.childNodes.forEach((child) => {
        const rendered = renderInline(child);
        if (rendered) em.appendChild(rendered);
      });
      return em;
    }
    case "term": {
      const span = document.createElement("span");
      span.className = "usc-term";
      span.textContent = node.textContent.trim();
      return span;
    }
    case "quotedContent":
      return renderQuoted(node);
    default: {
      const span = document.createElement("span");
      node.childNodes.forEach((child) => {
        const rendered = renderInline(child);
        if (rendered) span.appendChild(rendered);
      });
      return span;
    }
  }
}

function renderStructuredBlock(node) {
  const wrapper = document.createElement("div");
  wrapper.className = `usc-${node.localName}`;
  const markerText = directChildText(node, "num");
  if (markerText) {
    const marker = document.createElement("span");
    marker.className = "usc-marker";
    marker.textContent = markerText;
    wrapper.appendChild(marker);
  }
  const headingText = directChildText(node, "heading");
  if (headingText) {
    const heading = document.createElement("strong");
    heading.textContent = headingText + " ";
    wrapper.appendChild(heading);
  }
  const body = document.createElement("div");
  body.className = "usc-text";
  node.childNodes.forEach((child) => {
    if (child.namespaceURI === USLM_NS && ["num", "heading"].includes(child.localName)) {
      return;
    }
    const rendered = renderNode(child);
    if (rendered) body.appendChild(rendered);
  });
  wrapper.appendChild(body);
  return wrapper;
}

function renderNote(node) {
  const container = document.createElement("section");
  container.className = "usc-note";
  const heading = directChildText(node, "heading");
  if (heading) {
    const h3 = document.createElement("h3");
    h3.textContent = heading;
    container.appendChild(h3);
  }
  node.childNodes.forEach((child) => {
    if (child.namespaceURI === USLM_NS && child.localName === "heading") {
      return;
    }
    const rendered = renderNode(child);
    if (rendered) container.appendChild(rendered);
  });
  return container;
}

function renderNotes(notes) {
  const fragment = document.createElement("section");
  fragment.className = "usc-note";
  const heading = notes.getAttribute("role") || "Notes";
  const h3 = document.createElement("h3");
  h3.textContent = heading.replace(/([A-Z])/g, " $1").trim();
  fragment.appendChild(h3);
  notes.childNodes.forEach((child) => {
    const rendered = renderNode(child);
    if (rendered) fragment.appendChild(rendered);
  });
  return fragment;
}

function renderQuoted(node) {
  const block = document.createElement("blockquote");
  block.className = "usc-quoted";
  node.childNodes.forEach((child) => {
    const rendered = renderNode(child);
    if (rendered) block.appendChild(rendered);
  });
  return block;
}

function renderList(node) {
  const ul = document.createElement("ul");
  node.childNodes.forEach((child) => {
    if (child.nodeType !== Node.ELEMENT_NODE || child.localName !== "item") return;
    const li = document.createElement("li");
    const rendered = renderNode(child);
    if (rendered) li.appendChild(rendered);
    ul.appendChild(li);
  });
  return ul;
}

function prepareForKeywordSearch() {
  state.selectedTitleId = null;
  state.selectedTitleMeta = null;
  state.selectedSectionId = null;
  highlightTitle(null);
  elements.titleOverview.hidden = true;
  elements.titleOverview.innerHTML = "";
  elements.tocContainer.hidden = true;
  elements.toc.innerHTML = "";
  elements.sectionContent.hidden = true;
  elements.sectionContent.innerHTML = "";
  elements.breadcrumbs.innerHTML = "";
  elements.message.textContent = "";
  setTocCollapsed(false);
  resetShareMetadata();
  setLocationState({ title: null, section: null }, { replace: true });
}

async function handleKeywordSearch() {
  const query = elements.keywordInput ? elements.keywordInput.value.trim() : "";
  if (!query) {
    elements.message.textContent = "Enter a keyword or phrase to search.";
    return;
  }

  prepareForKeywordSearch();
  hideSearchResults();
  if (!elements.searchResults) return;

  elements.searchResults.hidden = false;
  if (elements.searchResultsSummary) {
    elements.searchResultsSummary.textContent = `Searching for "${query}"...`;
  }
  if (elements.searchResultsList) {
    elements.searchResultsList.innerHTML = "";
  }

  const normalizedQuery = query.toLowerCase();
  const matches = [];
  const skippedTitles = [];
  const failedTitles = [];
  const seenSections = new Set();

  for (const metadata of state.titles) {
    if (metadata.pointer) {
      skippedTitles.push(metadata);
      continue;
    }
    let payload;
    try {
      payload = await fetchTitleDocument(metadata);
    } catch (error) {
      console.error(error);
      failedTitles.push(metadata);
      continue;
    }

    let nav = state.navigation.get(metadata.file);
    if (!nav) {
      nav = buildNavigation(metadata, payload.doc);
      state.navigation.set(metadata.file, nav);
    }

    const sections = payload.doc.getElementsByTagNameNS(USLM_NS, "section");
    const sectionList = Array.from(sections);
    sectionList.forEach((section) => {
      const text = cleanWhitespace(section.textContent || "");
      if (!text) return;
      const lower = text.toLowerCase();
      const matchIndex = lower.indexOf(normalizedQuery);
      if (matchIndex === -1) return;
      const identifier = section.getAttribute("identifier") || "";
      const number = directChildText(section, "num");
      const key = `${metadata.file}::${identifier || sectionKey(number || "")}`;
      if (seenSections.has(key)) return;
      seenSections.add(key);
      matches.push({
        title: metadata,
        identifier,
        number,
        heading: directChildText(section, "heading"),
        snippetSource: text,
        matchIndex,
      });
    });
  }

  renderSearchResults(query, matches, skippedTitles, failedTitles);
}

function renderSearchResults(query, matches, skippedTitles, failedTitles) {
  if (!elements.searchResults) return;
  elements.searchResults.hidden = false;

  const count = matches.length;
  const summary =
    count === 0
      ? `No results found for "${query}".`
      : `Found ${count} ${count === 1 ? "result" : "results"} for "${query}".`;
  if (elements.searchResultsSummary) {
    elements.searchResultsSummary.textContent = summary;
  }

  if (elements.searchResultsList) {
    elements.searchResultsList.innerHTML = "";
    const fragment = document.createDocumentFragment();
    matches.forEach((match) => {
      const item = document.createElement("li");
      item.className = "search-results__item";

      const meta = document.createElement("div");
      meta.className = "search-results__meta";

      const titleLabel = formatTitleShareLabel(match.title) || getTitleDisplayLabel(match.title);
      const titleElement = document.createElement("p");
      titleElement.className = "search-results__title";
      titleElement.textContent = titleLabel;
      meta.appendChild(titleElement);

      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-results__button";
      const numberSpan = document.createElement("span");
      numberSpan.className = "search-results__section-number";
      numberSpan.textContent = cleanSectionNumber(match.number || "") || "Section";
      button.appendChild(numberSpan);

      const headingText = cleanWhitespace(match.heading || "");
      if (headingText) {
        const headingSpan = document.createElement("span");
        headingSpan.className = "search-results__section-heading";
        headingSpan.textContent = headingText;
        button.appendChild(headingSpan);
      }

      button.addEventListener("click", async () => {
        hideSearchResults();
        await loadTitle(match.title.file);
        const target = match.identifier || match.number;
        if (target) {
          await displaySection(target);
        }
      });

      meta.appendChild(button);
      item.appendChild(meta);

      const snippet = createSnippetElement(match.snippetSource, match.matchIndex, query);
      if (snippet) {
        item.appendChild(snippet);
      }

      fragment.appendChild(item);
    });
    elements.searchResultsList.appendChild(fragment);
  }

  if (elements.searchResultsNote) {
    const notes = [];
    if (skippedTitles.length) {
      const labelList = skippedTitles.map((title) => getTitleDisplayLabel(title)).join(", ");
      notes.push(
        `Some titles could not be searched because their XML is stored in Git LFS: ${labelList}.`,
      );
    }
    if (failedTitles.length) {
      const labelList = failedTitles.map((title) => getTitleDisplayLabel(title)).join(", ");
      notes.push(`Unable to search the following titles due to a loading error: ${labelList}.`);
    }

    if (notes.length) {
      elements.searchResultsNote.innerHTML = "";
      notes.forEach((text) => {
        const p = document.createElement("p");
        p.textContent = text;
        elements.searchResultsNote.appendChild(p);
      });
      elements.searchResultsNote.hidden = false;
    } else {
      elements.searchResultsNote.hidden = true;
      elements.searchResultsNote.innerHTML = "";
    }
  }
}

function createSnippetElement(sourceText, matchIndex, query) {
  if (!sourceText || matchIndex < 0 || !query) return null;
  const start = Math.max(0, matchIndex - SEARCH_SNIPPET_RADIUS);
  const end = Math.min(
    sourceText.length,
    matchIndex + query.length + SEARCH_SNIPPET_RADIUS,
  );
  const snippetText = sourceText.slice(start, end);
  const paragraph = document.createElement("p");
  paragraph.className = "search-results__snippet";
  if (start > 0) {
    paragraph.appendChild(document.createTextNode("…"));
  }
  paragraph.appendChild(buildHighlightedFragment(snippetText, query));
  if (end < sourceText.length) {
    paragraph.appendChild(document.createTextNode("…"));
  }
  return paragraph;
}

function buildHighlightedFragment(text, query) {
  const fragment = document.createDocumentFragment();
  if (!query) {
    fragment.appendChild(document.createTextNode(text));
    return fragment;
  }
  const lowerText = text.toLowerCase();
  const lowerQuery = query.toLowerCase();
  const queryLength = query.length;
  let index = 0;
  while (index < text.length) {
    const matchIndex = lowerText.indexOf(lowerQuery, index);
    if (matchIndex === -1) {
      fragment.appendChild(document.createTextNode(text.slice(index)));
      break;
    }
    if (matchIndex > index) {
      fragment.appendChild(document.createTextNode(text.slice(index, matchIndex)));
    }
    const mark = document.createElement("mark");
    mark.textContent = text.slice(matchIndex, matchIndex + queryLength);
    fragment.appendChild(mark);
    index = matchIndex + queryLength;
  }
  return fragment;
}

function getTitleDisplayLabel(metadata) {
  if (!metadata) return "";
  if (metadata.label) return metadata.label;
  if (metadata.number) return `Title ${metadata.number}`;
  return metadata.heading || metadata.file || "Title";
}

async function handleCitationSearch(event) {
  event.preventDefault();
  if (state.searchMode === "keyword") {
    await handleKeywordSearch();
    return;
  }

  const titleValue = elements.citationTitle.value.trim();
  const sectionValue = elements.citationSection.value.trim();
  if (!titleValue) {
    elements.message.textContent = "Enter a title number to search.";
    return;
  }
  hideSearchResults();
  const titleMeta = state.titles.find((t) => normalizeTitleNumber(t.number) === normalizeTitleNumber(titleValue));
  if (!titleMeta) {
    elements.message.textContent = `Title ${titleValue} not found.`;
    return;
  }
  await loadTitle(titleMeta.file);
  if (sectionValue) {
    displaySection(sectionValue);
  }
}

function normalizeTitleNumber(value) {
  return value.replace(/[^a-z0-9]/gi, "").toLowerCase();
}

document.addEventListener("DOMContentLoaded", bootstrap);

function toggleToc() {
  setTocCollapsed(!state.tocCollapsed);
}

function setTocCollapsed(collapsed) {
  state.tocCollapsed = collapsed;
  elements.tocContainer.dataset.state = collapsed ? "collapsed" : "expanded";
  elements.tocToggle.textContent = collapsed ? "Expand" : "Collapse";
  elements.tocToggle.setAttribute("aria-expanded", String(!collapsed));
  elements.toc.setAttribute("aria-hidden", collapsed ? "true" : "false");
}

function initializeTheme() {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  if (stored && ["system", "light", "dark"].includes(stored)) {
    state.theme = stored;
  }
  applyTheme();
  if (typeof mediaQueries.prefersDark.addEventListener === "function") {
    mediaQueries.prefersDark.addEventListener("change", handleSystemThemeChange);
  } else if (typeof mediaQueries.prefersDark.addListener === "function") {
    mediaQueries.prefersDark.addListener(handleSystemThemeChange);
  }
  updateThemeButtons();
}

function setTheme(choice) {
  if (!choice || !["system", "light", "dark"].includes(choice)) return;
  state.theme = choice;
  localStorage.setItem(THEME_STORAGE_KEY, choice);
  applyTheme();
  updateThemeButtons();
}

function applyTheme() {
  const root = document.documentElement;
  const theme = state.theme === "system"
    ? (mediaQueries.prefersDark.matches ? "dark" : "light")
    : state.theme;
  root.dataset.theme = theme;
}

function updateThemeButtons() {
  elements.themeButtons.forEach((button) => {
    const active = button.dataset.themeChoice === state.theme;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function handleSystemThemeChange() {
  if (state.theme === "system") {
    applyTheme();
  }
}
