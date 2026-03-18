---
name: telegram-send-file
description: Send files to Telegram chats via Bot API. **ALWAYS use this skill when user asks to send, share, deliver, or attach any file via Telegram.** Trigger immediately when user says: "发给我", "发送文件", "把文件发给我", "send me", "send file", "share file", "发文件", or any request to transfer files via Telegram. This is the primary skill for file delivery to Telegram.
---

# Telegram Send File

Send files to Telegram using the Bot API.

## IMPORTANT: When to Use

**ALWAYS use this skill when user asks to send any file via Telegram.**

## Configuration

### Token
Set via environment variable:
```bash
export TELEGRAM_BOT_TOKEN="your-token-here"
```
Or create file: `~/.telegram_bot_token`

### Chat ID
From message metadata: `chat_id` or `sender_id`

## Quick Usage

```bash
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --chat-id <CHAT_ID> --file <FILE_PATH>
```

## Supported Types

- **Documents**: PDF, DOC, DOCX, TXT, XLS, ZIP
- **Images**: PNG, JPG, GIF, WEBP
- **Audio**: MP3, OGG, WAV
- **Video**: MP4, AVI, MOV
