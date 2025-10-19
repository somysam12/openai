# 🤖 Personal Account Bot - AI Integration Guide

## ✨ Features

Aapka personal account bot ab **exactly same logic** use karta hai jo aapka main bot use karta hai!

### 🎯 What's Included:

1. **🔑 Keywords** - Automatic keyword detection and instant replies
2. **🧠 AI Responses** - GPT-4o-mini powered intelligent conversations
3. **📚 Knowledge Base** - Uses all knowledge from main bot's database
4. **💬 Chat History** - Remembers previous conversations for context
5. **🔄 API Key Rotation** - Automatic failover when rate limits hit
6. **📊 Shared Database** - Same knowledge & keywords as main bot

---

## 🔧 Environment Variables (Secrets)

### Required:
```bash
TELEGRAM_API_ID=123456          # From https://my.telegram.org/apps
TELEGRAM_API_HASH=abcdef123456  # From https://my.telegram.org/apps
OPENAI_API_KEY=sk-...           # Your OpenAI API key
```

### Optional (Customize Behavior):
```bash
# Feature Toggles (default: all enabled)
USE_AI_RESPONSES=true           # Enable/disable AI responses
USE_KEYWORDS=true               # Enable/disable keyword matching
USE_KNOWLEDGE_BASE=true         # Enable/disable knowledge base

# Rate Limiting (default: disabled)
REPLY_COOLDOWN_HOURS=0          # 0 = reply har message ko
                                # 24 = max 1 reply per user per 24 hours

# Multiple API Keys (for rotation)
OPENAI_API_KEY_1=sk-...
OPENAI_API_KEY_2=sk-...
OPENAI_API_KEY_3=sk-...
```

---

## 📊 How It Works

### Message Flow:

```
📨 Incoming DM
    ↓
🔍 Check Keywords
    ├─ Match Found → Send Instant Reply ✅
    └─ No Match ↓
🤖 Generate AI Response
    ├─ Load Knowledge Base
    ├─ Load Chat History (last 3 messages)
    ├─ Build Context
    └─ Get Response from OpenAI
        ↓
💾 Save to Database
    ↓
✅ Reply Sent!
```

### Priority Order:

1. **Keywords** (Instant, no AI) - Highest priority
2. **AI + Knowledge** (Intelligent, contextual)
3. **AI Only** (General conversation)
4. **Fallback** (If OpenAI unavailable)

---

## 🎨 Examples

### Example 1: Keyword Match
```
User: "What's your price?"
Bot: "Our pricing starts at ₹500/month!" (Instant - from keyword)
```

### Example 2: Knowledge Base
```
User: "Tell me about your features"
Bot: "We offer the following features:
     - Feature A: Description from knowledge base
     - Feature B: Description from knowledge base
     ..." (From AI + Knowledge)
```

### Example 3: General Chat
```
User: "How are you?"
Bot: "Main bilkul theek hoon! Aap kaise ho?" (From AI)
```

---

## 🔄 Shared Database

Personal account bot **same database** use karta hai:

### Tables Used:
- `bot_knowledge` - Knowledge entries (READ)
- `group_keywords` - Keywords & responses (READ)
- `chat_history` - Conversation history (READ/WRITE)

### What This Means:
- ✅ Main bot pe knowledge add karo → Personal bot use karega
- ✅ Keywords add karo → Dono bots respond karenge
- ✅ Chat history merged → Better context for AI
- ✅ One admin panel → Manage everything from main bot

---

## 🚀 Running Both Bots

### Option 1: Separate Workflows (Recommended)

**Workflow 1: Main Bot**
```bash
python main.py
```

**Workflow 2: Personal Account Bot**
```bash
python personal_account_autoreply.py
```

### Option 2: Combined Script

Create `run_both_bots.py`:
```python
import threading
from main import TelegramChatBot
from personal_account_autoreply import PersonalAccountBot

def run_main_bot():
    bot = TelegramChatBot()
    bot.run()

def run_personal_bot():
    pbot = PersonalAccountBot()
    pbot.run()

if __name__ == '__main__':
    # Start main bot in background thread
    main_thread = threading.Thread(target=run_main_bot, daemon=True)
    main_thread.start()
    
    # Start personal bot in main thread
    run_personal_bot()
```

---

## ⚙️ Customization

### Disable AI (Keywords Only):
```bash
USE_AI_RESPONSES=false
USE_KEYWORDS=true
```
Result: Only keyword-based instant replies

### Enable Rate Limiting:
```bash
REPLY_COOLDOWN_HOURS=24
```
Result: Max 1 auto-reply per user per day

### Knowledge Base Only (No Keywords):
```bash
USE_KEYWORDS=false
USE_KNOWLEDGE_BASE=true
```
Result: AI uses knowledge, but no instant keyword replies

---

## 🛡️ Security

### Same Best Practices:
- ✅ Session files are gitignored
- ✅ API keys in environment variables only
- ✅ No secrets in code
- ✅ Rate limiting available

### Additional Security:
- Personal bot only processes **incoming** messages
- Ignores your own messages
- Logs all activity

---

## 📝 Admin Panel Integration

Use main bot's admin panel to manage:

1. **📚 Knowledge Base**
   - `/start` → Add Knowledge
   - Personal bot automatically uses it

2. **🔑 Keywords**
   - `/start` → Keywords → Add Keyword
   - Personal bot checks same keywords

3. **👥 View Users**
   - See all users who messaged (both bots)

4. **📂 Chat History**
   - View conversations from both bots

---

## 🐛 Troubleshooting

### Issue: Personal bot not using knowledge
**Solution:** Make sure `chat_history.db` exists (run main bot first)

### Issue: Keywords not working
**Solution:** Check `USE_KEYWORDS=true` and add keywords via main bot admin panel

### Issue: AI responses disabled
**Solution:** Set `USE_AI_RESPONSES=true` and ensure `OPENAI_API_KEY` is set

### Issue: Too many replies
**Solution:** Set `REPLY_COOLDOWN_HOURS=24` for rate limiting

---

## 📊 Logs

Personal bot logs show:
```
Personal Account Bot initialized:
  - AI Responses: ✅
  - Keywords: ✅
  - Knowledge Base: ✅
  - Cooldown: 0 hours (disabled)

📨 Received DM from username (ID: 123): Hello...
✅ Sent keyword response to username
```

Or:
```
📨 Received DM from username (ID: 123): Tell me more...
✅ Sent AI response to username
```

---

## 🎯 Summary

**Ek configuration, dono bots use karenge:**
- Main bot pe knowledge add karo → Personal bot use karega
- Keywords set karo → Both bots respond karenge
- Same intelligent AI logic
- Shared database & history

**Result:** Consistent, intelligent responses across both bots! 🚀

---

**Status:** ✅ Ready to use! Setup karo aur test karo!
