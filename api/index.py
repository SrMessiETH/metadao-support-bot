import os
import json
from telegram import Update
from telegram.ext import Application, ContextTypes, CallbackQueryHandler

BOT_TOKEN = os.environ['BOT_TOKEN']

# Build the application but do not call run_polling()
application = Application.builder().token(BOT_TOKEN).build()

# Add handlers here
# Example:
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello from Vercel!")

application.add_handler(CallbackQueryHandler(start, pattern="^start$"))

# Vercel handler
async def handler(event, context):
    if 'body' not in event:
        return {"statusCode": 400, "body": "No body"}
    
    update = Update.de_json(json.loads(event['body']), application.bot)
    await application.update_queue.put(update)
    await application.update_queue.join()  # process immediately
    return {"statusCode": 200, "body": "ok"}
