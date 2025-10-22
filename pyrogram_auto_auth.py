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
    
    def update_account_session(self, account_id: int, session_string: str | None = None, is_authenticated: int = 1, error_message: str | None = None):
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
        """
        DEPRECATED: Use two-step authentication instead
        Step 1: request_code_only() to send OTP
        Step 2: authenticate_account_with_hash() to verify OTP (within 5 minutes)
        
        This method sends a NEW code each time, which can cause expiration issues
        """
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
            logger.warning(f"⚠️ You have 5 minutes to enter the code!")
            
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
                logger.info(f"💡 Tip: Use two-step auth - request_code_only() then authenticate_account_with_hash()")
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
        """Request OTP code (first step) - Keeps connection alive to prevent hash expiration"""
        try:
            import os
            
            clean_phone = phone.replace('+', '').replace('-', '').replace(' ', '')
            session_name = f"temp_auth_{clean_phone}"
            
            if os.path.exists(f"{session_name}.session"):
                try:
                    os.remove(f"{session_name}.session")
                    logger.info(f"🗑️ Removed old temp session for {phone}")
                except:
                    pass
            
            app = Client(
                session_name,
                api_id=api_id,
                api_hash=api_hash,
                phone_number=f"+{clean_phone}"
            )
            
            await app.connect()
            
            sent_code = await app.send_code(f"+{clean_phone}")
            phone_code_hash = sent_code.phone_code_hash
            
            logger.info(f"✅ OTP sent to +{clean_phone}")
            logger.info(f"📝 Phone code hash saved: {phone_code_hash[:20]}...")
            logger.info(f"⏰ Code valid for 5 minutes - DO NOT disconnect!")
            logger.info(f"🔒 Session kept alive at: {session_name}.session")
            
            await app.disconnect()
            
            return True, phone_code_hash
        
        except Exception as e:
            logger.error(f"❌ Failed to send OTP: {e}")
            return False, str(e)
    
    async def authenticate_account_with_hash(self, account_id: int, phone: str, api_id: int, api_hash: str, code: str, phone_code_hash: str):
        """Authenticate using existing session - MUST reuse same session to avoid code expiration"""
        import os
        import time
        
        try:
            clean_phone = phone.replace('+', '').replace('-', '').replace(' ', '')
            session_name = f"temp_auth_{clean_phone}"
            
            session_exists = os.path.exists(f"{session_name}.session")
            logger.info(f"🔍 Looking for session: {session_name}.session - Exists: {session_exists}")
            
            if not session_exists:
                logger.error(f"❌ Session file not found! OTP might be expired.")
                logger.error(f"   Expected: {session_name}.session")
                logger.error(f"   This usually means too much time passed or session was deleted.")
                return False, "Session expired. Please request OTP again (Click 'Resend OTP')."
            
            logger.info(f"✅ Found existing session - reusing connection")
            
            app = Client(
                session_name,
                api_id=api_id,
                api_hash=api_hash,
                phone_number=f"+{clean_phone}"
            )
            
            await app.connect()
            
            logger.info(f"🔐 Attempting sign-in for +{clean_phone}")
            logger.info(f"   Code: {code}")
            logger.info(f"   Hash: {phone_code_hash[:20]}...")
            
            try:
                signed_in = await app.sign_in(f"+{clean_phone}", phone_code_hash, code)
                logger.info(f"✅ Successfully authenticated +{clean_phone}")
                
                session_string = await app.export_session_string()
                logger.info(f"📝 Exported session string (length: {len(session_string)})")
                
                self.update_account_session(account_id, session_string, 1, None)
                logger.info(f"💾 Saved to database for account #{account_id}")
                
                await app.disconnect()
                
                try:
                    if os.path.exists(f"{session_name}.session"):
                        os.remove(f"{session_name}.session")
                        logger.info(f"🗑️ Cleaned up temp session")
                except Exception as cleanup_err:
                    logger.warning(f"⚠️ Cleanup warning: {cleanup_err}")
                
                return True, "✅ Successfully authenticated! Account is ready to use."
                
            except SessionPasswordNeeded:
                logger.error(f"❌ 2FA is enabled for +{clean_phone}")
                await app.disconnect()
                return False, "2-Step Verification is enabled. Please disable it temporarily in Telegram Settings → Privacy & Security, then try again."
                
            except PhoneCodeExpired as e:
                logger.error(f"❌ Code expired: {e}")
                await app.disconnect()
                try:
                    if os.path.exists(f"{session_name}.session"):
                        os.remove(f"{session_name}.session")
                except:
                    pass
                return False, f"OTP expired. Click 'Resend OTP' to get a fresh code."
                
            except PhoneCodeInvalid as e:
                logger.error(f"❌ Invalid code: {e}")
                await app.disconnect()
                return False, f"Wrong OTP code. Please check and try again, or click 'Resend OTP'."
        
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.update_account_session(account_id, None, 0, str(e))
            return False, f"Error: {str(e)}"

if __name__ == '__main__':
    print("Pyrogram Auto Authenticator")
    print("This module is designed to be used by the Telegram bot")
