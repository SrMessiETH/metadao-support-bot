import json
import logging
from telegram.ext import Application, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
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
SUPPORT_CATEGORY, NAME, EMAIL, QUESTION = range(4)

GET_LISTED_CONFIRM, GET_LISTED_NAME, GET_LISTED_EMAIL, GET_LISTED_PROJECT = range(12, 16)

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
        [InlineKeyboardButton("🚀 Get Listed", callback_data='get_listed'), InlineKeyboardButton("📅 ICOs & Calendar", callback_data='icos')],
        [InlineKeyboardButton("📚 How Launches Work", callback_data='how_launches_work')],
        [InlineKeyboardButton("🎯 Introduction to Futarchy", callback_data='futarchy_intro')],
        [InlineKeyboardButton("📊 Proposals", callback_data='proposals')],
        [InlineKeyboardButton("💼 For Entrepreneurs", callback_data='entrepreneurs')],
        [InlineKeyboardButton("💰 For Investors", callback_data='investors')],
        [InlineKeyboardButton("💬 Support Request", callback_data='support_request')]
    ]
    return InlineKeyboardMarkup(keyboard)

def proposals_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("✍️ Creating Proposals", callback_data='proposals_create')],
        [InlineKeyboardButton("📈 Trading Proposals", callback_data='proposals_trade')],
        [InlineKeyboardButton("✅ Finalizing Proposals", callback_data='proposals_finalize')],
        [InlineKeyboardButton("📊 View Markets", url='https://v1.metadao.fi/markets')],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_sheets_client(sheet_name='Support Requests'):
    try:
        if not GOOGLE_CREDENTIALS:
            return None
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(GOOGLE_CREDENTIALS, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open(SHEET_NAME)
        
        # Try to get the sheet by name, create if it doesn't exist
        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Sheet '{sheet_name}' not found, creating it...")
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=50)
            
            if sheet_name == 'Support Requests':
                # Horizontal layout with headers for Support Requests
                headers = ['Timestamp', 'Name', 'Email', 'Question', 'Category', 'Subcategory']
                sheet.append_row(headers)
                logger.info(f"Created sheet '{sheet_name}' with horizontal layout")
            else:
                # Vertical layout for Get Listed - no initial headers needed
                logger.info(f"Created sheet '{sheet_name}' with vertical layout")
        
        return sheet
    except Exception as e:
        logger.error(f"Error setting up Google Sheets: {e}")
        return None

def log_request(name, email, question, category, subcategory=None, extra_data=None):
    sheet_name = 'Get Listed' if category == 'Get Listed' else 'Support Requests'
    sheet = get_sheets_client(sheet_name)
    
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if category == 'Support Request':
            # Horizontal layout - append one row
            row = [timestamp, name, email, question, category, subcategory or '']
            sheet.append_row(row)
            logger.info(f"Request logged to '{sheet_name}' sheet: {name}, {email}, {category}, {subcategory}")
        else:
            # Vertical layout for Get Listed - append to next available column
            all_values = sheet.get_all_values()
            
            # Find the next empty column (columns come in pairs: field name, value)
            next_col = 1  # Start at column A
            if all_values and len(all_values) > 0:
                first_row = all_values[0]
                filled_cols = len([cell for cell in first_row if cell.strip()])
                next_col = filled_cols + 1
            
            if extra_data:
                fields = [
                    ('Timestamp', timestamp),
                    ('Name', name),
                    ('Email', email),
                    ('Project Name', extra_data.get('project_name', '')),
                    ('Category', category)
                ]
            else:
                fields = [
                    ('Timestamp', timestamp),
                    ('Name', name),
                    ('Email', email),
                    ('Question', question),
                    ('Category', category)
                ]
            
            # Write field names in column next_col and values in column next_col+1
            for row_idx, (field_name, field_value) in enumerate(fields, start=1):
                sheet.update_cell(row_idx, next_col, field_name)
                sheet.update_cell(row_idx, next_col + 1, field_value)
            
            logger.info(f"Request logged vertically to '{sheet_name}' sheet in columns {next_col}-{next_col+1}: {name}, {category}")
    else:
        logger.warning("Could not log to Google Sheets - client not available")

