#!/usr/bin/env python3
import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramChatBot:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        if not self.telegram_token:
            raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.openai_client = OpenAI(api_key=self.openai_api_key)
        self.db_path = 'chat_history.db'
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
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
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
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
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
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_message = update.message.text
        
        logger.info(f"Received message from {user.id} ({user.username}): {user_message}")
        
        await update.message.chat.send_action("typing")
        
        try:
            recent_history = self.get_recent_history(user.id, limit=3)
            
            messages = [
                {
                    "role": "system",
                    "content": "Tum ek helpful aur friendly AI assistant ho. Tum Hindi aur English dono mein baat kar sakte ho. User ki madad karo aur unke sawaalon ka sahi jawab do."
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
