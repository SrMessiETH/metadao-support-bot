import json
import logging
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, BotCommand
from telegram.request import HTTPXRequest
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
    GOOGLE_CREDENTIALS = None
else:
    GOOGLE_CREDENTIALS = json.loads(GOOGLE_CREDENTIALS_JSON)

# Resource links
RESOURCE_LINKS = {
    'docs': 'https://docs.metadao.fi/',
    'get_listed': 'https://docs.metadao.fi/how-launches-work/create',
    'icos': 'https://www.idontbelieve.link',
    'how_launches_work': 'https://docs.metadao.fi/how-launches-work/sale',
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

# Known project info
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
        [InlineKeyboardButton("How Launches Work", callback_data='how_launches_work')],
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

# Function to log request to Google Sheets
def log_request(name, email, question, category, extra_data=None):
    sheet = get_sheets_client()
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if extra_data:
            # For get listed submissions with detailed data
            row = [timestamp, name, email, category]
            row.extend([
                extra_data.get('project_name_short', ''),
                extra_data.get('project_desc_long', ''),
                extra_data.get('token_name', ''),
                extra_data.get('token_ticker', ''),
                extra_data.get('project_image', ''),
                extra_data.get('token_image', ''),
                extra_data.get('min_raise', ''),
                extra_data.get('monthly_budget', ''),
                extra_data.get('performance_package', ''),
                extra_data.get('performance_unlock_time', ''),
                extra_data.get('intellectual_property', '')
            ])
            sheet.append_row(row)
        else:
            # For simple support requests
            sheet.append_row([timestamp, name, email, question, category])
        logger.info(f"Request logged: {name}, {email}, {category}")
    else:
        logger.warning("Could not log to Google Sheets - client not available")

# Function to forward to support chat
async def forward_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if SUPPORT_CHAT_ID:
        user = update.effective_user
        username = user.username if user.username else 'no username'
        chat_type = 'Group' if update.effective_chat.type != 'private' else 'Private'
        message_text = (
            f"New support request from {context.user_data.get('name')} ({username}):\n"
            f"Email: {context.user_data.get('email')}\n"
            f"Question: {context.user_data.get('question')}\n"
            f"Category: {context.user_data.get('category', 'General')}\n"
            f"User ID: {user.id}\n"
            f"Chat Type: {chat_type}"
        )
        await context.bot.send_message(chat_id=SUPPORT_CHAT_ID, text=message_text)

# Start message handler
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
    # Remove any reply keyboard
    await update.message.reply_text(".", reply_markup=ReplyKeyboardRemove())
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id + 1)

# Help command handler
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != 'private':
        return
    help_text = (
        "🤖 *MetaDAO Support Bot Help*\n\n"
        "*Available Commands:*\n"
        "/start - Start the bot and show main menu\n"
        "/help - Show this help message\n"
        "/cancel - Cancel current operation\n\n"
        "*How to use:*\n"
        "• Use the inline menu buttons to navigate\n"
        "• Select 'Support Request' to submit a question\n"
        "• Type 'ca' to get the META token contract address\n\n"
        "*Resources:*\n"
        "📚 Documentation: https://docs.metadao.fi/\n"
        "🌐 Website: https://metadao.fi"
    )
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]]),
        disable_web_page_preview=True
    )

