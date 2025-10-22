#!/usr/bin/env python3
"""
Personal Telegram Account Auto-Reply Bot with AI Integration + Music Playback
Uses Pyrogram to read and reply to DMs on your personal account
Integrates with existing bot's knowledge base, keywords, and AI logic
Now includes PyTgCalls music playback in group voice chats
"""

import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatAction
import sqlite3
from datetime import datetime, timedelta
from openai import OpenAI
from pytgcalls import PyTgCalls
from pytgcalls.types.stream import MediaStream, AudioQuality
from pytgcalls.exceptions import NoActiveGroupCall, AlreadyJoinedError
import yt_dlp
from collections import deque
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class PersonalAccountBot:
    def __init__(self):
        # Pyrogram credentials - Get from https://my.telegram.org/apps
        self.api_id = int(os.getenv('TELEGRAM_API_ID', '0'))
        self.api_hash = os.getenv('TELEGRAM_API_HASH', '')
        
        if self.api_id == 0 or not self.api_hash:
            raise ValueError("Please set TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables")
        
        # OpenAI Setup (uses same logic as main bot)
        self.api_keys = []
        for i in range(1, 20):
            key = os.getenv(f'OPENAI_API_KEY_{i}')
            if key:
                self.api_keys.append(key)
        
        single_key = os.getenv('OPENAI_API_KEY')
        if single_key and single_key not in self.api_keys:
            self.api_keys.insert(0, single_key)
        
        if not self.api_keys:
            logger.warning("No OpenAI API key found - AI responses will be disabled")
            self.openai_client = None
        else:
            self.current_key_index = 0
            self.openai_client = OpenAI(api_key=self.api_keys[self.current_key_index], max_retries=0)
            logger.info(f"✅ Loaded {len(self.api_keys)} API keys for rotation")
        
        # Session name - will create a file to save login
        self.app = Client(
            "my_personal_account",
            api_id=self.api_id,
            api_hash=self.api_hash
        )
        
        # Use same database as main bot for knowledge and keywords
        self.main_db_path = 'chat_history.db'
        self.tracking_db_path = 'personal_autoreplies.db'
        self.init_database()
        
        # Enable/Disable features
        self.use_ai_responses = os.getenv('USE_AI_RESPONSES', 'true').lower() == 'true'
        self.use_keywords = os.getenv('USE_KEYWORDS', 'true').lower() == 'true'
        self.use_knowledge_base = os.getenv('USE_KNOWLEDGE_BASE', 'true').lower() == 'true'
        
        # Rate limiting: Max replies per user
        self.reply_cooldown_hours = int(os.getenv('REPLY_COOLDOWN_HOURS', '0'))
        
        # Auto-reply message
        self.auto_reply_message = os.getenv('AUTO_REPLY_MESSAGE', 
            "Namaste! Main abhi busy hoon. Aap ka message dekha hai, jald hi reply karunga. 🙏")
        
        # Initialize PyTgCalls for music playback
        self.call_py = PyTgCalls(self.app)
        
        # Music queue management
        self.queues = {}  # {chat_id: deque([{title, file_path, url, requester}])}
        self.current_playing = {}  # {chat_id: {title, file_path, url, requester}}
        
        logger.info(f"Personal Account Bot initialized:")
        logger.info(f"  - AI Responses: {'✅' if self.use_ai_responses and self.openai_client else '❌'}")
        logger.info(f"  - Keywords: {'✅' if self.use_keywords else '❌'}")
        logger.info(f"  - Knowledge Base: {'✅' if self.use_knowledge_base else '❌'}")
        logger.info(f"  - Cooldown: {self.reply_cooldown_hours} hours (0 = disabled)")
        logger.info(f"  - Music Playback: ✅ (PyTgCalls enabled)")
    
    def rotate_api_key(self, reason="manual"):
        """Rotate to the next available API key and track in database"""
        if not self.openai_client or len(self.api_keys) <= 1:
            return 0
        
        # Track rate limit hit in database if applicable
        if reason == "rate_limit":
            self.track_api_key_usage(rate_limit_hit=True)
        
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        new_key = self.api_keys[self.current_key_index]
        self.openai_client = OpenAI(api_key=new_key, max_retries=0)
        logger.warning(f"🔄 Rotated to API key #{self.current_key_index + 1} (Reason: {reason})")
        return self.current_key_index + 1
    
    def track_api_key_usage(self, rate_limit_hit=False, tokens_input=0, tokens_output=0):
        """Track API key usage with token counting in database (same as main bot)"""
        from datetime import datetime, timedelta
        try:
            conn = sqlite3.connect(self.main_db_path)
            cursor = conn.cursor()
            
            # Get current stats for this key
            cursor.execute('SELECT daily_reset_time FROM api_key_stats WHERE key_index = ?', (self.current_key_index,))
            result = cursor.fetchone()
            
            # Check if daily reset is needed
            should_reset = False
            if result and result[0]:
                last_reset = datetime.fromisoformat(result[0])
                if datetime.now() - last_reset >= timedelta(hours=24):
                    should_reset = True
            else:
                should_reset = True
            
            tokens_total = tokens_input + tokens_output
            
            if should_reset:
                # Reset daily counters
                if rate_limit_hit:
                    cursor.execute('''
                        INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits,
                                                   tokens_used_today, tokens_input_today, tokens_output_today,
                                                   daily_reset_time, total_tokens_lifetime)
                        VALUES (?, 0, ?, 1, 0, 0, 0, ?, ?)
                        ON CONFLICT(key_index) DO UPDATE SET
                            rate_limit_hits = rate_limit_hits + 1,
                            last_used = ?,
                            tokens_used_today = 0,
                            tokens_input_today = 0,
                            tokens_output_today = 0,
                            daily_reset_time = ?,
                            total_tokens_lifetime = total_tokens_lifetime + ?
                    ''', (self.current_key_index, datetime.now().isoformat(), datetime.now().isoformat(), tokens_total,
                          datetime.now().isoformat(), datetime.now().isoformat(), tokens_total))
                else:
                    cursor.execute('''
                        INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits,
                                                   tokens_used_today, tokens_input_today, tokens_output_today,
                                                   daily_reset_time, total_tokens_lifetime)
                        VALUES (?, 1, ?, 0, ?, ?, ?, ?, ?)
                        ON CONFLICT(key_index) DO UPDATE SET
                            usage_count = usage_count + 1,
                            last_used = ?,
                            tokens_used_today = ?,
                            tokens_input_today = ?,
                            tokens_output_today = ?,
                            daily_reset_time = ?,
                            total_tokens_lifetime = total_tokens_lifetime + ?
                    ''', (self.current_key_index, datetime.now().isoformat(), tokens_total, tokens_input, tokens_output,
                          datetime.now().isoformat(), tokens_total, datetime.now().isoformat(), tokens_total, 
                          tokens_input, tokens_output, datetime.now().isoformat(), tokens_total))
            else:
                # Increment daily counters
                if rate_limit_hit:
                    cursor.execute('''
                        INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits,
                                                   tokens_used_today, tokens_input_today, tokens_output_today,
                                                   daily_reset_time, total_tokens_lifetime)
                        VALUES (?, 0, ?, 1, 0, 0, 0, ?, ?)
                        ON CONFLICT(key_index) DO UPDATE SET
                            rate_limit_hits = rate_limit_hits + 1,
                            last_used = ?,
                            total_tokens_lifetime = total_tokens_lifetime + ?
                    ''', (self.current_key_index, datetime.now().isoformat(), datetime.now().isoformat(), tokens_total,
                          datetime.now().isoformat(), tokens_total))
                else:
                    cursor.execute('''
                        INSERT INTO api_key_stats (key_index, usage_count, last_used, rate_limit_hits,
                                                   tokens_used_today, tokens_input_today, tokens_output_today,
                                                   daily_reset_time, total_tokens_lifetime)
                        VALUES (?, 1, ?, 0, ?, ?, ?, ?, ?)
                        ON CONFLICT(key_index) DO UPDATE SET
                            usage_count = usage_count + 1,
                            last_used = ?,
                            tokens_used_today = tokens_used_today + ?,
                            tokens_input_today = tokens_input_today + ?,
                            tokens_output_today = tokens_output_today + ?,
                            total_tokens_lifetime = total_tokens_lifetime + ?
                    ''', (self.current_key_index, datetime.now().isoformat(), tokens_total, tokens_input, tokens_output,
                          datetime.now().isoformat(), tokens_total, datetime.now().isoformat(), tokens_total,
                          tokens_input, tokens_output, tokens_total))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to track API key usage: {e}")
    
    def init_database(self):
        """Initialize database to track auto-replies"""
        conn = sqlite3.connect(self.tracking_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_replies (
                user_id INTEGER PRIMARY KEY,
                last_reply_time DATETIME,
                reply_count INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized for personal account bot")
    
    def get_bot_knowledge(self):
        """Get bot knowledge from main bot's database"""
        if not self.use_knowledge_base:
            return None
        
        try:
            conn = sqlite3.connect(self.main_db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT knowledge_text FROM bot_knowledge ORDER BY created_at ASC')
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return None
            
            return '\n\n'.join([row[0] for row in results])
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            return None
    
    def check_keyword_match(self, message: str):
        """Check if message contains any keyword from main bot's database"""
        if not self.use_keywords:
            return None
        
        try:
            conn = sqlite3.connect(self.main_db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT keyword, response FROM group_keywords')
            keywords = cursor.fetchall()
            conn.close()
            
            message_lower = message.lower()
            
            for keyword, response in keywords:
                if keyword.lower() in message_lower:
                    logger.info(f"Keyword matched: '{keyword}' in message")
                    return response
            
            return None
        except Exception as e:
            logger.error(f"Failed to check keywords: {e}")
            return None
    
    def get_recent_history(self, user_id: int, limit: int = 3):
        """Get recent chat history with this user"""
        try:
            conn = sqlite3.connect(self.main_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT message, response FROM chat_history
                WHERE user_id = ? AND chat_type = 'dm'
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (user_id, limit))
            
            history = cursor.fetchall()
            conn.close()
            
            return list(reversed(history))
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []
    
    def save_chat_history(self, user_id: int, username: str, message: str, response: str):
        """Save chat to main bot's database"""
        try:
            conn = sqlite3.connect(self.main_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO chat_history (user_id, username, message, response, message_role, chat_type, chat_id)
                VALUES (?, ?, ?, ?, 'user', 'dm', ?)
            ''', (user_id, username, message, response, user_id))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")
    
    def should_auto_reply(self, user_id: int) -> bool:
        """Check if we should auto-reply to this user (rate limiting)"""
        if self.reply_cooldown_hours == 0:
            return True  # Cooldown disabled
        
        conn = sqlite3.connect(self.tracking_db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT last_reply_time FROM auto_replies WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return True  # First time, allow
        
        last_reply = datetime.fromisoformat(result[0])
        time_since_reply = datetime.now() - last_reply
        
        # Allow if cooldown period has passed
        return time_since_reply > timedelta(hours=self.reply_cooldown_hours)
    
    def record_auto_reply(self, user_id: int):
        """Record that we sent an auto-reply"""
        if self.reply_cooldown_hours == 0:
            return  # Don't track if cooldown disabled
        
        conn = sqlite3.connect(self.tracking_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO auto_replies (user_id, last_reply_time, reply_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                last_reply_time = ?,
                reply_count = reply_count + 1
        ''', (user_id, datetime.now().isoformat(), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    async def handle_incoming_dm(self, client: Client, message: Message):
        """Handle incoming private messages with AI, keywords, and knowledge"""
        # Ignore if message is from yourself
        if message.from_user.is_self:
            return
        
        # Ignore if message is outgoing (you sent it)
        if message.outgoing:
            return
        
        # Only process text messages
        if not message.text:
            logger.info("Ignoring non-text message")
            return
        
        user_id = message.from_user.id
        username = message.from_user.username or "Unknown"
        first_name = message.from_user.first_name or "Dost"
        user_message = message.text
        
        logger.info(f"📨 Received DM from {username} (ID: {user_id}): {user_message[:50]}")
        
        # Check rate limiting
        if not self.should_auto_reply(user_id):
            logger.info(f"⏳ Skipping reply for {username} (cooldown active)")
            return
        
        try:
            # Step 1: Check for keyword match (instant response)
            keyword_response = self.check_keyword_match(user_message)
            if keyword_response:
                await message.reply_text(keyword_response)
                self.record_auto_reply(user_id)
                self.save_chat_history(user_id, username, user_message, keyword_response)
                logger.info(f"✅ Sent keyword response to {username}")
                return
            
            # Step 2: Generate AI response (if enabled)
            if self.use_ai_responses and self.openai_client:
                await client.send_chat_action(message.chat.id, ChatAction.TYPING)
                
                # Get conversation history
                recent_history = self.get_recent_history(user_id, limit=3)
                custom_knowledge = self.get_bot_knowledge()
                
                # Build system prompt (same as main bot)
                system_prompt = "Tum ek highly intelligent aur helpful AI assistant ho. Tumhe Hindi aur English dono languages mein expert tarike se baat karni aani hai."
                system_prompt += f"\n\nUser ka naam: {first_name}"
                if username != "Unknown":
                    system_prompt += f" (@{username})"
                system_prompt += "\nNatural conversation mein user ka naam use kar sakte ho jab appropriate ho."
                
                if custom_knowledge:
                    system_prompt += f"\n\n📚 KNOWLEDGE BASE - CRITICAL INSTRUCTIONS:\n"
                    system_prompt += f"Tumhe niche detailed knowledge base diya gaya hai. Yeh tumhari PRIMARY source of information hai:\n\n"
                    system_prompt += f"=== START KNOWLEDGE BASE ===\n{custom_knowledge}\n=== END KNOWLEDGE BASE ===\n\n"
                    system_prompt += f"🎯 RULES FOR USING KNOWLEDGE:\n"
                    system_prompt += f"1. Jab bhi user kuch poochu, PEHLE knowledge base mein check karo\n"
                    system_prompt += f"2. Agar knowledge base mein answer mil jaye, toh WAHI detailed answer do\n"
                    system_prompt += f"3. Knowledge base ki information ko accurately aur completely use karo\n"
                    system_prompt += f"4. Products, services, pricing, features - SAB knowledge base se hi batana\n"
                    system_prompt += f"5. AGAR knowledge base mein koi information NAHI hai, tab normal conversation karo\n"
                else:
                    system_prompt += "\n\n💬 Normal friendly conversation karo."
                
                # Build messages
                messages = [{"role": "system", "content": system_prompt}]
                
                for prev_msg, prev_resp in recent_history:
                    messages.append({"role": "user", "content": prev_msg})
                    messages.append({"role": "assistant", "content": prev_resp})
                
                messages.append({"role": "user", "content": user_message})
                
                # Try API call with rotation
                max_attempts = len(self.api_keys)
                ai_response = None
                
                for attempt in range(max_attempts):
                    try:
                        response = self.openai_client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=messages,
                            max_tokens=500,
                            temperature=0.7
                        )
                        ai_response = response.choices[0].message.content
                        
                        # Track successful API usage with token counts
                        tokens_input = response.usage.prompt_tokens if response.usage else 0
                        tokens_output = response.usage.completion_tokens if response.usage else 0
                        self.track_api_key_usage(rate_limit_hit=False, tokens_input=tokens_input, tokens_output=tokens_output)
                        logger.info(f"✅ Personal bot API call. Tokens: {tokens_input} in + {tokens_output} out = {tokens_input + tokens_output} total")
                        break
                        
                    except Exception as api_error:
                        error_str = str(api_error).lower()
                        
                        # Check for errors that need key rotation
                        should_rotate = False
                        rotation_reason = "error"
                        
                        if "429" in error_str or "rate limit" in error_str:
                            should_rotate = True
                            rotation_reason = "rate_limit"
                            logger.warning(f"⚠️ Rate limit hit on API key #{self.current_key_index + 1}")
                        
                        elif "401" in error_str or "unauthorized" in error_str or "account_deactivated" in error_str:
                            should_rotate = True
                            rotation_reason = "account_deactivated"
                            logger.warning(f"⚠️ API key #{self.current_key_index + 1} is deactivated/invalid")
                        
                        elif "403" in error_str or "forbidden" in error_str:
                            should_rotate = True
                            rotation_reason = "forbidden"
                            logger.warning(f"⚠️ API key #{self.current_key_index + 1} access forbidden")
                        
                        elif "invalid_api_key" in error_str or "incorrect api key" in error_str:
                            should_rotate = True
                            rotation_reason = "invalid_key"
                            logger.warning(f"⚠️ API key #{self.current_key_index + 1} is invalid")
                        
                        if should_rotate:
                            if attempt < max_attempts - 1:
                                self.rotate_api_key(reason=rotation_reason)
                                logger.info(f"🔄 Retrying with next API key (Attempt {attempt + 2}/{max_attempts})...")
                                continue
                            else:
                                logger.error("❌ All API keys exhausted!")
                                raise Exception(f"All {max_attempts} API keys failed")
                        else:
                            # Unknown error - don't rotate, just fail
                            logger.error(f"❌ Unexpected API error: {api_error}")
                            raise api_error
                
                if ai_response:
                    await message.reply_text(ai_response)
                    self.record_auto_reply(user_id)
                    self.save_chat_history(user_id, username, user_message, ai_response)
                    logger.info(f"✅ Sent AI response to {username}")
                else:
                    raise Exception("No AI response generated")
            
            else:
                # Fallback: Simple message
                fallback_msg = "Thank you for your message! I'll get back to you soon."
                await message.reply_text(fallback_msg)
                self.record_auto_reply(user_id)
                logger.info(f"✅ Sent fallback response to {username}")
        
        except Exception as e:
            logger.error(f"❌ Error handling message from {username}: {e}")
            try:
                await message.reply_text("Sorry, I'm experiencing technical difficulties. Please try again later.")
            except:
                pass
    
    # ========== MUSIC PLAYBACK METHODS ==========
    
    async def download_song(self, query: str):
        """Download song from YouTube"""
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
            'audioquality': 0,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        os.makedirs('downloads', exist_ok=True)
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if not query.startswith('http'):
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                else:
                    info = ydl.extract_info(query, download=False)
                
                file_path = ydl.prepare_filename(info)
                file_path = file_path.rsplit('.', 1)[0] + '.mp3'
                
                if not os.path.exists(file_path):
                    ydl.download([info['webpage_url']])
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'file_path': file_path,
                    'url': info.get('webpage_url', ''),
                    'duration': info.get('duration', 0)
                }
        except Exception as e:
            logger.error(f"Error downloading song: {e}")
            return None
    
    async def join_voice_chat(self, message: Message):
        """Join the voice chat"""
        chat_id = message.chat.id
        
        try:
            silence_file = 'downloads/silence.mp3'
            if not os.path.exists(silence_file):
                os.makedirs('downloads', exist_ok=True)
                import subprocess
                subprocess.run([
                    'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                    '-t', '1', '-q:a', '9', '-acodec', 'libmp3lame', silence_file,
                    '-y'
                ], check=True, capture_output=True)
            
            await self.call_py.join_group_call(
                chat_id,
                MediaStream(silence_file, AudioQuality.HIGH)
            )
            await message.reply_text("✅ Voice chat mein join kar gaya!")
        except AlreadyJoinedError:
            await message.reply_text("⚠️ Main pehle se hi voice chat mein hoon!")
        except Exception as e:
            logger.error(f"Error joining voice chat: {e}")
            await message.reply_text(f"❌ Voice chat join nahi kar paya: {str(e)}")
    
    async def leave_voice_chat(self, message: Message):
        """Leave the voice chat"""
        chat_id = message.chat.id
        
        try:
            await self.call_py.leave_group_call(chat_id)
            
            if chat_id in self.queues:
                self.queues[chat_id].clear()
            if chat_id in self.current_playing:
                del self.current_playing[chat_id]
            
            await message.reply_text("✅ Voice chat se nikal gaya!")
        except Exception as e:
            logger.error(f"Error leaving voice chat: {e}")
            await message.reply_text(f"❌ Voice chat se nikal nahi paya: {str(e)}")
    
    async def play_music(self, message: Message, query: str = None):
        """Play music in voice chat"""
        chat_id = message.chat.id
        
        # Get song query from command or parameter
        if not query:
            if not message.text:
                await message.reply_text("❌ Song ka naam ya link bataiye!\n\nExample: /play Arijit Singh songs")
                return
            query_parts = message.text.split(maxsplit=1)
            if len(query_parts) < 2:
                await message.reply_text("❌ Song ka naam ya link bataiye!\n\nExample: /play Arijit Singh songs")
                return
            query = query_parts[1]
        
        status_msg = await message.reply_text("🔍 Song search kar raha hoon...")
        
        # Download song
        song_info = await self.download_song(query)
        
        if not song_info:
            await status_msg.edit_text("❌ Song nahi mila ya download nahi ho paya!")
            return
        
        # Add to queue
        if chat_id not in self.queues:
            self.queues[chat_id] = deque()
        
        song_data = {
            'title': song_info['title'],
            'file_path': song_info['file_path'],
            'url': song_info['url'],
            'requester': message.from_user.first_name
        }
        
        # Check if already playing
        if chat_id in self.current_playing:
            self.queues[chat_id].append(song_data)
            position = len(self.queues[chat_id])
            await status_msg.edit_text(
                f"✅ Queue mein add kar diya!\n\n"
                f"🎵 **{song_info['title']}**\n"
                f"📍 Position: #{position}\n"
                f"👤 Requested by: {message.from_user.first_name}"
            )
        else:
            # Play immediately
            self.current_playing[chat_id] = song_data
            await self.start_streaming(chat_id, song_info['file_path'])
            await status_msg.edit_text(
                f"🎶 **Ab bajega:**\n\n"
                f"🎵 {song_info['title']}\n"
                f"👤 Requested by: {message.from_user.first_name}"
            )
    
    async def start_streaming(self, chat_id: int, file_path: str):
        """Start streaming audio to voice chat"""
        try:
            await self.call_py.change_stream(
                chat_id,
                MediaStream(file_path, AudioQuality.HIGH)
            )
        except NoActiveGroupCall:
            await self.call_py.join_group_call(
                chat_id,
                MediaStream(file_path, AudioQuality.HIGH)
            )
        except Exception as e:
            logger.error(f"Error streaming audio: {e}")
    
    async def pause_music(self, message: Message):
        """Pause the music"""
        chat_id = message.chat.id
        
        try:
            await self.call_py.pause_stream(chat_id)
            await message.reply_text("⏸️ Music pause kar diya!")
        except Exception as e:
            await message.reply_text(f"❌ Pause nahi kar paya: {str(e)}")
    
    async def resume_music(self, message: Message):
        """Resume the music"""
        chat_id = message.chat.id
        
        try:
            await self.call_py.resume_stream(chat_id)
            await message.reply_text("▶️ Music resume kar diya!")
        except Exception as e:
            await message.reply_text(f"❌ Resume nahi kar paya: {str(e)}")
    
    async def skip_music(self, message: Message):
        """Skip to next song"""
        chat_id = message.chat.id
        
        if chat_id in self.current_playing:
            current = self.current_playing[chat_id]['title']
            await message.reply_text(f"⏭️ **{current}** ko skip kar diya!")
            await self.play_next_in_queue(chat_id)
        else:
            await message.reply_text("❌ Koi song nahi chal raha!")
    
    async def stop_music(self, message: Message):
        """Stop the music and clear queue"""
        chat_id = message.chat.id
        
        try:
            await self.call_py.leave_group_call(chat_id)
            
            if chat_id in self.queues:
                self.queues[chat_id].clear()
            if chat_id in self.current_playing:
                del self.current_playing[chat_id]
            
            await message.reply_text("⏹️ Music band kar diya aur queue clear kar di!")
        except Exception as e:
            await message.reply_text(f"❌ Stop nahi kar paya: {str(e)}")
    
    async def show_queue(self, message: Message):
        """Show current queue"""
        chat_id = message.chat.id
        
        if chat_id not in self.current_playing and (chat_id not in self.queues or len(self.queues[chat_id]) == 0):
            await message.reply_text("📭 Queue khali hai!")
            return
        
        response = "🎵 **Current Queue:**\n\n"
        
        if chat_id in self.current_playing:
            current = self.current_playing[chat_id]
            response += f"▶️ **Now Playing:**\n{current['title']}\n👤 {current['requester']}\n\n"
        
        if chat_id in self.queues and len(self.queues[chat_id]) > 0:
            response += "📝 **Up Next:**\n"
            for i, song in enumerate(list(self.queues[chat_id])[:10], 1):
                response += f"{i}. {song['title']}\n   👤 {song['requester']}\n"
            
            remaining = len(self.queues[chat_id]) - 10
            if remaining > 0:
                response += f"\n...and {remaining} more songs"
        
        await message.reply_text(response)
    
    async def play_next_in_queue(self, chat_id: int):
        """Play next song in queue"""
        if chat_id not in self.queues or len(self.queues[chat_id]) == 0:
            if chat_id in self.current_playing:
                del self.current_playing[chat_id]
            await self.call_py.leave_group_call(chat_id)
            return
        
        next_song = self.queues[chat_id].popleft()
        self.current_playing[chat_id] = next_song
        await self.start_streaming(chat_id, next_song['file_path'])
    
    async def handle_music_mention(self, client: Client, message: Message):
        """Handle mentions with music requests in natural language"""
        if not message.text:
            return
        
        text_lower = message.text.lower()
        
        # Check for play/song keywords with mention
        play_keywords = ['play', 'bajao', 'chalao', 'song', 'gaana', 'music']
        
        if any(keyword in text_lower for keyword in play_keywords):
            # Extract song name after mention
            # Remove mention part
            text_clean = re.sub(r'@\w+', '', message.text).strip()
            
            # Remove play keywords
            for keyword in ['play', 'bajao', 'chalao', 'song', 'gaana', 'music']:
                text_clean = re.sub(rf'\b{keyword}\b', '', text_clean, flags=re.IGNORECASE).strip()
            
            if text_clean:
                await self.play_music(message, query=text_clean)
            else:
                await message.reply_text("❌ Song ka naam bataiye!\n\nExample: @username play Kesariya")
    
    # ========== END MUSIC METHODS ==========
    
    def run(self):
        """Start the personal account bot with music playback support"""
        import asyncio
        logger.info("Starting Personal Account Auto-Reply Bot + Music Bot...")
        
        # Register handler for incoming private messages
        @self.app.on_message(filters.private & filters.incoming)
        async def on_private_message(client: Client, message: Message):
            await self.handle_incoming_dm(client, message)
        
        # ===== MUSIC COMMAND HANDLERS (GROUP ONLY) =====
        
        @self.app.on_message(filters.command("play") & filters.group)
        async def play_command(client: Client, message: Message):
            await self.play_music(message)
        
        @self.app.on_message(filters.command("pause") & filters.group)
        async def pause_command(client: Client, message: Message):
            await self.pause_music(message)
        
        @self.app.on_message(filters.command("resume") & filters.group)
        async def resume_command(client: Client, message: Message):
            await self.resume_music(message)
        
        @self.app.on_message(filters.command("skip") & filters.group)
        async def skip_command(client: Client, message: Message):
            await self.skip_music(message)
        
        @self.app.on_message(filters.command("stop") & filters.group)
        async def stop_command(client: Client, message: Message):
            await self.stop_music(message)
        
        @self.app.on_message(filters.command("queue") & filters.group)
        async def queue_command(client: Client, message: Message):
            await self.show_queue(message)
        
        @self.app.on_message(filters.command("join") & filters.group)
        async def join_command(client: Client, message: Message):
            await self.join_voice_chat(message)
        
        @self.app.on_message(filters.command("leave") & filters.group)
        async def leave_command(client: Client, message: Message):
            await self.leave_voice_chat(message)
        
        # Handle mentions with music keywords (natural language)
        @self.app.on_message(filters.group & filters.mentioned & filters.incoming)
        async def on_mention(client: Client, message: Message):
            await self.handle_music_mention(client, message)
        
        # Stream ended callback - automatically play next song
        @self.call_py.on_stream_end()
        async def on_stream_end(client, update):
            chat_id = update.chat_id
            await self.play_next_in_queue(chat_id)
        
        # Start the client
        logger.info("Bot is running and monitoring your personal DMs...")
        logger.info(f"Auto-reply message: {self.auto_reply_message[:100]}...")
        logger.info(f"Cooldown period: {self.reply_cooldown_hours} hours per user")
        
        # Use asyncio approach instead of run() to avoid signal handling issues in threads
        async def start_and_idle():
            await self.app.start()
            await self.call_py.start()
            logger.info("✅ Personal account bot started successfully!")
            logger.info("✅ PyTgCalls music bot started successfully!")
            logger.info("🎵 Music commands: /play, /pause, /resume, /skip, /stop, /queue, /join, /leave")
            logger.info("🎤 Mention support: Tag bot + 'play <song name>' in groups")
            # Keep running without signal handlers (which don't work in threads)
            while True:
                await asyncio.sleep(1)
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(start_and_idle())
        except KeyboardInterrupt:
            logger.info("Stopping personal account bot...")
            loop.run_until_complete(self.app.stop())
        except EOFError as e:
            logger.warning("⚠️  Session file needs re-authentication (EOF error)")
            logger.warning("Personal bot will be skipped - session needs to be regenerated")
            logger.warning("Run 'python quick_auth.py' locally to create new session")
        except Exception as e:
            logger.error(f"Error in personal bot: {e}")
            try:
                loop.run_until_complete(self.app.stop())
            except:
                pass

if __name__ == '__main__':
    try:
        bot = PersonalAccountBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise
