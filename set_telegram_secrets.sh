#!/bin/bash
# Telegram API Credentials Setup Script

echo "🔐 Telegram API Credentials Setup"
echo "=================================="
echo ""
echo "Pehle credentials le lo: https://my.telegram.org/auth"
echo ""
read -p "Enter your TELEGRAM_API_ID (7-8 digit number): " API_ID
read -p "Enter your TELEGRAM_API_HASH (32 character string): " API_HASH

echo ""
echo "✅ Credentials received!"
echo ""

# Export to current session
export TELEGRAM_API_ID="$API_ID"
export TELEGRAM_API_HASH="$API_HASH"

# Save to .env file for persistence
echo "TELEGRAM_API_ID=$API_ID" >> .env
echo "TELEGRAM_API_HASH=$API_HASH" >> .env

echo "✅ Credentials saved to .env file"
echo ""
echo "Now run: source .env"
echo "Then run: python quick_auth.py"
