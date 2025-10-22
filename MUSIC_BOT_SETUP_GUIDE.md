# 🎵 Music Bot Setup Guide (Hindi + English)

## ✅ Dependencies Fixed!

Sab kuch install ho gaya hai:
- ✅ FFmpeg 7.1.1 installed
- ✅ Pyrogram 2.0.106 installed  
- ✅ PyTgCalls 2.2.8 installed
- ✅ yt-dlp 2025.10.14 installed
- ✅ All Python dependencies working

---

## 🔐 Step 1: Login with Pyrogram

### Replit Shell mein ye command run karo:

```bash
python3 simple_login.py
```

### Kya hoga:
1. Apna phone number enter karo (with country code): **+919876543210**
2. Telegram pe OTP aayega - enter karo
3. Agar 2FA enabled hai toh password enter karo
4. ✅ Session file ban jayega: `my_personal_account.session`

### Important:
- Make sure `TELEGRAM_API_ID` aur `TELEGRAM_API_HASH` Replit Secrets mein set hon
- Ye credentials milenge: https://my.telegram.org/apps

---

## 🎵 Step 2: Music Commands (Groups mein)

Bot ko kisi bhi Telegram group mein add karo aur ye commands use karo:

### Slash Commands:
- `/play <song name>` - Song bajao (YouTube search)
- `/pause` - Music pause karo
- `/resume` - Music resume karo  
- `/skip` - Next song
- `/stop` - Music band karo aur queue clear karo
- `/queue` - Current queue dekho
- `/join` - Voice chat mein join karo
- `/leave` - Voice chat se niklo

### Natural Language (Mention):
Group mein bot ko mention karo aur plain text mein bolo:

```
@username play Kesariya
@username bajao Arijit Singh songs
@username chalao tum hi ho
@username song laga de Kishore Kumar
```

Keywords jo kaam karti hain: **play, bajao, chalao, song, gaana, music**

---

## 🚀 Step 3: Bot Chalao

### Local Testing (Replit pe):
```bash
python3 start_both_bots.py
```

### Render Deployment:
1. Make sure session file git mein commit ho
2. Git push karo
3. Render automatically redeploy karega
4. Environment variables check karo:
   - `TELEGRAM_BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `ADMIN_ID`
   - `TELEGRAM_API_ID` (for music)
   - `TELEGRAM_API_HASH` (for music)

---

## 🔍 Test Music Setup

Dependencies test karne ke liye:

```bash
python3 test_music_setup.py
```

Ye check karega:
- FFmpeg working hai ya nahi
- Pyrogram installed hai
- PyTgCalls working hai
- yt-dlp working hai

---

## ❌ Troubleshooting

### Error: "Session file needs re-authentication"
```bash
python3 simple_login.py
```
Naya session banao

### Error: "FFmpeg not found"
Already installed! Check karo:
```bash
ffmpeg -version
```

### Error: "No active group call"
1. Group voice chat start karo
2. Phir `/play` command use karo
3. Ya pehle `/join` use karo

### Error: "Song nahi mila"
- Internet connection check karo
- Song ka naam sahi spell karo
- Ya YouTube link directly use karo: `/play https://youtube.com/watch?v=...`

---

## 📝 Features

### ✅ Working:
- YouTube search aur download
- High quality MP3 conversion (192kbps)
- Queue management (multiple songs)
- Auto next-song playback
- Pause/Resume/Skip controls
- Natural language mention support
- Multiple groups simultaneously

### ⚠️ Limitations:
- Session file local computer pe hi ban sakti hai (Replit shell mein bhi ban sakti hai!)
- Voice chat pehle se active hona chahiye (ya `/join` use karo)
- Downloaded songs `downloads/` folder mein cache hote hain

---

## 🎉 Ready!

Ab aap:
1. ✅ Login kar sakte ho: `python3 simple_login.py`
2. ✅ Bot chala sakte ho: `python3 start_both_bots.py`
3. ✅ Groups mein music play kar sakte ho: `/play <song>`
4. ✅ Natural mentions use kar sakte ho: `@bot play kesariya`

Enjoy! 🎵🎶
