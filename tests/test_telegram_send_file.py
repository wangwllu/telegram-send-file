"""
Unit tests for telegram_send_file.py

Coverage:
- classify_local_file: extension → media type mapping including .svg fix
- caption_from_filename: normal, hidden, dash/underscore-only, empty fallback
- build_parser: argument parsing
- mutual exclusivity validation in main()
- --caption-from-filename + --url / --file-id warning in main()
"""

import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import telegram_send_file as tsf


# ---------------------------------------------------------------------------
# classify_local_file
# ---------------------------------------------------------------------------

class TestClassifyLocalFile:
    def test_png_is_photo(self, tmp_path):
        f = tmp_path / "image.png"
        assert tsf.classify_local_file(str(f)) == "photo"

    def test_jpg_is_photo(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "photo.jpg")) == "photo"

    def test_jpeg_is_photo(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "photo.jpeg")) == "photo"

    def test_gif_is_photo(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "anim.gif")) == "photo"

    def test_webp_is_photo(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "img.webp")) == "photo"

    def test_bmp_is_photo(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "img.bmp")) == "photo"

    # --- SVG fix: was classified as photo, must now be document ---
    def test_svg_is_document_not_photo(self, tmp_path):
        result = tsf.classify_local_file(str(tmp_path / "diagram.svg"))
        assert result == "document", (
            ".svg must be sent as a document; Telegram cannot render SVG as a photo"
        )

    def test_svg_uppercase_is_document(self, tmp_path):
        # classify_local_file lowercases the extension
        result = tsf.classify_local_file(str(tmp_path / "ICON.SVG"))
        assert result == "document"

    def test_mp4_is_video(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "clip.mp4")) == "video"

    def test_avi_is_video(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "clip.avi")) == "video"

    def test_mp3_is_audio(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "track.mp3")) == "audio"

    def test_ogg_is_audio(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "sound.ogg")) == "audio"

    def test_pdf_is_document(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "report.pdf")) == "document"

    def test_zip_is_document(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "archive.zip")) == "document"

    def test_unknown_extension_is_document(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "data.xyz")) == "document"

    def test_no_extension_is_document(self, tmp_path):
        assert tsf.classify_local_file(str(tmp_path / "Makefile")) == "document"


# ---------------------------------------------------------------------------
# caption_from_filename
# ---------------------------------------------------------------------------

class TestCaptionFromFilename:
    def test_normal_filename(self):
        assert tsf.caption_from_filename("my-report.pdf") == "my report"

    def test_underscores_replaced(self):
        assert tsf.caption_from_filename("hello_world.txt") == "hello world"

    def test_mixed_dashes_underscores(self):
        assert tsf.caption_from_filename("foo-bar_baz.pdf") == "foo bar baz"

    def test_trailing_spaces_stripped(self):
        result = tsf.caption_from_filename("-leading.txt")
        assert result == result.strip()
        assert result != ""

    # --- Hidden file fix: leading dots stripped ---
    def test_hidden_file_strips_leading_dot(self):
        result = tsf.caption_from_filename(".hidden.txt")
        assert not result.startswith("."), f"Caption should not start with a dot, got: {result!r}"
        assert result.strip() == result
        # stem is ".hidden" → strip dot → "hidden"
        assert result == "hidden"

    def test_hidden_file_with_dashes(self):
        result = tsf.caption_from_filename("._my_data.json")
        assert not result.startswith("."), f"Got: {result!r}"
        assert result.strip() != ""

    def test_dotfile_no_extension(self):
        result = tsf.caption_from_filename(".gitignore")
        # Path(".gitignore").stem == ".gitignore" (no extension)
        assert not result.startswith("."), f"Got: {result!r}"
        assert result != ""

    # --- Empty caption fallback ---
    def test_dash_only_stem_falls_back_to_filename(self):
        # stem is "-", after re.sub = " ", after strip = "" → fallback to full name
        result = tsf.caption_from_filename("-.txt")
        assert result != "", "Caption must never be empty"
        assert result == "-.txt"

    def test_underscore_only_stem_falls_back_to_filename(self):
        result = tsf.caption_from_filename("_.txt")
        assert result != ""
        assert result == "_.txt"

    def test_dash_underscore_combo_falls_back_to_filename(self):
        result = tsf.caption_from_filename("-_.txt")
        assert result != ""
        assert result == "-_.txt"

    def test_multiple_dashes_falls_back(self):
        result = tsf.caption_from_filename("---file.txt")
        # stem "---file" → sub → " file" → strip → "file"
        assert result == "file"

    def test_path_with_directory(self):
        result = tsf.caption_from_filename("/tmp/my-report.pdf")
        assert result == "my report"

    def test_no_extension_normal(self):
        result = tsf.caption_from_filename("README")
        assert result == "README"


