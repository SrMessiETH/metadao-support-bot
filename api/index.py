import os
import json
from telegram import Update
from telegram.ext import Application, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.environ['BOT_TOKEN']

# Build the application at module level
application = Application.builder().token(BOT_TOKEN).build()

# Example handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello from Vercel!")

# Register handlers inside a function
def setup_handlers():
    if not application.handlers:
        application.add_handler(CallbackQueryHandler(start, pattern="^start$"))

# Vercel webhook entrypoint
async def handler(event, context):
    setup_handlers()  # ensures handlers are registered only when invoked
    if 'body' not in event:
        return {"statusCode": 400, "body": "No body"}
    
    update = Update.de_json(json.loads(event['body']), application.bot)
    await application.update_queue.put(update)
    await application.update_queue.join()
    return {"statusCode": 200, "body": "ok"}

