# Image + Video Prompt Tutor Bot

Telegram bot that teaches prompt writing through short lessons every 2 hours.

## Features
- Gemini-powered mini-lessons with a fixed teaching format
- Alternates between image prompting and video prompting in `auto` mode
- Persists per-chat progress and preferences
- Sends scheduled lessons every 2 hours
- Handles direct learning requests from users in chat
- Supports Gemini data replies via `/data` and `data: ...` messages

## Setup
1. Create and activate a Python virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill values:
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
4. Run the bot:
   ```bash
   python bot.py
   ```

## Commands
- `/start` - activate tutoring and receive your first lesson
- `/lesson` - get an immediate lesson
- `/data <question>` - get a structured data-focused response from Gemini
- `/mode auto|image|video` - choose alternation or fixed lesson type
- `/pause` - stop scheduled lessons
- `/resume` - resume scheduled lessons
- `/status` - view current learning mode and progress

## Notes
- The bot stores chat state in `data/chats.json`.
- Scheduled lessons use `LESSON_INTERVAL_SECONDS` (default 7200 seconds).
- You can also send `data: your question` in chat to trigger a data response.

## Testing
Run automated checks with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

If you use the project virtual environment on Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
# imgvedGen
