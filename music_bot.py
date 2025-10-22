#!/usr/bin/env python3
import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import HighQualityAudio
from pytgcalls.exceptions import NoActiveGroupCall, AlreadyJoinedError
import yt_dlp
from collections import deque
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class MusicBot:
    def __init__(self):
        self.api_id = os.getenv('TELEGRAM_API_ID')
        self.api_hash = os.getenv('TELEGRAM_API_HASH')
        
        if not self.api_id or not self.api_hash:
            raise ValueError("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set!")
        
        # Initialize Pyrogram client using shared session file
        # Uses same session as personal bot: my_personal_account.session
        self.app = Client(
            "my_personal_account",
            api_id=int(self.api_id),
            api_hash=self.api_hash
        )
        
        # Initialize PyTgCalls
        self.call_py = PyTgCalls(self.app)
        
        # Queue management
        self.queues = {}  # {chat_id: deque([{title, url, requester}])}
        self.current_playing = {}  # {chat_id: {title, url, requester}}
        
        # Register handlers
        self.register_handlers()
    
    def register_handlers(self):
        """Register command handlers"""
        
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
        
        # Stream ended callback
        @self.call_py.on_stream_end()
        async def on_stream_end(client, update):
            chat_id = update.chat_id
            await self.play_next_in_queue(chat_id)
    
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
        
        # Create downloads directory if it doesn't exist
        os.makedirs('downloads', exist_ok=True)
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Search or get direct URL
                if not query.startswith('http'):
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                else:
                    info = ydl.extract_info(query, download=False)
                
                # Download the audio
                file_path = ydl.prepare_filename(info)
                file_path = file_path.rsplit('.', 1)[0] + '.mp3'
                
                # Download if not exists
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
            # Create a silent audio file if it doesn't exist
            silence_file = 'downloads/silence.mp3'
            if not os.path.exists(silence_file):
                os.makedirs('downloads', exist_ok=True)
                # Create 1 second of silence using ffmpeg
                import subprocess
                subprocess.run([
                    'ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
                    '-t', '1', '-q:a', '9', '-acodec', 'libmp3lame', silence_file,
                    '-y'
                ], check=True, capture_output=True)
            
            await self.call_py.join_group_call(
                chat_id,
                AudioPiped(silence_file),
                stream_type=StreamType().pulse_stream
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
            
            # Clear queue
            if chat_id in self.queues:
                self.queues[chat_id].clear()
            if chat_id in self.current_playing:
                del self.current_playing[chat_id]
            
            await message.reply_text("✅ Voice chat se nikal gaya!")
        except Exception as e:
            logger.error(f"Error leaving voice chat: {e}")
            await message.reply_text(f"❌ Voice chat se nikal nahi paya: {str(e)}")
    
    async def play_music(self, message: Message):
        """Play music in voice chat"""
        chat_id = message.chat.id
        
        # Get song query
        query = message.text.split(maxsplit=1)
        if len(query) < 2:
            await message.reply_text("❌ Song ka naam ya link bataiye!\n\nExample: /play Arijit Singh songs")
            return
        
        query = query[1]
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
                AudioPiped(file_path, HighQualityAudio())
            )
        except NoActiveGroupCall:
            # Join voice chat first
            await self.call_py.join_group_call(
                chat_id,
                AudioPiped(file_path, HighQualityAudio()),
                stream_type=StreamType().pulse_stream
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
            
            # Clear queue
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
        
        # Current playing
        if chat_id in self.current_playing:
            current = self.current_playing[chat_id]
            response += f"▶️ **Now Playing:**\n{current['title']}\n👤 {current['requester']}\n\n"
        
        # Queue
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
            # No more songs
            if chat_id in self.current_playing:
                del self.current_playing[chat_id]
            await self.call_py.leave_group_call(chat_id)
            return
        
        # Get next song
        next_song = self.queues[chat_id].popleft()
        self.current_playing[chat_id] = next_song
        
        # Play it
        await self.start_streaming(chat_id, next_song['file_path'])
    
    async def start(self):
        """Start the music bot"""
        await self.app.start()
        await self.call_py.start()
        logger.info("🎵 Music bot started successfully!")
    
    async def stop(self):
        """Stop the music bot"""
        await self.call_py.stop()
        await self.app.stop()
        logger.info("🎵 Music bot stopped!")


async def main():
    """Main function to run music bot"""
    try:
        music_bot = MusicBot()
        await music_bot.start()
        
        # Keep the bot running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Error in music bot: {e}")
    finally:
        if 'music_bot' in locals():
            await music_bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
