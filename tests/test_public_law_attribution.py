"""Regression tests for public-law to U.S. Code attribution.

Run with: python -m unittest discover -s tests -p "test_public_law_attribution.py"
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_public_laws_index import targets_from_action  # noqa: E402


class PublicLawAttributionTests(unittest.TestCase):
    def test_explicit_target_does_not_inherit_unrelated_prose_references(self):
        action = {
            "result_status": "applied",
            "final_section_or_subsection_identifier": "/us/usc/t18/s205",
            "planned_action": "Also references 22 U.S.C. § 618 for context.",
            "validation_result": "The background describes /us/usc/t5/s101.",
        }
        self.assertEqual(
            [(t["title"], t["section"]) for t in targets_from_action(action, False)],
            [("18", "205")],
        )

    def test_explanatory_citation_alone_is_not_a_target(self):
        action = {
            "result_status": "applied",
            "final_section_or_subsection_identifier": "n/a",
            "planned_action": "Mentions 22 U.S.C. § 618 without amending it",
            "xml_file_after": "usc22.xml",
        }
        self.assertEqual(targets_from_action(action, False), [])

    def test_documented_no_code_action_cannot_generate_section_links(self):
        action = {
            "result_status": "documented-no-code-action",
            "final_section_or_subsection_identifier": "/us/usc/t28/s1",
            "actual_node_ids_changed": ["rp-pl004032-t28-s1"],
        }
        self.assertEqual(targets_from_action(action, False), [])

    def test_superseded_action_cannot_generate_section_links(self):
        action = {
            "result_status": "superseded-by-later-action",
            "final_section_or_subsection_identifier": "/us/usc/t5/s101",
        }
        self.assertEqual(targets_from_action(action, False), [])

    def test_title_wide_notes_remain_title_wide(self):
        action = {
            "result_status": "applied",
            "final_section_or_subsection_identifier": "/us/usc/t5",
            "planned_action": "Title-wide historical note, not an amendment to 5 U.S.C. § 101",
        }
        targets = targets_from_action(action, False)
        self.assertEqual(len(targets), 1)
        self.assertIsNone(targets[0]["section"])
        self.assertIsNone(targets[0]["href"])

    def test_compound_explicit_targets_are_separate(self):
        action = {
            "result_status": "applied",
            "final_section_or_subsection_identifier": (
                "/us/usc/t8/s1101 | /us/usc/t8/s1551"
            ),
        }
        self.assertEqual(
            {(t["title"], t["section"]) for t in targets_from_action(action, False)},
            {("8", "1101"), ("8", "1551")},
        )

    def test_changed_node_can_ground_legacy_placement(self):
        action = {
            "result_status": "applied",
            "xml_file_after": "usc18.xml",
            "final_section_or_subsection_identifier": "n/a",
            "actual_node_ids_added": ["rp-pl041271-t18-s205"],
        }
        self.assertEqual(
            [(t["title"], t["section"]) for t in targets_from_action(action, False)],
            [("18", "205")],
        )


if __name__ == "__main__":
    unittest.main()
