 import json
import logging
from telegram.ext import Application
from telegram.ext import ConversationHandler, CommandHandler, MessageHandler, filters
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for support conversation
NAME, EMAIL, QUESTION = range(3)

# Secrets from env vars
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env var is required")
SUPPORT_CHAT_ID = int(os.environ.get('SUPPORT_CHAT_ID', 0)) if os.environ.get('SUPPORT_CHAT_ID') else None
SHEET_NAME = os.environ.get('SHEET_NAME', 'MetaDAO Support Requests')

# Google Sheets setup
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS')
if not GOOGLE_CREDENTIALS_JSON:
    logger.warning("GOOGLE_CREDENTIALS env var missing—Sheets logging disabled")
else:
    GOOGLE_CREDENTIALS = json.loads(GOOGLE_CREDENTIALS_JSON)

# Resource links (unchanged)
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
    'listed': 'https://docs.metadao.fi/how-launches-work/create',
    'ico': 'https://docs.metadao.fi/how-launches-work/sale',
    'proposal': 'https://docs.metadao.fi/governance/proposals',
    'calendar': 'https://www.idontbelieve.link',
    'website': 'https://metadao.fi',
    'umbra': 'https://metadao.fi/projects/umbra/fundraise',
    'avici': 'https://www.idontbelieve.link/?p=27eeb88879cf81a5b421cee972236ed6&pm=c',
    'paystream': 'https://www.idontbelieve.link/?p=27eeb88879cf81bb9374eb8a1009d4ff&pm=c',
    'loyal': 'https://www.idontbelieve.link/?p=27eeb88879cf81339324e7f98d8dbd9f&pm=c',
    'zklsol': 'https://www.idontbelieve.link/?p=27eeb88879cf81269d9ece79cba66623&pm=c',
    'evora': 'https://www.idontbelieve.link/?p=283eb88879cf80aaa0b7ed2c1f691d2d&pm=c',
    'aurum': 'https://www.idontbelieve.link/?p=285eb88879cf808e83d3f2ea73b00647&pm=c',
}

# Known project info (unchanged)
PROJECT_INFO = {
    'meta': {
        'ca': 'METAwkXcqyXKy1AtsSgJ8JiUHwGCafnZL38n3vYmeta'
    },
    'umbra': {
        'ca': 'TBA (Token not yet launched - check after ICO completion)',
        'max_supply': '28.5 million tokens',
        'min_target': '$750K',
        'max_target': 'Is blind and will reveal when ICO ends',
        'tokenomics': 'https://x.com/UmbraPrivacy/status/1973785682872062014'
    }
}
META_CA = 'METAwkXcqyXKy1AtsSgJ8JiUHwGCafnZL38n3vYmeta'

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

# Initialize Google Sheets client
def get_sheets_client():
    try:
        if not GOOGLE_CREDENTIALS:
            return None
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).sheet1
        return sheet
    except Exception as e:
        logger.error(f"Error setting up Google Sheets: {e}")
        return None

# Function to log request to Google Sheets (unchanged)
def log_request(name, email, question, category):
    sheet = get_sheets_client()
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([timestamp, name, email, question, category])
        logger.info(f"Request logged: {name}, {email}, {question}, {category}")
    else:
        logger.warning("Could not log to Google Sheets - client not available")

# Function to forward to support chat (unchanged)
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

# Start message handler (unchanged, but async)
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != 'private':
        return
    user = update.effective_user
    await update.message.reply_text(
        f'Hello {user.first_name}! Welcome to MetaDAO Support Bot.\n\n'
        f'For more information, check our docs: https://docs.metadao.fi/\n\n'
        'Please select a category from the menu below:',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Show Main Menu", callback_data='main_menu')]]),
        disable_web_page_preview=True
    )

# Callback query handler (updated: handle support_request to start conv and return NAME)
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != 'private':
        await update.callback_query.answer()
        return
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data == 'main_menu':
        await context.bot.send_message(
            chat_id=chat_id,
            text="Main Menu:",
            reply_markup=main_inline_keyboard(),
            disable_web_page_preview=True
        )
        return

    if data == 'proposals':
        await context.bot.send_message(
            chat_id=chat_id,
            text="Proposals Submenu:",
            reply_markup=proposals_inline_keyboard(),
            disable_web_page_preview=True
        )
        return

    # Handle sub proposals (unchanged)
    sub_map = {
        'proposals_create': 'Creating Proposals',
        'proposals_trade': 'Trading Proposals',
        'proposals_finalize': 'Finalizing Proposals',
    }
    if data in sub_map:
        text_name = sub_map[data]
        link = RESOURCE_LINKS[data]
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Here is the information for {text_name}:\n{link}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')]]),
            disable_web_page_preview=True
        )
        return

    # Handle main categories (unchanged)
    category_map = {
        'get_listed': 'Get Listed',
        'icos': 'ICOs',
        'futarchy_intro': 'Introduction to Futarchy',
        'entrepreneurs': 'For Entrepreneurs',
        'investors': 'For Investors',
    }
    if data in category_map:
        text_name = category_map[data]
        link = RESOURCE_LINKS[data]
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
        return NAME  # Start the conversation

# Support conversation handlers (unchanged)
async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This is now triggered by callback, so minimal
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

    # Log to sheets
    log_request(name, email, question, 'Support Request')

    # Forward to support if enabled
    await forward_to_support(update, context)

    response = "Thank you for your submission! Our support team will review it and get back to you via email soon."

    await update.message.reply_text(
        response,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
    )
    context.user_data.clear()  # Reset for next conversation
    context.user_data['support_active'] = False
    return ConversationHandler.END

# Text message handler for non-support (fixed ca_variants)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != 'private':
        return
    text = update.message.text.lower()
    if context.user_data.get('support_active'):
        return  # Let conversation handler deal with it

    if text in ['start', '/start']:
        await start_handler(update, context)
        return

    ca_variants = ["ca"]  # Deduped
    if text in ca_variants:
        await update.message.reply_text(META_CA)
        return

    await update.message.reply_text(
        "Please use the inline menu to select an option.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
    )

# CA handler for groups only (unchanged, but fixed variants)
async def handle_ca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == 'private':
        return  # Ignore in private to avoid interfering with conversation
    ca_variants = ["CA", "ca", "Ca"]
    if update.message.text in ca_variants:
        await update.message.reply_text(META_CA, reply_markup=ReplyKeyboardRemove())

# Build the application (once, outside handler)
application = Application.builder().token(BOT_TOKEN).build()

# Conversation handler (updated entry point for callback)
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(support_start, pattern='^support_request$')],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
        QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
    },
    fallbacks=[],
)

# Add handlers
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.Regex(r'^(CA|ca|Ca)$'), handle_ca))
application.add_handler(conv_handler)
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
application.add_handler(MessageHandler(filters.COMMAND, text_handler))  # Handle commands as text

if __name__ == "__main__":
    logger.info("Starting MetaDAO Support Bot...")
    application.run_polling(drop_pending_updates=True)  # drop_pending_updates=True ignores old messages on start
