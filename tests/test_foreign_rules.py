import json
import tempfile
import unittest
from pathlib import Path

from crawler.foreign_rules import (
    campaign_identity,
    evaluate_campaign,
    load_company_registry,
    resolve_company,
)


class ForeignRuleTests(unittest.TestCase):
    def test_accepts_only_2027_full_time_china_campaigns(self):
        accepted = evaluate_campaign(
            "Deloitte China 2027 Graduate Program 上海 全职申请",
            {"scopeCountry": "CN"},
        )
        self.assertTrue(accepted["eligible"])
        self.assertEqual(accepted["graduateYear"], "2027")
        self.assertEqual(accepted["employmentType"], "full_time")

        rejected = [
            "2027 Summer Internship Shanghai",
            "2027届暑期实习生招聘",
            "2027 Experienced Hire Beijing",
            "2026届校园招聘 中国",
            "2027 Graduate Program Hong Kong only",
        ]
        for text in rejected:
            with self.subTest(text=text):
                self.assertFalse(evaluate_campaign(text, {"scopeCountry": "CN"})["eligible"])

    def test_recognizes_formal_campaign_variants(self):
        cases = {
            "某外企中国2027届秋招正式启动": ("campus_recruitment", "autumn"),
            "某外企中国2027届春招正式启动": ("campus_recruitment", "spring"),
            "某外企中国2027届校园招聘补录": ("supplemental", "supplemental"),
            "China 2027 Management Trainee campus hiring": ("management_trainee", "annual"),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                result = evaluate_campaign(text, {"scopeCountry": "CN"})
                self.assertTrue(result["eligible"])
                self.assertEqual((result["campaignType"], result["season"]), expected)

    def test_explicit_mainland_scope_cannot_be_supplied_by_source_configuration(self):
        source = {"scopeCountry": "CN", "requireExplicitChinaEvidence": True}
        self.assertFalse(evaluate_campaign("Deloitte 2027 Graduate Program", source)["eligible"])
        self.assertFalse(evaluate_campaign("Deloitte Hong Kong, China 2027 Graduate Program", source)["eligible"])
        self.assertTrue(evaluate_campaign("Deloitte China 2027 Graduate Program", source)["eligible"])
        self.assertTrue(evaluate_campaign("Deloitte Shanghai 2027 Graduate Program", source)["eligible"])
        self.assertTrue(evaluate_campaign("Bosch Wuxi 2027 Graduate Program", source)["eligible"])
        self.assertTrue(evaluate_campaign("Company Jiangsu 2027 Campus Recruitment", source)["eligible"])

    def test_unknown_company_is_not_publishable_and_longest_alias_wins(self):
        companies = {
            "deloitte": {
                "id": "deloitte",
                "name": "德勤",
                "nameEn": "Deloitte",
                "aliases": ["德勤", "德勤中国", "Deloitte", "Deloitte China"],
                "publishable": True,
            },
            "disabled": {
                "id": "disabled",
                "aliases": ["未知公司"],
                "publishable": False,
            },
        }
        self.assertEqual(resolve_company("德勤中国2027校园招聘", {}, companies)["id"], "deloitte")
        self.assertIsNone(resolve_company("未知公司2027校园招聘", {}, companies))
        self.assertIsNone(resolve_company("money market 2027 campus recruitment", {}, companies))

    def test_source_company_id_must_resolve_to_publishable_registry_entry(self):
        companies = {
            "pwc": {"id": "pwc", "aliases": ["PwC"], "publishable": True},
            "hidden": {"id": "hidden", "aliases": ["Hidden"], "publishable": False},
        }
        self.assertEqual(resolve_company("no alias needed", {"companyId": "pwc"}, companies)["id"], "pwc")
        self.assertIsNone(resolve_company("Hidden", {"companyId": "hidden"}, companies))

    def test_identity_is_independent_of_title_and_url(self):
        first = campaign_identity("deloitte", "2027", "graduate_program", "autumn")
        replacement = campaign_identity("deloitte", "2027", "graduate_program", "autumn")
        spring = campaign_identity("deloitte", "2027", "graduate_program", "spring")
        self.assertEqual(first, replacement)
        self.assertNotEqual(first, spring)
        self.assertTrue(first[1].startswith("foreign_"))
        self.assertEqual(len(first[1]), 28)

    def test_registry_validation_rejects_unverified_or_duplicate_entries(self):
        valid = {
            "schemaVersion": 1,
            "companies": [{
                "id": "example-company",
                "name": "示例",
                "nameEn": "Example",
                "aliases": [],
                "ownership": "foreign_owned",
                "ownershipEvidenceUrl": "https://example.com/about",
                "officialDomains": ["example.com"],
                "delegatedUrlPrefixes": [],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "companies.json"
            path.write_text(json.dumps(valid), encoding="utf-8")
            loaded = load_company_registry(path)
            self.assertEqual(loaded["example-company"]["aliases"], ["示例", "Example"])

            invalid = json.loads(json.dumps(valid))
            invalid["companies"][0]["ownershipEvidenceUrl"] = ""
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ownershipEvidenceUrl"):
                load_company_registry(path)

            invalid = json.loads(json.dumps(valid))
            invalid["companies"][0]["delegatedUrlPrefixes"] = [
                "https://jobs.shared-ats.example/employer-a"
            ]
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "end with a slash"):
                load_company_registry(path)

    def test_repository_registry_contains_verified_companies_and_shell_tenant_boundary(self):
        registry_path = Path(__file__).resolve().parents[1] / "crawler" / "foreign_companies.json"
        companies = load_company_registry(registry_path)
        self.assertEqual(len(companies), 51)
        self.assertTrue({"apple", "deloitte", "tesla", "dhl", "shell"} <= set(companies))
        self.assertNotIn("myworkdayjobs.com", companies["shell"]["officialDomains"])
        self.assertEqual(
            companies["shell"]["delegatedUrlPrefixes"][0],
            "https://shell.wd3.myworkdayjobs.com/ShellCareers/",
        )

    def test_foreign_source_config_keeps_manual_and_unreviewed_platforms_disabled(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads((root / "crawler" / "foreign_sources.json").read_text(encoding="utf-8"))
        companies = load_company_registry(root / "crawler" / "foreign_companies.json")

        self.assertEqual(config["schemaVersion"], 1)
        self.assertEqual(config["targetGraduateYear"], "2027")
        self.assertTrue(config["chinaOnly"])
        sources = {item["id"]: item for item in config["sources"]}
        self.assertEqual(len(sources), len(config["sources"]))
        for source in sources.values():
            if source.get("companyId"):
                self.assertIn(source["companyId"], companies)
        roche = sources["roche-china-startup-2027"]
        self.assertTrue(roche.get("enabled", True))
        self.assertEqual(roche["companyId"], "roche")
        self.assertEqual(roche["tier"], "official_verified")
        self.assertEqual(
            roche["requiredTerms"],
            ["2027届招聘", "中国大陆学校", "正式 offer"],
        )
        shell = sources["shell-graduate-programme-2027-china"]
        self.assertTrue(shell.get("enabled", True))
        self.assertEqual(shell["companyId"], "shell")
        self.assertNotIn("allowedDomains", shell)
        self.assertEqual(
            shell["allowedUrlPrefixes"],
            ["https://shell.wd3.myworkdayjobs.com/ShellCareers/"],
        )
        self.assertFalse(sources["nowcoder-campus-schedule"]["enabled"])
        self.assertFalse(sources["shixiseng-manual"]["enabled"])
        self.assertTrue(sources["shixiseng-manual"]["manualOnly"])
        self.assertEqual(sources["shixiseng-manual"]["tier"], "manual_only")


if __name__ == "__main__":
    unittest.main()
