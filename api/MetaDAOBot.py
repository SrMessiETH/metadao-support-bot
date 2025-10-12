import json
import logging
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
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
            f"Category: {context.user_data.get('category')}\n"
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
    
    logger.info(f"[v0] Button handler called for callback_data: {query.data}")
    logger.info(f"[v0] About to call query.answer()")
    
    try:
        await query.answer()
        logger.info(f"[v0] query.answer() completed successfully")
    except Exception as e:
        logger.error(f"[v0] query.answer() failed: {e}")
        import traceback
        traceback.print_exc()
    
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

    # Handle main categories (excluding get_listed which is now a conversation)
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

    if data == 'support_request':
        await query.edit_message_text("To submit a support request, please provide your full name:")
        context.user_data['support_active'] = True
        return NAME

# Support conversation handlers
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

    # Log to sheets
    log_request(name, email, question, 'Support Request')

    # Forward to support if enabled
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
    """Start the get listed conversation"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("Yes, I want to get listed", callback_data='get_listed_yes')],
        [InlineKeyboardButton("Back to Main Menu", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        "Would you like to submit your project to get listed on MetaDAO?\n\n"
        "You'll need to provide detailed information about your project including:\n"
        "• Project name and description\n"
        "• Token details\n"
        "• Fundraising information\n"
        "• Performance package configuration\n"
        "• Intellectual property\n\n"
        "This will take about 5-10 minutes to complete.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['get_listed_active'] = True
    return GET_LISTED_CONFIRM

async def get_listed_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle confirmation to proceed with get listed"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'main_menu':
        context.user_data.clear()
        await query.edit_message_text("Main Menu:", reply_markup=main_inline_keyboard())
        return ConversationHandler.END
    
    await query.edit_message_text(
        "Great! Let's start with your project details.\n\n"
        "Please provide your project name and a short description (1-2 sentences):\n\n"
        "Example: Omnipair - A decentralized exchange aggregator that finds the best prices across multiple DEXs."
    )
    return PROJECT_NAME_SHORT

async def get_project_name_short(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get project name and short description"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['project_name_short'] = update.message.text
    await update.message.reply_text(
        "Thank you! Now please provide a longer, more detailed description of your project.\n\n"
        "Explain what your project does, why it's valuable, and why someone should want to participate in its upside.\n"
        "(This will be displayed on the MetaDAO website)"
    )
    return PROJECT_DESC_LONG

async def get_project_desc_long(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get long project description"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['project_desc_long'] = update.message.text
    await update.message.reply_text(
        "Excellent! Now let's get your token details.\n\n"
        "What is your token name?\n\n"
        "Example: Omnipair"
    )
    return TOKEN_NAME

async def get_token_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get token name"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['token_name'] = update.message.text
    await update.message.reply_text(
        "What is your token ticker?\n\n"
        "Example: OMFG\n\n"
        "We recommend using memorable and unique tickers."
    )
    return TOKEN_TICKER

async def get_token_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get token ticker"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['token_ticker'] = update.message.text
    await update.message.reply_text(
        "Please provide the URL for your project image.\n\n"
        "This will be displayed on the MetaDAO site and trading venues like Jupiter.\n\n"
        "Example: https://example.com/project-logo.png"
    )
    return PROJECT_IMAGE

async def get_project_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get project image URL"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['project_image'] = update.message.text
    await update.message.reply_text(
        "Do you have a different token image, or is it the same as your project image?\n\n"
        "If it's the same, type 'same'\n"
        "If different, provide the URL for your token image."
    )
    return TOKEN_IMAGE

async def get_token_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get token image URL"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    text = update.message.text
    if text.lower() == 'same':
        context.user_data['token_image'] = context.user_data['project_image']
    else:
        context.user_data['token_image'] = text
    
    await update.message.reply_text(
        "Now let's discuss fundraising details.\n\n"
        "What is your minimum raise amount?\n\n"
        "This is how much your project needs for you to proceed. If the project raises less than this amount, the sale will be refunded.\n\n"
        "Example: $750,000"
    )
    return MIN_RAISE

async def get_min_raise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get minimum raise amount"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['min_raise'] = update.message.text
    await update.message.reply_text(
        "What is your monthly team budget?\n\n"
        "This is how much the team needs every month from the treasury to operate normally. "
        "Spends larger than this need to be approved by governance.\n\n"
        "Note: This can be no larger than 1/6th of the minimum raise amount.\n\n"
        "Example: $50,000"
    )
    return MONTHLY_BUDGET

async def get_monthly_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get monthly team budget"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['monthly_budget'] = update.message.text
    await update.message.reply_text(
        "Performance Package Configuration:\n\n"
        "After the ICO, 10M tokens go to sale participants and 5M tokens go to liquidity. "
        "You can choose for up to 15M tokens to be pre-allocated to a performance package.\n\n"
        "This package is split into 5 equal tranches, unlocking at 2x, 4x, 8x, 16x, and 32x the ICO price.\n\n"
        "How many tokens do you want to allocate to the performance package? (0 to 15,000,000)\n\n"
        "Example: 10000000"
    )
    return PERFORMANCE_PACKAGE

async def get_performance_package(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get performance package allocation"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['performance_package'] = update.message.text
    await update.message.reply_text(
        "What is the minimum unlock time for the performance package?\n\n"
        "This must be at least 18 months from ICO date but can be longer if you wish.\n\n"
        "Example: 24 months"
    )
    return PERFORMANCE_UNLOCK_TIME

async def get_performance_unlock_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get performance package unlock time"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['performance_unlock_time'] = update.message.text
    await update.message.reply_text(
        "Finally, please list the intellectual properties that the founder(s) will give up to the project's entity.\n\n"
        "This includes but is not limited to:\n"
        "• Domain names\n"
        "• Software/code repositories\n"
        "• Social media accounts\n"
        "• Trademarks\n\n"
        "Please list all intellectual property:"
    )
    return INTELLECTUAL_PROPERTY

_processing_updates = set()

async def get_intellectual_property(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get intellectual property list and complete submission"""
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['intellectual_property'] = update.message.text
    
    user_id = update.effective_user.id
    submission_key = f"get_listed_{user_id}_{context.user_data.get('token_ticker', '')}"
    
    if submission_key in _processing_updates:
        logger.warning(f"Duplicate submission detected for {submission_key}, skipping")
        await update.message.reply_text(
            "This submission has already been processed.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    _processing_updates.add(submission_key)
    
    # Validate all fields are filled
    required_fields = [
        'project_name_short', 'project_desc_long', 'token_name', 'token_ticker',
        'project_image', 'token_image', 'min_raise', 'monthly_budget',
        'performance_package', 'performance_unlock_time', 'intellectual_property'
    ]
    
    missing_fields = [field for field in required_fields if not context.user_data.get(field)]
    
    if missing_fields:
        _processing_updates.discard(submission_key)
        await update.message.reply_text(
            f"Error: The following fields are missing: {', '.join(missing_fields)}\n\n"
            "Please start over by typing /cancel and then selecting Get Listed again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
        )
        context.user_data.clear()
        return ConversationHandler.END
    
    # Prepare data for logging
    extra_data = {
        'project_name_short': context.user_data['project_name_short'],
        'project_desc_long': context.user_data['project_desc_long'],
        'token_name': context.user_data['token_name'],
        'token_ticker': context.user_data['token_ticker'],
        'project_image': context.user_data['project_image'],
        'token_image': context.user_data['token_image'],
        'min_raise': context.user_data['min_raise'],
        'monthly_budget': context.user_data['monthly_budget'],
        'performance_package': context.user_data['performance_package'],
        'performance_unlock_time': context.user_data['performance_unlock_time'],
        'intellectual_property': context.user_data['intellectual_property']
    }
    
    # Log to Google Sheets
    user = update.effective_user
    log_request(
        name=user.first_name or 'Unknown',
        email=f"@{user.username}" if user.username else f"User ID: {user.id}",
        question='',
        category='Get Listed Submission',
        extra_data=extra_data
    )
    
    # Send confirmation
    await update.message.reply_text(
        "Thank you for your submission! 🎉\n\n"
        "Your project listing request has been received and will be reviewed by the MetaDAO team.\n\n"
        "We'll contact you soon with next steps.\n\n"
        f"Project: {context.user_data['token_name']} ({context.user_data['token_ticker']})",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
    )
    
    asyncio.create_task(_cleanup_submission_key(submission_key))
    
    context.user_data.clear()
    context.user_data['get_listed_active'] = False
    return ConversationHandler.END

async def _cleanup_submission_key(key: str):
    """Remove submission key from tracking after 60 seconds"""
    await asyncio.sleep(60)
    _processing_updates.discard(key)
    logger.info(f"Cleaned up submission key: {key}")

async def get_listed_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel get listed conversation"""
    if context.user_data.get('get_listed_active'):
        context.user_data.clear()
        await update.message.reply_text(
            "Get listed submission cancelled.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END
    return ConversationHandler.END

# Text message handler for non-support
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != 'private':
        return
    text = update.message.text.lower()
    if context.user_data.get('support_active'):
        return

    if text in ['start', '/start']:
        await start_handler(update, context)
        return

    ca_variants = ["ca"]
    if text in ca_variants:
        # Remove any reply keyboard
        await update.message.reply_text(META_CA, reply_markup=ReplyKeyboardRemove())
        return

    # Remove any reply keyboard
    await update.message.reply_text(
        "Please use the inline menu to select an option.",
        reply_markup=ReplyKeyboardRemove()
    )
    await update.message.reply_text(
        "Main Menu:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Main Menu", callback_data='main_menu')]])
    )

# CA handler for groups only
async def handle_ca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == 'private':
        return
    ca_variants = ["CA", "ca", "Ca"]
    if update.message.text in ca_variants:
        await update.message.reply_text(META_CA, reply_markup=ReplyKeyboardRemove())

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

# Add handlers
application.add_handler(CommandHandler('start', start_handler))
application.add_handler(CommandHandler('help', help_handler))
application.add_handler(CommandHandler('cancel', cancel_handler))
application.add_handler(get_listed_conv_handler)
application.add_handler(CallbackQueryHandler(button_handler))
application.add_handler(MessageHandler(filters.Regex(r'^(CA|ca|Ca)$'), handle_ca))
application.add_handler(conv_handler)
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
application.add_handler(MessageHandler(filters.COMMAND, text_handler))

_initialized = False

async def ensure_initialized():
    """Ensure application is initialized before processing updates"""
    global _initialized
    if not _initialized:
        await application.initialize()
        await application.bot.initialize()
        from telegram import BotCommand
        commands = [
            BotCommand("start", "Start the bot and show main menu"),
            BotCommand("help", "Show help information"),
            BotCommand("cancel", "Cancel current operation")
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands menu set successfully")
        _initialized = True

try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.initialize())
    loop.run_until_complete(application.bot.initialize())
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Start the bot and show main menu"),
        BotCommand("help", "Show help information"),
        BotCommand("cancel", "Cancel current operation")
    ]
    loop.run_until_complete(application.bot.set_my_commands(commands))
    logger.info("Bot commands menu registered successfully")
    try:
        loop.run_until_complete(application.bot.get_me())
        logger.info("Bot HTTP client warmed up successfully")
    except Exception as e:
        logger.warning(f"Could not warm up bot HTTP client: {e}")
    loop.close()
    _initialized = True
    logger.info("Application and bot pre-initialized successfully")
except Exception as e:
    logger.warning(f"Could not pre-initialize application: {e}")
    _initialized = False

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle POST requests from Telegram webhook"""
        try:
            logger.info("[v0] Webhook POST request received")
            
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            logger.info(f"[v0] Request body length: {content_length}")
            
            # Parse JSON update from Telegram
            update_dict = json.loads(body.decode('utf-8'))
            logger.info(f"[v0] Parsed update: {update_dict}")
            
            update_id = update_dict.get('update_id')
            if update_id and update_id in _processing_updates:
                logger.warning(f"Duplicate update {update_id} detected, skipping")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({'ok': True, 'skipped': 'duplicate'})
                self.wfile.write(response.encode('utf-8'))
                return
            
            if update_id:
                _processing_updates.add(update_id)
            
            logger.info(f"[v0] Processing update {update_id}")
            
            # Create Update object and process
            update = Update.de_json(update_dict, application.bot)
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if not _initialized:
                    loop.run_until_complete(ensure_initialized())
                loop.run_until_complete(application.process_update(update))
                logger.info("[v0] Update processed successfully")
                
                pending = asyncio.all_tasks(loop)
                if pending:
                    logger.info(f"[v0] Waiting for {len(pending)} pending tasks to complete")
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    logger.info("[v0] All pending tasks completed")
            finally:
                loop.close()
                if update_id:
                    asyncio.create_task(_cleanup_update_id(update_id))
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({'ok': True})
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"[v0] Error processing webhook: {e}")
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({'ok': False, 'error': str(e)})
            self.wfile.write(response.encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests for health check"""
        logger.info("[v0] Health check GET request received")
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'MetaDAO Bot is running!')

async def _cleanup_update_id(update_id: int):
    """Remove update ID from tracking after 30 seconds"""
    await asyncio.sleep(30)
    _processing_updates.discard(update_id)
    logger.info(f"Cleaned up update ID: {update_id}")
