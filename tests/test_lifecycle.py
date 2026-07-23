import unittest
from datetime import datetime, timezone

from crawler.lifecycle import extract_registration_window


NOW = datetime(2026, 7, 20, 2, 30, tzinfo=timezone.utc)


class RegistrationWindowTests(unittest.TestCase):
    def test_registration_range_ignores_later_exam_dates(self):
        result = extract_registration_window(
            "报名时间：7月10日9:00至7月20日17:00，7月21日打印准考证，7月25日笔试。",
            NOW,
        )

        self.assertEqual(result["registrationStart"], "2026-07-10")
        self.assertEqual(result["registrationEnd"], "2026-07-20")
        self.assertEqual(result["deadlineConfidence"], "high")
        self.assertIn("报名时间", result["deadlineEvidence"])
        self.assertNotIn("笔试", result["deadlineEvidence"])

    def test_explicit_registration_extension_overrides_original_end(self):
        result = extract_registration_window(
            "原报名时间为7月10日至7月20日。经研究，报名截止时间延长至7月23日。",
            NOW,
        )

        self.assertEqual(result["registrationStart"], "2026-07-10")
        self.assertEqual(result["registrationEnd"], "2026-07-23")
        self.assertIn("延长至7月23日", result["deadlineEvidence"])

    def test_cross_year_registration_range_advances_the_end_year(self):
        result = extract_registration_window(
            "报名时间为2026年12月20日至2027年1月5日，考试时间另行通知。",
            NOW,
        )

        self.assertEqual(result["registrationStart"], "2026-12-20")
        self.assertEqual(result["registrationEnd"], "2027-01-05")

    def test_unrelated_dates_without_registration_context_are_unknown(self):
        result = extract_registration_window("7月20日打印准考证，7月25日组织笔试。", NOW)

        self.assertIsNone(result["registrationStart"])
        self.assertIsNone(result["registrationEnd"])
        self.assertEqual(result["deadlineConfidence"], "unknown")
        self.assertEqual(result["deadlineEvidence"], "")


if __name__ == "__main__":
    unittest.main()
