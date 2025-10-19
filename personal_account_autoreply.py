#!/usr/bin/env python3
"""
Personal Telegram Account Auto-Reply Bot
Uses Pyrogram to read and reply to DMs on your personal account
"""

import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
import sqlite3
from datetime import datetime, timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PersonalAccountBot:
    def __init__(self):
        # Get from https://my.telegram.org/apps
        self.api_id = int(os.getenv('TELEGRAM_API_ID', '0'))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '')
        
        if self.api_id == 0 or not self.api_hash:
            raise ValueError("Please set TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables")
        
        # Session name - will create a file to save login
        self.app = Client(
            "my_personal_account",
            api_id=self.api_id,
            api_hash=self.api_hash
        )
        
        # Database for tracking auto-replies (prevent spam)
        self.db_path = 'personal_autoreplies.db'
        self.init_database()
        
        # Default auto-reply message
        self.auto_reply_message = os.getenv(
            'AUTO_REPLY_MESSAGE',
            "🤖 Automatic Reply:\n\n"
            "Thank you for your message! I'm currently unavailable. "
            "I'll respond as soon as possible.\n\n"
            "For urgent matters, please contact: @support"
        )
        
        # Rate limiting: Max 1 auto-reply per user per 24 hours
        self.reply_cooldown_hours = 24
    
    def init_database(self):
        """Initialize database to track auto-replies"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_replies (
                user_id INTEGER PRIMARY KEY,
                last_reply_time DATETIME,
                reply_count INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized for personal account bot")
    
    def should_auto_reply(self, user_id: int) -> bool:
        """Check if we should auto-reply to this user (rate limiting)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT last_reply_time FROM auto_replies WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True  # First time, allow
        
        last_reply = datetime.fromisoformat(result[0])
        time_since_reply = datetime.now() - last_reply
        
        # Allow if cooldown period has passed
        return time_since_reply > timedelta(hours=self.reply_cooldown_hours)
    
    def record_auto_reply(self, user_id: int):
        """Record that we sent an auto-reply"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO auto_replies (user_id, last_reply_time, reply_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                last_reply_time = ?,
                reply_count = reply_count + 1
        ''', (user_id, datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    async def handle_incoming_dm(self, client: Client, message: Message):
        """Handle incoming private messages"""
        # Ignore if message is from yourself
        if message.from_user.is_self:
            logger.info("Ignoring message from self")
            return
        
        # Ignore if message is outgoing (you sent it)
        if message.outgoing:
            logger.info("Ignoring outgoing message")
            return
        
        user_id = message.from_user.id
        username = message.from_user.username or "Unknown"
        
        logger.info(f"Received DM from {username} (ID: {user_id}): {message.text[:50] if message.text else 'Media'}")
        
        # Check rate limiting
        if not self.should_auto_reply(user_id):
            logger.info(f"Skipping auto-reply for {username} (cooldown active)")
            return
        
        # Send auto-reply
        try:
            await message.reply_text(self.auto_reply_message)
            self.record_auto_reply(user_id)
            logger.info(f"✅ Sent auto-reply to {username} (ID: {user_id})")
        except Exception as e:
            logger.error(f"Failed to send auto-reply: {e}")
    
    def run(self):
        """Start the personal account bot"""
        logger.info("Starting Personal Account Auto-Reply Bot...")
        
        # Register handler for incoming private messages
        @self.app.on_message(filters.private & filters.incoming)
        async def on_private_message(client: Client, message: Message):
            await self.handle_incoming_dm(client, message)
        
        # Start the client
        logger.info("Bot is running and monitoring your personal DMs...")
        logger.info(f"Auto-reply message: {self.auto_reply_message[:100]}...")
        logger.info(f"Cooldown period: {self.reply_cooldown_hours} hours per user")
        
        self.app.run()

if __name__ == '__main__':
    try:
        bot = PersonalAccountBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise
