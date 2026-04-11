# Tg_kino_bot

A simple Telegram bot for sharing movies through channel subscription checks.

## Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
4. Set your bot token in `.env`:
   ```env
   API_TOKEN=8731382216:AAHQk8iYperJ3Uhsky0HKkMqW7OBYDQRqak
   ```

## Run

```bash
python main.py
```

## Notes

- The bot requires a Telegram channel subscription check.
- The channel username and ID are configurable in `main.py`.
- Store the token securely and do not commit `.env` to source control.
