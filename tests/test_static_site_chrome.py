import unittest

from tools.build_criminal_law_routes import shell


class StaticSiteChromeTests(unittest.TestCase):
    def test_generated_criminal_routes_use_institutional_site_chrome(self):
        page = shell(
            title="Example citation",
            description="Example description",
            canonical="https://example.invalid/example",
            body='<main id="static-law-content"></main>',
        )

        self.assertIn('class="brand-mark"', page)
        self.assertIn("Federal Statutory Law", page)
        self.assertIn('class="primary-nav"', page)
        self.assertIn('href="https://nationalarchivesusar.github.io/us-code/criminal-law.html" aria-current="page"', page)
        self.assertIn('class="primary-nav__related"', page)
        self.assertIn('class="nara-attribution"', page)
        self.assertIn('class="footer-nav"', page)
        self.assertIn("An independent USAR community resource.", page)
        self.assertNotIn("static-law-header", page)
        self.assertNotIn("Maintained for the USAR community.", page)


if __name__ == "__main__":
    unittest.main()
