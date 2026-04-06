from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import unittest

EXPECTED_CHAT_ID = "5571936375"
EXPECTED_BOT_ID = "8600089290"


def load_env_file() -> dict:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    loaded: dict = {}

    if not env_path.exists():
        return loaded

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        loaded[key.strip()] = value.strip()

    return loaded


class TestDirectTelegramSend(unittest.TestCase):
    def test_send_direct_message(self) -> None:
        env_file = load_env_file()

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN", env_file.get("TELEGRAM_BOT_TOKEN", "")).strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", env_file.get("TELEGRAM_CHAT_ID", "")).strip()

        self.assertTrue(bot_token)
        self.assertEqual(bot_token.split(":", 1)[0], EXPECTED_BOT_ID)
        self.assertEqual(chat_id, EXPECTED_CHAT_ID)

        text = (
            "IDE direct test message | "
            + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8", errors="replace")

        data = json.loads(payload)
        self.assertTrue(data.get("ok"), msg=str(data))

        message_id = data.get("result", {}).get("message_id")
        print(f"Direct test sent successfully (message_id={message_id})")


if __name__ == "__main__":
    unittest.main()
