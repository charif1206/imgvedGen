import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("prompt_tutor_bot")

IMAGE_CATEGORIES = [
    "Image prompting basics",
    "Subject description",
    "Environment description",
    "Lighting",
    "Camera angle",
    "Lens and shot type",
    "Mood and atmosphere",
    "Style transfer",
    "Realism vs stylization",
    "Cinematic prompting",
    "Negative prompting",
    "Prompt refinement",
    "Prompt variations",
    "Story-based prompting",
    "Character consistency",
    "Scene consistency",
    "Common prompting mistakes",
]

VIDEO_CATEGORIES = [
    "Video prompting basics",
    "Subject description",
    "Environment description",
    "Lighting",
    "Camera angle",
    "Lens and shot type",
    "Motion description",
    "Mood and atmosphere",
    "Style transfer",
    "Realism vs stylization",
    "Cinematic prompting",
    "Negative prompting",
    "Prompt refinement",
    "Prompt variations",
    "Story-based prompting",
    "Character consistency",
    "Scene consistency",
    "Shot sequencing for video",
    "Common prompting mistakes",
]

REQUIRED_MARKERS = [
    "🎯 Lesson:",
    "📌 Focus:",
    "🧩 Base Prompt:",
    "🔍 Breakdown:",
    "🎛️ How to modify it:",
    "🧪 Practice:",
    "🔥 Bonus Challenge:",
]

SYSTEM_INSTRUCTIONS = """
You are an AI tutor bot specialized in teaching Image Prompting and Video Prompting through short, structured lessons.

Mission:
- Help the learner improve step by step from beginner to advanced in image and video prompting.
- Every response must be a mini-lesson that teaches exactly one concept.

Teaching style:
- Clear, friendly, encouraging, practical.
- Keep lessons concise and usable immediately.
- Do not overwhelm the learner.

Output constraints:
- Keep each lesson between 120 and 220 words.
- Always include at least one ready-to-use prompt.
- Always explain why the prompt works.
- Always include creative variations.
- Always include one short exercise and one bonus challenge.
- Avoid repetition and keep each lesson fresh.

Required output format exactly:
🎯 Lesson: [short title]

📌 Focus:
[1-2 sentences explaining the idea]

🧩 Base Prompt:
"[insert prompt here]"

🔍 Breakdown:
- [phrase or keyword] -> [why it matters]
- [phrase or keyword] -> [why it matters]
- [phrase or keyword] -> [why it matters]

🎛️ How to modify it:
- To make it more realistic: ...
- To make it more cinematic: ...
- To change the style: ...
- To change the mood: ...
- To change camera or motion: ...

🧪 Practice:
[give the user a short task]

🔥 Bonus Challenge:
[give a harder variation]

Additional rules:
- Alternate image and video lessons when mode is auto.
- If learner asks for examples, provide 3 variations: simple, strong, cinematic/creative.
- If learner asks to improve a prompt, analyze and rewrite with explanation.
- For image lessons, emphasize subject, composition, lighting, style, detail level, mood, and camera terms when relevant.
- For video lessons, emphasize subject movement, camera movement, scene progression, pacing, cinematic action, environmental motion, and continuity.
""".strip()


class ChatStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._data: Dict[str, Any] = {"chats": {}}
        self._load_from_disk()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "active": False,
            "mode": "auto",
            "next_modality": "image",
            "lesson_count": 0,
            "image_index": 0,
            "video_index": 0,
            "level": "beginner",
        }

    def _load_from_disk(self) -> None:
        if not self.path.exists():
            return

        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            if "chats" not in self._data:
                self._data = {"chats": {}}
        except Exception as exc:
            logger.warning("Could not load chat state file: %s", exc)
            self._data = {"chats": {}}

    def _save_unlocked(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _ensure_unlocked(self, chat_id: int) -> Dict[str, Any]:
        key = str(chat_id)
        if key not in self._data["chats"]:
            self._data["chats"][key] = self._default_state()
        return self._data["chats"][key]

    async def get(self, chat_id: int) -> Dict[str, Any]:
        async with self._lock:
            state = self._ensure_unlocked(chat_id)
            return json.loads(json.dumps(state))

    async def update(self, chat_id: int, updater) -> Dict[str, Any]:
        async with self._lock:
            state = self._ensure_unlocked(chat_id)
            updater(state)
            self._save_unlocked()
            return json.loads(json.dumps(state))

    async def active_chat_ids(self) -> List[int]:
        async with self._lock:
            chat_ids: List[int] = []
            for key, state in self._data["chats"].items():
                if state.get("active"):
                    chat_ids.append(int(key))
            return chat_ids


class GeminiLessonEngine:
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )

    async def generate_lesson(
        self,
        modality: str,
        category: str,
        level: str,
        lesson_number: int,
        user_request: Optional[str] = None,
    ) -> str:
        feedback = ""
        for attempt in range(3):
            user_prompt = self._build_user_prompt(
                modality=modality,
                category=category,
                level=level,
                lesson_number=lesson_number,
                user_request=user_request,
                feedback=feedback,
            )

            text = await self._call_gemini(user_prompt)
            if self._is_valid_lesson(text):
                return text

            wc = self._word_count(text)
            feedback = (
                "Your previous output was invalid. "
                f"Word count was {wc}. Include all required sections exactly once and keep 120-220 words."
            )

        return self._fallback_lesson(modality, category)

    def _build_user_prompt(
        self,
        modality: str,
        category: str,
        level: str,
        lesson_number: int,
        user_request: Optional[str],
        feedback: str,
    ) -> str:
        lines = [
            f"Generate lesson #{lesson_number}.",
            f"Target learner level: {level}.",
            f"Lesson modality: {modality}.",
            f"Current teaching category: {category}.",
            "Keep difficulty progressive and practical.",
            "Use simple language if the user appears beginner.",
            "Do not include extra sections outside the required format.",
            "The full response must be 120-220 words.",
        ]

        if user_request:
            lines.append(f"Learner request: {user_request}")

        if feedback:
            lines.append(feedback)

        return "\n".join(lines)

    async def _call_gemini(self, user_prompt: str) -> str:
        payload = {
            "system_instruction": {
                "parts": [
                    {
                        "text": SYSTEM_INSTRUCTIONS,
                    }
                ]
            },
            "contents": [
                {
                    "parts": [
                        {
                            "text": user_prompt,
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.8,
                "topP": 0.95,
            },
        }

        params = {"key": self.api_key}
        timeout = httpx.Timeout(40.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self.endpoint, params=params, json=payload)
            response.raise_for_status()
            data = response.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [part.get("text", "") for part in parts if part.get("text")]
        text = "\n".join(text_parts).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response")

        return text

    def _word_count(self, text: str) -> int:
        return len(re.findall(r"\b\w+\b", text))

    def _is_valid_lesson(self, text: str) -> bool:
        if not text:
            return False

        for marker in REQUIRED_MARKERS:
            if marker not in text:
                return False

        wc = self._word_count(text)
        return 120 <= wc <= 220

    def _fallback_lesson(self, modality: str, category: str) -> str:
        motion_line = "camera motion"
        if modality == "image":
            motion_line = "camera angle"

        return (
            f"🎯 Lesson: Precision Through {category}\n\n"
            "📌 Focus:\n"
            "Today you will learn to add one high-impact detail that makes prompts clearer and easier for a model to execute. "
            "A strong prompt names the subject, the setting, and one technical cue.\n\n"
            "🧩 Base Prompt:\n"
            f'"A lone traveler crossing a windy desert at sunset, wide composition, dramatic side lighting, realistic detail, calm but tense mood, {motion_line} kept steady."\n\n'
            "🔍 Breakdown:\n"
            "- lone traveler -> gives the model a clear subject\n"
            "- windy desert at sunset -> anchors environment and time\n"
            "- dramatic side lighting -> shapes mood and visual depth\n\n"
            "🎛️ How to modify it:\n"
            "- To make it more realistic: add natural textures like dust, skin detail, and cloth folds.\n"
            "- To make it more cinematic: increase contrast and include a stronger horizon line.\n"
            "- To change the style: switch to watercolor, anime ink, or documentary realism.\n"
            "- To change the mood: use hopeful dawn colors or harsh storm tones.\n"
            "- To change camera or motion: use close-up framing or a slow tracking movement.\n\n"
            "🧪 Practice:\n"
            "Rewrite the base prompt with a different subject but keep the same lighting strategy.\n\n"
            "🔥 Bonus Challenge:\n"
            "Create two versions of the same scene, one realistic and one stylized, while keeping composition consistent."
        )


def choose_modality(state: Dict[str, Any]) -> str:
    mode = state.get("mode", "auto")
    if mode in ("image", "video"):
        return mode
    return state.get("next_modality", "image")


def choose_category(state: Dict[str, Any], modality: str) -> str:
    if modality == "image":
        idx = int(state.get("image_index", 0))
        return IMAGE_CATEGORIES[idx % len(IMAGE_CATEGORIES)]

    idx = int(state.get("video_index", 0))
    return VIDEO_CATEGORIES[idx % len(VIDEO_CATEGORIES)]


def detect_mode_hint(text: str) -> Optional[str]:
    lowered = text.lower()
    if "image only" in lowered or "only image" in lowered or "only images" in lowered:
        return "image"
    if "video only" in lowered or "only video" in lowered or "only videos" in lowered:
        return "video"
    return None


async def send_next_lesson(
    app: Application,
    chat_id: int,
    user_request: Optional[str] = None,
) -> None:
    store: ChatStore = app.bot_data["store"]
    engine: GeminiLessonEngine = app.bot_data["engine"]

    state = await store.get(chat_id)
    modality = choose_modality(state)
    category = choose_category(state, modality)
    lesson_number = int(state.get("lesson_count", 0)) + 1

    lesson = await engine.generate_lesson(
        modality=modality,
        category=category,
        level=state.get("level", "beginner"),
        lesson_number=lesson_number,
        user_request=user_request,
    )

    await app.bot.send_message(chat_id=chat_id, text=lesson)

    def updater(current: Dict[str, Any]) -> None:
        current["lesson_count"] = int(current.get("lesson_count", 0)) + 1
        if modality == "image":
            current["image_index"] = int(current.get("image_index", 0)) + 1
        else:
            current["video_index"] = int(current.get("video_index", 0)) + 1

        if current.get("mode", "auto") == "auto":
            current["next_modality"] = "video" if modality == "image" else "image"

    await store.update(chat_id, updater)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    store: ChatStore = context.application.bot_data["store"]

    await store.update(chat_id, lambda s: s.update({"active": True}))
    await send_next_lesson(
        app=context.application,
        chat_id=chat_id,
        user_request="First lesson for a beginner. Keep it simple and confidence-building.",
    )


async def lesson_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    store: ChatStore = context.application.bot_data["store"]
    await store.update(chat_id, lambda s: s.update({"active": True}))

    request = None
    if context.args:
        request = " ".join(context.args)

    await send_next_lesson(app=context.application, chat_id=chat_id, user_request=request)


async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return

    if not context.args:
        await update.message.reply_text("Usage: /mode auto|image|video")
        return

    mode = context.args[0].strip().lower()
    if mode not in {"auto", "image", "video"}:
        await update.message.reply_text("Mode must be one of: auto, image, video")
        return

    chat_id = update.effective_chat.id
    store: ChatStore = context.application.bot_data["store"]

    await store.update(chat_id, lambda s: s.update({"mode": mode, "active": True}))
    await update.message.reply_text(f"Learning mode set to: {mode}")


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    store: ChatStore = context.application.bot_data["store"]
    await store.update(chat_id, lambda s: s.update({"active": False}))
    await update.message.reply_text("Scheduled lessons paused.")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    store: ChatStore = context.application.bot_data["store"]
    await store.update(chat_id, lambda s: s.update({"active": True}))
    await update.message.reply_text("Scheduled lessons resumed.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    store: ChatStore = context.application.bot_data["store"]
    state = await store.get(chat_id)

    status = (
        f"Active: {state.get('active')}\n"
        f"Mode: {state.get('mode')}\n"
        f"Next modality: {state.get('next_modality')}\n"
        f"Lessons sent: {state.get('lesson_count')}"
    )
    await update.message.reply_text(status)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_chat or not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    message_text = update.message.text.strip()
    store: ChatStore = context.application.bot_data["store"]

    mode_hint = detect_mode_hint(message_text)
    if mode_hint:
        await store.update(chat_id, lambda s: s.update({"mode": mode_hint, "active": True}))
    else:
        await store.update(chat_id, lambda s: s.update({"active": True}))

    await send_next_lesson(
        app=context.application,
        chat_id=chat_id,
        user_request=message_text,
    )


async def scheduled_lesson_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    app = context.application
    store: ChatStore = app.bot_data["store"]

    for chat_id in await store.active_chat_ids():
        try:
            await send_next_lesson(
                app=app,
                chat_id=chat_id,
                user_request="Scheduled follow-up lesson. Continue progression and avoid repeating prior concepts.",
            )
        except Exception as exc:
            logger.exception("Failed to send scheduled lesson to %s: %s", chat_id, exc)


def build_application() -> Application:
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()
    interval_seconds = int(os.getenv("LESSON_INTERVAL_SECONDS", "7200"))

    if not telegram_token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in environment")
    if not gemini_api_key:
        raise RuntimeError("Missing GEMINI_API_KEY in environment")

    app = Application.builder().token(telegram_token).build()

    data_path = Path("data") / "chats.json"
    store = ChatStore(data_path)
    engine = GeminiLessonEngine(api_key=gemini_api_key, model=gemini_model)

    app.bot_data["store"] = store
    app.bot_data["engine"] = engine

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("lesson", lesson_command))
    app.add_handler(CommandHandler("mode", mode_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    if app.job_queue is None:
        raise RuntimeError("Job queue is not available. Install telegram bot with job-queue extras.")

    app.job_queue.run_repeating(
        callback=scheduled_lesson_job,
        interval=interval_seconds,
        first=30,
        name="scheduled_lessons",
    )

    return app


def main() -> None:
    # PTB 21.x expects a default event loop in the main thread.
    # Python 3.14 may not provide one implicitly.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app = build_application()
    logger.info("Prompt tutor bot started")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
