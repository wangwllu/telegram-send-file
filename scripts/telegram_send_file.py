#!/usr/bin/env python3
"""
Telegram File Sender - Send files via Telegram Bot API

Supports:
- Local file sending
- URL file sending
- File ID forwarding
- Batch sending
- Documents, images, audio, video

Requires: python-telegram-bot>=20.0 (async API)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, List, Union

try:
    from telegram import Bot
    from telegram.error import TelegramError
except ImportError:
    print("Error: python-telegram-bot not installed. Run: pip install python-telegram-bot")
    sys.exit(1)


def get_token() -> str:
    """Get bot token from environment or config file."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    
    # Try to read from config file
    config_paths = [
        Path.home() / ".config" / "telegram-send-file" / "config",
        Path.home() / ".telegram_bot_token",
        Path.home() / "telegram_token",
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            token = config_path.read_text().strip()
            if token:
                return token
    
    raise ValueError(
        "Telegram bot token not found.\n"
        "To create one:\n"
        "1. Message @BotFather on Telegram\n"
        "2. Send /newbot\n"
        "3. Follow the prompts to name your bot\n"
        "4. Copy the token BotFather shows you\n"
        "5. Save it to ~/.telegram_bot_token\n"
        '   Example: echo "YOUR_TOKEN" > ~/.telegram_bot_token\n'
        "You can also set TELEGRAM_BOT_TOKEN in your environment."
    )


async def send_file(
    bot: Bot,
    chat_id: Union[str, int],
    file_path: Optional[str] = None,
    file_url: Optional[str] = None,
    file_id: Optional[str] = None,
    caption: Optional[str] = None,
    parse_mode: Optional[str] = None,
) -> dict:
    """
    Send a file to Telegram (async).
    
    Args:
        bot: Telegram Bot instance
        chat_id: Target chat ID
        file_path: Local file path
        file_url: URL to download and send
        file_id: Telegram file_id to forward
        caption: Optional caption
        parse_mode: Parse mode (Markdown, HTML)
    
    Returns:
        dict with message info
    """
    if file_path:
        # Send local file
        with open(file_path, "rb") as f:
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                return (await bot.send_photo(
                    chat_id=chat_id,
                    photo=f,
                    caption=caption,
                    parse_mode=parse_mode,
                )).to_dict()
            elif file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                return (await bot.send_video(
                    chat_id=chat_id,
                    video=f,
                    caption=caption,
                    parse_mode=parse_mode,
                )).to_dict()
            elif file_path.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac')):
                return (await bot.send_audio(
                    chat_id=chat_id,
                    audio=f,
                    caption=caption,
                    parse_mode=parse_mode,
                )).to_dict()
            elif file_path.lower().endswith(('.zip', '.rar', '.7z', '.tar', '.gz')):
                return (await bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    caption=caption,
                    parse_mode=parse_mode,
                )).to_dict()
            else:
                # Default to document (PDF, DOC, TXT, etc.)
                return (await bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    caption=caption,
                    parse_mode=parse_mode,
                )).to_dict()
    
    elif file_url:
        # Send file from URL
        return (await bot.send_document(
            chat_id=chat_id,
            document=file_url,
            caption=caption,
            parse_mode=parse_mode,
        )).to_dict()
    
    elif file_id:
        # Forward existing file
        return (await bot.send_document(
            chat_id=chat_id,
            document=file_id,
            caption=caption,
            parse_mode=parse_mode,
        )).to_dict()
    
    else:
        raise ValueError("Must provide file_path, file_url, or file_id")


async def send_batch(
    bot: Bot,
    chat_id: Union[str, int],
    files: List[dict],
) -> List[dict]:
    """
    Send multiple files in a batch (async).
    
    Args:
        bot: Telegram Bot instance
        chat_id: Target chat ID
        files: List of file dicts with keys: path, url, file_id, caption, parse_mode
    
    Returns:
        List of message dicts
    """
    results = []
    for file_spec in files:
        try:
            result = await send_file(
                bot=bot,
                chat_id=chat_id,
                file_path=file_spec.get("path"),
                file_url=file_spec.get("url"),
                file_id=file_spec.get("file_id"),
                caption=file_spec.get("caption"),
                parse_mode=file_spec.get("parse_mode"),
            )
            results.append(result)
            print(f"✓ Sent: {file_spec.get('path', file_spec.get('url', file_spec.get('file_id')))}")
        except TelegramError as e:
            print(f"✗ Failed: {e}")
            results.append({"error": str(e)})
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Send files via Telegram Bot API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send a local PDF
  python telegram_send_file.py --chat-id 123456789 --file document.pdf

  # Send file with caption
  python telegram_send_file.py --chat-id 123456789 --file photo.jpg --caption "My photo"

  # Send file from URL
  python telegram_send_file.py --chat-id 123456789 --url "https://example.com/file.pdf"

  # Forward a file by ID
  python telegram_send_file.py --chat-id 123456789 --file-id "ABC123"

  # Send multiple files
  python telegram_send_file.py --chat-id 123456789 --files file1.pdf file2.jpg

  # Use custom token
  python telegram_send_file.py --chat-id 123456789 --file document.pdf --token "YOUR_TOKEN"
"""
    )
    
    parser.add_argument("--chat-id", required=True, help="Telegram chat ID")
    parser.add_argument("--file", dest="file_path", help="Local file path")
    parser.add_argument("--url", help="URL to send")
    parser.add_argument("--file-id", dest="file_id", help="Telegram file ID to forward")
    parser.add_argument("--files", nargs="+", help="Multiple local files (batch mode)")
    parser.add_argument("--caption", help="File caption")
    parser.add_argument("--parse-mode", dest="parse_mode", choices=["Markdown", "HTML"], help="Caption parse mode")
    parser.add_argument("--token", help="Telegram bot token (or set TELEGRAM_BOT_TOKEN)")
    
    args = parser.parse_args()
    
    # Get token
    token = args.token or get_token()
    bot = Bot(token=token)
    
    # Determine chat_id
    chat_id = args.chat_id
    
    # Batch mode
    if args.files:
        files = []
        for f in args.files:
            files.append({
                "path": f,
                "caption": args.caption,
                "parse_mode": args.parse_mode,
            })
        results = asyncio.run(send_batch(bot, chat_id, files))
        print(f"\nSent {len(results)} files")
        return
    
    # Single file mode
    try:
        result = asyncio.run(send_file(
            bot=bot,
            chat_id=chat_id,
            file_path=args.file_path,
            file_url=args.url,
            file_id=args.file_id,
            caption=args.caption,
            parse_mode=args.parse_mode,
        ))
        print(f"✓ File sent successfully")
        print(f"  Message ID: {result.get('message_id')}")
        
        # Try to get file_id for future use
        if 'document' in result:
            print(f"  File ID: {result.get('document', {}).get('file_id', 'N/A')}")
        elif 'photo' in result:
            # For photos, get the largest file_id
            photos = result.get('photo', [])
            if photos:
                print(f"  File ID: {photos[-1].get('file_id', 'N/A')}")
        
    except TelegramError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