async def forward_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if SUPPORT_CHAT_ID:
        user = update.effective_user
        username = user.username if user.username else 'no username'
        chat_type = 'Group' if update.effective_chat.type != 'private' else 'Private'
        message_text = (
            f"New support request from {context.user_data.get('name')} ({username}):\n"
            f"Email: {context.user_data.get('email')}\n"
            f"Question: {context.user_data.get('question')}\n"
            f"Subcategory: {context.user_data.get('subcategory', 'N/A')}\n"
            f"Category: {context.user_data.get('category', 'General')}\n"
            f"User ID: {user.id}\n"
            f"Chat Type: {chat_type}"
        )
        await context.bot.send_message(chat_id=SUPPORT_CHAT_ID, text=message_text)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != 'private':
        return
    user = update.effective_user
    welcome_text = (
        f"👋 *Welcome to MetaDAO, {user.first_name}!*\n\n"
        "I'm your MetaDAO assistant, here to help you navigate our platform.\n\n"
        "What I can help you with:\n"
        "📅 View upcoming ICOs and calendar\n"
        "📚 Learn about our launch process\n"
        "🎯 Understand futarchy governance\n"
        "💬 Submit support requests\n\n"
        "📖 *Quick Links:*\n"
        "• Documentation: [docs.metadao.fi](https://docs.metadao.fi/)\n"
        "• Website: [metadao.fi](https://metadao.fi)\n\n"
        "👇 *Select an option below to get started:*"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=main_inline_keyboard(),
        disable_web_page_preview=True
    )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != 'private':
        return
    help_text = (
        "🤖 *MetaDAO Support Bot Help*\n\n"
        "*Available Commands:*\n"
        "/start - Start the bot and show main menu\n"
        "/help - Show this help message\n"
        "/cancel - Cancel current operation\n"
        "/ca - Get META contract address\n"
        "/web - Get MetaDAO website link\n"
        "/docs - Get documentation link\n"
        "/icos - Get calendar and ICOs link\n"
        "/markets - View active markets\n\n"
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

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.type != 'private':
        return ConversationHandler.END
    
    # Clear any active support request
    if context.user_data.get('support_active'):
        context.user_data.clear()
        await update.message.reply_text(
            "❌ *Operation Cancelled*\n\nYour support request has been cancelled. No worries, you can start again anytime!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "ℹ️ No active operation to cancel.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != 'private':
        await update.callback_query.answer()
        return
    query = update.callback_query
    
    await query.answer()
    
    data = query.data
    chat_id = query.message.chat_id

    if data == 'main_menu':
        await query.edit_message_text(
            text="🏠 *Main Menu*\n\nSelect an option below:",
            parse_mode='Markdown',
            reply_markup=main_inline_keyboard()
        )
        return

    if data == 'proposals':
        await query.edit_message_text(
            text="📊 *Proposals*\n\nLearn about creating, trading, and finalizing proposals:\n\n🔗 [View Active Markets](https://v1.metadao.fi/markets)",
            parse_mode='Markdown',
            reply_markup=proposals_inline_keyboard(),
            disable_web_page_preview=True
        )
        return

    # Handle sub proposals
    sub_map = {
        'proposals_create': ('✍️ Creating Proposals', 'Learn how to create and submit proposals'),
        'proposals_trade': ('📈 Trading Proposals', 'Discover how to trade on proposal markets'),
        'proposals_finalize': ('✅ Finalizing Proposals', 'Understand the finalization process'),
    }
    if data in sub_map:
        title, description = sub_map[data]
        link = RESOURCE_LINKS[data]
        await query.edit_message_text(
            text=f"*{title}*\n\n{description}\n\n🔗 [View Documentation]({link})",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]]),
            disable_web_page_preview=True
        )
        return

    # Handle main categories (excluding support_request which is a conversation)
    category_map = {
        'icos': ('📅 ICOs & Calendar', 'View all upcoming and active ICOs'),
        'how_launches_work': ('📚 How Launches Work', 'Learn about the MetaDAO launch process'),
        'futarchy_intro': ('🎯 Introduction to Futarchy', 'Understand futarchy governance'),
        'entrepreneurs': ('💼 For Entrepreneurs', 'Benefits and resources for project founders'),
        'investors': ('💰 For Investors', 'Investment opportunities and benefits'),
    }
    if data in category_map:
        title, description = category_map[data]
        link = RESOURCE_LINKS[data]
        await query.edit_message_text(
            text=f"*{title}*\n\n{description}\n\n🔗 [Learn More]({link})",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]]),
            disable_web_page_preview=True
        )
        return