# Cancel command handler
async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.type != 'private':
        return ConversationHandler.END
    
    # Clear any active support request
    if context.user_data.get('support_active'):
        context.user_data.clear()
        await update.message.reply_text(
            "Support request cancelled.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "No active operation to cancel.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END

# Callback query handler
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

    # Handle sub proposals
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

    # Handle main categories (excluding get_listed and support_request which are conversations)
    category_map = {
        'icos': 'ICOs',
        'how_launches_work': 'How Launches Work',
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
    context.user_data['category'] = 'Support Request'
    name = context.user_data['name']
    email = context.user_data['email']

    log_request(name, email, question, 'Support Request')
    await forward_to_support(update, context)

    response = "Thank you for your submission! Our support team will review it and get back to you via email soon."

    await update.message.reply_text(
        response,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
    )
    context.user_data.clear()
    context.user_data['support_active'] = False
    return ConversationHandler.END

# Get listed conversation handlers
async def get_listed_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("Yes, I want to get listed", callback_data='get_listed_yes')],
        [InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        "Would you like to proceed with getting your project listed on MetaDAO?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GET_LISTED_CONFIRM

async def get_listed_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == 'get_listed_yes':
        context.user_data['get_listed_active'] = True
        await query.edit_message_text(
            "Great! Let's get started. Please provide your project name and a short description (1-2 sentences):"
        )
        return PROJECT_NAME_SHORT
    else:
        await query.edit_message_text(
            "No problem! Returning to main menu.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END

async def get_project_name_short(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['project_name_short'] = update.message.text
    await update.message.reply_text("Thank you! Now please provide a longer, more detailed description of your project:")
    return PROJECT_DESC_LONG

async def get_project_desc_long(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['project_desc_long'] = update.message.text
    await update.message.reply_text("Great! What is your token name?")
    return TOKEN_NAME

async def get_token_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['token_name'] = update.message.text
    await update.message.reply_text("What is your token ticker symbol?")
    return TOKEN_TICKER

async def get_token_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['token_ticker'] = update.message.text
    await update.message.reply_text("Please provide the URL for your project image:")
    return PROJECT_IMAGE

async def get_project_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['project_image'] = update.message.text
    await update.message.reply_text("Please provide the URL for your token image (or type 'same' if it's the same as the project image):")
    return TOKEN_IMAGE

async def get_token_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    token_image = update.message.text
    if token_image.lower() == 'same':
        context.user_data['token_image'] = context.user_data['project_image']
    else:
        context.user_data['token_image'] = token_image
    await update.message.reply_text("What is your minimum raise amount? (e.g., $50,000)")
    return MIN_RAISE

async def get_min_raise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['min_raise'] = update.message.text
    await update.message.reply_text("What is your monthly team budget? (e.g., $10,000)")
    return MONTHLY_BUDGET

async def get_monthly_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['monthly_budget'] = update.message.text
    await update.message.reply_text("What is your performance package amount? (e.g., $25,000)")
    return PERFORMANCE_PACKAGE

async def get_performance_package(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['performance_package'] = update.message.text
    await update.message.reply_text("What is the minimum unlock time for the performance package? (e.g., 6 months)")
    return PERFORMANCE_UNLOCK_TIME

async def get_performance_unlock_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['performance_unlock_time'] = update.message.text
    await update.message.reply_text("Finally, please list any intellectual property (patents, trademarks, etc.) or type 'none':")
    return INTELLECTUAL_PROPERTY

async def get_intellectual_property(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['intellectual_property'] = update.message.text
    
    # Validate all fields are filled
    required_fields = [
        'project_name_short', 'project_desc_long', 'token_name', 'token_ticker',
        'project_image', 'token_image', 'min_raise', 'monthly_budget',
        'performance_package', 'performance_unlock_time', 'intellectual_property'
    ]
    
    missing_fields = [field for field in required_fields if not context.user_data.get(field)]
    
    if missing_fields:
        await update.message.reply_text(
            f"Some fields are missing: {', '.join(missing_fields)}. Please start over with /start",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Prepare extra_data for logging
    extra_data = {k: context.user_data.get(k, '') for k in required_fields}
    
    # Log to Google Sheets
    log_request(
        context.user_data['project_name_short'],
        update.effective_user.username or str(update.effective_user.id),
        None,  # No question for get listed
        'Get Listed',
        extra_data=extra_data
    )
    
    await update.message.reply_text(
        "Thank you for your submission! Our team will review your project and get back to you soon.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
    )
    
    context.user_data.clear()
    context.user_data['get_listed_active'] = False
    return ConversationHandler.END

async def get_listed_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get('get_listed_active'):
        context.user_data.clear()
        await update.message.reply_text(
            "Get listed submission cancelled.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END
    return ConversationHandler.END

# CA handler
async def handle_ca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == 'private':
        return
    ca_variants = ["CA", "ca", "Ca"]
    if update.message.text in ca_variants:
        await update.message.reply_text(META_CA, reply_markup=ReplyKeyboardRemove())

# Text handler (placeholder)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass

# Build application
application = Application.builder().token(BOT_TOKEN).build()

# Get listed conversation handler
get_listed_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(get_listed_start, pattern='^get_listed$')],
    states={
        GET_LISTED_CONFIRM: [CallbackQueryHandler(get_listed_confirm)],
        PROJECT_NAME_SHORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_project_name_short)],
        PROJECT_DESC_LONG: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_project_desc_long)],
        TOKEN_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_token_name)],
        TOKEN_TICKER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_token_ticker)],
        PROJECT_IMAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_project_image)],
        TOKEN_IMAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_token_image)],
        MIN_RAISE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_min_raise)],
        MONTHLY_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_monthly_budget)],
        PERFORMANCE_PACKAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_performance_package)],
        PERFORMANCE_UNLOCK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_performance_unlock_time)],
        INTELLECTUAL_PROPERTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_intellectual_property)],
    },
    fallbacks=[CommandHandler('cancel', get_listed_cancel)],
)

