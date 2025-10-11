import json
import logging
import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
NAME, EMAIL, QUESTION = range(3)

# Environment variables
BOT_TOKEN = os.environ['BOT_TOKEN']
SUPPORT_CHAT_ID = int(os.environ.get('SUPPORT_CHAT_ID', 0)) if os.environ.get('SUPPORT_CHAT_ID') else None
SHEET_NAME = os.environ.get('SHEET_NAME', 'MetaDAO Support Requests')
GOOGLE_CREDENTIALS = json.loads(os.environ['GOOGLE_CREDENTIALS'])

META_CA = 'METAwkXcqyXKy1AtsSgJ8JiUHwGCafnZL38n3vYmeta'

RESOURCE_LINKS = {
    'docs': 'https://docs.metadao.fi/',
    'get_listed': 'https://docs.metadao.fi/how-launches-work/create',
    'icos': 'https://docs.metadao.fi/how-launches-work/sale',
    'futarchy_intro': 'https://docs.metadao.fi/governance/overview',
    'proposals_create': 'https://docs.metadao.fi/governance/proposals',
    'proposals_trade': 'https://docs.metadao.fi/governance/markets',
    'proposals_finalize': 'https://docs.metadao.fi/governance/twaps',
    'entrepreneurs': 'https://docs.metadao.fi/benefits/founders',
    'investors': 'https://docs.metadao.fi/benefits/investors',
}

# Keyboards
def main_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("Get Listed", callback_data='get_listed')],
        [InlineKeyboardButton("ICOs", callback_data='icos')],
        [InlineKeyboardButton("Introduction to Futarchy", callback_data='futarchy_intro')],
        [InlineKeyboardButton("Proposals", callback_data='proposals')],
        [InlineKeyboardButton("For Entrepreneurs", callback_data='entrepreneurs')],
        [InlineKeyboardButton("For Investors", callback_data='investors')],
        [InlineKeyboardButton("Support Request", callback_data='support_request')]
    ]
    return InlineKeyboardMarkup(keyboard)

def proposals_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("Creating Proposals", callback_data='proposals_create')],
        [InlineKeyboardButton("Trading Proposals", callback_data='proposals_trade')],
        [InlineKeyboardButton("Finalizing Proposals", callback_data='proposals_finalize')],
        [InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Google Sheets
def get_sheets_client():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        logger.error(f"Error setting up Google Sheets: {e}")
        return None

def log_request(name, email, question, category):
    sheet = get_sheets_client()
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, name, email, question, category])
        logger.info(f"Request logged: {name}, {email}, {question}, {category}")
    else:
        logger.warning("Could not log to Google Sheets - client not available")

# Support forward
async def forward_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if SUPPORT_CHAT_ID:
        user = update.effective_user
        username = user.username if user.username else 'no username'
        chat_type = 'Group' if update.effective_chat.type != 'private' else 'Private'
        message_text = (
            f"New support request from {context.user_data.get('name')} ({username}):\n"
            f"Email: {context.user_data.get('email')}\n"
            f"Question: {context.user_data.get('question')}\n"
            f"Category: {context.user_data.get('category')}\n"
            f"User ID: {user.id}\n"
            f"Chat Type: {chat_type}"
        )
        await context.bot.send_message(chat_id=SUPPORT_CHAT_ID, text=message_text)

# Handlers
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    user = update.effective_user
    await update.message.reply_text(
        f'Hello {user.first_name}! Welcome to MetaDAO Support Bot.\n\n'
        'Please select a category from the menu below:',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Show Main Menu", callback_data='main_menu')]])
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        await update.callback_query.answer()
        return

    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data == 'main_menu':
        await context.bot.send_message(chat_id=chat_id, text="Main Menu:", reply_markup=main_inline_keyboard())
        return

    if data == 'proposals':
        await context.bot.send_message(chat_id=chat_id, text="Proposals Submenu:", reply_markup=proposals_inline_keyboard())
        return

    sub_map = {
        'proposals_create': 'Creating Proposals',
        'proposals_trade': 'Trading Proposals',
        'proposals_finalize': 'Finalizing Proposals',
    }
    if data in sub_map:
        text_name = sub_map[data]
        link = RESOURCE_LINKS.get(data, "No link available")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Here is the information for {text_name}:\n{link}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')]]),
            disable_web_page_preview=True
        )
        return

    category_map = {
        'get_listed': 'Get Listed',
        'icos': 'ICOs',
        'futarchy_intro': 'Introduction to Futarchy',
        'entrepreneurs': 'For Entrepreneurs',
        'investors': 'For Investors',
    }
    if data in category_map:
        text_name = category_map[data]
        link = RESOURCE_LINKS.get(data, "No link available")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Here is the resource for {text_name}:\n{link}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')]]),
            disable_web_page_preview=True
        )
        return

    if data == 'support_request':
        await query.edit_message_text("To submit a support request, please provide your full name:")
        context.user_data['support_active'] = True
        return NAME

# Conversation Handlers
async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['support_active'] = True
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Thank you! Now, please provide your email address:")
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    context.user_data['email'] = update.message.text
    await update.message.reply_text("Now, please describe your issue, question, or bug:")
    return QUESTION

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    question = update.message.text
    context.user_data['question'] = question

    log_request(context.user_data['name'], context.user_data['email'], question, 'Support Request')
    await forward_to_support(update, context)

    await update.message.reply_text(
        "Thank you for your submission! Our support team will review it soon.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
    )
    context.user_data.clear()
    return ConversationHandler.END

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != 'private':
        return
    text = update.message.text.lower()
    if context.user_data.get('support_active'):
        return
    if text in ['start', '/start']:
        await start_handler(update, context)
        return
    if text in ['ca']:
        await update.message.reply_text(META_CA)
        return
    await update.message.reply_text(
        "Please use the inline menu to select an option.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
    )

async def handle_ca(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
        return
    if update.message.text.lower() == "ca":
        await update.message.reply_text(META_CA, reply_markup=ReplyKeyboardRemove())
async def handler(event=None, context=None):
    if event is None or 'body' not in event:
        return {"statusCode": 400, "body": "No body"}

    # Create application and add handlers (singleton)
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(support_start, pattern='^support_request$')],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
        },
        fallbacks=[],
        per_message=False
    )

    # Add handlers
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^(CA|ca|Ca)$'), handle_ca))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(MessageHandler(filters.COMMAND, text_handler))

    # Deserialize update
    update = Update.de_json(json.loads(event['body']), application.bot)

    # Process update immediately (no queue)
    await application.bot.process_update(update)

    return {"statusCode": 200, "body": "Update received"}
