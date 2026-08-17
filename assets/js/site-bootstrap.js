(() => {
  const THEME_STORAGE_KEY = "usc-theme";
  const allowedThemes = new Set(["system", "light", "dark"]);
  const scriptUrl = document.currentScript?.src;
  const APP_BASE_URL = scriptUrl
    ? new URL("../../", scriptUrl)
    : new URL("./", window.location.href);

  let theme = "system";
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (allowedThemes.has(stored)) {
      theme = stored;
    } else {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    }
  } catch {
    // Private browsing/storage restrictions should not prevent the site loading.
  }

  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? false;
  document.documentElement.dataset.theme =
    theme === "dark" || (theme === "system" && prefersDark) ? "dark" : "light";

  function rootSiteNavigation() {
    document.querySelectorAll(".brand, .primary-nav a, .footer-nav a").forEach((anchor) => {
      const href = anchor.getAttribute("href") || "";
      if (!href || href.startsWith("#")) return;
      anchor.href = new URL(href, APP_BASE_URL).toString();
    });
  }

  function pageIs(path) {
    const target = new URL(path, APP_BASE_URL);
    return new URL(window.location.href).pathname === target.pathname;
  }

  function insertNavLink(nav, { path, label, marker, beforeRelated = true }) {
    if (!nav || nav.querySelector(`[data-legal-material="${marker}"]`)) return;
    const link = document.createElement("a");
    link.href = new URL(path, APP_BASE_URL).toString();
    link.textContent = label;
    link.dataset.legalMaterial = marker;
    if (pageIs(path)) link.setAttribute("aria-current", "page");
    const related = beforeRelated ? nav.querySelector(".primary-nav__related") : null;
    if (related) related.before(link);
    else nav.appendChild(link);
  }

  function addResearchLinks() {
    if (
      typeof document.querySelector !== "function" ||
      typeof document.createElement !== "function"
    ) {
      return;
    }

    const nav = document.querySelector(".primary-nav__inner");
    insertNavLink(nav, {
      path: "changes.html",
      label: "Code Changes",
      marker: "code-changes",
    });
    insertNavLink(nav, {
      path: "constitution.html",
      label: "Constitution",
      marker: "constitution",
    });

    document.querySelectorAll(".footer-nav").forEach((footerNav) => {
      const courts = Array.from(footerNav.querySelectorAll("a")).find((anchor) =>
        /United States Courts/i.test(anchor.textContent || ""),
      );

      if (!footerNav.querySelector('[data-legal-material="code-changes"]')) {
        const changes = document.createElement("a");
        changes.href = new URL("changes.html", APP_BASE_URL).toString();
        changes.textContent = "Code Changes";
        changes.dataset.legalMaterial = "code-changes";
        if (courts) courts.before(changes);
        else footerNav.appendChild(changes);
      }

      if (!footerNav.querySelector('[data-legal-material="constitution"]')) {
        const constitution = document.createElement("a");
        constitution.href = new URL("constitution.html", APP_BASE_URL).toString();
        constitution.textContent = "Constitution";
        constitution.dataset.legalMaterial = "constitution";
        if (courts) courts.before(constitution);
        else footerNav.appendChild(constitution);
      }

      if (!footerNav.querySelector('[data-legal-material="api"]')) {
        const api = document.createElement("a");
        api.href = new URL("api.html", APP_BASE_URL).toString();
        api.textContent = "API";
        api.dataset.legalMaterial = "api";
        if (courts) courts.before(api);
        else footerNav.appendChild(api);
      }
    });
  }

  function loadPageEnhancements() {
    if (
      typeof document.getElementById !== "function" ||
      !document.getElementById("document-viewer")
    ) {
      return;
    }

    const modules = [
      ["homepage search", "assets/js/homepage-search.js"],
      ["research tools", "assets/js/research-tools.js"],
      ["section comparisons", "assets/js/section-comparison.js"],
      ["section research", "assets/js/section-research.js"],
    ];
    modules.forEach(([label, path]) => {
      const moduleUrl = new URL(path, APP_BASE_URL).toString();
      import(moduleUrl).catch((error) => {
        console.error(`Unable to load ${label}`, error);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    rootSiteNavigation();
    addResearchLinks();
    loadPageEnhancements();
  });

  const params = new URLSearchParams(window.location.search);
  const redirect = params.get("redirect");
  if (!redirect) return;

  let target;
  try {
    target = new URL(redirect, APP_BASE_URL);
  } catch {
    params.delete("redirect");
    const clean = new URL(APP_BASE_URL);
    clean.search = params.toString();
    history.replaceState(null, "", clean.toString());
    return;
  }

  if (
    target.origin !== APP_BASE_URL.origin ||
    !target.pathname.startsWith(APP_BASE_URL.pathname)
  ) {
    params.delete("redirect");
    const clean = new URL(APP_BASE_URL);
    clean.search = params.toString();
    history.replaceState(null, "", clean.toString());
    return;
  }

  const relativePath = target.pathname
    .slice(APP_BASE_URL.pathname.length)
    .replace(/^\/+|\/+$/g, "");
  const parts = relativePath.split("/").filter(Boolean);

  if (parts[0] !== "cite") return;

  if (parts.length === 2) {
    let title;
    try {
      title = decodeURIComponent(parts[1]);
    } catch {
      title = null;
    }
    const normalized = new URL(APP_BASE_URL);
    if (title) normalized.searchParams.set("t", title);
    if (target.searchParams.has("p")) {
      normalized.searchParams.set("p", target.searchParams.get("p"));
    }
    normalized.hash = target.hash;
    history.replaceState(null, "", normalized.toString());
    return;
  }

  if (parts.length === 3) return;

  const destination = parts.at(-1);
  if (
    destination === "criminal-law.html" ||
    destination === "public-laws.html" ||
    destination === "changes.html" ||
    destination === "constitution.html" ||
    destination === "api.html"
  ) {
    window.location.replace(new URL(destination, APP_BASE_URL).toString());
    return;
  }

  history.replaceState(null, "", APP_BASE_URL.toString());
})();
