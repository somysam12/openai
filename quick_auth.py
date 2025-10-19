from pyrogram import Client
import os

api_id = int(os.getenv('TELEGRAM_API_ID'))
api_hash = os.getenv('TELEGRAM_API_HASH')

print("🔐 Pyrogram Quick Authentication")
print("=" * 50)

app = Client("my_personal_account", api_id=api_id, api_hash=api_hash)

app.start()
me = app.get_me()

print(f"\n✅ Successfully logged in!")
print(f"   Name: {me.first_name}")
print(f"   Phone: {me.phone_number}")
print(f"   Username: @{me.username if me.username else 'None'}")
print(f"\n✅ Session saved: my_personal_account.session")

app.stop()
