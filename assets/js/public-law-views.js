const APP_BASE_URL = new URL("../../", import.meta.url);

function ensureStyles() {
  if (document.querySelector('link[data-legislative-views="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = new URL("assets/css/legislative-views.css", APP_BASE_URL).toString();
  link.dataset.legislativeViews = "true";
  document.head.appendChild(link);
}

const views = {
  laws: document.getElementById("public-laws-view"),
  changes: document.getElementById("code-changes-view"),
};
const tabs = Array.from(document.querySelectorAll("[data-public-law-view]"));

function requestedView() {
  const params = new URLSearchParams(window.location.search);
  const value = params.get("view");
  if (value === "changes") return "changes";
  if (/^#pl-/i.test(window.location.hash)) return "laws";
  return "laws";
}

function setView(view, { updateUrl = false } = {}) {
  const normalized = view === "changes" ? "changes" : "laws";
  Object.entries(views).forEach(([key, node]) => {
    if (node) node.hidden = key !== normalized;
  });
  tabs.forEach((tab) => {
    const active = tab.dataset.publicLawView === normalized;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
    tab.tabIndex = active ? 0 : -1;
  });

  if (updateUrl) {
    const url = new URL(window.location.href);
    if (normalized === "changes") {
      url.searchParams.set("view", "changes");
      url.hash = "";
    } else {
      url.searchParams.delete("view");
    }
    history.replaceState(null, "", url.toString());
  }
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => setView(tab.dataset.publicLawView, { updateUrl: true }));
  tab.addEventListener("keydown", (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const next = tab.dataset.publicLawView === "laws" ? "changes" : "laws";
    setView(next, { updateUrl: true });
    tabs.find((candidate) => candidate.dataset.publicLawView === next)?.focus();
  });
});

window.addEventListener("popstate", () => setView(requestedView()));
ensureStyles();
setView(requestedView());
