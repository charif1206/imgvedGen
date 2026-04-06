import unittest

from bot import (
    GeminiLessonEngine,
    choose_category,
    choose_modality,
    detect_mode_hint,
    extract_data_request,
)


def build_valid_lesson_text() -> str:
    return """🎯 Lesson: Building Better Prompts

📌 Focus:
Today we practice writing prompts that are clear, specific, and visually consistent from the first sentence to the final detail. This helps models produce more reliable outputs.

🧩 Base Prompt:
"A young explorer standing on a cliff at sunrise, wide shot, golden rim light, realistic textures, calm wind, cinematic color grading"

🔍 Breakdown:
- young explorer -> defines a specific subject identity
- cliff at sunrise -> anchors location and time clearly
- cinematic color grading -> shapes mood and output style

🎛️ How to modify it:
- To make it more realistic: add natural texture cues and subtle imperfections.
- To make it more cinematic: increase contrast and dynamic framing.
- To change the style: switch to watercolor, anime, or noir photography.
- To change the mood: shift to stormy tones or warm hopeful light.
- To change camera or motion: use close-up framing or a slow dolly move.

🧪 Practice:
Rewrite the prompt with a different subject while keeping the same lighting logic.

🔥 Bonus Challenge:
Create two versions of the same scene, one realistic and one stylized, while keeping composition stable."""


def build_valid_data_text() -> str:
    return """📊 Data Brief:
The latest snapshot shows stable short-term movement with moderate uncertainty due to market volatility and source timing differences. Momentum appears constructive but not decisive, so trend confirmation still matters.

🧾 Key Data:
- 24h change near 1.8% -> indicates modest upward momentum
- trading volume up around 6% -> suggests higher participation
- seven-day range remained narrow -> reflects temporary consolidation

⚠️ Confidence:
These values are directional estimates and can shift quickly as new data arrives. Different exchanges and update windows may show slightly different numbers.

✅ Next Step:
Track the same three indicators every 6 hours to confirm whether the trend is strengthening or fading, and log each snapshot in one table so pattern changes are easier to compare over time."""


class TestBotCore(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = GeminiLessonEngine(api_key="test-key", model="gemini-2.0-flash")

    def test_choose_modality_respects_explicit_mode(self) -> None:
        self.assertEqual(choose_modality({"mode": "image", "next_modality": "video"}), "image")
        self.assertEqual(choose_modality({"mode": "video", "next_modality": "image"}), "video")

    def test_choose_modality_uses_next_modality_in_auto(self) -> None:
        self.assertEqual(choose_modality({"mode": "auto", "next_modality": "video"}), "video")
        self.assertEqual(choose_modality({"mode": "auto"}), "image")

    def test_choose_category_wraps_indexes(self) -> None:
        image_state = {"image_index": 10_000}
        video_state = {"video_index": 10_000}

        self.assertIsInstance(choose_category(image_state, "image"), str)
        self.assertIsInstance(choose_category(video_state, "video"), str)

    def test_detect_mode_hint(self) -> None:
        self.assertEqual(detect_mode_hint("please use image only for now"), "image")
        self.assertEqual(detect_mode_hint("i want only video lessons"), "video")
        self.assertIsNone(detect_mode_hint("teach me prompting basics"))

    def test_extract_data_request(self) -> None:
        self.assertEqual(extract_data_request("data: btc trend last 24h"), "btc trend last 24h")
        self.assertEqual(extract_data_request("  DATA : weather in paris  "), "weather in paris")
        self.assertIsNone(extract_data_request("just normal chat"))

    def test_valid_lesson_text_passes_validator(self) -> None:
        self.assertTrue(self.engine._is_valid_lesson(build_valid_lesson_text()))

    def test_invalid_lesson_text_fails_validator(self) -> None:
        invalid = "🎯 Lesson: Too Short\n\n📌 Focus:\nThis misses most required sections."
        self.assertFalse(self.engine._is_valid_lesson(invalid))

    def test_valid_data_text_passes_validator(self) -> None:
        self.assertTrue(self.engine._is_valid_data_message(build_valid_data_text()))

    def test_invalid_data_text_fails_validator(self) -> None:
        invalid = "📊 Data Brief:\nToo short and incomplete."
        self.assertFalse(self.engine._is_valid_data_message(invalid))


if __name__ == "__main__":
    unittest.main()