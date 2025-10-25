# MetaDAO AI Telegram Bot

An AI-powered Telegram bot for MetaDAO that uses Groq for intelligent responses in private messages.

## Features

- **AI-Powered Responses**: Uses Groq (llama-3.3-70b-versatile) to answer user questions about MetaDAO
- **Get Listed Form**: 26-step structured form for project submissions
- **Support Request System**: Multi-category support with image URL attachment
- **Google Sheets Integration**: Automatic logging of all submissions
- **Command Handlers**: Quick access to resources via commands

## Environment Variables

Required environment variables:
- `BOT_TOKEN`: Telegram bot token
- `GROQ_API_KEY`: Groq API key for AI responses
- `GOOGLE_CREDENTIALS`: Google service account credentials (JSON)
- `SHEET_NAME`: Google Sheets spreadsheet name (default: "MetaDAO Get Listed Requests")
- `SUPPORT_CHAT_ID`: Telegram chat ID for forwarding support requests (optional)

## Deployment

This bot is designed to run on Vercel as a serverless function. The webhook handler processes incoming Telegram updates.

## Usage

### Private Messages
- Users can ask any question and get AI-powered responses
- The bot provides relevant links and information about MetaDAO
- Two main actions available via buttons: "Get Listed" and "Support Request"

### Commands
- `/start` - Start the bot and show main menu
- `/help` - Show help information
- `/cancel` - Cancel current operation
- `/ca` - Get META contract address
- `/web`, `/docs`, `/icos`, `/markets` - Quick access to resources
- `/twitter`, `/telegram`, `/discord`, `/youtube`, `/blog`, `/github` - Social links

## Support Request Flow

1. Select category (Refunds, Bugs, Suggestions, Technical Issues, Account Issues, General Inquiry)
2. Provide name
3. Provide email
4. Describe the issue
5. Provide image URL (optional)
6. Submission logged to Google Sheets and forwarded to support team

## Get Listed Flow

26-step form collecting:
- Founder and project emails
- Project details and description
- Token information
- Visual assets
- Financial details
- Social media links
- Intellectual property information
- And more...

All submissions are logged to a dedicated Google Sheets tab.
