# 🚀 Music Bot - Quick Start (हिंदी में)

## ✅ सब कुछ तैयार है!

मैंने सब fix कर दिया है:
- ✅ FFmpeg installed
- ✅ Pyrogram installed  
- ✅ PyTgCalls installed
- ✅ yt-dlp installed
- ✅ Music bot code fixed
- ✅ Old session deleted

---

## 🔐 Step 1: Login करो (बहुत आसान!)

### Replit Shell में ये command चलाओ:

```bash
python3 simple_login.py
```

### क्या होगा:

1. **Phone Number** पूछेगा → अपना number डालो with country code
   - Example: `+919876543210`

2. **OTP** Telegram पे आएगा → वो OTP enter करो

3. **Password** (अगर 2FA enabled है) → अपना password डालो

4. ✅ **हो गया!** Session file `my_personal_account.session` बन गई

---

## ⚠️ Important: Secrets Set करो

**Replit Secrets** में ये 2 चीजें होनी चाहिए:

1. `TELEGRAM_API_ID` → Example: `12345678`
2. `TELEGRAM_API_HASH` → Example: `0123456789abcdef0123456789abcdef`

### कहाँ से मिलेंगे?
👉 https://my.telegram.org/apps पे जाओ
- अपने phone number से login करो
- "Create new application" button दबाओ
- API ID और API Hash copy करो
- Replit Secrets में add करो

---

## 🎵 Step 2: Music Commands (Groups में)

Bot को किसी भी Telegram group में add करो और ये commands use करो:

### Commands:
```
/play Kesariya          → Song bajao
/pause                  → Music pause करो
/resume                 → Music resume करो  
/skip                   → Next song
/stop                   → Music band करो
/queue                  → Current queue dekho
/join                   → Voice chat में join करो
/leave                  → Voice chat से niklo
```

### Natural Language (Mention):
```
@YourBotUsername play Arijit Singh songs
@YourBotUsername bajao Kesariya
@YourBotUsername chalao tum hi ho
```

---

## 🚀 Step 3: Bot चलाओ

### Local Testing (Replit पे):
```bash
python3 start_both_bots.py
```

### Render Deployment:
Session file git में commit करके push करो:
```bash
git add my_personal_account.session
git commit -m "Added Pyrogram session for music bot"
git push
```

Render automatically redeploy कर देगा! ✅

---

## 🧪 Test करो

Dependencies test करने के लिए:
```bash
python3 test_music_setup.py
```

---

## ❓ Errors?

### "Session needs re-authentication"
```bash
python3 simple_login.py
```
फिर से login करो

### "TELEGRAM_API_ID not found"
Replit Secrets में add करो (ऊपर देखो)

### "No active group call"
1. Group में voice chat start करो
2. Phir `/join` command use करो
3. फिर `/play <song>` use करो

---

## 🎉 Done!

अब आप music play कर सकते हो! Enjoy! 🎵

Questions? Check: `MUSIC_BOT_SETUP_GUIDE.md`
