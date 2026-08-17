const APP_BASE_URL = new URL("../../", import.meta.url);
const STYLE_URL = new URL("assets/css/homepage-search.css", APP_BASE_URL);

function ensureStylesheet() {
  if (document.querySelector('link[data-homepage-search="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.homepageSearch = "true";
  document.head.appendChild(link);
}

function pinpointFromParentheticals(value) {
  const parts = Array.from(String(value || "").matchAll(/\(([^()]+)\)/g), (match) => match[1].trim())
    .filter(Boolean);
  return parts.length ? parts.join(".") : null;
}

function parseLegalCitation(input) {
  const raw = String(input || "").trim();
  if (!raw) return null;

  const publicLaw = raw.match(
    /^(?:public\s+law|pub\.?\s*l\.?|pl)\s*0*(\d+)\s*[-–—]\s*0*(\d+)\s*$/i,
  );
  if (publicLaw) {
    return { type: "public-law", publicLaw: `${Number(publicLaw[1])}-${Number(publicLaw[2])}` };
  }

  const usc = raw.match(
    /^(?:title\s*)?(\d+[A-Za-z]?)\s*(?:(?:U\.?\s*S\.?\s*C\.?|USC)\s*)?(?:§{1,2}|sec(?:tion)?\.?\s*)\s*([0-9A-Za-z.-]+)\s*(.*)$/i,
  );
  if (usc) {
    return {
      type: "usc",
      title: usc[1],
      section: usc[2],
      pinpoint: pinpointFromParentheticals(usc[3]),
    };
  }

  const compact = raw.match(/^(\d+[A-Za-z]?)\s+([0-9A-Za-z.-]+)\s*(.*)$/);
  if (compact) {
    return {
      type: "usc",
      title: compact[1],
      section: compact[2],
      pinpoint: pinpointFromParentheticals(compact[3]),
    };
  }

  return null;
}

function navigate(parsed) {
  if (parsed.type === "public-law") {
    const url = new URL("public-laws.html", APP_BASE_URL);
    url.hash = `pl-${parsed.publicLaw}`;
    window.location.assign(url.toString());
    return;
  }
  const url = new URL(
    `cite/${encodeURIComponent(parsed.title)}/${encodeURIComponent(parsed.section)}/`,
    APP_BASE_URL,
  );
  if (parsed.pinpoint) url.searchParams.set("p", parsed.pinpoint);
  window.location.assign(url.toString());
}

function removeLegacyQuickCitation() {
  document.getElementById("quick-citation-form")?.remove();
}

function initialize() {
  const form = document.getElementById("citation-search");
  const titleInput = document.getElementById("citation-title");
  const sectionInput = document.getElementById("citation-section");
  const keyword = document.getElementById("keyword-search");
  const searchInner = document.querySelector(".search-band__inner");
  if (!form || !titleInput || !sectionInput || !keyword || !searchInner) return;
  if (form.dataset.unifiedCitation === "true") return;
  form.dataset.unifiedCitation = "true";
  searchInner.classList.add("search-band__inner--compact");

  const titleField = titleInput.closest(".field");
  const sectionField = sectionInput.closest(".field");
  if (titleField) titleField.hidden = true;
  if (sectionField) sectionField.hidden = true;

  const smartField = document.createElement("div");
  smartField.className = "field citation-search__smart";
  smartField.innerHTML = `
    <label for="legal-citation-search">Citation or Public Law</label>
    <input
      id="legal-citation-search"
      type="search"
      spellcheck="false"
      placeholder="18 U.S.C. § 1752(a)(1) or Pub. L. 41-271"
      aria-describedby="legal-citation-help legal-citation-message"
    />
    <span id="legal-citation-help" class="citation-search__hint">U.S. Code citations, Title/Section citations, and USAR Public Laws.</span>
    <span id="legal-citation-message" class="citation-search__message" role="status" aria-live="polite"></span>
  `;
  const keywordField = keyword.closest(".field");
  if (keywordField) keywordField.before(smartField);
  else form.querySelector("button[type='submit']")?.before(smartField);

  const smartInput = smartField.querySelector("input");
  const message = smartField.querySelector(".citation-search__message");

  const syncMode = () => {
    const mode = form.querySelector('input[name="search-mode"]:checked')?.value || "citation";
    const citationMode = mode === "citation";
    smartField.hidden = !citationMode;
    if (keywordField) keywordField.hidden = citationMode;
    if (smartInput) smartInput.disabled = !citationMode;
    if (!citationMode && message) message.textContent = "";
  };
  form.querySelectorAll('input[name="search-mode"]').forEach((input) => input.addEventListener("change", syncMode));
  syncMode();

  form.addEventListener(
    "submit",
    (event) => {
      const mode = form.querySelector('input[name="search-mode"]:checked')?.value || "citation";
      if (mode !== "citation") return;
      const parsed = parseLegalCitation(smartInput?.value || "");
      if (!parsed) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (message) message.textContent = "Enter a citation such as 18 U.S.C. § 1752 or Public Law 41-271.";
        smartInput?.focus();
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
      if (message) message.textContent = "Opening citation…";
      navigate(parsed);
    },
    true,
  );

  removeLegacyQuickCitation();
  const observer = new MutationObserver(removeLegacyQuickCitation);
  observer.observe(searchInner, { childList: true });
  window.setTimeout(() => observer.disconnect(), 2500);
}

ensureStylesheet();
initialize();
