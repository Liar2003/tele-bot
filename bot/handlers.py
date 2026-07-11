from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from bot.tasks import process_upload

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Send me a direct file link with /upload <url>.\nMax ~2GB."
    )

async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /upload <direct_url>")
        return

    url = context.args[0]
    user_client = context.bot_data.get("user_client")
    if not user_client:
        await update.message.reply_text("User client not ready, try later.")
        return

    # Acknowledge and run upload in background
    message = await update.message.reply_text("⬇️ Downloading file info...")
    context.application.create_task(
        process_upload(update, context, url, message, user_client)
    )

def setup_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upload", upload))
