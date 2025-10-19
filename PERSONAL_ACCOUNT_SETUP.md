# 🔧 Personal Telegram Account Auto-Reply Setup Guide

## ⚠️ Important Information

Yeh script aapke **personal Telegram account** ko automate karti hai. Regular bot API se yeh possible nahi hai.

### Security Warning:
- Yeh script aapke account ko **full access** deti hai
- Session file ko secure rakho, kabhi share mat karo
- Trusted server pe hi run karo
- Telegram Terms of Service follow karo

---

## 📋 Setup Steps

### Step 1: API Credentials Prapt Karo

1. Browser mein https://my.telegram.org/apps pe jao
2. Apne phone number se login karo
3. **Create new application** click karo:
   - **App title**: "My Auto Reply Bot"
   - **Short name**: "autoreply"
   - **Platform**: Choose any (e.g., "Desktop")
4. **API ID** aur **API Hash** mil jayega - inhe save karo!

### Step 2: Environment Variables Set Karo

Replit mein secrets add karo:
```
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
AUTO_REPLY_MESSAGE=Your custom auto-reply message here
```

### Step 3: Dependencies Install Karo

```bash
pip install pyrogram tgcrypto
```

**Note:** `tgcrypto` optional hai but speed badhata hai

### Step 4: First Time Login

Script ko pehli baar run karne par:

```bash
python personal_account_autoreply.py
```

Aapse poocha jayega:
1. **Phone number** (with country code, e.g., +911234567890)
2. **Login code** (Telegram se SMS/app mein aayegi)
3. **2FA Password** (agar enabled hai)

Login successful hone ke baad **session file** create hogi (`my_personal_account.session`).

### Step 5: Workflow Setup (Optional)

Agar continuously run karna chahte ho, workflow add karo:
```bash
python personal_account_autoreply.py
```

---

## 🎯 Features

### ✅ Automatic Reply
- Har incoming DM ka automatic reply
- Customizable message via `AUTO_REPLY_MESSAGE` environment variable

### ✅ Rate Limiting (Spam Prevention)
- Ek user ko max **1 auto-reply per 24 hours**
- Infinite loop prevention
- Database mein tracking

### ✅ Smart Filtering
- Ignores messages from yourself
- Only private messages (no groups)
- Only incoming messages

---

## 🔧 Customization

### Change Auto-Reply Message:

Environment variable set karo:
```
AUTO_REPLY_MESSAGE=Your custom message here!
```

Ya code mein directly change karo (`personal_account_autoreply.py` line 42)

### Change Cooldown Period:

Code mein `reply_cooldown_hours` change karo (default: 24 hours)

### Advanced: Keyword-Based Replies

Code mein `handle_incoming_dm()` function modify karo:

```python
async def handle_incoming_dm(self, client: Client, message: Message):
    if not message.text:
        return
    
    message_text = message.text.lower()
    
    # Keyword-based responses
    if "price" in message_text:
        reply = "Our pricing starts at ₹500/month! Contact @support for details."
    elif "contact" in message_text:
        reply = "You can reach us at: support@example.com"
    else:
        reply = self.auto_reply_message
    
    if self.should_auto_reply(message.from_user.id):
        await message.reply_text(reply)
        self.record_auto_reply(message.from_user.id)
```

---

## 🚨 Security Best Practices

### 1. Session File Security
```bash
# Never commit session files to git
echo "*.session" >> .gitignore
```

### 2. Use Environment Variables
```bash
# Never hardcode API credentials
api_id = os.getenv('TELEGRAM_API_ID')  # ✅ Good
api_id = 12345  # ❌ Bad
```

### 3. Rate Limiting
- Current implementation: 1 reply per user per 24 hours
- Prevents spam and Telegram bans
- Adjust cooldown as needed

### 4. Telegram ToS Compliance
- Don't spam users
- Don't use for marketing without consent
- Follow Telegram's acceptable use policy

---

## 📊 Database Schema

Auto-replies tracked in `personal_autoreplies.db`:

```sql
CREATE TABLE auto_replies (
    user_id INTEGER PRIMARY KEY,
    last_reply_time DATETIME,
    reply_count INTEGER
);
```

---

## 🐛 Troubleshooting

### Issue: "API ID/Hash not set"
**Solution:** Make sure environment variables are set correctly in Secrets

### Issue: "Phone number required"
**Solution:** First run needs interactive login. Run locally first, then upload session file

### Issue: "Session expired"
**Solution:** Delete `.session` file and login again

### Issue: "Flood wait" error
**Solution:** Too many messages sent. Wait and increase cooldown period

---

## 🔄 Running Both Bots Together

Aap **dono bots** simultaneously run kar sakte ho:

1. **main.py** - Regular bot (Bot API) - Bot account ke liye
2. **personal_account_autoreply.py** - Personal account automation

Dono alag workflows mein run karein ya ek script se dono start karein.

---

## 📞 Support

Agar koi issue aaye ya customization chahiye, admin panel se contact karein!

---

**Status:** Ready to use! Setup karke test karo! 🚀
