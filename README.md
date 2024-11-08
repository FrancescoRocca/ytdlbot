# 📥 YTDLBot - Telegram Video Downloader

## 📦 Requirements
Before getting started, ensure you have the following installed:

- [uv](https://github.com/astral-sh/uv)
- [telegram-bot-api](https://github.com/tdlib/telegram-bot-api)
- [ffmpeg](https://www.ffmpeg.org/download.html)

## 🚀 Quick Start Guide

1. **Run Your Local Bot API Server**
    - Follow the instructions to set up your local server from the [official documentation](https://tdlib.github.io/telegram-bot-api/build.html). If you don't want to build it yourself, you can check tdlib.native.

2. **Obtain API Credentials**
    - Get your `api-id` and `api-hash` from the [Telegram API](https://core.telegram.org/api/obtaining_api_id).

3. **Start the Server**
    - Run the bot API server using the following command:
        ```bash
        telegram-bot-api --api-id YOUR_API_ID --api-hash YOUR_API_HASH --http-port 7575 --local
        ```

4. **Log Out the Bot from the Official API**
    - Open this link in your browser:
    
        ```url
        https://api.telegram.org/bot<YOUR_TOKEN>/logOut
        ```

    - Make sure to replace `<YOUR_TOKEN>` with your actual bot token. You should see a JSON response that looks like this:

        ```json
        {"ok":true,"result":true}
        ```

5. **Interact with the Bot**
    - Rename `.env-example` to `.env` and add your bot token there (or pass it to the script with `-t <TOKEN>`). Then run the bot:

        ```bash
        uv run bot.py
        ```

## 🤝 Contributing
We welcome contributions from the community! Feel free to submit issues, fork the project, and create pull requests.