# ---------------------------------------------------------------------------
# build_parser
# ---------------------------------------------------------------------------

class TestBuildParser:
    def setup_method(self):
        self.parser = tsf.build_parser()

    def test_file_sets_file_path(self):
        args = self.parser.parse_args(["--file", "doc.pdf", "--chat-id", "123"])
        assert args.file_path == "doc.pdf"

    def test_url_is_parsed(self):
        args = self.parser.parse_args(["--url", "https://example.com/f.pdf"])
        assert args.url == "https://example.com/f.pdf"

    def test_files_nargs(self):
        args = self.parser.parse_args(["--files", "a.pdf", "b.png"])
        assert args.files == ["a.pdf", "b.png"]

    def test_file_id(self):
        args = self.parser.parse_args(["--file-id", "AQAD123"])
        assert args.file_id == "AQAD123"

    def test_topic_id_alias_thread_id(self):
        args = self.parser.parse_args(["--file", "x.pdf", "--thread-id", "5"])
        assert args.topic_id == 5

    def test_silent_flag(self):
        args = self.parser.parse_args(["--file", "x.pdf", "--silent"])
        assert args.silent is True

    def test_verbose_flag(self):
        args = self.parser.parse_args(["--file", "x.pdf", "--verbose"])
        assert args.verbose is True

    def test_caption_from_filename_flag(self):
        args = self.parser.parse_args(["--file", "x.pdf", "--caption-from-filename"])
        assert args.caption_from_filename is True

    def test_parse_mode_choices(self):
        for mode in ("Markdown", "HTML", "MarkdownV2"):
            args = self.parser.parse_args(["--file", "x.pdf", "--parse-mode", mode])
            assert args.parse_mode == mode

    def test_invalid_parse_mode_raises(self):
        with pytest.raises(SystemExit):
            self.parser.parse_args(["--file", "x.pdf", "--parse-mode", "text"])


# ---------------------------------------------------------------------------
# main(): mutual exclusivity validation
# ---------------------------------------------------------------------------

def _run_main_with_args(argv, mock_token="fake-token", mock_chat="123"):
    """
    Run main() with given argv, mocking token/chat resolution and Bot.
    Returns (exit_code_or_none, stderr_records).
    """
    log_records = []

    class CapturingHandler(logging.Handler):
        def emit(self, record):
            log_records.append(record)

    with (
        patch("sys.argv", ["prog"] + argv),
        patch.object(tsf, "get_token", return_value=mock_token),
        patch.object(tsf, "get_default_target", return_value=(mock_chat, None)),
        patch("telegram_send_file.Bot") as MockBot,
    ):
        # Wire up a mock bot that returns a minimal message dict
        mock_bot_instance = MagicMock()
        mock_msg = MagicMock()
        mock_msg.to_dict.return_value = {"message_id": 42}
        mock_bot_instance.send_document = AsyncMock(return_value=mock_msg)
        mock_bot_instance.send_photo = AsyncMock(return_value=mock_msg)
        mock_bot_instance.send_video = AsyncMock(return_value=mock_msg)
        mock_bot_instance.send_audio = AsyncMock(return_value=mock_msg)
        MockBot.return_value = mock_bot_instance

        # Attach capturing handler to catch log output
        log = tsf.setup_logging(verbose=False)
        handler = CapturingHandler()
        log.addHandler(handler)
        try:
            exit_code = None
            try:
                tsf.main()
            except SystemExit as e:
                exit_code = e.code
            return exit_code, log_records
        finally:
            log.removeHandler(handler)


