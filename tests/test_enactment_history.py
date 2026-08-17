import json
import tempfile
import unittest
from pathlib import Path

from tools.build_enactment_history import build_records, target_from_identifier, write_dataset


class EnactmentHistoryTests(unittest.TestCase):
    def test_target_parser_preserves_alphanumeric_sections_and_subsections(self):
        self.assertEqual(
            target_from_identifier('/us/usc/t28/s530E/a/1'),
            {
                'title': '28',
                'section': '530E',
                'subsection_path': 'a/1',
                'usc_node_id': '/us/usc/t28/s530E/a/1',
            },
        )

    def test_only_applied_substantive_section_actions_are_published(self):
        audit = {
            'status': 'complete',
            'baseline_commit': 'baseline123',
            'results': [
                {
                    'action_id': 'A1',
                    'public_law': '41-271',
                    'provision_reference': 'SEC. 4',
                    'planned_action': 'insert new section',
                    'planned_treatment': 'new-section',
                    'result_status': 'applied',
                    'final_section_or_subsection_identifier': '/us/usc/t18/s205',
                    'actual_node_ids_added': ['node-205'],
                    'source_file': 'law.txt',
                    'source_quotation': 'source words',
                    'validation_result': 'validated',
                },
                {
                    'action_id': 'A2',
                    'public_law': '41-271',
                    'planned_action': 'add statutory note',
                    'planned_treatment': 'statutory-note',
                    'result_status': 'applied',
                    'final_section_or_subsection_identifier': '/us/usc/t18/s205',
                    'actual_node_ids_changed': ['note-node'],
                },
                {
                    'action_id': 'A3',
                    'public_law': '42-1',
                    'planned_action': 'amend existing text',
                    'planned_treatment': 'amend-existing-text',
                    'result_status': 'planned',
                    'final_section_or_subsection_identifier': '/us/usc/t18/s205',
                    'actual_node_ids_changed': ['node-205'],
                },
                {
                    'action_id': 'A4',
                    'public_law': '42-2',
                    'planned_action': 'amend existing text',
                    'planned_treatment': 'amend-existing-text',
                    'result_status': 'applied',
                    'final_section_or_subsection_identifier': '/us/usc/t18',
                    'actual_node_ids_changed': ['title-node'],
                },
            ],
        }
        laws = {
            'laws': [
                {
                    'public_law': '41-271',
                    'title': 'Example Act',
                    'status': 'active',
                    'trello_url': 'https://example.invalid/law',
                }
            ]
        }
        manifest, sections = build_records(audit, laws)
        self.assertEqual(manifest['counts']['events'], 1)
        self.assertEqual(manifest['counts']['sections'], 1)
        event = sections[('18', '205')]['events'][0]
        self.assertEqual(event['public_law'], '41-271')
        self.assertEqual(event['change_labels'], ['added'])
        self.assertTrue(event['verified_enactment_event'])
        self.assertFalse(event['exact_text_snapshot_available'])
        self.assertIsNone(event['exact_text_snapshot'])
        self.assertNotIn('exact_enacted_text_applied', json.dumps(event))

    def test_multiple_actions_for_one_law_and_section_collapse_into_one_event(self):
        audit = {
            'results': [
                {
                    'action_id': 'A1', 'public_law': '7-39', 'provision_reference': 'SEC. 1(a)',
                    'planned_action': 'amend existing text', 'planned_treatment': 'amend-existing-text',
                    'result_status': 'applied', 'final_section_or_subsection_identifier': '/us/usc/t42/s217/a',
                    'actual_node_ids_changed': ['x'], 'validation_result': 'ok',
                },
                {
                    'action_id': 'A2', 'public_law': '7-39', 'provision_reference': 'SEC. 1(b)',
                    'planned_action': 'amend existing text', 'planned_treatment': 'amend-existing-text',
                    'result_status': 'applied', 'final_section_or_subsection_identifier': '/us/usc/t42/s217/b',
                    'actual_node_ids_changed': ['y'], 'validation_result': 'ok',
                },
            ]
        }
        manifest, sections = build_records(audit, {'laws': []})
        self.assertEqual(manifest['counts']['events'], 1)
        event = sections[('42', '217')]['events'][0]
        self.assertEqual(event['source_provisions'], ['SEC. 1(a)', 'SEC. 1(b)'])
        self.assertEqual(event['subsection_paths'], ['a', 'b'])
        self.assertEqual(event['changed_node_ids'], ['x', 'y'])

    def test_writer_creates_manifest_and_section_files(self):
        manifest = {'counts': {'events': 1}, 'sections': {}}
        sections = {('18', '205'): {'citation': '18 U.S.C. § 205', 'events': []}}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_dataset(manifest, sections, root)
            self.assertTrue((root / 'manifest.json').is_file())
            self.assertTrue((root / '18' / '205.json').is_file())


if __name__ == '__main__':
    unittest.main()
