const APP_BASE_URL = new URL("../../", import.meta.url);
const STYLE_URL = new URL("assets/css/homepage-search.css", APP_BASE_URL);

function ensureStyles() {
  if (document.querySelector('link[data-homepage-search="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.homepageSearch = "true";
  document.head.appendChild(link);
}

function pinpointFromParentheticals(value) {
  const parts = Array.from(String(value || "").matchAll(/\(([^()]+)\)/g), (m) => m[1].trim()).filter(Boolean);
  return parts.length ? parts.join(".") : null;
}

function parseCitation(input) {
  const raw = String(input || "").trim();
  if (!raw) return null;
  const law = raw.match(/^(?:public\s+law|pub\.?\s*l\.?|pl)\s*0*(\d+)\s*[-–—]\s*0*(\d+)\s*$/i);
  if (law) return { type: "public-law", publicLaw: `${Number(law[1])}-${Number(law[2])}` };
  const usc = raw.match(/^(\d+[A-Za-z]?)\s*(?:U\.?\s*S\.?\s*C\.?|USC)\s*(?:§{1,2}|sec(?:tion)?\.?\s*)?\s*([0-9A-Za-z.-]+)\s*(.*)$/i);
  if (!usc) return null;
  return { type: "usc", title: usc[1], section: usc[2], pinpoint: pinpointFromParentheticals(usc[3]) };
}

function navigate(parsed) {
  if (parsed.type === "public-law") {
    const url = new URL("public-laws.html", APP_BASE_URL);
    url.hash = `pl-${parsed.publicLaw}`;
    window.location.assign(url);
    return;
  }
  const url = new URL(`cite/${encodeURIComponent(parsed.title)}/${encodeURIComponent(parsed.section)}/`, APP_BASE_URL);
  if (parsed.pinpoint) url.searchParams.set("p", parsed.pinpoint);
  window.location.assign(url);
}

function enhanceSearch() {
  const form = document.getElementById("citation-search");
  const title = document.getElementById("citation-title");
  const section = document.getElementById("citation-section");
  if (!form || !title || !section || form.dataset.smartCitation === "true") return;
  form.dataset.smartCitation = "true";

  document.getElementById("quick-citation-form")?.remove();
  const sectionLabel = form.querySelector('label[for="citation-section"]');
  if (sectionLabel) sectionLabel.textContent = "Section or citation";
  title.placeholder = "18";
  section.placeholder = "1752 or 18 U.S.C. § 1752(a)(1)";

  const help = document.createElement("p");
  help.className = "citation-search__smart-help";
  help.textContent = "Citation mode also accepts a full U.S. Code citation or Public Law number.";
  form.appendChild(help);

  form.addEventListener("submit", (event) => {
    const mode = form.querySelector('input[name="search-mode"]:checked')?.value;
    if (mode !== "citation") return;
    const candidates = [section.value, title.value].map((value) => String(value || "").trim()).filter(Boolean);
    for (const candidate of candidates) {
      const parsed = parseCitation(candidate);
      if (!parsed) continue;
      event.preventDefault();
      event.stopImmediatePropagation();
      navigate(parsed);
      return;
    }
  }, true);
}

function suppressLegacyQuickCitation() {
  document.getElementById("quick-citation-form")?.remove();
  const search = document.querySelector(".search-band__inner");
  if (!search) return;
  new MutationObserver(() => document.getElementById("quick-citation-form")?.remove())
    .observe(search, { childList: true });
}

ensureStyles();
enhanceSearch();
suppressLegacyQuickCitation();
