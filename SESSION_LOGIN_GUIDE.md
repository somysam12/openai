# 🔐 Pyrogram Session Login Guide - Hindi/Hinglish

## 📋 पूरी Process (Step by Step)

### Step 1: API Credentials Set करो

पहले अपने Telegram API credentials Secrets में add करो:

**Replit Secrets में जाकर add करो:**
- Key: `TELEGRAM_API_ID` → Value: आपकी API ID (जैसे: `24586002`)
- Key: `TELEGRAM_API_HASH` → Value: आपकी API Hash (जैसे: `dd899a75e335...`)

**या फिर Shell में सेट करो (temporary):**
```bash
export TELEGRAM_API_ID="24586002"
export TELEGRAM_API_HASH="dd899a75e335d7f630e0dc8b4d11b7c7"
```

> 💡 API credentials कैसे पाएं? 
> https://my.telegram.org/apps पर जाओ और नया app बनाओ

---

### Step 2: Shell में Login करो

अब Shell में ये command चलाओ:

```bash
python3 create_new_session.py
```

**Process:**
1. Script पुरानी session files को delete करेगी
2. आपसे phone number माँगेगी (country code के साथ, जैसे: `+919876543210`)
3. Telegram पर OTP आएगा - **तुरंत enter करो (5 min में expire हो जाएगा)**
4. अगर 2FA है तो password भी माँगेगा
5. Session file बन जाएगी: `my_personal_account.session`

---

### Step 3: Verify करो

Session बनने के बाद check करो:

```bash
ls -la *.session
```

Output में `my_personal_account.session` दिखनी चाहिए!

---

## ❓ Session Auto-Logout क्यों होता है?

### मुख्य कारण:

1. **OTP Expire (सबसे आम)**
   - OTP 5 minutes में expire हो जाता है
   - **Solution:** तुरंत OTP enter करो, जल्दी करो!

2. **Multiple Logins**
   - Same account अलग-अलग जगह login है
   - **Solution:** एक device पर ही रखो active

3. **Session File Delete/Corrupt**
   - Session file गलती से delete हो गई
   - **Solution:** हमेशा backup रखो (`my_personal_account_backup.txt`)

4. **API Key Change**
   - अलग API ID/Hash use किया
   - **Solution:** हमेशा same credentials use करो

5. **2FA Conflict**
   - Two-Factor Authentication में issue
   - **Solution:** Login के समय password properly enter करो

6. **Telegram Account Restrictions**
   - Account banned/restricted है
   - **Solution:** Telegram support से contact करो

---

## 💡 Session को Permanent रखने के Tips

### ✅ DO:
- Session file को safe रखो (delete मत करो)
- Same API credentials हमेशा use करो
- Session string की backup रखो
- Regular intervals में test करो
- Git में commit करो (private repo में)

### ❌ DON'T:
- Multiple devices पर same session use मत करो
- Session file manually edit मत करो
- API credentials बार-बार change मत करो
- Telegram में "Terminate all other sessions" मत करो
- 2FA password reset मत करो

---

## 🚀 Quick Commands Reference

### पुरानी session delete करो:
```bash
rm -f my_personal_account.session my_personal_account.session-journal
```

### नया session बनाओ:
```bash
python3 create_new_session.py
```

### Session check करो:
```bash
ls -la *.session
```

### Session backup restore करो (अगर string है):
```bash
python3 restore_from_string.py
```

### Test करो session काम कर रही है:
```bash
python3 quick_auth.py
```

---

## 🆘 Troubleshooting

### Problem: "OTP Expired"
**Solution:**
```bash
# फिर से run करो तुरंत
python3 create_new_session.py
# इस बार OTP आते ही immediately enter करो
```

### Problem: "Session file not found"
**Solution:**
```bash
# चेक करो file exist करती है
ls -la *.session

# अगर नहीं है तो नया बनाओ
python3 create_new_session.py
```

### Problem: "Multiple sessions detected"
**Solution:**
```bash
# सभी पुरानी sessions delete करो
rm -f *.session *.session-journal

# फिर नया session बनाओ
python3 create_new_session.py
```

### Problem: "API ID/Hash invalid"
**Solution:**
1. https://my.telegram.org/apps जाओ
2. Fresh API credentials लो
3. Replit Secrets में update करो
4. फिर से login करो

---

## 📱 Complete Example

```bash
# Step 1: API credentials सेट करो (Replit Secrets में already होने चाहिए)

# Step 2: पुरानी session delete करो (optional)
rm -f my_personal_account.session*

# Step 3: नया session बनाओ
python3 create_new_session.py

# Output:
# Enter your phone number: +919876543210
# Enter the code: 12345  ← OTP तुरंत enter करो!
# ✅ SUCCESS! Session created!

# Step 4: Verify करो
ls -la my_personal_account.session

# Step 5: Bot चलाओ
python3 start_both_bots.py
```

---

## 🔑 Session String Backup क्या है?

Session string एक long text होता है जो आपकी login को represent करता है।

**Backup कब use करें:**
- Session file corrupt हो गई
- नई machine पर restore करना है
- Git में file commit नहीं कर सकते

**Session string कैसे use करें:**
```python
from pyrogram import Client

session_string = "YOUR_SESSION_STRING_HERE"

app = Client(
    "my_account",
    api_id=24586002,
    api_hash="dd899a75...",
    session_string=session_string
)
```

---

## ✅ Summary

1. **Login Command:** `python3 create_new_session.py`
2. **Auto-logout क्यों:** OTP expire, multiple logins, session file issues
3. **Solution:** तुरंत OTP enter करो, session file को safe रखो
4. **Backup:** Session string save करके रखो

---

**अब तुरंत shell में जाओ और command चलाओ! 🚀**
