import unittest

from tools.build_enactment_history import build_records
from tools.usc_target_normalization import (
    canonicalize_audit_payload,
    expand_authoritative_targets,
    fold_section_token,
    parse_section_identifier,
    resolve_canonical_section,
)


class UscTargetNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.index = {
            '8': {
                '1101': '1101',
                '1182': '1182',
                '1532': '1532',
            },
            '20': {
                '3404': '3404',
                '3411': '3411',
                '3412': '3412',
                '3413': '3413',
            },
            '42': {
                '2000e': '2000e',
                '2000e–2': '2000e–2',
                '2000e-2': '2000e–2',
            },
        }

    def test_legacy_question_mark_resolves_to_live_dash_section(self):
        self.assertEqual(fold_section_token('2000e?2'), '2000e-2')
        self.assertEqual(
            resolve_canonical_section('42', '2000e?2', self.index),
            '2000e–2',
        )
        parsed = parse_section_identifier(
            '/us/usc/t42/s2000e?2/a/1', self.index
        )
        self.assertEqual(parsed['section'], '2000e–2')
        self.assertEqual(
            parsed['identifier'], '/us/usc/t42/s2000e–2/a/1'
        )

    def test_explicit_compound_target_beats_inferred_nearby_section(self):
        targets = [
            {
                'identifier': (
                    '/us/usc/t42/s2000e?2/a/1 | '
                    '/us/usc/t42/s2000e?2/a/2'
                ),
                'title': '42',
                'section': '2000e?2',
                'inferred': False,
            },
            {
                'identifier': '/us/usc/t42/s2000e',
                'title': '42',
                'section': '2000e',
                'inferred': True,
            },
        ]
        expanded = expand_authoritative_targets(targets, self.index)
        self.assertEqual(len(expanded), 2)
        self.assertEqual({item['section'] for item in expanded}, {'2000e–2'})
        self.assertFalse(any(item.get('inferred') for item in expanded))
        self.assertFalse(any(item['section'] == '2000e' for item in expanded))

    def test_compound_audit_record_expands_to_each_section(self):
        payload = {
            'status': 'complete',
            'results': [
                {
                    'action_id': 'A1',
                    'public_law': '17-129',
                    'planned_action': 'insert new subsection',
                    'planned_treatment': 'new-subsection',
                    'result_status': 'applied',
                    'final_section_or_subsection_identifier': (
                        '/us/usc/t20/s3404 | /us/usc/t20/s3411 | '
                        '/us/usc/t20/s3412 | /us/usc/t20/s3413'
                    ),
                    'actual_node_ids_added': ['node-a'],
                }
            ],
        }
        canonical = canonicalize_audit_payload(payload, self.index)
        identifiers = {
            row['final_section_or_subsection_identifier']
            for row in canonical['results']
        }
        self.assertEqual(
            identifiers,
            {
                '/us/usc/t20/s3404',
                '/us/usc/t20/s3411',
                '/us/usc/t20/s3412',
                '/us/usc/t20/s3413',
            },
        )
        self.assertEqual(
            canonical['canonical_target_expansion'],
            {'source_record_count': 1, 'expanded_record_count': 4},
        )

    def test_enactment_builder_receives_separate_canonical_sections(self):
        payload = {
            'status': 'complete',
            'baseline_commit': 'base',
            'results': [
                {
                    'action_id': 'A1',
                    'public_law': '17-129',
                    'planned_action': 'insert new subsection',
                    'planned_treatment': 'new-subsection',
                    'result_status': 'applied',
                    'final_section_or_subsection_identifier': (
                        '/us/usc/t20/s3404 | /us/usc/t20/s3411'
                    ),
                    'actual_node_ids_added': ['node-a'],
                }
            ],
        }
        canonical = canonicalize_audit_payload(payload, self.index)
        manifest, sections = build_records(canonical, {'laws': []})
        self.assertEqual(manifest['counts']['sections'], 2)
        self.assertEqual(manifest['counts']['events'], 2)
        self.assertIn(('20', '3404'), sections)
        self.assertIn(('20', '3411'), sections)
        self.assertFalse(
            any('|' in section for _, section in sections)
        )


if __name__ == '__main__':
    unittest.main()
