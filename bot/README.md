# Telegram Auto-posting Bot

A simple Python bot for automatic posting to Telegram groups/channels. Supports scheduled posts, recurring daily posts, and comprehensive post management - all using only Python's standard library.

## Features

### ✨ Post Types
- 📝 Text-only posts
- 📷 Single photo posts (with or without caption)
- 🖼️ Mixed content with photo and text

### ⏰ Scheduling
- 📅 Schedule posts for specific date/time
- 🔄 Weekday recurring posts (Monday-Friday, excluding weekends)
- ⚡ Immediate posting option

### 🎛️ Management Interface
- `/add` - Step-by-step post creation wizard
- `/list` - View all scheduled posts as actual content preview
- 🗑️ Delete posts with confirmation
- 📊 Clear post status and scheduling info
- 🔐 Password protection for authorized access only
- 📸 Visual post preview showing exactly how posts will appear

### 🔧 Technical Features
- 💾 SQLite database for reliable storage
- 🌐 Direct Telegram Bot API integration (no external libraries)
- 🔄 Automatic scheduler with threading
- 📱 Interactive calendar and time picker interface
- 🛡️ Error handling and validation
- 📅 Visual date selection with past date protection

## Requirements

- Python 3.6+
- Telegram Bot Token
- Target Chat ID (group/channel/private chat)

**No external libraries required** - uses only Python standard library!

## Quick Setup

### 1. Create Your Bot

1. Open Telegram and search for `@BotFather`
2. Send `/start` to BotFather
3. Send `/newbot` and follow instructions
4. Choose a name and username for your bot
5. Copy the bot token you receive

### 2. Get Chat ID

**For Groups/Channels:**
1. Add your bot to the group/channel as admin
2. Send any message in the group/channel  
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find `"chat":{"id": -1001234567890}` in the response
5. Copy the ID (including minus sign)

**For Private Messages:**
1. Search for `@userinfobot` on Telegram
2. Send any message to it
3. Copy your user ID

### 3. Configure the Bot

1. Open `config.py`
2. Replace `YOUR_BOT_TOKEN_HERE` with your bot token
3. Replace `YOUR_CHAT_ID_HERE` with your chat ID
4. **Set your access password** in `ACCESS_PASSWORD` (default: "totoncha")
5. Save the file

**Important:** Only users who know the access password can use the bot!

### 4. Run the Bot

```bash
python bot.py
```

That's it! Your bot is now running and ready to schedule posts.

## Usage Guide

### First Time Setup (Authentication)

**New users must authenticate first in private chat:**
1. **Start a private chat** with the bot (click bot name → "Send Message")
2. Send `/start` to your bot in private chat
3. Enter the access password when prompted
4. Once authorized, you can manage posts in private chat

**Important:** 
- **All bot management** (adding, editing, listing posts) **only works in private chats**
- **Group/channel chats** are used **only for scheduled posts** - the bot stays completely silent otherwise
- **No authentication prompts** or other messages in groups - keeps them clean!

### Adding Posts

**In private chat with the bot:**
1. Send `/add` to your bot
2. Follow the 4-step wizard:
   - **Step 1:** Enter text content (or "skip" for photo-only)
   - **Step 2:** Send photos one by one (up to 10 for galleries) or "skip" for text-only
   - **Step 3:** Use calendar interface to select date and time
   - **Step 4:** Choose if post should repeat on weekdays (Monday-Friday)

### Managing Posts

**In private chat with the bot:**
1. Send `/list` to see all scheduled posts displayed exactly as they will appear
2. Each post shows:
   - **Actual content** (text, single photo, or photo gallery exactly as it will be posted)
   - **Photo galleries** display all photos as media groups
   - **Post ID** and **scheduling information**
   - **Recurring status** (daily or one-time)
   - **🗑️ Delete button** to remove the post with confirmation

### Calendar Interface

The bot features an intuitive calendar interface for date/time selection:

**📅 Date Selection:**
- Navigate months with ◀️ ▶️ arrows
- Past dates are disabled (shown as ◽)
- Available dates are clickable numbers
- Selected date is highlighted (🔹)

