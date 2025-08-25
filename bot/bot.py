#!/usr/bin/env python3
"""
Telegram Auto-posting Bot

A simple bot for automatic posting to Telegram groups/channels.
Supports scheduled posts, recurring daily posts, and post management.

Requirements:
- Python 3.6+
- Telegram Bot Token
- Target Chat ID (group/channel)

Author: Assistant
"""

import json
import sqlite3
import urllib.request
import urllib.parse
import urllib.error
import threading
import time
import datetime
import os

import calendar
from typing import Dict, List, Optional, Any

class TelegramBot:
    """
    Main Telegram Bot class for auto-posting functionality.
    Uses only Python standard library with direct HTTPS requests to Telegram Bot API.
    """
    
    def __init__(self, bot_token: str, target_chat_id: str):
        """
        Initialize the bot with token and target chat ID.
        
        Args:
            bot_token: Telegram Bot API token
            target_chat_id: Target chat ID for posting (group/channel)
        """
        self.bot_token = bot_token
        self.target_chat_id = target_chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Initialize database
        self.init_database()
        
        # Store user states for multi-step commands
        self.user_states = {}
        
        # Scheduler thread
        self.scheduler_running = False
        self.scheduler_thread = None
        
        print("Bot initialized successfully!")
    
    def init_database(self):
        """Initialize SQLite database for storing posts and authorized users."""
        self.conn = sqlite3.connect('bot_posts.db', check_same_thread=False)
        
        # Posts table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                photo_data BLOB,
                photo_filename TEXT,
                scheduled_time TEXT NOT NULL,
                is_recurring INTEGER DEFAULT 0,
                is_posted INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check and repair any corrupted data
        self._repair_database_data()
        
        # Migrate old database schema if needed
        self._migrate_database_schema()
        
        # Authorized users table
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS authorized_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                authorized_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        print("Database initialized successfully!")
    
    def _repair_database_data(self):
        """Repair any corrupted data in the database."""
        try:
            cursor = self.conn.cursor()
            
            # Check if there are posts with invalid scheduled_time
            cursor.execute('SELECT id, scheduled_time FROM posts WHERE scheduled_time IS NOT NULL')
            posts = cursor.fetchall()
            
            repaired_count = 0
            for post_id, scheduled_time in posts:
                # Check if scheduled_time is a valid datetime string
                if not isinstance(scheduled_time, str) or not scheduled_time.strip():
                    print(f"Repairing post {post_id}: Invalid scheduled_time '{scheduled_time}'")
                    
                    # Set a default time (1 hour from now)
                    default_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
                    cursor.execute('UPDATE posts SET scheduled_time = ? WHERE id = ?', (default_time, post_id))
                    repaired_count += 1
                else:
                    # Validate the datetime format
                    try:
                        datetime.datetime.fromisoformat(scheduled_time)
                    except ValueError:
                        print(f"Repairing post {post_id}: Invalid datetime format '{scheduled_time}'")
                        
                        # Try to parse common formats or set default
                        try:
                            # Try different date formats
                            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
                                try:
                                    dt = datetime.datetime.strptime(scheduled_time, fmt)
                                    # Add current time if only date was provided
                                    if fmt in ['%Y-%m-%d']:
                                        dt = dt.replace(hour=12, minute=0)
                                    fixed_time = dt.isoformat()
                                    cursor.execute('UPDATE posts SET scheduled_time = ? WHERE id = ?', (fixed_time, post_id))
                                    repaired_count += 1
                                    break
                                except ValueError:
                                    continue
                            else:
                                # If no format worked, set default time
                                default_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
                                cursor.execute('UPDATE posts SET scheduled_time = ? WHERE id = ?', (default_time, post_id))
                                repaired_count += 1
                        except Exception as e:
                            print(f"Could not repair post {post_id}: {e}")
                            # Set default time as last resort
                            default_time = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
                            cursor.execute('UPDATE posts SET scheduled_time = ? WHERE id = ?', (default_time, post_id))
                            repaired_count += 1
            
            if repaired_count > 0:
                self.conn.commit()
                print(f"Repaired {repaired_count} posts with invalid scheduled_time")
            else:
                print("No database repairs needed")
                
        except Exception as e:
            print(f"Error during database repair: {e}")
    
    def _migrate_database_schema(self):
        """Migrate database from old schema to new schema."""
        try:
            cursor = self.conn.cursor()
            
            # Check if old photos_data column exists
            cursor.execute("PRAGMA table_info(posts)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if 'photos_data' in column_names:
                print("Migrating database schema: Removing photos_data column...")
                
                # Create new table with correct schema
                cursor.execute('''
                    CREATE TABLE posts_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        content TEXT NOT NULL,
                        photo_data BLOB,
                        photo_filename TEXT,
                        scheduled_time TEXT NOT NULL,
                        is_recurring INTEGER DEFAULT 0,
                        is_posted INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Copy data from old table to new table
                cursor.execute('''
                    INSERT INTO posts_new (id, content, photo_data, photo_filename, scheduled_time, is_recurring, is_posted, created_at)
                    SELECT id, content, photo_data, photo_filename, scheduled_time, is_recurring, is_posted, created_at
                    FROM posts
                ''')
                
                # Drop old table and rename new table
                cursor.execute('DROP TABLE posts')
                cursor.execute('ALTER TABLE posts_new RENAME TO posts')
                
                self.conn.commit()
                print("Database schema migration completed successfully!")
            else:
                print("Database schema is already up to date.")
                
        except Exception as e:
            print(f"Error during database migration: {e}")
    
    def make_request(self, method: str, params: Dict = None, files: Dict = None) -> Dict:
        """
        Make HTTPS request to Telegram Bot API.
        
        Args:
            method: API method name
            params: Request parameters
            files: Files to upload (for photo uploads)
            
        Returns:
            API response as dictionary
        """
        url = f"{self.api_url}/{method}"
        
        try:
            if files:
                # Handle file upload with multipart/form-data
                boundary = '----WebKitFormBoundary' + ''.join([str(x) for x in range(10)])
                body = b''
                
                # Add regular parameters
                if params:
                    for key, value in params.items():
                        body += f'--{boundary}\r\n'.encode()
                        body += f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode()
                        body += f'{value}\r\n'.encode()
                
                # Add file
                for key, (filename, file_data) in files.items():
                    body += f'--{boundary}\r\n'.encode()
                    body += f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode()
                    body += f'Content-Type: application/octet-stream\r\n\r\n'.encode()
                    body += file_data
                    body += b'\r\n'
                
                body += f'--{boundary}--\r\n'.encode()
                
                req = urllib.request.Request(url, data=body)
                req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
            else:
                # Regular POST request
                data = urllib.parse.urlencode(params or {}).encode() if params else b''
                req = urllib.request.Request(url, data=data)
                req.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                return result
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            print(f"HTTP Error {e.code}: {error_body}")
            return {"ok": False, "error": f"HTTP {e.code}: {error_body}"}
        except Exception as e:
            print(f"Request error: {e}")
            return {"ok": False, "error": str(e)}
    
    def send_message(self, chat_id: str, text: str, reply_markup: Dict = None) -> Dict:
        """Send text message to chat."""
        params = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        
        return self.make_request("sendMessage", params)
    
    def send_photo(self, chat_id: str, photo_data: bytes, caption: str = "", filename: str = "photo.jpg") -> Dict:
        """Send photo to chat."""
        params = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "HTML"
        }
        files = {
            "photo": (filename, photo_data)
        }
        
        return self.make_request("sendPhoto", params, files)
    

    
    def edit_message_text(self, chat_id: str, message_id: int, text: str, reply_markup: Dict = None) -> Dict:
        """Edit message text."""
        params = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)
        
        return self.make_request("editMessageText", params)
    
    def get_updates(self, offset: int = 0) -> Dict:
        """Get updates from Telegram."""
        params = {
            "offset": offset,
            "timeout": 10
        }
        return self.make_request("getUpdates", params)
    
    def add_post(self, content: str, photo_data: bytes = None, photo_filename: str = None,
                scheduled_time: str = None, is_recurring: bool = False) -> int:
        """
        Add a new post to the database.
        
        Args:
            content: Post text/caption
            photo_data: Single photo binary data
            photo_filename: Single photo filename
            scheduled_time: ISO format datetime string
            is_recurring: Whether post should repeat on weekdays (Monday-Friday)
            
        Returns:
            Post ID
        """
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO posts (content, photo_data, photo_filename, scheduled_time, is_recurring)
            VALUES (?, ?, ?, ?, ?)
        ''', (content, photo_data, photo_filename, scheduled_time, int(is_recurring)))
        self.conn.commit()
        post_id = cursor.lastrowid
        
        print(f"Added post {post_id} scheduled for {scheduled_time}")
        return post_id
    
    def get_posts(self, include_posted: bool = False) -> List[Dict]:
        """Get all posts from database."""
        cursor = self.conn.cursor()
        if include_posted:
            cursor.execute('SELECT * FROM posts ORDER BY scheduled_time')
        else:
            cursor.execute('SELECT * FROM posts WHERE is_posted = 0 ORDER BY scheduled_time')
        
        posts = []
        for row in cursor.fetchall():
            posts.append({
                'id': row[0],
                'content': row[1],
                'photo_data': row[2],
                'photo_filename': row[3],
                'scheduled_time': row[4],
                'is_recurring': bool(row[5]),
                'is_posted': bool(row[6]),
                'created_at': row[7]
            })
        return posts
    
    def delete_post(self, post_id: int) -> bool:
        """Delete a post from database."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        self.conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            print(f"Deleted post {post_id}")
        return deleted
    
    def update_post(self, post_id: int, **kwargs) -> bool:
        """Update a post in database."""
        if not kwargs:
            return False
        
        # Build UPDATE query dynamically
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ['content', 'photo_data', 'photo_filename', 'scheduled_time', 'is_recurring', 'is_posted']:
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return False
        
        values.append(post_id)
        query = f"UPDATE posts SET {', '.join(fields)} WHERE id = ?"
        
        cursor = self.conn.cursor()
        cursor.execute(query, values)
        self.conn.commit()
        updated = cursor.rowcount > 0
        if updated:
            print(f"Updated post {post_id}")
        return updated
    
    def mark_post_as_posted(self, post_id: int):
        """Mark a post as posted."""
        self.update_post(post_id, is_posted=1)
    
    def is_user_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id FROM authorized_users WHERE user_id = ?', (user_id,))
        return cursor.fetchone() is not None
    
    def _get_next_weekday(self, current_time: datetime.datetime) -> datetime.datetime:
        """Get the next weekday (Monday-Friday) at the same time, skipping weekends."""
        # Start with tomorrow
        next_time = current_time + datetime.timedelta(days=1)
        
        # Keep adding days until we find a weekday (Monday=0, Sunday=6)
        while next_time.weekday() >= 5:  # Saturday=5, Sunday=6
            next_time += datetime.timedelta(days=1)
        
        return next_time
    
    # def debug_database_schema(self):
    #     """Debug method to inspect database schema and data."""
    #     cursor = self.conn.cursor()
    #     
    #     # Check table structure
    #     cursor.execute("PRAGMA table_info(posts)")
    #     columns = cursor.fetchall()
    #     print("DEBUG: Database schema:")
    #     for col in columns:
    #         print(f"  {col[1]} ({col[2]}) - Default: {col[4]}")
    #     
    #     # Check all posts for data type issues
    #     cursor.execute("SELECT * FROM posts")
    #     posts = cursor.fetchall()
    #     if posts:
    #             print(f"DEBUG: Found {len(posts)} posts in database")
    #             print("    ... (showing first 3 posts only)")
    #             break
    #     else:
    #         print("DEBUG: No posts in database")
    
    def authorize_user(self, user_id: int, username: str = None, first_name: str = None):
        """Add user to authorized users list."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO authorized_users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))
        self.conn.commit()
        print(f"User {user_id} ({first_name or 'Unknown'}) authorized successfully!")
    
    def get_authorized_users(self) -> List[Dict]:
        """Get list of all authorized users."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM authorized_users ORDER BY authorized_at')
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'authorized_at': row[3]
            })
        return users
    
    def revoke_user_access(self, user_id: int) -> bool:
        """Remove user from authorized users list."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM authorized_users WHERE user_id = ?', (user_id,))
        self.conn.commit()
        revoked = cursor.rowcount > 0
        if revoked:
            print(f"User {user_id} access revoked!")
        return revoked
    
    def _handle_unauthorized_user(self, chat_id: str, user_id: int, user_info: Dict = None):
        """Handle unauthorized user trying to access the bot."""
        # Check if this is a private chat
        if not chat_id.startswith('-'):  # Private chats have positive IDs
            # This is a private chat - allow password authentication
            self.user_states[user_id] = {
                'state': 'waiting_for_password',
                'user_info': user_info or {}
            }
            
            user_name = ""
            if user_info:
                first_name = user_info.get('first_name', '')
                last_name = user_info.get('last_name', '')
                user_name = f" {first_name} {last_name}".strip()
            
            auth_text = f"""
🔐 <b>Access Required</b>

Hello{user_name}! This bot is restricted to authorized company employees only.

Please enter the access password to continue:
            """
            
            self.send_message(chat_id, auth_text)
        else:
            # This is a group/channel - do nothing, stay completely silent
            # The bot should only send scheduled posts to groups, never authentication messages
            pass
    
    def _handle_password_attempt(self, chat_id: str, user_id: int, password: str, user_info: Dict = None):
        """Handle password authentication attempt."""
        try:
            from config import ACCESS_PASSWORD
        except ImportError:
            ACCESS_PASSWORD = "totoncha"  # Fallback password
        
        if password.strip() == ACCESS_PASSWORD:
            # Password correct - authorize user
            username = user_info.get('username') if user_info else None
            first_name = user_info.get('first_name') if user_info else None
            
            self.authorize_user(user_id, username, first_name)
            
            # Clear user state
            if user_id in self.user_states:
                del self.user_states[user_id]
            
            success_text = """
✅ <b>Access Granted!</b>

Welcome to the Auto-posting Bot! You are now authorized to use all bot features.

Available commands:
/add - Add a new scheduled post
/list - View all scheduled posts
/help - Show detailed help

Type /help for more information.
            """
            self.send_message(chat_id, success_text)
        else:
            # Password incorrect
            error_text = """
❌ <b>Incorrect Password</b>

The password you entered is incorrect. Please contact your administrator for the correct access password.

Try again by sending the password:
            """
            self.send_message(chat_id, error_text)
    
    def process_command(self, chat_id: str, user_id: int, command: str, text: str, user_info: Dict = None):
        """Process bot commands."""
        command = command.lower()
        
        if command == "/start":
            # Only respond in private chats
            if chat_id.startswith('-'):  # This is a group/channel
                return  # Stay silent in groups
            
            # Check if user is authorized
            if not self.is_user_authorized(user_id):
                self._handle_unauthorized_user(chat_id, user_id, user_info)
                return
            
            welcome_text = """
🤖 <b>Welcome to Auto-posting Bot!</b>

✅ You are authorized to use this bot.

Available commands:
/add - Add a new scheduled post
/list - View all scheduled posts
/help - Show this help message
/repair - Repair corrupted database data
/migrate - Update database schema

The bot will automatically post your scheduled messages to the configured chat.
            """
            self.send_message(chat_id, welcome_text)
        
        elif command == "/help":
            # Only respond in private chats
            if chat_id.startswith('-'):  # This is a group/channel
                return  # Stay silent in groups
            
            if not self.is_user_authorized(user_id):
                self._handle_unauthorized_user(chat_id, user_id, user_info)
                return
            
            help_text = """
📋 <b>Bot Commands:</b>

/add - Add a new post (text, photo, or both)
  • The bot will guide you step by step with buttons
  • Easy skip buttons for optional steps
  • You can set specific date/time
  • Option for weekday recurring posts (Monday-Friday, excluding weekends)

/list - View all your scheduled posts
  • See all pending posts
  • Edit or delete posts using buttons
  • Change timing or content

/repair - Fix corrupted database data
  • Automatically repairs invalid scheduled times
  • Use if you see data type errors
  • Safe to run multiple times

/migrate - Update database schema
  • Migrates old database format to new format
  • Use if you see column-related errors
  • Safe to run multiple times

<b>Post Types Supported:</b>
• Text only
• Photo only
• Photo with caption

<b>Scheduling:</b>
• One-time posts at specific date/time
• Weekday recurring posts (Monday-Friday, excluding weekends)
            """
            self.send_message(chat_id, help_text)
        
        elif command == "/add":
            # Only respond in private chats
            if chat_id.startswith('-'):  # This is a group/channel
                return  # Stay silent in groups
            
            if not self.is_user_authorized(user_id):
                self._handle_unauthorized_user(chat_id, user_id, user_info)
                return
            self.start_add_post_flow(chat_id, user_id)
        
        elif command == "/list":
            # Only respond in private chats
            if chat_id.startswith('-'):  # This is a group/channel
                return  # Stay silent in groups
            
            if not self.is_user_authorized(user_id):
                self._handle_unauthorized_user(chat_id, user_id, user_info)
                return
            self.show_posts_list(chat_id, user_id)
        
        # elif command == "/debug":
        #     # Debug command for developers
        #     if chat_id.startswith('-'):  # This is a group/channel
        #         return  # Stay silent in groups
        #     
        #     if not self.is_user_authorized(user_id):
        #         self._handle_unauthorized_user(chat_id, user_id, user_info)
        #         return
        #     self.debug_database_schema()
        #     self.send_message(chat_id, "🔍 Database debug info printed to console. Check bot logs.")
        
        elif command == "/repair":
            # Repair command for fixing corrupted data
            if chat_id.startswith('-'):  # This is a group/channel
                return  # Stay silent in groups
            
            if not self.is_user_authorized(user_id):
                self._handle_unauthorized_user(chat_id, user_id, user_info)
                return
            self._repair_database_data()
            self.send_message(chat_id, "🔧 Database repair completed. Check console logs for details.")
        
        elif command == "/migrate":
            # Migration command for updating database schema
            if chat_id.startswith('-'):  # This is a group/channel
                return  # Stay silent in groups
            
            if not self.is_user_authorized(user_id):
                self._handle_unauthorized_user(chat_id, user_id, user_info)
                return
            self._migrate_database_schema()
            self.send_message(chat_id, "🔄 Database migration completed. Check console logs for details.")
        
        else:
            # Only respond in private chats
            if chat_id.startswith('-'):  # This is a group/channel
                return  # Stay silent in groups
            
            if not self.is_user_authorized(user_id):
                self._handle_unauthorized_user(chat_id, user_id, user_info)
                return
            self.send_message(chat_id, "Unknown command. Type /help for available commands.")
    
    def start_add_post_flow(self, chat_id: str, user_id: int):
        """Start the add post flow."""
        # Only allow post management in private chats
        if chat_id.startswith('-'):  # This is a group/channel
            return  # Stay silent in groups
        
        self.user_states[user_id] = {
            'state': 'waiting_for_content',
            'post_data': {}
        }
        
        text = """
📝 <b>Add New Post - Step 1/4</b>

Please send me the text content for your post.

You can:
• Send text content (for posts with caption)
• Use the "Skip Text" button below (for photo-only posts)
• Type "skip" if you prefer text input
        """
        
        # Add skip button
        reply_markup = {
            "inline_keyboard": [
                [{"text": "⏭️ Skip Text", "callback_data": "skip_text"}]
            ]
        }
        
        self.send_message(chat_id, text, reply_markup)
    
    def show_posts_list(self, chat_id: str, user_id: int):
        """Show list of scheduled posts with actual photos and captions."""
        # Only allow post management in private chats
        if chat_id.startswith('-'):  # This is a group/channel
            return  # Stay silent in groups
        
        posts = self.get_posts()
        
        if not posts:
            self.send_message(chat_id, "📭 No scheduled posts found.\n\nUse /add to create your first post!")
            return
        
        # Send header message
        header_text = f"📋 <b>Scheduled Posts ({len(posts)} total):</b>\n\nShowing actual posts as they will appear:"
        self.send_message(chat_id, header_text)
        
        # Send each post individually with its actual content
        for i, post in enumerate(posts[:10], 1):  # Limit to 10 posts for display
            # Format scheduled time
            try:
                dt = datetime.datetime.fromisoformat(post['scheduled_time'])
                time_str = dt.strftime("%B %d, %Y at %H:%M")
            except:
                time_str = post['scheduled_time']
            
            # Format post info
            recurring = "🔄 Weekday recurring" if post['is_recurring'] else "📅 One-time"
            post_info = f"📋 <b>Post #{post['id']}</b>\n📅 {time_str}\n{recurring}"
            
            # Create delete button for this post
            delete_button = {
                "inline_keyboard": [
                    [
                        {"text": f"🗑️ Delete Post #{post['id']}", "callback_data": f"delete_{post['id']}"}
                        # {"text": f"✏️ Edit #{post['id']}", "callback_data": f"edit_{post['id']}"}  # Commented out for now
                    ]
                ]
            }
            
            # Send the actual post content
            if post['photo_data'] and post['content']:
                # Photo with caption
                caption = f"{post['content']}\n\n{post_info}"
                self.send_photo(chat_id, post['photo_data'], caption, post['photo_filename'])
                # Send management button separately
                self.send_message(chat_id, "👆 Manage this post:", delete_button)
            elif post['photo_data']:
                # Photo only
                caption = f"{post_info}"
                self.send_photo(chat_id, post['photo_data'], caption, post['photo_filename'])
                # Send management button separately
                self.send_message(chat_id, "👆 Manage this post:", delete_button)
            else:
                # Text only
                full_text = f"{post['content']}\n\n{post_info}"
                self.send_message(chat_id, full_text, delete_button)
        
        if len(posts) > 10:
            remaining_text = f"... and {len(posts) - 10} more posts (showing first 10 only)"
            self.send_message(chat_id, remaining_text)
        
        # Add new post button at the end
        add_button = {
            "inline_keyboard": [
                [{"text": "➕ Add New Post", "callback_data": "add_new"}]
            ]
        }
        self.send_message(chat_id, "Create a new scheduled post:", add_button)
    
    def process_message(self, chat_id: str, user_id: int, message_text: str, photo_data: bytes = None, photo_filename: str = None, user_info: Dict = None):
        """Process incoming messages based on user state."""
        user_state = self.user_states.get(user_id)
        
        # Check if user is waiting for password
        if user_state and user_state.get('state') == 'waiting_for_password':
            self._handle_password_attempt(chat_id, user_id, message_text, user_state.get('user_info'))
            return
        
        # Check if we're in edit mode first
        if self._handle_edit_message(chat_id, user_id, message_text, photo_data, photo_filename):
            return
        
        if not user_state:
            # No active state, treat as command
            if message_text.startswith('/'):
                command = message_text.split()[0]
                self.process_command(chat_id, user_id, command, message_text, user_info)
            else:
                # Check if user is authorized before showing help
                if not self.is_user_authorized(user_id):
                    # For group chats, stay completely silent
                    if chat_id.startswith('-'):  # This is a group/channel
                        return
                    # For private chats, handle authentication
                    self._handle_unauthorized_user(chat_id, user_id, user_info)
                    return
                
                # Only respond with help in private chats
                if not chat_id.startswith('-'):  # Private chat only
                    self.send_message(chat_id, "Please use /help to see available commands.")
            return
        
        current_state = user_state['state']
        post_data = user_state['post_data']
        
        if current_state == 'waiting_for_content':
            # Step 1: Get content/caption
            if message_text.lower().strip() == 'skip':
                post_data['content'] = ''
            else:
                post_data['content'] = message_text
            
            # Move to photo step
            user_state['state'] = 'waiting_for_photo'
            text = """
📷 <b>Add New Post - Step 2/4</b>

Now send me a photo for your post:
• Send a photo (for photo-only or photo with caption posts)
• Use "Skip Photo" button below (for text-only posts)
• Send "skip" if you prefer typing

Current content: """ + (f'"{post_data["content"]}"' if post_data['content'] else '[No text]')
            
            # Add skip button for photo step
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "⏭️ Skip Photo", "callback_data": "skip_photo"}]
                ]
            }
            
            self.send_message(chat_id, text, reply_markup)
        
        elif current_state == 'waiting_for_photo':
            # Step 2: Get photo (optional)
            if photo_data:
                post_data['photo_data'] = photo_data
                post_data['photo_filename'] = photo_filename or 'photo.jpg'
                
                response_text = "✅ Photo added!"
                user_state['state'] = 'waiting_for_schedule'
                self._show_calendar_for_scheduling(chat_id, user_id, response_text)
                return
                
            elif message_text.lower().strip() == 'skip':
                response_text = "ℹ️ No photo will be added."
                user_state['state'] = 'waiting_for_schedule'
                self._show_calendar_for_scheduling(chat_id, user_id, response_text)
            else:
                self.send_message(chat_id, "Please send a photo or type 'skip' to continue without photos.")
                return
        
        elif current_state == 'waiting_for_schedule':
            # Step 3: Use calendar interface - don't process text messages here
            # Calendar interaction is handled in callback queries
            self.send_message(chat_id, "Please use the calendar buttons above to select a date.")
        
        elif current_state == 'waiting_for_recurring':
            # Step 4: Get recurring preference
            is_recurring = message_text.lower().strip() in ['yes', 'y', 'daily', 'repeat']
            
            # Create the post
            self.finish_add_post(chat_id, user_id, is_recurring)
    
    def finish_add_post(self, chat_id: str, user_id: int, is_recurring: bool):
        """Finish adding the post and save to database."""
        user_state = self.user_states.get(user_id)
        if not user_state:
            return
        
        post_data = user_state['post_data']
        
        # Validate we have either content or photo
        has_content = bool(post_data.get('content'))
        has_photo = bool(post_data.get('photo_data'))
        
        if not has_content and not has_photo:
            self.send_message(chat_id, "❌ Error: Post must have either text content or a photo!")
            return
        
        # Save to database
        try:
            post_id = self.add_post(
                content=post_data.get('content', ''),
                photo_data=post_data.get('photo_data'),
                photo_filename=post_data.get('photo_filename'),
                scheduled_time=post_data['scheduled_time'],
                is_recurring=is_recurring
            )
            
            # Clear user state
            del self.user_states[user_id]
            
            # Format display info
            display_time = datetime.datetime.fromisoformat(post_data['scheduled_time']).strftime('%Y-%m-%d %H:%M')
            
            # Determine post type
            if post_data.get('photo_data'):
                post_type = "📷 Photo"
            else:
                post_type = "📝 Text"
                
            recurring_info = " (Weekday recurring)" if is_recurring else ""
            
            success_text = f"""
✅ <b>Post Created Successfully!</b>

📋 Post ID: #{post_id}
📝 Type: {post_type}
📅 Scheduled: {display_time}{recurring_info}
💬 Content: {post_data.get('content', '[Photo only]')[:100]}

The post will be automatically published at the scheduled time.
Use /list to manage your posts.
            """
            
            self.send_message(chat_id, success_text)
            
        except Exception as e:
            print(f"Error saving post: {e}")
            self.send_message(chat_id, f"❌ Error saving post: {e}")
    
    def process_callback_query(self, callback_query: Dict):
        """Process inline button callbacks."""
        query_id = callback_query['id']
        callback_data = callback_query['data']
        chat_id = str(callback_query['message']['chat']['id'])
        user_id = callback_query['from']['id']
        message_id = callback_query['message']['message_id']
        
        # Answer callback query to remove loading state
        self.make_request("answerCallbackQuery", {"callback_query_id": query_id})
        
        # For edit operations, ensure they only work in private chats first
        # Note: edit_ callbacks are currently commented out, keeping delete operations only
        if callback_data.startswith(('delete_', 'confirm_delete_', 'cancel_delete_')) and chat_id.startswith('-'):
            # Edit/delete operations in groups are silently ignored
            return
        
        # Check if user is authorized (except for calendar/time navigation and skip buttons)
        if not callback_data.startswith(('cal_', 'time_', 'recurring_', 'skip_')) and not self.is_user_authorized(user_id):
            # For group chats, just ignore unauthorized callback queries silently
            if chat_id.startswith('-'):  # This is a group/channel
                return
            
            # For private chats, handle authentication
            user_info = {
                'user_id': user_id,
                'username': callback_query['from'].get('username'),
                'first_name': callback_query['from'].get('first_name'),
                'last_name': callback_query['from'].get('last_name')
            }
            self._handle_unauthorized_user(chat_id, user_id, user_info)
            return
        
        if callback_data == "add_new":
            self.start_add_post_flow(chat_id, user_id)
        
        elif callback_data.startswith("delete_"):
            post_id = int(callback_data.split("_")[1])
            self.handle_delete_post(chat_id, user_id, message_id, post_id)
        
        # elif callback_data.startswith("edit_"):
        #     post_id = int(callback_data.split("_")[1])
        #     self.handle_edit_post(chat_id, user_id, message_id, post_id)
        
        elif callback_data == "recurring_yes":
            self.finish_add_post(chat_id, user_id, True)
        
        elif callback_data == "recurring_no":
            self.finish_add_post(chat_id, user_id, False)
        
        elif callback_data == "skip_text":
            # User clicked skip text button - proceed to photo step
            user_state = self.user_states.get(user_id)
            if user_state and 'post_data' in user_state:
                user_state['post_data']['content'] = ''
                user_state['state'] = 'waiting_for_photo'
                
                text = """
📷 <b>Add New Post - Step 2/4</b>

Text content skipped. Now send me a photo for your post:

• Send a photo (for photo-only posts)
• Send "skip" to continue without photos (text-only post)
                """
                
                # Add skip button for photo step too
                reply_markup = {
                    "inline_keyboard": [
                        [{"text": "⏭️ Skip Photo", "callback_data": "skip_photo"}]
                    ]
                }
                
                self.edit_message_text(chat_id, message_id, text, reply_markup)
            else:
                self.make_request("answerCallbackQuery", {"callback_query_id": query_id, "text": "Error: Please start over"})
        
        elif callback_data == "skip_photo":
            # User clicked skip photo button - proceed to scheduling
            user_state = self.user_states.get(user_id)
            if user_state and 'post_data' in user_state:
                response_text = "ℹ️ No photo will be added."
                user_state['state'] = 'waiting_for_schedule'
                self._show_calendar_for_scheduling(chat_id, user_id, response_text)
            else:
                self.make_request("answerCallbackQuery", {"callback_query_id": query_id, "text": "Error: Please start over"})
        
        elif callback_data.startswith("confirm_delete_"):
            post_id = int(callback_data.split("_")[2])
            if self.delete_post(post_id):
                self.edit_message_text(chat_id, message_id, f"✅ Post #{post_id} deleted successfully!")
                # Refresh the posts list after a delay
                threading.Timer(2.0, lambda: self.show_posts_list(chat_id, user_id)).start()
            else:
                self.edit_message_text(chat_id, message_id, f"❌ Failed to delete post #{post_id}")
        
        elif callback_data.startswith("cancel_delete_"):
            self.show_posts_list(chat_id, user_id)
        
        # elif callback_data.startswith("edit_text_"):
        #     post_id = int(callback_data.split("_")[2])
        #     self._start_edit_text(chat_id, user_id, message_id, post_id)
        
        # elif callback_data.startswith("edit_photo_"):
        #     post_id = int(callback_data.split("_")[2])
        #     self._start_edit_photo(chat_id, user_id, message_id, post_id)
        
        # elif callback_data.startswith("edit_time_"):
        #     post_id = int(callback_data.split("_")[2])
        #     self._start_edit_time(chat_id, user_id, message_id, post_id)
        
        # elif callback_data.startswith("edit_recurring_"):
        #     post_id = int(callback_data.split("_")[2])
        #     self._toggle_recurring(chat_id, user_id, message_id, post_id)
        
        elif callback_data == "back_to_list":
            # Clear any edit state and show posts list
            if user_id in self.user_states:
                del self.user_states[user_id]
            self.show_posts_list(chat_id, user_id)
        
        # Calendar navigation callbacks
        elif callback_data.startswith("cal_nav_"):
            parts = callback_data.split("_")
            year, month = int(parts[2]), int(parts[3])
            calendar_markup = self.generate_calendar(year, month)
            
            # Update calendar display
            current_text = callback_query['message']['text']
            self.edit_message_text(chat_id, message_id, current_text, calendar_markup)
        
        elif callback_data.startswith("cal_day_"):
            parts = callback_data.split("_")
            year, month, day = int(parts[2]), int(parts[3]), int(parts[4])
            
            # Update calendar with selected day
            calendar_markup = self.generate_calendar(year, month, day)
            current_text = callback_query['message']['text']
            self.edit_message_text(chat_id, message_id, current_text, calendar_markup)
        
        elif callback_data.startswith("cal_confirm_"):
            parts = callback_data.split("_")
            year, month, day = int(parts[2]), int(parts[3]), int(parts[4])
            
            # Store selected date and show time picker
            user_state = self.user_states.get(user_id, {})
            if 'post_data' in user_state:
                user_state['post_data']['selected_date'] = f"{year}-{month:02d}-{day:02d}"
                selected_date_str = datetime.date(year, month, day).strftime("%B %d, %Y")
                self._show_time_picker_for_scheduling(chat_id, user_id, selected_date_str, message_id)
            else:
                # This is an edit operation
                self._handle_calendar_edit_confirm(chat_id, user_id, message_id, year, month, day)
        
        elif callback_data == "cal_cancel":
            # Cancel calendar operation
            user_state = self.user_states.get(user_id)
            if user_state and 'post_data' in user_state:
                # Cancel new post creation
                del self.user_states[user_id]
                self.edit_message_text(chat_id, message_id, "❌ Post creation cancelled.")
            else:
                # Cancel edit operation - clear state and show posts list
                if user_id in self.user_states:
                    del self.user_states[user_id]
                self.show_posts_list(chat_id, user_id)
        
        elif callback_data == "cal_ignore":
            # Ignore calendar header/day clicks
            pass
        
        # Time picker callbacks
        elif callback_data.startswith("time_hour_"):
            parts = callback_data.split("_")
            action = parts[2]  # inc or dec
            hour, minute = int(parts[3]), int(parts[4])
            
            if action == "inc":
                hour = (hour + 1) % 24
            else:  # dec
                hour = (hour - 1) % 24
            
            time_markup = self.generate_time_picker(hour, minute)
            current_text = callback_query['message']['text']
            self.edit_message_text(chat_id, message_id, current_text, time_markup)
        
        elif callback_data.startswith("time_min_"):
            parts = callback_data.split("_")
            action = parts[2]  # inc or dec
            hour, minute = int(parts[3]), int(parts[4])
            
            if action == "inc":
                minute = (minute + 30) % 60
            else:  # dec
                minute = (minute - 30) % 60
            
            time_markup = self.generate_time_picker(hour, minute)
            current_text = callback_query['message']['text']
            self.edit_message_text(chat_id, message_id, current_text, time_markup)
        
        elif callback_data.startswith("time_quick_"):
            parts = callback_data.split("_")
            if parts[2] == "now":
                # Schedule for now
                self._handle_time_confirm_now(chat_id, user_id, message_id)
            else:
                hour, minute = int(parts[2]), int(parts[3])
                # For quick times, automatically confirm the time
                if len(parts) == 4:  # This is a quick time selection
                    self._handle_time_confirm(chat_id, user_id, message_id, hour, minute)
                else:
                    # Just update the display
                    time_markup = self.generate_time_picker(hour, minute)
                    current_text = callback_query['message']['text']
                    self.edit_message_text(chat_id, message_id, current_text, time_markup)
        
        elif callback_data.startswith("time_confirm_"):
            parts = callback_data.split("_")
            hour, minute = int(parts[2]), int(parts[3])
            self._handle_time_confirm(chat_id, user_id, message_id, hour, minute)
        
        elif callback_data == "time_cancel":
            # Cancel time selection - go back to calendar
            user_state = self.user_states.get(user_id)
            if user_state and 'post_data' in user_state:
                # Go back to calendar for new post
                now = datetime.datetime.now()
                calendar_markup = self.generate_calendar(now.year, now.month)
                text = """
📅 <b>Add New Post - Step 3/4</b>

Please select the date when you want this post to be published:

◽ = Past dates (unavailable)
🔹 = Selected date
                """
                self.edit_message_text(chat_id, message_id, text, calendar_markup)
            else:
                # Cancel edit operation - clear state and show posts list
                if user_id in self.user_states:
                    del self.user_states[user_id]
                self.show_posts_list(chat_id, user_id)
        
        elif callback_data == "time_ignore":
            # Ignore time picker header clicks
            pass
    
    def _start_edit_text(self, chat_id: str, user_id: int, message_id: int, post_id: int):
        """Start editing post text."""
        # Set user state
        self.user_states[user_id] = {
            'state': 'editing_text',
            'post_id': post_id,
            'message_id': message_id
        }
        
        # Get current content
        posts = [p for p in self.get_posts(include_posted=True) if p['id'] == post_id]
        if not posts:
            self.edit_message_text(chat_id, message_id, f"❌ Post #{post_id} not found!")
            return
        
        current_content = posts[0]['content'] or "[No text content]"
        
        edit_text = f"""
✏️ <b>Edit Text for Post #{post_id}</b>

Current text:
{current_content}

Please send me the new text content, or send "delete" to remove all text.
        """
        
        self.edit_message_text(chat_id, message_id, edit_text)
    
    def _start_edit_photo(self, chat_id: str, user_id: int, message_id: int, post_id: int):
        """Start editing post photo."""
        # Set user state
        self.user_states[user_id] = {
            'state': 'editing_photo',
            'post_id': post_id,
            'message_id': message_id
        }
        
        # Get current photo status
        posts = [p for p in self.get_posts(include_posted=True) if p['id'] == post_id]
        if not posts:
            self.edit_message_text(chat_id, message_id, f"❌ Post #{post_id} not found!")
            return
        
        has_photo = posts[0]['photo_data'] is not None
        photo_status = "✅ Has photo" if has_photo else "❌ No photo"
        
        edit_text = f"""
📷 <b>Edit Photo for Post #{post_id}</b>

Current status: {photo_status}

Please send me a new photo, or send "delete" to remove the current photo.
        """
        
        self.edit_message_text(chat_id, message_id, edit_text)
    
    def _start_edit_time(self, chat_id: str, user_id: int, message_id: int, post_id: int):
        """Start editing post time."""
        # Set user state
        self.user_states[user_id] = {
            'state': 'editing_time',
            'post_id': post_id,
            'message_id': message_id
        }
        
        # Get current time
        posts = [p for p in self.get_posts(include_posted=True) if p['id'] == post_id]
        if not posts:
            self.edit_message_text(chat_id, message_id, f"❌ Post #{post_id} not found!")
            return
        
        try:
            current_time = datetime.datetime.fromisoformat(posts[0]['scheduled_time'])
            display_time = current_time.strftime('%B %d, %Y at %H:%M')
        except:
            display_time = posts[0]['scheduled_time']
        
        # Show calendar for date selection
        now = datetime.datetime.now()
        calendar_markup = self.generate_calendar(now.year, now.month)
        
        edit_text = f"""
📅 <b>Edit Schedule for Post #{post_id}</b>

Current schedule: <b>{display_time}</b>

Please select a new date:

◽ = Past dates (unavailable)
🔹 = Selected date
        """
        
        self.edit_message_text(chat_id, message_id, edit_text, calendar_markup)
    
    def _toggle_recurring(self, chat_id: str, user_id: int, message_id: int, post_id: int):
        """Toggle recurring status for a post."""
        posts = [p for p in self.get_posts(include_posted=True) if p['id'] == post_id]
        if not posts:
            self.edit_message_text(chat_id, message_id, f"❌ Post #{post_id} not found!")
            return
        
        current_recurring = posts[0]['is_recurring']
        new_recurring = not current_recurring
        
        # Update the post
        if self.update_post(post_id, is_recurring=int(new_recurring)):
            status = "🔄 Weekday recurring" if new_recurring else "📅 One-time"
            self.edit_message_text(chat_id, message_id, f"✅ Post #{post_id} updated!\n\nNew status: {status}")
            
            # Return to post list after a delay
            threading.Timer(2.0, lambda: self.show_posts_list(chat_id, user_id)).start()
        else:
            self.edit_message_text(chat_id, message_id, f"❌ Failed to update post #{post_id}")
    
    def _handle_edit_message(self, chat_id: str, user_id: int, message_text: str, photo_data: bytes = None, photo_filename: str = None):
        """Handle messages during edit mode."""
        user_state = self.user_states.get(user_id)
        if not user_state or not user_state['state'].startswith('editing_'):
            return False
        
        post_id = user_state['post_id']
        edit_state = user_state['state']
        message_id = user_state.get('message_id')
        
        if edit_state == 'editing_text':
            if message_text.lower().strip() == 'delete':
                new_content = ''
                success_msg = "✅ Text content removed!"
            else:
                new_content = message_text
                success_msg = "✅ Text content updated!"
            
            if self.update_post(post_id, content=new_content):
                self.send_message(chat_id, success_msg)
            else:
                self.send_message(chat_id, f"❌ Failed to update post #{post_id}")
        
        elif edit_state == 'editing_photo':
            if message_text.lower().strip() == 'delete':
                # Remove photo
                if self.update_post(post_id, photo_data=None, photo_filename=None):
                    self.send_message(chat_id, "✅ Photo removed!")
                else:
                    self.send_message(chat_id, f"❌ Failed to update post #{post_id}")
            elif photo_data:
                # Update photo
                if self.update_post(post_id, photo_data=photo_data, photo_filename=photo_filename):
                    self.send_message(chat_id, "✅ Photo updated!")
                else:
                    self.send_message(chat_id, f"❌ Failed to update post #{post_id}")
            else:
                self.send_message(chat_id, "Please send a photo or type 'delete' to remove the current photo.")
                return True
        
        elif edit_state == 'editing_time':
            # Time editing now uses calendar interface - no text input
            self.send_message(chat_id, "Please use the calendar interface above to select date and time.")
            return True
        
        # Clear user state and return to post list
        del self.user_states[user_id]
        threading.Timer(2.0, lambda: self.show_posts_list(chat_id, user_id)).start()
        return True
    
    def handle_delete_post(self, chat_id: str, user_id: int, message_id: int, post_id: int):
        """Handle post deletion with confirmation."""
        # Get post details
        posts = [p for p in self.get_posts(include_posted=True) if p['id'] == post_id]
        if not posts:
            self.edit_message_text(chat_id, message_id, f"❌ Post #{post_id} not found!")
            return
        
        post = posts[0]
        content_preview = post['content'][:100] + "..." if len(post['content']) > 100 else post['content']
        if not content_preview:
            content_preview = "[Photo only]"
        
        confirm_text = f"""
🗑️ <b>Delete Post #{post_id}?</b>

Content: {content_preview}

This action cannot be undone!
        """
        
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "✅ Yes, Delete", "callback_data": f"confirm_delete_{post_id}"},
                    {"text": "❌ Cancel", "callback_data": f"cancel_delete_{post_id}"}
                ]
            ]
        }
        
        self.edit_message_text(chat_id, message_id, confirm_text, reply_markup)
    
    def handle_edit_post(self, chat_id: str, user_id: int, message_id: int, post_id: int):
        """Handle post editing."""
        # Get post details
        posts = [p for p in self.get_posts(include_posted=True) if p['id'] == post_id]
        if not posts:
            self.edit_message_text(chat_id, message_id, f"❌ Post #{post_id} not found!")
            return
        
        post = posts[0]
        
        # Set user state for editing
        self.user_states[user_id] = {
            'state': 'editing_post',
            'post_id': post_id,
            'edit_type': None
        }
        
        # Format current post info
        content_preview = post['content'][:200] + "..." if len(post['content']) > 200 else post['content']
        if not content_preview:
            content_preview = "[No text content]"
        
        try:
            display_time = datetime.datetime.fromisoformat(post['scheduled_time']).strftime('%Y-%m-%d %H:%M')
        except:
            display_time = post['scheduled_time']
        
        post_type = "📷 Photo + Text" if post['photo_data'] and post['content'] else ("📷 Photo only" if post['photo_data'] else "📝 Text only")
        recurring = "🔄 Weekday recurring" if post['is_recurring'] else "📅 One-time"
        
        edit_text = f"""
✏️ <b>Edit Post #{post_id}</b>

📝 Type: {post_type}
📅 Scheduled: {display_time}
🔄 Repeat: {recurring}
💬 Content: {content_preview}

What would you like to edit?
        """
        
        reply_markup = {
            "inline_keyboard": [
                [{"text": "📝 Edit Text", "callback_data": f"edit_text_{post_id}"}],
                [{"text": "📷 Change Photo", "callback_data": f"edit_photo_{post_id}"}],
                [{"text": "📅 Change Time", "callback_data": f"edit_time_{post_id}"}],
                [{"text": "🔄 Toggle Recurring", "callback_data": f"edit_recurring_{post_id}"}],
                [{"text": "⬅️ Back to List", "callback_data": "back_to_list"}]
            ]
        }
        
        self.edit_message_text(chat_id, message_id, edit_text, reply_markup)
    
    def generate_calendar(self, year: int, month: int, selected_day: int = None) -> Dict:
        """Generate calendar inline keyboard for date selection."""
        # Month names
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        
        # Calendar header with navigation
        keyboard = []
        
        # Navigation row: < Month Year >
        nav_row = []
        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        
        nav_row.append({"text": "◀️", "callback_data": f"cal_nav_{prev_year}_{prev_month}"})
        nav_row.append({"text": f"{month_names[month-1]} {year}", "callback_data": "cal_ignore"})
        nav_row.append({"text": "▶️", "callback_data": f"cal_nav_{next_year}_{next_month}"})
        keyboard.append(nav_row)
        
        # Weekday headers
        weekday_row = []
        for day in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            weekday_row.append({"text": day, "callback_data": "cal_ignore"})
        keyboard.append(weekday_row)
        
        # Calendar days
        cal = calendar.monthcalendar(year, month)
        today = datetime.date.today()
        
        for week in cal:
            week_row = []
            for day in week:
                if day == 0:
                    # Empty cell
                    week_row.append({"text": " ", "callback_data": "cal_ignore"})
                else:
                    # Check if this is today or in the past
                    day_date = datetime.date(year, month, day)
                    
                    if day_date < today:
                        # Past date - disabled
                        week_row.append({"text": f"◽{day}", "callback_data": "cal_ignore"})
                    elif day == selected_day:
                        # Selected day
                        week_row.append({"text": f"🔹{day}", "callback_data": f"cal_day_{year}_{month}_{day}"})
                    else:
                        # Available day
                        week_row.append({"text": str(day), "callback_data": f"cal_day_{year}_{month}_{day}"})
            keyboard.append(week_row)
        
        # Control row
        control_row = []
        if selected_day:
            control_row.append({"text": "✅ Confirm Date", "callback_data": f"cal_confirm_{year}_{month}_{selected_day}"})
        control_row.append({"text": "❌ Cancel", "callback_data": "cal_cancel"})
        keyboard.append(control_row)
        
        return {"inline_keyboard": keyboard}
    
    def generate_time_picker(self, hour: int = 12, minute: int = 0) -> Dict:
        """Generate simplified time picker inline keyboard."""
        keyboard = []
        
        # Current time display
        time_display_row = []
        time_display_row.append({"text": f"🕐 Selected: {hour:02d}:{minute:02d}", "callback_data": "time_ignore"})
        keyboard.append(time_display_row)
        
        # Quick time buttons - Morning
        morning_row1 = []
        morning_row1.append({"text": "08:00", "callback_data": "time_quick_8_0"})
        morning_row1.append({"text": "08:30", "callback_data": "time_quick_8_30"})
        morning_row1.append({"text": "09:00", "callback_data": "time_quick_9_0"})
        morning_row1.append({"text": "09:30", "callback_data": "time_quick_9_30"})
        keyboard.append(morning_row1)
        
        morning_row2 = []
        morning_row2.append({"text": "10:00", "callback_data": "time_quick_10_0"})
        morning_row2.append({"text": "10:30", "callback_data": "time_quick_10_30"})
        morning_row2.append({"text": "11:00", "callback_data": "time_quick_11_0"})
        morning_row2.append({"text": "11:30", "callback_data": "time_quick_11_30"})
        keyboard.append(morning_row2)
        
        # Quick time buttons - Afternoon
        afternoon_row1 = []
        afternoon_row1.append({"text": "12:00", "callback_data": "time_quick_12_0"})
        afternoon_row1.append({"text": "12:30", "callback_data": "time_quick_12_30"})
        afternoon_row1.append({"text": "14:00", "callback_data": "time_quick_14_0"})
        afternoon_row1.append({"text": "14:30", "callback_data": "time_quick_14_30"})
        keyboard.append(afternoon_row1)
        
        afternoon_row2 = []
        afternoon_row2.append({"text": "16:00", "callback_data": "time_quick_16_0"})
        afternoon_row2.append({"text": "16:30", "callback_data": "time_quick_16_30"})
        afternoon_row2.append({"text": "18:00", "callback_data": "time_quick_18_0"})
        afternoon_row2.append({"text": "18:30", "callback_data": "time_quick_18_30"})
        keyboard.append(afternoon_row2)
        
        # Quick time buttons - Evening
        evening_row1 = []
        evening_row1.append({"text": "20:00", "callback_data": "time_quick_20_0"})
        evening_row1.append({"text": "20:30", "callback_data": "time_quick_20_30"})
        evening_row1.append({"text": "21:00", "callback_data": "time_quick_21_0"})
        evening_row1.append({"text": "21:30", "callback_data": "time_quick_21_30"})
        keyboard.append(evening_row1)
        
        evening_row2 = []
        evening_row2.append({"text": "22:00", "callback_data": "time_quick_22_0"})
        evening_row2.append({"text": "22:30", "callback_data": "time_quick_22_30"})
        evening_row2.append({"text": "Now", "callback_data": "time_quick_now"})
        keyboard.append(evening_row2)
        
        # Fine adjustment row (only if not using quick time)
        quick_times = [8, 9, 10, 11, 12, 14, 16, 18, 20, 21, 22]
        quick_minutes = [0, 30]
        if hour not in quick_times or minute not in quick_minutes:
            adjust_row = []
            adjust_row.append({"text": "Hour -", "callback_data": f"time_hour_dec_{hour}_{minute}"})
            adjust_row.append({"text": "Hour +", "callback_data": f"time_hour_inc_{hour}_{minute}"})
            adjust_row.append({"text": "Min -", "callback_data": f"time_min_dec_{hour}_{minute}"})
            adjust_row.append({"text": "Min +", "callback_data": f"time_min_inc_{hour}_{minute}"})
            keyboard.append(adjust_row)
        
        # Control row
        control_row = []
        control_row.append({"text": "✅ Confirm Time", "callback_data": f"time_confirm_{hour}_{minute}"})
        control_row.append({"text": "❌ Cancel", "callback_data": "time_cancel"})
        keyboard.append(control_row)
        
        return {"inline_keyboard": keyboard}
    
    def _show_calendar_for_scheduling(self, chat_id: str, user_id: int, status_text: str):
        """Show calendar for scheduling a post."""
        now = datetime.datetime.now()
        
        text = f"""
📅 <b>Add New Post - Step 3/4</b>

{status_text}

Please select the date when you want this post to be published:

◽ = Past dates (unavailable)
🔹 = Selected date
        """
        
        calendar_markup = self.generate_calendar(now.year, now.month)
        self.send_message(chat_id, text, calendar_markup)
    
    def _show_time_picker_for_scheduling(self, chat_id: str, user_id: int, selected_date: str, message_id: int = None):
        """Show time picker after date is selected."""
        now = datetime.datetime.now()
        default_hour = now.hour + 1 if now.hour < 23 else 12
        default_minute = 0
        
        text = f"""
⏰ <b>Add New Post - Step 3/4</b>

Selected date: <b>{selected_date}</b>

Choose a time by tapping one of the quick time buttons below:
        """
        
        time_markup = self.generate_time_picker(default_hour, default_minute)
        
        if message_id:
            self.edit_message_text(chat_id, message_id, text, time_markup)
        else:
            self.send_message(chat_id, text, time_markup)
    
    def _handle_time_confirm_now(self, chat_id: str, user_id: int, message_id: int):
        """Handle 'now' time selection."""
        user_state = self.user_states.get(user_id)
        if not user_state:
            return
        
        if 'post_data' in user_state:
            # New post creation
            post_data = user_state['post_data']
            now = datetime.datetime.now()
            scheduled_time = now.isoformat()
            post_data['scheduled_time'] = scheduled_time
            
            # Move to recurring step
            user_state['state'] = 'waiting_for_recurring'
            
            text = f"""
🔄 <b>Add New Post - Step 4/4</b>

Scheduled for: <b>Now (immediately)</b>

Should this post repeat on weekdays (Monday-Friday) at the same time?
            """
            
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "🔄 Yes, repeat on weekdays", "callback_data": "recurring_yes"},
                        {"text": "📅 No, one time only", "callback_data": "recurring_no"}
                    ]
                ]
            }
            
            self.edit_message_text(chat_id, message_id, text, reply_markup)
        else:
            # Edit operation
            self._handle_edit_time_confirm_now(chat_id, user_id, message_id)
    
    def _handle_time_confirm(self, chat_id: str, user_id: int, message_id: int, hour: int, minute: int):
        """Handle time confirmation."""
        user_state = self.user_states.get(user_id)
        if not user_state:
            return
        
        if 'post_data' in user_state:
            # New post creation
            post_data = user_state['post_data']
            selected_date = post_data.get('selected_date')
            if not selected_date:
                self.edit_message_text(chat_id, message_id, "❌ Error: No date selected!")
                return
            
            # Combine date and time
            try:
                date_obj = datetime.datetime.strptime(selected_date, '%Y-%m-%d')
                scheduled_datetime = date_obj.replace(hour=hour, minute=minute)
                
                # Check if in the past
                if scheduled_datetime < datetime.datetime.now():
                    self.edit_message_text(chat_id, message_id, "❌ Cannot schedule posts in the past! Please select a future time.")
                    return
                
                post_data['scheduled_time'] = scheduled_datetime.isoformat()
                
                # Move to recurring step
                user_state['state'] = 'waiting_for_recurring'
                
                display_time = scheduled_datetime.strftime('%B %d, %Y at %H:%M')
                
                text = f"""
🔄 <b>Add New Post - Step 4/4</b>

Scheduled for: <b>{display_time}</b>

Should this post repeat on weekdays (Monday-Friday) at the same time?
                """
                
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {"text": "🔄 Yes, repeat on weekdays", "callback_data": "recurring_yes"},
                            {"text": "📅 No, one time only", "callback_data": "recurring_no"}
                        ]
                    ]
                }
                
                self.edit_message_text(chat_id, message_id, text, reply_markup)
                
            except Exception as e:
                self.edit_message_text(chat_id, message_id, f"❌ Error processing date/time: {e}")
        else:
            # Edit operation
            self._handle_edit_time_confirm(chat_id, user_id, message_id, hour, minute)
    
    def _handle_calendar_edit_confirm(self, chat_id: str, user_id: int, message_id: int, year: int, month: int, day: int):
        """Handle calendar confirmation for edit operations."""
        user_state = self.user_states.get(user_id)
        if not user_state or user_state.get('state') != 'editing_time':
            return
        
        # Store selected date and show time picker
        user_state['selected_date'] = f"{year}-{month:02d}-{day:02d}"
        selected_date_str = datetime.date(year, month, day).strftime("%B %d, %Y")
        
        # Get current post to show current time as default
        post_id = user_state['post_id']
        posts = [p for p in self.get_posts(include_posted=True) if p['id'] == post_id]
        if posts:
            try:
                current_time = datetime.datetime.fromisoformat(posts[0]['scheduled_time'])
                default_hour, default_minute = current_time.hour, current_time.minute
            except:
                default_hour, default_minute = 12, 0
        else:
            default_hour, default_minute = 12, 0
        
        text = f"""
⏰ <b>Edit Schedule for Post #{post_id}</b>

Selected date: <b>{selected_date_str}</b>

Choose a time by tapping one of the quick time buttons below:
        """
        
        time_markup = self.generate_time_picker(default_hour, default_minute)
        self.edit_message_text(chat_id, message_id, text, time_markup)
    
    def _handle_edit_time_confirm_now(self, chat_id: str, user_id: int, message_id: int):
        """Handle 'now' time selection for edit operations."""
        user_state = self.user_states.get(user_id)
        if not user_state or user_state.get('state') != 'editing_time':
            return
        
        post_id = user_state['post_id']
        now = datetime.datetime.now()
        
        if self.update_post(post_id, scheduled_time=now.isoformat()):
            self.edit_message_text(chat_id, message_id, "✅ Post scheduled for immediate posting!")
        else:
            self.edit_message_text(chat_id, message_id, f"❌ Failed to update post #{post_id}")
        
        # Clear user state and return to post list
        del self.user_states[user_id]
        threading.Timer(2.0, lambda: self.show_posts_list(chat_id, user_id)).start()
    
    def _handle_edit_time_confirm(self, chat_id: str, user_id: int, message_id: int, hour: int, minute: int):
        """Handle time confirmation for edit operations."""
        user_state = self.user_states.get(user_id)
        if not user_state or user_state.get('state') != 'editing_time':
            return
        
        post_id = user_state['post_id']
        selected_date = user_state.get('selected_date')
        
        if not selected_date:
            self.edit_message_text(chat_id, message_id, "❌ Error: No date selected!")
            return
        
        try:
            date_obj = datetime.datetime.strptime(selected_date, '%Y-%m-%d')
            scheduled_datetime = date_obj.replace(hour=hour, minute=minute)
            
            # Check if in the past
            if scheduled_datetime < datetime.datetime.now():
                self.edit_message_text(chat_id, message_id, "❌ Cannot schedule posts in the past! Please select a future time.")
                return
            
            if self.update_post(post_id, scheduled_time=scheduled_datetime.isoformat()):
                display_time = scheduled_datetime.strftime('%B %d, %Y at %H:%M')
                self.edit_message_text(chat_id, message_id, f"✅ Post #{post_id} rescheduled for {display_time}!")
            else:
                self.edit_message_text(chat_id, message_id, f"❌ Failed to update post #{post_id}")
            
            # Clear user state and return to post list
            del self.user_states[user_id]
            threading.Timer(2.0, lambda: self.show_posts_list(chat_id, user_id)).start()
            
        except Exception as e:
            self.edit_message_text(chat_id, message_id, f"❌ Error processing date/time: {e}")
    
    def start_scheduler(self):
        """Start the post scheduler in a separate thread."""
        if self.scheduler_running:
            return
        
        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        print("📅 Post scheduler started!")
    
    def stop_scheduler(self):
        """Stop the post scheduler."""
        self.scheduler_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        print("📅 Post scheduler stopped!")
    
    def _scheduler_loop(self):
        """Main scheduler loop that checks for posts to publish."""
        while self.scheduler_running:
            try:
                self._check_and_publish_posts()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"Scheduler error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _check_and_publish_posts(self):
        """Check for posts that need to be published now."""
        now = datetime.datetime.now()
        
        # Get all unpublished posts
        posts = self.get_posts()
        
        # Debug: Print post structure (commented out)
        # if posts:
        #     print(f"DEBUG: Processing {len(posts)} posts")
        #     for post in posts:
        #         print(f"DEBUG: Post {post['id']} - scheduled_time: {type(post['scheduled_time'])} = {post['scheduled_time']}")
        
        for post in posts:
            try:
                # Validate scheduled_time is a string
                if not isinstance(post['scheduled_time'], str):
                    print(f"Error: Post {post['id']} has invalid scheduled_time type: {type(post['scheduled_time'])} = {post['scheduled_time']}")
                    continue
                
                scheduled_time = datetime.datetime.fromisoformat(post['scheduled_time'])
                
                # Check if it's time to publish
                if scheduled_time <= now:
                    self._publish_post(post)
            except Exception as e:
                print(f"Error processing post {post['id']}: {e}")
                print(f"Post data: {post}")
    
    def _publish_post(self, post: Dict):
        """Publish a single post to the target chat."""
        try:
            post_id = post['id']
            content = post['content']
            photo_data = post['photo_data']
            
            print(f"📤 Publishing post {post_id}...")
            
            # Send the post
            if photo_data and content:
                # Photo with caption
                result = self.send_photo(self.target_chat_id, photo_data, content, post['photo_filename'])
            elif photo_data:
                # Photo only
                result = self.send_photo(self.target_chat_id, photo_data, "", post['photo_filename'])
            else:
                # Text only
                result = self.send_message(self.target_chat_id, content)
            
            if result.get('ok'):
                print(f"✅ Post {post_id} published successfully!")
                
                # Handle recurring posts
                if post['is_recurring']:
                    # Schedule next occurrence (weekdays only - skip weekends)
                    try:
                        current_time = datetime.datetime.fromisoformat(post['scheduled_time'])
                        next_time = self._get_next_weekday(current_time)
                        
                        # Update the scheduled time for next occurrence
                        self.update_post(post_id, scheduled_time=next_time.isoformat(), is_posted=0)
                        print(f"🔄 Post {post_id} rescheduled for {next_time.strftime('%Y-%m-%d %H:%M')} (weekday)")
                    except Exception as e:
                        print(f"Error rescheduling recurring post {post_id}: {e}")
                        # Mark as posted anyway to prevent infinite retries
                        self.mark_post_as_posted(post_id)
                else:
                    # Mark one-time post as completed
                    self.mark_post_as_posted(post_id)
                    print(f"✅ Post {post_id} marked as completed")
            else:
                print(f"❌ Failed to publish post {post_id}: {result}")
                
        except Exception as e:
            print(f"Error publishing post {post['id']}: {e}")
    
    def run(self):
        """Main bot loop to handle updates."""
        print("🤖 Bot started! Listening for messages...")
        
        # Start the scheduler
        self.start_scheduler()
        
        offset = 0
        
        try:
            while True:
                # Get updates from Telegram
                updates = self.get_updates(offset)
                
                if not updates.get('ok'):
                    print(f"Error getting updates: {updates}")
                    time.sleep(5)
                    continue
                
                # Process each update
                for update in updates.get('result', []):
                    try:
                        offset = update['update_id'] + 1
                        self._process_update(update)
                    except Exception as e:
                        print(f"Error processing update: {e}")
                
                # Small delay to prevent API rate limiting
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n🛑 Bot stopping...")
        finally:
            self.stop_scheduler()
    
    def _process_update(self, update: Dict):
        """Process a single update from Telegram."""
        if 'message' in update:
            self._handle_message(update['message'])
        elif 'callback_query' in update:
            self.process_callback_query(update['callback_query'])
    
    def _handle_message(self, message: Dict):
        """Handle incoming message."""
        chat_id = str(message['chat']['id'])
        user_id = message['from']['id']
        
        # Get user info for authentication
        user_info = {
            'user_id': user_id,
            'username': message['from'].get('username'),
            'first_name': message['from'].get('first_name'),
            'last_name': message['from'].get('last_name')
        }
        
        # Get message text
        message_text = message.get('text', '')
        
        # Handle photo
        photo_data = None
        photo_filename = None
        
        if 'photo' in message:
            # Get the largest photo
            photos = message['photo']
            largest_photo = max(photos, key=lambda p: p['file_size'])
            
            # Get file info
            file_info = self.make_request("getFile", {"file_id": largest_photo['file_id']})
            if file_info.get('ok'):
                file_path = file_info['result']['file_path']
                
                # Download the file
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                
                try:
                    with urllib.request.urlopen(download_url) as response:
                        photo_data = response.read()
                        photo_filename = file_path.split('/')[-1]
                except Exception as e:
                    print(f"Error downloading photo: {e}")
        
        # Process the message
        self.process_message(chat_id, user_id, message_text, photo_data, photo_filename, user_info)

