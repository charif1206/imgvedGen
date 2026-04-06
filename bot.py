import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
HISTORY_FILE = Path(__file__).resolve().parent / "data" / "history.jsonl"
REQUIRED_LESSON_MARKERS = [
    "🗓️ درس اليوم",
    "🎯 النوع",
    "🧩 البرومبت الأساسي",
    "🔍 كيف تم بناء البرومبت",
    "🎓 مفهوم سريع",
    "🔁 3 تنويعات",
    "🕒 الطابع الزمني",
]


@dataclass
class Config:
    telegram_bot_token: str
    telegram_chat_id: str
    gemini_api_key: str
    gemini_model: str


def load_env_file() -> dict:
    env_path = Path(__file__).resolve().parent / ".env"
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


def load_config() -> Config:
    env_file = load_env_file()
    return Config(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", env_file.get("TELEGRAM_BOT_TOKEN", "")).strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", env_file.get("TELEGRAM_CHAT_ID", "")).strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", env_file.get("GEMINI_API_KEY", "")).strip(),
        gemini_model=os.getenv("GEMINI_MODEL", env_file.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)).strip(),
    )


def get_next_modality(history_path: Path) -> str:
    if not history_path.exists():
        return "image"

    lines = history_path.read_text(encoding="utf-8").splitlines()
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if entry.get("type") != "daily_arabic_lesson":
            continue

        last_modality = entry.get("modality")
        if last_modality == "image":
            return "video"
        if last_modality == "video":
            return "image"

    return "image"


def append_history_entry(
    history_path: Path,
    lesson_text: str,
    chat_id: str,
    model: str,
    modality: str,
) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "type": "daily_arabic_lesson",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chat_id": chat_id,
        "model": model,
        "modality": modality,
        "lesson": lesson_text,
    }

    with history_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def is_valid_arabic_lesson(text: str, modality: str) -> bool:
    if not text.strip():
        return False

    for marker in REQUIRED_LESSON_MARKERS:
        if marker not in text:
            return False

    required_type = "صورة" if modality == "image" else "فيديو"
    if f"🎯 النوع: {required_type}" not in text:
        return False

    variation_count = len(re.findall(r"(?m)^\s*[1-3]\.\s", text))
    return variation_count >= 3


def generate_daily_arabic_lesson(
    api_key: str,
    model: str,
    modality: str,
    retries: int = 3,
) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    nonce = f"{int(time.time())}-{random.randint(1000, 9999)}"
    modality_ar = "صورة" if modality == "image" else "فيديو"

    modality_rules = (
        "اكتب برومبت صورة ثابتة بدون أوامر حركة للكاميرا."
        if modality == "image"
        else "اكتب برومبت فيديو يتضمن حركة موضوع واضحة وحركة كاميرا مناسبة."
    )
    feedback = ""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    for attempt in range(1, retries + 1):
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "أنشئ درس prompting يومي باللغة العربية لمرسل Telegram. "
                                f"نوع الدرس المطلوب الآن: {modality_ar}. "
                                "يجب أن تكون الرسالة تعليمية وعملية ومناسبة للمبتدئين. "
                                "الرسالة يجب أن تتضمن: "
                                "1) برومبت عالي الجودة. "
                                "2) شرح كيف تم بناء البرومبت (الأسلوب، العناصر، البنية). "
                                "3) شرح مبسط لمفهوم prompting. "
                                "4) ثلاث تنويعات لنفس البرومبت عبر تغيير عناصر مفتاحية. "
                                f"{modality_rules} "
                                "اكتب الرسالة بهذا القالب وبنفس العناوين: "
                                "🗓️ درس اليوم\n"
                                f"🎯 النوع: {modality_ar}\n"
                                "🧩 البرومبت الأساسي\n"
                                "🔍 كيف تم بناء البرومبت\n"
                                "🎓 مفهوم سريع\n"
                                "🔁 3 تنويعات\n"
                                "اجعل الطول بين 180 و 320 كلمة. "
                                "يجب أن تبدأ التنويعات بالأرقام 1. 2. 3. "
                                "أضف سطرًا أخيرًا بعنوان 🕒 الطابع الزمني يحتوي الوقت التالي مرة واحدة فقط. "
                                f"الوقت: {now}. "
                                f"Nonce: {nonce}. "
                                f"{feedback}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 1.0,
                "topP": 0.95,
            },
        }

        body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8", errors="replace")
                data = json.loads(raw)

            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned no candidates")

            parts = candidates[0].get("content", {}).get("parts", [])
            text_parts = [part.get("text", "") for part in parts if part.get("text")]
            text = "\n".join(text_parts).strip()
            if not text:
                raise RuntimeError("Gemini returned empty text")

            if is_valid_arabic_lesson(text, modality):
                return text

            if attempt < retries:
                feedback = (
                    "الإخراج السابق غير مطابق للقالب المطلوب. "
                    "التزم بالعناوين المطلوبة وبالنوع الصحيح وبثلاث تنويعات مرقمة 1. 2. 3."
                )
                time.sleep(attempt)
                continue

            raise RuntimeError("Gemini returned lesson text with invalid structure")
        except urllib.error.HTTPError as exc:
            transient_codes = {429, 500, 502, 503, 504}
            if exc.code in transient_codes and attempt < retries:
                time.sleep(attempt * 3)
                continue

            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini request failed with status {exc.code}: {error_body}") from exc
        except urllib.error.URLError as exc:
            if attempt < retries:
                time.sleep(attempt * 3)
                continue
            raise RuntimeError(f"Network error while calling Gemini: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini returned invalid JSON") from exc

    raise RuntimeError("Gemini request failed after retries")


def send_telegram_message(bot_token: str, chat_id: str, text: str) -> dict:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram request failed with status {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while sending Telegram message: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Telegram returned invalid JSON") from exc

    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")

    return data


def main() -> None:
    config = load_config()

    if not config.telegram_bot_token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in .env")
    if not config.telegram_chat_id:
        raise RuntimeError("Missing TELEGRAM_CHAT_ID in .env")
    if not config.gemini_api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in .env")

    modality = get_next_modality(HISTORY_FILE)
    lesson = generate_daily_arabic_lesson(
        config.gemini_api_key,
        config.gemini_model,
        modality,
    )
    append_history_entry(
        HISTORY_FILE,
        lesson,
        config.telegram_chat_id,
        config.gemini_model,
        modality,
    )
    result = send_telegram_message(config.telegram_bot_token, config.telegram_chat_id, lesson)

    message_id = result.get("result", {}).get("message_id")
    print("Message sent successfully")
    print(f"Lesson type: {modality}")
    print(f"Chat ID: {config.telegram_chat_id}")
    print(f"Telegram message_id: {message_id}")
    print(f"Sent text: {lesson}")


if __name__ == "__main__":
    main()
