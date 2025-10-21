#!/usr/bin/env python3
"""
Multi-Account Pyrogram Manager
Runs multiple Pyrogram clients simultaneously for automated DM replies
Integrates with the admin panel database for account management
"""

import os
import logging
import sqlite3
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatAction
from openai import OpenAI

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class MultiAccountManager:
    def __init__(self):
        self.db_path = 'chat_history.db'
        
        # OpenAI Setup
        self.api_keys = []
        for i in range(1, 20):
            key = os.getenv(f'OPENAI_API_KEY_{i}')
            if key:
                self.api_keys.append(key)
        
        single_key = os.getenv('OPENAI_API_KEY')
        if single_key and single_key not in self.api_keys:
            self.api_keys.insert(0, single_key)
        
        if not self.api_keys:
            logger.warning("No OpenAI API key found - AI responses will be disabled")
            self.openai_client = None
        else:
            self.current_key_index = 0
            self.openai_client = OpenAI(api_key=self.api_keys[self.current_key_index], max_retries=0)
            logger.info(f"✅ Loaded {len(self.api_keys)} API keys for rotation")
        
        self.clients = {}
        self.running = False
    
    def get_active_accounts(self):
        """Get all authenticated and active accounts from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, phone_number, account_name, session_string, api_id, api_hash
            FROM pyrogram_accounts
            WHERE is_authenticated = 1 
            AND is_active = 1
            AND session_string IS NOT NULL
            AND api_id IS NOT NULL
            AND api_hash IS NOT NULL
            ORDER BY id
        ''')
        accounts = cursor.fetchall()
        conn.close()
        
        return accounts
    
    def get_all_authenticated_accounts(self):
        """Get all authenticated accounts regardless of active status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, phone_number, account_name, session_string, is_active, api_id, api_hash
            FROM pyrogram_accounts
            WHERE is_authenticated = 1
            AND session_string IS NOT NULL
            AND api_id IS NOT NULL
            AND api_hash IS NOT NULL
            ORDER BY id
        ''')
        accounts = cursor.fetchall()
        conn.close()
        
        return accounts
    
    def update_account_status(self, account_id: int, is_active: int, error_message: str = None):
        """Update account active status in database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE pyrogram_accounts
            SET is_active = ?, last_active = CURRENT_TIMESTAMP, error_message = ?
            WHERE id = ?
        ''', (is_active, error_message, account_id))
        
        conn.commit()
        conn.close()
    
    def increment_reply_count(self, account_id: int):
        """Increment reply count for an account"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE pyrogram_accounts
            SET reply_count = reply_count + 1, last_active = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (account_id,))
        
        conn.commit()
        conn.close()
    
    def get_bot_knowledge(self, bot_type='dm'):
        """Get bot knowledge from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT knowledge_text
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
        
        if not results:
            return None
        
        return '\n\n'.join([row[0] for row in results])
    
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
    
    def get_account_knowledge(self, account_id: int):
        """Get account-specific knowledge from database"""
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
    
    async def handle_dm_message(self, client: Client, message: Message, account_id: int, account_name: str):
        """Handle incoming DM message"""
        try:
            # Ignore own messages
            if message.from_user and message.from_user.is_self:
                return
            
            # Only respond to private messages
            if message.chat.type != "private":
                return
            
            # Ignore non-text messages
            if not message.text:
                return
            
            # Check for keyword matches first
            keyword_response = self.check_keyword_match(message.text)
            if keyword_response:
                await message.reply(keyword_response)
                self.increment_reply_count(account_id)
                logger.info(f"[{account_name}] Sent keyword response to {message.from_user.id}")
                return
            
            # Generate AI response if OpenAI is available
            if self.openai_client:
                await client.send_chat_action(message.chat.id, ChatAction.TYPING)
                
                # Get account-specific knowledge first, then global DM knowledge
                account_knowledge = self.get_account_knowledge(account_id)
                global_knowledge = self.get_bot_knowledge(bot_type='dm')
                
                system_prompt = "Tum ek highly intelligent aur helpful AI assistant ho. Tumhe Hindi aur English dono languages mein expert tarike se baat karni aani hai."
                
                # Priority: Account-specific knowledge > Global DM knowledge
                if account_knowledge:
                    system_prompt += f"\n\n🔥 ACCOUNT-SPECIFIC KNOWLEDGE (HIGHEST PRIORITY):\n{account_knowledge}\n\n"
                    system_prompt += "⚠️ IMPORTANT: Follow account-specific knowledge FIRST!"
                
                if global_knowledge:
                    system_prompt += f"\n\n📚 GLOBAL KNOWLEDGE:\n{global_knowledge}\n\n"
                    system_prompt += "Use this knowledge to answer questions accurately."
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message.text}
                ]
                
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        max_tokens=500
                    )
                    
                    ai_response = response.choices[0].message.content
                    await message.reply(ai_response)
                    self.increment_reply_count(account_id)
                    logger.info(f"[{account_name}] Sent AI response to {message.from_user.id}")
                    
                except Exception as e:
                    logger.error(f"[{account_name}] OpenAI error: {e}")
                    # Fallback message
                    await message.reply("Namaste! Main abhi busy hoon. Aap ka message dekha hai, jald hi reply karunga. 🙏")
                    self.increment_reply_count(account_id)
            else:
                # No AI available, send simple auto-reply
                await message.reply("Namaste! Main abhi busy hoon. Aap ka message dekha hai, jald hi reply karunga. 🙏")
                self.increment_reply_count(account_id)
                logger.info(f"[{account_name}] Sent auto-reply to {message.from_user.id}")
        
        except Exception as e:
            logger.error(f"[{account_name}] Error handling message: {e}")
    
    async def start_account(self, account_id: int, phone: str, account_name: str, session_string: str = None, api_id: int = None, api_hash: str = None):
        """Start a Pyrogram client for an account"""
        try:
            if not api_id or not api_hash:
                logger.error(f"❌ [{account_name}] Missing API credentials!")
                self.update_account_status(account_id, 0, "Missing API credentials")
                return False
            
            session_name = f"account_{account_id}_{phone}"
            
            client = Client(
                session_name,
                api_id=int(api_id),
                api_hash=api_hash,
                session_string=session_string
            )
            
            # Add message handler
            @client.on_message(filters.private & filters.incoming & ~filters.bot)
            async def message_handler(client_obj, message):
                await self.handle_dm_message(client_obj, message, account_id, account_name)
            
            await client.start()
            self.clients[account_id] = client
            self.update_account_status(account_id, 1, None)
            
            logger.info(f"✅ [{account_name}] Started successfully (+{phone})")
            return True
            
        except Exception as e:
            logger.error(f"❌ [{account_name}] Failed to start: {e}")
            self.update_account_status(account_id, 0, str(e))
            return False
    
    async def stop_account(self, account_id: int):
        """Stop a Pyrogram client"""
        if account_id in self.clients:
            try:
                await self.clients[account_id].stop()
                del self.clients[account_id]
                self.update_account_status(account_id, 0, None)
                logger.info(f"🛑 Account {account_id} stopped")
                return True
            except Exception as e:
                logger.error(f"Error stopping account {account_id}: {e}")
                return False
        return False
    
    async def run(self):
        """Main run loop - starts all authenticated accounts"""
        self.running = True
        
        logger.info("🚀 Multi-Account Manager starting...")
        
        # Get all authenticated accounts
        accounts = self.get_active_accounts()
        
        if not accounts:
            logger.warning("⚠️ No authenticated accounts found in database!")
            logger.info("Add and authenticate accounts via the admin panel first.")
            return
        
        logger.info(f"📱 Found {len(accounts)} authenticated account(s)")
        
        # Start all accounts
        tasks = []
        for account_id, phone, account_name, session_string, api_id, api_hash in accounts:
            logger.info(f"Starting {account_name} (+{phone})...")
            task = self.start_account(account_id, phone, account_name, session_string, api_id, api_hash)
            tasks.append(task)
        
        # Wait for all to start
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if r is True)
        logger.info(f"✅ {successful}/{len(accounts)} accounts started successfully")
        
        if successful == 0:
            logger.error("❌ No accounts started! Exiting...")
            return
        
        # Keep running
        logger.info("🟢 Multi-Account Manager is running. Press Ctrl+C to stop.")
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("⏹️ Stopping all accounts...")
            await self.stop_all()
    
    async def stop_all(self):
        """Stop all running clients"""
        self.running = False
        
        tasks = []
        for account_id in list(self.clients.keys()):
            tasks.append(self.stop_account(account_id))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("🛑 All accounts stopped")

if __name__ == '__main__':
    try:
        manager = MultiAccountManager()
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start manager: {e}")
        raise
