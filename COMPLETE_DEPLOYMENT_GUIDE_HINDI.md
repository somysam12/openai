# 🚀 Complete Deployment Guide - Hindi/Hinglish

## 📌 OpenAI API Key Information (2025)

### ✅ Free API Key Details:
- **Free Credits**: $5 (naye account ke liye)
- **Validity**: 3 months (90 days)
- **Important**: API key kabhi expire nahi hoti, sirf free credits 3 months baad khatam ho jaate hain

### 🔄 Token Limit & Reset:
- **Daily Limit**: 2.5M tokens/day per key (GPT-4o-mini model ke liye)
- **Reset Time**: Har 24 hours mein automatic reset (daily)
- **Best Model**: `gpt-4o-mini` use karo - sabse zyada cost-effective

### 💡 Important Points:
1. Token limit **daily reset** hota hai (monthly nahi)
2. API key kabhi expire nahi hoti
3. Free credits khatam hone ke baad billing add karna padega
4. Multiple keys se rotation karke aap poore din unlimited usage kar sakte ho!

---

## 🤖 Pyrogram Bot - New Telegram ID Se Connect Karna

### Step 1: Purane Session Ko Delete Karo
```bash
rm my_personal_account.session
```

### Step 2: Naya Session Generate Karo
```bash
python quick_auth.py
```

Yeh script aapse puchega:
1. **Phone Number**: Jis Telegram account se connect karna hai (with country code, e.g., +919876543210)
2. **OTP Code**: Telegram se aayega
3. **2FA Password**: Agar enabled hai toh

### Step 3: Session File Upload Karo
- Authentication successful hone ke baad `my_personal_account.session` file ban jayegi
- Yeh file Render pe deploy karte waqt automatically upload ho jayegi (already git mein committed hai)

### Environment Variables Required:
```
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

**Kaise milenge yeh credentials?**
1. https://my.telegram.org/apps pe jao
2. Login karo apne Telegram account se
3. Create new application
4. API ID aur API Hash copy karo

---

## 🌐 Render.com Deployment - Dono Bots Ek Saath

### ✅ Already Configured Features:
- **18 API Keys Rotation**: ✅ Dono bots automatically rotate karte hain
- **Token Tracking**: ✅ Real-time monitoring with auto-reset
- **Shared Database**: ✅ Dono bots ek hi database use karte hain
- **Health Check**: ✅ Flask server already configured
- **Combined Runner**: ✅ `start_both_bots.py` dono ko ek saath chalata hai

### 📝 Deployment Steps:

#### 1. GitHub Pe Code Push Karo
```bash
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

#### 2. Render Pe Web Service Banao

1. **Render.com** pe jao aur login karo
2. Click **"New +"** → **"Web Service"**
3. GitHub repo connect karo

#### 3. Configuration Settings:

**Basic Settings:**
- **Name**: `telegram-ai-bot`
- **Region**: Closest region select karo
- **Branch**: `main`
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python start_both_bots.py` ⚠️ (Important!)

**Instance Type:**
- Select **"Free"** tier

#### 4. Environment Variables (Critical!)

Click **"Advanced"** aur yeh sab add karo:

```
# Main Bot Credentials
TELEGRAM_BOT_TOKEN=8267153211:AAH81NuZHAbfU6U1htDTzmGSE_zNvPeNAzU
ADMIN_ID=5952524867

# Pyrogram Bot Credentials (Optional - sirf agar userbot bhi chahiye)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890

