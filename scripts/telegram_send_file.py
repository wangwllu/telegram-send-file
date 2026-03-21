#!/usr/bin/env python3
"""
Telegram File Sender — Send files via Telegram Bot API

Supports:
- Local file sending (with progress feedback for large files)
- URL file sending
- File ID forwarding
- Batch sending
- Auto-detection of chat_id/topic_id from OpenClaw session

Usage:
    python telegram_send_file.py --file document.pdf
    python telegram_send_file.py --file image.png --caption "Screenshot"
    python telegram_send_file.py --files file1.pdf file2.jpg

Requires: python-telegram-bot>=20.0
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, List, Union

try:
    from telegram import Bot, InputFile
    from telegram.error import (
        TelegramError,
        BadRequest,
        NetworkError,
        RetryAfter,
        Forbidden,
        NotFound,
        ChatNotFound,
        InvalidToken,
        TimedOut,
    )
except ImportError:
    print("Error: python-telegram-bot not installed. Run: pip install python-telegram-bot")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure structured logging."""
    logger = logging.getLogger("telegram_send_file")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    # Avoid duplicate handlers on re-runs
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = "[%(levelname)s] %(message)s" if not verbose else "[%(levelname)s] %(funcame)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    return logger

logger = None  # lazily initialized

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def get_token() -> str:
    """Get bot token from environment or config file, with clear error messages."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token

    config_paths = [
        Path.home() / ".config" / "telegram-send-file" / "config",
        Path.home() / ".telegram_bot_token",
        Path.home() / "telegram_token",
        Path.home() / ".openclaw" / "openclaw.json",
    ]

    for config_path in config_paths:
        if not config_path.exists():
            continue
        try:
            if config_path.name == "openclaw.json":
                with open(config_path) as f:
                    data = json.load(f)
                token = data.get("channels", {}).get("telegram", {}).get("botToken")
            else:
                token = config_path.read_text().strip()
            if token:
                return token
        except Exception:
            pass

    # Provide the most helpful error message
    openclaw_token_missing = (
        "\n"
        "  Tip: If you're running inside OpenClaw with a Telegram channel configured,\n"
        "       the bot token should be auto-detected from:\n"
        "         ~/.openclaw/openclaw.json → channels.telegram.botToken\n"
    )

    raise ValueError(
        "Telegram bot token not found.\n"
        "\n"
        "To fix:\n"
        "  1. Message @BotFather on Telegram\n"
        "  2. Send /newbot and follow the prompts\n"
        "  3. Copy the token (looks like: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)\n"
        "  4. Save it:\n"
        "       echo 'YOUR_TOKEN' > ~/.telegram_bot_token\n"
        "     or set it in your environment:\n"
        "       export TELEGRAM_BOT_TOKEN='YOUR_TOKEN'\n"
        + openclaw_token_missing
    )


# ---------------------------------------------------------------------------
# Session / context detection
# ---------------------------------------------------------------------------

def get_default_target() -> tuple:
    """
    Get default chat_id and topic_id from environment or OpenClaw session state.
    Returns (chat_id, topic_id) — either may be None.
    """
    chat_id = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID")
    topic_id = os.environ.get("TELEGRAM_DEFAULT_TOPIC_ID")
    if topic_id is not None:
        topic_id = int(topic_id)

    if chat_id is None:
        try:
            state_path = Path.home() / ".openclaw" / "session-state.json"
            if state_path.exists():
                with open(state_path) as f:
                    state = json.load(f)
                inbound = state.get("inbound_meta", {})
                chat_id = inbound.get("chat_id")
                if chat_id and isinstance(chat_id, str) and chat_id.startswith("telegram:"):
                    chat_id = chat_id.replace("telegram:", "")
                if topic_id is None:
                    topic_id = inbound.get("topic_id")
        except Exception:
            pass

    return chat_id, topic_id


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------

IMAGE_EXTS   = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_EXTS   = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"}
AUDIO_EXTS   = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".wma"}
DOC_EXTS     = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
                ".txt", ".rtf", ".odt", ".csv"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}


def classify_file(path: str) -> str:
    """Return 'photo' | 'video' | 'audio' | 'document' based on file extension."""
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in ARCHIVE_EXTS:
        return "document"
    # Default: document (covers PDF, DOC, TXT, etc.)
    return "document"


# ---------------------------------------------------------------------------
# Caption from filename
# ---------------------------------------------------------------------------

def caption_from_filename(file_path: str) -> str:
    """Strip extension and return filename as caption, with underscores replaced."""
    name = Path(file_path).stem
    # Replace underscores and hyphens with spaces, clean up extra whitespace
    import re
    name = re.sub(r"[-_]+", " ", name).strip()
    return name


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------

class ProgressTracker:
    """Print a simple progress bar for large files during upload."""

    def __init__(self, total_size: int, logger: Optional[logging.Logger] = None):
        self.total_size = total_size
        self.bytes_sent = 0
        self.logger = logger
        self.start_time = time.time()
        self._last_pct = -1

    def update(self, bytes_count: int):
        self.bytes_sent += bytes_count
        if self.total_size <= 0:
            return
        pct = int(100 * self.bytes_sent / self.total_size)
        # Only print at 20% intervals to avoid spam
        if pct >= self._last_pct + 20:
            self._last_pct = pct
            elapsed = time.time() - self.start_time
            rate = self.bytes_sent / elapsed if elapsed > 0 else 0
            bar = "#" * (pct // 10) + " " * (10 - pct // 10)
            msg = f"\r  Upload: [{bar}] {pct}%  ({_size_str(self.bytes_sent)} / {_size_str(self.total_size)})  {_size_str(rate)}/s"
            if self.logger:
                self.logger.debug(msg.rstrip())
            else:
                sys.stderr.write(msg + "   \r")
                sys.stderr.flush()

    def close(self):
        if not self.logger:
            sys.stderr.write("\n")
            sys.stderr.flush()


def _size_str(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.1f}{unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f}TB"


# ---------------------------------------------------------------------------
# Core sending logic with full error handling
# ---------------------------------------------------------------------------

async def send_file(
    bot: Bot,
    chat_id: Union[str, int],
    file_path: Optional[str] = None,
    file_url: Optional[str] = None,
    file_id: Optional[str] = None,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    message_thread_id: Optional[int] = None,
    silent: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Send a file to Telegram with comprehensive error handling.

    Raises:
        FileNotFoundError   — local file does not exist or is unreadable
        ValueError          — invalid input (e.g. no file provided)
        InvalidToken        — bot token is malformed
        ChatNotFound        — target chat does not exist or bot not added
        Forbidden           — bot was blocked or lacks permission
        RetryAfter          — rate limit hit; contains retry_after seconds
        NetworkError        — connection/network failure
        TimedOut            — request timed out
        BadRequest          — invalid file or other bad request
    """
    # ---------- Validate input ----------
    if not file_path and not file_url and not file_id:
        raise ValueError("Must provide --file, --url, or --file-id")

    # ---------- Validate local file ----------
    if file_path:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not p.is_file():
            raise ValueError(f"Not a file: {file_path}")
        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"File not readable: {file_path}")

    # ---------- Classify file type ----------
    file_type = None
    if file_path:
        file_type = classify_file(file_path)

    # ---------- Build upload kwargs ----------
    # We open the file here and hold it in memory for the duration of the request.
    # For very large files (>50 MB) we could use chunked upload, but InputFile
    # already handles streaming internally.
    f_obj = None
    try:
        upload_kwargs = dict(
            chat_id=chat_id,
            caption=caption,
            parse_mode=parse_mode,
            disable_notification=silent,
            message_thread_id=message_thread_id,
        )

        if file_path:
            f_obj = open(file_path, "rb")
            file_size = os.path.getsize(file_path)

            if verbose and file_size > 5 * 1024 * 1024:
                tracker = ProgressTracker(file_size)
            else:
                tracker = None

            if file_type == "photo":
                method = bot.send_photo
                upload_kwargs["photo"] = f_obj
            elif file_type == "video":
                method = bot.send_video
                upload_kwargs["video"] = f_obj
            elif file_type == "audio":
                method = bot.send_audio
                upload_kwargs["audio"] = f_obj
            else:
                method = bot.send_document
                upload_kwargs["document"] = f_obj

            if verbose:
                logger.debug(f"Sending {file_type} to chat {chat_id} (size: {_size_str(file_size)})")

            # The library (python-telegram-bot) handles retries internally for
            # transient errors, but we wrap at the user level for better messages.
            result = await method(**upload_kwargs)
            if tracker:
                tracker.close()

        elif file_url:
            if verbose:
                logger.debug(f"Sending URL to chat {chat_id}: {file_url}")
            # URL sending uses send_document with document=url
            result = await bot.send_document(
                document=file_url,
                **upload_kwargs,
            )

        elif file_id:
            if verbose:
                logger.debug(f"Forwarding file_id to chat {chat_id}: {file_id}")
            result = await bot.send_document(
                document=file_id,
                **upload_kwargs,
            )

        return result.to_dict()

    finally:
        if f_obj:
            f_obj.close()


