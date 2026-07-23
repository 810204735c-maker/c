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


if __name__ == "__main__":
    unittest.main()
