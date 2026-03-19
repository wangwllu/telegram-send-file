---
name: telegram-send-file
description: Send files to Telegram via Bot API. Auto-detects current session context (chat_id/topic_id) when run from within OpenClaw — no need to specify manually in most cases.
---

# Telegram Send File

Send files to Telegram via Bot API. **Now with auto-detection of current session context.**

## Auto-Detection (Default Behavior)

When run from within an OpenClaw session, the script automatically uses the current chat and topic — **no arguments needed in most cases**:

```bash
# Simple: auto-detects current chat and topic
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py --file document.pdf
```

The script detects context from (in priority order):
1. **Explicit arguments** (`--chat-id`, `--topic-id`) — highest priority
2. **Environment variables** (`TELEGRAM_DEFAULT_CHAT_ID`, `TELEGRAM_DEFAULT_TOPIC_ID`)
3. **OpenClaw session state** (if available)

## Getting a Bot Token

### If OpenClaw is already connected to Telegram
Your bot token is already configured! The script auto-detects it from `~/.openclaw/openclaw.json`.

### Manual setup (alternative)
1. Message `@BotFather` on Telegram.
2. Send the `/newbot` command.
3. Follow the prompts to choose a display name and username for your bot.
4. Copy the bot token that BotFather shows you.
5. Save it to `~/.telegram_bot_token`:

```bash
echo "YOUR_TOKEN" > ~/.telegram_bot_token
```

## Configuration

### Environment Variables (Optional)
```bash
export TELEGRAM_DEFAULT_CHAT_ID="-1003848180061"
export TELEGRAM_DEFAULT_TOPIC_ID="3"
```

### Topic/Thread ID (for forum chats)
```bash
# Explicit topic via argument
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --file document.pdf --topic-id 3

# Or via environment variable
export TELEGRAM_DEFAULT_TOPIC_ID=3
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py --file document.pdf
```

## Usage

```bash
# Auto-detect: sends to current OpenClaw session context (simplest)
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py --file document.pdf

# Explicit chat + topic
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --chat-id 5866004662 --topic-id 3 --file document.pdf

# Send with caption
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --file image.png --caption "Screenshot"
```

## Supported Types

| Type | Extensions |
|------|------------|
| Documents | PDF, DOC, DOCX, TXT, XLS, ZIP |
| Images | PNG, JPG, GIF, WEBP |
| Audio | MP3, OGG, WAV |
| Video | MP4, AVI, MOV |
