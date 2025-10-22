#!/usr/bin/env python3
"""
🔐 Pyrogram Session Creator - नया Session बनाओ
"""

from pyrogram import Client
import os
import sys

def delete_old_sessions():
    """पुरानी session files delete करो"""
    session_files = [
        "my_personal_account.session",
        "my_personal_account.session-journal"
    ]
    
    deleted_count = 0
    for file in session_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"🗑️  Deleted old session: {file}")
            deleted_count += 1
    
    if deleted_count == 0:
        print("ℹ️  No old session files found")
    else:
        print(f"✅ Deleted {deleted_count} old session file(s)\n")

def create_new_session():
    """नया session create करो"""
    print("=" * 70)
    print("🔐 TELEGRAM PYROGRAM SESSION CREATOR")
    print("=" * 70)
    
    # पुराने sessions delete करो
    print("\n📁 Checking for old sessions...")
    delete_old_sessions()
    
    # API credentials लो
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    
    if not api_id or not api_hash:
        print("\n⚠️  Environment variables not set!")
        print("\nPlease enter your Telegram API credentials:")
        print("(Get from: https://my.telegram.org/apps)\n")
        
        api_id = input("Enter API ID: ").strip()
        api_hash = input("Enter API Hash: ").strip()
        
        if not api_id or not api_hash:
            print("\n❌ Error: API credentials required!")
            sys.exit(1)
    else:
        print(f"\n✅ Using API credentials from environment")
        print(f"   API ID: {api_id}")
        print(f"   API Hash: {api_hash[:10]}...")
    
    # Convert to int
    try:
        api_id = int(api_id)
    except:
        print("❌ Invalid API ID!")
        sys.exit(1)
    
    # Session name
    session_name = "my_personal_account"
    
    print(f"\n🔐 Creating new session: {session_name}.session")
    print("=" * 70)
    
    # Create Pyrogram client
    app = Client(
        session_name,
        api_id=api_id,
        api_hash=api_hash
    )
    
    try:
        print("\n⏳ Starting authentication process...")
        print("\n📝 Steps:")
        print("   1. Enter your phone number (with country code, e.g., +91...)")
        print("   2. Wait for OTP on Telegram")
        print("   3. Enter OTP code (5 minutes expire time)")
        print("   4. If 2FA enabled, enter your password")
        print("\n" + "=" * 70)
        
        # Start authentication
        app.start()
        
        # Get user info
        me = app.get_me()
        
        print("\n" + "=" * 70)
        print("✅ ✅ ✅ SUCCESS! SESSION CREATED! ✅ ✅ ✅")
        print("=" * 70)
        print(f"   Name: {me.first_name} {me.last_name or ''}")
        print(f"   Phone: +{me.phone_number}")
        print(f"   Username: @{me.username if me.username else 'None'}")
        print(f"   User ID: {me.id}")
        print("=" * 70)
        print(f"\n📁 Session file created: {session_name}.session")
        
        # Export session string as backup
        try:
            session_string = app.export_session_string()
            print(f"\n🔑 Session String Backup:")
            print("=" * 70)
            print(f"{session_string}")
            print("=" * 70)
            
            # Save to backup file
            backup_file = f"{session_name}_backup.txt"
            with open(backup_file, "w") as f:
                f.write(f"Telegram Session Backup\n")
                f.write(f"Name: {me.first_name} {me.last_name or ''}\n")
                f.write(f"Phone: +{me.phone_number}\n")
                f.write(f"Username: @{me.username if me.username else 'None'}\n\n")
                f.write(f"Session String:\n{session_string}\n")
            
            print(f"\n💾 Backup saved to: {backup_file}")
        except Exception as e:
            print(f"\n⚠️  Could not export session string: {e}")
        
        app.stop()
        
        print("\n" + "=" * 70)
        print("🎯 SESSION READY!")
        print("=" * 70)
        print("✅ Your Pyrogram bot can now use this session")
        print("✅ Session will stay logged in until manually logged out")
        print("\n💡 Tips to prevent auto-logout:")
        print("   1. Don't login same account on multiple devices")
        print("   2. Keep session file safe (don't delete)")
        print("   3. Don't reset 2FA password")
        print("   4. Use same API ID/Hash always")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\n💡 Common solutions:")
        print("   1. OTP expired? Run script again immediately")
        print("   2. Wrong phone? Check country code (+91 for India)")
        print("   3. 2FA enabled? Enter password when asked")
        print("   4. Session conflict? Delete old .session files")
        print("   5. Network issue? Check internet connection")
        sys.exit(1)

if __name__ == "__main__":
    create_new_session()
