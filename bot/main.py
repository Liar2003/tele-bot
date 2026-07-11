import asyncio
import logging
from telegram.ext import ApplicationBuilder
from telethon import TelegramClient
from config import BOT_TOKEN, API_ID, API_HASH, SESSION_NAME
from bot.handlers import setup_handlers

async def main():
    # Bot client
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    setup_handlers(app)

    # MTProto user client (kept as a shared object)
    user_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await user_client.start()   # will prompt for phone/code if no session

    # Store user_client in bot_data for handlers to access
    app.bot_data["user_client"] = user_client

    # Run both (polling for bot; user_client already connected)
    async with app:
        await app.start()
        await app.updater.start_polling()
        logging.info("Bot and user client running...")
        # Keep alive
        await asyncio.Event().wait()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
