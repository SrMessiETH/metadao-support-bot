import os
import json
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, ContextTypes, CallbackQueryHandler, CommandHandler

app = FastAPI()

BOT_TOKEN = os.environ['BOT_TOKEN']
application = Application.builder().token(BOT_TOKEN).build()

# Fixed handler: Works for both messages (via CommandHandler) and callbacks
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("Hello from Vercel!")
    elif update.callback_query:
        await update.callback_query.message.reply_text("Hello from Vercel!")
        await update.callback_query.answer()  # Acknowledge the callback to remove loading spinner

def setup_handlers():
    if not application.handlers:
        # For /start command (messages)
        application.add_handler(CommandHandler("start", start))
        # For callback queries with data "start" (e.g., from inline keyboards)
        application.add_handler(CallbackQueryHandler(start, pattern="^start$"))

@app.post("/webhook")
async def webhook(request: Request):
    setup_handlers()  # Register handlers only on invocation
    body = await request.body()
    if not body:
        return {"statusCode": 400, "body": "No body"}
    
    try:
        update = Update.de_json(json.loads(body), application.bot)
        if update:
            await application.process_update(update)
        await application.update_queue.join()  # Wait for processing (optional but ensures completion)
        return {"statusCode": 200, "body": "ok"}
    except Exception as e:
        # Log error (in production, use proper logging)
        print(f"Error processing update: {e}")
        return {"statusCode": 500, "body": "Error"}

@app.get("/")
async def root():
    return {"message": "Bot is running on Vercel!"}
