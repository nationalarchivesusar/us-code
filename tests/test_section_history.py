import unittest

from tools.build_section_history import (
    comparison_record,
    extract_sections,
    public_law_targets,
    reconstruct_diff,
    title_filename,
)


USLM = "http://xml.house.gov/schemas/uslm/1.0"


def xml_section(*, heading="Heading", body="Body text.", source="Source credit", notes="Historical note"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<uscDoc xmlns="{USLM}">
  <main>
    <title>
      <section identifier="/us/usc/t18/s205">
        <num value="205">§ 205.</num>
        <heading>{heading}</heading>
        <subsection identifier="/us/usc/t18/s205/a">
          <num value="a">(a)</num>
          <heading class="bold">Rule</heading>
          <content><p>{body}</p></content>
        </subsection>
        <sourceCredit>{source}</sourceCredit>
        <notes><note><p>{notes}</p></note></notes>
      </section>
    </title>
  </main>
</uscDoc>
""".encode()


class SectionHistoryBuildTests(unittest.TestCase):
    def test_title_filename_normalizes_numeric_titles(self):
        self.assertEqual(title_filename("5"), "usc05.xml")
        self.assertEqual(title_filename("18"), "usc18.xml")
        self.assertEqual(title_filename("18A"), "usc18a.xml")

    def test_public_law_targets_deduplicates_section_targets(self):
        payload = {
            "laws": [
                {
                    "targets": [{"title": "18", "section": "205"}],
                    "actions": [
                        {
                            "targets": [
                                {"title": "18", "section": "205"},
                                {"title": "5", "section": "2501"},
                            ]
                        }
                    ],
                }
            ]
        }
        targets = public_law_targets(payload)
        self.assertEqual(targets["18"], {"205"})
        self.assertEqual(targets["5"], {"2501"})

    def test_statutory_text_excludes_source_credit_and_notes(self):
        record = extract_sections(xml_section(), expected_title="18")["205"]
        self.assertIn("(a) Rule Body text.", record["body"])
        self.assertNotIn("Source credit", record["text"])
        self.assertNotIn("Historical note", record["text"])

    def test_note_only_change_does_not_create_comparison(self):
        before = extract_sections(
            xml_section(source="Old source", notes="Old note"), expected_title="18"
        )["205"]
        after = extract_sections(
            xml_section(source="New source", notes="New note"), expected_title="18"
        )["205"]
        self.assertIsNone(comparison_record("18", "205", before, after, "baseline"))

    def test_amendment_diff_reconstructs_both_versions(self):
        before = extract_sections(
            xml_section(heading="Former heading", body="Former rule."),
            expected_title="18",
        )["205"]
        after = extract_sections(
            xml_section(heading="Current heading", body="Current rule."),
            expected_title="18",
        )["205"]
        record = comparison_record("18", "205", before, after, "baseline")
        self.assertEqual(record["status"], "amended")
        self.assertEqual(
            reconstruct_diff(record["diff"], "baseline"), record["baseline"]["text"]
        )
        self.assertEqual(
            reconstruct_diff(record["diff"], "current"), record["current"]["text"]
        )
        self.assertTrue(any(item["op"] == "delete" for item in record["diff"]))
        self.assertTrue(any(item["op"] == "insert" for item in record["diff"]))

    def test_added_section_is_marked_added(self):
        current = extract_sections(xml_section(), expected_title="18")["205"]
        record = comparison_record("18", "205", None, current, "baseline")
        self.assertEqual(record["status"], "added")
        self.assertFalse(record["baseline"]["present"])
        self.assertTrue(record["current"]["present"])


if __name__ == "__main__":
    unittest.main()
