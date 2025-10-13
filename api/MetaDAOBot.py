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
from groq import Groq

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for support conversation
SUPPORT_CATEGORY, NAME, EMAIL, QUESTION = range(4)

# States for get listed conversation
GET_LISTED_CONFIRM, PROJECT_NAME_SHORT, PROJECT_DESC_LONG, TOKEN_NAME, TOKEN_TICKER, PROJECT_IMAGE, TOKEN_IMAGE, MIN_RAISE, MONTHLY_BUDGET, PERFORMANCE_PACKAGE, PERFORMANCE_UNLOCK_TIME, INTELLECTUAL_PROPERTY = range(12, 24)

# Secrets from env vars
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env var is required")
SUPPORT_CHAT_ID = int(os.environ.get('SUPPORT_CHAT_ID', 0)) if os.environ.get('SUPPORT_CHAT_ID') else None
SHEET_NAME = os.environ.get('SHEET_NAME', 'MetaDAO Support Requests')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

# Google Sheets setup
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_CREDENTIALS')
if not GOOGLE_CREDENTIALS_JSON:
    logger.warning("GOOGLE_CREDENTIALS env var missing—Sheets logging disabled")
    GOOGLE_CREDENTIALS = None
else:
    GOOGLE_CREDENTIALS = json.loads(GOOGLE_CREDENTIALS_JSON)

groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    logger.info("Groq AI client initialized successfully")
else:
    logger.warning("GROQ_API_KEY not found - AI features will be disabled")

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
    'redeem_mtn': 'https://v1.metadao.fi/mtncapital/redeem',
    'redeem_meta': 'https://v1.metadao.fi/migration',
    'amm': 'https://dune.com/jacktheguy/futarchy-amm-metrics'
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

METADAO_KNOWLEDGE = """
MetaDAO is a decentralized autonomous organization that uses futarchy for governance and launches new crypto projects.

Key Information:
- META Token Contract: METAwkXcqyXKy1AtsSgJ8JiUHwGCafnZL38n3vYmeta
- Website: https://metadao.fi
- Documentation: https://docs.metadao.fi/
- ICO Calendar: https://www.idontbelieve.link

How Launches Work:
- Projects can get listed on MetaDAO to raise funds
- ICOs are conducted through the platform
- Investors can participate on initial token offerings (ICOs)
- Projects benefit from MetaDAO's infrastructure and community

Futarchy Governance:
- MetaDAO uses futarchy for decision-making
- Proposals are created and traded on prediction markets
- Markets determine which proposals pass based on expected outcomes
- TWAP (Time-Weighted Average Price) is used for finalization

For Entrepreneurs:
- Get your project listed on MetaDAO
- Access to funding and community
- Launch infrastructure and support
- Performance-based packages available

For Investors:
- Participate in early-stage initial coin offering
- Access to vetted projects
- Transparent governance through futarchy
- Multiple investment opportunities

Token Redemption:
- $MTN tokens can be redeemed at: https://v1.metadao.fi/mtncapital/redeem
- $META migration available at: https://v1.metadao.fi/migration

Support:
- Submit support requests through the bot
- Categories: Refunds, Bugs, Suggestions, Technical Issues, Account Issues, General Inquiry
"""

