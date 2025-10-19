#!/usr/bin/env python3
import os
import logging
import sqlite3
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def is_admin(self, user_id: int) -> bool:
        return user_id == self.admin_id
    
    def get_admin_keyboard(self):
        keyboard = [
            [
                InlineKeyboardButton("📚 View Knowledge", callback_data="admin_view_knowledge"),
                InlineKeyboardButton("✏️ Set Knowledge", callback_data="admin_set_knowledge")
            ],
            [
                InlineKeyboardButton("👥 View Users", callback_data="admin_view_users"),
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT knowledge_text FROM bot_knowledge ORDER BY updated_at DESC LIMIT 1')
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def set_bot_knowledge(self, knowledge: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM bot_knowledge')
        cursor.execute('INSERT INTO bot_knowledge (knowledge_text) VALUES (?)', (knowledge,))
        
        conn.commit()
        conn.close()
    
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
            knowledge = self.get_bot_knowledge()
            if knowledge:
                await query.edit_message_text(
                    f"📚 *Current Bot Knowledge:*\n\n{knowledge}\n\n"
                    f"To update, click 'Set Knowledge' button.",
                    reply_markup=self.get_admin_keyboard()
                )
            else:
                await query.edit_message_text(
                    "⚠️ *No knowledge set yet!*\n\n"
                    "Click 'Set Knowledge' to add information.",
                    reply_markup=self.get_admin_keyboard()
                )
        
        elif data == "admin_set_knowledge":
            self.admin_state[user_id] = "waiting_knowledge"
            await query.edit_message_text(
                "✏️ *Set Bot Knowledge*\n\n"
                "Please send the knowledge/information you want the bot to use.\n\n"
                "*Example:*\n"
                "Main Mars Loader sell karta hoon.\n"
                "Products:\n"
                "- Month Key: ₹500\n"
                "- Week Key: ₹200\n"
                "- Day Key: ₹50\n\n"
                "Support: @YourUsername\n\n"
                "Send /cancel to cancel.",
                parse_mode='Markdown'
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
                    f"✅ *Knowledge Updated!*\n\n"
                    f"New knowledge:\n{user_message}\n\n"
                    f"Bot will now use this information!",
                    reply_markup=self.get_admin_keyboard(),
                    parse_mode='Markdown'
                )
                logger.info(f"Admin {user.id} updated bot knowledge")
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
        
        await update.message.chat.send_action("typing")
        
        try:
            recent_history = self.get_recent_history(user.id, limit=3)
            custom_knowledge = self.get_bot_knowledge()
            
            system_prompt = "Tum ek helpful aur friendly AI assistant ho. Tum Hindi aur English dono mein baat kar sakte ho."
            
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
            logger.info(f"Sent response to {user.id}")
            
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
        bot = TelegramChatBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise
