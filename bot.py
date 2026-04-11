import argparse
import asyncio
import logging
import os
from time import time
from typing import Any, Dict, Optional, Tuple

import ffmpeg
import validators
from dotenv import load_dotenv
from telegram import Update
from telegram.error import BadRequest, NetworkError, RetryAfter, TimedOut
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from yt_dlp import YoutubeDL

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./videos")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:7575/bot")
READ_TIMEOUT = int(os.getenv("READ_TIMEOUT", "60"))
WRITE_TIMEOUT = int(os.getenv("WRITE_TIMEOUT", "120"))
POOL_TIMEOUT = int(os.getenv("POOL_TIMEOUT", "60"))
CONNECT_TIMEOUT = int(os.getenv("CONNECT_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
PROGRESS_UPDATE_INTERVAL = int(os.getenv("PROGRESS_UPDATE_INTERVAL", "3"))
PROGRESS_MIN_PERCENTAGE_CHANGE = int(os.getenv("PROGRESS_MIN_PERCENTAGE_CHANGE", "5"))
VIDEO_FORMAT = os.getenv("VIDEO_FORMAT", "bestvideo+bestaudio/best")
MERGE_FORMAT = os.getenv("MERGE_FORMAT", "mp4")
THUMBNAIL_TIMESTAMP = int(os.getenv("THUMBNAIL_TIMESTAMP", "1"))

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# --- Helpers ---
def get_video_metadata(
    filename: str,
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Extracts width, height, and duration from a video file."""
    try:
        probe = ffmpeg.probe(filename)
        video_stream = next(
            (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
            None,
        )
        if video_stream:
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            duration = int(float(probe.get("format", {}).get("duration", 0)))
            return width, height, duration
    except Exception as e:
        logger.error(f"Error probing video {filename}: {e}")
    return None, None, None


def create_progress_bar(percentage: float, width: int = 20) -> str:
    """Creates a visual progress bar string."""
    filled = int(width * percentage / 100)
    return "█" * filled + "▒" * (width - filled)


def generate_thumbnail(video_path: str, width: Optional[int]) -> Optional[str]:
    """Generates a thumbnail image from the video."""
    thumbnail_file = os.path.join(DOWNLOAD_DIR, f"thumb_{int(time())}.jpg")
    try:
        scale_width = width if width else 320
        (
            ffmpeg.input(video_path, ss=THUMBNAIL_TIMESTAMP)
            .filter("scale", scale_width, -1)
            .output(thumbnail_file, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return thumbnail_file
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        return None


class ProgressNotifier:
    """Handles download progress tracking and updating the Telegram message."""

    def __init__(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        message_id: int,
        url: str,
    ):
        self.context = context
        self.chat_id = chat_id
        self.message_id = message_id
        self.url = url
        self.last_update = 0.0
        self.last_percentage = 0
        self.loop = asyncio.get_running_loop()

    def __call__(self, d: Dict[str, Any]) -> None:
        if d["status"] == "downloading" and d.get("total_bytes"):
            self._handle_downloading(d)
        elif d["status"] == "finished":
            self._handle_finished()

    def _handle_downloading(self, d: Dict[str, Any]) -> None:
        current_time = time()
        total = d.get("total_bytes") or 0
        downloaded = d.get("downloaded_bytes") or 0
        percentage = round(downloaded * 100 / total) if total else 0

        time_passed = current_time - self.last_update >= PROGRESS_UPDATE_INTERVAL
        progress_changed = (
            abs(percentage - self.last_percentage) >= PROGRESS_MIN_PERCENTAGE_CHANGE
        )

        if time_passed and progress_changed:
            self.last_update = current_time
            self.last_percentage = percentage

            elapsed = round(d.get("elapsed", 0) or 0)
            eta = round(d.get("eta", 0) or 0)
            speed_raw = d.get("speed")
            speed = round(speed_raw / 1024) if speed_raw else 0

            progress_bar = create_progress_bar(percentage)
            file_size_mb = round(total / (1024 * 1024), 2) if total else 0

            text = (
                f"📥 Downloading: {self.url}\n"
                f"📦 Size: {file_size_mb} MB\n"
                f"⏳ Progress: {progress_bar} {percentage}%\n"
                f"🚀 Speed: {speed} KB/s\n"
                f"⌛ Elapsed: {elapsed}s\n"
                f"🎯 ETA: {eta}s"
            )
            self._schedule_update(text)

    def _handle_finished(self) -> None:
        self._schedule_update("🔄 Processing video...")

    def _schedule_update(self, text: str) -> None:
        async def update_msg():
            try:
                await self.context.bot.edit_message_text(
                    text=text,
                    chat_id=self.chat_id,
                    message_id=self.message_id,
                    disable_web_page_preview=True,
                )
            except BadRequest as e:
                if "Message is not modified" not in str(e):
                    logger.warning(f"Failed to update progress message: {e}")
            except Exception as e:
                logger.warning(f"Failed to update progress message: {e}")

        asyncio.run_coroutine_threadsafe(update_msg(), self.loop)


# --- Core Logic ---
async def send_video_with_retry(
    update: Update,
    video_path: str,
    video_width: Optional[int],
    video_height: Optional[int],
    video_duration: Optional[int],
    thumbnail_path: Optional[str],
    caption: str,
) -> bool:
    """Sends the downloaded video to the user with retry logic for network stability."""
    if not update.message:
        return False

    video_file_url = f"file://{os.path.abspath(video_path)}"
    thumb_file_url = (
        f"file://{os.path.abspath(thumbnail_path)}"
        if thumbnail_path and os.path.exists(thumbnail_path)
        else None
    )

    for attempt in range(MAX_RETRIES):
        try:
            await update.message.reply_video(
                video=video_file_url,
                width=video_width,
                height=video_height,
                duration=video_duration,
                thumbnail=thumb_file_url,
                caption=caption,
                supports_streaming=True,
                read_timeout=READ_TIMEOUT,
                write_timeout=WRITE_TIMEOUT,
            )
            return True
        except (RetryAfter, TimedOut, NetworkError) as e:
            if isinstance(e, RetryAfter):
                retry_seconds = (
                    e.retry_after
                    if isinstance(e.retry_after, int)
                    else int(e.retry_after.total_seconds())
                    if e.retry_after
                    else 5
                )
                wait_time = retry_seconds + 1
            else:
                wait_time = min(2**attempt, 30)

            logger.warning(
                f"Network issue: {e}. Retrying in {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Error sending video: {e}")
            raise

    return False


def _download_video_sync(
    url: str, notifier: ProgressNotifier
) -> Tuple[str, Dict[str, Any]]:
    """Synchronous function to run yt-dlp."""
    ytdlp_opts = {
        "format": VIDEO_FORMAT,
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "merge_output_format": MERGE_FORMAT,
        "progress_hooks": [notifier],
        "quiet": True,
        "no_warnings": True,
    }

    with YoutubeDL(ytdlp_opts) as ytdl:
        info_dict = ytdl.extract_info(url, download=True)
        filename = ytdl.prepare_filename(info_dict)

        # Adjust filename if yt-dlp merged it into mp4
        base_name = filename.rsplit(".", 1)[0]
        mp4_filename = base_name + ".mp4"
        if not os.path.exists(filename) and os.path.exists(mp4_filename):
            filename = mp4_filename

        return filename, info_dict


# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    name = update.effective_user.first_name if update.effective_user else "there"
    await update.message.reply_text(f"Hello {name}! Send me a video URL to download.")


async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_message:
        return

    url = update.effective_message.text
    if not url or not validators.url(url):
        await update.message.reply_text("Please provide a valid URL!")
        return

    update_msg = await update.message.reply_text(
        f"🎯 Target: {url}\n⏳ Initializing download..."
    )

    filename = None
    thumbnail_file = None

    try:
        notifier = ProgressNotifier(context, update_msg.chat_id, update_msg.id, url)
        filename, info_dict = await asyncio.to_thread(
            _download_video_sync, url, notifier
        )

        # Process metadata and thumbnail
        video_width, video_height, video_duration = get_video_metadata(filename)
        video_title = info_dict.get("title", "Unknown Title")

        thumbnail_file = await asyncio.to_thread(
            generate_thumbnail, filename, video_width
        )

        caption = (
            f"🎥 {video_title}\n🔗 {url}\n📊 Quality: {video_width}x{video_height}"
            if video_width
            else f"🎥 {video_title}"
        )

        # Send the finalized video
        success = await send_video_with_retry(
            update,
            filename,
            video_width,
            video_height,
            video_duration,
            thumbnail_file,
            caption,
        )

        if not success:
            await update.message.reply_text(
                "❌ Failed to send video after multiple retries. Please try again later."
            )
        else:
            await context.bot.delete_message(
                chat_id=update_msg.chat_id, message_id=update_msg.id
            )

    except Exception as e:
        logger.exception(f"Error during processing video {url}: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")
    finally:
        # Cleanup
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except OSError as e:
                logger.error(f"Error removing video file {filename}: {e}")
        if thumbnail_file and os.path.exists(thumbnail_file):
            try:
                os.remove(thumbnail_file)
            except OSError as e:
                logger.error(f"Error removing thumbnail file {thumbnail_file}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="YTdlBot")
    parser.add_argument("-t", "--token", help="Bot token")
    args = parser.parse_args()

    bot_token = args.token or os.getenv("BOT_TOKEN")
    if not bot_token:
        logger.error(
            "No bot token provided. Please set BOT_TOKEN environment variable or pass --token."
        )
        return

    app = (
        ApplicationBuilder()
        .token(bot_token)
        .base_url(API_BASE_URL)
        .local_mode(True)
        .read_timeout(READ_TIMEOUT)
        .write_timeout(WRITE_TIMEOUT)
        .pool_timeout(POOL_TIMEOUT)
        .connect_timeout(CONNECT_TIMEOUT)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(~filters.COMMAND, process_download))

    logger.info("Bot started successfully.")
    app.run_polling()


if __name__ == "__main__":
    main()
