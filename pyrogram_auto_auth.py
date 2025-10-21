#!/usr/bin/env python3
"""
Automated Pyrogram Account Authentication
Handles OTP collection and session creation via Telegram bot
"""

import os
import logging
import asyncio
import sqlite3
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PyrogramAuthenticator:
    def __init__(self, db_path='chat_history.db'):
        self.db_path = db_path
    
    def update_account_session(self, account_id: int, session_string: str, is_authenticated: int = 1, error_message: str = None):
        """Update account with session string and auth status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE pyrogram_accounts
            SET session_string = ?, is_authenticated = ?, error_message = ?, last_active = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (session_string, is_authenticated, error_message, account_id))
        
        conn.commit()
        conn.close()
    
    async def authenticate_account(self, account_id: int, phone: str, api_id: int, api_hash: str, code: str):
        """Authenticate a Pyrogram account using provided OTP"""
        try:
            session_name = f"account_{account_id}_{phone}"
            
            app = Client(
                session_name,
                api_id=api_id,
                api_hash=api_hash,
                phone_number=f"+{phone}",
                in_memory=True
            )
            
            await app.connect()
            
            # Send code
            sent_code = await app.send_code(f"+{phone}")
            logger.info(f"✅ OTP code sent to +{phone}")
            
            # Sign in with provided code
            try:
                signed_in = await app.sign_in(f"+{phone}", sent_code.phone_code_hash, code)
                logger.info(f"✅ Successfully authenticated +{phone}")
            except SessionPasswordNeeded:
                logger.error(f"❌ 2FA enabled for +{phone}. Please disable 2FA first!")
                await app.disconnect()
                return False, "2FA enabled. Please disable 2FA and try again."
            except (PhoneCodeInvalid, PhoneCodeExpired) as e:
                logger.error(f"❌ Invalid or expired code for +{phone}: {e}")
                await app.disconnect()
                return False, f"Invalid or expired OTP code: {str(e)}"
            
            # Export session string
            session_string = await app.export_session_string()
            
            # Save to database
            self.update_account_session(account_id, session_string, 1, None)
            
            await app.disconnect()
            logger.info(f"✅ Session saved for account #{account_id}")
            
            return True, "Successfully authenticated and session saved!"
        
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            self.update_account_session(account_id, None, 0, str(e))
            return False, f"Authentication failed: {str(e)}"
    
    async def request_code_only(self, phone: str, api_id: int, api_hash: str):
        """Request OTP code (first step)"""
        try:
            session_name = f"temp_{phone}"
            
            app = Client(
                session_name,
                api_id=api_id,
                api_hash=api_hash,
                phone_number=f"+{phone}",
                in_memory=True
            )
            
            await app.connect()
            sent_code = await app.send_code(f"+{phone}")
            await app.disconnect()
            
            logger.info(f"✅ OTP sent to +{phone}")
            return True, sent_code.phone_code_hash
        
        except Exception as e:
            logger.error(f"❌ Failed to send OTP: {e}")
            return False, str(e)
    
    async def authenticate_account_with_hash(self, account_id: int, phone: str, api_id: int, api_hash: str, code: str, phone_code_hash: str):
        """Authenticate a Pyrogram account using provided OTP and phone_code_hash"""
        try:
            session_name = f"account_{account_id}_{phone}"
            
            app = Client(
                session_name,
                api_id=api_id,
                api_hash=api_hash,
                phone_number=f"+{phone}",
                in_memory=True
            )
            
            await app.connect()
            
            # Sign in with provided code and phone_code_hash
            try:
                signed_in = await app.sign_in(f"+{phone}", phone_code_hash, code)
                logger.info(f"✅ Successfully authenticated +{phone}")
            except SessionPasswordNeeded:
                logger.error(f"❌ 2FA enabled for +{phone}. Please disable 2FA first!")
                await app.disconnect()
                return False, "2FA enabled. Please disable 2FA and try again."
            except (PhoneCodeInvalid, PhoneCodeExpired) as e:
                logger.error(f"❌ Invalid or expired code for +{phone}: {e}")
                await app.disconnect()
                return False, f"Invalid or expired OTP code: {str(e)}"
            
            # Export session string
            session_string = await app.export_session_string()
            
            # Save to database
            self.update_account_session(account_id, session_string, 1, None)
            
            await app.disconnect()
            logger.info(f"✅ Session saved for account #{account_id}")
            
            return True, "Successfully authenticated and session saved!"
        
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            self.update_account_session(account_id, None, 0, str(e))
            return False, f"Authentication failed: {str(e)}"

if __name__ == '__main__':
    print("Pyrogram Auto Authenticator")
    print("This module is designed to be used by the Telegram bot")
