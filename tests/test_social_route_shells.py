import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_social_routes as social


class SocialRouteShellTests(unittest.TestCase):
    def test_compact_shell_preserves_required_embed_metadata(self):
        rendered = social.render_page(
            canonical="https://nationalarchivesusar.github.io/us-code/cite/18/1752/",
            page_title="18 U.S.C. § 1752 — Restricted building or grounds | US Code Library",
            description="Read 18 U.S.C. § 1752 in the United States Code.",
            og_type="article",
        )

        for marker in social.ROUTE_SOCIAL_MARKERS:
            self.assertIn(marker, rendered)
        self.assertIn("location.replace('/us-code/?redirect='", rendered)
        self.assertLessEqual(len(rendered.encode("utf-8")), social.MAX_ROUTE_BYTES)

    def test_crawler_shell_does_not_repeat_twitter_title_description_or_image(self):
        rendered = social.render_page(
            canonical="https://nationalarchivesusar.github.io/us-code/cite/18/111/",
            page_title="18 U.S.C. § 111 | US Code Library",
            description="Read 18 U.S.C. § 111 in the United States Code.",
            og_type="article",
        )

        self.assertIn('name="twitter:card"', rendered)
        self.assertNotIn('name="twitter:title"', rendered)
        self.assertNotIn('name="twitter:description"', rendered)
        self.assertNotIn('name="twitter:image"', rendered)
        self.assertIn('property="og:title"', rendered)
        self.assertIn('property="og:description"', rendered)
        self.assertIn('property="og:image"', rendered)


if __name__ == "__main__":
    unittest.main()
