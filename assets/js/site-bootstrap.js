(() => {
  const THEME_STORAGE_KEY = "usc-theme";
  const allowedThemes = new Set(["system", "light", "dark"]);
  const scriptUrl = document.currentScript?.src;
  const APP_BASE_URL = scriptUrl
    ? new URL("../../", scriptUrl)
    : new URL("./", window.location.href);

  const PRIMARY_NAV = [
    { path: "./", label: "U.S. Code", key: "code" },
    { path: "public-laws.html", label: "Public Laws", key: "public-laws" },
    { path: "constitution.html", label: "Constitution", key: "constitution" },
    { path: "criminal-law.html", label: "Criminal Law", key: "criminal-law" },
    {
      url: "https://nationalarchivesusar.github.io/courts/",
      label: "United States Courts",
      key: "courts",
      external: true,
    },
  ];

  const FOOTER_NAV = [
    { path: "./", label: "U.S. Code" },
    { path: "public-laws.html", label: "Public Laws" },
    { path: "constitution.html", label: "Constitution" },
    { path: "criminal-law.html", label: "Criminal Law" },
    { path: "api.html", label: "Developer API" },
    { url: "https://nationalarchivesusar.github.io/courts/", label: "United States Courts" },
  ];

  function ensureStyle(path, marker) {
    if (document.querySelector(`link[data-site-style="${marker}"]`)) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = new URL(path, APP_BASE_URL).toString();
    link.dataset.siteStyle = marker;
    document.head.appendChild(link);
  }

  // Navigation CSS does not depend on body markup, so load it while the head is
  // still parsing to avoid a mobile flash of the fallback multi-row nav.
  ensureStyle("assets/css/navigation.css", "canonical-navigation");

  function ensureContextStyles() {
    if (document.querySelector(".criminal-about")) {
      ensureStyle("assets/css/criminal-law-ia.css", "criminal-law-ia");
    }
  }

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

  function pageKey() {
    const current = new URL(window.location.href);
    const relative = current.pathname
      .slice(APP_BASE_URL.pathname.length)
      .replace(/^\/+|\/+$/g, "");

    if (!relative || relative === "index.html" || relative.startsWith("cite/")) return "code";
    if (relative === "public-laws.html" || relative === "changes.html") return "public-laws";
    if (relative === "constitution.html") return "constitution";
    if (relative === "criminal-law.html" || relative.startsWith("criminal/")) return "criminal-law";
    return null;
  }

  function createNavLink(item, activeKey = null) {
    const anchor = document.createElement("a");
    anchor.href = item.url || new URL(item.path, APP_BASE_URL).toString();
    anchor.textContent = item.label;
    if (item.external) {
      anchor.classList.add("primary-nav__related");
      anchor.setAttribute("aria-label", `${item.label}, related site`);
      const external = document.createElement("span");
      external.setAttribute("aria-hidden", "true");
      external.textContent = " ↗";
      anchor.appendChild(external);
    }
    if (item.key && item.key === activeKey) anchor.setAttribute("aria-current", "page");
    return anchor;
  }

  function canonicalizeGlobalNavigation() {
    const activeKey = pageKey();
    document.querySelectorAll(".primary-nav").forEach((nav, index) => {
      let inner = nav.querySelector(".primary-nav__inner");
      if (!inner) {
        inner = document.createElement("div");
        inner.className = "primary-nav__inner";
        nav.appendChild(inner);
      }
      if (!inner.id) inner.id = `primary-nav-menu-${index + 1}`;
      inner.replaceChildren(...PRIMARY_NAV.map((item) => createNavLink(item, activeKey)));

      if (!nav.querySelector(".primary-nav__toggle")) {
        const toggle = document.createElement("button");
        toggle.type = "button";
        toggle.className = "primary-nav__toggle";
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-controls", inner.id);
        toggle.textContent = "Menu";
        toggle.addEventListener("click", () => {
          const open = nav.classList.toggle("is-open");
          toggle.setAttribute("aria-expanded", open ? "true" : "false");
          toggle.textContent = open ? "Close menu" : "Menu";
        });
        nav.prepend(toggle);
      }
      nav.dataset.menuReady = "true";
    });
  }

  function canonicalizeFooterNavigation() {
    document.querySelectorAll(".footer-nav").forEach((nav) => {
      nav.replaceChildren(
        ...FOOTER_NAV.map((item) => {
          const anchor = document.createElement("a");
          anchor.href = item.url || new URL(item.path, APP_BASE_URL).toString();
          anchor.textContent = item.label;
          return anchor;
        }),
      );
    });
  }

  function rootSiteNavigation() {
    document.querySelectorAll(".brand").forEach((anchor) => {
      anchor.href = APP_BASE_URL.toString();
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
      ["Courts case-law bridge", "assets/js/court-bridge.js"],
    ];
    modules.forEach(([label, path]) => {
      const moduleUrl = new URL(path, APP_BASE_URL).toString();
      import(moduleUrl).catch((error) => {
        console.error(`Unable to load ${label}`, error);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    ensureContextStyles();
    rootSiteNavigation();
    canonicalizeGlobalNavigation();
    canonicalizeFooterNavigation();
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
