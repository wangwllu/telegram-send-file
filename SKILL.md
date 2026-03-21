---
name: telegram-send-file
description: Send files to Telegram via Bot API. Auto-detects current session context (chat_id/topic_id) when run from within OpenClaw — no arguments needed in most cases.
---

# Telegram Send File

Send files to Telegram via Bot API with full error handling, progress feedback, and auto-detection of the current session context.

---

## Installation

### Prerequisites

```bash
pip install python-telegram-bot>=20.0
```

### Bot Token Setup

**Option A — OpenClaw with Telegram (recommended)**
If OpenClaw is already connected to Telegram, the bot token is auto-detected from `~/.openclaw/openclaw.json → channels.telegram.botToken`. No extra setup needed.

**Option B — Standalone / manual**

1. Message **@BotFather** on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the token BotFather shows you (format: `123456789:ABCdef...`)
4. Save it to `~/.telegram_bot_token`:

```bash
echo "YOUR_TOKEN" > ~/.telegram_bot_token
```

Or set it as an environment variable:

```bash
export TELEGRAM_BOT_TOKEN="YOUR_TOKEN"
```

---

## Quick Start

```bash
# Simplest usage — auto-detects chat and topic from OpenClaw session
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py --file document.pdf

# Explicit chat + topic
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --chat-id 123456789 --topic-id 3 --file photo.png

# With caption
python3 ~/.openclaw/skills/telegram-send-file/scripts/telegram_send_file.py \
  --file screenshot.png --caption "Bug report"
```

---

## CLI Options

| Option | Description |
|--------|-------------|
| `--file PATH` | Local file path to send |
| `--url URL` | URL to download and send |
| `--file-id ID` | Telegram file_id to forward |
| `--files PATH [PATH ...]` | Multiple files (batch mode, sequential) |
| `--chat-id ID` | Target chat ID (auto-detected from OpenClaw session) |
| `--topic-id N` | Topic/thread ID for forum chats (auto-detected) |
| `--thread-id N` | Alias for `--topic-id` |
| `--caption TEXT` | Caption for the file/media (supports HTML/Markdown) |
| `--caption-from-filename` | Use filename (without extension) as caption |
| `--parse-mode MODE` | `Markdown`, `MarkdownV2`, or `HTML` |
| `--silent` | Send silently (no notification sound) |
| `--verbose`, `-v` | Enable verbose debug output (shows file_id, upload speed, etc.) |
| `--token TOKEN` | Override bot token (or set `TELEGRAM_BOT_TOKEN`) |

---

## Configuration

### Environment Variables

```bash
# Default target (used when --chat-id / --topic-id are not provided)
export TELEGRAM_DEFAULT_CHAT_ID="-1003848180061"
export TELEGRAM_DEFAULT_TOPIC_ID="3"

# Bot token
export TELEGRAM_BOT_TOKEN="123456789:ABCdef..."

# Both can be set in your shell profile for convenience
```

### OpenClaw Session Auto-Detection

When run inside an OpenClaw session (Telegram channel), the script automatically reads the current `chat_id` and `topic_id` from `~/.openclaw/session-state.json`. This means **you don't need to specify `--chat-id` or `--topic-id`** in most cases.

Priority order for target resolution:
1. Explicit CLI flags (`--chat-id`, `--topic-id`) — highest priority
2. Environment variables (`TELEGRAM_DEFAULT_CHAT_ID`, `TELEGRAM_DEFAULT_TOPIC_ID`)
3. OpenClaw session state (lowest priority)

---

## Supported File Types

| Type | Extensions | Telegram Method |
|------|-----------|-----------------|
| Images | PNG, JPG, GIF, WEBP, BMP, SVG | `sendPhoto` |
| Video | MP4, AVI, MOV, MKV, WEBM | `sendVideo` |
| Audio | MP3, OGG, WAV, M4A, FLAC | `sendAudio` |
| Documents | PDF, DOC, DOCX, TXT, XLS, ZIP | `sendDocument` |

The appropriate Telegram API method is automatically selected based on the file extension.

---

## Examples

### Basic sending

```bash
# Image (auto-detected as photo)
python3 telegram_send_file.py --file screenshot.png

# PDF document
python3 telegram_send_file.py --file report.pdf

# With caption
python3 telegram_send_file.py --file photo.jpg --caption "Summer vacation"
```

### Caption from filename

```bash
# Uses "bug_report" as caption for bug_report.pdf
python3 telegram_send_file.py --file bug_report.pdf --caption-from-filename
```

### HTML caption (formatted)

```bash
python3 telegram_send_file.py --file doc.pdf \
  --caption "<b>Important</b> — Please review before Friday" \
  --parse-mode HTML
```

### Batch sending

```bash
# Send multiple files sequentially
python3 telegram_send_file.py \
  --files file1.pdf file2.jpg file3.zip \
  --caption "Delivery batch"
```

### Send from URL

```bash
python3 telegram_send_file.py --url "https://example.com/report.pdf"
```

### Forward existing file

```bash
python3 telegram_send_file.py --file-id "ABC123xyz"
```

### Silent send (no notification)

```bash
python3 telegram_send_file.py --file notes.pdf --silent
```

### Forum topic / thread

```bash
# Send to a specific topic in a forum
python3 telegram_send_file.py --chat-id -1003848180061 --topic-id 5 --file doc.pdf
```

### Verbose debug output

```bash
python3 telegram_send_file.py --file large_video.mp4 --verbose
# Output:
# [DEBUG] send_file: Sending video to chat ... (size: 45.2MB)
# Upload: [##########] 100%  (45.2MB / 45.2MB)  2.1MB/s
# [INFO] ✓ File sent successfully (message_id=123)
#   file_id: AgADABC...
```

---

## Error Handling

The script handles all common error cases with user-friendly messages:

| Error | Cause | Fix |
|-------|-------|-----|
| `File not found` | Local file doesn't exist or isn't readable | Check the file path |
| `Invalid bot token` | Token is wrong or revoked | Get a new one from @BotFather |
| `Chat not found` | Bot not added to the chat, or wrong chat_id | Add bot to chat or verify chat_id |
| `Bot was blocked` | User blocked the bot | Ask them to /start the bot |
| `Rate limit exceeded` | Too many requests | Wait a few seconds and retry |
| `Network error` | Connection problem | Check internet connection |

All errors print a short human-readable message and exit with code 1.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (file not found, invalid token, network error, etc.) |

---

## Logging / Debugging

Use `--verbose` (`-v`) for detailed debug output:

- Upload progress bar for files > 5 MB
- Which API method is being called
- Final `file_id` for future reuse
- Message link for group/channel sends

```bash
python3 telegram_send_file.py --file doc.pdf -v
```
