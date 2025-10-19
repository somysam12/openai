#!/usr/bin/env python3
import os
import logging
import sqlite3
import re
import threading
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI
from flask import Flask

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/health')
def health_check():
    return {'status': 'ok', 'message': 'Bot is running'}, 200

@app.route('/')
def home():
    return {'status': 'ok', 'message': 'Telegram Bot is active'}, 200

def run_flask():
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def escape_markdown(text):
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join('\\' + char if char in escape_chars else char for char in str(text))

class TelegramChatBot:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.admin_id = int(os.getenv('ADMIN_ID', '0'))
        
        if not self.telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        if self.admin_id == 0:
            logger.warning("ADMIN_ID not set! Admin features will not work.")
        
        # Load multiple API keys from environment variables
        self.api_keys = []
        for i in range(1, 20):  # Support up to 20 API keys
            key = os.getenv(f'OPENAI_API_KEY_{i}')
            if key:
                self.api_keys.append(key)
        
        # Also check for single OPENAI_API_KEY (backward compatibility)
        single_key = os.getenv('OPENAI_API_KEY')
        if single_key and single_key not in self.api_keys:
            self.api_keys.insert(0, single_key)
        
        if not self.api_keys:
            raise ValueError("No OPENAI_API_KEY found! Set OPENAI_API_KEY_1, OPENAI_API_KEY_2, etc.")
        
        logger.info(f"✅ Loaded {len(self.api_keys)} API keys for rotation")
        
        # API key rotation setup
        # max_retries=0 disables OpenAI's built-in retry for instant key switching
        self.current_key_index = 0
        self.openai_client = OpenAI(api_key=self.api_keys[self.current_key_index], max_retries=0)
        
        self.db_path = 'chat_history.db'
        self.active_admin_chats = {}
        self.user_to_admin_chat = {}
        self.admin_state = {}
        self.active_group_sessions = {}
        self.group_to_admin = {}
        self.init_database()
    
    def rotate_api_key(self):
        """Rotate to the next available API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        new_key = self.api_keys[self.current_key_index]
        # max_retries=0 disables OpenAI's built-in retry mechanism for instant switching
        self.openai_client = OpenAI(api_key=new_key, max_retries=0)
        logger.warning(f"🔄 Rotated to API key #{self.current_key_index + 1} (out of {len(self.api_keys)} keys)")
        return self.current_key_index + 1
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                session_context TEXT,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_text TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS all_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                response TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS automated_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_type TEXT UNIQUE NOT NULL,
                message_text TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_key_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_index INTEGER NOT NULL UNIQUE,
                usage_count INTEGER DEFAULT 0,
                last_used DATETIME,
                rate_limit_hits INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_registry (
                group_id INTEGER PRIMARY KEY,
                title TEXT,
                username TEXT,
                chat_type TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0
            )
        ''')
        
        try:
            cursor.execute('ALTER TABLE chat_history ADD COLUMN message_role TEXT DEFAULT "user"')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE chat_history ADD COLUMN chat_type TEXT DEFAULT "dm"')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE chat_history ADD COLUMN chat_id INTEGER')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat_history(user_id, timestamp DESC)')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_chat_type_time ON chat_history(chat_type, chat_id, timestamp DESC)')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_api_key_stats_key ON api_key_stats(key_index)')
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def is_admin(self, user_id: int) -> bool:
        return user_id == self.admin_id
    
    def get_automated_message(self, message_type: str):
        """Get automated message by type"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT message_text FROM automated_messages WHERE message_type = ?', (message_type,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def set_automated_message(self, message_type: str, message_text: str):
        """Set or update automated message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO automated_messages (message_type, message_text, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(message_type) DO UPDATE SET
                message_text = ?,
                updated_at = CURRENT_TIMESTAMP
        ''', (message_type, message_text, message_text))
        
        conn.commit()
        conn.close()
    
    def get_all_automated_messages(self):
        """Get all automated messages"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT message_type, message_text, updated_at FROM automated_messages ORDER BY message_type')
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def track_api_key_usage(self, key_index: int, is_rate_limit: bool = False):
        """Track API key usage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if is_rate_limit:
            cursor.execute('''
                INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits)
                VALUES (?, 0, CURRENT_TIMESTAMP, 1)
                ON CONFLICT(key_index) DO UPDATE SET
                    rate_limit_hits = rate_limit_hits + 1,
                    last_used = CURRENT_TIMESTAMP
            ''', (key_index,))
        else:
            cursor.execute('''
                INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits)
                VALUES (?, 1, CURRENT_TIMESTAMP, 0)
                ON CONFLICT(key_index) DO UPDATE SET
                    usage_count = usage_count + 1,
                    last_used = CURRENT_TIMESTAMP
            ''', (key_index,))
        
        conn.commit()
        conn.close()
    
    def get_api_key_stats(self):
        """Get API key usage statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT key_index, usage_count, last_used, rate_limit_hits
            FROM api_key_stats
            ORDER BY key_index
        ''')
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def get_admin_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("📚 View Knowledge", callback_data="admin_view_knowledge"),
                InlineKeyboardButton("✏️ Add Knowledge", callback_data="admin_set_knowledge")
            ],
            [
                InlineKeyboardButton("🗑️ Delete Knowledge", callback_data="admin_delete_knowledge"),
                InlineKeyboardButton("💬 Message User", callback_data="admin_message_user")
            ],
            [
                InlineKeyboardButton("🔑 Keywords", callback_data="admin_keywords"),
                InlineKeyboardButton("🔑 API Key Stats", callback_data="admin_api_stats")
            ],
            [
                InlineKeyboardButton("📝 Auto Messages", callback_data="admin_auto_messages"),
                InlineKeyboardButton("👥 View Users", callback_data="admin_view_users")
            ],
            [
                InlineKeyboardButton("📂 View User Chats", callback_data="admin_view_user_chats"),
                InlineKeyboardButton("🗑️ Delete Chats", callback_data="admin_delete_chats_menu")
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("🏘️ Group Sessions", callback_data="admin_group_sessions")
            ],
            [
                InlineKeyboardButton("🔚 End Session", callback_data="admin_end_session"),
                InlineKeyboardButton("🔄 Refresh Panel", callback_data="admin_refresh")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def track_user(self, user_id: int, username: str, first_name: str, last_name: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO all_users (user_id, username, first_name, last_name, last_active, message_count)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                username = ?,
                first_name = ?,
                last_name = ?,
                last_active = CURRENT_TIMESTAMP,
                message_count = message_count + 1
        ''', (user_id, username, first_name, last_name, username, first_name, last_name))
        
        conn.commit()
        conn.close()
    
    def get_bot_knowledge(self):
        """Get all knowledge entries combined as text for AI"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT knowledge_text FROM bot_knowledge ORDER BY created_at ASC')
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
        
        return '\n\n'.join([row[0] for row in results])
    
    def get_all_bot_knowledge(self):
        """Get all knowledge entries with IDs for display"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, knowledge_text, created_at FROM bot_knowledge ORDER BY created_at ASC')
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def set_bot_knowledge(self, knowledge: str):
        """Add new knowledge entry (does NOT delete existing)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO bot_knowledge (knowledge_text) VALUES (?)', (knowledge,))
        
        conn.commit()
        conn.close()
    
    def delete_bot_knowledge(self, knowledge_id: int):
        """Delete a specific knowledge entry by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM bot_knowledge WHERE id = ?', (knowledge_id,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted > 0
    
    def save_chat_history(self, user_id: int, username: str, message: str, response: str, chat_type: str = 'dm', chat_id: int | None = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chat_history (user_id, username, message, response, message_role, chat_type, chat_id)
            VALUES (?, ?, ?, ?, 'user', ?, ?)
        ''', (user_id, username, message, response, chat_type, chat_id if chat_id is not None else user_id))
        
        conn.commit()
        conn.close()
    
    def get_recent_history(self, user_id: int, limit: int = 5):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT message, response FROM chat_history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        
        history = cursor.fetchall()
        conn.close()
        
        return list(reversed(history))
    
    def get_all_users(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, first_seen, last_active, message_count
            FROM all_users
            ORDER BY last_active DESC
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        return users
    
    def get_user_info(self, user_id: int):
        """Get user information from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT username, first_name, last_name
            FROM all_users
            WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result if result else (None, None, None)
    
    
    def track_group(self, chat_id: int, title: str, username: str, chat_type: str):
        """Track group/supergroup in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO group_registry (group_id, title, username, chat_type, last_active, message_count)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
            ON CONFLICT(group_id) DO UPDATE SET
                title = ?,
                username = ?,
                last_active = CURRENT_TIMESTAMP,
                message_count = message_count + 1
        ''', (chat_id, title, username, chat_type, title, username))
        
        conn.commit()
        conn.close()
    
    def get_all_groups(self):
        """Get all groups bot is part of"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT group_id, title, username, chat_type, first_seen, last_active, message_count
            FROM group_registry
            ORDER BY last_active DESC
        ''')
        
        groups = cursor.fetchall()
        conn.close()
        
        return groups
    
    def get_user_chat_history(self, username: str, limit: int = 50):
        """Get chat history for a specific username"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ch.message, ch.response, ch.timestamp, ch.message_role
            FROM chat_history ch
            JOIN all_users au ON ch.user_id = au.user_id
            WHERE LOWER(au.username) = LOWER(?) AND ch.chat_type = 'dm'
            ORDER BY ch.timestamp DESC
            LIMIT ?
        ''', (username, limit))
        
        history = cursor.fetchall()
        conn.close()
        
        return list(reversed(history))
    
    def delete_user_chats(self, username: str):
        """Delete all chat history for a specific user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM chat_history
            WHERE user_id IN (SELECT user_id FROM all_users WHERE LOWER(username) = LOWER(?))
        ''', (username,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def delete_all_chats(self):
        """Delete all chat history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM chat_history')
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted
    
    def check_keyword_match(self, message: str):
        """Check if message contains any keyword and return response"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT keyword, response FROM group_keywords')
        keywords = cursor.fetchall()
        conn.close()
        
        message_lower = message.lower()
        
        for keyword, response in keywords:
            if keyword.lower() in message_lower:
                logger.info(f"Keyword matched: '{keyword}' in message")
                return response
        
        return None
    
    def add_keyword(self, keyword: str, response: str):
        """Add a new keyword with its response"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO group_keywords (keyword, response) VALUES (?, ?)', (keyword, response))
        
        conn.commit()
        conn.close()
    
    def get_all_keywords(self):
        """Get all keywords"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT id, keyword, response, created_at FROM group_keywords ORDER BY created_at DESC')
        keywords = cursor.fetchall()
        conn.close()
        
        return keywords
    
    def delete_keyword(self, keyword_id: int):
        """Delete a keyword by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM group_keywords WHERE id = ?', (keyword_id,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted > 0
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        self.track_user(user.id, user.username, user.first_name, user.last_name)
        
        if self.is_admin(user.id):
            welcome_message = (
                f"🔐 *Admin Control Panel*\n\n"
                f"Welcome {user.first_name}!\n\n"
                f"Use buttons below to manage your bot:"
            )
            await update.message.reply_text(
                welcome_message,
                reply_markup=self.get_admin_keyboard()
            )
        else:
            custom_welcome = self.get_automated_message('welcome')
            if custom_welcome:
                welcome_message = custom_welcome.replace('{first_name}', user.first_name)
            else:
                welcome_message = (
                    f"🤖 Namaste {user.first_name}!\n\n"
                    "Main aapka AI assistant hoon. Aap mujhse kuch bhi pooch sakte hain!\n\n"
                    "Commands:\n"
                    "/start - Bot ko shuru karein\n"
                    "/help - Madad prapt karein\n"
                    "/clear - Chat history clear karein\n\n"
                    "Bas apna message bhejein aur main jawab doonga! 🚀"
                )
            await update.message.reply_text(welcome_message)
        
        logger.info(f"User {user.id} ({user.username}) started the bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if self.is_admin(user.id):
            await update.message.reply_text(
                "🔐 *Admin Help*\n\n"
                "Use buttons in /start for easy control!",
                reply_markup=self.get_admin_keyboard()
            )
        else:
            custom_help = self.get_automated_message('help')
            if custom_help:
                help_text = custom_help
            else:
                help_text = (
                    "📚 *Kaise istemal karein:*\n\n"
                    "1. Mujhe koi bhi sawal poochein\n"
                    "2. Main AI ki madad se jawab doonga\n"
                    "3. Aapki chat history save rahegi\n\n"
                    "*Commands:*\n"
                    "/start - Bot shuru karein\n"
                    "/help - Yeh message\n"
                    "/clear - Apni chat history clear karein\n\n"
                    "Kuch bhi poochne ke liye bas message type karein! 💬"
                )
            await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM chat_history WHERE user_id = ?', (user_id,))
        cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text("✅ Aapki chat history clear ho gayi hai!")
        logger.info(f"User {user_id} cleared their chat history")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.answer("❌ Admin access required!")
            return
        
        await query.answer()
        
        data = query.data
        
        if data == "admin_view_knowledge":
            all_knowledge = self.get_all_bot_knowledge()
            if all_knowledge:
                knowledge_text = "📚 *All Bot Knowledge:*\n\n"
                for idx, (kid, ktext, created) in enumerate(all_knowledge, 1):
                    preview = ktext[:150] + "..." if len(ktext) > 150 else ktext
                    escaped_preview = escape_markdown(preview)
                    knowledge_text += f"{idx}\\. {escaped_preview}\n\n"
                knowledge_text += f"\n*Total: {len(all_knowledge)} knowledge entries*\n\n"
                knowledge_text += "Use 'Add Knowledge' to add more or 'Delete Knowledge' to remove\\."
                await query.edit_message_text(
                    knowledge_text,
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='MarkdownV2'
                )
            else:
                await query.edit_message_text(
                    "⚠️ *No knowledge set yet\\!*\n\n"
                    "Click 'Add Knowledge' to add information\\.",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='MarkdownV2'
                )
        
        elif data == "admin_set_knowledge":
            self.admin_state[user_id] = "waiting_knowledge"
            await query.edit_message_text(
                "✏️ *Add Bot Knowledge*\n\n"
                "Please send the knowledge/information you want to ADD.\n\n"
                "*Example:*\n"
                "Product: Mars Loader Premium\n"
                "Price: ₹500/month\n"
                "Features: Unlimited access, 24/7 support\n\n"
                "📌 *Note:* This will be ADDED to existing knowledge (not replaced).\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_delete_knowledge":
            all_knowledge = self.get_all_bot_knowledge()
            if not all_knowledge:
                await query.edit_message_text(
                    "⚠️ *No knowledge to delete\\!*\n\n"
                    "Add some knowledge first\\.",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='MarkdownV2'
                )
                return
            
            knowledge_text = "🗑️ *Delete Knowledge*\n\n"
            knowledge_text += "Current knowledge entries:\n\n"
            for idx, (kid, ktext, created) in enumerate(all_knowledge, 1):
                preview = ktext[:100] + "..." if len(ktext) > 100 else ktext
                escaped_preview = escape_markdown(preview)
                knowledge_text += f"{idx}\\. {escaped_preview}\n\n"
            knowledge_text += f"\n*Total: {len(all_knowledge)} entries*\n\n"
            knowledge_text += "Send the number \\(1, 2, 3\\.\\.\\.\\) of the knowledge you want to delete\\.\n"
            knowledge_text += "Send /cancel to cancel\\."
            
            self.admin_state[user_id] = "waiting_delete_knowledge"
            await query.edit_message_text(
                knowledge_text,
                parse_mode='MarkdownV2'
            )
        
        elif data == "admin_view_users":
            users = self.get_all_users()
            if not users:
                await query.edit_message_text(
                    "📭 No users yet!",
                    reply_markup=self.get_admin_keyboard()
                )
                return
            
            user_list = "👥 *All Users:*\n\n"
            for idx, (uid, username, first_name, last_name, first_seen, last_active, msg_count) in enumerate(users[:20], 1):
                full_name = f"{first_name or ''} {last_name or ''}".strip()
                username_display = f"@{username}" if username else "No username"
                user_list += (
                    f"{idx}. {full_name or 'Unknown'}\n"
                    f"   - {username_display}\n"
                    f"   - ID: {uid}\n"
                    f"   - Messages: {msg_count}\n\n"
                )
            
            user_list += f"\n*Total Users: {len(users)}*"
            
            if len(users) > 20:
                user_list += f"\n(Showing first 20)"
            
            await query.edit_message_text(
                user_list,
                reply_markup=self.get_admin_keyboard()
            )
        
        elif data == "admin_message_user":
            users = self.get_all_users()
            if not users:
                await query.edit_message_text(
                    "📭 No users to message!",
                    reply_markup=self.get_admin_keyboard()
                )
                return
            
            keyboard = []
            for uid, username, first_name, last_name, _, _, _ in users[:10]:
                full_name = f"{first_name or ''} {last_name or ''}".strip()
                display = f"{full_name or 'Unknown'} (@{username})" if username else f"{full_name or 'Unknown'}"
                keyboard.append([InlineKeyboardButton(display, callback_data=f"msg_user_{uid}")])
            
            keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_refresh")])
            
            await query.edit_message_text(
                "💬 *Select User to Message:*\n\n"
                "Choose a user from the list below:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data.startswith("msg_user_"):
            target_user_id = int(data.split("_")[2])
            self.active_admin_chats[user_id] = target_user_id
            self.user_to_admin_chat[target_user_id] = user_id
            self.admin_state[user_id] = "chatting"
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT username, first_name FROM all_users WHERE user_id = ?', (target_user_id,))
            result = cursor.fetchone()
            conn.close()
            
            username, first_name = result if result else ("Unknown", "Unknown")
            
            await query.edit_message_text(
                f"✅ *Chat Session Active*\n\n"
                f"Now chatting with: {first_name} (@{username})\n\n"
                f"Send your messages directly. User's replies will come here.\n\n"
                f"To end session, click button below:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔚 End Session", callback_data="admin_end_session")
                ]])
            )
        
        elif data == "admin_end_session":
            session_ended = False
            
            if user_id in self.active_admin_chats:
                target_user = self.active_admin_chats[user_id]
                del self.active_admin_chats[user_id]
                if target_user in self.user_to_admin_chat:
                    del self.user_to_admin_chat[target_user]
                if user_id in self.admin_state:
                    del self.admin_state[user_id]
                session_ended = True
                logger.info(f"Admin {user_id} ended user chat session")
            
            if user_id in self.active_group_sessions:
                group_id = self.active_group_sessions[user_id]
                del self.active_group_sessions[user_id]
                if group_id in self.group_to_admin:
                    del self.group_to_admin[group_id]
                if user_id in self.admin_state:
                    del self.admin_state[user_id]
                session_ended = True
                logger.info(f"Admin {user_id} ended group session with {group_id}")
            
            if session_ended:
                await query.edit_message_text(
                    "✅ *Session Ended*\n\n"
                    "Chat session has been closed.",
                    reply_markup=self.get_admin_keyboard()
                )
            else:
                await query.edit_message_text(
                    "⚠️ No active session!",
                    reply_markup=self.get_admin_keyboard()
                )
        
        elif data == "admin_broadcast":
            self.admin_state[user_id] = "waiting_broadcast"
            await query.edit_message_text(
                "📢 *Broadcast Message*\n\n"
                "Send the message you want to broadcast to all users.\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_auto_messages":
            all_messages = self.get_all_automated_messages()
            keyboard = [
                [InlineKeyboardButton("📝 Edit Welcome Message", callback_data="edit_msg_welcome")],
                [InlineKeyboardButton("📝 Edit Help Message", callback_data="edit_msg_help")],
                [InlineKeyboardButton("📋 View All Messages", callback_data="view_all_auto_msgs")],
                [InlineKeyboardButton("« Back", callback_data="admin_refresh")]
            ]
            await query.edit_message_text(
                "📝 *Automated Messages*\n\n"
                "Manage bot's automatic responses:\n\n"
                "• Welcome Message - /start command\n"
                "• Help Message - /help command\n\n"
                "Use {first_name} in messages for user's name\n\n"
                "Choose an option below:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("edit_msg_"):
            message_type = data.replace("edit_msg_", "")
            self.admin_state[user_id] = f"waiting_auto_msg_{message_type}"
            current_msg = self.get_automated_message(message_type)
            
            msg_name = "Welcome" if message_type == "welcome" else "Help"
            await query.edit_message_text(
                f"✏️ *Edit {msg_name} Message*\n\n"
                f"Current message:\n"
                f"```\n{current_msg if current_msg else 'Not set (using default)'}\n```\n\n"
                f"Send new message text. Use `{{first_name}}` for user's name.\n\n"
                f"Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "view_all_auto_msgs":
            all_messages = self.get_all_automated_messages()
            if all_messages:
                msg_text = "📋 *All Automated Messages:*\n\n"
                for msg_type, msg_text_db, updated in all_messages:
                    preview = msg_text_db[:100] + "..." if len(msg_text_db) > 100 else msg_text_db
                    msg_text += f"*{msg_type.title()}:*\n{preview}\n\n"
            else:
                msg_text = "⚠️ No automated messages set yet!\nUsing default messages."
            
            await query.edit_message_text(
                msg_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_auto_messages")]]),
                parse_mode='Markdown'
            )
        
        elif data == "admin_keywords":
            keyboard = [
                [InlineKeyboardButton("📝 View Keywords", callback_data="admin_view_keywords")],
                [InlineKeyboardButton("➕ Add Keyword", callback_data="admin_add_keyword")],
                [InlineKeyboardButton("🗑️ Delete Keyword", callback_data="admin_delete_keyword")],
                [InlineKeyboardButton("« Back", callback_data="admin_refresh")]
            ]
            await query.edit_message_text(
                "🔑 *Keyword Management*\n\n"
                "Keywords work in both groups and DMs!\n\n"
                "When someone sends a message containing a keyword, bot will automatically reply with the saved response.\n\n"
                "Choose an option:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_view_keywords":
            keywords = self.get_all_keywords()
            if keywords:
                kw_text = "📝 *All Keywords:*\n\n"
                for idx, (kid, keyword, response, created) in enumerate(keywords, 1):
                    resp_preview = response[:80] + "..." if len(response) > 80 else response
                    kw_text += f"{idx}. *Keyword:* `{keyword}`\n"
                    kw_text += f"   *Response:* {resp_preview}\n\n"
                kw_text += f"\n*Total: {len(keywords)} keywords*"
            else:
                kw_text = "⚠️ *No keywords set yet!*\n\nClick 'Add Keyword' to create one."
            
            await query.edit_message_text(
                kw_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_keywords")]]),
                parse_mode='Markdown'
            )
        
        elif data == "admin_add_keyword":
            self.admin_state[user_id] = "waiting_keyword"
            await query.edit_message_text(
                "➕ *Add New Keyword*\n\n"
                "Send the keyword you want to detect.\n\n"
                "*Example:* `price` or `contact` or `website`\n\n"
                "⚡ Bot will respond whenever this word appears in a message!\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_delete_keyword":
            keywords = self.get_all_keywords()
            if not keywords:
                await query.edit_message_text(
                    "⚠️ *No keywords to delete!*\n\nAdd some keywords first.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data="admin_keywords")]]),
                    parse_mode='Markdown'
                )
                return
            
            kw_text = "🗑️ *Delete Keyword*\n\n"
            for idx, (kid, keyword, response, created) in enumerate(keywords, 1):
                kw_text += f"{idx}. `{keyword}`\n"
            kw_text += f"\n*Total: {len(keywords)} keywords*\n\n"
            kw_text += "Send the number (1, 2, 3...) of the keyword you want to delete.\n\n"
            kw_text += "Send /cancel to cancel."
            
            self.admin_state[user_id] = "waiting_delete_keyword"
            await query.edit_message_text(
                kw_text,
                parse_mode='Markdown'
            )
        
        elif data == "admin_api_stats":
            stats = self.get_api_key_stats()
            stats_text = "🔑 *API Key Statistics*\n\n"
            stats_text += f"📊 Total API Keys: {len(self.api_keys)}\n"
            stats_text += f"🔄 Currently Using: Key #{self.current_key_index + 1}\n\n"
            
            if stats:
                stats_text += "*Usage Details:*\n"
                for key_idx, usage, last_used, rate_hits in stats:
                    stats_text += f"\n*Key #{key_idx + 1}:*\n"
                    stats_text += f"  ✅ Successful calls: {usage}\n"
                    stats_text += f"  ⚠️ Rate limit hits: {rate_hits}\n"
                    if last_used:
                        stats_text += f"  🕒 Last used: {last_used}\n"
            else:
                stats_text += "No usage data yet."
            
            await query.edit_message_text(
                stats_text,
                reply_markup=self.get_admin_keyboard(),
                parse_mode='Markdown'
            )
        
        elif data == "admin_view_user_chats":
            self.admin_state[user_id] = "waiting_username_for_chats"
            await query.edit_message_text(
                "📂 *View User Chats*\n\n"
                "Send the username (without @) of the user whose chat history you want to view.\n\n"
                "*Example:* `johndoe`\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_delete_chats_menu":
            keyboard = [
                [InlineKeyboardButton("🗑️ Delete User Chats", callback_data="admin_delete_user_chats")],
                [InlineKeyboardButton("🗑️ Delete ALL Chats", callback_data="admin_delete_all_chats")],
                [InlineKeyboardButton("« Back", callback_data="admin_refresh")]
            ]
            await query.edit_message_text(
                "🗑️ *Delete Chat History*\n\n"
                "Choose an option:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_delete_user_chats":
            self.admin_state[user_id] = "waiting_username_for_delete"
            await query.edit_message_text(
                "🗑️ *Delete User Chats*\n\n"
                "⚠️ This will delete ALL chat history for the specified user!\n\n"
                "Send the username (without @) of the user:\n\n"
                "*Example:* `johndoe`\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_delete_all_chats":
            keyboard = [
                [InlineKeyboardButton("✅ Yes, Delete ALL", callback_data="confirm_delete_all_chats")],
                [InlineKeyboardButton("❌ Cancel", callback_data="admin_refresh")]
            ]
            await query.edit_message_text(
                "⚠️ *DELETE ALL CHAT HISTORY?*\n\n"
                "This will permanently delete ALL chat history from ALL users!\n\n"
                "Are you absolutely sure?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "confirm_delete_all_chats":
            deleted_count = self.delete_all_chats()
            await query.edit_message_text(
                f"✅ *All Chats Deleted!*\n\n"
                f"Deleted {deleted_count} chat messages.\n\n"
                f"Database has been cleared.",
                reply_markup=self.get_admin_keyboard(),
                parse_mode='Markdown'
            )
            logger.info(f"Admin {user_id} deleted all chat history ({deleted_count} messages)")
        
        elif data == "admin_group_sessions":
            groups = self.get_all_groups()
            if not groups:
                await query.edit_message_text(
                    "📭 *No Groups Found!*\n\n"
                    "Bot is not in any groups yet, or no messages have been received from groups.",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='Markdown'
                )
                return
            
            keyboard = []
            for idx, (gid, title, username, chat_type, _, last_active, msg_count) in enumerate(groups[:10], 1):
                display_name = title or f"Group {gid}"
                keyboard.append([InlineKeyboardButton(
                    f"{idx}. {display_name} ({msg_count} msgs)",
                    callback_data=f"select_group_{gid}"
                )])
            
            keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_refresh")])
            
            await query.edit_message_text(
                "🏘️ *Group Sessions*\n\n"
                "Select a group to start live messaging mode:\n\n"
                "*Note:* You'll see all messages from that group and can reply through the bot.",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data.startswith("select_group_"):
            group_id = int(data.split("_")[2])
            self.active_group_sessions[user_id] = group_id
            self.group_to_admin[group_id] = user_id
            self.admin_state[user_id] = "group_messaging"
            
            groups = self.get_all_groups()
            group_info = next((g for g in groups if g[0] == group_id), None)
            group_name = group_info[1] if group_info else f"Group {group_id}"
            
            await query.edit_message_text(
                f"✅ *Group Session Active*\n\n"
                f"Connected to: {group_name}\n\n"
                f"You will now see all incoming messages from this group.\n"
                f"Send any message to reply to the group.\n\n"
                f"Click button below to end session:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔚 End Group Session", callback_data="admin_end_session")
                ]]),
                parse_mode='Markdown'
            )
            logger.info(f"Admin {user_id} started group session with {group_name} ({group_id})")
        
        elif data == "admin_refresh":
            await query.edit_message_text(
                "🔐 *Admin Control Panel*\n\n"
                "Use buttons below to manage your bot:",
                reply_markup=self.get_admin_keyboard()
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_message = update.message.text
        
        self.track_user(user.id, user.username, user.first_name, user.last_name)
        logger.info(f"Received message from {user.id} ({user.username}): {user_message}")
        
        if user_message == "/cancel" and self.is_admin(user.id):
            if user.id in self.admin_state:
                del self.admin_state[user.id]
            await update.message.reply_text(
                "❌ Cancelled!",
                reply_markup=self.get_admin_keyboard()
            )
            return
        
        if self.is_admin(user.id) and user.id in self.admin_state:
            state = self.admin_state[user.id]
            
            if state == "waiting_knowledge":
                self.set_bot_knowledge(user_message)
                del self.admin_state[user.id]
                await update.message.reply_text(
                    f"✅ *Knowledge Added!*\n\n"
                    f"New knowledge:\n{user_message}\n\n"
                    f"Bot will now use this information along with existing knowledge!",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {user.id} added bot knowledge")
                return
            
            elif state == "waiting_delete_knowledge":
                try:
                    knowledge_num = int(user_message.strip())
                    all_knowledge = self.get_all_bot_knowledge()
                    
                    if knowledge_num < 1 or knowledge_num > len(all_knowledge):
                        await update.message.reply_text(
                            f"❌ Invalid number! Please send a number between 1 and {len(all_knowledge)}.",
                            reply_markup=self.get_admin_keyboard()
                        )
                        return
                    
                    knowledge_id = all_knowledge[knowledge_num - 1][0]
                    deleted_text = all_knowledge[knowledge_num - 1][1]
                    
                    if self.delete_bot_knowledge(knowledge_id):
                        del self.admin_state[user.id]
                        preview = deleted_text[:100] + "..." if len(deleted_text) > 100 else deleted_text
                        escaped_preview = escape_markdown(preview)
                        await update.message.reply_text(
                            f"✅ *Knowledge Deleted\\!*\n\n"
                            f"Deleted entry \\#{knowledge_num}:\n{escaped_preview}\n\n"
                            f"Remaining: {len(all_knowledge) - 1} entries",
                            reply_markup=self.get_admin_keyboard(),
                            parse_mode='MarkdownV2'
                        )
                        logger.info(f"Admin {user.id} deleted knowledge #{knowledge_num}")
                    else:
                        await update.message.reply_text(
                            "❌ Failed to delete knowledge!",
                            reply_markup=self.get_admin_keyboard()
                        )
                    return
                    
                except ValueError:
                    await update.message.reply_text(
                        "❌ Please send a valid number!",
                        reply_markup=self.get_admin_keyboard()
                    )
                    return
            
            elif state == "waiting_keyword":
                keyword = user_message.strip()
                self.admin_state[user.id] = f"waiting_keyword_response:{keyword}"
                await update.message.reply_text(
                    f"✅ *Keyword Set:* `{keyword}`\n\n"
                    f"Now send the response you want bot to send when this keyword is detected.\n\n"
                    f"*Example:* Our product costs ₹500/month with premium support!\n\n"
                    f"Send /cancel to cancel.",
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {user.id} setting keyword: {keyword}")
                return
            
            elif state.startswith("waiting_keyword_response:"):
                keyword = state.split(":", 1)[1]
                response_text = user_message
                self.add_keyword(keyword, response_text)
                del self.admin_state[user.id]
                
                await update.message.reply_text(
                    f"✅ *Keyword Added Successfully!*\n\n"
                    f"*Keyword:* `{keyword}`\n"
                    f"*Response:* {response_text[:100]}{'...' if len(response_text) > 100 else ''}\n\n"
                    f"Bot will now respond with this message when '{keyword}' is detected!",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {user.id} added keyword '{keyword}' with response")
                return
            
            elif state == "waiting_delete_keyword":
                try:
                    keyword_num = int(user_message.strip())
                    all_keywords = self.get_all_keywords()
                    
                    if keyword_num < 1 or keyword_num > len(all_keywords):
                        await update.message.reply_text(
                            f"❌ Invalid number! Please send a number between 1 and {len(all_keywords)}.",
                            reply_markup=self.get_admin_keyboard()
                        )
                        return
                    
                    keyword_id = all_keywords[keyword_num - 1][0]
                    deleted_keyword = all_keywords[keyword_num - 1][1]
                    
                    if self.delete_keyword(keyword_id):
                        del self.admin_state[user.id]
                        await update.message.reply_text(
                            f"✅ *Keyword Deleted!*\n\n"
                            f"Deleted: `{deleted_keyword}`\n\n"
                            f"Remaining: {len(all_keywords) - 1} keywords",
                            reply_markup=self.get_admin_keyboard(),
                            parse_mode='Markdown'
                        )
                        logger.info(f"Admin {user.id} deleted keyword '{deleted_keyword}'")
                    else:
                        await update.message.reply_text(
                            "❌ Failed to delete keyword!",
                            reply_markup=self.get_admin_keyboard()
                        )
                    return
                    
                except ValueError:
                    await update.message.reply_text(
                        "❌ Please send a valid number!",
                        reply_markup=self.get_admin_keyboard()
                    )
                    return
            
            elif state == "waiting_broadcast":
                users = self.get_all_users()
                sent_count = 0
                failed_count = 0
                
                for uid, _, _, _, _, _, _ in users:
                    if uid == self.admin_id:
                        continue
                    try:
                        await context.bot.send_message(
                            chat_id=uid,
                            text=f"📢 *Broadcast Message:*\n\n{user_message}",
                            parse_mode='Markdown'
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send broadcast to {uid}: {e}")
                        failed_count += 1
                
                del self.admin_state[user.id]
                await update.message.reply_text(
                    f"✅ *Broadcast Complete!*\n\n"
                    f"Sent: {sent_count}\n"
                    f"Failed: {failed_count}",
                    reply_markup=self.get_admin_keyboard()
                )
                return
            
            elif state.startswith("waiting_auto_msg_"):
                message_type = state.replace("waiting_auto_msg_", "")
                self.set_automated_message(message_type, user_message)
                del self.admin_state[user.id]
                
                msg_name = "Welcome" if message_type == "welcome" else "Help"
                await update.message.reply_text(
                    f"✅ *{msg_name} Message Updated!*\n\n"
                    f"New message:\n{user_message}\n\n"
                    f"Users will now see this message!",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {user.id} updated {message_type} message")
                return
            
            elif state == "waiting_username_for_chats":
                username = user_message.strip().replace('@', '')
                history = self.get_user_chat_history(username, limit=30)
                
                if not history:
                    await update.message.reply_text(
                        f"❌ No chat history found for @{username}!\n\n"
                        f"User might not exist or hasn't messaged the bot yet.",
                        reply_markup=self.get_admin_keyboard(),
                        parse_mode='Markdown'
                    )
                    del self.admin_state[user.id]
                    return
                
                chat_text = f"📂 *Chat History for @{username}*\n\n"
                for idx, (msg, resp, timestamp, role) in enumerate(history[-20:], 1):
                    time_str = timestamp.split()[1][:5] if ' ' in timestamp else ""
                    msg_preview = msg[:50] + "..." if len(msg) > 50 else msg
                    resp_preview = resp[:50] + "..." if len(resp) > 50 else resp
                    
                    chat_text += f"*{time_str}*\n"
                    chat_text += f"👤 User: {msg_preview}\n"
                    chat_text += f"🤖 Bot: {resp_preview}\n\n"
                
                chat_text += f"\n*Total messages: {len(history)}*\n"
                chat_text += f"(Showing last 20)"
                
                del self.admin_state[user.id]
                await update.message.reply_text(
                    chat_text,
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {user.id} viewed chat history for @{username}")
                return
            
            elif state == "waiting_username_for_delete":
                username = user_message.strip().replace('@', '')
                deleted_count = self.delete_user_chats(username)
                
                if deleted_count == 0:
                    await update.message.reply_text(
                        f"❌ No chats found for @{username}!",
                        reply_markup=self.get_admin_keyboard(),
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"✅ *User Chats Deleted!*\n\n"
                        f"Deleted {deleted_count} messages from @{username}.",
                        reply_markup=self.get_admin_keyboard(),
                        parse_mode='Markdown'
                    )
                    logger.info(f"Admin {user.id} deleted {deleted_count} chats from @{username}")
                
                del self.admin_state[user.id]
                return
            
            elif state == "group_messaging":
                if user.id in self.active_group_sessions:
                    group_id = self.active_group_sessions[user.id]
                    try:
                        await context.bot.send_message(
                            chat_id=group_id,
                            text=user_message
                        )
                        await update.message.reply_text("✅ Message sent to group!")
                        logger.info(f"Admin {user.id} sent message to group {group_id}")
                    except Exception as e:
                        await update.message.reply_text(f"❌ Failed to send: {e}")
                        logger.error(f"Failed to send admin message to group: {e}")
                return
        
        if user.id in self.user_to_admin_chat:
            admin_id = self.user_to_admin_chat[user.id]
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 *Message from {user.first_name}* (@{user.username or 'no_username'}):\n\n{user_message}",
                    parse_mode='Markdown'
                )
                await update.message.reply_text("✅ Aapka message support team ko bhej diya gaya hai!")
                return
            except Exception as e:
                logger.error(f"Failed to forward message to admin: {e}")
        
        if self.is_admin(user.id) and user.id in self.active_admin_chats:
            target_user_id = self.active_admin_chats[user.id]
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"💬 *Message from Support:*\n\n{user_message}",
                    parse_mode='Markdown'
                )
                await update.message.reply_text("✅ Message sent!")
                return
            except Exception as e:
                await update.message.reply_text(f"❌ Failed to send: {e}")
                return
        
        chat_type = update.message.chat.type
        is_group = chat_type in ['group', 'supergroup']
        
        if is_group:
            chat = update.message.chat
            self.track_group(
                chat.id,
                chat.title or "Unknown Group",
                chat.username or "",
                chat_type
            )
            
            if chat.id in self.group_to_admin:
                admin_id = self.group_to_admin[chat.id]
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"📩 *Group: {chat.title}*\n"
                             f"👤 {user.first_name} (@{user.username or 'no_username'}):\n\n"
                             f"{user_message}",
                        parse_mode='Markdown'
                    )
                    logger.info(f"Forwarded group message to admin {admin_id}")
                except Exception as e:
                    logger.error(f"Failed to forward group message to admin: {e}")
        
        # Check for keyword matches (works in both groups and DMs)
        keyword_response = self.check_keyword_match(user_message)
        if keyword_response:
            logger.info(f"Keyword match found! Sending response to {'group' if is_group else 'DM'}")
            await update.message.reply_text(keyword_response)
            return
        
        is_reply_to_bot = False
        
        if is_group:
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username
            
            if update.message.reply_to_message:
                replied_user = update.message.reply_to_message.from_user
                if replied_user and replied_user.username == bot_username:
                    is_reply_to_bot = True
                    logger.info(f"Group message is reply to bot from {user.id}")
            
            is_mentioned = f"@{bot_username.lower()}" in user_message.lower()
            
            if not (is_reply_to_bot or is_mentioned):
                logger.info(f"Ignoring group message (not mentioned/replied): {user_message[:50]}")
                return
        
        await update.message.chat.send_action("typing")
        
        try:
            recent_history = self.get_recent_history(user.id, limit=3)
            custom_knowledge = self.get_bot_knowledge()
            
            username_db, first_name_db, last_name_db = self.get_user_info(user.id)
            user_first_name = user.first_name or first_name_db or "Dost"
            user_username = user.username or username_db
            
            system_prompt = "Tum ek highly intelligent aur helpful AI assistant ho. Tumhe Hindi aur English dono languages mein expert tarike se baat karni aani hai."
            
            system_prompt += f"\n\nUser ka naam: {user_first_name}"
            if user_username:
                system_prompt += f" (@{user_username})"
            system_prompt += "\nNatural conversation mein user ka naam use kar sakte ho jab appropriate ho."
            
            system_prompt += f"\n\n🔐 IMPORTANT - OWNER RESPECT: Tumhare owner ka naam @tgshaitaan hai. Jab bhi owner baat kare ya unka zikr ho, tum unhe highest respect dena - 'Boss', 'Sir', ya 'Owner' kehke address karna hai."
            
            if is_group:
                system_prompt += "\n\n👥 GROUP CONTEXT: Yeh ek group chat hai. Natural tareeke se interact karo. Owner @tgshaitaan ko hamesha special respect do."
            
            if custom_knowledge:
                system_prompt += f"\n\n📚 KNOWLEDGE BASE - CRITICAL INSTRUCTIONS:\n"
                system_prompt += f"Tumhe niche detailed knowledge base diya gaya hai. Yeh tumhari PRIMARY source of information hai:\n\n"
                system_prompt += f"=== START KNOWLEDGE BASE ===\n{custom_knowledge}\n=== END KNOWLEDGE BASE ===\n\n"
                system_prompt += f"🎯 RULES FOR USING KNOWLEDGE:\n"
                system_prompt += f"1. Jab bhi user kuch poochu, PEHLE knowledge base mein check karo\n"
                system_prompt += f"2. Agar knowledge base mein answer mil jaye, toh WAHI detailed answer do\n"
                system_prompt += f"3. Knowledge base ki information ko accurately aur completely use karo\n"
                system_prompt += f"4. Products, services, pricing, features - SAB knowledge base se hi batana\n"
                system_prompt += f"5. AGAR knowledge base mein koi information NAHI hai, tab normal conversation karo\n"
                system_prompt += f"6. User ko helpful aur detailed response do, knowledge base ke saath match karte hue\n\n"
                system_prompt += f"⚡ Jo bhi user poochu, knowledge base ko thoroughly check karo aur relevant information extract karke clear answer do!"
            else:
                system_prompt += "\n\n💬 Normal friendly conversation karo kyunki abhi knowledge base empty hai."
            
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]
            
            for prev_msg, prev_resp in recent_history:
                messages.append({"role": "user", "content": prev_msg})
                messages.append({"role": "assistant", "content": prev_resp})
            
            messages.append({"role": "user", "content": user_message})
            
            # Try API call with automatic key rotation on rate limit
            max_attempts = len(self.api_keys)
            ai_response = None
            
            for attempt in range(max_attempts):
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        max_tokens=500,
                        temperature=0.7
                    )
                    ai_response = response.choices[0].message.content
                    self.track_api_key_usage(self.current_key_index, is_rate_limit=False)
                    break  # Success! Exit loop
                    
                except Exception as api_error:
                    error_str = str(api_error)
                    
                    # Check if it's a rate limit error (429)
                    if "429" in error_str or "rate limit" in error_str.lower():
                        logger.warning(f"⚠️ Rate limit hit on API key #{self.current_key_index + 1}")
                        self.track_api_key_usage(self.current_key_index, is_rate_limit=True)
                        
                        if attempt < max_attempts - 1:
                            # Rotate to next key and retry
                            key_num = self.rotate_api_key()
                            logger.info(f"🔄 Retrying with API key #{key_num}...")
                            continue
                        else:
                            # All keys exhausted
                            logger.error("❌ All API keys have reached rate limit!")
                            raise Exception("All API keys exhausted. Please wait for rate limits to reset.")
                    else:
                        # Different error, don't rotate
                        raise api_error
            
            if not ai_response:
                raise Exception("Failed to get response from OpenAI")
            
            self.save_chat_history(user.id, user.username or "Unknown", user_message, ai_response)
            
            await update.message.reply_text(ai_response)
            logger.info(f"Sent AI response to {user.id}")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            error_message = (
                "❌ Maaf kijiye, kuch galat ho gaya.\n"
                "Kripya thodi der baad phir se try karein."
            )
            await update.message.reply_text(error_message)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Kuch error aa gayi hai. Please thodi der baad try karein."
            )
    
    def run(self):
        logger.info("Starting Telegram bot...")
        
        application = Application.builder().token(self.telegram_token).connect_timeout(30).read_timeout(30).build()
        
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("clear", self.clear_command))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        application.add_error_handler(self.error_handler)
        
        logger.info("Bot is ready and polling for messages...")
        logger.info(f"🔑 Using API key rotation system with {len(self.api_keys)} keys")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    try:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask health check server started")
        
        bot = TelegramChatBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise
