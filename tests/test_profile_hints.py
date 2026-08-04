import unittest

from crawler.profile_hints import extract_profile_hints


class ProfileHintTests(unittest.TestCase):
    def test_extracts_chinese_major_roles_qualifications_and_evidence(self):
        text = (
            "宣传岗位负责文稿起草、新媒体编辑和品牌传播。"
            "专业要求：中国语言文学、新闻传播学。"
            "硕士研究生及以上，中共党员优先。"
        )

        hints = extract_profile_hints(text)

        self.assertEqual(hints["schemaVersion"], 3)
        self.assertEqual(hints["majorTags"], ["中国语言文学"])
        self.assertEqual(
            hints["roleTags"],
            ["综合文字", "宣传文化", "新媒体"],
        )
        self.assertEqual(hints["qualificationTags"], ["硕士", "中共党员"])
        self.assertIn("中国语言文学", hints["evidence"]["中国语言文学"])
        self.assertIn("文稿起草", hints["evidence"]["综合文字"])

    def test_extracts_graduate_year_teacher_certificate_and_experience(self):
        text = (
            "面向2027届应届毕业生，须取得高中语文教师资格证。"
            "另一社会招聘岗位要求具有2年以上相关工作经历。"
        )

        hints = extract_profile_hints(text)

        self.assertEqual(hints["graduateYears"], ["2027"])
        self.assertEqual(
            hints["qualificationTags"],
            ["应届", "教师资格证", "工作经历"],
        )

    def test_does_not_invent_hints_from_generic_recruitment_copy(self):
        hints = extract_profile_hints("现面向社会公开招聘工作人员，具体岗位见附件。")

        self.assertEqual(hints["majorTags"], [])
        self.assertEqual(hints["roleTags"], [])
        self.assertEqual(hints["qualificationTags"], [])
        self.assertEqual(hints["graduateYears"], [])
        self.assertEqual(hints["evidence"], {})

    def test_ignores_public_account_and_publishing_boilerplate(self):
        text = (
            "后续通知将在微信公众号发布，请考生及时关注。"
            "本次招考不出版辅导用书，社会发行的出版物与本单位无关。"
        )

        hints = extract_profile_hints(text)

        self.assertEqual(hints["roleTags"], [])

    def test_ignores_editorial_metadata_and_navigation_labels(self):
        text = "【责任编辑：王晓蕾】\n政务新媒体"

        hints = extract_profile_hints(text)

        self.assertEqual(hints["roleTags"], [])

    def test_keeps_specific_editorial_and_public_account_duties(self):
        text = "报刊编辑负责稿件校对，并承担公众号运营和内容策划工作。"

        hints = extract_profile_hints(text)

        self.assertEqual(hints["roleTags"], ["编辑出版", "新媒体"])

    def test_evidence_is_bounded(self):
        text = "甲" * 200 + "专业要求中国语言文学" + "乙" * 200

        hints = extract_profile_hints(text)

        self.assertLessEqual(len(hints["evidence"]["中国语言文学"]), 120)


if __name__ == "__main__":
    unittest.main()
