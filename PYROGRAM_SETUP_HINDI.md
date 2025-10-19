# Pyrogram Personal Bot Setup Guide (हिंदी में)

## ⚠️ बहुत जरूरी बात (IMPORTANT)

**Pyrogram bot को चलाने के लिए आपको एक बार phone number और OTP देना ही होगा।**
इसके बिना कोई रास्ता नहीं है क्योंकि यह आपके personal Telegram account को use करता है।

## 🎯 अच्छी खबर (Good News)

आपके पास पहले से **`my_personal_account.session`** file है! 
**मतलब आपने पहले authenticate कर लिया था।** 
अब दोबारा OTP की जरूरत नहीं है! ✅

## 🔧 क्या Fix किया गया है

### 1. Threading Error Fix
- **पुरानी समस्या**: "signal only works in main thread" error
- **Fix**: Code को update किया गया है ताकि thread में चले बिना signal issues के
- **स्टेटस**: ✅ Fixed

### 2. Bot Conflict Error
**समस्या**: "Conflict: terminated by other getUpdates request"

यह error तब आता है जब:
- Bot एक ही time पर 2 जगह चल रहा है (Render + Replit)
- Telegram allows केवल 1 bot instance at a time

**समाधान**: 
- एक समय पर सिर्फ 1 जगह bot चलाएं
- अगर Render पर चल रहा है, तो वहां stop करें
- अगर Replit पर चलाना है, तो Render को बंद करें

## 📋 Pyrogram Bot चलाने के लिए Required Environment Variables

```bash
# जरूरी Variables (Must have):
TELEGRAM_API_ID=your_api_id          # https://my.telegram.org/apps से मिलेगा
TELEGRAM_API_HASH=your_api_hash      # https://my.telegram.org/apps से मिलेगा

# Main bot के लिए (Already set होंगे):
TELEGRAM_BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
ADMIN_ID=your_telegram_user_id

# Optional (customize करने के लिए):
USE_AI_RESPONSES=true                # AI replies enable/disable
USE_KEYWORDS=true                    # Keyword responses enable/disable
USE_KNOWLEDGE_BASE=true              # Knowledge base use करें
REPLY_COOLDOWN_HOURS=0               # Users को कितने घंटे बाद reply (0 = हर बार)
AUTO_REPLY_MESSAGE=आपका custom message
```

## 🚀 कैसे चलाएं

### पहली बार Authentication (अगर session file नहीं है):

```bash
# 1. Local machine पर चलाएं (Replit पर नहीं)
python quick_auth.py

# 2. Phone number डालें (with country code): +919876543210
# 3. OTP code डालें जो Telegram ने भेजा
# 4. Successfully login होने पर "my_personal_account.session" file बनेगी
# 5. इस file को Replit में upload करें
```

### अगर Session File Already Exists:

आपके पास पहले से session file है, तो सीधे bot चलाएं:

```bash
# दोनों bots एक साथ चलाने के लिए:
python start_both_bots.py

# या सिर्फ personal bot:
python personal_account_autoreply.py

# या सिर्फ main bot:
python main.py
```

## ⚡ Replit पर Setup

### Step 1: Environment Variables Set करें

Replit Secrets में add करें:
- `TELEGRAM_API_ID` 
- `TELEGRAM_API_HASH`

### Step 2: Session File Upload करें

अगर नहीं है तो:
1. अपने local computer पर `quick_auth.py` चलाएं
2. Phone number + OTP से login करें  
3. बनी हुई `my_personal_account.session` file को Replit में upload करें

### Step 3: Python Dependencies Install करें

```bash
pip install -r requirements.txt
```

### Step 4: Bot Run करें

```bash
python start_both_bots.py
```

## 🔍 Troubleshooting

### Error: "TELEGRAM_API_ID or TELEGRAM_API_HASH not set"
**Fix**: Replit Secrets में ये variables add करें

### Error: "Session file not found"
**Fix**: 
1. Local पर `quick_auth.py` चलाएं
2. Session file upload करें Replit में

### Error: "Conflict: terminated by other getUpdates request"
**Fix**: 
- Bot को एक ही जगह चलाएं (Render या Replit, दोनों नहीं)
- Render deployment को stop करें अगर Replit पर चलाना है

### Error: "signal only works in main thread"
**Fix**: ✅ Already fixed! Updated code use करें।

## 💡 Tips

1. **Session File बहुत Important है**: इसे backup रखें, यह आपका login है
2. **API Credentials Safe रखें**: ये आपके personal account की keys हैं
3. **एक साथ दोनों bots**: `start_both_bots.py` use करें
4. **Testing के लिए**: पहले सिर्फ main bot चलाकर देखें, फिर personal bot add करें

## 📞 Telegram API Keys कहाँ से लें?

1. https://my.telegram.org/apps पर जाएं
2. अपने phone number से login करें
3. "Create new application" पर click करें
4. App title और short name डालें
5. आपको `api_id` और `api_hash` मिलेंगे
6. इन्हें Replit Secrets में add करें

---

## ✅ अब क्या करना है?

1. ✅ Code already fixed है
2. ⏳ TELEGRAM_API_ID और TELEGRAM_API_HASH add करें (अगर नहीं है)
3. ⏳ Session file check करें (already है तो OK)
4. ⏳ सिर्फ एक जगह bot चलाएं (Render या Replit)
5. ⏳ Test करें

**अगर ये सब set है, तो bot अब बिना error के चलेगा!** 🎉
