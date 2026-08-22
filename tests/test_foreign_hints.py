import unittest
from datetime import datetime, timezone

from crawler.foreign_hints import extract_foreign_hints


NOW = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)


class ForeignHintTests(unittest.TestCase):
    def test_extracts_chinese_fields(self):
        hints = extract_foreign_hints(
            "面向2027届本科及硕士毕业生，工作地点上海、北京，"
            "市场品牌与人力资源方向，英语六级优先，网申截止2026年10月18日。",
            NOW,
        )
        self.assertEqual(hints["graduateYears"], ["2027"])
        self.assertEqual(hints["cities"], ["北京", "上海"])
        self.assertEqual(hints["jobFunctions"], ["市场/品牌", "人力资源"])
        self.assertEqual(hints["educationLevels"], ["本科", "硕士"])
        self.assertEqual(hints["englishRequirements"], ["英语六级"])
        self.assertEqual(hints["deadline"], "2026-10-18")

    def test_extracts_english_fields(self):
        hints = extract_foreign_hints(
            "China 2027 Graduate Programme for Marketing and Supply Chain. "
            "Bachelor or Master degree. Applications close on 18 October 2026.",
            NOW,
        )
        self.assertEqual(hints["graduateYears"], ["2027"])
        self.assertEqual(hints["jobFunctions"], ["市场/品牌", "供应链"])
        self.assertEqual(hints["educationLevels"], ["本科", "硕士"])
        self.assertEqual(hints["deadline"], "2026-10-18")

    def test_extracts_mainland_industrial_city_beyond_first_tier(self):
        hints = extract_foreign_hints(
            "China 2027 Graduate Programme locations: Wuxi, Kunshan and Foshan.",
            NOW,
        )
        self.assertEqual(hints["cities"], ["无锡", "昆山", "佛山"])

    def test_negative_terms_override_positive_metadata(self):
        hints = extract_foreign_hints("China 2027 Summer Internship, full-time schedule", NOW)
        self.assertIn("internship", hints["excludedEmploymentTerms"])

    def test_does_not_invent_deadline_and_ignores_invalid_dates(self):
        self.assertIsNone(extract_foreign_hints("申请日期另行通知", NOW)["deadline"])
        self.assertIsNone(extract_foreign_hints("网申截止2026年2月31日", NOW)["deadline"])

    def test_source_opt_in_extracts_application_period_range_end(self):
        text = (
            "China 2027 Graduate Programme Investment Bank Corporate Bank "
            "7 Sep - 18 Oct 2026 To be eligible for the 2027 Graduate Programme"
        )
        self.assertIsNone(extract_foreign_hints(text, NOW)["deadline"])
        hints = extract_foreign_hints(text, NOW, allow_application_range=True)
        self.assertEqual(hints["deadline"], "2026-10-18")
        self.assertEqual(hints["deadlineEvidence"], "7 Sep - 18 Oct 2026")

    def test_evidence_is_bounded(self):
        hints = extract_foreign_hints("甲" * 200 + "fluent English" + "乙" * 200, NOW)
        self.assertLessEqual(len(hints["evidence"]["英语流利"]), 120)


if __name__ == "__main__":
    unittest.main()
