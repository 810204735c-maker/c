import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "update-jobs.yml"


class WorkflowTests(unittest.TestCase):
    def test_pages_actions_use_node24_compatible_majors(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("actions/upload-pages-artifact@v5", workflow)
        self.assertIn("actions/deploy-pages@v5", workflow)
        self.assertNotIn("actions/upload-pages-artifact@v3", workflow)
        self.assertNotIn("actions/deploy-pages@v4", workflow)

    def test_workflow_refreshes_validates_and_commits_foreign_channel(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("python crawler/foreign_crawl.py", workflow)
        self.assertIn("--config crawler/foreign_sources.json", workflow)
        self.assertIn("--companies crawler/foreign_companies.json", workflow)
        self.assertIn("--output data/foreign-campus.json", workflow)
        self.assertIn("--health-output data/foreign-health.json", workflow)
        self.assertIn("python scripts/check_foreign_snapshot.py", workflow)
        self.assertIn("data/foreign-campus.json data/foreign-health.json", workflow)
        self.assertIn("crawler/cache/foreign-details.json", workflow)
        self.assertIn("crawler/cache/foreign-seen.json", workflow)


if __name__ == "__main__":
    unittest.main()
