import json
import logging
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, BotCommand
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from http.server import BaseHTTPRequestHandler
import asyncio

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for support conversation
NAME, EMAIL, QUESTION = range(3)

# States for get listed conversation
GET_LISTED_CONFIRM, PROJECT_NAME_SHORT, PROJECT_DESC_LONG, TOKEN_NAME, TOKEN_TICKER, PROJECT_IMAGE, TOKEN_IMAGE, MIN_RAISE, MONTHLY_BUDGET, PERFORMANCE_PACKAGE, PERFORMANCE_UNLOCK_TIME, INTELLECTUAL_PROPERTY = range(12, 24)

# ... existing code ...

# <CHANGE> Move all function definitions before ConversationHandler definitions

# Support start handler
async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("To submit a support request, please provide your full name:")
    context.user_data['support_active'] = True
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Thank you! Now, please provide your email address so we can contact you if needed.")
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    context.user_data['email'] = update.message.text
    await update.message.reply_text("Now, please describe your issue, question, or bug:")
    return QUESTION

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    question = update.message.text
    context.user_data['question'] = question
    name = context.user_data['name']
    email = context.user_data['email']

    log_request(name, email, question, 'Support Request')
    await forward_to_support(update, context)

    response = "Thank you for your submission! Our support tea
