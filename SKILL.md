---
name: telegram-send-file
description: Send files to Telegram. **USE THIS SKILL whenever user requests any file to be sent/delivered/shared via Telegram, without exception.** Triggers on any of: (1) Chinese: "发给我", "发送文件", "把文件发给我", "发文件", "发过来", "发一下", "把这个发给我", "给我发", "发个我", "你能发给我吗", "帮我发", "帮我把"; (2) English: "send me", "send file", "send to telegram", "share file", "share via telegram", "deliver file", "attach file"; (3) Any request involving file paths or attachments to be sent to Telegram. This is the ONLY skill for file transfer to Telegram.
---

# Telegram Send File

Send files to Telegram via Bot API.

## When to Use

**USE THIS SKILL for EVERY file sending request to Telegram.**

## Configuration

### Token (from OpenClaw or set manually)
```bash
echo "YOUR_TOKEN" > ~/.telegram_bot_token
export TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
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
