#!/usr/bin/env python3
"""
🔐 Replit Shell mein Session File Banao
Yeh script Replit Shell mein run karo - OTP instant enter kar sakte ho!
"""

from pyrogram import Client
import os
import sys

print("=" * 70)
print("🔐 TELEGRAM SESSION CREATOR (Replit Shell mein)")
print("=" * 70)

# Check if we're in Replit
if os.getenv('REPL_ID'):
    print("✅ Replit environment detected!")
else:
    print("⚠️  This works on any system, not just Replit")

print("\n📝 Instructions:")
print("1. Enter your API credentials")
print("2. Enter phone number when asked")
print("3. Enter OTP instantly when it arrives")
print("4. Session file will be created!")
print("=" * 70)

# Get API credentials from environment or user input
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

if not api_id or not api_hash:
    print("\n⚠️  Environment variables not set. Please enter manually:")
    api_id = input("Enter API ID (24586002): ").strip() or "24586002"
    api_hash = input("Enter API Hash (dd899a75e335...): ").strip() or "dd899a75e335d7f630e0dc8b4d11b7c7"
else:
    print(f"\n✅ Using API credentials from environment variables")
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

print(f"\n🔐 Creating session: {session_name}.session")
print("=" * 70)

# Create client
app = Client(
    session_name,
    api_id=api_id,
    api_hash=api_hash
)

try:
    print("\n⏳ Starting authentication...")
    print("📱 Telegram will ask for your phone number")
    print("📨 Then you'll receive OTP - enter it immediately!")
    print("\n" + "=" * 70)
    
    # This will:
    # 1. Ask for phone number
    # 2. Send OTP
    # 3. Ask for OTP code
    # 4. Create session file
    app.start()
    
    # Get user info
    me = app.get_me()
    
    print("\n" + "=" * 70)
    print("✅ ✅ ✅ SUCCESS! ✅ ✅ ✅")
    print("=" * 70)
    print(f"   Name: {me.first_name} {me.last_name or ''}")
    print(f"   Phone: {me.phone_number}")
    print(f"   Username: @{me.username if me.username else 'None'}")
    print(f"   User ID: {me.id}")
    print("=" * 70)
    print(f"\n📁 Session file created: {session_name}.session")
    
    # Export session string as backup
    session_string = app.export_session_string()
    print(f"\n🔑 Session String (Backup - copy this somewhere safe!):")
    print("=" * 70)
    print(f"{session_string}")
    print("=" * 70)
    
    # Save session string to file as backup
    with open(f"{session_name}_backup.txt", "w") as f:
        f.write(f"Session String Backup\n")
        f.write(f"Created: {app.get_me().first_name}\n")
        f.write(f"Phone: {app.get_me().phone_number}\n\n")
        f.write(f"Session String:\n{session_string}\n")
    
    print(f"\n💾 Session string also saved to: {session_name}_backup.txt")
    
    app.stop()
    
    print("\n" + "=" * 70)
    print("🎯 NEXT STEPS:")
    print("=" * 70)
    print("1. ✅ Session file created successfully!")
    print("2. Commit to git:")
    print(f"   git add {session_name}.session")
    print(f"   git commit -m 'Add authenticated session'")
    print(f"   git push")
    print("\n3. Bot will automatically use this session!")
    print("4. Both bot and userbot will work! 🚀")
    print("=" * 70)
    
except KeyboardInterrupt:
    print("\n\n❌ Cancelled by user")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    print("\n💡 Common issues:")
    print("1. OTP expired? Run the script again")
    print("2. 2FA enabled? Disable it temporarily in Telegram settings")
    print("3. Wrong phone number? Check and try again")
    sys.exit(1)