async def send_batch(
    bot: Bot,
    chat_id: Union[str, int],
    files: List[dict],
    silent: bool = False,
    verbose: bool = False,
) -> List[dict]:
    """Send multiple files sequentially with error handling per file."""
    results = []
    for idx, spec in enumerate(files, 1):
        path = spec.get("path") or spec.get("url") or spec.get("file_id")
        try:
            result = await send_file(
                bot=bot,
                chat_id=chat_id,
                file_path=spec.get("path"),
                file_url=spec.get("url"),
                file_id=spec.get("file_id"),
                caption=spec.get("caption"),
                parse_mode=spec.get("parse_mode"),
                silent=silent,
                verbose=verbose,
            )
            results.append(result)
            prefix = f"[{idx}/{len(files)}]"
            logger.info(f"{prefix} ✓ Sent: {path}")
        except Exception as e:
            prefix = f"[{idx}/{len(files)}]"
            logger.error(f"{prefix} ✗ Failed: {path} — {e}")
            results.append({"error": str(e)})
    return results


# ---------------------------------------------------------------------------
# Error classification for user-friendly messages
# ---------------------------------------------------------------------------

def classify_error(e: Exception) -> str:
    """Return a short human-readable error reason."""
    if isinstance(e, FileNotFoundError):
        return f"File not found: {e}"
    if isinstance(e, PermissionError):
        return f"Permission denied: {e}"
    if isinstance(e, InvalidToken):
        return (
            "Invalid bot token. "
            "Make sure your token is correct and has not been revoked. "
            "Get a new one from @BotFather."
        )
    if isinstance(e, ChatNotFound):
        return (
            "Chat not found. "
            "Make sure the bot has been added to the target chat "
            "and the chat_id is correct."
        )
    if isinstance(e, Forbidden):
        return (
            "Bot was blocked by the user or lacks permission to write to this chat. "
            "Ask the user to /start the bot first."
        )
    if isinstance(e, RetryAfter):
        return (
            f"Rate limit exceeded. "
            f"Telegram requires a short pause (RetryAfter={e.retry_after}s). "
            f"Wait and try again."
        )
    if isinstance(e, (NetworkError, TimedOut)):
        return (
            f"Network error: {e}. "
            f"Check your internet connection and try again."
        )
    if isinstance(e, BadRequest):
        return f"Bad request: {e}. The file may be corrupt or the request invalid."
    if isinstance(e, TelegramError):
        return f"Telegram API error: {e}"
    return str(e)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telegram_send_file.py",
        description="Send files to Telegram via Bot API. "
                   "Auto-detects chat_id/topic_id from OpenClaw session when available.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Simplest: auto-detect context from OpenClaw session
  python telegram_send_file.py --file document.pdf

  # Explicit chat + topic
  python telegram_send_file.py --chat-id 123456789 --topic-id 3 --file photo.png

  # Send with caption
  python telegram_send_file.py --file screenshot.png --caption "Bug report screenshot"

  # Use filename as caption
  python telegram_send_file.py --file bug_report.pdf --caption-from-filename

  # Send silently (no notification sound)
  python telegram_send_file.py --file doc.pdf --silent

  # Multiple files (batch mode)
  python telegram_send_file.py --files file1.pdf file2.jpg --caption "Batch delivery"

  # Send from URL
  python telegram_send_file.py --url "https://example.com/report.pdf"

  # Forward an existing file by its file_id
  python telegram_send_file.py --file-id "ABC123xyz"

  # Verbose debug output
  python telegram_send_file.py --file doc.pdf --verbose

