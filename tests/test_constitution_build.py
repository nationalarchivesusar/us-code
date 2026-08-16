import unittest

from tools.build_constitution import strip_markdown


class ConstitutionBuildFormattingTests(unittest.TestCase):
    def test_markdown_headings_keep_structural_boundaries(self):
        source = """---
title: Constitution
---
# The Constitution of The United States of America
>We The People.

---
# Article I - The Congress
### Section I
All legislative Powers herein granted shall be vested in a Congress.
### Section II
The House of Representatives shall be composed of representatives.
"""

        rendered = strip_markdown(source)

        self.assertIn(
            "The Constitution of The United States of America\n\nWe The People.",
            rendered,
        )
        self.assertIn(
            "Article I - The Congress\n\nSection I\n\nAll legislative Powers",
            rendered,
        )
        self.assertIn(
            "representatives.\n\nSection II\n\nThe House of Representatives",
            rendered,
        )

    def test_import_does_not_rewrite_section_wording(self):
        source = """# Amendment XXIV - Occupation of Multiple Offices
Secton. 1. Any person who is confirmed shall not withhold another position.
"""

        rendered = strip_markdown(source)

        self.assertIn("Amendment XXIV - Occupation of Multiple Offices", rendered)
        self.assertIn(
            "Secton. 1. Any person who is confirmed shall not withhold another position.",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()
