# 🚀 Render Deployment Guide - Dono Bots Ek Saath (EASY WAY)

## 📋 Prerequisites (Pehle Yeh Taiyar Karo)

### 1. API Keys/Tokens Required:
- ✅ `TELEGRAM_BOT_TOKEN` (BotFather se)
- ✅ `OPENAI_API_KEY` (OpenAI se)
- ✅ `ADMIN_ID` (Apna Telegram User ID)
- ✅ `TELEGRAM_API_ID` (my.telegram.org/apps se)
- ✅ `TELEGRAM_API_HASH` (my.telegram.org/apps se)

### 2. Session File (Personal Account Bot ke liye)

**⚠️ IMPORTANT:** Pyrogram personal bot ke liye **pehle login karna ZAROORI hai**

**Option A: Replit pe Login Karo (Recommended)**
```bash
python quick_auth.py
```
- Phone number enter karo (+91XXXXXXXXXX)
- Telegram se aaya code enter karo
- 2FA password (agar hai)
- ✅ `my_personal_account.session` file ban jayegi

**Option B: Bina Personal Bot ke Deploy**
- Agar personal account bot nahi chahiye, to sirf `main.py` deploy karo

---

## 🎯 Step-by-Step Deployment

### Step 1: GitHub Repository Setup

1. **GitHub pe jao** → New Repository banao
   - Name: `telegram-ai-bot`
   - Privacy: **Private** (session file ke liye)

2. **Replit se Code Push Karo:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/telegram-ai-bot.git
   git push -u origin main
   ```

   **Note:** Agar session file hai to wo bhi push ho jayegi (needed for deployment)

---

### Step 2: Render.com pe Web Service Banao

1. **Render.com** pe jao → **Sign Up/Login**

2. **Dashboard** pe → **"New +"** button click → **"Web Service"** select karo

3. **Connect GitHub:**
   - "Connect a repository" → GitHub authorize karo
   - Apna `telegram-ai-bot` repo select karo

---

### Step 3: Configure Web Service

**Basic Configuration:**

| Field | Value |
|-------|-------|
| **Name** | `telegram-ai-bot` |
| **Region** | Singapore / Frankfurt (closest) |
| **Branch** | `main` |
| **Root Directory** | (leave blank) |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python main.py` |

**Instance Type:**
- ✅ Select **"Free"** (0$/month)

---

### Step 4: Environment Variables Add Karo

**"Advanced"** section expand karo → **"Add Environment Variable"** click karo

**Main Bot ke liye:**
```
TELEGRAM_BOT_TOKEN = your_bot_token_here
OPENAI_API_KEY = your_openai_key_here
ADMIN_ID = your_telegram_user_id
```

**Personal Bot ke liye (Optional - agar use kar rahe ho):**
```
TELEGRAM_API_ID = your_api_id
TELEGRAM_API_HASH = your_api_hash
USE_AI_RESPONSES = true
USE_KEYWORDS = true
REPLY_COOLDOWN_HOURS = 0
```

**Multiple OpenAI Keys (Optional - for rotation):**
```
OPENAI_API_KEY_1 = sk-proj-...
OPENAI_API_KEY_2 = sk-proj-...
OPENAI_API_KEY_3 = sk-proj-...
```

---

### Step 5: Deploy!

1. **"Create Web Service"** button click karo
2. Render build start karega (2-3 minutes lagenge)
3. **"Deploy succeeded ✅"** dikhe to done!

---

## ✅ Deployment Check Karo

### Test Main Bot:
1. Telegram open karo
2. Apne bot ko search karo
3. `/start` bhejo
4. Admin panel khulna chahiye!

### Test Personal Bot (agar deploy kiya):
1. Kisi se apne personal account pe message bhejwao
2. Auto-reply aana chahiye

---

## 🔧 Dono Bots Ek Saath Run Karne Ke 2 Options

### **Option 1: Sirf Main Bot (Simple & Recommended)**

**Start Command:**
```
python main.py
```

**Pros:**
- ✅ Easy setup
- ✅ No session file needed
- ✅ Stable

**Cons:**
- ❌ Personal account bot nahi chalega

---

### **Option 2: Dono Bots Ek Saath (Advanced)**

**Pehle ek combined script banao** (ya existing use karo):

**File: `start_both_bots.py`**
```python
#!/usr/bin/env python3
import os
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_main_bot():
    """Run main Telegram bot"""
    try:
        from main import main
        logger.info("🤖 Starting Main Telegram Bot...")
        main()
    except Exception as e:
        logger.error(f"Main bot failed: {e}")

def run_personal_bot():
    """Run personal account bot"""
    try:
        # Check if session file exists
        if not os.path.exists('my_personal_account.session'):
            logger.warning("⚠️ Session file not found - Personal bot skipped")
            return
        
        from personal_account_autoreply import PersonalAccountBot
        logger.info("👤 Starting Personal Account Bot...")
        bot = PersonalAccountBot()
        bot.run()
    except Exception as e:
        logger.error(f"Personal bot failed: {e}")

if __name__ == '__main__':
    # Start personal bot in background thread
    personal_thread = threading.Thread(target=run_personal_bot, daemon=True)
    personal_thread.start()
    
    # Start main bot in foreground
    run_main_bot()
```

**Render Start Command:**
```
python start_both_bots.py
```

**Pros:**
- ✅ Dono bots chal rahe hain
- ✅ Ek hi service mein

**Cons:**
- ⚠️ Session file chahiye
- ⚠️ Thoda complex setup

---

## 🐛 Common Issues & Solutions

### Issue 1: "Build Failed"
**Solution:** 
- Check `requirements.txt` file exists
- Check Render logs for exact error

### Issue 2: "Bot not responding"
**Solution:**
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check Render logs tab
- Make sure bot is not running anywhere else

### Issue 3: "Personal bot not working"
**Solution:**
- Session file upload hua hai?
- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` correct hai?
- Session expire ho gaya ho sakta hai - re-authenticate karo

### Issue 4: "Database locked" errors
**Solution:**
- Free tier limitation
- Consider upgrading to paid plan ($7/month)
- Or migrate to PostgreSQL

---

## 💰 Render Pricing

**Free Tier:**
- ✅ 750 hours/month (24/7 for 31 days)
- ✅ Auto-sleep after 15 min inactivity
- ⚠️ Database may reset
- ⚠️ Limited resources

**Paid Tier ($7/month):**
- ✅ Always-on
- ✅ Persistent disk
- ✅ Better performance

**Recommendation:** Free tier test karo, agar sab theek hai to upgrade karo

---

## 📝 Quick Deployment Checklist

- [ ] GitHub account ready
- [ ] Render account banaya
- [ ] All API keys ready
- [ ] Session file banaya (for personal bot)
- [ ] Code GitHub pe push kiya
- [ ] Render web service create kiya
- [ ] Environment variables set kiye
- [ ] Deploy succeeded ✅
- [ ] Bot test kiya
- [ ] Working! 🎉

---

## 🎯 Recommended Approach

**Agar aap beginner ho:**
👉 **Sirf Main Bot deploy karo** (`python main.py`)
- Easy setup
- No complications
- Stable

**Agar experienced ho:**
👉 **Dono bots deploy karo** (`python start_both_bots.py`)
- More features
- Personal account automation
- Requires session management

---

## 📞 Help Needed?

Agar koi issue aaye:
1. Render → Logs tab check karo
2. Error message exactly note karo
3. Environment variables verify karo
4. Session file check karo (for personal bot)

---

**Good Luck! 🚀**
