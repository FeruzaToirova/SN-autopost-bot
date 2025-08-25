#!/usr/bin/env python3
"""
Configuration file for Telegram Auto-posting Bot

Instructions:
1. Get a bot token from @BotFather on Telegram
2. Get your target chat ID (group/channel where posts will be sent)
3. Replace the placeholder values below with your actual values
4. Save the file and run: python bot.py
"""

# ============================================================================
# REQUIRED CONFIGURATION - YOU MUST CHANGE THESE VALUES
# ============================================================================

# Your Telegram Bot Token from @BotFather
# Example: "1234567890:ABCDEFghijklmnopqrstuvwxyz1234567890"
BOT_TOKEN = "8362260096:AAHTMoiUwC0lEv5F2f2gxJev3uZQws5BPxo"

# Target Chat ID where posts will be sent
# For groups: negative number like "-1001234567890"
# For channels: negative number like "-1001234567890" 
# For private chats: positive number like "1234567890"
TARGET_CHAT_ID = "-1002667543758"

# Access password for new users
# Change this password to restrict access to your company employees only
ACCESS_PASSWORD = "totoncha"

# ============================================================================
# OPTIONAL CONFIGURATION - You can modify these if needed
# ============================================================================

# Database file name (SQLite database will be created automatically)
DATABASE_FILE = "bot_posts.db"

# Scheduler check interval in seconds (how often to check for posts to publish)
SCHEDULER_INTERVAL = 30

# Bot update polling interval in seconds (how often to check for new messages)
POLLING_INTERVAL = 0.1

# Maximum file size for photos in bytes (10MB default)
MAX_PHOTO_SIZE = 10 * 1024 * 1024

# ============================================================================
# HOW TO GET YOUR BOT TOKEN AND CHAT ID
# ============================================================================

"""
HOW TO GET BOT TOKEN:
1. Open Telegram and search for @BotFather
2. Send /start to BotFather
3. Send /newbot and follow the instructions
4. Choose a name and username for your bot
5. BotFather will give you a token - copy it to BOT_TOKEN above

HOW TO GET CHAT ID:
Method 1 - For groups/channels:
1. Add your bot to the group/channel as admin
2. Send a message in the group/channel
3. Visit: https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
4. Look for "chat":{"id": -1001234567890} in the response
5. Copy the ID (including the minus sign) to TARGET_CHAT_ID above

Method 2 - Using @userinfobot:
1. Add @userinfobot to your group/channel
2. The bot will show you the chat ID
3. Copy the ID to TARGET_CHAT_ID above

Method 3 - For private messages:
1. Search for @userinfobot on Telegram
2. Send any message to it
3. It will reply with your user ID
4. Copy the ID to TARGET_CHAT_ID above

PASSWORD PROTECTION:
- Only users who know the ACCESS_PASSWORD can use the bot
- New users will be prompted to enter the password when they first use the bot
- Once authorized, users remain authorized until manually revoked
- Change the password regularly for security
- Only share the password with authorized company employees
"""