class TestMutualExclusivity:
    def test_no_source_exits_1(self):
        exit_code, records = _run_main_with_args(["--chat-id", "123"])
        assert exit_code == 1
        errors = [r for r in records if r.levelno == logging.ERROR]
        assert any("No source" in r.getMessage() for r in errors)

    def test_file_and_url_exits_1(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("x")
        exit_code, records = _run_main_with_args(["--file", str(f), "--url", "https://x.com/f.pdf"])
        assert exit_code == 1
        errors = [r for r in records if r.levelno == logging.ERROR]
        assert any("mutually exclusive" in r.getMessage() for r in errors)

    def test_files_and_url_exits_1(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("x")
        exit_code, records = _run_main_with_args(["--files", str(f), "--url", "https://x.com/f.pdf"])
        assert exit_code == 1
        errors = [r for r in records if r.levelno == logging.ERROR]
        assert any("mutually exclusive" in r.getMessage() for r in errors)

    def test_file_and_file_id_exits_1(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("x")
        exit_code, records = _run_main_with_args(["--file", str(f), "--file-id", "AQAD"])
        assert exit_code == 1
        errors = [r for r in records if r.levelno == logging.ERROR]
        assert any("mutually exclusive" in r.getMessage() for r in errors)

    def test_file_and_files_exits_1(self, tmp_path):
        f1 = tmp_path / "a.pdf"
        f2 = tmp_path / "b.pdf"
        f1.write_text("x")
        f2.write_text("y")
        exit_code, records = _run_main_with_args(["--file", str(f1), "--files", str(f2)])
        assert exit_code == 1
        errors = [r for r in records if r.levelno == logging.ERROR]
        assert any("mutually exclusive" in r.getMessage() for r in errors)

    def test_error_message_names_conflicting_flags(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("x")
        _, records = _run_main_with_args(["--file", str(f), "--url", "https://x.com/f.pdf"])
        errors = [r for r in records if r.levelno == logging.ERROR]
        msg = " ".join(r.getMessage() for r in errors)
        assert "--file" in msg
        assert "--url" in msg


# ---------------------------------------------------------------------------
# main(): --caption-from-filename warnings
# ---------------------------------------------------------------------------

class TestCaptionFromFilenameWarnings:
    def test_url_with_caption_from_filename_warns(self):
        exit_code, records = _run_main_with_args(
            ["--url", "https://example.com/report.pdf", "--caption-from-filename"]
        )
        # Should not exit with error (URL is a valid source)
        assert exit_code in (None, 0)
        warnings = [r for r in records if r.levelno == logging.WARNING]
        assert any("--caption-from-filename" in r.getMessage() and "--url" in r.getMessage()
                   for r in warnings), (
            "Expected a warning that --caption-from-filename has no effect with --url"
        )

    def test_file_id_with_caption_from_filename_warns(self):
        exit_code, records = _run_main_with_args(
            ["--file-id", "AQAD123", "--caption-from-filename"]
        )
        assert exit_code in (None, 0)
        warnings = [r for r in records if r.levelno == logging.WARNING]
        assert any("--caption-from-filename" in r.getMessage() and "--file-id" in r.getMessage()
                   for r in warnings), (
            "Expected a warning that --caption-from-filename has no effect with --file-id"
        )

    def test_file_with_caption_from_filename_no_warning(self, tmp_path):
        f = tmp_path / "my-report.pdf"
        f.write_bytes(b"%PDF-")
        exit_code, records = _run_main_with_args(
            ["--file", str(f), "--caption-from-filename"]
        )
        warnings = [r for r in records if r.levelno == logging.WARNING]
        # No warning expected: local file + caption-from-filename is valid
        assert not any(
            "--caption-from-filename" in r.getMessage() for r in warnings
        ), "No warning expected when --caption-from-filename is used with a local file"


# ---------------------------------------------------------------------------
# send_single: unit tests for SVG routing
# ---------------------------------------------------------------------------

class TestSendSingleSvgRouting:
    """Ensure SVG files are sent via send_document, not send_photo."""

    @pytest.mark.anyio
    async def test_svg_sent_as_document(self, tmp_path):
        svg_file = tmp_path / "icon.svg"
        svg_file.write_text("<svg/>")

        mock_bot = MagicMock()
        mock_msg = MagicMock()
        mock_msg.to_dict.return_value = {"message_id": 1}
        mock_bot.send_document = AsyncMock(return_value=mock_msg)
        mock_bot.send_photo = AsyncMock(return_value=mock_msg)

        # Must not raise; send_document must be called, send_photo must not
        with patch.object(tsf, "logger", tsf.setup_logging()):
            await tsf.send_single(
                bot=mock_bot,
                chat_id="123",
                file_path=str(svg_file),
            )

        mock_bot.send_document.assert_called_once()
        mock_bot.send_photo.assert_not_called()

    @pytest.mark.anyio
    async def test_png_sent_as_photo(self, tmp_path):
        png_file = tmp_path / "image.png"
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_bot = MagicMock()
        mock_msg = MagicMock()
        mock_msg.to_dict.return_value = {"message_id": 2}
        mock_bot.send_photo = AsyncMock(return_value=mock_msg)
        mock_bot.send_document = AsyncMock(return_value=mock_msg)

        with patch.object(tsf, "logger", tsf.setup_logging()):
            await tsf.send_single(
                bot=mock_bot,
                chat_id="123",
                file_path=str(png_file),
            )

        mock_bot.send_photo.assert_called_once()
        mock_bot.send_document.assert_not_called()
