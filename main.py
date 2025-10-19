#!/usr/bin/env python3
import os
import logging
import sqlite3
import re
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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
                "🔐 *Admin Panel - Namaste {}\\!*\n\n"
                "You have admin access\\. Admin commands:\n\n"
                "*Bot Management:*\n"
                "/setknowledge \\- Set bot knowledge/logic\n"
                "/viewknowledge \\- View current knowledge\n\n"
                "*User Management:*\n"
                "/users \\- View all users list\n"
                "/message @username \\- Start chat with user\n"
                "/endsession \\- End current chat session\n"
                "/broadcast \\- Send message to all users\n\n"
                "*Regular Commands:*\n"
                "/start \\- Bot ko shuru karein\n"
                "/help \\- Madad prapt karein\n"
                "/clear \\- Chat history clear karein"
            ).format(escape_markdown(user.first_name))
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
        
        await update.message.reply_text(welcome_message, parse_mode='MarkdownV2' if self.is_admin(user.id) else None)
        logger.info(f"User {user.id} ({user.username}) started the bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        if self.is_admin(user.id):
            help_text = (
                "🔐 *Admin Help*\n\n"
                "*Bot Knowledge Management:*\n"
                "/setknowledge \\- Apni products aur services ki details add karein\n"
                "/viewknowledge \\- Current knowledge dekhein\n\n"
                "*User Management:*\n"
                "/users \\- Sabhi users ki list dekhein\n"
                "/message @username \\- Kisi user se baat karein\n"
                "/endsession \\- Chat session khatam karein\n"
                "/broadcast \\- Sabhi users ko message bhejein\n\n"
                "Bot jo knowledge aap denge, wahi users ko batayega\\! 💡"
            )
            await update.message.reply_text(help_text, parse_mode='MarkdownV2')
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
    
    async def setknowledge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Yeh command sirf admin ke liye hai!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📝 Knowledge/Logic kaise set karein:\n\n"
                "Command: /setknowledge <your knowledge>\n\n"
                "Example:\n"
                "/setknowledge Main Mars Loader sell karta hoon. Hamare products:\n"
                "1. Month Key - ₹500\n"
                "2. Week Key - ₹200\n"
                "3. Day Key - ₹50\n\n"
                "Support: @YourUsername\n\n"
                "Yeh knowledge bot sabhi users ko batayega! 🚀"
            )
            return
        
        knowledge = ' '.join(context.args)
        self.set_bot_knowledge(knowledge)
        
        await update.message.reply_text(
            f"✅ Bot knowledge successfully update ho gayi hai!\n\n"
            f"Current Knowledge:\n{knowledge}\n\n"
            "Ab bot yahi information users ko dega! 🎯"
        )
        logger.info(f"Admin {update.effective_user.id} updated bot knowledge")
    
    async def viewknowledge_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Yeh command sirf admin ke liye hai!")
            return
        
        knowledge = self.get_bot_knowledge()
        
        if knowledge:
            await update.message.reply_text(
                f"📚 Current Bot Knowledge:\n\n{knowledge}"
            )
        else:
            await update.message.reply_text(
                "⚠️ Abhi tak koi knowledge set nahi hui hai!\n\n"
                "Use /setknowledge to add knowledge."
            )
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Yeh command sirf admin ke liye hai!")
            return
        
        users = self.get_all_users()
        
        if not users:
            await update.message.reply_text("📭 Abhi tak koi user nahi hai!")
            return
        
        user_list = "👥 All Users:\n\n"
        
        for idx, (user_id, username, first_name, last_name, first_seen, last_active, msg_count) in enumerate(users, 1):
            full_name = f"{first_name or ''} {last_name or ''}".strip()
            username_display = f"@{username}" if username else "No username"
            user_list += (
                f"{idx}. {full_name or 'Unknown'}\n"
                f"   - {username_display}\n"
                f"   - ID: {user_id}\n"
                f"   - Messages: {msg_count}\n"
                f"   - Last Active: {last_active[:16]}\n\n"
            )
        
        user_list += f"Total Users: {len(users)}"
        
        await update.message.reply_text(user_list)
    
    async def message_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Yeh command sirf admin ke liye hai!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📨 Kisi user se chat kaise karein:\n\n"
                "Command: /message @username\n\n"
                "Example:\n"
                "/message @John\n\n"
                "Fir aap jo bhi message bhejenge, wo us user ko jayega!\n"
                "Chat khatam karne ke liye: /endsession"
            )
            return
        
        target_username = context.args[0].replace('@', '')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, first_name FROM all_users WHERE username = ?', (target_username,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await update.message.reply_text(f"❌ User @{target_username} not found!")
            return
        
        target_user_id, first_name = result
        self.active_admin_chats[self.admin_id] = target_user_id
        self.user_to_admin_chat[target_user_id] = self.admin_id
        
        await update.message.reply_text(
            f"✅ Chat session active with {first_name} (@{target_username})\n\n"
            f"Ab aap jo bhi message bhejenge, {first_name} ko jayega.\n"
            f"Unke replies bhi aapko milenge.\n"
            f"Session end karne ke liye: /endsession"
        )
    
    async def endsession_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Yeh command sirf admin ke liye hai!")
            return
        
        if self.admin_id in self.active_admin_chats:
            target_user = self.active_admin_chats[self.admin_id]
            del self.active_admin_chats[self.admin_id]
            if target_user in self.user_to_admin_chat:
                del self.user_to_admin_chat[target_user]
            await update.message.reply_text("✅ Chat session khatam ho gayi hai!")
        else:
            await update.message.reply_text("⚠️ Koi active session nahi hai!")
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Yeh command sirf admin ke liye hai!")
            return
        
        if not context.args:
            await update.message.reply_text(
                "📢 Broadcast Message kaise bhejein:\n\n"
                "Command: /broadcast <your message>\n\n"
                "Example:\n"
                "/broadcast New offer! 50% discount today only!\n\n"
                "Yeh message sabhi users ko jayega! 🚀"
            )
            return
        
        message = ' '.join(context.args)
        users = self.get_all_users()
        
        sent_count = 0
        failed_count = 0
        
        for user_id, _, _, _, _, _, _ in users:
            if user_id == self.admin_id:
                continue
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📢 Broadcast Message:\n\n{message}"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user_id}: {e}")
                failed_count += 1
        
        await update.message.reply_text(
            f"✅ Broadcast complete!\n\n"
            f"Sent: {sent_count}\n"
            f"Failed: {failed_count}"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_message = update.message.text
        
        self.track_user(user.id, user.username, user.first_name, user.last_name)
        logger.info(f"Received message from {user.id} ({user.username}): {user_message}")
        
        if user.id in self.user_to_admin_chat:
            admin_id = self.user_to_admin_chat[user.id]
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"💬 Message from {user.first_name} (@{user.username or 'no_username'}):\n\n{user_message}"
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
                    text=f"💬 Message from Support:\n\n{user_message}"
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
        application.add_handler(CommandHandler("setknowledge", self.setknowledge_command))
        application.add_handler(CommandHandler("viewknowledge", self.viewknowledge_command))
        application.add_handler(CommandHandler("users", self.users_command))
        application.add_handler(CommandHandler("message", self.message_command))
        application.add_handler(CommandHandler("endsession", self.endsession_command))
        application.add_handler(CommandHandler("broadcast", self.broadcast_command))
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
