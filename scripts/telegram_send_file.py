#!/usr/bin/env python3
"""
Send files to Telegram via Bot API.

Scope:
- Send local files, URLs, or file_ids
- Reuse current OpenClaw Telegram session context when available
- Support batch sending while preserving topic/thread context
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

try:
    from telegram import Bot
    from telegram.error import (
        TelegramError,
        BadRequest,
        NetworkError,
        RetryAfter,
        Forbidden,
        InvalidToken,
        TimedOut,
    )
    # ChatNotFound was removed in newer versions; handle gracefully
    try:
        from telegram.error import ChatNotFound
    except ImportError:
        ChatNotFound = BadRequest  # Fallback for compatibility
except ImportError:
    print("Error: python-telegram-bot not installed. Run: pip install python-telegram-bot>=20.0")
    sys.exit(1)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
# .svg is intentionally excluded: Telegram cannot render SVG as a photo preview;
# it must be sent as a document so the file is delivered intact.
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".wma"}

# Telegram Bot API limits (in bytes)
TELEGRAM_MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
TELEGRAM_MAX_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB

logger: Optional[logging.Logger] = None


def setup_logging(verbose: bool = False) -> logging.Logger:
    log = logging.getLogger("telegram_send_file")
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    if log.handlers:
        return log
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = "[%(levelname)s] %(message)s" if not verbose else "[%(levelname)s] %(funcName)s: %(message)s"
    handler.setFormatter(logging.Formatter(fmt))
    log.addHandler(handler)
    return log


def get_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token

    config_paths = [
        Path.home() / ".config" / "telegram-send-file" / "config",
        Path.home() / ".telegram_bot_token",
        Path.home() / ".telegram_token",
        Path.home() / ".openclaw" / "openclaw.json",
    ]
    for config_path in config_paths:
        if not config_path.exists():
            continue
        try:
            if config_path.name == "openclaw.json":
                data = json.loads(config_path.read_text())
                token = data.get("channels", {}).get("telegram", {}).get("botToken")
            else:
                token = config_path.read_text().strip()
            if token:
                return token
        except Exception:
            continue

    raise ValueError(
        "Telegram bot token not found. Set TELEGRAM_BOT_TOKEN, save ~/.telegram_token or ~/.telegram_bot_token, "
        "or configure ~/.openclaw/openclaw.json with channels.telegram.botToken."
    )


def get_default_target() -> tuple[Optional[str], Optional[int]]:
    chat_id = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID")
    topic_id = os.environ.get("TELEGRAM_DEFAULT_TOPIC_ID")
    if topic_id is not None:
        topic_id = int(topic_id)

    if chat_id is None:
        try:
            state_path = Path.home() / ".openclaw" / "session-state.json"
            if state_path.exists():
                state = json.loads(state_path.read_text())
                inbound = state.get("inbound_meta", {})
                chat_id = inbound.get("chat_id")
                if isinstance(chat_id, str) and chat_id.startswith("telegram:"):
                    chat_id = chat_id.replace("telegram:", "", 1)
                if topic_id is None:
                    inbound_topic = inbound.get("topic_id")
                    topic_id = int(inbound_topic) if inbound_topic is not None else None
        except Exception:
            pass

    return chat_id, topic_id


def classify_local_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in IMAGE_EXTS:
        return "photo"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return "document"


def caption_from_filename(file_path: str) -> str:
    p = Path(file_path)
    stem = p.stem
    # Hidden files (e.g. ".hidden", "._data") start with a dot; strip it so the
    # caption doesn't begin with punctuation.
    stem = stem.lstrip(".")
    caption = re.sub(r"[-_]+", " ", stem).strip()
    # If the result is empty (e.g. the filename was "-_.txt" or just "-.txt"),
    # fall back to the full filename so the caption is never silently blank.
    if not caption:
        caption = p.name
    return caption


def classify_error(e: Exception) -> str:
    if isinstance(e, FileNotFoundError):
        return str(e)
    if isinstance(e, PermissionError):
        return f"Permission denied: {e}"
    if isinstance(e, InvalidToken):
        return "Invalid bot token. Check TELEGRAM_BOT_TOKEN or BotFather credentials."
    if isinstance(e, ChatNotFound):
        return "Chat not found. Verify chat_id and ensure the bot is in the chat."
    if isinstance(e, Forbidden):
        return "Bot lacks permission to write to this chat or was blocked."
    if isinstance(e, RetryAfter):
        return f"Rate limited by Telegram. Retry after {e.retry_after}s."
    if isinstance(e, (NetworkError, TimedOut)):
        return f"Network error: {e}"
    if isinstance(e, BadRequest):
        return f"Bad request: {e}"
    if isinstance(e, TelegramError):
        return f"Telegram API error: {e}"
    return str(e)


async def send_single(
    bot: Bot,
    chat_id: str | int,
    file_path: Optional[str] = None,
    file_url: Optional[str] = None,
    file_id: Optional[str] = None,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
    message_thread_id: Optional[int] = None,
    silent: bool = False,
    verbose: bool = False,
) -> dict:
    if not any([file_path, file_url, file_id]):
        raise ValueError("Must provide --file, --url, or --file-id")

    upload_kwargs = {
        "chat_id": chat_id,
        "caption": caption,
        "parse_mode": parse_mode,
        "disable_notification": silent,
        "message_thread_id": message_thread_id,
    }
    upload_kwargs = {k: v for k, v in upload_kwargs.items() if v is not None}

    if file_path:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not p.is_file():
            raise ValueError(f"Not a file: {file_path}")
        if not os.access(file_path, os.R_OK):
            raise PermissionError(file_path)

        file_size = p.stat().st_size
        file_type = classify_local_file(file_path)
        size_limit = TELEGRAM_MAX_PHOTO_SIZE if file_type == "photo" else TELEGRAM_MAX_FILE_SIZE
        if file_size > size_limit:
            limit_mb = size_limit // (1024 * 1024)
            raise ValueError(
                f"File size ({file_size / (1024*1024):.1f} MB) exceeds Telegram's "
                f"{limit_mb} MB limit for {file_type}."
            )

        if verbose:
            logger.debug(f"Sending local {file_type}: {file_path} -> chat {chat_id}, topic {message_thread_id}")

        with open(file_path, "rb") as fh:
            if file_type == "photo":
                result = await bot.send_photo(photo=fh, **upload_kwargs)
            elif file_type == "video":
                result = await bot.send_video(video=fh, **upload_kwargs)
            elif file_type == "audio":
                result = await bot.send_audio(audio=fh, **upload_kwargs)
            else:
                result = await bot.send_document(document=fh, **upload_kwargs)
        return result.to_dict()

    if file_url:
        if verbose:
            logger.debug(f"Sending URL as document: {file_url}")
        result = await bot.send_document(document=file_url, **upload_kwargs)
        return result.to_dict()

    if verbose:
        logger.debug(f"Sending file_id as document: {file_id}")
    result = await bot.send_document(document=file_id, **upload_kwargs)
    return result.to_dict()


async def send_batch(
    bot: Bot,
    chat_id: str | int,
    files: list[dict],
    message_thread_id: Optional[int] = None,
    silent: bool = False,
    verbose: bool = False,
) -> list[dict]:
    results = []
    for idx, spec in enumerate(files, 1):
        label = spec.get("path") or spec.get("url") or spec.get("file_id") or f"item-{idx}"
        try:
            result = await send_single(
                bot=bot,
                chat_id=chat_id,
                file_path=spec.get("path"),
                file_url=spec.get("url"),
                file_id=spec.get("file_id"),
                caption=spec.get("caption"),
                parse_mode=spec.get("parse_mode"),
                message_thread_id=message_thread_id,
                silent=silent,
                verbose=verbose,
            )
            logger.info(f"[{idx}/{len(files)}] ✓ Sent: {label}")
            results.append(result)
        except Exception as e:
            logger.error(f"[{idx}/{len(files)}] ✗ Failed: {label} — {classify_error(e)}")
            results.append({"error": classify_error(e), "label": label})
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="telegram_send_file.py",
        description="Send files to Telegram via Bot API with optional OpenClaw context auto-detection.",
    )
    parser.add_argument("--chat-id", help="Telegram chat ID")
    parser.add_argument("--topic-id", dest="topic_id", type=int, help="Forum topic / thread ID")
    parser.add_argument("--thread-id", dest="topic_id", type=int, help="Alias for --topic-id")
    parser.add_argument("--file", dest="file_path", metavar="PATH", help="Local file path to send")
    parser.add_argument("--files", nargs="+", metavar="PATH", help="Multiple local files to send sequentially")
    parser.add_argument("--url", metavar="URL", help="URL to send as a Telegram document")
    parser.add_argument("--file-id", dest="file_id", metavar="ID", help="Telegram file_id to resend")
    parser.add_argument("--caption", help="Caption text")
    parser.add_argument("--caption-from-filename", action="store_true", dest="caption_from_filename")
    parser.add_argument("--parse-mode", choices=["Markdown", "HTML", "MarkdownV2"])
    parser.add_argument("--token", help="Override bot token")
    parser.add_argument("--silent", action="store_true", help="Send without notification sound")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    return parser


def main():
    global logger
    parser = build_parser()
    args = parser.parse_args()
    logger = setup_logging(verbose=args.verbose)

    caption = args.caption

    # Validate mutual exclusivity of source options before anything else so
    # early-exit errors are consistent regardless of flag order.
    sources = {
        "--file": args.file_path,
        "--files": args.files,
        "--url": args.url,
        "--file-id": args.file_id,
    }
    active_sources = [name for name, val in sources.items() if val]
    if len(active_sources) == 0:
        logger.error("No source provided. Use --file, --files, --url, or --file-id.")
        sys.exit(1)
    if len(active_sources) > 1:
        logger.error(
            f"Conflicting sources: {' and '.join(active_sources)} are mutually exclusive. "
            "Provide only one source type."
        )
        sys.exit(1)

    if args.caption_from_filename:
        if args.url:
            logger.warning(
                "--caption-from-filename has no effect with --url (no local filename available); "
                "use --caption to set an explicit caption."
            )
        elif args.file_id:
            logger.warning(
                "--caption-from-filename has no effect with --file-id; "
                "use --caption to set an explicit caption."
            )
        elif args.file_path:
            caption = caption or caption_from_filename(args.file_path)

    try:
        token = args.token or get_token()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    default_chat_id, default_topic_id = get_default_target()
    chat_id = args.chat_id or default_chat_id
    topic_id = args.topic_id if args.topic_id is not None else default_topic_id
    if chat_id is None:
        logger.error("No chat_id available. Use --chat-id or set TELEGRAM_DEFAULT_CHAT_ID.")
        sys.exit(1)

    bot = Bot(token=token)

    try:
        if args.files:
            # Batch mode: build payload with per-file caption logic
            if args.caption:
                # Explicit caption applies to all files
                payload = [{"path": p, "caption": args.caption, "parse_mode": args.parse_mode} for p in args.files]
            elif args.caption_from_filename:
                # Each file gets its own caption from its filename
                payload = [
                    {"path": p, "caption": caption_from_filename(p), "parse_mode": args.parse_mode}
                    for p in args.files
                ]
            else:
                payload = [{"path": p, "caption": None, "parse_mode": args.parse_mode} for p in args.files]
            results = asyncio.run(
                send_batch(
                    bot=bot,
                    chat_id=chat_id,
                    files=payload,
                    message_thread_id=topic_id,
                    silent=args.silent,
                    verbose=args.verbose,
                )
            )
            failed = [r for r in results if "error" in r]
            logger.info(f"Batch complete: {len(results) - len(failed)} sent, {len(failed)} failed")
            if failed:
                sys.exit(1)
            return

        result = asyncio.run(
            send_single(
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
        if args.verbose and str(chat_id).startswith("-100") and msg_id:
            logger.info(f"Link: https://t.me/c/{str(chat_id).replace('-100', '')}/{msg_id}")
    except Exception as e:
        logger.error(classify_error(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
