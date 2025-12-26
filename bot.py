import os
import argparse
import validators
import ffmpeg
import asyncio
import logging
from time import time
from yt_dlp import YoutubeDL
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import RetryAfter, TimedOut, NetworkError
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    name = update.effective_user.first_name if update.effective_user else "there"
    await update.message.reply_text(f"Hello {name}! Send me a video URL to download.")


def get_video_metadata(filename):
    try:
        probe = ffmpeg.probe(filename)
        video_stream = next(
            (stream for stream in probe["streams"] if stream["codec_type"] == "video"),
            None,
        )
        if video_stream:
            width = int(video_stream["width"])
            height = int(video_stream["height"])
            duration = int(float(probe.get("format", {}).get("duration", 0)))
            return width, height, duration
    except Exception as e:
        logger.error(f"Error probing video: {e}")
    return None, None, None


def create_progress_bar(percentage: float, width: int = 20) -> str:
    filled = int(width * percentage / 100)
    bar = "█" * filled + "▒" * (width - filled)
    return bar


async def send_video_with_retry(
    update: Update,
    video_path: str,
    video_width: int,
    video_height: int,
    video_duration: int,
    thumbnail_path: str,
    caption: str,
) -> bool:
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
        except RetryAfter as e:
            retry_seconds = (
                e.retry_after
                if isinstance(e.retry_after, int)
                else int(e.retry_after.total_seconds())
                if e.retry_after
                else 5
            )
            wait_time = retry_seconds + 1
            logger.warning(
                f"Rate limit hit. Waiting {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait_time)
        except TimedOut:
            wait_time = min(2**attempt, 30)
            logger.warning(
                f"Timeout. Retrying in {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait_time)
        except NetworkError as e:
            wait_time = min(2**attempt, 30)
            logger.warning(
                f"Network error: {e}. Retrying in {wait_time}s (attempt {attempt + 1}/{MAX_RETRIES})"
            )
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error(f"Error sending video: {e}")
            raise
    return False


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_message:
        return

    url = update.effective_message.text
    if not url or not validators.url(url):
        await update.message.reply_text("Please provide a valid URL!")
        return

    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

    update_msg = await update.message.reply_text(
        f"🎯 Target: {url}\n⏳ Initializing download..."
    )

    loop = asyncio.get_running_loop()

    progress_state = {
        "last_update": 0,
        "update_interval": PROGRESS_UPDATE_INTERVAL,
        "last_percentage": 0,
    }

    def progress_hook(d: dict):
        if d["status"] == "downloading" and d.get("total_bytes"):
            current_time = time()
            total = d.get("total_bytes") or 0
            downloaded = d.get("downloaded_bytes") or 0
            percentage = round(downloaded * 100 / total) if total else 0

            if (
                current_time - progress_state["last_update"]
                >= progress_state["update_interval"]
                and abs(percentage - progress_state["last_percentage"])
                >= PROGRESS_MIN_PERCENTAGE_CHANGE
            ):
                progress_state["last_update"] = current_time
                progress_state["last_percentage"] = percentage

                elapsed_raw = d.get("elapsed")
                eta_raw = d.get("eta")
                speed_raw = d.get("speed")

                elapsed = (
                    round(elapsed_raw) if isinstance(elapsed_raw, (int, float)) else 0
                )
                eta = round(eta_raw) if isinstance(eta_raw, (int, float)) else 0
                speed = (
                    round(speed_raw / 1024)
                    if isinstance(speed_raw, (int, float)) and speed_raw is not None
                    else 0
                )

                progress_bar = create_progress_bar(percentage)
                file_size_mb = round(total / (1024 * 1024), 2) if total else 0

                text = (
                    f"📥 Downloading: {url}\n"
                    f"📦 Size: {file_size_mb} MB\n"
                    f"⏳ Progress: {progress_bar} {percentage}%\n"
                    f"🚀 Speed: {speed} KB/s\n"
                    f"⌛ Elapsed: {elapsed}s\n"
                    f"🎯 ETA: {eta}s"
                )

                try:
                    coro = context.bot.edit_message_text(
                        text=text,
                        chat_id=update_msg.chat_id,
                        message_id=update_msg.id,
                        disable_web_page_preview=True,
                    )
                    try:
                        asyncio.run_coroutine_threadsafe(coro, loop)
                    except Exception:
                        coro.close()
                except Exception:
                    return
        elif d["status"] == "finished":
            try:
                coro = context.bot.edit_message_text(
                    text="🔄 Processing video...",
                    chat_id=update_msg.chat_id,
                    message_id=update_msg.id,
                )
                try:
                    asyncio.run_coroutine_threadsafe(coro, loop)
                except Exception:
                    coro.close()
            except Exception:
                return

    ytdlp_opts = {
        "format": VIDEO_FORMAT,
        "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
        "merge_output_format": MERGE_FORMAT,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
    }

    filename = None
    thumbnail_file = None

    try:
        with YoutubeDL(ytdlp_opts) as ytdl:
            info_dict = await asyncio.to_thread(ytdl.extract_info, url, download=True)
            filename = ytdl.prepare_filename(info_dict)
            if not os.path.exists(filename) and os.path.exists(
                filename.rsplit(".", 1)[0] + ".mp4"
            ):
                filename = filename.rsplit(".", 1)[0] + ".mp4"

        video_width, video_height, video_duration = get_video_metadata(filename)
        video_title = info_dict.get("title", "No title found")

        thumbnail_file = f"{DOWNLOAD_DIR}/thumb_{int(time())}.jpg"
        try:
            await asyncio.to_thread(
                lambda: (
                    ffmpeg.input(filename, ss=THUMBNAIL_TIMESTAMP)
                    .filter("scale", video_width if video_width else 320, -1)
                    .output(thumbnail_file, vframes=1)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
            )
        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            thumbnail_file = None

        # Send the video with retry logic
        caption = (
            f"🎥 {video_title}\n🔗 {url}\n📊 Quality: {video_width}x{video_height}"
            if video_width
            else f"🎥 {video_title}"
        )

        success = await send_video_with_retry(
            update,
            filename,
            video_width,
            video_height,
            video_duration,
            thumbnail_file or "",
            caption,
        )

        if not success:
            await update.message.reply_text(
                "❌ Failed to send video after multiple retries. Please try again later."
            )
            return

        await context.bot.delete_message(
            chat_id=update_msg.chat_id, message_id=update_msg.id
        )

    except Exception as e:
        logger.error(f"Error during processing: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")
    finally:
        if filename and os.path.exists(filename):
            os.remove(filename)
        if thumbnail_file and os.path.exists(thumbnail_file):
            os.remove(thumbnail_file)


def main():
    parser = argparse.ArgumentParser(prog="YTdlBot")
    parser.add_argument("-t", "--token", help="Bot token")
    args = parser.parse_args()

    bot_token = args.token or os.getenv("BOT_TOKEN")

    if not bot_token:
        logger.error("No bot token provided")
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
    app.add_handler(MessageHandler(~filters.COMMAND, message_handler))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
