import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bot


class TestHistoryFlow(unittest.TestCase):
    def test_main_writes_history_before_sending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "history.jsonl"

            def fake_send_telegram_message(bot_token: str, chat_id: str, text: str) -> dict:
                self.assertTrue(history_path.exists())
                history_lines = history_path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(history_lines), 1)

                entry = json.loads(history_lines[0])
                self.assertEqual(entry["type"], "daily_arabic_lesson")
                self.assertEqual(entry["chat_id"], "5571936375")
                self.assertEqual(entry["modality"], "image")
                self.assertEqual(entry["lesson"], "generated arabic lesson from gemini")
                self.assertEqual(text, "generated arabic lesson from gemini")
                return {"ok": True, "result": {"message_id": 99}}

            with patch.object(bot, "HISTORY_FILE", history_path), \
                 patch.object(bot, "generate_daily_arabic_lesson", return_value="generated arabic lesson from gemini"), \
                 patch.object(bot, "send_telegram_message", side_effect=fake_send_telegram_message):
                bot.main()

            self.assertTrue(history_path.exists())
            history_lines = history_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(history_lines), 1)

    def test_is_valid_arabic_lesson(self) -> None:
        valid_text = """🗓️ درس اليوم
🎯 النوع: صورة
🧩 البرومبت الأساسي
مشهد شارع قديم وقت الغروب بإضاءة ناعمة وتفاصيل واقعية.
🔍 كيف تم بناء البرومبت
تم تحديد الموضوع، البيئة، الإضاءة، والأسلوب.
🎓 مفهوم سريع
كلما كانت التعليمات أوضح، كانت النتيجة أدق.
🔁 3 تنويعات
1. نسخة صباحية بإضاءة باردة وألوان فاتحة.
2. نسخة سينمائية بعدسة واسعة وتباين أعلى.
3. نسخة فنية بأسلوب watercolor وألوان حالمة.
🕒 الطابع الزمني: 2026-04-06 16:00:00 UTC
"""

        self.assertTrue(bot.is_valid_arabic_lesson(valid_text, "image"))
        self.assertFalse(bot.is_valid_arabic_lesson(valid_text, "video"))

    def test_get_next_modality_alternates_from_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = Path(temp_dir) / "history.jsonl"

            history_path.write_text(
                json.dumps({"type": "daily_arabic_lesson", "modality": "image"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(bot.get_next_modality(history_path), "video")

            history_path.write_text(
                history_path.read_text(encoding="utf-8")
                + json.dumps({"type": "daily_arabic_lesson", "modality": "video"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(bot.get_next_modality(history_path), "image")


if __name__ == "__main__":
    unittest.main()
