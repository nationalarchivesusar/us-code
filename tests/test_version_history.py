import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_version_history as history


class DirectPublicLawLinkTests(unittest.TestCase):
    def test_latest_capitol_police_snapshot_is_tracked(self):
        self.assertIn(
            "8461e76f47a7df89b4e03888aa6986460890b072",
            {item["commit"] for item in history.SNAPSHOTS},
        )

    def test_single_relevant_named_law_gets_direct_repository_link(self):
        versions = [
            {
                "commit": "abc123",
                "named_public_laws": ["41-271", "42-272"],
            }
        ]
        section_laws = [
            {"public_law": "42-272", "title": "Example Act", "status": "active"},
        ]

        count = history.attach_direct_law_links(versions, section_laws)

        self.assertEqual(count, 1)
        self.assertEqual(versions[0]["named_public_laws"], ["42-272"])
        link = versions[0]["direct_public_law_link"]
        self.assertEqual(link["public_law"], "42-272")
        self.assertEqual(link["evidence"], "direct-commit-message-and-section-target")
        self.assertIn("does not by itself prove", link["limitation"])

    def test_multiple_relevant_named_laws_are_not_over_attributed(self):
        versions = [
            {
                "commit": "abc123",
                "named_public_laws": ["41-271", "42-272"],
            }
        ]
        section_laws = [
            {"public_law": "41-271", "title": "First Act", "status": "active"},
            {"public_law": "42-272", "title": "Second Act", "status": "active"},
        ]

        count = history.attach_direct_law_links(versions, section_laws)

        self.assertEqual(count, 0)
        self.assertNotIn("direct_public_law_link", versions[0])

    def test_unrelated_named_laws_are_filtered_out(self):
        versions = [
            {
                "commit": "abc123",
                "named_public_laws": ["42-999"],
            }
        ]
        section_laws = [
            {"public_law": "42-272", "title": "Example Act", "status": "active"},
        ]

        count = history.attach_direct_law_links(versions, section_laws)

        self.assertEqual(count, 0)
        self.assertEqual(versions[0]["named_public_laws"], [])
        self.assertNotIn("direct_public_law_link", versions[0])


if __name__ == "__main__":
    unittest.main()
