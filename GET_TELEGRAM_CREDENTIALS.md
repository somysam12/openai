# 🔑 Telegram API Credentials Kaise Le (Step-by-Step)

## Method 1: Web Browser Se (Easiest)

### Step 1: Website Pe Jao
👉 **https://my.telegram.org/auth**

### Step 2: Login Karo
1. Apna **phone number** enter karo (with country code)
   - Example: `+919876543210`
2. **Send confirmation code** click karo
3. Telegram app mein **OTP** aayega (5-digit code)
4. OTP enter karo website pe

### Step 3: App Create Karo
1. Login hone ke baad **"API development tools"** click karo
2. Form fill karo:
   - **App title**: `My Telegram Bot` (kuch bhi naam)
   - **Short name**: `mybot` (koi bhi short name)
   - **Platform**: `Other` select karo
   - **Description**: (optional - khali chod sakte ho)
3. **Create application** button click karo

### Step 4: Credentials Copy Karo
Ab aapko dikhengi:
```
App api_id: 12345678
App api_hash: abcdef1234567890abcdef1234567890
```

✅ **In dono ko copy kar lo** - yeh aapke permanent credentials hain!

---

## Method 2: Telegram App Se (Alternative)

### iOS/Android:
1. Telegram app kholo
2. Settings → Devices → Link Desktop Device
3. QR code scan karo browser se (my.telegram.org/auth pe)
4. Same steps follow karo

---

## ⚠️ Important Notes:

1. **API ID** - 7-8 digit number hoga (e.g., `12345678`)
2. **API Hash** - 32 character hex string hoga (e.g., `abcd1234...`)
3. Yeh credentials **permanent** hain - kabhi expire nahi hote
4. Yeh credentials **kisi ko mat batao** - private rakho
5. Ek Telegram account se multiple apps bana sakte ho

---

## 🔒 Security Tips:

- API credentials ko `.env` file mein rakho (git pe push mat karo)
- Session file safe rakho
- 2FA enable rakho Telegram account pe
- Production mein environment variables use karo

---

**Next Step**: In credentials ko Replit Secrets mein add karo!
