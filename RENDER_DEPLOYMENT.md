# Render.com Deployment Guide - Telegram AI Chatbot

## Prerequisites
- Render.com account (free tier works)
- Your Telegram Bot Token
- Your OpenAI API Key
- Your Telegram Admin ID

## Step-by-Step Deployment

### 1. Push Code to GitHub (Optional)
If you want to deploy from GitHub:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

### 2. Create New Web Service on Render

1. Go to https://render.com and login
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo OR use **"Public Git repository"** and paste your repo URL

### 3. Configure Web Service

**Basic Settings:**
- **Name:** `telegram-ai-bot` (or any name you prefer)
- **Region:** Choose closest to your users
- **Branch:** `main`
- **Root Directory:** Leave blank
- **Runtime:** `Python 3`
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python main.py`

**Instance Type:**
- Select **"Free"** (sufficient for most use cases)

### 4. Environment Variables

Click **"Advanced"** and add these environment variables:

| Key | Value |
|-----|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token (e.g., 8267153211:AAH81NuZHAbfU6U1htDTzmGSE_zNvPeNAzU) |
| `OPENAI_API_KEY` | Your OpenAI API key (starts with sk-) |
| `ADMIN_ID` | Your Telegram User ID (e.g., 5952524867) |

### 5. Deploy

1. Click **"Create Web Service"**
2. Render will start building and deploying your bot
3. Wait for "Deploy succeeded" message
4. Your bot is now live 24/7!

## Important Notes

### Database Persistence
The SQLite database (`chat_history.db`) will be stored on Render's disk. However, **free tier instances may reset on restart**. For production:

**Option A: Use Render's Disk (Paid)**
- Upgrade to a paid plan for persistent disk

**Option B: Use PostgreSQL (Recommended for Free Tier)**
- Modify code to use Render's free PostgreSQL database
- This ensures data persists across restarts

### Health Checks
Render expects HTTP responses. Since this is a Telegram bot (not a web server):
- Go to **Settings** → **Health Check Path**
- Set to: `/health` (we'll add this endpoint)
- OR disable health checks entirely

### Keeping Bot Alive
Free tier instances sleep after 15 minutes of inactivity. Your Telegram bot uses polling, so it should stay active when receiving messages.

## Troubleshooting

### Bot Not Responding
1. Check **Logs** tab on Render dashboard
2. Verify all environment variables are set correctly
3. Make sure bot token is valid

### Database Issues
If you see "database locked" errors:
- This happens on free tier due to disk limitations
- Consider upgrading or switching to PostgreSQL

### Build Failed
- Check `requirements.txt` is present
- Verify Python version compatibility
- Check Render logs for specific error

## Testing Deployment

1. Open Telegram
2. Search for your bot
3. Send `/start` command
4. If admin, try `/users` to see all users
5. Try `/setknowledge` to set your product info

## Post-Deployment

### Admin Panel (Button-Based Interface)

Admin ko commands yaad rakhne ki zarurat nahi! Bot mein ab **interactive buttons** hain.

**Admin Access:**
1. Telegram pe bot ko `/start` karein
2. Admin panel automatically khul jayega buttons ke saath:

**Available Buttons:**
- 📚 **View Knowledge** - Current bot knowledge dekho
- ✏️ **Set Knowledge** - Naya knowledge set karo
- 👥 **View Users** - Sabhi users ki list
- 💬 **Message User** - Kisi user ko select karke message karo
- 📢 **Broadcast** - Sabhi users ko message bhejo
- 🔚 **End Session** - Active chat session khatam karo
- 🔄 **Refresh Panel** - Panel refresh karo

**Example Workflow:**
1. Click "Set Knowledge" button
2. Bot knowledge message bhejega
3. Type your product details and send
4. Done! ✅

No need to remember any commands - sab kuch buttons mein hai!

## Cost Estimate

**Free Tier:**
- ✅ Hosting: Free
- ✅ 750 hours/month (sufficient for 24/7)
- ⚠️ Database may not persist on restart
- ⚠️ Sleeps after inactivity

**Paid Tier ($7/month):**
- ✅ Persistent disk storage
- ✅ Always-on, no sleeping
- ✅ Better performance

## Alternative: Keep Free Tier Active

Use a cron job service to ping your bot every 14 minutes:
- UptimeRobot (free)
- Cron-job.org (free)

However, this requires adding a simple HTTP endpoint to your bot.

---

**Need Help?** Check Render's documentation or contact support.
