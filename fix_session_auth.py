#!/usr/bin/env python3
"""
🔧 Session Authentication Fixer
यह script OTP expire problem को fix करता है
Session string से authenticate करने के लिए
"""

from pyrogram import Client
import os
import sys

print("=" * 70)
print("🔐 Telegram Session Authentication Fix")
print("=" * 70)

api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

if not api_id or not api_hash:
    print("\n❌ TELEGRAM_API_ID और TELEGRAM_API_HASH नहीं मिले!")
    print("\nकृपया Replit Secrets में ये add करें:")
    print("1. TELEGRAM_API_ID - https://my.telegram.org/apps से प्राप्त करें")
    print("2. TELEGRAM_API_HASH - https://my.telegram.org/apps से प्राप्त करें")
    sys.exit(1)

api_id = int(api_id)

print("\n✅ API credentials found")
print(f"   API ID: {api_id}")
print(f"   API Hash: {api_hash[:8]}...")

print("\n" + "=" * 70)
print("📱 2 तरीके authentication के लिए:")
print("=" * 70)
print("\nविकल्प 1: Session String से (बेहतर तरीका - OTP expire नहीं होगा)")
print("   - अगर आपके पास पहले से session string है")
print("   - या किसी दूसरे device से निकाल सकते हैं")
print("\nविकल्प 2: Fresh Login (OTP चाहिए - 5 मिनट में)")
print("   - New phone number के लिए")
print("   - Fresh authentication चाहिए तो")

choice = input("\nअपनी choice चुनें (1 या 2): ").strip()

session_name = "my_personal_account"

if choice == "1":
    print("\n" + "=" * 70)
    print("📝 Session String Authentication")
    print("=" * 70)
    print("\nSession string कहाँ से लें:")
    print("1. किसी दूसरे device पर यह script चलाएं:")
    print("   app = Client('temp', api_id, api_hash)")
    print("   app.start()")
    print("   print(app.export_session_string())")
    print("   app.stop()")
    print("\n2. या नीचे paste करें:\n")
    
    session_string = input("Session String: ").strip()
    
    if not session_string or len(session_string) < 50:
        print("❌ Invalid session string!")
        sys.exit(1)
    
    try:
        print("\n⏳ Session से connect हो रहे हैं...")
        app = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string
        )
        
        app.start()
        me = app.get_me()
        
        print("\n" + "=" * 70)
        print("✅ ✅ ✅ सफलतापूर्वक Connected! ✅ ✅ ✅")
        print("=" * 70)
        print(f"   नाम: {me.first_name} {me.last_name or ''}")
        print(f"   Phone: {me.phone_number}")
        print(f"   Username: @{me.username if me.username else 'None'}")
        print(f"   Session file saved: {session_name}.session")
        print("=" * 70)
        
        app.stop()
        
        print("\n✅ Session file create हो गया!")
        print("   अब bot चला सकते हैं: python start_both_bots.py")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        print("\nSession string invalid हो सकता है।")
        print("Fresh session string try करें या विकल्प 2 चुनें।")
        sys.exit(1)

elif choice == "2":
    print("\n" + "=" * 70)
    print("📱 Fresh Phone Login (⚠️ OTP 5 मिनट में expire होगा)")
    print("=" * 70)
    
    phone = input("\nPhone number (country code के साथ, जैसे +919876543210): ").strip()
    
    if not phone.startswith('+'):
        print("\n❌ Phone number '+' से शुरू होना चाहिए!")
        sys.exit(1)
    
    try:
        print(f"\n⏳ {phone} पर OTP भेजा जा रहा है...")
        print("\n⚠️  IMPORTANT:")
        print("   - OTP 5 मिनट में expire होगा")
        print("   - OTP मिलते ही तुरंत यहाँ enter करें")
        print("   - देर मत करें!\n")
        
        app = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone
        )
        
        app.start()
        me = app.get_me()
        
        print("\n" + "=" * 70)
        print("✅ ✅ ✅ सफलतापूर्वक Authenticated! ✅ ✅ ✅")
        print("=" * 70)
        print(f"   नाम: {me.first_name} {me.last_name or ''}")
        print(f"   Phone: {me.phone_number}")
        print(f"   Username: @{me.username if me.username else 'None'}")
        print(f"   Session file saved: {session_name}.session")
        print("=" * 70)
        
        session_string = app.export_session_string()
        print(f"\n📝 Session String (future के लिए save करें):")
        print(f"\n{session_string}\n")
        print("⚠️  इस session string को safe जगह save करें!")
        print("   अगली बार OTP की जरूरत नहीं पड़ेगी।")
        
        app.stop()
        
        print("\n✅ अब bot चला सकते हैं: python start_both_bots.py")
        
    except Exception as e:
        print(f"\n❌ Authentication Failed!")
        print(f"Error: {str(e)}")
        
        if "PHONE_CODE_EXPIRED" in str(e):
            print("\n💡 OTP expire हो गया!")
            print("   Solution:")
            print("   1. फिर से script run करें")
            print("   2. OTP मिलते ही तुरंत (30 seconds में) enter करें")
            print("   3. या विकल्प 1 चुनें (session string)")
        elif "2FA" in str(e) or "PASSWORD" in str(e):
            print("\n💡 2-Step Verification enabled है!")
            print("   Solution:")
            print("   1. Telegram Settings > Privacy & Security")
            print("   2. Two-Step Verification को temporarily disable करें")
            print("   3. Authentication के बाद फिर enable कर दें")
        else:
            print(f"\n💡 Troubleshooting:")
            print(f"   1. Phone number सही है? (जैसे +919876543210)")
            print(f"   2. API credentials सही हैं?")
            print(f"   3. Internet connection stable है?")
        
        sys.exit(1)

else:
    print("\n❌ Invalid choice! 1 या 2 चुनें।")
    sys.exit(1)
