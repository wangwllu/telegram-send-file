---
name: telegram-send-file
description: Comprehensive Telegram file-delivery skill for Bot API transfers. Trigger whenever the user asks to send, share, deliver, upload, attach, forward, push, transmit, or return any local/generated file to Telegram chat(s), group(s), or recipient(s), whether Telegram is named explicitly or implied by context (chat_id, sender_id, bot message metadata, prior Telegram workflow, or "send it to me" after creating a file). Trigger for all file types (documents, images, audio, video, archives, logs, exports, reports, screenshots) and all path forms (absolute paths, relative paths, newly created output artifacts, wildcard-selected files, or attachments referenced in conversation). Trigger on multilingual variants and paraphrases, including Chinese intents such as "发给我", "给我发", "发送", "传给我", "发一下", "把这个发我", "发到电报", "发到TG", "发群里", "转发到Telegram", and English intents such as "send me", "send this", "share it", "upload to Telegram", "forward to Telegram", "post in Telegram", "deliver the file", "attach and send". Trigger even when request is indirect ("after you generate it, send it to me on Telegram", "push output to the bot", "drop it in our Telegram group") or embedded inside larger tasks. Treat this as the default and authoritative skill for any Telegram-bound file transfer workflow.
---

# Telegram Send File

Send files to Telegram via Bot API.

## When to Use

**USE THIS SKILL for EVERY file sending request to Telegram.**

## Getting a Bot Token

### If OpenClaw is already connected to Telegram
Your bot token is already configured! Find it at:
```
~/.openclaw/openclaw.json → channels.telegram.botToken
```
The skill will auto-detect it from there — no extra setup needed.

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

### Token (auto-detected, no setup needed for OpenClaw users)
The script auto-detects the token from (in order of priority):
1. `TELEGRAM_BOT_TOKEN` environment variable
2. `~/.telegram_bot_token` file
3. `~/.openclaw/openclaw.json → channels.telegram.botToken` ← **OpenClaw 用户无需配置！**
```

### Chat ID
From message metadata: `chat_id` or `sender_id`

## Usage

```bash
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --chat-id <CHAT_ID> --file <FILE_PATH> [--caption "text"]
```

## Examples

```bash
# Send document
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --chat-id 5866004662 --file /path/to/file.pdf

# Send with caption
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --chat-id 5866004662 --file image.png --caption "Screenshot"
```

## Supported Types

| Type | Extensions |
|------|------------|
| Documents | PDF, DOC, DOCX, TXT, XLS, ZIP |
| Images | PNG, JPG, GIF, WEBP |
| Audio | MP3, OGG, WAV |
| Video | MP4, AVI, MOV |