Environment variables:
  TELEGRAM_BOT_TOKEN       Bot token (overrides config file)
  TELEGRAM_DEFAULT_CHAT_ID Default chat ID for all sends
  TELEGRAM_DEFAULT_TOPIC_ID Default topic/thread ID
""",
    )
    parser.add_argument("--chat-id", help="Telegram chat ID (auto-detected from session)")
    parser.add_argument("--file", dest="file_path", metavar="PATH",
                        help="Local file path to send")
    parser.add_argument("--url", metavar="URL",
                        help="URL to download and send")
    parser.add_argument("--file-id", dest="file_id", metavar="ID",
                        help="Telegram file_id to forward")
    parser.add_argument("--files", nargs="+", metavar="PATH",
                        help="Multiple local files (batch mode)")
    parser.add_argument("--caption", help="File/media caption (supports HTML/Markdown)")
    parser.add_argument("--caption-from-filename", action="store_true",
                        dest="caption_from_filename",
                        help="Use the filename (without extension) as the caption")
    parser.add_argument("--parse-mode", dest="parse_mode",
                        choices=["Markdown", "HTML", "MarkdownV2"],
                        help="Caption parse mode (default: none)")
    parser.add_argument("--token", help="Telegram bot token (or set TELEGRAM_BOT_TOKEN)")
    parser.add_argument("--topic-id", dest="topic_id", type=int,
                        help="Topic/thread ID for forum chats (auto-detected)")
    parser.add_argument("--thread-id", dest="topic_id", type=int,
                        help="Alias for --topic-id (same thing)")
    parser.add_argument("--silent", action="store_true",
                        help="Send silently (no notification sound for recipients)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable verbose debug output")
    return parser


def main():
    global logger

    parser = build_parser()
    args = parser.parse_args()

    # Silencing here means noop for everything that follows
    if args.silent:
        # Suppress stdout progress bars (but not stderr)
        pass

    logger = setup_logging(verbose=args.verbose)

    # Resolve --thread-id / --topic-id (they share the same dest)
    topic_id = args.topic_id

    # Auto-detect from session
    default_chat_id, default_topic_id = get_default_target()

    # Caption from filename
    caption = args.caption
    if args.caption_from_filename:
        source = args.file_path or (args.files[0] if args.files else None)
        if not source:
            logger.warning("--caption-from-filename used but no file given; ignoring")
        else:
            caption = caption or caption_from_filename(source)

    # Token
    try:
        token = args.token or get_token()
    except ValueError as e:
        logger.error(e)
        sys.exit(1)

    # Determine targets
    chat_id = args.chat_id or default_chat_id
    if chat_id is None:
        logger.error(
            "No chat_id provided. Use --chat-id or set TELEGRAM_DEFAULT_CHAT_ID"
        )
        sys.exit(1)
    topic_id = topic_id or default_topic_id

    bot = Bot(token=token)

    # -------------------------------------------------------------------------
    # Batch mode
    # -------------------------------------------------------------------------
    if args.files:
        files = [
            {
                "path": f,
                "caption": caption,
                "parse_mode": args.parse_mode,
            }
            for f in args.files
        ]
        try:
            results = asyncio.run(
                send_batch(bot, chat_id, files, silent=args.silent, verbose=args.verbose)
            )
            succeeded = sum(1 for r in results if "error" not in r)
            failed = len(results) - succeeded
            logger.info(f"Batch complete: {succeeded} sent, {failed} failed")
            if failed:
                sys.exit(1)
        except TelegramError as e:
            logger.error(f"Telegram error: {classify_error(e)}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error: {classify_error(e)}")
            sys.exit(1)
        return

    # -------------------------------------------------------------------------
    # Single-file mode
    # -------------------------------------------------------------------------
    try:
        result = asyncio.run(
            send_file(
                bot=bot,
                chat_id=chat_id,
                file_path=args.file_path,
                file_url=args.url,
                file_id=args.file_id,
                caption=caption,
                parse_mode=args.parse_mode,
                message_thread_id=topic_id,
                silent=args.silent,
                verbose=args.verbose,
            )
        )

        msg_id = result.get("message_id")
        logger.info(f"✓ File sent successfully (message_id={msg_id})")

        # Print the file_id so users can reuse it
        file_id_out = None
        if "document" in result:
            file_id_out = result["document"].get("file_id")
        elif "photo" in result:
            photos = result.get("photo")
            if photos:
                file_id_out = max(photos, key=lambda p: p.get("file_size", 0)).get("file_id")

        if file_id_out and args.verbose:
            logger.info(f"  file_id: {file_id_out}")

        # If running in OpenClaw, print the message link
        if str(chat_id).startswith("-100") and msg_id:
            logger.info(f"  Link: https://t.me/c/{str(chat_id).replace('-100', '')}/{msg_id}")

    except FileNotFoundError as e:
        logger.error(f"File not found: {args.file_path}")
        sys.exit(1)
    except PermissionError as e:
        logger.error(f"Permission denied: {e}")
        sys.exit(1)
    except (InvalidToken, ChatNotFound, Forbidden, RetryAfter,
            NetworkError, TimedOut, BadRequest, TelegramError) as e:
        logger.error(classify_error(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {classify_error(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
