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
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.admin_id = int(os.getenv('ADMIN_ID', '0'))
        
        if not self.telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        if self.admin_id == 0:
            logger.warning("ADMIN_ID not set! Admin features will not work.")
        
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        self.db_path = 'chat_history.db'
        self.active_admin_chats = {}
        self.user_to_admin_chat = {}
        self.admin_state = {}
        self.init_database()
    
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def is_admin(self, user_id: int) -> bool:
        return user_id == self.admin_id
    
    def get_admin_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("📚 View Knowledge", callback_data="admin_view_knowledge"),
                InlineKeyboardButton("✏️ Add Knowledge", callback_data="admin_set_knowledge")
            ],
            [
                InlineKeyboardButton("🗑️ Delete Knowledge", callback_data="admin_delete_knowledge"),
                InlineKeyboardButton("👥 View Users", callback_data="admin_view_users")
            ],
            [
                InlineKeyboardButton("🔑 View Keywords", callback_data="admin_view_keywords"),
                InlineKeyboardButton("➕ Add Keyword", callback_data="admin_add_keyword")
            ],
            [
                InlineKeyboardButton("➖ Remove Keyword", callback_data="admin_remove_keyword"),
                InlineKeyboardButton("💬 Message User", callback_data="admin_message_user")
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
                InlineKeyboardButton("🔚 End Session", callback_data="admin_end_session")
            ],
            [
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
    
    def save_chat_history(self, user_id: int, username: str, message: str, response: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chat_history (user_id, username, message, response)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, message, response))
        
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
    
    def get_group_keywords(self):
        """Get all group keywords with responses"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT keyword, response FROM group_keywords')
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def add_group_keyword(self, keyword: str, response: str = None):
        """Add a new group keyword with optional custom response"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO group_keywords (keyword, response) VALUES (?, ?)', (keyword, response))
        conn.commit()
        conn.close()
    
    def remove_group_keyword(self, keyword: str):
        """Remove a group keyword"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM group_keywords WHERE LOWER(keyword) = LOWER(?)', (keyword,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted > 0
    
    def check_keyword_match(self, message_text: str) -> tuple:
        """Check if message contains a keyword and return the keyword and its response"""
        message_lower = message_text.lower()
        keywords = self.get_group_keywords()
        
        for keyword, response in keywords:
            if keyword.lower() in message_lower:
                return (keyword, response)
        
        return (None, None)
    
    def should_respond_in_group(self, message_text: str, bot_username: str, is_reply_to_bot: bool = False) -> bool:
        """Check if bot should respond to a group message"""
        if is_reply_to_bot:
            return True
            
        message_lower = message_text.lower()
        
        if f"@{bot_username.lower()}" in message_lower:
            return True
        
        keyword, _ = self.check_keyword_match(message_text)
        return keyword is not None
    
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
            if user_id in self.active_admin_chats:
                target_user = self.active_admin_chats[user_id]
                del self.active_admin_chats[user_id]
                if target_user in self.user_to_admin_chat:
                    del self.user_to_admin_chat[target_user]
                if user_id in self.admin_state:
                    del self.admin_state[user_id]
                
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
        
        elif data == "admin_view_keywords":
            keywords = self.get_group_keywords()
            if keywords:
                keyword_text = "🔑 *Group Keywords:*\n\n"
                for idx, (kw, resp) in enumerate(keywords, 1):
                    escaped_kw = escape_markdown(kw)
                    keyword_text += f"{idx}\\. {escaped_kw}\n"
                    if resp:
                        escaped_resp = escape_markdown(resp[:50] + "..." if len(resp) > 50 else resp)
                        keyword_text += f"   Response: {escaped_resp}\n"
                    else:
                        keyword_text += f"   Response: AI generated\n"
                keyword_text += f"\n*Total: {len(keywords)} keywords*\n\n"
                keyword_text += "Bot will respond in groups when these keywords appear\\."
                await query.edit_message_text(
                    keyword_text,
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='MarkdownV2'
                )
            else:
                await query.edit_message_text(
                    "⚠️ *No keywords set\\!*\n\n"
                    "Bot will only respond in groups when tagged\\.\n"
                    "Click 'Add Keyword' to add trigger words\\.",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='MarkdownV2'
                )
        
        elif data == "admin_add_keyword":
            self.admin_state[user_id] = "waiting_add_keyword"
            await query.edit_message_text(
                "➕ *Add Group Keyword*\n\n"
                "Send in this format:\n"
                "`keyword | custom response`\n\n"
                "*Example 1:* `help | Bot help: Contact @tgshaitaan for support!`\n"
                "*Example 2:* `price` (AI will generate response)\n\n"
                "📌 *Note:* \n"
                "- Keywords are case-insensitive\n"
                "- Use `|` to separate keyword and response\n"
                "- Without `|`, AI will generate response\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
            )
        
        elif data == "admin_remove_keyword":
            keywords = self.get_group_keywords()
            if not keywords:
                await query.edit_message_text(
                    "⚠️ *No keywords to remove\\!*\n\n"
                    "Add some keywords first\\.",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='MarkdownV2'
                )
                return
            
            keyword_text = "➖ *Remove Keyword*\n\n"
            keyword_text += "Current keywords:\n\n"
            for idx, (kw, _) in enumerate(keywords, 1):
                escaped_kw = escape_markdown(kw)
                keyword_text += f"{idx}\\. {escaped_kw}\n"
            keyword_text += f"\n*Total: {len(keywords)} keywords*\n\n"
            keyword_text += "Send the number \\(1, 2, 3\\.\\.\\.\\) of the keyword you want to remove\\.\n"
            keyword_text += "Send /cancel to cancel\\."
            
            self.admin_state[user_id] = "waiting_remove_keyword"
            await query.edit_message_text(
                keyword_text,
                parse_mode='MarkdownV2'
            )
        
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
            
            elif state == "waiting_add_keyword":
                if '|' in user_message:
                    parts = user_message.split('|', 1)
                    keyword = parts[0].strip()
                    response = parts[1].strip()
                else:
                    keyword = user_message.strip()
                    response = None
                
                self.add_group_keyword(keyword, response)
                del self.admin_state[user.id]
                
                response_info = f"Custom: {response[:50]}..." if response and len(response) > 50 else (response if response else "AI generated")
                
                await update.message.reply_text(
                    f"✅ *Keyword Added!*\n\n"
                    f"Keyword: {keyword}\n"
                    f"Response: {response_info}\n\n"
                    f"Bot will now respond in groups when this word appears!",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {user.id} added keyword: {keyword} with response: {response}")
                return
            
            elif state == "waiting_remove_keyword":
                try:
                    keyword_num = int(user_message.strip())
                    keywords = self.get_group_keywords()
                    
                    if keyword_num < 1 or keyword_num > len(keywords):
                        await update.message.reply_text(
                            f"❌ Invalid number! Please send a number between 1 and {len(keywords)}.",
                            reply_markup=self.get_admin_keyboard()
                        )
                        return
                    
                    keyword_to_remove, _ = keywords[keyword_num - 1]
                    
                    if self.remove_group_keyword(keyword_to_remove):
                        del self.admin_state[user.id]
                        await update.message.reply_text(
                            f"✅ *Keyword Removed!*\n\n"
                            f"Removed: {keyword_to_remove}\n\n"
                            f"Remaining: {len(keywords) - 1} keywords",
                            reply_markup=self.get_admin_keyboard(),
                            parse_mode='Markdown'
                        )
                        logger.info(f"Admin {user.id} removed keyword: {keyword_to_remove}")
                    else:
                        await update.message.reply_text(
                            "❌ Failed to remove keyword!",
                            reply_markup=self.get_admin_keyboard()
                        )
                    return
                    
                except ValueError:
                    await update.message.reply_text(
                        "❌ Please send a valid number!",
                        reply_markup=self.get_admin_keyboard()
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
        
        is_reply_to_bot = False
        custom_response = None
        
        if is_group:
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username
            
            if update.message.reply_to_message:
                replied_user = update.message.reply_to_message.from_user
                if replied_user and replied_user.username == bot_username:
                    is_reply_to_bot = True
                    logger.info(f"Group message is reply to bot from {user.id}")
            
            keyword, response = self.check_keyword_match(user_message)
            if response:
                custom_response = response
                logger.info(f"Keyword matched: {keyword}, using custom response")
            
            if not self.should_respond_in_group(user_message, bot_username, is_reply_to_bot):
                logger.info(f"Ignoring group message (no keyword/tag/reply): {user_message[:50]}")
                return
        
        await update.message.chat.send_action("typing")
        
        try:
            if custom_response:
                final_response = custom_response
                self.save_chat_history(user.id, user.username or "Unknown", user_message, final_response)
                await update.message.reply_text(final_response)
                logger.info(f"Sent custom response to {user.id}")
            else:
                recent_history = self.get_recent_history(user.id, limit=3)
                custom_knowledge = self.get_bot_knowledge()
                
                username_db, first_name_db, last_name_db = self.get_user_info(user.id)
                user_first_name = user.first_name or first_name_db or "Dost"
                user_username = user.username or username_db
                
                system_prompt = "Tum ek helpful aur friendly AI assistant ho. Tum Hindi aur English dono mein baat kar sakte ho."
                
                system_prompt += f"\n\nUser ka naam: {user_first_name}"
                if user_username:
                    system_prompt += f" (@{user_username})"
                system_prompt += "\nJab zarurat ho, tum user ka naam use kar sakte ho apne response mein natural tareeke se."
                
                system_prompt += f"\n\nIMPORTANT: Tumhare owner ka naam @tgshaitaan hai. Jab bhi owner ka zikr ho ya unka message ho, tum unhe full respect dena. Unhe 'Boss', 'Sir', ya 'Owner' kehke address karna."
                
                if is_group:
                    system_prompt += "\n\nYeh ek group chat hai. Natural tareeke se sabke saath baat karo. Agar @tgshaitaan (owner) baat kar rahe hain, unhe special respect do."
                
                if custom_knowledge:
                    system_prompt += f"\n\nIMPORTANT - Tumhe yeh information diya gaya hai:\n{custom_knowledge}\n\nJab bhi user tumse kuch pooche, tum yahi information use karna aur unhe products ya services ke baare mein batana."
                
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
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=500,
                    temperature=0.7
                )
                
                ai_response = response.choices[0].message.content
                
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
        
        application = Application.builder().token(self.telegram_token).build()
        
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("clear", self.clear_command))
        application.add_handler(CallbackQueryHandler(self.button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        application.add_error_handler(self.error_handler)
        
        logger.info("Bot is ready and polling for messages...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

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
