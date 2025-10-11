# api/MetaDAOBot.py
import os
import json
from telegram import Update
from telegram.ext import Application

BOT_TOKEN = os.environ['BOT_TOKEN']

application = Application.builder().token(BOT_TOKEN).build()

async def handler(event, context):
    if 'body' not in event:
        return {"statusCode": 400, "body": "No body"}
    update = Update.de_json(json.loads(event['body']), application.bot)
    await application.update_queue.put(update)
    await application.update_queue.join()  # process immediately
    return {"statusCode": 200, "body": "ok"}
