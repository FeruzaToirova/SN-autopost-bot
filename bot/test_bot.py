#!/usr/bin/env python3
"""
Simple test script for the Telegram Auto-posting Bot

This script helps verify that your bot configuration is working correctly.
Run this before starting the main bot to check your setup.
"""

import sys
import datetime

def test_configuration():
    """Test if configuration is properly set up."""
    print("🧪 Testing Bot Configuration...")
    print("-" * 40)
    
    # Test config import
    try:
        from config import BOT_TOKEN, TARGET_CHAT_ID
        print("✅ Configuration file imported successfully")
    except ImportError:
        print("❌ Error: config.py file not found!")
        print("Please create config.py with your bot token and chat ID.")
        return False
    
    # Test configuration values
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Error: BOT_TOKEN not configured!")
        print("Please set your bot token in config.py")
        return False
    else:
        print(f"✅ Bot token configured: {BOT_TOKEN[:10]}...")
    
    if TARGET_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("❌ Error: TARGET_CHAT_ID not configured!")
        print("Please set your target chat ID in config.py")
        return False
    else:
        print(f"✅ Target chat ID configured: {TARGET_CHAT_ID}")
    
    # Test basic validation
    if not BOT_TOKEN or len(BOT_TOKEN) < 10:
        print("❌ Error: Bot token appears invalid (too short)")
        return False
    
    if not TARGET_CHAT_ID:
        print("❌ Error: Target chat ID is empty")
        return False
    
    print("✅ Configuration looks good!")
    return True

def test_database():
    """Test database functionality."""
    print("\n🗄️ Testing Database Functionality...")
    print("-" * 40)
    
    try:
        from bot import TelegramBot
        
        # Create bot instance (this initializes the database)
        bot = TelegramBot("test_token", "test_chat")
        print("✅ Database initialization successful")
        
        # Test adding a post
        test_content = "Test post content"
        test_time = datetime.datetime.now().isoformat()
        
        post_id = bot.add_post(
            content=test_content,
            scheduled_time=test_time,
            is_recurring=False
        )
        print(f"✅ Post creation successful (ID: {post_id})")
        
        # Test retrieving posts
        posts = bot.get_posts()
        if posts and len(posts) > 0:
            print(f"✅ Post retrieval successful ({len(posts)} posts found)")
        else:
            print("⚠️ Warning: No posts found after creation")
        
        # Test updating post
        updated = bot.update_post(post_id, content="Updated test content")
        if updated:
            print("✅ Post update successful")
        else:
            print("❌ Error: Post update failed")
        
        # Test deleting post
        deleted = bot.delete_post(post_id)
        if deleted:
            print("✅ Post deletion successful")
        else:
            print("❌ Error: Post deletion failed")
        
        # Clean up
        bot.conn.close()
        print("✅ Database test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def test_telegram_connection():
    """Test connection to Telegram API."""
    print("\n🌐 Testing Telegram Connection...")
    print("-" * 40)
    
    try:
        from config import BOT_TOKEN, TARGET_CHAT_ID
        from bot import TelegramBot
        
        bot = TelegramBot(BOT_TOKEN, TARGET_CHAT_ID)
        
        # Test basic API call
        print("Testing API connection...")
        result = bot.make_request("getMe")
        
        if result.get('ok'):
            bot_info = result['result']
            print(f"✅ Connected to Telegram successfully!")
            print(f"   Bot name: {bot_info.get('first_name', 'Unknown')}")
            print(f"   Bot username: @{bot_info.get('username', 'Unknown')}")
        else:
            print(f"❌ Error connecting to Telegram: {result}")
            return False
        
        # Note: Bot will only send scheduled posts to the target chat
        print("✅ API connection verified!")
        print("ℹ️ Bot will only send scheduled posts to your target chat.")
        print("ℹ️ No test messages will be sent to avoid spam.")
        
        bot.conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    """Run all tests."""
    print("🤖 Telegram Auto-posting Bot Test Suite")
    print("=" * 50)
    
    # Run tests
    config_ok = test_configuration()
    if not config_ok:
        print("\n❌ Configuration test failed. Please fix config.py first.")
        return
    
    db_ok = test_database()
    if not db_ok:
        print("\n❌ Database test failed. Check for Python/SQLite issues.")
        return
    
    telegram_ok = test_telegram_connection()
    if not telegram_ok:
        print("\n❌ Telegram connection test failed. Check your bot token and chat ID.")
        return
    
    print("\n" + "=" * 50)
    print("🎉 All tests passed! Your bot is ready to run.")
    print("\nTo start the bot, run: python bot.py")

if __name__ == "__main__":
    main()

