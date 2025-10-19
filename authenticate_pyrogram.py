#!/usr/bin/env python3
"""
Simple script to authenticate Pyrogram
Run this once to login to your personal account
"""

import os
from pyrogram import Client

api_id = int(os.getenv('TELEGRAM_API_ID', '0'))
api_hash = os.getenv('TELEGRAM_API_HASH', '')
phone_number = os.getenv('PHONE_NUMBER', '')
phone_code = os.getenv('PHONE_CODE', '')
password = os.getenv('TWO_FACTOR_PASSWORD', '')

if api_id == 0 or not api_hash:
    print("❌ Error: TELEGRAM_API_ID and TELEGRAM_API_HASH not found!")
    print("Please set them in Replit Secrets")
    exit(1)

print("🔐 Pyrogram Authentication")
print("=" * 50)

if not phone_number:
    print("\n⚠️  PHONE_NUMBER environment variable not set!")
    print("\nPlease add your phone number to Replit Secrets:")
    print("   Key: PHONE_NUMBER")
    print("   Value: Your phone with country code (e.g., +919876543210)")
    print("\nThen restart this workflow.")
    exit(1)

print(f"\n📱 Using phone number: {phone_number}")

if not phone_code:
    print("\n⚠️  PHONE_CODE environment variable not set!")
    print("\nPlease check your Telegram app for the OTP code.")
    print("Then add it to Replit Secrets:")
    print("   Key: PHONE_CODE")
    print("   Value: The 5-digit code from Telegram (e.g., 12345)")
    print("\nThen restart this workflow.")
    exit(1)

print(f"\n✅ Using OTP code: {phone_code}")
print("\n" + "=" * 50)

app = Client("my_personal_account", api_id=api_id, api_hash=api_hash, phone_number=phone_number, phone_code=phone_code, password=password if password else None)

with app:
    me = app.get_me()
    print(f"\n✅ Successfully logged in as: {me.first_name}")
    print(f"   Phone: {me.phone_number}")
    print(f"   Username: @{me.username if me.username else 'None'}")
    print(f"\n✅ Session file created: my_personal_account.session")
    print("\nYou can now run the Personal Account Bot!")
