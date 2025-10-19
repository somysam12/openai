#!/usr/bin/env python3
"""
Combined Bot Runner - Starts both Main Bot and Personal Account Bot
Use this for Render deployment to run both bots in one web service
"""
import os
import threading
import logging
import time

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def run_main_bot():
    """Run main Telegram bot (regular bot API)"""
    try:
        logger.info("=" * 60)
        logger.info("🤖 STARTING MAIN TELEGRAM BOT (Bot API)")
        logger.info("=" * 60)
        
        # Import main bot modules
        from main import TelegramChatBot, run_flask
        
        # Start Flask health check server in background
        flask_thread = threading.Thread(target=run_flask, daemon=True, name="FlaskThread")
        flask_thread.start()
        logger.info("✅ Flask health check server started on port 10000")
        
        # Create and run bot
        bot = TelegramChatBot()
        logger.info("✅ Main bot initialized successfully")
        bot.run()
        
    except ValueError as ve:
        logger.error(f"❌ Configuration error: {ve}")
        logger.error("Please check your environment variables!")
        raise
    except Exception as e:
        logger.error(f"❌ Main bot failed to start: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

def run_personal_bot():
    """Run personal account bot (Pyrogram user bot)"""
    try:
        # Check if session file exists
        if not os.path.exists('my_personal_account.session'):
            logger.warning("=" * 60)
            logger.warning("⚠️  SESSION FILE NOT FOUND")
            logger.warning("Personal Account Bot will NOT start")
            logger.warning("To enable it:")
            logger.warning("1. Run 'python quick_auth.py' locally")
            logger.warning("2. Upload session file to deployment")
            logger.warning("=" * 60)
            return
        
        # Check if API credentials are set
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        
        if not api_id or not api_hash:
            logger.warning("=" * 60)
            logger.warning("⚠️  TELEGRAM_API_ID or TELEGRAM_API_HASH not set")
            logger.warning("Personal Account Bot will NOT start")
            logger.warning("Set these environment variables to enable it")
            logger.warning("=" * 60)
            return
        
        logger.info("=" * 60)
        logger.info("👤 STARTING PERSONAL ACCOUNT BOT (Pyrogram)")
        logger.info("=" * 60)
        
        # Fix for Python 3.13: Create new event loop for this thread
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        from personal_account_autoreply import PersonalAccountBot
        bot = PersonalAccountBot()
        logger.info("✅ Personal bot initialized successfully")
        bot.run()
        
    except Exception as e:
        logger.error(f"❌ Personal bot failed to start: {e}")
        logger.warning("Personal bot will be skipped, but main bot will continue")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == '__main__':
    logger.info("🚀 COMBINED BOT RUNNER STARTING...")
    logger.info("This will run both bots simultaneously")
    logger.info("")
    
    # Start personal bot in background thread (daemon)
    # Daemon thread will automatically stop when main thread stops
    personal_thread = threading.Thread(
        target=run_personal_bot,
        daemon=True,
        name="PersonalBotThread"
    )
    personal_thread.start()
    
    # Give personal bot a moment to start
    time.sleep(2)
    
    # Start main bot in foreground (this will keep the process alive)
    # Main bot includes Flask health check server for Render
    try:
        run_main_bot()
    except KeyboardInterrupt:
        logger.info("🛑 Bots stopped by user")
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        logger.error("")
        logger.error("=" * 60)
        logger.error("DEPLOYMENT FAILED - CHECK ENVIRONMENT VARIABLES:")
        logger.error("Required variables:")
        logger.error("  - TELEGRAM_BOT_TOKEN")
        logger.error("  - OPENAI_API_KEY (or OPENAI_API_KEY_1)")
        logger.error("  - ADMIN_ID")
        logger.error("=" * 60)
        raise