**⏰ Time Selection:**
- **Quick time buttons** for common posting times with 30-minute intervals:
  - **Morning:** 8:00, 8:30, 9:00, 9:30, 10:00, 10:30, 11:00, 11:30
  - **Afternoon:** 12:00, 12:30, 14:00, 14:30, 16:00, 16:30, 18:00, 18:30
  - **Evening:** 20:00, 20:30, 21:00, 21:30, 22:00, 22:30
- **"Now" button** for immediate posting
- **Fine adjustment** buttons appear only when needed (Hour +/-, Min +/-)
- **30-minute increments** for minute adjustments
- **One-tap selection** for most common times

**🎯 User Experience:**
- No manual typing of dates/times required
- Visual feedback for all selections
- Past date protection prevents scheduling errors
- Seamless integration with post creation and editing

### Commands (Private Chat Only)

- `/start` - Welcome message and introduction
- `/help` - Show detailed help and instructions  
- `/add` - Add new scheduled post
- `/list` - View and manage scheduled posts

**Note:** All commands only work in private chat. Groups/channels only receive scheduled posts.

## File Structure

```
bot/
├── bot.py          # Main bot application
├── config.py       # Configuration file
├── README.md       # This file
└── bot_posts.db    # SQLite database (created automatically)
```

## How It Works

### Post Scheduling
- Bot checks every 30 seconds for posts that need publishing
- Posts are automatically sent to your configured chat
- Recurring posts are rescheduled for next day after posting
- One-time posts are marked as completed

### Data Storage
- All posts stored in SQLite database (`bot_posts.db`)
- Photos stored as binary data in database
- No external files needed for photos

### Message Processing
- Bot maintains user states for multi-step commands
- Supports both text messages and inline button interactions
- Handles photo uploads and downloads automatically

## Troubleshooting

### Common Issues

**"Configuration file not found"**
- Make sure `config.py` exists with your bot token and chat ID

**"Please configure BOT_TOKEN and TARGET_CHAT_ID"**
- Replace placeholder values in `config.py` with real ones

**"Failed to publish post"**
- Check if bot has permission to post in target chat
- Verify bot is added as admin in groups/channels

**"HTTP Error 403"**
- Bot doesn't have permission to send messages
- Make sure bot is admin in target chat

**"HTTP Error 400"**
- Invalid chat ID format
- Make sure chat ID includes minus sign for groups/channels

### Debug Mode

Add debug prints by modifying the bot:

```python
# Add this line after creating bot instance in main()
print(f"Bot token: {BOT_TOKEN[:10]}...")
print(f"Target chat: {TARGET_CHAT_ID}")
```

## Advanced Configuration

Edit `config.py` for advanced options:

```python
# Scheduler check interval (seconds)
SCHEDULER_INTERVAL = 30

# Bot polling interval (seconds)  
POLLING_INTERVAL = 0.1

# Maximum photo size (bytes)
MAX_PHOTO_SIZE = 10 * 1024 * 1024
```

## Security Notes

- Keep your `config.py` file private
- Don't share your bot token
- **Keep your access password secure** - only share with authorized employees
- Use environment variables for production deployment
- Database file contains your photos - keep it secure

### Password Management

**To change the access password:**
1. Edit `ACCESS_PASSWORD` in `config.py`
2. Restart the bot
3. Inform authorized users of the new password

**Important Notes:**
- **Authentication only works in private chats** for security
- Current authorized users are stored in the database and remain authorized even after password changes
- Users who try to use the bot in groups without being authenticated will be directed to start a private chat first

## Limitations

- Photos limited by Telegram's file size restrictions
- Bot must remain running for scheduled posts to work
- No built-in backup/restore functionality
- Single timezone support (system timezone)

## Support

This bot is designed to be simple and readable. If you need to modify it:

1. All code is well-commented
2. Functions are small and focused
3. No complex dependencies
4. Clear separation of concerns

For issues or questions, check the error messages in the console - they're designed to be helpful and specific.

