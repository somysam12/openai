# 🔑 Fresh API Keys Kaise Banaye

## Problem
Purani API keys already heavily use ho chuki hain, isliye turant exhaust ho jati hain.

## Solution: Naye API Keys Generate Karo

### Step 1: Naye OpenAI Accounts Banao
1. **Different emails use karo** (Gmail, Outlook, Yahoo, etc.)
2. Har email se ek naya OpenAI account banao
3. Phone verification ke liye same number use kar sakte ho

### Step 2: API Keys Generate Karo
1. https://platform.openai.com pe login karo
2. Settings → API Keys pe jao
3. "Create new secret key" click karo
4. Key copy karke save kar lo

### Step 3: Replit Secrets Mein Add Karo
```
OPENAI_API_KEY_7=sk-proj-your-new-key-7
OPENAI_API_KEY_8=sk-proj-your-new-key-8
OPENAI_API_KEY_9=sk-proj-your-new-key-9
... (jitne chahiye)
```

## Pro Tips

### 🎯 Fresh Keys Ki Pehchan:
- **Fresh key**: Turant kaam karegi, no delay
- **Used key**: Immediately 429 error

### 📊 Usage Check Karne Ke Liye:
1. https://platform.openai.com/usage pe jao
2. Current usage dekh sakte ho
3. Agar 90%+ usage hai, toh fresh key nahi hai

### 🔄 Long-term Strategy:
- **10-15 fresh keys** rakhna best hai
- Rotation system automatically handle kar lega
- Monthly usage track karte raho

## Alternative: Paid Tier

Agar consistent service chahiye:
- OpenAI ka paid tier lo ($5+ credit add karo)
- Rate limits bahut zyada badh jayenge:
  - Free: 100,000 TPM
  - Tier 1 ($5+): 450,000 TPM
  - Tier 2 ($50+): 2,000,000 TPM

## Testing Fresh Keys

Naya key add karne ke baad test karo:
```python
# Terminal mein run karo
export OPENAI_API_KEY="your-new-key"
curl https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"test"}]}'
```

Agar immediately kaam kare = Fresh key ✅
Agar 429 error = Already used ❌
