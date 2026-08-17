const APP_BASE_URL = new URL("../../", import.meta.url);
const STYLE_URL = new URL("assets/css/constitution-provenance.css", APP_BASE_URL);

function initialize() {
  const hero = document.querySelector(".constitution-hero");
  if (!hero || document.querySelector(".constitution-provenance")) return;

  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = STYLE_URL.toString();
  link.dataset.constitutionProvenance = "true";
  document.head.appendChild(link);

  const section = document.createElement("section");
  section.className = "constitution-provenance";
  section.setAttribute("aria-labelledby", "constitution-provenance-heading");
  section.innerHTML = `
    <div class="constitution-provenance__inner">
      <div>
        <h2 id="constitution-provenance-heading">Publication & constitutional authority</h2>
        <p>The NARA HackMD copy is the canonical publication source used to build this page. Editing that source changes the published website text on the next successful build; it does not, by itself, constitute legal ratification or amendment. Constitutional change remains governed by the Constitution's own amendment and ratification provisions.</p>
      </div>
      <dl class="constitution-provenance__facts">
        <div><dt>Web source</dt><dd><a href="https://hackmd.io/CDCV7p2_Sca6O0FrEJyaIQ?view" target="_blank" rel="noreferrer">NARA HackMD copy ↗</a></dd></div>
        <div><dt>Publication</dt><dd>Build-time synchronization</dd></div>
        <div><dt>Amendments</dt><dd><a href="#article-v">Article V</a></dd></div>
        <div><dt>Ratification</dt><dd><a href="#article-vi">Article VI</a></dd></div>
      </dl>
    </div>
  `;
  hero.after(section);
}

initialize();