async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💰 Refunds", callback_data='support_refunds')],
        [InlineKeyboardButton("🐛 Bugs", callback_data='support_bugs')],
        [InlineKeyboardButton("💡 Suggestions", callback_data='support_suggestions')],
        [InlineKeyboardButton("🔧 Technical Issues", callback_data='support_technical')],
        [InlineKeyboardButton("👤 Account Issues", callback_data='support_account')],
        [InlineKeyboardButton("❓ General Inquiry", callback_data='support_general')],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        "💬 *Support Request*\n\n"
        "Please select the category that best describes your request:\n\n"
        "💰 *Refunds* - Payment and refund inquiries\n"
        "🐛 *Bugs* - Report technical bugs or errors\n"
        "💡 *Suggestions* - Feature requests and improvements\n"
        "🔧 *Technical Issues* - General technical problems\n"
        "👤 *Account Issues* - Account-related concerns\n"
        "❓ *General Inquiry* - Other questions",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['support_active'] = True
    return SUPPORT_CATEGORY

async def support_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    # Map callback data to subcategory names
    subcategory_map = {
        'support_refunds': 'Refunds',
        'support_bugs': 'Bugs',
        'support_suggestions': 'Suggestions',
        'support_technical': 'Technical Issues',
        'support_account': 'Account Issues',
        'support_general': 'General Inquiry'
    }
    
    subcategory = subcategory_map.get(query.data, 'General Inquiry')
    context.user_data['subcategory'] = subcategory
    
    # Get emoji for the selected category
    emoji_map = {
        'Refunds': '💰',
        'Bugs': '🐛',
        'Suggestions': '💡',
        'Technical Issues': '🔧',
        'Account Issues': '👤',
        'General Inquiry': '❓'
    }
    emoji = emoji_map.get(subcategory, '💬')
    
    await query.edit_message_text(
        f"{emoji} *Support Request: {subcategory}*\n\n"
        "Great! I'll help you submit your request to our team.\n\n"
        "📝 *Step 1 of 3:* Please provide your full name:",
        parse_mode='Markdown'
    )
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    context.user_data['name'] = update.message.text
    await update.message.reply_text(
        f"✅ Got it, *{update.message.text}*!\n\n"
        "📧 *Step 2 of 3:* Please provide your email address so we can get back to you:",
        parse_mode='Markdown'
    )
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    context.user_data['email'] = update.message.text
    
    subcategory = context.user_data.get('subcategory', 'General Inquiry')
    
    await update.message.reply_text(
        "✅ Perfect!\n\n"
        f"📝 *Step 3 of 3:* Please describe your *{subcategory.lower()}* in detail:",
        parse_mode='Markdown'
    )
    return QUESTION

async def get_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('support_active'):
        return ConversationHandler.END
    question = update.message.text
    context.user_data['question'] = question
    context.user_data['category'] = 'Support Request'
    name = context.user_data['name']
    email = context.user_data['email']
    subcategory = context.user_data.get('subcategory', 'General Inquiry')

    log_request(name, email, question, 'Support Request', subcategory=subcategory)
    await forward_to_support(update, context)

    response = (
        "✅ *Request Submitted Successfully!*\n\n"
        "Thank you for reaching out! Our support team has received your request and will review it shortly.\n\n"
        "📧 We'll get back to you via email at:\n"
        f"`{email}`\n\n"
        "⏱️ *Expected response time:* 24-48 hours\n\n"
        "Need anything else? Feel free to explore the menu below!"
    )

    await update.message.reply_text(
        response,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]])
    )
    context.user_data.clear()
    context.user_data['support_active'] = False
    return ConversationHandler.END

async def ca_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🪙 *META Contract Address*\n\n"
        f"`{META_CA}`\n\n"
        "💡 Tap to copy the address above",
        parse_mode='Markdown'
    )

