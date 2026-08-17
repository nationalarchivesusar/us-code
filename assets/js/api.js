const APP_BASE_URL = new URL("../../", import.meta.url);
const MANIFEST_URL = new URL("data/api/v1/code/manifest.json", APP_BASE_URL);
const status = document.getElementById("api-manifest-status");

function initializeTheme() {
  const buttons = document.querySelectorAll("[data-theme-choice]");
  const stored = localStorage.getItem("usc-theme") || "system";
  buttons.forEach((button) => {
    const active = button.dataset.themeChoice === stored;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
    button.addEventListener("click", () => {
      const choice = button.dataset.themeChoice;
      localStorage.setItem("usc-theme", choice);
      const dark = choice === "dark" || (choice === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
      document.documentElement.dataset.theme = dark ? "dark" : "light";
      buttons.forEach((item) => {
        item.classList.toggle("is-active", item === button);
        item.setAttribute("aria-pressed", item === button ? "true" : "false");
      });
    });
  });
}

async function initialize() {
  initializeTheme();
  if (!status) return;
  try {
    const response = await fetch(MANIFEST_URL, { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const manifest = await response.json();
    status.textContent = `${manifest.counts?.titles ?? 0} titles · ${manifest.counts?.sections ?? 0} current sections · schema ${manifest.schema_version || "unknown"}`;
  } catch (error) {
    console.error(error);
    status.textContent = "The generated API manifest is currently unavailable.";
  }
}

initialize();
