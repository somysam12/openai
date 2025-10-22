#!/bin/bash
# Test script for music bot - LOCAL TESTING ONLY

# Check if environment variables are set
if [ -z "$TELEGRAM_API_ID" ] || [ -z "$TELEGRAM_API_HASH" ]; then
    echo "❌ ERROR: Environment variables not set!"
    echo ""
    echo "Please set these variables first:"
    echo "export TELEGRAM_API_ID=your_api_id"
    echo "export TELEGRAM_API_HASH=your_api_hash"
    echo ""
    echo "Get these from: https://my.telegram.org/apps"
    exit 1
fi

echo "✅ Environment variables found"
echo "✅ Starting music bot test..."
python3 start_both_bots.py