async def web_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌐 *MetaDAO Website*\n\n"
        f"Visit us at: {RESOURCE_LINKS['website']}\n\n"
        "Explore our platform, learn about futarchy, and discover upcoming projects!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def docs_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📚 *MetaDAO Documentation*\n\n"
        f"Access our docs at: {RESOURCE_LINKS['docs']}\n\n"
        "Find guides, tutorials, and detailed information about our platform.",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def icos_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📅 *MetaDAO Calendar & ICOs*\n\n"
        f"View all upcoming ICOs: {RESOURCE_LINKS['icos']}\n\n"
        "Stay updated on the latest project launches and investment opportunities!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def markets_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📊 *MetaDAO Markets*\n\n"
        "View active markets: https://v1.metadao.fi/markets\n\n"
        "Participate in governance by trading on proposal markets!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def twitter_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🐦 *Follow MetaDAO on X (Twitter)*\n\n"
        "Stay updated with the latest news and announcements:\n"
        "https://x.com/MetaDAOProject\n\n"
        "Join our community and be part of the conversation!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def telegram_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "💬 *Join MetaDAO on Telegram*\n\n"
        "Connect with our community:\n"
        "https://t.me/+WXdyUMb4-M9lNmNh\n\n"
        "Ask questions, share ideas, and stay updated!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def discord_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "💬 *Join MetaDAO on Discord*\n\n"
        "Connect with our community:\n"
        "https://discord.com/invite/metadao\n\n"
        "Participate in discussions and get support!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def youtube_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📺 *MetaDAO on YouTube*\n\n"
        "Watch tutorials, updates, and more:\n"
        "https://www.youtube.com/@metaDAOproject\n\n"
        "Subscribe to stay informed!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def blog_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📝 *MetaDAO Blog*\n\n"
        "Read our latest articles and updates:\n"
        "https://blog.metadao.fi/\n\n"
        "Deep dives, announcements, and insights!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def futarchyamm_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📊 *Futarchy AMM Metrics*\n\n"
        "View detailed analytics and metrics:\n"
        "https://dune.com/jacktheguy/futarchy-amm-metrics\n\n"
        "Track performance and market data!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def github_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "💻 *MetaDAO on GitHub*\n\n"
        "Explore our open-source code:\n"
        "https://github.com/metaDAOproject\n\n"
        "Contribute, review, and build with us!",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def handle_ca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == 'private':
        return
    ca_variants = ["CA", "ca", "Ca"]
    if update.message.text in ca_variants:
        await update.message.reply_text(
            f"🪙 *META Contract Address*\n\n`{META_CA}`\n\n💡 Tap to copy",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass

async def get_listed_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, let's get started!", callback_data='get_listed_yes')],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        "🚀 *Get Your Project Listed on MetaDAO*\n\n"
        "To get listed, we'll need some basic information about you and your project.\n\n"
        "⏱️ *Time required:* ~2 minutes\n\n"
        "Ready to begin?",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GET_LISTED_CONFIRM

async def get_listed_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    if query.data == 'get_listed_yes':
        context.user_data['get_listed_active'] = True
        await query.edit_message_text(
            "📝 *Step 1 of 3: Your Name*\n\n"
            "Please provide your full name:",
            parse_mode='Markdown'
        )
        return GET_LISTED_NAME
    else:
        await query.edit_message_text(
            "👍 No problem! Feel free to come back anytime.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END

async def get_listed_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['name'] = update.message.text
    await update.message.reply_text(
        f"✅ Got it, *{update.message.text}*!\n\n"
        "📧 *Step 2 of 3:* Please provide your email address:",
        parse_mode='Markdown'
    )
    return GET_LISTED_EMAIL

async def get_listed_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['email'] = update.message.text
    await update.message.reply_text(
        "✅ Perfect!\n\n"
        "🚀 *Step 3 of 3:* What is your project name?",
        parse_mode='Markdown'
    )
    return GET_LISTED_PROJECT

async def get_listed_project(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    
    context.user_data['project_name'] = update.message.text
    
    extra_data = {
        'project_name': context.user_data.get('project_name', ''),
    }
    
    # Log to Google Sheets
    log_request(
        context.user_data['name'],
        context.user_data['email'],
        None,
        'Get Listed',
        extra_data=extra_data
    )
    
    success_message = (
        "🎉 *Submission Complete!*\n\n"
        "Congratulations! Your project listing request has been submitted successfully.\n\n"
        "*What happens next:*\n"
        "1️⃣ Our team will review your submission\n"
        "2️⃣ We'll reach out to gather more details about your project\n"
        "3️⃣ You'll receive a response within 3-5 business days\n\n"
        "📧 We'll contact you via email at the address you provided.\n\n"
        "Thank you for choosing MetaDAO! 🚀"
    )
    
    await update.message.reply_text(
        success_message,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]])
    )
    
    context.user_data.clear()
    context.user_data['get_listed_active'] = False
    return ConversationHandler.END

async def get_listed_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if context.user_data.get('get_listed_active'):
        context.user_data.clear()
        await update.message.reply_text(
            "❌ *Listing Cancelled*\n\nYour get listed submission has been cancelled. You can restart anytime!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END
    return ConversationHandler.END

_initialized = False
_application = None
_event_loop = None

def get_event_loop():
    """Get or create a persistent event loop for the serverless instance"""
    global _event_loop
    if _event_loop is None or _event_loop.is_closed():
        _event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_event_loop)
        logger.info("Created new persistent event loop")
    return _event_loop

