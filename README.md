# YTDLBot - Telegram Video Downloader

## Requirements

Before proceeding, ensure the following components are installed on your system:

- [uv](https://github.com/astral-sh/uv)
- [telegram-bot-api](https://github.com/tdlib/telegram-bot-api)
- [ffmpeg](https://www.ffmpeg.org/download.html)

## Installation and Configuration Guide

### 1. Local Telegram Bot API Server Setup

To bypass the file size limits imposed by official Telegram servers, a local server configuration is required.

- Follow the [official documentation](https://tdlib.github.io/telegram-bot-api/build.html) to build the server, or use pre-compiled versions such as tdlib.native.

### 2. Telegram API Credentials

- Obtain your `api-id` and `api-hash` by registering your application on the [Telegram API](https://core.telegram.org/api/obtaining_api_id) portal.

### 3. Starting the API Server

Run the local server using the following command:

```bash
telegram-bot-api --api-id YOUR_API_ID --api-hash YOUR_API_HASH --http-port 7575 --local
```

### 4. Logging Out from the Official Server

Before using the local server, you must log out the bot from the official Telegram servers. Access the following URL via your browser:

```url
https://api.telegram.org/bot<YOUR_TOKEN>/logOut
```

Replace `<YOUR_TOKEN>` with the bot token provided by BotFather. A JSON response with `"ok": true` confirms the operation.

### 5. Environment Configuration

1. Rename the `.env-example` file to `.env`.
2. Enter your bot token in the `.env` file or pass it as an argument during startup.

## Usage

To start the bot, use the following command:

```bash
uv run bot.py
```

The bot will process valid URLs sent in the chat, download the content, and send the video file.

## Contributing

Contributions to the project are welcome. You can report bugs via issues or propose improvements through pull requests.
