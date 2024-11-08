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


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.effective_message.text
    if not validators.url(url):
        await update.message.reply_text("Please provide a valid URL!")
        return

    ytdlp_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": "./videos/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
    }

    with YoutubeDL(ytdlp_opts) as ytdl:
        update_msg = await update.message.reply_text(f"Downloading {url}...")
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

        await context.bot.edit_message_text(
            text="Uploading...",
            chat_id=update.message.chat_id,
            message_id=update_msg.id,
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
                caption=f"{video_title}\n\n{url}\nInfo: {video_width}x{video_height}",
            )

            await context.bot.delete_message(
                chat_id=update_msg.chat_id, message_id=update_msg.id
            )

    os.remove(filename)
    if thumbnail_file:
        os.remove(thumbnail_file)


def main():
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
