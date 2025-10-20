# 🎯 Live Token Tracking System - Complete! ✅

## ✨ Features Added

### 📊 **Live Token Statistics in Admin Panel**

Admin panel mein ab **live token tracking** hai with complete details:

#### Overall Statistics:
- 🔥 **Total Used Today**: Sabhi keys ki combined tokens used
- ✅ **Total Left Today**: Sabhi keys mein kitne tokens bache hain
- 🌟 **Lifetime Total**: Start se ab tak total tokens use kiye

#### Individual Key Statistics:
Har API key ke liye:
- 📊 **Tokens Used / Daily Limit**: Kitne use kiye / kitne max hain
- 💚 **Tokens Left**: Kitne tokens bache hain
- 📞 **API Calls**: Kitni baar call ki gayi
- ⚠️ **Rate Hits**: Kitni baar rate limit hit hui
- ⏰ **Reset Time**: Kitne ghante/minute mein reset hoga

#### Smart Status Indicators:
- 🟢 **FRESH**: Koi token use nahi hua
- 🟢 **ACTIVE**: Normal use, kaafi tokens bache hain
- 🟡 **LOW**: 500K se kam tokens bache (warning!)
- 🔴 **EXHAUSTED**: Sab tokens khatam (skip this key!)

## 🔧 Technical Implementation

### Database Schema:
```sql
api_key_stats table mein new columns:
- tokens_used_today      (aaj tak kitne tokens use kiye)
- tokens_input_today     (input/prompt tokens)
- tokens_output_today    (output/completion tokens)
- daily_reset_time       (last kab reset hua)
- total_tokens_lifetime  (total lifetime usage)
```

### Auto Reset Logic:
- **24 hours** ke baad automatically daily counters reset ho jate hain
- Reset time track hota hai database mein
- Next reset time admin panel mein dikhta hai

### Token Limits (Free Tier):
```
GPT-4o-mini Complimentary Program (Data Sharing):
- Tier 1-2: 2,500,000 tokens/day per key
- Tier 3-5: 10,000,000 tokens/day per key

Currently configured: 2.5M tokens/day (conservative)
```

## 📱 Admin Panel Display Example

```
🔑 API Key & Token Statistics

📊 Total API Keys: 18
🔄 Currently Using: Key #3
💎 Daily Limit Per Key: 2.5M tokens (GPT-4o-mini)

📈 Overall Today:
🔥 Total Used: 156,789 tokens
✅ Total Left: 44,843,211 tokens
🌟 Lifetime Total: 2,456,123 tokens

━━━━━━━━━━━━━━━━━

🔑 Individual Keys:

Key #1 🟢 ACTIVE
  📊 Used: 45,231 / 2,500,000
  💚 Left: 2,454,769 tokens
  📞 API Calls: 156
  ⏰ Resets in: 18h 45m

Key #2 🟡 LOW
  📊 Used: 2,123,456 / 2,500,000
  💚 Left: 376,544 tokens
  📞 API Calls: 2,456
  ⚠️ Rate Hits: 3
  ⏰ Resets in: 12h 30m

Key #3 🔴 EXHAUSTED
  📊 Used: 2,500,000 / 2,500,000
  💚 Left: 0 tokens
  📞 API Calls: 3,789
  ⏰ Resets in: 6h 15m

...and 15 more keys
```

## 🚀 Both Bots Track Tokens

### Main Bot (`main.py`):
- ✅ Tracks tokens on every API call
- ✅ Shows in admin panel
- ✅ Auto resets daily
- ✅ Shares database with Pyrogram bot

### Personal Bot (`personal_account_autoreply.py`):
- ✅ Tracks tokens on every API call  
- ✅ Writes to same database as main bot
- ✅ Combined stats visible in main bot admin panel
- ✅ Same rotation & tracking logic

## 💡 How It Works

### 1. API Call Made:
```python
response = openai_client.chat.completions.create(...)

# Extract tokens from response
tokens_input = response.usage.prompt_tokens
tokens_output = response.usage.completion_tokens
```

### 2. Track in Database:
```python
self.track_api_key_usage(
    key_index=self.current_key_index,
    is_rate_limit=False,
    tokens_input=tokens_input,
    tokens_output=tokens_output
)
```

### 3. Check & Reset Daily:
```python
if datetime.now() - last_reset >= timedelta(hours=24):
    # Reset daily counters
    tokens_used_today = 0
    daily_reset_time = now
```

### 4. Display in Admin:
```python
# Calculate tokens left
tokens_left = DAILY_LIMIT - tokens_used_today

# Calculate reset time
hours_until_reset = (last_reset + 24h - now).hours
```

## 📈 Benefits

1. **Real-time Monitoring**: Dekho har key kitne tokens use kar rahi hai
2. **Prevent Overuse**: Red/Yellow status se pata chal jata hai limit near hai
3. **Smart Rotation**: Bot automatically exhausted keys ko skip kar deta hai
4. **Cost Control**: Track karo kitna use ho raha hai
5. **Reset Tracking**: Pata hai kab fresh tokens milenge
6. **Combined View**: Main + Personal bot dono ki stats ek jagah

## 🎯 Usage in Admin Panel

1. Bot ko `/admin` command send karo
2. "🔑 API Key Stats" button click karo
3. Real-time stats dekho:
   - Overall usage
   - Individual key stats
   - Reset times
   - Status indicators

## ✅ Status

**FULLY IMPLEMENTED & READY TO DEPLOY!**

Dono bots (Main + Pyrogram) mein:
- ✅ Token tracking active
- ✅ Database schema updated
- ✅ Admin panel updated
- ✅ Auto reset logic working
- ✅ Smart rotation based on token limits

**Ab git push karo aur deploy karo!** 🚀
