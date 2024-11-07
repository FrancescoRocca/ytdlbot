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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"Hello {update.effective_user.first_name}!")


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    url = update.effective_message.text
    if not validators.url(url):
        await update.message.reply_text("Please provide a valid URL!")
        return

    await update.message.reply_text(f"Downloading {url}...")

    ytdlp_opts = {
        "format": "bestvideo+bestaudio/best",
        "outtmpl": "./videos/%(title)s.%(ext)s",
        "merge_output_format": "mp4",
    }

    with YoutubeDL(ytdlp_opts) as ytdl:
        info_dict = ytdl.extract_info(url, download=True)
        filename = ytdl.prepare_filename(info_dict)

        video_duration = info_dict.get("duration", 0)
        video_width = info_dict.get("width", 0)
        video_height = info_dict.get("height", 0)
        thumbnail = info_dict.get("thumbnail", None)

        await context.bot.send_message(
            chat_id=update.message.chat_id, text="Uploading video..."
        )

        media = InputMediaVideo(
            media=open(filename, "rb"),
            width=video_width,
            height=video_height,
            duration=video_duration,
            thumbnail=thumbnail,
        )
        await update.message.reply_media_group(media=[media])


def main():
    parser = argparse.ArgumentParser(
        prog="YTdlBot", description="Telegram Video Downloader Bot"
    )
    parser.add_argument("-t", "--token", help="Bot token")
    parser.add_argument("-w", "--webhook", help="Webhook URL")
    args = parser.parse_args()
    print(args)

    print("Loading bot token...")
    load_dotenv()
    bot_token = os.getenv("BOT_TOKEN")

    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(~filters.COMMAND, message))
    app.run_polling()


if __name__ == "__main__":
    main()
