# 📥 YTDLBot - Telegram Video Downloader

## 📦 Requirements
Before getting started, make sure you have the following installed:
- [uv](https://github.com/astral-sh/uv)
- [telegram-bot-api](https://github.com/tdlib/telegram-bot-api)
- [ffmpeg](https://www.ffmpeg.org/download.html)

## 🚀 Quick Start Guide

### Step 1: Run Your Local Bot API Server
Follow the instructions to set up your local server from the [official documentation](https://tdlib.github.io/telegram-bot-api/build.html).

### Step 2: Obtain API Credentials
Get your `api-id` and `api-hash` from the [Telegram API](https://core.telegram.org/api/obtaining_api_id).

### Step 3: Set Up Environment Variables
Set your environment variables with your obtained credentials:

```bash
export TELEGRAM_API_ID=YOUR_API_ID
export TELEGRAM_API_HASH=YOUR_API_HASH
```

### Step 4: Start the Server
Run the bot API server using the following command:

```bash
telegram-bot-api --api-id YOUR_API_ID --api-hash YOUR_API_HASH --http-port 7575
```

### Step 5: Interact with Your Bot
Start chatting with your bot on Telegram and begin downloading videos!

## 🤝 Contributing
We welcome contributions from the community! Feel free to submit issues, fork the project, and create pull requests.
