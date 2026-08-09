import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "tools" / "check_encoding.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_encoding_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_encoding_under_test"] = module
    spec.loader.exec_module(module)
    return module


class CheckEncodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def write_temp(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".xml", delete=False, encoding="utf-8"
        )
        tmp.write(text)
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return Path(tmp.name)

    def test_clean_file_has_no_failures(self):
        path = self.write_temp(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<section>Ordinary text with a genuine question, like this one?</section>\n"
        )
        failures, question_marks = self.mod.scan_file(path)
        self.assertEqual([], failures)
        self.assertEqual(1, question_marks)

    def test_replacement_character_is_a_hard_failure(self):
        path = self.write_temp("<section>Broken � text</section>\n")
        failures, _ = self.mod.scan_file(path)
        self.assertEqual(1, len(failures))
        self.assertIn("replacement character", failures[0])

    def test_mojibake_em_dash_is_a_hard_failure(self):
        mojibake_em_dash = "—".encode("utf-8").decode("latin-1")
        path = self.write_temp(f"<section>Heading{mojibake_em_dash}Body</section>\n")
        failures, _ = self.mod.scan_file(path)
        self.assertEqual(1, len(failures))
        self.assertIn("em dash", failures[0])

    def test_mojibake_curly_quote_is_a_hard_failure(self):
        mojibake_quote = "’".encode("utf-8").decode("latin-1")
        path = self.write_temp(f"<section>President{mojibake_quote}s intention</section>\n")
        failures, _ = self.mod.scan_file(path)
        self.assertEqual(1, len(failures))
        self.assertIn("right single quotation mark", failures[0])

    def test_xml_processing_instructions_are_not_flagged(self):
        path = self.write_temp(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<?xml-stylesheet type="text/css" href="usctitle.css"?>\n'
            "<section>No stray punctuation here.</section>\n"
        )
        failures, question_marks = self.mod.scan_file(path)
        self.assertEqual([], failures)
        self.assertEqual(0, question_marks)

    def test_lfs_pointer_file_is_skipped(self):
        path = self.write_temp(
            "version https://git-lfs.github.com/spec/v1\noid sha256:abc\nsize 123\n"
        )
        failures, question_marks = self.mod.scan_file(path)
        self.assertEqual([], failures)
        self.assertEqual(0, question_marks)

    def test_main_returns_nonzero_when_a_failure_is_present(self):
        path = self.write_temp("<section>Broken � text</section>\n")
        exit_code = self.mod.main([str(path)])
        self.assertEqual(1, exit_code)

    def test_main_returns_zero_for_clean_input(self):
        path = self.write_temp("<section>All clear, right?</section>\n")
        exit_code = self.mod.main([str(path)])
        self.assertEqual(0, exit_code)


