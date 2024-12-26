from yt_dlp import YoutubeDL
from telegram import Update, InputMediaVideo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from dotenv import load_dotenv
import os
import argparse
import validators
import ffmpeg
import urllib3
import json
from time import time

bot_token = None


def tg_edit_message(text: str, chat_id: int, message_id: int):
    # @TODO: find a better way to deal with this
    urllib3.request(
        "POST",
        f"https://api.telegram.org/bot{bot_token}/editMessageText",
        body=json.dumps(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "disable_web_page_preview": True,
            }
        ),
        headers={"Content-Type": "application/json"},
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Hello {update.effective_user.first_name}!")


def get_video_metadata(filename):
    probe = ffmpeg.probe(filename)
    video_stream = next(
        (stream for stream in probe["streams"] if stream["codec_type"] == "video"), None
    )
    if video_stream:
        width = int(video_stream["width"])
        height = int(video_stream["height"])
        duration = int(float(probe["format"]["duration"]))
        return width, height, duration
    return None, None, None


def create_progress_bar(percentage: float, width: int = 20) -> str:
    filled = int(width * percentage / 100)
    bar = "█" * filled + "▒" * (width - filled)
    return bar


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.effective_message.text
    if not validators.url(url):
        await update.message.reply_text("Please provide a valid URL!")
        return

    update_msg = await update.message.reply_text(
        f"🎯 Target: {url}\n⏳ Initializing download..."
    )

    def progress_hook(d: dict):
        last_update = 0
        update_interval = 1

        if d["status"] == "downloading" and d.get("total_bytes"):
            current_time = time()
            if current_time - last_update >= update_interval:
                last_update = current_time
                percentage = round(d["downloaded_bytes"] / d["total_bytes"] * 100)
                elapsed = round(d["elapsed"]) if d.get("elapsed") else 0
                eta = round(d["eta"]) if d.get("eta") else 0
                speed = round(round(d["speed"]) / 1024) if d.get("speed") else 0

                progress_bar = create_progress_bar(percentage)
                file_size_mb = round(d["total_bytes"] / (1024 * 1024), 2)
                tg_edit_message(
                    text=(
                        f"📥 Downloading: {url}\n"
                        f"📦 Size: {file_size_mb} MB\n"
                        f"⏳ Progress: {progress_bar} {percentage}%\n"
                        f"🚀 Speed: {speed} KB/s\n"
                        f"⌛ Elapsed: {elapsed}s\n"
                        f"🎯 ETA: {eta}s"
                    ),
                    chat_id=update_msg.chat_id,
                    message_id=update_msg.id,
                )
        elif d["status"] == "finished":
            tg_edit_message(
                text="🔄 Processing video...",
                chat_id=update_msg.chat_id,
                message_id=update_msg.id,
            )

    ytdlp_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": "./videos/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
        "progress_hooks": [progress_hook],
    }

    with YoutubeDL(ytdlp_opts) as ytdl:
        info_dict = ytdl.extract_info(url, download=True)
        filename = ytdl.prepare_filename(info_dict)

        video_width, video_height, video_duration = get_video_metadata(filename)
        video_title = info_dict.get("title", "No title found")

        thumbnail_file = "./videos/thumb.jpg"
        (
            ffmpeg.input(filename, ss=5)
            .filter("scale", video_width, -1)
            .output(thumbnail_file, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )

        with open(filename, "rb") as video_file:
            media = InputMediaVideo(
                media=video_file,
                width=video_width,
                height=video_height,
                duration=video_duration,
                thumbnail=open(thumbnail_file, "rb") if thumbnail_file else None,
                supports_streaming=True,
            )
            await update.message.reply_media_group(
                media=[media],
                caption=(
                    f"🎥 {video_title}\n"
                    f"🔗 {url}\n"
                    f"📊 Quality: {video_width}x{video_height}"
                ),
            )

            await context.bot.delete_message(
                chat_id=update_msg.chat_id, message_id=update_msg.id
            )

    os.remove(filename)
    if thumbnail_file:
        os.remove(thumbnail_file)


def main():
    global bot_token

    parser = argparse.ArgumentParser(
        prog="YTdlBot", description="Telegram Video Downloader Bot"
    )
    parser.add_argument("-t", "--token", help="Bot token")
    args = parser.parse_args()

    if args.token:
        print("Token obtained from the args...")
        bot_token = args.token
    else:
        print("Loading env vars...")
        load_dotenv()
        bot_token = os.getenv("BOT_TOKEN")

    app = (
        ApplicationBuilder()
        .token(bot_token)
        .base_url("http://localhost:7575/bot")
        .local_mode(True)
        .read_timeout(20)
        .write_timeout(35)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(~filters.COMMAND, message))
    app.run_polling()


if __name__ == "__main__":
    main()
