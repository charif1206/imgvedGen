import unittest
from pathlib import Path


WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "telegram-ping.yml"


class TestTelegramPingWorkflow(unittest.TestCase):
    def test_workflow_file_exists(self) -> None:
        self.assertTrue(WORKFLOW_PATH.exists(), f"Workflow file not found: {WORKFLOW_PATH}")

    def test_workflow_uses_gemini_api(self) -> None:
        content = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("GEMINI_API_KEY", content)
        self.assertIn(":generateContent", content)
        self.assertIn("Generate Gemini message and send Telegram", content)

    def test_workflow_no_longer_uses_static_heartbeat_text(self) -> None:
        content = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertNotIn("GitHub Actions heartbeat", content)


if __name__ == "__main__":
    unittest.main()