# Support conversation handler
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(support_start, pattern='^support_request$')],
    states={
        NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
        QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
    },
    fallbacks=[CommandHandler('cancel', cancel_handler)],
)

# Add handlers in correct order
application.add_handler(CommandHandler('start', start_handler))
application.add_handler(CommandHandler('help', help_handler))
application.add_handler(CommandHandler('cancel', cancel_handler))
application.add_handler(get_listed_conv_handler)
application.add_handler(conv_handler)
application.add_handler(CallbackQueryHandler(button_handler, pattern='^(?!get_listed$|support_request$)'))
application.add_handler(MessageHandler(filters.Regex(r'^(CA|ca|Ca)$'), handle_ca))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
application.add_handler(MessageHandler(filters.COMMAND, text_handler))

_initialized = False

async def ensure_initialized():
    """Ensure application is initialized before processing updates"""
    global _initialized
    if not _initialized:
        await application.initialize()
        await application.bot.initialize()
        commands = [
            BotCommand("start", "Start the bot and show main menu"),
            BotCommand("help", "Show help information"),
            BotCommand("cancel", "Cancel current operation")
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands menu set successfully")
        _initialized = True

_processing_updates = set()
_update_cleanup_tasks = {}

class handler(BaseHTTPRequestHandler):
    def send_success_response(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = json.dumps({'ok': True})
        self.wfile.write(response.encode('utf-8'))

    def do_POST(self):
        """Handle POST requests from Telegram webhook"""
        update_id = None
        try:
            logger.info("Webhook POST request received")
            
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            # Parse JSON update from Telegram
            update_dict = json.loads(body.decode('utf-8'))
            
            update_id = update_dict.get('update_id')
            if update_id and update_id in _processing_updates:
                logger.warning(f"Duplicate update {update_id} detected, skipping")
                self.send_success_response()
                return
            
            if update_id:
                _processing_updates.add(update_id)
            
            logger.info(f"Processing update {update_id}")
            
            # Create Update object
            update = Update.de_json(update_dict, application.bot)
            
            # Use asyncio.run() which properly manages event loop lifecycle
            asyncio.run(self._process_update_async(update, update_id))
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            import traceback
            traceback.print_exc()
            
            # Remove from processing set on error
            if update_id and update_id in _processing_updates:
                _processing_updates.discard(update_id)
        finally:
            self.send_success_response()
    
    async def _process_update_async(self, update: Update, update_id: int):
        """Async function to process update with proper cleanup"""
        try:
            # Ensure initialization
            await ensure_initialized()
            
            # Process the update
            await application.process_update(update)
            logger.info("Update processed successfully")
            
            # Give time for any pending HTTP operations to complete
            await asyncio.sleep(0.5)
            
            # Schedule cleanup for later
            if update_id:
                asyncio.create_task(self._cleanup_update_id_delayed(update_id))
                
        except Exception as e:
            logger.error(f"Error in async update processing: {e}")
            import traceback
            traceback.print_exc()
    
    async def _cleanup_update_id_delayed(self, update_id: int):
        """Remove update ID from tracking after delay"""
        await asyncio.sleep(30)
        _processing_updates.discard(update_id)
        logger.info(f"Cleaned up update ID: {update_id}")

    def do_GET(self):
        """Handle GET requests for health check"""
        logger.info("Health check GET request received")
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'MetaDAO Bot is running!')

logger.info("Application built successfully")
