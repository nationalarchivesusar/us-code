const COURTS_CASELAW_URL = "https://nationalarchivesusar.github.io/courts/caselaw/";

function enhanceCourtLink() {
  document.querySelectorAll('.section-research-summary a[title^="Open the United States Courts case-law research portal for "]').forEach((link) => {
    if (link.dataset.courtBridge === "true") return;
    const citation = link.title.replace(/^Open the United States Courts case-law research portal for\s+/, "").trim();
    if (!citation) return;
    const url = new URL(COURTS_CASELAW_URL);
    url.searchParams.set("q", `\"${citation}\"`);
    link.href = url.toString();
    link.dataset.courtBridge = "true";
    link.textContent = "Search case law ↗";
  });
}

const content = document.getElementById("section-content");
if (content) {
  new MutationObserver(() => queueMicrotask(enhanceCourtLink)).observe(content, { childList: true, subtree: true });
  enhanceCourtLink();
}
