import unittest

from crawler.application_hints import extract_application_hints


class ApplicationHintTests(unittest.TestCase):
    def test_extracts_methods_materials_and_evidence(self):
        text = (
            "请登录报名系统进行网上报名，并上传报名表、身份证正反面、"
            "学历学位证书及学信网学籍在线验证报告。"
        )

        hints = extract_application_hints(text)

        self.assertEqual(hints["schemaVersion"], 1)
        self.assertEqual(hints["methods"], ["网上报名"])
        self.assertEqual(
            hints["materialTags"],
            ["报名表", "身份证", "学历学位证明", "学信网证明"],
        )
        self.assertIn("报名系统", hints["evidence"]["网上报名"])

    def test_extracts_email_and_on_site_application(self):
        text = (
            "报名材料发送至指定邮箱，压缩包内附个人简历和近期免冠证件照。"
            "无法线上提交的，可携带劳动合同到现场报名。"
        )

        hints = extract_application_hints(text)

        self.assertEqual(hints["methods"], ["邮箱报名", "现场报名"])
        self.assertEqual(
            hints["materialTags"],
            ["个人简历", "工作经历证明", "近期照片"],
        )

    def test_ignores_generic_contact_email_and_unmentioned_materials(self):
        hints = extract_application_hints("咨询邮箱：help@example.gov.cn，请保持电话畅通。")

        self.assertEqual(hints["methods"], [])
        self.assertEqual(hints["materialTags"], [])
        self.assertEqual(hints["evidence"], {})

    def test_evidence_is_bounded(self):
        hints = extract_application_hints("甲" * 200 + "报名表" + "乙" * 200)

        self.assertLessEqual(len(hints["evidence"]["报名表"]), 120)

    def test_extracts_english_application_materials(self):
        hints = extract_application_hints(
            "Apply online with your resume, transcript, cover letter, portfolio and IELTS score."
        )

        self.assertEqual(hints["methods"], ["网上报名"])
        self.assertEqual(
            hints["materialTags"],
            ["个人简历", "成绩单", "作品材料", "求职信", "语言成绩"],
        )
        self.assertIn("Apply online", hints["evidence"]["网上报名"])


if __name__ == "__main__":
    unittest.main()
