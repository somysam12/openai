#!/usr/bin/env python3
import os
import logging
import sqlite3
import re
import threading
import asyncio
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
    
    def get_db_connection(self):
        """Get database connection with foreign keys enabled"""
        conn = sqlite3.connect(self.db_path)
        conn.execute('PRAGMA foreign_keys = ON')
        return conn
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute('PRAGMA foreign_keys = ON')
        
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
                rate_limit_hits INTEGER DEFAULT 0,
                tokens_used_today INTEGER DEFAULT 0,
                tokens_input_today INTEGER DEFAULT 0,
                tokens_output_today INTEGER DEFAULT 0,
                daily_reset_time DATETIME,
                total_tokens_lifetime INTEGER DEFAULT 0
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pyrogram_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                account_name TEXT,
                api_id TEXT,
                api_hash TEXT,
                session_string TEXT,
                is_active INTEGER DEFAULT 0,
                is_authenticated INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active DATETIME,
                reply_count INTEGER DEFAULT 0,
                error_message TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS account_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                title TEXT,
                knowledge_text TEXT NOT NULL,
                priority TEXT DEFAULT 'regular',
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES pyrogram_accounts(id) ON DELETE CASCADE
            )
        ''')
        
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_account_knowledge_account ON account_knowledge(account_id, priority, updated_at DESC)')
        except sqlite3.OperationalError:
            pass
        
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
        
        # Add token tracking columns if they don't exist
        try:
            cursor.execute('ALTER TABLE api_key_stats ADD COLUMN tokens_used_today INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE api_key_stats ADD COLUMN tokens_input_today INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE api_key_stats ADD COLUMN tokens_output_today INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE api_key_stats ADD COLUMN daily_reset_time DATETIME')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE api_key_stats ADD COLUMN total_tokens_lifetime INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        # Add deactivation tracking columns
        try:
            cursor.execute('ALTER TABLE api_key_stats ADD COLUMN is_deactivated INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE api_key_stats ADD COLUMN deactivation_reason TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE api_key_stats ADD COLUMN deactivated_at DATETIME')
        except sqlite3.OperationalError:
            pass
        
        # Add Super Knowledge columns to bot_knowledge table
        try:
            cursor.execute('ALTER TABLE bot_knowledge ADD COLUMN priority TEXT DEFAULT "regular"')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE bot_knowledge ADD COLUMN target_scope TEXT DEFAULT "both"')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE bot_knowledge ADD COLUMN title TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE bot_knowledge ADD COLUMN status TEXT DEFAULT "active"')
        except sqlite3.OperationalError:
            pass
        
        # Create index for efficient knowledge retrieval
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_knowledge_scope_priority ON bot_knowledge(target_scope, priority, updated_at DESC)')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE pyrogram_accounts ADD COLUMN api_id TEXT')
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute('ALTER TABLE pyrogram_accounts ADD COLUMN api_hash TEXT')
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
    
    def track_api_key_usage(self, key_index: int, is_rate_limit: bool = False, tokens_input: int = 0, tokens_output: int = 0):
        """Track API key usage with token counting and daily reset"""
        from datetime import datetime, timedelta
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get current stats for this key
        cursor.execute('SELECT daily_reset_time, tokens_used_today FROM api_key_stats WHERE key_index = ?', (key_index,))
        result = cursor.fetchone()
        
        # Check if daily reset is needed (24 hours passed)
        should_reset = False
        if result and result[0]:
            last_reset = datetime.fromisoformat(result[0])
            if datetime.now() - last_reset >= timedelta(hours=24):
                should_reset = True
        else:
            should_reset = True  # First time tracking
        
        tokens_total = tokens_input + tokens_output
        
        if should_reset:
            # Reset daily counters
            if is_rate_limit:
                cursor.execute('''
                    INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits, 
                                               tokens_used_today, tokens_input_today, tokens_output_today,
                                               daily_reset_time, total_tokens_lifetime)
                    VALUES (?, 0, CURRENT_TIMESTAMP, 1, 0, 0, 0, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(key_index) DO UPDATE SET
                        rate_limit_hits = rate_limit_hits + 1,
                        last_used = CURRENT_TIMESTAMP,
                        tokens_used_today = 0,
                        tokens_input_today = 0,
                        tokens_output_today = 0,
                        daily_reset_time = CURRENT_TIMESTAMP,
                        total_tokens_lifetime = total_tokens_lifetime + ?
                ''', (key_index, tokens_total, tokens_total))
            else:
                cursor.execute('''
                    INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits,
                                               tokens_used_today, tokens_input_today, tokens_output_today,
                                               daily_reset_time, total_tokens_lifetime)
                    VALUES (?, 1, CURRENT_TIMESTAMP, 0, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(key_index) DO UPDATE SET
                        usage_count = usage_count + 1,
                        last_used = CURRENT_TIMESTAMP,
                        tokens_used_today = ?,
                        tokens_input_today = ?,
                        tokens_output_today = ?,
                        daily_reset_time = CURRENT_TIMESTAMP,
                        total_tokens_lifetime = total_tokens_lifetime + ?
                ''', (key_index, tokens_total, tokens_input, tokens_output, tokens_total, 
                      tokens_total, tokens_input, tokens_output, tokens_total))
        else:
            # Increment daily counters
            if is_rate_limit:
                cursor.execute('''
                    INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits,
                                               tokens_used_today, tokens_input_today, tokens_output_today,
                                               daily_reset_time, total_tokens_lifetime)
                    VALUES (?, 0, CURRENT_TIMESTAMP, 1, 0, 0, 0, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(key_index) DO UPDATE SET
                        rate_limit_hits = rate_limit_hits + 1,
                        last_used = CURRENT_TIMESTAMP,
                        total_tokens_lifetime = total_tokens_lifetime + ?
                ''', (key_index, tokens_total, tokens_total))
            else:
                cursor.execute('''
                    INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits,
                                               tokens_used_today, tokens_input_today, tokens_output_today,
                                               daily_reset_time, total_tokens_lifetime)
                    VALUES (?, 1, CURRENT_TIMESTAMP, 0, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ON CONFLICT(key_index) DO UPDATE SET
                        usage_count = usage_count + 1,
                        last_used = CURRENT_TIMESTAMP,
                        tokens_used_today = tokens_used_today + ?,
                        tokens_input_today = tokens_input_today + ?,
                        tokens_output_today = tokens_output_today + ?,
                        total_tokens_lifetime = total_tokens_lifetime + ?
                ''', (key_index, tokens_total, tokens_input, tokens_output, tokens_total,
                      tokens_total, tokens_input, tokens_output, tokens_total))
        
        conn.commit()
        conn.close()
    
    def mark_api_key_deactivated(self, key_index: int, reason: str):
        """Mark an API key as deactivated in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO api_key_stats (key_index, is_deactivated, deactivation_reason, deactivated_at, 
                                       usage_count, rate_limit_hits)
            VALUES (?, 1, ?, CURRENT_TIMESTAMP, 0, 0)
            ON CONFLICT(key_index) DO UPDATE SET
                is_deactivated = 1,
                deactivation_reason = ?,
                deactivated_at = CURRENT_TIMESTAMP
        ''', (key_index, reason, reason))
        
        conn.commit()
        conn.close()
        logger.warning(f"🔴 API key #{key_index + 1} marked as deactivated: {reason}")
    
    def get_api_key_stats(self):
        """Get detailed API key usage statistics with token tracking"""
        from datetime import datetime, timedelta
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT key_index, usage_count, last_used, rate_limit_hits,
                   tokens_used_today, tokens_input_today, tokens_output_today,
                   daily_reset_time, total_tokens_lifetime
            FROM api_key_stats
            ORDER BY key_index
        ''')
        results = cursor.fetchall()
        conn.close()
        
        # Free tier limits (assuming GPT-4o-mini complimentary program)
        # Tier 1-2: 2.5M tokens/day for mini models
        DAILY_TOKEN_LIMIT = 2500000  # 2.5 million tokens for GPT-4o-mini
        
        detailed_stats = []
        for row in results:
            (key_index, usage_count, last_used, rate_limit_hits,
             tokens_used_today, tokens_input_today, tokens_output_today,
             daily_reset_time, total_tokens_lifetime) = row
            
            # Calculate tokens left
            tokens_left = max(0, DAILY_TOKEN_LIMIT - (tokens_used_today or 0))
            
            # Calculate reset time
            reset_time = None
            hours_until_reset = None
            if daily_reset_time:
                try:
                    reset_dt = datetime.fromisoformat(daily_reset_time)
                    next_reset = reset_dt + timedelta(hours=24)
                    hours_until_reset = (next_reset - datetime.now()).total_seconds() / 3600
                    if hours_until_reset < 0:
                        hours_until_reset = 0
                    reset_time = next_reset.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            detailed_stats.append({
                'key_index': key_index,
                'usage_count': usage_count or 0,
                'last_used': last_used,
                'rate_limit_hits': rate_limit_hits or 0,
                'tokens_used_today': tokens_used_today or 0,
                'tokens_input_today': tokens_input_today or 0,
                'tokens_output_today': tokens_output_today or 0,
                'tokens_left': tokens_left,
                'daily_limit': DAILY_TOKEN_LIMIT,
                'reset_time': reset_time,
                'hours_until_reset': hours_until_reset,
                'total_tokens_lifetime': total_tokens_lifetime or 0
            })
        
        return detailed_stats
    
    def add_super_knowledge(self, title: str, knowledge_text: str, target_scope: str):
        """Add super knowledge with priority and scope"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bot_knowledge (title, knowledge_text, priority, target_scope, status, updated_at)
            VALUES (?, ?, 'super', ?, 'active', CURRENT_TIMESTAMP)
        ''', (title, knowledge_text, target_scope))
        
        conn.commit()
        knowledge_id = cursor.lastrowid
        conn.close()
        logger.info(f"✅ Added super knowledge: {title} (scope: {target_scope})")
        return knowledge_id
    
    def get_super_knowledge_list(self):
        """Get all super knowledge entries for display"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, title, knowledge_text, target_scope, status, updated_at
            FROM bot_knowledge
            WHERE priority = 'super'
            ORDER BY updated_at DESC
        ''')
        results = cursor.fetchall()
        conn.close()
        
        entries = []
        for row in results:
            entry_id, title, text, scope, status, updated_at = row
            entries.append({
                'id': entry_id,
                'title': title or f"Knowledge #{entry_id}",
                'text': text,
                'scope': scope,
                'status': status,
                'updated_at': updated_at
            })
        
        return entries
    
    def delete_super_knowledge(self, knowledge_id: int):
        """Delete super knowledge by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM bot_knowledge WHERE id = ? AND priority = "super"', (knowledge_id,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        return deleted > 0
    
    def toggle_knowledge_status(self, knowledge_id: int):
        """Toggle knowledge status between active/inactive"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE bot_knowledge 
            SET status = CASE 
                WHEN status = 'active' THEN 'inactive'
                ELSE 'active'
            END,
            updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (knowledge_id,))
        
        conn.commit()
        conn.close()
    
    def add_account_knowledge(self, account_id: int, title: str, knowledge_text: str, priority: str = 'regular'):
        """Add knowledge for a specific Pyrogram account"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO account_knowledge (account_id, title, knowledge_text, priority, status, updated_at)
            VALUES (?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
        ''', (account_id, title, knowledge_text, priority))
        
        conn.commit()
        knowledge_id = cursor.lastrowid
        conn.close()
        logger.info(f"✅ Added {priority} knowledge for account #{account_id}: {title}")
        return knowledge_id
    
    def get_account_knowledge_list(self, account_id: int, priority_filter: str = None):
        """Get knowledge entries for a specific account"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if priority_filter:
            cursor.execute('''
                SELECT id, title, knowledge_text, priority, status, updated_at
                FROM account_knowledge
                WHERE account_id = ? AND priority = ?
                ORDER BY priority DESC, updated_at DESC
            ''', (account_id, priority_filter))
        else:
            cursor.execute('''
                SELECT id, title, knowledge_text, priority, status, updated_at
                FROM account_knowledge
                WHERE account_id = ?
                ORDER BY 
                    CASE priority 
                        WHEN 'super' THEN 0 
                        ELSE 1 
                    END,
                    updated_at DESC
            ''', (account_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        entries = []
        for row in results:
            kid, title, text, priority, status, updated_at = row
            entries.append({
                'id': kid,
                'title': title or f"Knowledge #{kid}",
                'text': text,
                'priority': priority,
                'status': status,
                'updated_at': updated_at
            })
        
        return entries
    
    def delete_account_knowledge(self, knowledge_id: int):
        """Delete account knowledge by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM account_knowledge WHERE id = ?', (knowledge_id,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        return deleted > 0
    
    def toggle_account_knowledge_status(self, knowledge_id: int):
        """Toggle account knowledge status between active/inactive"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE account_knowledge 
            SET status = CASE 
                WHEN status = 'active' THEN 'inactive'
                ELSE 'active'
            END,
            updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (knowledge_id,))
        
        conn.commit()
        conn.close()
    
    def get_account_knowledge_for_dm(self, account_id: int):
        """Get active knowledge for DM bot responses"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT knowledge_text
            FROM account_knowledge
            WHERE account_id = ? AND status = 'active'
            ORDER BY 
                CASE priority 
                    WHEN 'super' THEN 0 
                    ELSE 1 
                END,
                updated_at DESC
        ''', (account_id,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return None
        
        return '\n\n'.join([row[0] for row in results])
    
    async def show_super_knowledge_manage(self, query_or_message, user_id: int, knowledge_id: int, context=None):
        """Show super knowledge management interface"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, title, knowledge_text, target_scope, status, updated_at
            FROM bot_knowledge
            WHERE id = ? AND priority = 'super'
        ''', (knowledge_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            error_msg = f"❌ Super Knowledge #{knowledge_id} not found!"
            if hasattr(query_or_message, 'edit_message_text'):
                await query_or_message.edit_message_text(
                    error_msg,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back", callback_data="admin_list_super_knowledge")
                    ]])
                )
            else:
                await query_or_message.reply_text(
                    error_msg,
                    reply_markup=self.get_admin_keyboard()
                )
            return
        
        kid, title, text, scope, status, updated_at = result
        
        scope_map = {
            'main_only': '🤖 Main Bot Only',
            'dm_only': '💬 DM Bot Only',
            'both': '🤝 Both Bots'
        }
        scope_text = scope_map.get(scope, scope)
        status_icon = "✅ Active" if status == 'active' else "❌ Inactive"
        
        message_text = f"🧠 *SUPER KNOWLEDGE #{kid}*\n\n"
        message_text += f"*Title:* {title}\n"
        message_text += f"*Scope:* {scope_text}\n"
        message_text += f"*Status:* {status_icon}\n"
        message_text += f"*Updated:* {updated_at}\n\n"
        message_text += f"*Content:*\n{text}\n\n"
        message_text += "Manage this knowledge:"
        
        keyboard = [
            [InlineKeyboardButton(
                "✅ Activate" if status != 'active' else "❌ Deactivate",
                callback_data=f"sk_toggle_{kid}"
            )],
            [InlineKeyboardButton("🗑️ Delete", callback_data=f"sk_delete_{kid}")],
            [InlineKeyboardButton("« Back to List", callback_data="admin_list_super_knowledge")]
        ]
        
        if hasattr(query_or_message, 'edit_message_text'):
            await query_or_message.edit_message_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await query_or_message.reply_text(
                message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
    
    def get_deactivated_keys(self):
        """Get list of deactivated API keys"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT key_index, deactivation_reason, deactivated_at
            FROM api_key_stats
            WHERE is_deactivated = 1
            ORDER BY key_index
        ''')
        results = cursor.fetchall()
        conn.close()
        
        deactivated_keys = []
        for row in results:
            key_index, reason, deactivated_at = row
            deactivated_keys.append({
                'key_index': key_index,
                'key_number': key_index + 1,  # Human readable (1-indexed)
                'reason': reason or 'Unknown',
                'deactivated_at': deactivated_at
            })
        
        return deactivated_keys
    
    def get_admin_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("🧠 Super Knowledge", callback_data="admin_super_knowledge"),
                InlineKeyboardButton("📚 Knowledge Base", callback_data="admin_knowledge_menu")
            ],
            [
                InlineKeyboardButton("🔑 Keywords", callback_data="admin_keywords"),
                InlineKeyboardButton("🔑 API Key Stats", callback_data="admin_api_stats")
            ],
            [
                InlineKeyboardButton("🔴 Deactivated Keys", callback_data="admin_deactivated_keys"),
                InlineKeyboardButton("📝 Auto Messages", callback_data="admin_auto_messages")
            ],
            [
                InlineKeyboardButton("👥 View Users", callback_data="admin_view_users"),
                InlineKeyboardButton("📂 View User Chats", callback_data="admin_view_user_chats")
            ],
            [
                InlineKeyboardButton("🗑️ Delete Chats", callback_data="admin_delete_chats_menu"),
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")
            ],
            [
                InlineKeyboardButton("💬 Message User", callback_data="admin_message_user"),
                InlineKeyboardButton("🏘️ Group Sessions", callback_data="admin_group_sessions")
            ],
            [
                InlineKeyboardButton("📱 Multi-Account DM Bot", callback_data="admin_pyrogram_manager"),
                InlineKeyboardButton("🔄 Refresh Panel", callback_data="admin_refresh")
            ],
            [
                InlineKeyboardButton("🔚 End Session", callback_data="admin_end_session")
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
    
    def get_enhanced_knowledge(self, bot_type='main'):
        """
        Get knowledge with priority and scope filtering for enhanced AI understanding.
        bot_type: 'main' for main bot, 'dm' for pyrogram DM bot
        Returns: dict with 'super_knowledge' and 'regular_knowledge' lists
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get active knowledge filtered by scope and ordered by priority
        cursor.execute('''
            SELECT id, title, knowledge_text, priority, target_scope, updated_at
            FROM bot_knowledge
            WHERE status = 'active' 
            AND (target_scope = ? OR target_scope = 'both')
            ORDER BY 
                CASE priority 
                    WHEN 'super' THEN 0 
                    ELSE 1 
                END,
                updated_at DESC
        ''', (f'{bot_type}_only',))
        
        results = cursor.fetchall()
        conn.close()
        
        super_knowledge = []
        regular_knowledge = []
        
        for row in results:
            entry_id, title, text, priority, scope, updated_at = row
            entry = {
                'id': entry_id,
                'title': title or f"Knowledge #{entry_id}",
                'text': text,
                'scope': scope,
                'updated_at': updated_at
            }
            
            if priority == 'super':
                super_knowledge.append(entry)
            else:
                regular_knowledge.append(entry)
        
        return {
            'super': super_knowledge,
            'regular': regular_knowledge
        }
    
    def get_bot_knowledge(self):
        """Get all knowledge entries combined as text for AI (backward compatibility)"""
        knowledge = self.get_enhanced_knowledge(bot_type='main')
        all_entries = knowledge['super'] + knowledge['regular']
        
        if not all_entries:
            return None
        
        return '\n\n'.join([entry['text'] for entry in all_entries])
    
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
            stats_text = "🔑 *API Key & Token Statistics*\n\n"
            stats_text += f"📊 Total API Keys: {len(self.api_keys)}\n"
            stats_text += f"🔄 Currently Using: Key #{self.current_key_index + 1}\n"
            stats_text += f"💎 Daily Limit Per Key: 2.5M tokens (GPT-4o-mini)\n\n"
            
            if stats:
                # Calculate overall stats
                total_tokens_today = sum(s['tokens_used_today'] for s in stats)
                total_tokens_left = sum(s['tokens_left'] for s in stats)
                total_lifetime = sum(s['total_tokens_lifetime'] for s in stats)
                
                stats_text += "*📈 Overall Today:*\n"
                stats_text += f"🔥 Total Used: {total_tokens_today:,} tokens\n"
                stats_text += f"✅ Total Left: {total_tokens_left:,} tokens\n"
                stats_text += f"🌟 Lifetime Total: {total_lifetime:,} tokens\n\n"
                stats_text += "━━━━━━━━━━━━━━━━━\n\n"
                
                # Individual key stats (top 5 or all if less than 6)
                display_stats = stats[:5] if len(stats) > 5 else stats
                stats_text += "*🔑 Individual Keys:*\n"
                for s in display_stats:
                    key_num = s['key_index'] + 1
                    tokens_used = s['tokens_used_today']
                    tokens_left = s['tokens_left']
                    hours_left = s['hours_until_reset']
                    
                    # Status indicator
                    if tokens_left == 0:
                        status = "🔴 EXHAUSTED"
                    elif tokens_used == 0:
                        status = "🟢 FRESH"
                    elif tokens_left < 500000:
                        status = "🟡 LOW"
                    else:
                        status = "🟢 ACTIVE"
                    
                    stats_text += f"\n*Key #{key_num}* {status}\n"
                    stats_text += f"  📊 Used: {tokens_used:,} / {s['daily_limit']:,}\n"
                    stats_text += f"  💚 Left: {tokens_left:,} tokens\n"
                    stats_text += f"  📞 API Calls: {s['usage_count']}\n"
                    
                    if s['rate_limit_hits'] > 0:
                        stats_text += f"  ⚠️ Rate Hits: {s['rate_limit_hits']}\n"
                    
                    if hours_left is not None:
                        hours = int(hours_left)
                        mins = int((hours_left - hours) * 60)
                        stats_text += f"  ⏰ Resets in: {hours}h {mins}m\n"
                
                if len(stats) > 5:
                    remaining = len(stats) - 5
                    stats_text += f"\n_...and {remaining} more keys_\n"
            else:
                stats_text += "No usage data yet. Start using the bot!"
            
            await query.edit_message_text(
                stats_text,
                reply_markup=self.get_admin_keyboard(),
                parse_mode='Markdown'
            )
        
        elif data == "admin_deactivated_keys":
            deactivated = self.get_deactivated_keys()
            
            if not deactivated:
                msg_text = "🟢 *No Deactivated API Keys!*\n\n"
                msg_text += "Sab API keys kaam kar rahe hain! ✅"
            else:
                msg_text = f"🔴 *Deactivated API Keys ({len(deactivated)})*\n\n"
                msg_text += "⚠️ Ye API keys deactivated ho chuke hain:\n\n"
                
                for key in deactivated:
                    key_num = key['key_number']
                    reason = key['reason']
                    deactivated_at = key['deactivated_at']
                    
                    # Format reason in Hindi/English
                    if reason == "account_deactivated":
                        reason_text = "❌ Account Deactivated (401)"
                    elif reason == "forbidden":
                        reason_text = "🚫 Forbidden (403)"
                    elif reason == "invalid_key":
                        reason_text = "🔑 Invalid API Key"
                    elif reason == "rate_limit":
                        reason_text = "⏱️ Rate Limit Exceeded"
                    else:
                        reason_text = f"❓ {reason}"
                    
                    msg_text += f"*Key #{key_num}*\n"
                    msg_text += f"  └ Reason: {reason_text}\n"
                    if deactivated_at:
                        msg_text += f"  └ Time: {deactivated_at}\n"
                    msg_text += "\n"
                
                msg_text += "━━━━━━━━━━━━━━━━━\n\n"
                msg_text += "💡 *Note:* Bot automatically switches to working keys.\n"
                msg_text += "Deactivated keys ko replace kar dijiye naye keys se."
            
            await query.edit_message_text(
                msg_text,
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
        
        elif data == "admin_super_knowledge":
            keyboard = [
                [InlineKeyboardButton("➕ Add Super Knowledge", callback_data="admin_add_super_knowledge")],
                [InlineKeyboardButton("📋 List/Manage", callback_data="admin_list_super_knowledge")],
                [InlineKeyboardButton("« Back", callback_data="admin_refresh")]
            ]
            await query.edit_message_text(
                "🧠 *SUPER KNOWLEDGE*\n\n"
                "⚡ Super Knowledge = MANDATORY Administrator Directives\n\n"
                "*Features:*\n"
                "• Highest priority - bot MUST follow\n"
                "• Target specific bots (Main/DM/Both)\n"
                "• Your teachings override everything\n\n"
                "Choose an option:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_knowledge_menu":
            keyboard = [
                [InlineKeyboardButton("📚 View Knowledge", callback_data="admin_view_knowledge_old")],
                [InlineKeyboardButton("✏️ Add Knowledge", callback_data="admin_set_knowledge")],
                [InlineKeyboardButton("🗑️ Delete Knowledge", callback_data="admin_delete_knowledge")],
                [InlineKeyboardButton("« Back", callback_data="admin_refresh")]
            ]
            await query.edit_message_text(
                "📚 *REGULAR KNOWLEDGE BASE*\n\n"
                "Standard knowledge base for bot responses.\n\n"
                "Choose an option:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "admin_add_super_knowledge":
            self.admin_state[user_id] = "waiting_super_knowledge_title"
            await query.edit_message_text(
                "🧠 *ADD SUPER KNOWLEDGE*\n\n"
                "Step 1/3: Enter a TITLE for this knowledge\n\n"
                "*Example:* `Product Pricing Rules`\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_list_super_knowledge":
            entries = self.get_super_knowledge_list()
            
            if not entries:
                await query.edit_message_text(
                    "🧠 *SUPER KNOWLEDGE*\n\n"
                    "No super knowledge added yet!\n\n"
                    "Add your first MANDATORY directive to teach the bots.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back", callback_data="admin_super_knowledge")
                    ]]),
                    parse_mode='Markdown'
                )
                return
            
            text = f"🧠 *SUPER KNOWLEDGE LIST* ({len(entries)} entries)\n\n"
            
            for entry in entries[:10]:  # Show first 10
                status_icon = "✅" if entry['status'] == 'active' else "❌"
                scope_map = {
                    'main_only': '🤖 Main Bot Only',
                    'dm_only': '💬 DM Bot Only',
                    'both': '🤝 Both Bots'
                }
                scope_text = scope_map.get(entry['scope'], entry['scope'])
                
                text += f"{status_icon} *#{entry['id']}: {entry['title']}*\n"
                text += f"   Scope: {scope_text}\n"
                text += f"   Updated: {entry['updated_at'][:10]}\n"
                text += f"   Preview: {entry['text'][:50]}...\n\n"
            
            if len(entries) > 10:
                text += f"_...and {len(entries) - 10} more entries_\n\n"
            
            text += "\n💡 Send knowledge ID number to manage it\n"
            text += "Example: Send `5` to manage knowledge #5"
            
            self.admin_state[user_id] = "waiting_super_knowledge_id"
            await query.edit_message_text(
                text,
                parse_mode='Markdown'
            )
        
        elif data.startswith("sk_toggle_"):
            # Toggle super knowledge active/inactive
            knowledge_id = int(data.split("_")[2])
            self.toggle_knowledge_status(knowledge_id)
            await query.answer("✅ Status toggled!")
            # Refresh the manage view
            await self.show_super_knowledge_manage(query, user_id, knowledge_id)
        
        elif data.startswith("sk_delete_"):
            # Delete super knowledge
            knowledge_id = int(data.split("_")[2])
            self.delete_super_knowledge(knowledge_id)
            await query.answer("🗑️ Deleted!")
            await query.edit_message_text(
                "✅ *Super Knowledge Deleted!*",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to List", callback_data="admin_list_super_knowledge")
                ]]),
                parse_mode='Markdown'
            )
        
        elif data.startswith("sk_scope_"):
            # Handle super knowledge scope selection
            scope = data.replace("sk_scope_", "")
            
            if user_id not in self.admin_state or not self.admin_state[user_id].startswith("waiting_super_knowledge_scope:"):
                await query.answer("❌ Session expired! Please start again.")
                await query.edit_message_text(
                    "❌ Session expired. Please add super knowledge again.",
                    reply_markup=self.get_admin_keyboard()
                )
                return
            
            # Extract title and knowledge text
            state_data = self.admin_state[user_id].replace("waiting_super_knowledge_scope:", "")
            parts = state_data.split("|||")
            if len(parts) != 2:
                await query.answer("❌ Error! Please start again.")
                return
            
            title, knowledge_text = parts
            
            # Add super knowledge to database
            knowledge_id = self.add_super_knowledge(title, knowledge_text, scope)
            
            del self.admin_state[user_id]
            await query.answer("✅ Super Knowledge Added!")
            
            scope_map = {
                'main_only': '🤖 Main Bot Only',
                'dm_only': '💬 DM Bot Only',
                'both': '🤝 Both Bots'
            }
            scope_text = scope_map.get(scope, scope)
            
            await query.edit_message_text(
                f"✅ *SUPER KNOWLEDGE ADDED!*\n\n"
                f"*ID:* #{knowledge_id}\n"
                f"*Title:* {title}\n"
                f"*Scope:* {scope_text}\n\n"
                f"*Content Preview:*\n{knowledge_text[:200]}{'...' if len(knowledge_text) > 200 else ''}\n\n"
                f"✅ This MANDATORY knowledge is now ACTIVE and will be applied to bot responses!",
                reply_markup=self.get_admin_keyboard(),
                parse_mode='Markdown'
            )
            logger.info(f"Admin {user_id} added super knowledge #{knowledge_id}: {title} (scope: {scope})")
        
        elif data == "admin_pyrogram_manager":
            # Get all Pyrogram accounts
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, phone_number, account_name, is_active, is_authenticated, reply_count FROM pyrogram_accounts ORDER BY created_at DESC')
            accounts = cursor.fetchall()
            conn.close()
            
            if not accounts:
                text = "📱 *MULTI-ACCOUNT DM BOT MANAGER*\n\n"
                text += "No accounts added yet!\n\n"
                text += "Add Pyrogram accounts to enable automated replies on multiple phone numbers.\n\n"
                text += "⚠️ *Requirements:*\n"
                text += "• Valid phone numbers with Telegram accounts\n"
                text += "• Telegram API ID & API Hash from my.telegram.org\n"
                text += "• Access to OTP for authentication\n\n"
                text += "Add your first account to get started!"
                
                keyboard = [
                    [InlineKeyboardButton("➕ Add Account", callback_data="pyrogram_add_account")],
                    [InlineKeyboardButton("« Back", callback_data="admin_refresh")]
                ]
            else:
                text = f"📱 *MULTI-ACCOUNT DM BOT MANAGER*\n\n"
                text += f"Total Accounts: {len(accounts)}\n\n"
                
                for acc_id, phone, name, is_active, is_auth, replies in accounts[:5]:
                    status = "🟢 Active" if is_active else "🔴 Inactive"
                    auth = "✅ Auth" if is_auth else "⚠️ Not Auth"
                    text += f"*{name}*\n"
                    text += f"  Phone: +{phone}\n"
                    text += f"  Status: {status} | {auth}\n"
                    text += f"  Replies: {replies}\n\n"
                
                keyboard = [
                    [InlineKeyboardButton("➕ Add Account", callback_data="pyrogram_add_account")],
                    [InlineKeyboardButton("📋 View All", callback_data="pyrogram_list_accounts")],
                    [InlineKeyboardButton("🧠 Manage Account Knowledge", callback_data="pyrogram_manage_knowledge")],
                    [InlineKeyboardButton("▶️ Start All", callback_data="pyrogram_start_all")],
                    [InlineKeyboardButton("⏹️ Stop All", callback_data="pyrogram_stop_all")],
                    [InlineKeyboardButton("« Back", callback_data="admin_refresh")]
                ]
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        
        elif data == "pyrogram_add_account":
            self.admin_state[user_id] = "waiting_pyrogram_api_id"
            await query.edit_message_text(
                "📱 *ADD PYROGRAM ACCOUNT*\n\n"
                "Step 1/5: Send your Telegram API ID\n\n"
                "*Where to get it?*\n"
                "1. Visit: https://my.telegram.org/apps\n"
                "2. Login with your phone number\n"
                "3. Create an app (if not already done)\n"
                "4. Copy the *API ID* number\n\n"
                "*Example:* 12345678\n\n"
                "⚠️ Each bot can have its own API credentials!\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "pyrogram_list_accounts":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, phone_number, account_name, is_active, is_authenticated, reply_count, last_active, error_message FROM pyrogram_accounts ORDER BY created_at DESC')
            accounts = cursor.fetchall()
            conn.close()
            
            if not accounts:
                text = "No accounts found!"
                keyboard = [
                    [InlineKeyboardButton("« Back", callback_data="admin_pyrogram_manager")]
                ]
            else:
                text = f"📱 *ALL PYROGRAM ACCOUNTS ({len(accounts)})*\n\n"
                keyboard = []
                
                for acc_id, phone, name, is_active, is_auth, replies, last_active, error in accounts[:10]:
                    status = "🟢 Active" if is_active else "🔴 Inactive"
                    auth = "✅ Authenticated" if is_auth else "⚠️ Not Authenticated"
                    text += f"*{name}* (ID: {acc_id})\n"
                    text += f"  Phone: +{phone}\n"
                    text += f"  Status: {status}\n"
                    text += f"  Auth: {auth}\n"
                    text += f"  Replies: {replies}\n"
                    if error:
                        text += f"  Error: {error[:50]}...\n"
                    text += f"  Last: {last_active or 'Never'}\n\n"
                    
                    # Add toggle button for each account
                    if is_auth:
                        toggle_text = "⏹️ Deactivate" if is_active else "▶️ Activate"
                        keyboard.append([InlineKeyboardButton(
                            f"{toggle_text} {name}",
                            callback_data=f"pyro_toggle_{acc_id}"
                        )])
                
                keyboard.append([InlineKeyboardButton("🗑️ Delete Account", callback_data="pyro_delete_menu")])
                keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_pyrogram_manager")])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data.startswith("pyro_toggle_"):
            account_id = int(data.split("_")[2])
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Toggle is_active status
            cursor.execute('''
                UPDATE pyrogram_accounts
                SET is_active = CASE 
                    WHEN is_active = 1 THEN 0
                    ELSE 1
                END
                WHERE id = ?
            ''', (account_id,))
            conn.commit()
            
            # Get new status
            cursor.execute('SELECT is_active, account_name FROM pyrogram_accounts WHERE id = ?', (account_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                is_active, name = result
                status_text = "activated" if is_active else "deactivated"
                await query.answer(f"✅ {name} {status_text}!")
                logger.info(f"Admin {user_id} {status_text} Pyrogram account #{account_id}")
            
            # Refresh list
            await query.message.edit_reply_markup(reply_markup=None)
            await asyncio.sleep(0.5)
            
            # Re-trigger list view
            data = "pyrogram_list_accounts"
            # Fall through to list view below
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, phone_number, account_name, is_active, is_authenticated, reply_count, last_active, error_message FROM pyrogram_accounts ORDER BY created_at DESC')
            accounts = cursor.fetchall()
            conn.close()
            
            text = f"📱 *ALL PYROGRAM ACCOUNTS ({len(accounts)})*\n\n"
            keyboard = []
            
            for acc_id, phone, name, is_active, is_auth, replies, last_active, error in accounts[:10]:
                status = "🟢 Active" if is_active else "🔴 Inactive"
                auth = "✅ Authenticated" if is_auth else "⚠️ Not Authenticated"
                text += f"*{name}* (ID: {acc_id})\n"
                text += f"  Phone: +{phone}\n"
                text += f"  Status: {status}\n"
                text += f"  Auth: {auth}\n"
                text += f"  Replies: {replies}\n"
                if error:
                    text += f"  Error: {error[:50]}...\n"
                text += f"  Last: {last_active or 'Never'}\n\n"
                
                if is_auth:
                    toggle_text = "⏹️ Deactivate" if is_active else "▶️ Activate"
                    keyboard.append([InlineKeyboardButton(
                        f"{toggle_text} {name}",
                        callback_data=f"pyro_toggle_{acc_id}"
                    )])
            
            keyboard.append([InlineKeyboardButton("🗑️ Delete Account", callback_data="pyro_delete_menu")])
            keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_pyrogram_manager")])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data == "pyro_delete_menu":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, phone_number, account_name FROM pyrogram_accounts ORDER BY created_at DESC')
            accounts = cursor.fetchall()
            conn.close()
            
            if not accounts:
                await query.edit_message_text(
                    "No accounts to delete!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back", callback_data="pyrogram_list_accounts")
                    ]])
                )
                return
            
            text = "🗑️ *DELETE PYROGRAM ACCOUNT*\n\n"
            text += "⚠️ WARNING: This will permanently delete the account from the database!\n\n"
            text += "Select account to delete:\n\n"
            
            keyboard = []
            for acc_id, phone, name in accounts[:10]:
                text += f"• {name} (+{phone})\n"
                keyboard.append([InlineKeyboardButton(
                    f"🗑️ Delete {name}",
                    callback_data=f"pyro_delete_{acc_id}"
                )])
            
            keyboard.append([InlineKeyboardButton("« Cancel", callback_data="pyrogram_list_accounts")])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data.startswith("pyro_delete_"):
            account_id = int(data.split("_")[2])
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT account_name FROM pyrogram_accounts WHERE id = ?', (account_id,))
            result = cursor.fetchone()
            
            account_name = "Unknown"
            if result:
                account_name = result[0]
                cursor.execute('DELETE FROM pyrogram_accounts WHERE id = ?', (account_id,))
                conn.commit()
                await query.answer(f"🗑️ {account_name} deleted!")
                logger.info(f"Admin {user_id} deleted Pyrogram account #{account_id}: {account_name}")
            
            conn.close()
            
            await query.edit_message_text(
                f"✅ *Account Deleted!*\n\n{account_name} has been removed from the database.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back to List", callback_data="pyrogram_list_accounts")
                ]]),
                parse_mode='Markdown'
            )
        
        elif data == "pyrogram_start_all":
            await query.answer("⚠️ Feature coming soon! Use start_both_bots.py to start Pyrogram bots.")
            await query.edit_message_text(
                "⚠️ *MULTI-ACCOUNT AUTOMATION*\n\n"
                "To use multiple Pyrogram accounts:\n\n"
                "1. Set environment variables:\n"
                "   • TELEGRAM_API_ID\n"
                "   • TELEGRAM_API_HASH\n\n"
                "2. Run: `python start_both_bots.py`\n\n"
                "This will start all authenticated accounts.\n\n"
                "📝 *Note:* Each account needs authentication first (OTP verification).",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back", callback_data="admin_pyrogram_manager")
                ]]),
                parse_mode='Markdown'
            )
        
        elif data == "pyrogram_stop_all":
            await query.answer("ℹ️ Stop the process/deployment to stop all bots.")
        
        elif data == "pyrogram_manage_knowledge":
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT id, phone_number, account_name, is_authenticated FROM pyrogram_accounts ORDER BY created_at DESC')
            accounts = cursor.fetchall()
            conn.close()
            
            if not accounts:
                await query.edit_message_text(
                    "📱 *ACCOUNT KNOWLEDGE MANAGER*\n\n"
                    "No accounts found!\n\n"
                    "Add accounts first before managing their knowledge.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back", callback_data="admin_pyrogram_manager")
                    ]]),
                    parse_mode='Markdown'
                )
                return
            
            text = f"📱 *SELECT ACCOUNT TO MANAGE KNOWLEDGE*\n\n"
            text += f"Total Accounts: {len(accounts)}\n\n"
            text += "Choose an account to manage its custom knowledge:\n\n"
            
            keyboard = []
            for acc_id, phone, name, is_auth in accounts[:10]:
                auth_icon = "✅" if is_auth else "⚠️"
                keyboard.append([InlineKeyboardButton(
                    f"{auth_icon} {name} (+{phone})",
                    callback_data=f"pyro_know_{acc_id}"
                )])
            
            keyboard.append([InlineKeyboardButton("« Back", callback_data="admin_pyrogram_manager")])
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data.startswith("pyro_know_"):
            account_id = int(data.split("_")[2])
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT account_name, phone_number FROM pyrogram_accounts WHERE id = ?', (account_id,))
            account = cursor.fetchone()
            
            if not account:
                await query.answer("❌ Account not found!")
                return
            
            account_name, phone = account
            
            # Get knowledge count
            cursor.execute('SELECT COUNT(*) FROM account_knowledge WHERE account_id = ?', (account_id,))
            knowledge_count = cursor.fetchone()[0]
            conn.close()
            
            text = f"🧠 *KNOWLEDGE FOR: {account_name}*\n\n"
            text += f"📱 Phone: +{phone}\n"
            text += f"📚 Knowledge Entries: {knowledge_count}\n\n"
            text += "What would you like to do?"
            
            keyboard = [
                [InlineKeyboardButton("➕ Add Knowledge", callback_data=f"pyro_know_add_{account_id}")],
                [InlineKeyboardButton("📋 View Knowledge", callback_data=f"pyro_know_list_{account_id}")],
                [InlineKeyboardButton("🗑️ Delete Knowledge", callback_data=f"pyro_know_del_{account_id}")],
                [InlineKeyboardButton("« Back", callback_data="pyrogram_manage_knowledge")]
            ]
            
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        elif data.startswith("pyro_know_add_"):
            account_id = int(data.split("_")[3])
            self.admin_state[user_id] = f"waiting_account_knowledge_text:{account_id}"
            await query.edit_message_text(
                f"🧠 *ADD ACCOUNT KNOWLEDGE*\n\n"
                f"Send the knowledge/instruction for this specific account.\n\n"
                f"*Example:*\n"
                f"\"When users ask about pricing, mention our special discount code SAVE20 for 20% off.\"\n\n"
                f"⚠️ This knowledge will ONLY apply to this specific account!\n\n"
                f"Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data.startswith("pyro_know_list_"):
            account_id = int(data.split("_")[3])
            
            entries = self.get_account_knowledge_list(account_id)
            
            if not entries:
                await query.edit_message_text(
                    f"🧠 *ACCOUNT KNOWLEDGE*\n\n"
                    f"No knowledge added for this account yet!\n\n"
                    f"Add custom knowledge to customize this bot's behavior.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back", callback_data=f"pyro_know_{account_id}")
                    ]]),
                    parse_mode='Markdown'
                )
                return
            
            text = f"🧠 *ACCOUNT KNOWLEDGE LIST* ({len(entries)} entries)\n\n"
            
            for entry in entries[:10]:
                status_icon = "✅" if entry['status'] == 'active' else "❌"
                priority_icon = "🔥" if entry['priority'] == 'super' else "📌"
                
                text += f"{status_icon} {priority_icon} *#{entry['id']}*\n"
                text += f"   {entry['text'][:80]}...\n"
                text += f"   Updated: {entry['updated_at'][:10]}\n\n"
            
            if len(entries) > 10:
                text += f"_...and {len(entries) - 10} more entries_"
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("« Back", callback_data=f"pyro_know_{account_id}")
                ]]),
                parse_mode='Markdown'
            )
        
        elif data.startswith("pyro_know_del_"):
            account_id = int(data.split("_")[3])
            
            entries = self.get_account_knowledge_list(account_id)
            
            if not entries:
                await query.edit_message_text(
                    "No knowledge to delete!",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("« Back", callback_data=f"pyro_know_{account_id}")
                    ]])
                )
                return
            
            text = f"🗑️ *DELETE ACCOUNT KNOWLEDGE*\n\n"
            text += "Send the knowledge ID number to delete:\n\n"
            
            for entry in entries[:10]:
                text += f"*#{entry['id']}:* {entry['text'][:50]}...\n"
            
            self.admin_state[user_id] = f"waiting_account_knowledge_delete:{account_id}"
            await query.edit_message_text(text, parse_mode='Markdown')
        
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
            
            elif state == "waiting_super_knowledge_title":
                title = user_message.strip()
                if not title or len(title) < 3:
                    await update.message.reply_text(
                        "❌ Title too short! Please send a meaningful title (at least 3 characters).",
                        parse_mode='Markdown'
                    )
                    return
                
                self.admin_state[user.id] = f"waiting_super_knowledge_text:{title}"
                await update.message.reply_text(
                    f"✅ *Title Set:* `{title}`\n\n"
                    f"Step 2/3: Now send the SUPER KNOWLEDGE content\n\n"
                    f"*This is MANDATORY knowledge that bots MUST follow*\n\n"
                    f"*Example:*\n"
                    f"\"When user asks about pricing, ALWAYS mention our premium package at ₹999/month with 24/7 support and unlimited features. This is the ONLY package we offer.\"\n\n"
                    f"Send /cancel to cancel.",
                    parse_mode='Markdown'
                )
                return
            
            elif state.startswith("waiting_super_knowledge_text:"):
                title = state.split(":", 1)[1]
                knowledge_text = user_message.strip()
                
                if not knowledge_text or len(knowledge_text) < 10:
                    await update.message.reply_text(
                        "❌ Knowledge text too short! Please send meaningful content (at least 10 characters).",
                        parse_mode='Markdown'
                    )
                    return
                
                self.admin_state[user.id] = f"waiting_super_knowledge_scope:{title}|||{knowledge_text}"
                
                await update.message.reply_text(
                    f"✅ *Knowledge Content Received!*\n\n"
                    f"Step 3/3: Choose TARGET SCOPE\n\n"
                    f"*Where should this knowledge be applied?*\n\n"
                    f"Send one of these options:\n"
                    f"1️⃣ `main` - Main Bot Only (Telegram bot only)\n"
                    f"2️⃣ `dm` - DM Bot Only (Pyrogram accounts only)\n"
                    f"3️⃣ `both` - Both Bots (Apply everywhere)\n\n"
                    f"*Example:* Just type `both` or `dm` or `main`\n\n"
                    f"Send /cancel to cancel.",
                    parse_mode='Markdown'
                )
                return
            
            elif state.startswith("waiting_super_knowledge_scope:"):
                scope_input = user_message.strip().lower()
                
                scope_mapping = {
                    'main': 'main_only',
                    'main_only': 'main_only',
                    'dm': 'dm_only',
                    'dm_only': 'dm_only',
                    'both': 'both',
                    '1': 'main_only',
                    '2': 'dm_only',
                    '3': 'both'
                }
                
                scope = scope_mapping.get(scope_input)
                
                if not scope:
                    await update.message.reply_text(
                        "❌ Invalid choice! Please send:\n"
                        "• `main` for Main Bot Only\n"
                        "• `dm` for DM Bot Only\n"
                        "• `both` for Both Bots\n\n"
                        "Or send /cancel to cancel.",
                        parse_mode='Markdown'
                    )
                    return
                
                state_data = self.admin_state[user.id].replace("waiting_super_knowledge_scope:", "")
                parts = state_data.split("|||")
                if len(parts) != 2:
                    await update.message.reply_text(
                        "❌ Error! Please start again.",
                        reply_markup=self.get_admin_keyboard()
                    )
                    del self.admin_state[user.id]
                    return
                
                title, knowledge_text = parts
                
                knowledge_id = self.add_super_knowledge(title, knowledge_text, scope)
                
                del self.admin_state[user.id]
                
                scope_map = {
                    'main_only': '🤖 Main Bot Only',
                    'dm_only': '💬 DM Bot Only',
                    'both': '🤝 Both Bots'
                }
                scope_text = scope_map.get(scope, scope)
                
                await update.message.reply_text(
                    f"✅ *SUPER KNOWLEDGE ADDED!*\n\n"
                    f"*ID:* #{knowledge_id}\n"
                    f"*Title:* {title}\n"
                    f"*Scope:* {scope_text}\n\n"
                    f"*Content Preview:*\n{knowledge_text[:200]}{'...' if len(knowledge_text) > 200 else ''}\n\n"
                    f"✅ This MANDATORY knowledge is now ACTIVE and will be applied to bot responses!",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {user.id} added super knowledge #{knowledge_id}: {title} (scope: {scope})")
                return
            
            elif state == "waiting_super_knowledge_id":
                try:
                    knowledge_id = int(user_message.strip())
                    await self.show_super_knowledge_manage(update.message, user.id, knowledge_id, context)
                    del self.admin_state[user.id]
                except ValueError:
                    await update.message.reply_text(
                        "❌ Please send a valid knowledge ID number!",
                        parse_mode='Markdown'
                    )
                return
            
            elif state == "waiting_pyrogram_api_id":
                api_id = user_message.strip()
                if not api_id.isdigit():
                    await update.message.reply_text(
                        "❌ Invalid API ID! Please send only numbers.\n\n"
                        "*Example:* 12345678\n\n"
                        "Send /cancel to cancel.",
                        parse_mode='Markdown'
                    )
                    return
                
                self.admin_state[user.id] = f"waiting_pyrogram_api_hash:{api_id}"
                await update.message.reply_text(
                    f"✅ *API ID:* `{api_id}`\n\n"
                    f"Step 2/5: Send your Telegram API Hash\n\n"
                    f"*Where to find it?*\n"
                    f"On the same page: https://my.telegram.org/apps\n"
                    f"Copy the *API Hash* string\n\n"
                    f"*Example:* 1a2b3c4d5e6f7g8h9i0j\n\n"
                    f"Send /cancel to cancel.",
                    parse_mode='Markdown'
                )
                return
            
            elif state.startswith("waiting_pyrogram_api_hash:"):
                api_id = state.split(":", 1)[1]
                api_hash = user_message.strip()
                
                if len(api_hash) < 10:
                    await update.message.reply_text(
                        "❌ API Hash seems too short! Please check and send again.\n\n"
                        "Send /cancel to cancel.",
                        parse_mode='Markdown'
                    )
                    return
                
                self.admin_state[user.id] = f"waiting_pyrogram_phone:{api_id}|||{api_hash}"
                await update.message.reply_text(
                    f"✅ *API Hash:* `{api_hash[:10]}...`\n\n"
                    f"Step 3/5: Send the phone number\n\n"
                    f"*Format:* Country code + number (without + or spaces)\n"
                    f"*Example:* 919876543210\n\n"
                    f"⚠️ Make sure you have:\n"
                    f"• Access to this phone number\n"
                    f"• Can receive OTP on this number\n"
                    f"• Telegram account on this number\n\n"
                    f"Send /cancel to cancel.",
                    parse_mode='Markdown'
                )
                return
            
            elif state.startswith("waiting_pyrogram_phone:"):
                parts = state.split(":", 1)[1].split("|||")
                api_id = parts[0]
                api_hash = parts[1]
                phone = user_message.strip().replace('+', '').replace(' ', '').replace('-', '')
                
                if not phone.isdigit() or len(phone) < 10:
                    await update.message.reply_text(
                        "❌ Invalid phone number! Please send a valid phone number.\n\n"
                        "*Example:* 919876543210 (without + or spaces)\n\n"
                        "Send /cancel to cancel.",
                        parse_mode='Markdown'
                    )
                    return
                
                self.admin_state[user.id] = f"waiting_pyrogram_name:{api_id}|||{api_hash}|||{phone}"
                await update.message.reply_text(
                    f"✅ *Phone:* `+{phone}`\n\n"
                    f"Step 4/5: Send a NAME for this account\n\n"
                    f"*Example:* `Personal Account 1` or `Business DM Bot`\n\n"
                    f"Send /cancel to cancel.",
                    parse_mode='Markdown'
                )
                return
            
            elif state.startswith("waiting_pyrogram_name:"):
                parts = state.split(":", 1)[1].split("|||")
                api_id = parts[0]
                api_hash = parts[1]
                phone = parts[2]
                account_name = user_message.strip()
                
                try:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    
                    # Check if phone already exists
                    cursor.execute('SELECT id, account_name FROM pyrogram_accounts WHERE phone_number = ?', (phone,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        conn.close()
                        await update.message.reply_text(
                            f"❌ *Phone Already Added!*\n\n"
                            f"Phone +{phone} is already registered as:\n"
                            f"*{existing[1]}* (ID: {existing[0]})\n\n"
                            f"Please use a different phone number.",
                            reply_markup=self.get_admin_keyboard(),
                            parse_mode='Markdown'
                        )
                        del self.admin_state[user.id]
                        return
                    
                    # Insert account with API credentials
                    cursor.execute('''
                        INSERT INTO pyrogram_accounts (phone_number, account_name, api_id, api_hash, is_active, is_authenticated)
                        VALUES (?, ?, ?, ?, 0, 0)
                    ''', (phone, account_name, api_id, api_hash))
                    conn.commit()
                    account_id = cursor.lastrowid
                    conn.close()
                    
                    # Now request OTP
                    await update.message.reply_text(
                        f"✅ *Account Details Saved!*\n\n"
                        f"*Name:* {account_name}\n"
                        f"*Phone:* +{phone}\n"
                        f"*API ID:* {api_id}\n\n"
                        f"🔐 Sending OTP to +{phone}...\n\n"
                        f"Please wait...",
                        parse_mode='Markdown'
                    )
                    
                    # Import and use pyrogram auth
                    from pyrogram_auto_auth import PyrogramAuthenticator
                    authenticator = PyrogramAuthenticator(self.db_path)
                    
                    # Request OTP
                    success, phone_code_hash = await authenticator.request_code_only(phone, int(api_id), api_hash)
                    
                    if success:
                        self.admin_state[user.id] = f"waiting_pyrogram_otp:{account_id}|||{phone}|||{api_id}|||{api_hash}|||{phone_code_hash}"
                        await update.message.reply_text(
                            f"✅ *OTP Sent Successfully!*\n\n"
                            f"Step 5/5: Check your Telegram app on +{phone}\n\n"
                            f"📩 You should have received a login code.\n\n"
                            f"*Send the OTP code here*\n"
                            f"*Example:* 12345\n\n"
                            f"⚠️ Code expires in ~2 minutes! Enter it quickly.\n"
                            f"💡 If it expires, I'll automatically send you a new one.\n\n"
                            f"Send /cancel to cancel.",
                            parse_mode='Markdown'
                        )
                        logger.info(f"OTP requested for account #{account_id} (+{phone})")
                    else:
                        await update.message.reply_text(
                            f"❌ *Failed to send OTP!*\n\n"
                            f"Error: {phone_code_hash}\n\n"
                            f"Please try again later or check your credentials.",
                            reply_markup=self.get_admin_keyboard(),
                            parse_mode='Markdown'
                        )
                        # Delete the account
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        cursor.execute('DELETE FROM pyrogram_accounts WHERE id = ?', (account_id,))
                        conn.commit()
                        conn.close()
                        del self.admin_state[user.id]
                    
                except Exception as e:
                    logger.error(f"Failed to add Pyrogram account: {e}")
                    await update.message.reply_text(
                        f"❌ Failed to add account: {str(e)}\n\n"
                        f"Please try again or contact support.",
                        reply_markup=self.get_admin_keyboard()
                    )
                    if user.id in self.admin_state:
                        del self.admin_state[user.id]
                return
            
            elif state.startswith("waiting_pyrogram_otp:"):
                parts = state.split(":", 1)[1].split("|||")
                account_id = int(parts[0])
                phone = parts[1]
                api_id = parts[2]
                api_hash = parts[3]
                phone_code_hash = parts[4]
                otp_code = user_message.strip()
                
                if not otp_code.isdigit() or len(otp_code) != 5:
                    await update.message.reply_text(
                        "❌ Invalid OTP! Please send the 5-digit code.\n\n"
                        "*Example:* 12345\n\n"
                        "Send /cancel to cancel.",
                        parse_mode='Markdown'
                    )
                    return
                
                await update.message.reply_text(
                    f"🔐 Authenticating with Telegram...\n\n"
                    f"Please wait...",
                    parse_mode='Markdown'
                )
                
                try:
                    from pyrogram_auto_auth import PyrogramAuthenticator
                    authenticator = PyrogramAuthenticator(self.db_path)
                    
                    # Authenticate with OTP
                    success, message = await authenticator.authenticate_account_with_hash(
                        account_id, phone, int(api_id), api_hash, otp_code, phone_code_hash
                    )
                    
                    if success:
                        del self.admin_state[user.id]
                        await update.message.reply_text(
                            f"✅ *AUTHENTICATION SUCCESSFUL!*\n\n"
                            f"🎉 Account #{account_id} is now authenticated and ready!\n\n"
                            f"*Phone:* +{phone}\n"
                            f"*Status:* ✅ Authenticated\n\n"
                            f"You can now:\n"
                            f"• Activate/deactivate this bot\n"
                            f"• Add custom knowledge for this bot\n"
                            f"• Manage its behavior separately\n\n"
                            f"Use the Pyrogram Manager to control it!",
                            reply_markup=self.get_admin_keyboard(),
                            parse_mode='Markdown'
                        )
                        logger.info(f"Admin {user.id} successfully authenticated Pyrogram account #{account_id}")
                    else:
                        # Check if code expired, if yes, automatically request a new code
                        if "PHONE_CODE_EXPIRED" in message or "expired" in message.lower():
                            await update.message.reply_text(
                                f"⏰ *OTP Code Expired!*\n\n"
                                f"Don't worry, I'm sending you a fresh code...",
                                parse_mode='Markdown'
                            )
                            
                            # Request a new code
                            new_success, new_phone_code_hash = await authenticator.request_code_only(phone, int(api_id), api_hash)
                            
                            if new_success:
                                # Update the state with new hash
                                self.admin_state[user.id] = f"waiting_pyrogram_otp:{account_id}|||{phone}|||{api_id}|||{api_hash}|||{new_phone_code_hash}"
                                await update.message.reply_text(
                                    f"✅ *New OTP Code Sent!*\n\n"
                                    f"📩 A fresh login code has been sent to +{phone}\n\n"
                                    f"*Please send the NEW code here*\n"
                                    f"*Example:* 12345\n\n"
                                    f"⚠️ Please enter it quickly this time (expires in ~2 minutes)\n\n"
                                    f"Send /cancel to cancel.",
                                    parse_mode='Markdown'
                                )
                                logger.info(f"Resent OTP for account #{account_id} (+{phone}) after expiration")
                            else:
                                await update.message.reply_text(
                                    f"❌ *Failed to resend OTP!*\n\n"
                                    f"Error: {new_phone_code_hash}\n\n"
                                    f"Please try adding the account again from the Pyrogram Manager.",
                                    reply_markup=self.get_admin_keyboard(),
                                    parse_mode='Markdown'
                                )
                                del self.admin_state[user.id]
                        else:
                            # Other errors (2FA, invalid code, etc.)
                            await update.message.reply_text(
                                f"❌ *Authentication Failed!*\n\n"
                                f"Error: {message}\n\n"
                                f"Please try adding the account again.",
                                reply_markup=self.get_admin_keyboard(),
                                parse_mode='Markdown'
                            )
                            del self.admin_state[user.id]
                
                except Exception as e:
                    logger.error(f"Failed to authenticate: {e}")
                    await update.message.reply_text(
                        f"❌ Authentication error: {str(e)}\n\n"
                        f"Please try again.",
                        reply_markup=self.get_admin_keyboard()
                    )
                    if user.id in self.admin_state:
                        del self.admin_state[user.id]
                return
            
            elif state.startswith("waiting_account_knowledge_text:"):
                account_id = int(state.split(":", 1)[1])
                knowledge_text = user_message.strip()
                
                if len(knowledge_text) < 10:
                    await update.message.reply_text(
                        "❌ Knowledge text too short! Please send at least 10 characters.",
                        parse_mode='Markdown'
                    )
                    return
                
                try:
                    # Auto-generate title from first 50 chars of knowledge
                    title = f"Knowledge {account_id}-{datetime.now().strftime('%H%M')}"
                    knowledge_id = self.add_account_knowledge(account_id, title, knowledge_text)
                    del self.admin_state[user.id]
                    
                    await update.message.reply_text(
                        f"✅ *ACCOUNT KNOWLEDGE ADDED!*\n\n"
                        f"*Knowledge ID:* #{knowledge_id}\n"
                        f"*For Account:* ID #{account_id}\n\n"
                        f"*Content:*\n{knowledge_text[:200]}{'...' if len(knowledge_text) > 200 else ''}\n\n"
                        f"✅ This knowledge is now ACTIVE for this specific account!",
                        reply_markup=self.get_admin_keyboard(),
                        parse_mode='Markdown'
                    )
                    logger.info(f"Admin {user.id} added knowledge to account #{account_id}")
                except Exception as e:
                    logger.error(f"Failed to add account knowledge: {e}")
                    await update.message.reply_text(
                        f"❌ Failed to add knowledge: {str(e)}",
                        reply_markup=self.get_admin_keyboard()
                    )
                    if user.id in self.admin_state:
                        del self.admin_state[user.id]
                return
            
            elif state.startswith("waiting_account_knowledge_delete:"):
                account_id = int(state.split(":", 1)[1])
                try:
                    knowledge_id = int(user_message.strip())
                    
                    if self.delete_account_knowledge(knowledge_id):
                        del self.admin_state[user.id]
                        await update.message.reply_text(
                            f"✅ *Knowledge Deleted!*\n\n"
                            f"Knowledge #{knowledge_id} has been removed from account #{account_id}.",
                            reply_markup=self.get_admin_keyboard(),
                            parse_mode='Markdown'
                        )
                        logger.info(f"Admin {user.id} deleted knowledge #{knowledge_id} from account #{account_id}")
                    else:
                        await update.message.reply_text(
                            "❌ Failed to delete knowledge! ID not found.",
                            reply_markup=self.get_admin_keyboard()
                        )
                        del self.admin_state[user.id]
                except ValueError:
                    await update.message.reply_text(
                        "❌ Please send a valid knowledge ID number!",
                        parse_mode='Markdown'
                    )
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
            
            # Get enhanced knowledge with priority system
            knowledge_data = self.get_enhanced_knowledge(bot_type='main')
            super_knowledge = knowledge_data['super']
            regular_knowledge = knowledge_data['regular']
            
            system_prompt = "Tum ek highly intelligent aur helpful AI assistant ho. Tumhe Hindi aur English dono languages mein expert tarike se baat karni aani hai."
            
            system_prompt += f"\n\nUser ka naam: {user_first_name}"
            if user_username:
                system_prompt += f" (@{user_username})"
            system_prompt += "\nNatural conversation mein user ka naam use kar sakte ho jab appropriate ho."
            
            system_prompt += f"\n\n🔐 IMPORTANT - OWNER RESPECT: Tumhare owner ka naam @tgshaitaan hai. Jab bhi owner baat kare ya unka zikr ho, tum unhe highest respect dena - 'Boss', 'Sir', ya 'Owner' kehke address karna hai."
            
            if is_group:
                system_prompt += "\n\n👥 GROUP CONTEXT: Yeh ek group chat hai. Natural tareeke se interact karo. Owner @tgshaitaan ko hamesha special respect do."
            
            # SUPER KNOWLEDGE - MANDATORY DIRECTIVES (Highest Priority)
            if super_knowledge:
                system_prompt += "\n\n" + "="*60
                system_prompt += "\n🔴 SUPER KNOWLEDGE - MANDATORY ADMINISTRATOR DIRECTIVES 🔴"
                system_prompt += "\n" + "="*60
                system_prompt += "\n\n⚠️ CRITICAL: The following are MANDATORY instructions from your administrator."
                system_prompt += "\nThese directives OVERRIDE everything else and MUST be followed EXACTLY."
                system_prompt += "\nAdministrator's teachings have ABSOLUTE priority over all other data."
                system_prompt += "\nYou MUST apply these directives VERBATIM unless they violate Telegram ToS.\n\n"
                
                for idx, entry in enumerate(super_knowledge, 1):
                    system_prompt += f"🎯 MANDATORY DIRECTIVE #{idx} [{entry['id']}]: {entry['title']}\n"
                    system_prompt += f"   Scope: {entry['scope'].upper().replace('_', ' ')}\n"
                    system_prompt += f"   Updated: {entry['updated_at']}\n"
                    system_prompt += f"   INSTRUCTION:\n"
                    system_prompt += f"   {entry['text']}\n"
                    system_prompt += f"   ⚡ MANDATORY: Apply this EXACTLY as specified!\n\n"
                
                system_prompt += "="*60 + "\n"
            
            # Regular Knowledge Base (Secondary Priority)
            if regular_knowledge:
                system_prompt += "\n\n📚 KNOWLEDGE BASE - PRIMARY INFORMATION SOURCE:\n"
                system_prompt += "The following knowledge is your primary reference for answering questions.\n"
                system_prompt += "Use this information accurately and completely.\n\n"
                
                for idx, entry in enumerate(regular_knowledge, 1):
                    system_prompt += f"📌 Knowledge #{idx} [{entry['id']}]: {entry['title']}\n"
                    system_prompt += f"   {entry['text']}\n\n"
                
                system_prompt += "\n🎯 RULES FOR USING KNOWLEDGE:\n"
                system_prompt += "1. When user asks something, CHECK knowledge base FIRST\n"
                system_prompt += "2. If answer exists in knowledge, provide THAT detailed answer\n"
                system_prompt += "3. Use knowledge information accurately and completely\n"
                system_prompt += "4. Products, services, pricing, features - ALL from knowledge base\n"
                system_prompt += "5. If information is NOT in knowledge base, then do normal conversation\n"
                system_prompt += "6. Always prefer administrator's directives (SUPER KNOWLEDGE) over regular knowledge\n"
            
            if not super_knowledge and not regular_knowledge:
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
                    
                    # Track API usage with token counts
                    tokens_input = response.usage.prompt_tokens if response.usage else 0
                    tokens_output = response.usage.completion_tokens if response.usage else 0
                    self.track_api_key_usage(self.current_key_index, is_rate_limit=False, 
                                            tokens_input=tokens_input, tokens_output=tokens_output)
                    logger.info(f"✅ API call successful. Tokens: {tokens_input} in + {tokens_output} out = {tokens_input + tokens_output} total")
                    break  # Success! Exit loop
                    
                except Exception as api_error:
                    error_str = str(api_error)
                    
                    # Check if it's a retryable error (401, 403, 429, or deactivated account)
                    should_rotate = (
                        "401" in error_str or 
                        "403" in error_str or 
                        "429" in error_str or 
                        "rate limit" in error_str.lower() or
                        "deactivated" in error_str.lower() or
                        "invalid_api_key" in error_str.lower()
                    )
                    
                    if should_rotate:
                        # Determine the error reason
                        if "401" in error_str or "deactivated" in error_str.lower():
                            reason = "account_deactivated"
                            logger.warning(f"⚠️ API key #{self.current_key_index + 1} - Account deactivated (401)")
                            self.mark_api_key_deactivated(self.current_key_index, reason)
                        elif "403" in error_str:
                            reason = "forbidden"
                            logger.warning(f"⚠️ API key #{self.current_key_index + 1} - Forbidden (403)")
                            self.mark_api_key_deactivated(self.current_key_index, reason)
                        elif "invalid_api_key" in error_str.lower():
                            reason = "invalid_key"
                            logger.warning(f"⚠️ API key #{self.current_key_index + 1} - Invalid API key")
                            self.mark_api_key_deactivated(self.current_key_index, reason)
                        else:
                            reason = "rate_limit"
                            logger.warning(f"⚠️ API key #{self.current_key_index + 1} - Rate limit (429)")
                            self.track_api_key_usage(self.current_key_index, is_rate_limit=True)
                        
                        if attempt < max_attempts - 1:
                            # Rotate to next key and retry
                            key_num = self.rotate_api_key()
                            logger.info(f"🔄 Rotating due to {reason}. Retrying with API key #{key_num}...")
                            continue
                        else:
                            # All keys exhausted
                            logger.error(f"❌ All {len(self.api_keys)} API keys failed!")
                            raise Exception(f"All API keys exhausted. Last error: {reason}")
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