FAQ_DATABASE = {
    "futarchy": {
        "question": "What is futarchy?",
        "answer": "Futarchy is a governance system where decisions are made based on prediction markets. In MetaDAO, proposals are traded on markets, and the market prices determine which proposals pass. This creates a data-driven approach to governance where the wisdom of the crowd guides decision-making.",
        "related_links": [RESOURCE_LINKS['futarchy_intro'], RESOURCE_LINKS['proposals_create']]
    },
    "ico": {
        "question": "How do ICOs work on MetaDAO?",
        "answer": "MetaDAO hosts token sales for vetted projects. Projects get listed, set their fundraising goals, and investors can participate in the token sale. The platform provides infrastructure, community access, and transparent governance for all launches.",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['how_launches_work']]
    },
    "listing": {
        "question": "How do I get my project listed?",
        "answer": "To get listed, click the 'Get Listed' button and fill out the application form with your project details, token information, and financial requirements. Our team reviews submissions within 3-5 business days.",
        "related_links": [RESOURCE_LINKS['get_listed'], RESOURCE_LINKS['entrepreneurs']]
    },
    "meta_token": {
        "question": "What is the META token?",
        "answer": f"META is MetaDAO's governance token with contract address: {META_CA}. It's used for participating in futarchy governance and accessing platform benefits.",
        "related_links": [RESOURCE_LINKS['website'], RESOURCE_LINKS['docs']]
    },
    "proposals": {
        "question": "How do proposals work?",
        "answer": "Proposals are created, traded on prediction markets, and finalized based on TWAP (Time-Weighted Average Price). Users can create proposals, trade on their outcomes, and the market determines which proposals pass.",
        "related_links": [RESOURCE_LINKS['proposals_create'], RESOURCE_LINKS['proposals_trade'], RESOURCE_LINKS['proposals_finalize']]
    },
    "investing": {
        "question": "How can I invest in projects?",
        "answer": "Browse the ICO calendar to see upcoming and active token sales. Each project has detailed information about tokenomics, team, and goals. You can participate directly through the platform.",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['investors']]
    },
    "redemption": {
        "question": "How do I redeem my tokens?",
        "answer": f"You can redeem $MTN tokens at {RESOURCE_LINKS['redeem_mtn']} and migrate to the new $META contract at {RESOURCE_LINKS['redeem_meta']}.",
        "related_links": [RESOURCE_LINKS['redeem_mtn'], RESOURCE_LINKS['redeem_meta']]
    },
    "interact_ecosystem": {
        "question": "How to interact with the MetaDAO ecosystem?",
        "answer": "MetaDAO enables interaction primarily through trading conditional markets on project proposals, allowing you to bet on outcomes (pass/fail) and hedge/grow your portfolio.Key Steps:\n1. Monitor Proposals: Watch for proposals that gain enough stake, moving half the project's liquidity (e.g., from META/USDC spot) into pass and fail conditional markets for 3 days.\n2. Trade Conditionally: Buy/sell tokens in these markets like normal trades, but they revert if the proposal doesn't pass as expected.\n    ◦ Example (ORE Proposal): If you believe ORE hits $30 on passing (vs. $19 current), buy ORE in the pass market (e.g., $1,000 for 50 ORE at $20). On pass: You own them. On fail: Trade voids—no loss.\n3. Portfolio Strategies:\n    ◦ Bad Proposal (e.g., EXMPL founder siphons funds): Sell pass (overvalued if token tanks to $0) and buy fail (undervalued at ~11% profit potential on liquidation).\n    ◦ Good Proposal (e.g., XYZ adds revenue): Buy pass if undervalued (e.g., $110M vs. $150M fair value); sell if overvalued. Hedge by trading fail around fair value.Proposal Finalization:Outcomes use lagging TWAPs (time-weighted average prices) over the period to prevent manipulation—observations lag (e.g., max $5/min change from $500 baseline). Pass requires TWAP ≥1.5% above fail threshold by default.Trade via supported DEXs; start small to learn conditional reversion.",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['investors']]
    },
    "create_proposal_cost": {
        "question": "How much cost to make a proposal? Anyone can do it?",
        "answer": "Creating Proposals\nAnyone can create a proposal to a project. Proposals can:\n• Spend USDC from the treasury\n• Issue new tokens\n• Update token metadata\n• Increase or decrease the liquidity provided by the project’s treasuryOnce a proposal is created, holders must stake tokens on it for it to go live. By default, a proposal requires 50,000 tokens (5% of the ICO) staked on it for it to go live.Staking is purely to prevent spam and doesn’t have lockups or risk of slashing.There can only be one proposal live at once",
        "related_links": [RESOURCE_LINKS['proposals_create']]
    },
    "participate_icos": {
        "question": "How to participate on ICOS?",
        "answer": "MetaDAO ICOs protect investors from rugs via mechanistic (treasury) and legal (revenue) safeguards, letting you buy tokens with reduced risk.Key Protections:\n1. Mechanistic Treasury Protection:\n    ◦ All raised funds enter a market-governed treasury—no team control.\n    ◦ If rugged (team walks) or token price < book value, anyone can propose returning capital to holders.\n    ◦ Past Solana ICO Risks Avoided: Parrot ($85M raised, $72M rugged); UXD ($57M, $46M insiders took); Mango ($70M, founders suing over theft); Aurory ($108M, token -99.5%, funds vanished).\n2. Legal Revenue Protection:\n    ◦ Launch creates a legal entity for tokenholders.\n    ◦ Sue teams for revenue misappropriation or force IP transfer (e.g., domains/socials) to a new team.\n    ◦ Examples: Uniswap ($30M frontend fees to Labs, not holders); Unibot/Trojan ($206M fees kept by team).How to Participate:\n• Buy Tokens at Launch: Trade on MetaDAO's spot markets (e.g., NEW/USDC) during ICO—funds auto-secure in treasury.\n• Monitor & Vote: Stake/track proposals; use conditional markets to hedge (as in prior guides).\n• Start Small: Review project treasury/book value; exit via proposals if risks emerge.",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['investors']]
    },
    "futarchy_works": {
        "question": "How Futarchy works?",
        "answer": "Replacing token voting with market trading to make smarter, less manipulable decisions. Since November 2023, MetaDAO has run 96 proposals for 14 organizations, including Jito’s fee switch, Flash’s revenue-sharing for stakers, and all of Sanctum’s governance.Core Mechanism (TL;DR)\n• Trade Outcome Markets: For each proposal, traders buy/sell in two conditional markets: \"Token value if proposal passes\" vs. \"Token value if proposal fails.\"\n• Decide by Market Wisdom: Accept the proposal if the pass market prices higher (traders predict value increase); reject if fail prices higher (value decrease).\n• Invented by economist Robin Hanson, it lets markets aggregate info efficiently—no quorums or whale dominance.Why It's Better Than VotingMarkets historically outperform experts:\n• Elections: Prediction markets beat pollsters.\n• Weather: Orange juice futures outpredict government forecasts.\n• Disasters: In the 1986 Challenger explosion, markets pinpointed Morton-Thiokol’s O-rings as the cause in 16 minutes (stock plunged 12% vs. others flat/up), while government took 4 months.Why It MattersFutarchy hardens against rugs: ICO funds in market-governed treasuries can't be easily siphoned, as traders enforce accountability. As Umbra Research notes, it's \"trustless joint ownership.\" Per Kevin Heavey: \"Futarchy is such a radical improvement over majoritarian DAOs... any DAO still [using] token voting... is malicious or incompetent.\" Bind to futarchy for fair, market-driven ownership—or stick to traditional companies without tokens.",
        "related_links": [RESOURCE_LINKS['futarchy_intro'], RESOURCE_LINKS['proposals_create'], RESOURCE_LINKS['proposals_trade'], RESOURCE_LINKS['proposals_finalize']]
    },
    "nfts_related": {
        "question": "There are NFTs related?",
        "answer": "NO",
        "related_links": []
    },
    "what_is_metadao": {
        "question": "What is MetaDAO?",
        "answer": "MetaDAO is for founders who want to launch a token the right way. MetaDAO’s core principles are:\n• Fair launch early: instead of launching at a high FDV, projects launch early with high-float ICOs so that they can grow over time.\n• Real ownership and unruggability: the most important parts of the project - the intellectual property, the funds, and the ability to mint new tokens - are controlled by market-driven governance. This imbues the token with value and prevents malicious teams from rugging the treasury.\n• Pay-for-performance: insiders unlocks are proportional to the premium over the launch price. This keeps teams and participants aligned.While much of crypto concerns itself with how to maximally extract value over the short-term, MetaDAO is built from the ground up for long-term founders and their communities.",
        "related_links": [RESOURCE_LINKS['website'], RESOURCE_LINKS['docs']]
    },
    "get_listed": {
        "question": "How to get listed on MetaDAO?",
        "answer": "For the moment you need to talk with Proph3t or Kollan until we go permisionless",
        "related_links": [RESOURCE_LINKS['get_listed'], RESOURCE_LINKS['entrepreneurs']]
    },
    "discretionary_cap": {
        "question": "why discretionary cap?",
        "answer": "Why a discretionary cap? The purpose of the discretionary cap is to allow believers to participate while preventing projects from over-raising.If you look at other launch mechanisms, they all have issues:\n• Capped first-come-first-serve launches can be sniped\n• Capped pro rata launches can be gamed - if you see a sale is 2x oversubscribed, you may put up 2x the USDC, which makes it even more oversubscribed - which leads to poor UX for believers\n• Uncapped sales are more likely to over-raise\n• Dutch auctions are too complicated",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['how_launches_work']]
    },
    "sale_successful": {
        "question": "What happens when a sale is successful?",
        "answer": "If a sale is successful, the following happens:\n1. All USDC goes to a market-governed treasury.\n2. The authority to mint new tokens is transferred to the treasury.\n3. That treasury provides 20% of the USDC and 5M tokens to liquidity pools. In effect the project will buy back tokens below the ICO price and sell them above the ICO price.The team can then spend their configured monthly budget out of the treasury. To make larger spends or issue new tokens, they need to raise governance proposals.",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['how_launches_work']]
    },
    "sale_fails": {
        "question": "What happens when a sale fails to reach its minimum?",
        "answer": "When a project fails to reach its minimum, everyone is refunded their USDC back.",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['how_launches_work']]
    },
    "teams_incentivized": {
        "question": "How are teams incentivized?",
        "answer": "Teams can optionally decide to have up to 15M tokens (50% of initial supply) allocated to a price-based performance package.This package is split into 5 equal tranches: one that unlocks at 2x ICO price, one that unlocks at 4x ICO price, and so on for 8x, 16x, and 32x.The minimum unlock time on these tranches is at least 18 months from ICO date but can be extended by the founder.Teams may also forego this route and instead figure out incentives later, as MetaDAO did.",
        "related_links": [RESOURCE_LINKS['get_listed'], RESOURCE_LINKS['entrepreneurs']]
    },
    "why_metadao": {
        "question": "Why MetaDAO?",
        "answer": "Why Launch on MetaDAO?MetaDAO is the best for crypto-native businesses seeking sustainable capital without rugs or hype traps—framed by founders as \"a place... that doesn’t suck.\"Vs. Alternatives:\n• Standard VC/Token Path: Extracts from retail; locks teams into bad outcomes (hyped TGEs, vesting).\n• No Token: Solid for equity, but misses crypto alignment.\n• Bonding Curves (Pump/etc.): Low raises ($10k–$100k); no value, snipers, poor hiring.\n• Normal ICOs (Metaplex): Viable with trust/legal work, but rugs scare long-term holders.MetaDAO Perks:\n• Valuable, intrinsic tokens for quality holders.\n• Transparent treasury (no OTC doubts).\n• Early entry, mintable supply, believer community.\n• Minimal legal/smart contract hassle.Trade-offs: Token volatility. But \"if we were launching today, MetaDAO is the place.\" – Proph3t & Kollan House",
        "related_links": [RESOURCE_LINKS['website'], RESOURCE_LINKS['docs']]
    },
    "meta_token_does": {
        "question": "What the $META token does?",
        "answer": "Meta token is a blank slate. It’s one proposal away from being anything a passing proposal wants it to be.",
        "related_links": [RESOURCE_LINKS['website'], RESOURCE_LINKS['docs'], RESOURCE_LINKS['amm']]
    },
    "token_gate_icos": {
        "question": "Is there a reaosn why it isn’t being used to token gate ICOs, like $VIRTUAL does for virtual launches?",
        "answer": "You don’t have to own apple shares to buy an iphone",
        "related_links": []
    },
    "value_beyond_speculation": {
        "question": "What is the value behind the token beyond speculation?",
        "answer": "You all could raise a proposal to say pay us dividens or buy back or burn or…. The bigger thing here is that MetaDAO with its new AMM will be post revenue.",
         "related_links": [RESOURCE_LINKS['amm']]
    },
    "kyc_icos": {
        "question": "Need KYC for joining ICOs?",
        "answer": "No",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['how_launches_work']]
    },
    "hold_meta_icos": {
        "question": "Need to hold $META tokens to join ICOs?",
        "answer": "No",
        "related_links": [RESOURCE_LINKS['icos'], RESOURCE_LINKS['how_launches_work']]
    },
    "meta_holders_benefit": {
        "question": "Does $META holders benefit from ICOs like early access?",
        "answer": "NO. MetaDAO accrues fees from the AMM we’ve built which the token of the ICO goes into.",
         "related_links": [RESOURCE_LINKS['amm']]
    },
    "prevent_other_amm": {
        "question": "Does it prevent any other AMM or MMs from participating in making markets?",
        "answer": "It does not",
        "related_links": []
    },
    "amm_only_metadao": {
        "question": "Will MetaDAO’s AMM only be activated for MetaDAO projects?",
        "answer": "No, it is core to the use of the protocol now. So you have to put funds into the AMM ro tun the proposal",
         "related_links": [RESOURCE_LINKS['amm']]
    },
    "meta_liquidity_pool": {
        "question": "What is the address of the main liquidity pool for $META?",
        "answer": "https://solscan.io/token/AUvYM8tdeY8TDJ9SMjRntDuYUuTG3S1TfqurZ9dqW4NM",
        "related_links": ["https://solscan.io/token/AUvYM8tdeY8TDJ9SMjRntDuYUuTG3S1TfqurZ9dqW4NM"]
    },
    "meta_team_allocation": {
        "question": "Whats $META team allocation?",
        "answer": "0",
        "related_links": []
    },
    "voting_works": {
        "question": "How voting works?",
        "answer": "Check JITO youtube tutorial: https://www.youtube.com/watch?v=1LK8osvL4jg",
        "related_links": ["https://www.youtube.com/watch?v=1LK8osvL4jg"]
    }
}
def find_relevant_faq(user_message: str) -> dict:
    """
    Find the most relevant FAQ based on user message
    
    Args:
        user_message: User's question
    
    Returns:
        FAQ dict or None if no match found
    """
    message_lower = user_message.lower()
    
    # Keyword mapping to FAQ categories
    keyword_map = {
         "interact_ecosystem": ["interact", "ecosystem", "trade", "proposals", "conditional markets"],
         "create_proposal_cost": ["create proposal", "cost", "anyone", "stake"],
         "participate_icos": ["participate", "icos", "buy tokens", "protections"],
         "futarchy_works": ["futarchy works", "mechanism", "markets", "voting"],
         "nfts_related": ["nfts", "nft"],
         "what_is_metadao": ["what is metadao", "metadao", "principles"],
         "get_listed": ["get listed", "permissionless"],
         "discretionary_cap": ["discretionary cap", "cap", "over-raising"],
         "sale_successful": ["sale successful", "what happens", "treasury"],
         "sale_fails": ["sale fails", "refund", "minimum"],
         "teams_incentivized": ["teams incentivized", "performance package", "unlocks"],
         "why_metadao": ["why metadao", "launch", "alternatives"],
         "meta_token_does": ["meta token does", "blank slate"],
         "token_gate_icos": ["token gate", "virtual", "reason"],
         "value_beyond_speculation": ["value beyond speculation", "dividends", "buy back"],
         "kyc_icos": ["kyc", "joining icos"],
         "hold_meta_icos": ["hold meta", "join icos"],
         "meta_holders_benefit": ["meta holders benefit", "early access"],
         "prevent_other_amm": ["prevent amm", "making markets"],
         "amm_only_metadao": ["amm only metadao", "activated"],
         "meta_liquidity_pool": ["meta liquidity pool", "address"],
         "meta_team_allocation": ["meta team allocation"],
         "voting_works": ["voting works", "jito tutorial"]
}
    
    # Find matching FAQ
    for faq_key, keywords in keyword_map.items():
        if any(keyword in message_lower for keyword in keywords):
            return FAQ_DATABASE.get(faq_key)
    
    return None

async def faq_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /faq command to show common questions"""
    if update.effective_chat.type != 'private':
        return
    
    faq_text = (
        "❓ *Frequently Asked Questions*\n\n"
        "*Common Topics:*\n\n"
        "🎯 *Futarchy* - What is futarchy and how does it work?\n"
        "📅 *ICOs* - How do initial coin offerings work on MetaDAO?\n"
        "🚀 *Getting Listed* - How to list your project\n"
        "🪙 *META Token* - Information about the META token\n"
        "📊 *Proposals* - Creating and trading proposals\n"
        "💰 *Investing* - How to participate in ICOs\n"
        "🔄 *Redemption* - Redeeming and migrating tokens\n\n"
        "💡 *Tip:* Just ask me any question in plain English, and I'll help you find the answer!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎯 Futarchy", callback_data='faq_futarchy'), InlineKeyboardButton("📅 ICOs", callback_data='faq_ico')],
        [InlineKeyboardButton("🚀 Getting Listed", callback_data='faq_listing'), InlineKeyboardButton("🪙 META Token", callback_data='faq_meta_token')],
        [InlineKeyboardButton("📊 Proposals", callback_data='faq_proposals'), InlineKeyboardButton("💰 Investing", callback_data='faq_investing')],
        [InlineKeyboardButton("🔄 Redemption", callback_data='faq_redemption'), InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
    ]
    
    await update.message.reply_text(
        faq_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def faq_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle FAQ button callbacks"""
    query = update.callback_query
    await query.answer()
    
    # Extract FAQ key from callback data
    faq_key = query.data.replace('faq_', '')
    faq = FAQ_DATABASE.get(faq_key)
    
    if faq:
        # Format links
        links_text = "\n\n📚 *Related Resources:*\n"
        for link in faq['related_links']:
            links_text += f"• {link}\n"
        
        response_text = f"*{faq['question']}*\n\n{faq['answer']}{links_text}"
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to FAQs", callback_data='show_faq_menu')],
            [InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
        ]
        
        await query.edit_message_text(
            text=response_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )

async def show_faq_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show FAQ menu when user clicks back"""
    query = update.callback_query
    await query.answer()
    
    faq_text = (
        "❓ *Frequently Asked Questions*\n\n"
        "*Common Topics:*\n\n"
        "🎯 *Futarchy* - What is futarchy and how does it work?\n"
        "📅 *ICOs* - How do ICOs work on MetaDAO?\n"
        "🚀 *Getting Listed* - How to list your project\n"
        "🪙 *META Token* - Information about the META token\n"
        "📊 *Proposals* - Creating and trading proposals\n"
        "💰 *Investing* - How to participate in ICOs\n"
        "🔄 *Redemption* - Redeeming and migrating tokens\n\n"
        "💡 *Tip:* Just ask me any question in plain English, and I'll help you find the answer!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎯 Futarchy", callback_data='faq_futarchy'), InlineKeyboardButton("📅 ICOs", callback_data='faq_ico')],
        [InlineKeyboardButton("🚀 Getting Listed", callback_data='faq_listing'), InlineKeyboardButton("🪙 META Token", callback_data='faq_meta_token')],
        [InlineKeyboardButton("📊 Proposals", callback_data='faq_proposals'), InlineKeyboardButton("💰 Investing", callback_data='faq_investing')],
        [InlineKeyboardButton("🔄 Redemption", callback_data='faq_redemption'), InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        faq_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )


def main_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 Get Listed", callback_data='get_listed'), InlineKeyboardButton("📅 ICOs & Calendar", callback_data='icos')],
        [InlineKeyboardButton("📚 How Launches Work", callback_data='how_launches_work'), InlineKeyboardButton("🎯 Introduction to Futarchy", callback_data='futarchy_intro')],
        [InlineKeyboardButton("📊 Proposals", callback_data='proposals'), InlineKeyboardButton("💼 For Entrepreneurs", callback_data='entrepreneurs')],
        [InlineKeyboardButton("💰 For Investors", callback_data='investors'), InlineKeyboardButton("🎁 Redeem $MTN", callback_data='redeem_mtn')],
        [InlineKeyboardButton("🔄 Redeem $META", callback_data='redeem_meta'), InlineKeyboardButton("💬 Support Request", callback_data='support_request')]
    ]
    return InlineKeyboardMarkup(keyboard)

def proposals_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("✍️ Creating Proposals", callback_data='proposals_create')],
        [InlineKeyboardButton("📈 Trading Proposals", callback_data='proposals_trade')],
        [InlineKeyboardButton("✅ Finalizing Proposals", callback_data='proposals_finalize')],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Initialize Google Sheets client
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
                # Horizontal layout with headers
                headers = ['Timestamp', 'Name', 'Email', 'Question', 'Category', 'Subcategory']
                sheet.append_row(headers)
                logger.info(f"Created sheet '{sheet_name}' with horizontal layout")
            else:
                # Vertical layout - no initial headers needed
                logger.info(f"Created sheet '{sheet_name}' with vertical layout")
        
        return sheet
    except Exception as e:
        logger.error(f"Error setting up Google Sheets: {e}")
        return None

# Function to log request to Google Sheets
def log_request(name, email, question, category, subcategory=None, extra_data=None):
    sheet_name = 'Get Listed' if category == 'Get Listed' else 'Support Requests'
    sheet = get_sheets_client(sheet_name)
    
    if sheet:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if category == 'Support Request':
            # Horizontal layout - append one row
            row = [timestamp, name, email, question, category, subcategory or '']
            sheet.append_row(row)
            logger.info(f"Request logged horizontally to '{sheet_name}' sheet: {name}, {email}, {category}, {subcategory}")
        else:
            # Vertical layout for Get Listed - append to next available column
            # Get all values to find the next empty column
            all_values = sheet.get_all_values()
            
            # Find the next empty column (columns come in pairs: field name, value)
            next_col = 1  # Start at column A
            if all_values and len(all_values) > 0:
                # Find the first row and check how many columns are filled
                first_row = all_values[0]
                # Count non-empty cells to find next available column
                filled_cols = len([cell for cell in first_row if cell.strip()])
                next_col = filled_cols + 1
            
            # Prepare data to write vertically
            if extra_data:
                fields = [
                    ('Timestamp', timestamp),
                    ('Project Name', name),
                    ('Contact', email),
                    ('Category', category),
                    ('Project Name Short', extra_data.get('project_name_short', '')),
                    ('Project Description', extra_data.get('project_desc_long', '')),
                    ('Token Name', extra_data.get('token_name', '')),
                    ('Token Ticker', extra_data.get('token_ticker', '')),
                    ('Project Image', extra_data.get('project_image', '')),
                    ('Token Image', extra_data.get('token_image', '')),
                    ('Min Raise', extra_data.get('min_raise', '')),
                    ('Monthly Budget', extra_data.get('monthly_budget', '')),
                    ('Performance Package', extra_data.get('performance_package', '')),
                    ('Performance Unlock Time', extra_data.get('performance_unlock_time', '')),
                    ('Intellectual Property', extra_data.get('intellectual_property', ''))
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
                # Update cell by cell in the next available column pair
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
        "*What I can help you with:*\n"
        "🚀 Get your project listed on MetaDAO\n"
        "📅 View upcoming ICOs and calendar\n"
        "📚 Learn about our launch process\n"
        "🎯 Understand futarchy governance\n"
        "💬 Submit support requests\n\n"
        "*📖 Quick Links:*\n"
        "• Documentation: [docs.metadao.fi](https://docs.metadao.fi/)\n"
        "• Website: [metadao.fi](https://metadao.fi)\n\n"
        "• Calendar: [idontbelieve.link](https://www.idontbelieve.link)\n\n"
        "• Ca: METAwkXcqyXKy1AtsSgJ8JiUHwGCafnZL38n3vYmeta\n\n"
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
        "/icos - Get calendar and ICOs link\n\n"
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
            text="📊 *Proposals*\n\nLearn about creating, trading, and finalizing proposals:",
            parse_mode='Markdown',
            reply_markup=proposals_inline_keyboard()
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

    # Handle main categories (excluding get_listed and support_request which are conversations)
    category_map = {
        'icos': ('📅 ICOs & Calendar', 'View all upcoming and active ICOs'),
        'how_launches_work': ('📚 How Launches Work', 'Learn about the MetaDAO launch process'),
        'futarchy_intro': ('🎯 Introduction to Futarchy', 'Understand futarchy governance'),
        'entrepreneurs': ('💼 For Entrepreneurs', 'Benefits and resources for project founders'),
        'investors': ('💰 For Investors', 'Investment opportunities and benefits'),
        'redeem_mtn': ('🎁 Redeem $MTN Tokens', 'Redeem your $MTN tokens'),
        'redeem_meta': ('🔄 Redeem $META Tokens', 'Migrate to the new $META contract'),
    }
    if data in category_map:
        title, description = category_map[data]
        link = RESOURCE_LINKS[data]
        await query.edit_message_text(
            text=f"*{title}*\n\n{description}\n\n🔗 {link}",
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
        "📝 *Step 3 of 3:* Please describe your *{subcategory.lower()}* request in detail:",
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

async def get_listed_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, let's get started!", callback_data='get_listed_yes')],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data='main_menu')]
    ]
    
    await query.edit_message_text(
        "🚀 *Get Your Project Listed on MetaDAO*\n\n"
        "Great choice! We'll guide you through the listing process.\n\n"
        "*What you'll need:*\n"
        "• Project details and description\n"
        "• Token information\n"
        "• Images and branding\n"
        "• Financial details\n\n"
        "⏱️ *Time required:* ~5 minutes\n\n"
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
            "🎯 *Step 1 of 11: Project Overview*\n\n"
            "Please provide your *project name* and a *short description* (1-2 sentences):\n\n"
            "💡 *Example:* \"Umbra - A privacy-focused DeFi protocol enabling anonymous transactions on Solana.\"",
            parse_mode='Markdown'
        )
        return PROJECT_NAME_SHORT
    else:
        await query.edit_message_text(
            "👍 No problem! Feel free to come back anytime.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]])
        )
        return ConversationHandler.END

async def get_project_name_short(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['project_name_short'] = update.message.text
    await update.message.reply_text(
        "✅ Great start!\n\n"
        "📝 *Step 2 of 11: Detailed Description*\n\n"
        "Now provide a *longer, more detailed description* of your project:\n\n"
        "💡 Include your mission, key features, and what makes you unique.",
        parse_mode='Markdown'
    )
    return PROJECT_DESC_LONG

async def get_project_desc_long(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['project_desc_long'] = update.message.text
    await update.message.reply_text(
        "✅ Excellent!\n\n"
        "🪙 *Step 3 of 11: Token Name*\n\n"
        "What is your *token name*?\n\n"
        "💡 *Example:* \"Umbra Token\"",
        parse_mode='Markdown'
    )
    return TOKEN_NAME

async def get_token_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['token_name'] = update.message.text
    await update.message.reply_text(
        "✅ Got it!\n\n"
        "🏷️ *Step 4 of 11: Token Ticker*\n\n"
        "What is your *token ticker symbol*?\n\n"
        "💡 *Example:* \"UMBRA\"",
        parse_mode='Markdown'
    )
    return TOKEN_TICKER

async def get_token_ticker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['token_ticker'] = update.message.text
    await update.message.reply_text(
        "✅ Perfect!\n\n"
        "🖼️ *Step 5 of 11: Project Image*\n\n"
        "Please provide the *URL for your project image*:\n\n"
        "💡 This should be your logo or main branding image (PNG, JPG, or SVG)",
        parse_mode='Markdown'
    )
    return PROJECT_IMAGE

async def get_project_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['project_image'] = update.message.text
    await update.message.reply_text(
        "✅ Image saved!\n\n"
        "🎨 *Step 6 of 11: Token Image*\n\n"
        "Please provide the *URL for your token image*:\n\n"
        "💡 Type 'same' if it's the same as your project image",
        parse_mode='Markdown'
    )
    return TOKEN_IMAGE

async def get_token_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    token_image = update.message.text
    if token_image.lower() == 'same':
        context.user_data['token_image'] = context.user_data['project_image']
    else:
        context.user_data['token_image'] = token_image
    await update.message.reply_text(
        "✅ Looks good!\n\n"
        "💵 *Step 7 of 11: Minimum Raise*\n\n"
        "What is your *minimum raise amount*?\n\n"
        "💡 *Example:* \"$50,000\" or \"50000 USDC\"",
        parse_mode='Markdown'
    )
    return MIN_RAISE

async def get_min_raise(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['min_raise'] = update.message.text
    await update.message.reply_text(
        "✅ Noted!\n\n"
        "📊 *Step 8 of 11: Monthly Budget*\n\n"
        "What is your *monthly team budget*?\n\n"
        "💡 *Example:* \"$10,000\"",
        parse_mode='Markdown'
    )
    return MONTHLY_BUDGET

async def get_monthly_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['monthly_budget'] = update.message.text
    await update.message.reply_text(
        "✅ Understood!\n\n"
        "🎁 *Step 9 of 11: Performance Package*\n\n"
        "What is your *performance package amount*?\n\n"
        "💡 *Example:* \"$25,000\"",
        parse_mode='Markdown'
    )
    return PERFORMANCE_PACKAGE

async def get_performance_package(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['performance_package'] = update.message.text
    await update.message.reply_text(
        "✅ Great!\n\n"
        "⏰ *Step 10 of 11: Unlock Time*\n\n"
        "What is the *minimum unlock time* for the performance package?\n\n"
        "💡 *Example:* \"6 months\" or \"180 days\"",
        parse_mode='Markdown'
    )
    return PERFORMANCE_UNLOCK_TIME

async def get_performance_unlock_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not context.user_data.get('get_listed_active'):
        return ConversationHandler.END
    context.user_data['performance_unlock_time'] = update.message.text
    await update.message.reply_text(
        "✅ Almost done!\n\n"
        "📜 *Step 11 of 11: Intellectual Property*\n\n"
        "Please list any *intellectual property* (patents, trademarks, etc.):\n\n"
        "💡 Type 'none' if you don't have any",
        parse_mode='Markdown'
    )
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
            f"❌ *Oops! Some information is missing*\n\n"
            f"Missing fields: {', '.join(missing_fields)}\n\n"
            f"Please start over with /start to submit your listing.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')]])
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
        "🎉 *Submission Complete!*\n\n"
        "Congratulations! Your project listing has been submitted successfully.\n\n"
        "*What happens next:*\n"
        "1️⃣ Our team will review your submission\n"
        "2️⃣ We'll reach out if we need any additional information\n"
        "3️⃣ You'll receive a decision within 3-5 business days\n\n"
        "📧 We'll contact you via Telegram or the email you provided.\n\n"
        "Thank you for choosing MetaDAO! 🚀",
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

async def ca_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"`{META_CA}`\n\n",
        parse_mode='Markdown'
    )

async def web_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"{RESOURCE_LINKS['website']}\n\n",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def docs_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"{RESOURCE_LINKS['docs']}\n\n",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def icos_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"{RESOURCE_LINKS['icos']}\n\n",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def redeem_mtn_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"{RESOURCE_LINKS['redeem_mtn']}\n\n",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def redeem_meta_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"{RESOURCE_LINKS['redeem_meta']}\n\n",
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def handle_ca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == 'private':
        return
    ca_variants = ["CA", "ca", "Ca"]
    if update.message.text in ca_variants:
        await update.message.reply_text(
            f"`{META_CA}`\n\n",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )

def determine_context_type(message: str) -> str:
    """
    Determine the type of query based on message content
    
    Args:
        message: User's message text
    
    Returns:
        Context type string (faq, help, summarize, general)
    """
    message_lower = message.lower()
    
    # FAQ keywords
    faq_keywords = ['what is', 'how do', 'how can', 'explain', 'tell me about', 'what are', 
                    'futarchy', 'metadao', 'ico', 'proposal', 'token', 'launch']
    if any(keyword in message_lower for keyword in faq_keywords):
        return "faq"
    
    # Help/navigation keywords
    help_keywords = ['help', 'how to', 'where', 'find', 'navigate', 'get started', 
                     'i want to', 'i need', 'looking for']
    if any(keyword in message_lower for keyword in help_keywords):
        return "help"
    
    # Summarize keywords
    summarize_keywords = ['summarize', 'summary', 'brief', 'overview', 'tldr']
    if any(keyword in message_lower for keyword in summarize_keywords):
        return "summarize"
    
    return "general"

def get_contextual_keyboard(message: str) -> InlineKeyboardMarkup:
    """
    Generate contextual keyboard buttons based on user message
    
    Args:
        message: User's message text
    
    Returns:
        InlineKeyboardMarkup with relevant buttons
    """
    message_lower = message.lower()
    
    # Default buttons
    buttons = []
    
    # ICO/Calendar related
    if any(word in message_lower for word in ['ico', 'calendar', 'launch', 'upcoming', 'sale']):
        buttons.append([InlineKeyboardButton("📅 View ICO Calendar", callback_data='icos')])
    
    # Listing related
    if any(word in message_lower for word in ['list', 'launch', 'project', 'entrepreneur', 'founder']):
        buttons.append([InlineKeyboardButton("🚀 Get Listed", callback_data='get_listed')])
    
    # Futarchy/Governance related
    if any(word in message_lower for word in ['futarchy', 'governance', 'proposal', 'vote', 'decision']):
        buttons.append([InlineKeyboardButton("🎯 Learn About Futarchy", callback_data='futarchy_intro')])
        buttons.append([InlineKeyboardButton("📊 View Proposals", callback_data='proposals')])
    
    # Investment related
    if any(word in message_lower for word in ['invest', 'buy', 'token', 'participate']):
        buttons.append([InlineKeyboardButton("💰 For Investors", callback_data='investors')])
    
    # Redemption related
    if any(word in message_lower for word in ['redeem', 'migrate', 'mtn', 'meta']):
        buttons.append([InlineKeyboardButton("🎁 Redeem $MTN", callback_data='redeem_mtn')])
        buttons.append([InlineKeyboardButton("🔄 Redeem $META", callback_data='redeem_meta')])
    
    # Always add main menu and support
    if len(buttons) > 0:
        buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')])
    else:
        # If no specific context, show main menu
        buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data='main_menu')])
        buttons.append([InlineKeyboardButton("💬 Contact Support", callback_data='support_request')])
    
    return InlineKeyboardMarkup(buttons)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Use AI for general text messages if not a command or in a conversation
    if update.effective_chat.type == 'private':
        user_message = update.message.text
        # Avoid responding to commands or while in a conversation
        if not user_message.startswith('/') and not context.user_data.get('support_active') and not context.user_data.get('get_listed_active'):
            faq = find_relevant_faq(user_message)
            
            if faq:
                # Found a matching FAQ, provide structured answer
                links_text = "\n\n📚 *Related Resources:*\n"
                for link in faq['related_links']:
                    links_text += f"• {link}\n"
                
                response_text = f"*{faq['question']}*\n\n{faq['answer']}{links_text}"
                keyboard = get_contextual_keyboard(user_message)
                
                await update.message.reply_text(
                    response_text,
                    parse_mode='Markdown',
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
            else:
                # No FAQ match, use AI
                context_type = determine_context_type(user_message)
                ai_response = await get_ai_response(user_message, context_type=context_type)
                
                # Add helpful buttons based on context
                keyboard = get_contextual_keyboard(user_message)
                
                await update.message.reply_text(
                    ai_response, 
                    parse_mode='Markdown', 
                    disable_web_page_preview=True,
                    reply_markup=keyboard
                )
    pass

async def get_ai_response(user_message: str, context_type: str = "general") -> str:
    """
    Generate AI response using Groq
    
    Args:
        user_message: The user's question or message
        context_type: Type of context (general, faq, summarize, help)
    
    Returns:
        AI-generated response string
    """
    if not groq_client:
        return "AI features are currently unavailable. Please use the menu buttons or contact support."
    
    try:
        # Build system prompt based on context type
        if context_type == "faq":
            system_prompt = f"""You are a helpful MetaDAO assistant. Answer questions about MetaDAO concisely and accurately.
