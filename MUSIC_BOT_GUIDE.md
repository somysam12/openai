# 🎵 Music Bot Guide - Voice Chat Music Player

## 🎉 **UPDATED: Music Now Integrated into Personal Bot!**

Music playback ab **Personal Account Bot** (`personal_account_autoreply.py`) mein integrate ho gaya hai! Ab alag se music bot run karne ki zarurat nahi hai.

### What Changed?
- ✅ Music features ab personal bot mein built-in hain
- ✅ Slash commands `/play`, `/pause`, etc. kaam karte hain
- ✅ **NEW:** Natural language support - Tag karke bolo: `@username play Kesariya`
- ✅ Ek hi session file, ek hi bot, sabkuch automated

## Overview
Aapke bot mein ab music playing feature add ho gaya hai! Ye bot Telegram group voice chats mein songs play kar sakta hai YouTube se search karke.

## 🎯 Features
- ✅ YouTube se songs search aur play karna
- ✅ Queue management (multiple songs)
- ✅ Pause, resume, skip controls
- ✅ Voice chat mein automatic join/leave
- ✅ Real-time song playing status
- ✅ **NEW:** Natural language mentions support
- ✅ **NEW:** Tag bot + say "play <song>" in plain text

---

## 📋 Requirements

### 1. Telegram API Credentials
Music bot ko chalane ke liye aapko ye environment variables set karne honge:

```bash
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

**Kaise milenge?**
1. https://my.telegram.org/apps pe jao
2. Login karo apne Telegram account se
3. Create new application
4. API ID aur API Hash copy karo

### 2. Session File
Music bot ko ek session file bhi chahiye:
- File name: `my_personal_account.session`
- Yeh file `quick_auth.py` run karke banati hai

**Session kaise banaye?**
```bash
python quick_auth.py
```

### 3. Group Permissions
Bot ko group mein ye permissions chahiye:
- ✅ Admin hona chahiye
- ✅ "Manage Voice Chats" permission
- ✅ Voice chat join karne ki permission

---

## 🎮 Commands

### Basic Commands

#### `/play <song name or link>`
YouTube se song search karke play karta hai.

**Examples:**
```
/play Arijit Singh songs
/play Kesariya Tera Ishq Hai Piya
/play https://www.youtube.com/watch?v=VIDEO_ID
```

#### `/pause`
Current song ko pause kar deta hai.

#### `/resume`
Paused song ko dubara chalu karta hai.

#### `/skip`
Current song skip karke next song play karta hai.

#### `/stop`
Music band kar deta hai aur puri queue clear kar deta hai.

#### `/queue`
Current queue dikhata hai (jo songs play hone wale hain).

---

### 🎤 Natural Language Mentions (NEW!)

Ab aap bot ko tag karke plain text mein bhi song request kar sakte ho!

**Format:**
```
@username play <song name>
@username bajao <song name>
@username chalao <song name>
```

**Examples:**
```
@YourBotUsername play Kesariya
@YourBotUsername bajao last christmas
Hey @YourBotUsername chalao Arijit Singh songs
@YourBotUsername song play karo tum hi ho
```

**Supported Keywords:**
- play, bajao, chalao, song, gaana, music

Bot automatically detect karega keywords aur song name extract karega!

---

### Voice Chat Controls

#### `/join`
Bot ko voice chat mein join karata hai.

#### `/leave`
Bot ko voice chat se nikal deta hai aur queue clear kar deta hai.

---

## 🚀 Usage Examples

### Example 1: Simple Play
```
User: /play Tum Hi Ho
Bot: 🔍 Song search kar raha hoon...
Bot: 🎶 Ab bajega:
     🎵 Tum Hi Ho - Aashiqui 2
     👤 Requested by: Your Name
```

### Example 2: Queue Multiple Songs
```
User: /play Kesariya
Bot: 🎶 Ab bajega: Kesariya - Brahmastra

User: /play Apna Bana Le
Bot: ✅ Queue mein add kar diya!
     🎵 Apna Bana Le - Bhediya
     📍 Position: #1
```

### Example 3: Check Queue
```
User: /queue
Bot: 🎵 Current Queue:
     
     ▶️ Now Playing:
     Kesariya - Brahmastra
     👤 User1
     
     📝 Up Next:
     1. Apna Bana Le - Bhediya
        👤 User2
     2. Chaleya - Jawan
        👤 User3
```

---

## ⚙️ How It Works

### Architecture
```
┌─────────────────┐
│  Telegram Group │
│   Voice Chat    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Music Bot     │
│  (PyTgCalls)    │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌──────────┐
│YouTube │ │  Queue   │
│ yt-dlp │ │ Manager  │
└────────┘ └──────────┘
```

### Process Flow
1. User sends `/play` command with song name
2. Bot searches YouTube using yt-dlp
3. Downloads audio (MP3 format)
4. Joins voice chat if not already in
5. Streams audio to voice chat
6. When song ends, plays next from queue
7. Leaves voice chat when queue is empty

---

## 🔧 Deployment

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run music bot standalone
python music_bot.py

# Or run with all bots
python start_both_bots.py
```

### Render.com Deployment
Music bot automatically start hoga agar ye environment variables set hain:
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- Session file (`my_personal_account.session`) git mein committed hai

---

## 🐛 Troubleshooting

### Bot voice chat join nahi kar pa raha
**Solution:**
1. Check karo bot admin hai ya nahi
2. "Manage Voice Chats" permission diya hai ya nahi
3. Voice chat active hai ya nahi

### Song download nahi ho raha
**Solution:**
1. Internet connection check karo
2. YouTube link valid hai ya nahi check karo
3. Disk space available hai ya nahi

### "SESSION FILE NOT FOUND" error
**Solution:**
```bash
python quick_auth.py
```
Run karke session file banao aur git mein commit karo.

### Music quality kharab hai
**Solution:**
Music bot `HighQualityAudio()` use karta hai by default. Agar aur improve karna hai:
1. `music_bot.py` file open karo
2. Line 227 pe `HighQualityAudio()` ko customize karo

---

## 📊 Queue Management

### How Queue Works
- First song immediately play hoti hai
- Baaki songs queue mein add ho jaati hain
- Jab ek song khatam hoti hai, automatically next play hoti hai
- Queue maximum 10 songs display karti hai `/queue` command pe

### Queue Limits
- Default: Unlimited queue size
- Agar limit lagana hai to `music_bot.py` mein `MAX_QUEUE_SIZE` variable add karo

---

## 🎛️ Advanced Configuration

### Custom Audio Quality
`music_bot.py` mein line 227:
```python
AudioPiped(file_path, HighQualityAudio())
```

### Custom Download Location
`music_bot.py` mein line 93:
```python
'outtmpl': 'downloads/%(title)s.%(ext)s',
```

### Custom Audio Format
`music_bot.py` mein line 100:
```python
'preferredcodec': 'mp3',
'preferredquality': '192',
```

---

## 📝 Notes

1. **FFmpeg Required:** System mein FFmpeg install hona chahiye (Replit pe already hai)
2. **Storage:** Songs `downloads/` folder mein save hote hain
3. **Cleanup:** Purane songs manually delete karne padenge storage bachane ke liye
4. **Concurrent Groups:** Music bot multiple groups mein simultaneously music play kar sakta hai
5. **Pyrogram Session:** Music bot aur Personal Account Bot same session file use karte hain

---

## 🆘 Support

Agar koi problem hai ya questions hain:
1. Logs check karo: Render Dashboard → Logs
2. Error messages padho carefully
3. Environment variables double-check karo
4. Session file valid hai ya nahi verify karo

---

**Happy Listening! 🎵**
