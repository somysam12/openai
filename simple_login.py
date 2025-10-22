#!/usr/bin/env python3
"""
Simple Pyrogram Login Script
Run this to create a new session for your Telegram account
Usage: python simple_login.py
"""

import os
from pyrogram import Client

print("=" * 60)
print("🔐 Telegram Account Login - Pyrogram Session Creator")
print("=" * 60)
print()

# Get API credentials
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

if not api_id or not api_hash:
    print("❌ ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH not found in environment!")
    print()
    print("Please set these in Replit Secrets:")
    print("1. Go to Tools > Secrets in Replit")
    print("2. Add TELEGRAM_API_ID (example: 12345678)")
    print("3. Add TELEGRAM_API_HASH (example: 0123456789abcdef0123456789abcdef)")
    print()
    print("Get your credentials from: https://my.telegram.org/apps")
    exit(1)

api_id = int(api_id)

print("✅ API credentials found!")
print(f"   API ID: {api_id}")
print(f"   API Hash: {api_hash[:8]}...")
print()

# Delete old session if exists
old_session = "my_personal_account.session"
if os.path.exists(old_session):
    print(f"🗑️  Deleting old session file: {old_session}")
    os.remove(old_session)
    print("✅ Old session deleted!")
    print()

# Create new session
print("📱 Creating new Pyrogram session...")
print()
print("IMPORTANT:")
print("1. Enter your phone number with country code (example: +919876543210)")
print("2. You will receive an OTP on Telegram")
print("3. Enter the OTP when prompted")
print("4. If you have 2FA enabled, enter your password")
print()

app = Client(
    "my_personal_account",
    api_id=api_id,
    api_hash=api_hash
)

print("-" * 60)

async def login():
    async with app:
        me = await app.get_me()
        print()
        print("=" * 60)
        print("✅ LOGIN SUCCESSFUL!")
        print("=" * 60)
        print(f"👤 Name: {me.first_name} {me.last_name or ''}")
        print(f"📱 Phone: +{me.phone_number}")
        print(f"🆔 User ID: {me.id}")
        print(f"👤 Username: @{me.username}" if me.username else "")
        print()
        print(f"✅ Session saved to: {old_session}")
        print()
        print("🎉 You can now use the music bot and DM bot features!")
        print("=" * 60)

# Run the login
import asyncio
asyncio.run(login())