async def get_application():
    """Get or create application instance with proper event loop binding"""
    global _application, _initialized
    
    if _application is None:
        _application = Application.builder().token(BOT_TOKEN).build()
        
        get_listed_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(get_listed_start, pattern='^get_listed$')],
            states={
                GET_LISTED_CONFIRM: [CallbackQueryHandler(get_listed_confirm)],
                GET_LISTED_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_listed_name)],
                GET_LISTED_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_listed_email)],
                GET_LISTED_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_listed_project)],
            },
            fallbacks=[CommandHandler('cancel', get_listed_cancel, filters=filters.ChatType.PRIVATE)],
        )

        # Support conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(support_start, pattern='^support_request$')],
            states={
                SUPPORT_CATEGORY: [CallbackQueryHandler(support_category_selected, pattern='^support_')],
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
                QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_question)],
            },
            fallbacks=[CommandHandler('cancel', cancel_handler, filters=filters.ChatType.PRIVATE)],
        )

        _application.add_handler(CommandHandler('start', start_handler, filters=filters.ChatType.PRIVATE))
        _application.add_handler(CommandHandler('help', help_handler, filters=filters.ChatType.PRIVATE))
        _application.add_handler(CommandHandler('cancel', cancel_handler, filters=filters.ChatType.PRIVATE))
        
        _application.add_handler(CommandHandler('ca', ca_command_handler))
        _application.add_handler(CommandHandler('web', web_command_handler))
        _application.add_handler(CommandHandler('docs', docs_command_handler))
        _application.add_handler(CommandHandler('icos', icos_command_handler))
        _application.add_handler(CommandHandler('markets', markets_command_handler))
        _application.add_handler(CommandHandler('twitter', twitter_command_handler))
        
        _application.add_handler(CommandHandler('telegram', telegram_command_handler))
        _application.add_handler(CommandHandler('discord', discord_command_handler))
        _application.add_handler(CommandHandler('youtube', youtube_command_handler))
        _application.add_handler(CommandHandler('blog', blog_command_handler))
        _application.add_handler(CommandHandler('futarchyamm', futarchyamm_command_handler))
        _application.add_handler(CommandHandler('github', github_command_handler))
        
        _application.add_handler(get_listed_conv_handler)
        _application.add_handler(conv_handler)
        _application.add_handler(CallbackQueryHandler(button_handler, pattern='^(?!get_listed$|support_request$)'))
        _application.add_handler(MessageHandler(filters.Regex(r'^(CA|ca|Ca)$'), handle_ca))
        _application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
        _application.add_handler(MessageHandler(filters.COMMAND, text_handler))
    
    if not _initialized:
        await _application.initialize()
        await _application.bot.initialize()
        
        await _application.bot.delete_my_commands()
        
        # Set commands for private chats only (conversation commands)
        private_commands = [
            BotCommand("start", "Start the bot and show main menu"),
            BotCommand("help", "Show help information"),
            BotCommand("cancel", "Cancel current operation")
        ]
        await _application.bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        
        # Set commands for group chats only (info commands)
        group_commands = [
            BotCommand("ca", "Get META contract address"),
            BotCommand("web", "Get MetaDAO website link"),
            BotCommand("docs", "Get documentation link"),
            BotCommand("icos", "Get calendar and ICOs link"),
            BotCommand("markets", "View active markets"),
            BotCommand("twitter", "Follow us on Twitter/X"),
            BotCommand("telegram", "Join our Telegram community"),
            BotCommand("discord", "Join our Discord server"),
            BotCommand("youtube", "Subscribe to our YouTube"),
            BotCommand("blog", "Read our blog"),
            BotCommand("futarchyamm", "View AMM metrics"),
            BotCommand("github", "Explore our GitHub")
        ]
        await _application.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        
        logger.info("Bot commands configured: conversation commands for private chats only, info commands for groups only")
        _initialized = True
    
    return _application

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
            
            loop = get_event_loop()
            loop.run_until_complete(self._process_update_async(update_dict, update_id))
            
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            import traceback
            traceback.print_exc()
            
            # Remove from processing set on error
            if update_id and update_id in _processing_updates:
                _processing_updates.discard(update_id)
        finally:
            self.send_success_response()
    
    async def _process_update_async(self, update_dict: dict, update_id: int):
        """Async function to process update with proper cleanup"""
        try:
            app = await get_application()
            
            update = Update.de_json(update_dict, app.bot)
            
            # Process the update
            await app.process_update(update)
            logger.info("Update processed successfully")
            
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

logger.info("Module loaded successfully")
