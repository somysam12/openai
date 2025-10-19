# 🔑 Smart Keyword Feature - User Guide

## नया Feature क्या है?

अब आप keywords add कर सकते हैं जो **automatically** आपके Knowledge Base से intelligent replies generate करेंगे!

## कैसे काम करता है?

### Option 1: Smart AI Response (NEW! ✨)
जब आप सिर्फ keyword add करते हैं बिना response के:
```
price
```

**Bot क्या करेगा:**
1. ✅ Keyword detect करेगा
2. 🔍 Knowledge Base में search करेगा
3. 🧠 AI से intelligent response generate करेगा
4. 💬 Context-aware reply भेजेगा

**Example:**
- Admin ने Knowledge Base में add किया: "हमारा product ₹500 per month है, unlimited features के साथ"
- User बोले: "Price kya hai?"
- Bot automatically Knowledge Base से information निकाल कर reply देगा!

### Option 2: Fixed Response (पहले जैसा)
जब आप keyword के साथ response भी देते हैं:
```
help | Support के लिए @tgshaitaan को contact करें!
```

**Bot क्या करेगा:**
- सीधा वही response भेज देगा जो आपने add किया है

## Admin Panel में कैसे Add करें?

### Smart Keyword (AI + Knowledge Base):
1. Admin panel खोलें (`/start`)
2. "➕ Add Keyword" बटन दबाएं
3. सिर्फ keyword type करें: `price`
4. भेज दें!

✅ Done! अब जब भी कोई "price" बोलेगा, bot knowledge base से intelligent reply देगा।

### Fixed Response Keyword:
1. Admin panel खोलें
2. "➕ Add Keyword" दबाएं
3. इस format में type करें: `help | Contact @tgshaitaan for support`
4. भेज दें!

## Keywords देखने के लिए:

Admin panel में "🔑 View Keywords" दबाएं। आपको दिखेगा:

```
1. price
   ✨ AI + Knowledge Base

2. help
   📝 Direct: Contact @tgshaitaan for support
```

## फायदे:

✅ **Time Saving**: हर keyword के लिए response लिखने की जरूरत नहीं  
✅ **Smart Replies**: Bot knowledge base से automatically context samajh ke reply करता है  
✅ **Flexible**: कुछ keywords fixed रखें, कुछ AI से handle करवाएं  
✅ **Easy Updates**: Knowledge base update करो, सभी keywords automatically updated replies देंगे  

## Example Use Cases:

### E-commerce Bot:
```
Keywords (Smart):
- price
- features
- delivery
- warranty

Knowledge Base:
- Product: Premium Mouse
- Price: ₹1500
- Features: RGB, Wireless, 6 buttons
- Delivery: Free in 2 days
- Warranty: 1 year
```

User: "price batao"  
Bot: "Premium Mouse की price ₹1500 है! 😊"

User: "features kya hain?"  
Bot: "Features: RGB lighting, Wireless connectivity aur 6 programmable buttons! 🖱️"

## Important Notes:

⚠️ **Knowledge Base Empty**: Agar knowledge base में information nahi hai, toh bot politely batayega ki information available nahi hai.

💡 **Best Practice**: Pehle Knowledge Base me information add karein, phir keywords add karein for best results!

🔄 **Updates**: Knowledge base update karne se automatically sare smart keywords ka response update ho jayega!
