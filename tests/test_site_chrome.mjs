import assert from "node:assert/strict";
import { test } from "node:test";
import fs from "node:fs";

const pages = [
  ["index.html", "U.S. Code"],
  ["criminal-law.html", "Criminal Law"],
  ["public-laws.html", "Public Laws"],
  ["constitution.html", "Constitution"],
];

for (const [filename, currentLabel] of pages) {
  test(`${filename} uses the shared institutional site chrome`, () => {
    const html = fs.readFileSync(new URL(`../${filename}`, import.meta.url), "utf8");
    assert.match(html, /class="brand-mark"[^>]+assets\/images\/icon-512\.png/);
    assert.match(html, /class="brand-kicker">Federal Statutory Law</);
    assert.match(html, /class="brand-title">United States Code</);
    assert.match(html, /class="masthead__tools"/);
    assert.match(html, /class="primary-nav__related"/);
    assert.match(html, new RegExp(`aria-current="page">${currentLabel}<`));
    assert.match(html, /class="footer-primary"/);
    assert.match(html, /class="nara-attribution"/);
    assert.match(html, /class="footer-nav"/);
    assert.match(html, />Developer API</);
    assert.match(html, /class="footer-disclaimer"/);
    assert.doesNotMatch(html, /class="brand-abbr"/);
    assert.doesNotMatch(html, /class="site-footer__links"/);

    const primaryStart = html.indexOf('<nav class="primary-nav"');
    const primaryEnd = html.indexOf("</nav>", primaryStart);
    const primary = html.slice(primaryStart, primaryEnd);
    assert.match(primary, />U\.S\. Code</);
    assert.match(primary, />Public Laws</);
    assert.match(primary, />Constitution</);
    assert.match(primary, />Criminal Law</);
    assert.match(primary, /United States Courts/);
    assert.doesNotMatch(primary, />Home</);
    assert.doesNotMatch(primary, />Search Code</);
    assert.doesNotMatch(primary, />Code Titles</);
    assert.doesNotMatch(primary, />Code Changes</);
    assert.doesNotMatch(primary, />API</);
  });
}
