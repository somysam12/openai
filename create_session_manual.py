#!/usr/bin/env python3
"""
Manual Session Creator - Input from credentials.txt file
"""
import os
from pyrogram import Client

print("=" * 60)
print("🔐 Manual Telegram Session Creator")
print("=" * 60)

# Read from environment (Replit Secrets)
api_id = os.getenv('TELEGRAM_API_ID')
api_hash = os.getenv('TELEGRAM_API_HASH')

if not api_id or not api_hash:
    print("❌ Error: TELEGRAM_API_ID or TELEGRAM_API_HASH not found!")
    print("Please set them in Replit Secrets")
    exit(1)

api_id = int(api_id)

print("✅ API credentials loaded from Replit Secrets")
print("")
print("📱 Ab credentials.txt file banao with:")
print("   Line 1: Phone number (e.g., +919876543210)")
print("   Line 2: OTP code (Telegram se aayega)")
print("   Line 3: 2FA password (optional, agar enabled hai)")
print("")
print("File banne ke baad yeh script phir se run karo")
print("=" * 60)

# Check if credentials file exists
if not os.path.exists('credentials.txt'):
    print("")
    print("⚠️  credentials.txt file nahi mili")
    print("")
    print("Pehle yeh file banao:")
    with open('credentials.txt', 'w') as f:
        f.write("+91XXXXXXXXXX\n")
        f.write("12345\n")
        f.write("your_2fa_password_if_any\n")
    
    print("✅ Template file created: credentials.txt")
    print("   Apne phone number, OTP aur password se replace karo")
    print("   Phir script dobara run karo")
    exit(0)

# Read credentials
with open('credentials.txt', 'r') as f:
    lines = f.read().strip().split('\n')

phone = lines[0].strip() if len(lines) > 0 else None
otp = lines[1].strip() if len(lines) > 1 else None
password = lines[2].strip() if len(lines) > 2 else None

if not phone or phone.startswith('+91XXX'):
    print("❌ Error: credentials.txt mein phone number update karo!")
    exit(1)

print(f"📱 Phone: {phone}")
print(f"🔐 OTP: {otp if otp else 'Not provided'}")
print("")

# This approach won't work perfectly in non-interactive mode
# Better to guide user to use Replit Console or local machine
print("⚠️  Note: This script requires interactive input")
print("")
print("🎯 BEST APPROACH:")
print("   1. Open Replit Console tab (bottom)")
print("   2. Run: python create_session_interactive.py")
print("   3. Enter phone number when asked")
print("   4. Enter OTP when Telegram sends it")
print("")
print("   OR")
print("")
print("   Run this on your local computer and upload .session file")