# Multiple OpenAI API Keys (Sabhi 18 keys add karo!)
OPENAI_API_KEY_1=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_2=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_3=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_4=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_5=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_6=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_7=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_8=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_9=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_10=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_11=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_12=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_13=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_14=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_15=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_16=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_17=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_18=sk-proj-xxxxxxxxxxxx
```

#### 5. Deploy Button Click Karo!

- **"Create Web Service"** click karo
- Render build karega aur deploy karega
- **"Deploy succeeded"** message ka wait karo
- Done! ✅ Dono bots 24/7 live ho gaye!

---

## 🔄 API Key Rotation System (Already Working!)

### Kaise Kaam Karta Hai:

1. **Automatic Detection**:
   - Rate limit hit (429 error)
   - Account deactivated (401 error)
   - Invalid key (403 error)
   - Koi bhi API error

2. **Instant Rotation**:
   ```
   Key #1 fails → Instantly switch to Key #2
   Key #2 fails → Instantly switch to Key #3
   ... aur aage
   Key #18 ke baad → Key #1 pe wapas
   ```

3. **Shared Tracking**:
   - Dono bots same `api_key_stats` table use karte hain
   - Token usage real-time track hota hai
   - Daily auto-reset (24 hours)

4. **Admin Dashboard**:
   - `/start` command se admin panel kholo
   - "🔑 API Key Stats" button click karo
   - Sabhi 18 keys ka status dekho:
     - 🟢 FRESH/ACTIVE
     - 🟡 LOW (80% used)
     - 🔴 EXHAUSTED (limit crossed)

### Daily Token Calculation:
```
18 keys × 2.5M tokens = 45M tokens per day! 🚀
```

### Reset Time:
- Har key ka apna 24-hour timer hai
- 24 hours baad automatic reset
- Admin panel mein countdown timer dikhega

---

## 🎯 Testing After Deployment

### Main Bot Test:
1. Telegram pe apne bot ko search karo
2. `/start` command bhejo
3. Admin panel dikhe toh ✅ working!
4. Kuch message bhejo, AI response aana chahiye

### Pyrogram Bot Test:
1. Apne personal account se kisi ko DM karo
2. Bot automatically reply karega (if configured)
3. Check `personal_autoreplies.db` for tracking

### API Rotation Test:
1. Admin panel mein jao
2. "🔑 API Key Stats" click karo
3. Dekho ki keys rotate ho rahi hain ya nahi
4. Token count badh raha hai ya nahi

---

## ⚠️ Common Issues & Solutions

### Issue 1: Personal Bot Start Nahi Ho Raha
**Solution:**
- Check `TELEGRAM_API_ID` aur `TELEGRAM_API_HASH` set hain ya nahi
- Session file (`my_personal_account.session`) upload hua hai ya nahi
- Logs check karo: "Personal bot will NOT start" message aata hai

### Issue 2: API Keys Rotate Nahi Ho Rahe
**Solution:**
- Sabhi keys correct format mein hain (`sk-proj-...`)
- Environment variables properly set hain
- Logs mein "Rotated to API key #X" message aana chahiye

### Issue 3: Database Issues
**Solution:**
- Free tier pe SQLite persistence issue ho sakta hai
- Restart pe data reset ho sakta hai
- Production mein PostgreSQL use karo (recommended)

### Issue 4: Health Check Failing
**Solution:**
- Already configured hai `/health` endpoint
- Port 10000 automatically set hoga
- Render logs check karo agar issue hai

---

## 📊 What's Already Implemented:

### ✅ Main Bot Features:
- Multi-language AI chat (Hindi, English, Hinglish)
- Knowledge base system
- Admin panel with buttons
- User management & blocking
- Broadcast messages
- Chat history tracking
- Token usage monitoring
- 18 API keys rotation

### ✅ Pyrogram Bot Features:
- Personal account auto-reply
- Same knowledge base
- Same API key pool (18 keys)
- Shared token tracking
- Rate limiting
- Conversation history

### ✅ Shared Features:
- Single SQLite database
- Unified API key rotation
- Real-time token tracking
- Daily auto-reset
- Admin dashboard visibility

---

## 💰 Cost Breakdown

### Free Tier (Current):
- **Render Hosting**: Free (750 hours/month = 24/7 ✅)
- **OpenAI API**: 18 keys × $5 = $90 free credits
- **Total Cost**: $0 for 3 months! 🎉

### After Free Credits Expire:
- **OpenAI API**: ~$0.0001 per 1K tokens (GPT-4o-mini)
- **Estimated**: $3-10/month depending on usage
- **Render**: Still free!

### Recommended for Production:
- **Render Paid**: $7/month (persistent storage)
- **OpenAI Paid**: ~$10/month (usage-based)
- **Total**: ~$17/month for reliable service

---

## 🚀 Quick Commands Reference

### Deployment:
```bash
# Code push karo
git add .
git commit -m "Deploy to Render"
git push origin main

# Render automatically detect karega aur redeploy karega
```

### New Pyrogram Session:
```bash
python quick_auth.py
```

### Local Testing:
```bash
# Dono bots ek saath
python start_both_bots.py

# Sirf main bot
python main.py

# Sirf pyrogram bot
python personal_account_autoreply.py
```

---

## 📞 Need Help?

### Logs Check Karne Ke Liye:
1. Render Dashboard → Your Service
2. "Logs" tab click karo
3. Real-time logs dikhenge
4. Errors red color mein honge

### Common Log Messages:
```
✅ "Loaded 18 API keys for rotation"
✅ "Main bot initialized successfully"
✅ "Personal bot initialized successfully"
✅ "Flask health check server started"
🔄 "Rotated to API key #X"
⚠️ "Rate limit hit on API key #X"
```

---

## 🎉 Final Checklist

Before Deployment:
- [ ] GitHub repo ready
- [ ] All 18 API keys copied
- [ ] TELEGRAM_BOT_TOKEN ready
- [ ] ADMIN_ID noted
- [ ] TELEGRAM_API_ID & TELEGRAM_API_HASH (optional)
- [ ] Session file generated (if using Pyrogram)

After Deployment:
- [ ] Logs mein "Deploy succeeded"
- [ ] Bot responds to /start
- [ ] Admin panel working
- [ ] API keys rotating
- [ ] Token tracking active
- [ ] Personal bot working (if enabled)

---

**Congratulations!** 🎊 
Aapke dono bots ab 24/7 live hain with automatic API key rotation!

**Total Power**: 18 keys × 2.5M tokens = 45 Million tokens per day! 🚀
