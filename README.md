# YTDLBot - Telegram Video Downloader

## Prerequisites

Before deploying the bot, you will need:

- A **Bot Token** from [@BotFather](https://t.me/botfather).
- Your **API ID** and **API Hash** from the [Telegram API Portal](https://my.telegram.org/apps).

## Quick Start

### 1. Configure the Environment

Clone the repository and prepare your environment variables:

```bash
cp .env.example .env
```

Edit the `.env` file and fill in your preferences.

### 2. Log out from the Official Server

Before using a local API server, you must log out your bot from the official Telegram cloud. Open your browser and navigate to:

```url
https://api.telegram.org/bot<YOUR_TOKEN>/logOut
```

_A JSON response with `"ok": true` confirms the operation._

### 3. Start the Services

Run the following command to build and start the bot alongside the Telegram API server:

```bash
docker compose up -d --build
```

The bot is now running and ready to process video URLs in your Telegram chats.
