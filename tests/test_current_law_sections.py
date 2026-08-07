import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from lxml import etree as ET

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'apply_current_law_sections.py'
spec = importlib.util.spec_from_file_location('current_law_sections', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

NS = mod.NS
q = mod.q


def title_doc(title, body_builder):
    root = ET.Element(q('uscDoc'), nsmap={None: NS}, identifier=f'/us/usc/t{title}')
    main = ET.SubElement(root, q('main'))
    t = ET.SubElement(main, q('title'), identifier=f'/us/usc/t{title}', id=f'base-t{title}')
    ET.SubElement(t, q('num'), value=str(title)).text = f'Title {title}—'
    ET.SubElement(t, q('heading')).text = 'TEST TITLE'
    toc = ET.SubElement(t, q('toc'), role='threeColumnTOC', id=f'base-t{title}-toc')
    layout = ET.SubElement(toc, q('layout'))
    body_builder(t, layout)
    return ET.ElementTree(root)


def add_chapter(parent, parent_layout, title, chapter, first_section, heading='Existing'):
    item = mod.chapter_toc(title, f'{parent.get("identifier")}/ch{chapter}', str(chapter), heading, str(first_section))
    item.set('id', f'base-t{title}-ch{chapter}-toc')
    parent_layout.append(item)
    ch = ET.SubElement(parent, q('chapter'), identifier=f'{parent.get("identifier")}/ch{chapter}', id=f'base-t{title}-ch{chapter}')
    ET.SubElement(ch, q('num'), value=str(chapter)).text = f'CHAPTER {chapter}—'
    ET.SubElement(ch, q('heading')).text = heading
    toc = ET.SubElement(ch, q('toc'), role='twoColumnTOC', id=f'base-t{title}-ch{chapter}-toc2')
    layout = ET.SubElement(toc, q('layout'))
    ET.SubElement(ET.SubElement(layout, q('header')), q('column')).text = 'Sec.'
    return ch, layout


class OverlayTests(unittest.TestCase):
    def test_round_trip_all_operation_types(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'usc').mkdir()

            def build5(t, layout):
                part = ET.SubElement(t, q('part'), identifier='/us/usc/t5/ptIII', id='base-t5-ptIII')
                pt_toc = ET.SubElement(part, q('toc'), role='threeColumnTOC', id='base-t5-ptIII-toc')
                pt_layout = ET.SubElement(pt_toc, q('layout'))
                sub = ET.SubElement(part, q('subpart'), identifier='/us/usc/t5/ptIII/sptA', id='base-t5-sptA')
                ch, ch_layout = add_chapter(sub, pt_layout, 5, 23, 2301, 'Merit System Principles')
                sec = ET.SubElement(ch, q('section'), identifier='/us/usc/t5/s2301', id='base-t5-s2301')
                ET.SubElement(sec, q('num'), value='2301').text = '§ 2301.'
                ET.SubElement(ET.SubElement(sec, q('content')), q('p')).text = 'Existing merit system principles text.'
                ch_layout.append(mod.section_toc(5, '2301', 'Merit system principles'))

            def build6(t, layout):
                add_chapter(t, layout, 6, 6, 1500, 'Cybersecurity')

            def build18(t, layout):
                ch, ch_layout = add_chapter(t, layout, 18, 11, 201, 'Bribery, Graft, and Conflicts of Interest')
                sec = ET.SubElement(ch, q('section'), identifier='/us/usc/t18/s205', id='base-t18-s205')
                ET.SubElement(sec, q('num'), value='205').text = '§ 205.'
                ET.SubElement(sec, q('heading')).text = ' Activities of officers and employees'
                ET.SubElement(ET.SubElement(sec, q('content')), q('p')).text = 'Existing sufficiently long substantive section text for validation.'
                ET.SubElement(sec, q('sourceCredit'), id='base-t18-s205-source').text = '(Existing law.)'
                notes = ET.SubElement(sec, q('notes'), type='uscNote', id='base-t18-s205-notes')
                note = ET.SubElement(notes, q('note'), id='rp-pl041271-codification', topic='amendments')
                ET.SubElement(note, q('heading')).text = 'Old Great Change note'
                ET.SubElement(note, q('p')).text = 'Old note text.'
                ch_layout.append(mod.section_toc(18, '205', 'Activities of officers and employees'))

            docs = {5: title_doc(5, build5), 6: title_doc(6, build6), 18: title_doc(18, build18)}
            for title, tree in docs.items():
                tree.write(root / 'usc' / f'usc{title:02d}.xml', encoding='UTF-8', xml_declaration=True)

            manifest = {
                'schema_version': '1.0',
                'chapters': [{
                    'title': 6,
                    'parent_identifier': '/us/usc/t6',
                    'toc_parent_identifier': '/us/usc/t6',
                    'chapter': '7',
                    'heading': 'FEDERAL LAW ENFORCEMENT COMMUNICATIONS AND COORDINATION',
                    'sections': [{
                        'section': '1801', 'heading': 'Definitions',
                        'paragraphs': ['This section contains a sufficiently long permanent rule for testing purposes.'],
                        'source': 'Homeland Security Coordination Act, H.R. 9, 42d Cong.', 'source_section': '2'
                    }],
                    'chapter_notes': [{'heading': 'Short Title', 'text': 'This chapter may be cited as the test Act.'}]
                }, {
                    'title': 5,
                    'parent_identifier': '/us/usc/t5/ptIII/sptA',
                    'toc_parent_identifier': '/us/usc/t5/ptIII',
                    'chapter': '25',
                    'heading': 'COMMISSIONED SERVICE STAFFING AND CONTINUITY',
                    'sections': [{
                        'section': '2501', 'heading': 'Minimum commissioned staffing',
                        'paragraphs': ['Each covered agency shall maintain the required minimum staffing level at all times.'],
                        'source': 'Pub. L. 41–271', 'source_section': '501'
                    }],
                    'chapter_notes': []
                }],
                'existing_chapter_sections': [{
                    'title': 5,
                    'chapter_identifier': '/us/usc/t5/ptIII/sptA/ch23',
                    'sections': [{
                        'section': '2308', 'heading': 'Protected disclosures',
                        'paragraphs': ['A covered employee may make a protected disclosure through an authorized channel without retaliation.'],
                        'source': 'Pub. L. 41–271', 'source_section': '601'
                    }]
                }],
                'section_subsections': [{
                    'title': 18,
                    'section_identifier': '/us/usc/t18/s205',
                    'subsections': [{
                        'label': 'k', 'heading': 'Definitions',
                        'paragraphs': ['For purposes of this section, the terms used in this subsection have the meanings provided by law.']
                    }],
                    'notes': [{'heading': '2026 Amendment', 'text': 'Pub. L. 41–271 added and revised conflict-of-interest provisions.'}]
                }],
                'replacement_notes': [{
                    'title': 18, 'note_id': 'rp-pl041271-codification', 'topic': 'amendments',
                    'heading': 'The Great Change Act of 2026',
                    'paragraphs': ['The Act is consolidated into the subject-matter titles of the United States Code.']
                }]
            }

            old_title_path = mod.title_path
            try:
                mod.title_path = lambda title: root / 'usc' / f'usc{title:02d}.xml'
                affected = mod.apply(manifest, write=True)
                self.assertEqual(affected, [5, 6, 18])
                mod.verify(manifest)
                mod.apply(manifest, write=True)
                mod.verify(manifest)
            finally:
                mod.title_path = old_title_path

            t5 = mod.parse_title(root / 'usc' / 'usc05.xml').getroot()
            self.assertIsNotNone(mod.find_identifier(t5, '/us/usc/t5/ptIII/sptA/ch25'))
            self.assertIsNotNone(mod.find_identifier(t5, '/us/usc/t5/s2308'))
            self.assertEqual(len(t5.xpath("//*[@identifier='/us/usc/t5/s2501']")), 1)

            t6 = mod.parse_title(root / 'usc' / 'usc06.xml').getroot()
            self.assertIsNotNone(mod.find_identifier(t6, '/us/usc/t6/ch7'))
            self.assertIsNotNone(mod.find_identifier(t6, '/us/usc/t6/s1801'))

            t18 = mod.parse_title(root / 'usc' / 'usc18.xml').getroot()
            self.assertIsNotNone(mod.find_identifier(t18, '/us/usc/t18/s205/k'))
            note = t18.xpath("//*[@id='rp-pl041271-codification']")[0]
            self.assertIn('consolidated', ' '.join(note.itertext()).lower())


if __name__ == '__main__':
    unittest.main()
