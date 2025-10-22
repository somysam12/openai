#!/usr/bin/env python3
"""
Quick test to verify music bot dependencies are working
"""

import sys

print("=" * 60)
print("🎵 Testing Music Bot Setup")
print("=" * 60)

try:
    print("\n1. Testing FFmpeg...")
    import subprocess
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
    if result.returncode == 0:
        version_line = result.stdout.split('\n')[0]
        print(f"   ✅ FFmpeg: {version_line}")
    else:
        print("   ❌ FFmpeg not working!")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ FFmpeg error: {e}")
    sys.exit(1)

try:
    print("\n2. Testing Pyrogram...")
    import pyrogram
    print(f"   ✅ Pyrogram installed (version: {pyrogram.__version__})")
except Exception as e:
    print(f"   ❌ Pyrogram error: {e}")
    sys.exit(1)

try:
    print("\n3. Testing PyTgCalls...")
    import pytgcalls
    from pytgcalls import PyTgCalls
    print("   ✅ PyTgCalls installed")
except Exception as e:
    print(f"   ❌ PyTgCalls error: {e}")
    sys.exit(1)

try:
    print("\n4. Testing yt-dlp...")
    import yt_dlp
    print(f"   ✅ yt-dlp installed (version: {yt_dlp.version.__version__})")
except Exception as e:
    print(f"   ❌ yt-dlp error: {e}")
    sys.exit(1)

try:
    print("\n5. Testing other dependencies...")
    import aiofiles
    import aiohttp
    print("   ✅ aiofiles, aiohttp installed")
except Exception as e:
    print(f"   ❌ Dependencies error: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL MUSIC BOT DEPENDENCIES ARE WORKING!")
print("=" * 60)
print("\nNext steps:")
print("1. Run: python simple_login.py")
print("2. Login with your phone number")
print("3. Start the bot with: python start_both_bots.py")
print("4. In any Telegram group, use:")
print("   - /play <song name>")
print("   - /pause, /resume, /skip, /stop")
print("   - /queue (show current queue)")
print("   - /join, /leave (voice chat)")
print("   - Or mention bot: @username play Kesariya")
print("=" * 60)
