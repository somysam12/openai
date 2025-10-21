#!/usr/bin/env python3
"""
आसान Telegram Authentication
यह script OTP expire होने की problem को fix करता है
"""

from pyrogram import Client
import os
import sys

print("=" * 60)
print("🔐 Telegram Account Authentication (आसान तरीका)")
print("=" * 60)

# API credentials check करें
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

if not api_id or not api_hash:
    print("\n❌ Error: TELEGRAM_API_ID और TELEGRAM_API_HASH environment variables नहीं मिले!")
    print("\nKृपया पहले ये secrets set करें:")
    print("1. Replit Secrets में जाएं")
    print("2. TELEGRAM_API_ID और TELEGRAM_API_HASH add करें")
    sys.exit(1)

api_id = int(api_id)

print(f"\n✅ API credentials मिल गए")
print(f"   API ID: {api_id}")
print(f"   API Hash: {api_hash[:8]}...")

# Session name
session_name = "my_personal_account"

print(f"\n📱 अपना phone number enter करें (country code के साथ)")
print(f"   Example: +919876543210")

# Phone number input करें
phone = input("\nPhone number: ").strip()

if not phone.startswith('+'):
    print("\n❌ Error: Phone number '+' से शुरू होना चाहिए (जैसे +919876543210)")
    sys.exit(1)

print(f"\n⏳ Telegram से connect हो रहे हैं...")

# Pyrogram client बनाएं
app = Client(
    session_name,
    api_id=api_id,
    api_hash=api_hash,
    phone_number=phone
)

try:
    print(f"⏳ {phone} पर OTP भेजा जा रहा है...")
    
    # यह automatically:
    # 1. OTP request करेगा
    # 2. आपसे OTP मांगेगा  
    # 3. Telegram से verify करेगा
    # 4. Session file save करेगा
    
    app.start()
    
    # User info प्राप्त करें
    me = app.get_me()
    
    print("\n" + "=" * 60)
    print("✅ ✅ ✅ सफलतापूर्वक Authenticated! ✅ ✅ ✅")
    print("=" * 60)
    print(f"   नाम: {me.first_name} {me.last_name or ''}")
    print(f"   Phone: {me.phone_number}")
    print(f"   Username: @{me.username if me.username else 'None'}")
    print(f"   Session file: {session_name}.session")
    print("=" * 60)
    
    # Export session string (optional - database के लिए)
    session_string = app.export_session_string()
    print(f"\n📝 Session String (backup के लिए):")
    print(f"{session_string[:50]}...")
    
    app.stop()
    
    print("\n✅ अब आप अपना personal account bot चला सकते हैं!")
    print("   Run: python personal_account_autoreply.py")
    
except Exception as e:
    print(f"\n❌ Authentication Failed!")
    print(f"Error: {str(e)}")
    print("\nसामान्य समस्याएं:")
    print("1. ❌ PHONE_CODE_EXPIRED - OTP expire हो गया")
    print("   ✅ Fix: फिर से try करें और OTP जल्दी enter करें (5 मिनट के अंदर)")
    print("\n2. ❌ 2FA enabled")
    print("   ✅ Fix: Telegram settings में 2FA disable करें")
    print("\n3. ❌ Wrong phone number")
    print("   ✅ Fix: सही phone number enter करें (country code के साथ)")
    sys.exit(1)