Use this knowledge base:

{METADAO_KNOWLEDGE}

Keep answers brief (2-3 sentences) and include relevant links when helpful.
If you don't know something, say so and suggest using the menu or contacting support."""
        
        elif context_type == "summarize":
            system_prompt = """You are a helpful assistant that summarizes documentation clearly and concisely.
Provide a brief summary in 2-3 sentences that captures the key points."""
        
        elif context_type == "help":
            system_prompt = f"""You are a helpful MetaDAO assistant that guides users to the right resources.
Based on the user's intent, suggest relevant actions or menu options.

Available resources:
{METADAO_KNOWLEDGE}

Be conversational and helpful. Suggest specific menu buttons or commands when appropriate."""
        
        else:  # general
            system_prompt = f"""You are a helpful MetaDAO assistant. Answer questions about MetaDAO clearly and concisely.

{METADAO_KNOWLEDGE}

Keep responses brief and friendly. Include relevant links when helpful."""
        
        # Call Groq API
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
            max_tokens=500
        )
        
        response = chat_completion.choices[0].message.content
        logger.info(f"AI response generated for context: {context_type}")
        return response
        
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "I'm having trouble processing that right now. Please try using the menu buttons or contact support."

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
        _application.add_handler(CommandHandler('faq', faq_command_handler, filters=filters.ChatType.PRIVATE))
        
        _application.add_handler(CommandHandler('ca', ca_command_handler))
        _application.add_handler(CommandHandler('web', web_command_handler))
        _application.add_handler(CommandHandler('docs', docs_command_handler))
        _application.add_handler(CommandHandler('icos', icos_command_handler))
        _application.add_handler(CommandHandler('redeem_mtn', redeem_mtn_command_handler))
        _application.add_handler(CommandHandler('redeem_meta', redeem_meta_command_handler))
        
        _application.add_handler(get_listed_conv_handler)
        _application.add_handler(conv_handler)
        _application.add_handler(CallbackQueryHandler(faq_button_handler, pattern='^faq_'))
        _application.add_handler(CallbackQueryHandler(show_faq_menu_handler, pattern='^show_faq_menu$'))
        _application.add_handler(CallbackQueryHandler(button_handler, pattern='^(?!get_listed$|support_request$|faq_|show_faq_menu$)'))
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
            BotCommand("faq", "View frequently asked questions"),
            BotCommand("cancel", "Cancel current operation")
        ]
        await _application.bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
        
        # Set commands for group chats only (info commands)
        group_commands = [
            BotCommand("ca", "Get META contract address"),
            BotCommand("web", "Get MetaDAO website link"),
            BotCommand("docs", "Get documentation link"),
            BotCommand("icos", "Get calendar and ICOs link"),
            BotCommand("redeem_mtn", "Redeem $MTN Tokens"),
            BotCommand("redeem_meta", "Redeem $META Tokens")
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
