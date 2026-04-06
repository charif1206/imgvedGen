# Arabic Prompting Lesson Bot

This bot generates a new daily prompting lesson in Arabic on each run and sends it to Telegram.

## Setup
1. No external dependencies are required.
2. Optional (creates/updates local environment only):
   ```bash
   pip install -r requirements.txt
   ```
3. Ensure `.env` contains:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `GEMINI_API_KEY`
   - `GEMINI_MODEL` (optional, default: `gemini-2.5-flash`)

## Run Bot Once
```bash
python bot.py
```
Each run will:
- generate an Arabic lesson from Gemini,
- include either an image prompt or a video prompt,
- explain the prompt construction,
- teach prompting concepts simply,
- include 3 variations,
- save the lesson in `data/history.jsonl`,
- send the lesson to Telegram.

## GitHub Actions Schedule (Every 2 Hours)
Workflow file: `.github/workflows/send-arabic-lesson.yml`

It runs automatically every 2 hours (UTC) and can also be run manually via `workflow_dispatch`.

Required GitHub repository secrets:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GEMINI_API_KEY`
- `GEMINI_MODEL` (optional)

## Direct IDE Test (no Gemini)
```bash
python -m unittest tests.test_send_direct -v
```
This test sends one direct Telegram message to verify token/chat configuration from IDE.

## Flow Test
```bash
python tests/test_history_flow.py
```
This verifies that lesson history is written before Telegram send.