def main():
    """Main function to run the bot."""
    # Try to import configuration
    try:
        from config import BOT_TOKEN, TARGET_CHAT_ID, ACCESS_PASSWORD
    except ImportError:
        print("❌ Configuration file not found!")
        print("Please create config.py file with your bot token, chat ID, and access password.")
        print("See config.py for reference.")
        return
    
    # Validate configuration
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or TARGET_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("❌ Please configure BOT_TOKEN and TARGET_CHAT_ID in config.py!")
        print("Check config.py for instructions on how to get these values.")
        return
    
    if not BOT_TOKEN or not TARGET_CHAT_ID:
        print("❌ BOT_TOKEN and TARGET_CHAT_ID are required!")
        return
    
    if not ACCESS_PASSWORD:
        print("❌ ACCESS_PASSWORD is required in config.py!")
        return
    
    print(f"🔐 Bot access password is set. Users will need to authenticate.")
    print(f"💡 To change the password, edit ACCESS_PASSWORD in config.py")
    
    # Create bot instance
    bot = TelegramBot(BOT_TOKEN, TARGET_CHAT_ID)
    
    print("Bot is starting...")
    print("Use Ctrl+C to stop the bot")
    
    try:
        # Start the bot
        bot.run()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Bot error: {e}")
    finally:
        # Clean up
        if hasattr(bot, 'conn'):
            bot.conn.close()


if __name__ == "__main__":
    # For Render compatibility - start a simple web server
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting web server on port {port}")
    
    # Simple HTTP server
    import http.server
    import socketserver
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        print("Web server started")
        # Start in background
        import threading
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
        
        # Start your bot
        main()
