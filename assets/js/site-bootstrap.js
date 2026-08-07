(() => {
  const THEME_STORAGE_KEY = "usc-theme";
  const allowedThemes = new Set(["system", "light", "dark"]);

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

  const params = new URLSearchParams(window.location.search);
  const redirect = params.get("redirect");
  if (!redirect) return;

  const base = new URL(document.baseURI);
  let target;
  try {
    target = new URL(redirect, base);
  } catch {
    params.delete("redirect");
    const clean = new URL(base);
    clean.search = params.toString();
    history.replaceState(null, "", clean.toString());
    return;
  }

  if (target.origin !== base.origin || !target.pathname.startsWith(base.pathname)) {
    params.delete("redirect");
    const clean = new URL(base);
    clean.search = params.toString();
    history.replaceState(null, "", clean.toString());
    return;
  }

  const relativePath = target.pathname
    .slice(base.pathname.length)
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
    const normalized = new URL(base);
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
  if (destination === "criminal-law.html" || destination === "public-laws.html") {
    window.location.replace(new URL(destination, base).toString());
    return;
  }

  const normalized = new URL(base);
  history.replaceState(null, "", normalized.toString());
})();
