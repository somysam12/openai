#!/usr/bin/env python3
"""
Interactive Telegram Session Creator
Yeh script API ID/Hash manually enter karke session file banayegi
"""
from pyrogram import Client

print("=" * 60)
print("🔐 Telegram Session Creator (Interactive)")
print("=" * 60)
print("")
print("Pehle credentials le lo: https://my.telegram.org/auth")
print("")

# Manual input
api_id = input("Enter your API ID (numbers only): ").strip()
api_hash = input("Enter your API Hash (32 characters): ").strip()

print("")
print("✅ Credentials received! Ab login process shuru hogi...")
print("")
print("Note: Telegram se OTP code aayega, yahan enter karna hai")
print("=" * 60)
print("")

# Convert API ID to integer
try:
    api_id = int(api_id)
except ValueError:
    print("❌ Error: API ID should be numbers only!")
    exit(1)

# Create client
app = Client("my_personal_account", api_id=api_id, api_hash=api_hash)

try:
    # Start will automatically ask for phone number and OTP
    app.start()
    
    # Get user info
    me = app.get_me()
    
    print("")
    print("=" * 60)
    print("✅ SESSION SUCCESSFULLY CREATED!")
    print("=" * 60)
    print(f"   Name: {me.first_name} {me.last_name or ''}")
    print(f"   Phone: {me.phone_number}")
    print(f"   Username: @{me.username if me.username else 'None'}")
    print(f"   User ID: {me.id}")
    print("")
    print("📁 Session file saved: my_personal_account.session")
    print("=" * 60)
    print("")
    print("✅ Ab yeh session file git pe push kar sakte ho!")
    print("")
    
    # Stop client
    app.stop()
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("")
    print("Common issues:")
    print("1. API ID/Hash galat hai")
    print("2. OTP code wrong enter hua")
    print("3. Phone number format galat hai (+91XXXXXXXXXX)")
