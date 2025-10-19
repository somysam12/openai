# 🔑 API Key Rotation Setup Guide

## Kaise Setup Karein (Hinglish Guide)

### Step 1: Multiple API Keys Add Karein

Aapko apne environment variables mein multiple OpenAI API keys add karne hain. Replit mein secrets ke through add karein:

```
OPENAI_API_KEY_1=sk-proj-xxxxxxxxxxxx
OPENAI_API_KEY_2=sk-proj-yyyyyyyyyyyy
OPENAI_API_KEY_3=sk-proj-zzzzzzzzzzzz
OPENAI_API_KEY_4=sk-proj-aaaaaaaaaaaaa
... (up to OPENAI_API_KEY_20)
```

### Step 2: Kaise Kaam Karta Hai

1. **Auto Rotation**: Jab ek API key rate limit hit karegi (429 error), bot automatically next key pe switch ho jayega
2. **Cycle Through**: Saare keys ko cycle karega - pehli key limit hit hui toh dusri use karegi, phir teesri, aur sab khatam hue toh phir pehli pe wapis jayega
3. **No Downtime**: Users ko koi interruption nahi hoga, seamless switching

### Step 3: Check Logs

Jab bot chale, logs mein aapko dikhai dega:
```
✅ Loaded 8 API keys for rotation
🔄 Rotated to API key #2 (out of 8 keys)
```

## OpenAI Free API Key Limits

### Current Limits (Free Tier):
- **Tokens Per Minute (TPM)**: 100,000
- **Requests Per Minute (RPM)**: 500
- **Requests Per Day (RPD)**: 10,000

### Reset Time:
- TPM limit resets **every minute** on a rolling basis
- Agar limit cross ho jaye: **40-45 minutes** wait karna padta hai complete reset ke liye

### Pro Tip:
- Agar aap 8-9 keys use kar rahe ho, toh theoretically aap **800,000 - 900,000 tokens per minute** use kar sakte ho
- Yeh bahut zyada hai normal chatbot usage ke liye!

## Example: 8 Keys Setup

```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id

# Add as many keys as you have
OPENAI_API_KEY_1=sk-proj-key1
OPENAI_API_KEY_2=sk-proj-key2
OPENAI_API_KEY_3=sk-proj-key3
OPENAI_API_KEY_4=sk-proj-key4
OPENAI_API_KEY_5=sk-proj-key5
OPENAI_API_KEY_6=sk-proj-key6
OPENAI_API_KEY_7=sk-proj-key7
OPENAI_API_KEY_8=sk-proj-key8
```

## How to Get OpenAI API Keys

1. Go to https://platform.openai.com
2. Create account (use different emails for multiple accounts)
3. Go to API Keys section
4. Create new API key
5. Copy aur apne secrets mein paste kar dein

## Important Notes

⚠️ **Security**: API keys ko kabhi publicly share mat karna
✅ **Testing**: Pehle ek key se test karo, phir multiple add karo
🔄 **Monitoring**: Logs check karte raho to see which key is being used

## Troubleshooting

**Problem**: Bot "All API keys exhausted" error de raha hai
**Solution**: Saari keys ka rate limit reset hone ka wait karo (40-45 min) ya zyada keys add karo

**Problem**: Bot start nahi ho raha
**Solution**: Check karo ki kam se kam ek OPENAI_API_KEY_1 set hai

**Problem**: Sirf ek key use ho rahi hai
**Solution**: Logs check karo - rotation tab hi hoga jab rate limit hit hogi
