#!/usr/bin/env python3
"""
Session String Based Authentication
Bypasses OTP entirely by using pre-authenticated session strings
"""

import os
import logging
import sqlite3
import asyncio
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SessionStringAuthenticator:
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
    
    async def authenticate_with_session_string(self, account_id: int, phone: str, api_id: int, api_hash: str, session_string: str):
        """
        Authenticate using a session string (bypasses OTP completely)
        
        Args:
            account_id: Database account ID
            phone: Phone number (for logging only)
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            session_string: Pre-authenticated session string
        
        Returns:
            (success: bool, message: str)
        """
        try:
            logger.info(f"🔐 Authenticating with session string for account #{account_id}")
            logger.info(f"   Phone: +{phone}")
            logger.info(f"   Session string length: {len(session_string)}")
            
            # Create in-memory client with session string
            app = Client(
                f"account_{account_id}",
                api_id=api_id,
                api_hash=api_hash,
                session_string=session_string,
                in_memory=True
            )
            
            # Test the session by connecting
            await app.start()
            
            # Get user info to verify
            me = await app.get_me()
            logger.info(f"✅ Session valid for: {me.first_name} (@{me.username if me.username else me.phone_number})")
            
            # Export fresh session string (in case it updated)
            fresh_session_string = await app.export_session_string()
            
            # Save to database
            self.update_account_session(account_id, fresh_session_string, 1, None)
            
            await app.stop()
            
            logger.info(f"✅ Successfully authenticated account #{account_id}")
            
            return True, f"✅ Authenticated as {me.first_name}! Account ready to use."
        
        except SessionPasswordNeeded:
            logger.error(f"❌ 2FA enabled - cannot use session string")
            return False, "2-Step Verification is enabled. Please disable it first."
        
        except Exception as e:
            logger.error(f"❌ Failed to authenticate with session string: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            error_msg = str(e)
            
            if "AUTH_KEY_UNREGISTERED" in error_msg or "SESSION_REVOKED" in error_msg:
                return False, "Session has been revoked. Please generate a fresh session string."
            elif "AUTH_KEY_DUPLICATED" in error_msg:
                return False, "Session is being used elsewhere. Each account needs a unique session."
            else:
                return False, f"Authentication failed: {error_msg}"

async def test_session_string():
    """Test function to validate a session string"""
    print("=" * 70)
    print("🔐 SESSION STRING TESTER")
    print("=" * 70)
    
    api_id = input("Enter API ID: ").strip()
    api_hash = input("Enter API Hash: ").strip()
    session_string = input("Enter Session String: ").strip()
    
    if not api_id or not api_hash or not session_string:
        print("❌ All fields are required!")
        return
    
    api_id = int(api_id)
    
    try:
        print("\n⏳ Testing session string...")
        
        app = Client(
            "test_session",
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True
        )
        
        await app.start()
        me = await app.get_me()
        
        print("\n" + "=" * 70)
        print("✅ SESSION STRING IS VALID!")
        print("=" * 70)
        print(f"Name: {me.first_name} {me.last_name or ''}")
        print(f"Phone: {me.phone_number}")
        print(f"Username: @{me.username if me.username else 'None'}")
        print(f"User ID: {me.id}")
        print("=" * 70)
        
        await app.stop()
        
    except Exception as e:
        print("\n" + "=" * 70)
        print("❌ SESSION STRING IS INVALID!")
        print("=" * 70)
        print(f"Error: {str(e)}")
        print("=" * 70)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(test_session_string())
    else:
        print("Session String Authenticator")
        print("This module is designed to be used by the Telegram bot")
        print("\nTo test a session string: python add_session_string_auth.py test")