class Title18SentencingRegressionTests(unittest.TestCase):
    """Protect the Roblox catalog from charge-classification/filter regressions."""

    @classmethod
    def setUpClass(cls):
        base = ROOT / "data" / "api" / "v1" / "criminal-law"
        charges_path = base / "charges.json"
        if not charges_path.is_file():
            raise unittest.SkipTest("Generated criminal-law API is not present")
        cls.base = base
        cls.payload = json.loads(charges_path.read_text(encoding="utf-8"))
        cls.manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        cls.sentencing = json.loads((base / "sentencing.json").read_text(encoding="utf-8"))
        cls.title18 = [
            item for item in cls.payload.get("charges", [])
            if item.get("source") == "title18"
        ]
        cls.title18_by_section = {
            str(item.get("section")): item for item in cls.title18
        }

    def test_title18_has_both_automatic_and_manual_entries(self):
        automatic = [
            item for item in self.title18
            if item.get("sentencing_mode") == "automatic_class_rule"
        ]
        manual = [
            item for item in self.title18
            if item.get("sentencing_mode") == "manual_required"
        ]
        self.assertGreater(len(automatic), 0)
        self.assertGreater(len(manual), 0)
        self.assertEqual(len(self.title18), len(automatic) + len(manual))

    def test_automatic_title18_entries_have_class_and_sentence_metadata(self):
        automatic = [
            item for item in self.title18
            if item.get("sentencing_mode") == "automatic_class_rule"
        ]
        for item in automatic:
            with self.subTest(section=item.get("section")):
                self.assertIn(item.get("offense_category"), {"felony", "misdemeanor"})
                self.assertIn(item.get("offense_class"), {"A", "B", "C", "D", "E"})
                self.assertEqual(item.get("classification_status"), "derived_from_title18")
                self.assertIsInstance(item.get("suggested_minutes"), (int, float))
                self.assertGreater(item["suggested_minutes"], 0)
                self.assertIn("18 U.S.C. § 3559", item.get("classification_basis", ""))

    def test_multitier_section_111_remains_manual(self):
        section_111 = self.title18_by_section["111"]
        self.assertEqual(section_111.get("sentencing_mode"), "manual_required")
        self.assertEqual(
            section_111.get("classification_status"),
            "manual_review_required",
        )

    def test_escape_section_751_remains_bookable_with_body_withheld(self):
        section_751 = self.title18_by_section["751"]
        self.assertEqual(section_751.get("charge_classification"), "known_positive_charge")
        self.assertEqual(section_751.get("sentencing_mode"), "manual_required")
        self.assertTrue(section_751.get("text_withheld"))

        detail = json.loads((self.base / "title18" / "751.json").read_text(encoding="utf-8"))
        self.assertEqual(detail.get("heading"), "Prisoners in custody of institution or officer")
        self.assertTrue(detail.get("text_withheld"))
        self.assertEqual(detail.get("text_display_scope"), "withheld_for_platform_safety")

    def test_unusual_criminal_drafting_forms_remain_bookable(self):
        # Representative sections from every drafting form that the old exact-
        # phrase classifier missed: conditional penalties, incorporated penalty
        # sections, guilt declarations, punishable-by clauses, em-dash penalty
        # lists, and direct substantive prohibitions.
        required = {
            "40", "40A", "153", "203", "204", "205", "208", "209", "213",
            "241", "371", "372", "402", "514", "650", "752", "842", "922",
            "937", "956", "1031", "1113", "1115", "1117", "1120", "1121",
            "1366", "1389", "1501", "1694", "1695", "1725", "1865", "1866",
            "1917", "1962", "2119", "2319B", "2319C", "2384", "2722",
        }
        missing = sorted(required - set(self.title18_by_section))
        self.assertEqual([], missing, f"Legitimate Title 18 charges were filtered out: {missing}")

    def test_secondary_body_hits_with_safe_metadata_are_withheld_not_deleted(self):
        # These sections were previously false negatives because the secondary
        # screen searched the entire detail record and deleted the charge when a
        # restricted word appeared only in the body.
        sections = {"112", "226", "491", "832", "970", "1001", "1505", "2280"}
        missing = sorted(sections - set(self.title18_by_section))
        self.assertEqual([], missing, f"Body-only safety hits deleted safe charges: {missing}")
        for section in sorted(sections):
            with self.subTest(section=section):
                item = self.title18_by_section[section]
                self.assertTrue(item.get("text_withheld"))
                detail = json.loads(
                    (self.base / "title18" / f"{section}.json").read_text(encoding="utf-8")
                )
                self.assertTrue(detail.get("text_withheld"))
                self.assertEqual(
                    detail.get("text_display_scope"),
                    "withheld_for_platform_safety",
                )

    def test_explicit_platform_exclusions_stay_excluded(self):
        excluded = {
            "41", "42", "43", "47", "48", "49", "175", "1091", "1368",
            "2280a", "2283", "2316", "2317", "2340A", "2441",
        }
        leaked = sorted(excluded & set(self.title18_by_section))
        self.assertEqual([], leaked, f"Explicit Roblox exclusions leaked into booking: {leaked}")

    def test_secondary_filter_is_charge_preserving_v5(self):
        roblox = self.manifest.get("roblox") or {}
        surface = roblox.get("public_surface") or {}
        self.assertEqual("roblox-safe-charge-only-v5", roblox.get("filter_version"))
        self.assertTrue(surface.get("preserve_safe_charge_metadata_when_body_withheld"))

    def test_classifier_audit_finds_no_obvious_charge_syntax_false_negatives(self):
        # Independent source-level audit: deliberately use simpler/broader
        # offense signals than the production classifier. If a future Title 18
        # section has unmistakable criminal syntax but production fails to
        # recognize it, CI must fail instead of silently dropping the charge.
        tools_dir = str(ROOT / "tools")
        if tools_dir not in sys.path:
            sys.path.insert(0, tools_dir)
        import build_criminal_law_api as builder
        import harden_roblox_criminal_api as production

        audit_non_charge_heading = re.compile(
            r"\b(?:definitions?|defined|rules?|regulations?|reports?|construction|"
            r"applicability|jurisdiction|venue|limitations?|procedures?|administrative|"
            r"authorization|appropriations?|duties|powers|findings|severability|"
            r"separability|preemption|exceptions?|exemptions?|immunity|disclosure|"
            r"records?|civil remedies?|civil proceedings?|civil actions?|injunctions?|"
            r"forfeitures?|restitution|sentencing|penalties|penalty|licensing|"
            r"licenses? and user permits|laws? governing|exclusive remedies|"
            r"effect on state law)\b",
            re.I,
        )
        audit_signals = (
            re.compile(r"\b(?:it\s+)?(?:is|shall\s+be)\s+unlawful\b", re.I),
            re.compile(r"\bno\s+person\s+shall\b", re.I),
            re.compile(r"\b(?:shall\s+be|is|are)\s+guilty\s+of\b", re.I),
            re.compile(
                r"\bshall\b[^.;]{0,560}\b(?:be\s+)?"
                r"(?:fined|imprisoned|punished|sentenced)\b",
                re.I | re.S,
            ),
            re.compile(
                r"\bpunishable\s+by\b[^.;]{0,320}\b(?:fine|imprisonment)\b",
                re.I | re.S,
            ),
            re.compile(
                r"\bsubject\s+to\b[^.;]{0,220}"
                r"\b(?:felony|misdemeanor|criminal\s+offense)\b",
                re.I | re.S,
            ),
        )
        framework_sections = {"2", "1153"}
        misses = []
        for detail in builder.title18_sections(ROOT / "usc" / "usc18.xml"):
            section = str(detail.get("section") or "")
            heading = str(detail.get("heading") or "")
            body = str(detail.get("text") or "")
            if detail.get("status") != "current" or not detail.get("charge_candidate"):
                continue
            if section in framework_sections or audit_non_charge_heading.search(heading):
                continue
            if not any(pattern.search(body) for pattern in audit_signals):
                continue
            if not production.title18_is_positive_charge(detail):
                misses.append((section, heading))

        self.assertEqual([], misses, f"Classifier missed charge-like Title 18 sections: {misses}")

    def test_roblox_booking_cap_is_20_without_rewriting_statutory_ceiling(self):
        policy = self.payload.get("sentencing_policy") or {}
        roblox = self.manifest.get("roblox") or {}
        booking = self.sentencing.get("roblox_booking_policy") or {}
        statutory = (self.sentencing.get("rules") or {}).get("multi_charge_max_minutes")

        self.assertEqual(30, statutory)
        self.assertEqual(20, policy.get("multi_charge_max_minutes"))
        self.assertEqual(20, roblox.get("multi_charge_max_minutes"))
        self.assertEqual(20, booking.get("multi_charge_max_minutes"))
        self.assertEqual(30, policy.get("statutory_multi_charge_max_minutes"))
        self.assertEqual(30, roblox.get("statutory_multi_charge_max_minutes"))
        self.assertEqual(30, booking.get("statutory_multi_charge_max_minutes"))


if __name__ == "__main__":
    unittest.main()
