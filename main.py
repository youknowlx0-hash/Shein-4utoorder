import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
import config

BOT_TOKEN = config.BOT_TOKEN
ADMIN_ID = config.ADMIN_ID
CHANNELS = config.CHANNELS

bot = telebot.TeleBot(BOT_TOKEN)

# ===== DATABASE =====
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    referrals INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    dp TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS stats (
    total_users INTEGER DEFAULT 0,
    total_video_unlock INTEGER DEFAULT 0,
    total_file_unlock INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS items (
    type TEXT PRIMARY KEY,
    file_id TEXT
)
''')
conn.commit()

# ===== FUNCTIONS =====
def is_joined_all(user_id):
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "creator", "administrator"]:
                return False
        except:
            return False
    return True

def add_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        cursor.execute("UPDATE stats SET total_users = total_users + 1")
        conn.commit()

def update_user_dp(user_id):
    photos = bot.get_user_profile_photos(user_id, limit=1)
    if photos.total_count > 0:
        file_id = photos.photos[0][0].file_id
        cursor.execute("UPDATE users SET dp=? WHERE user_id=?", (file_id, user_id))
        conn.commit()

def add_referral(referrer_id):
    cursor.execute("SELECT points, referrals FROM users WHERE user_id=?", (referrer_id,))
    row = cursor.fetchone()
    if row:
        new_ref = row[1]+1
        new_points = row[0]+1
        cursor.execute("UPDATE users SET referrals=?, points=? WHERE user_id=?",
                       (new_ref,new_points,referrer_id))
        conn.commit()
        bot.send_message(referrer_id, f"🎉 New referral joined! 💎 +1 Point\nTotal Points: {new_points}")

def get_points(user_id):
    cursor.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

def unlock_item(user_id, item_type):
    points = get_points(user_id)
    if item_type == "video" and points >= 5:
        cursor.execute("UPDATE stats SET total_video_unlock = total_video_unlock + 1")
        conn.commit()
        return True
    elif item_type == "file" and points >= 10:
        cursor.execute("UPDATE stats SET total_file_unlock = total_file_unlock + 1")
        conn.commit()
        return True
    else:
        return False

# ===== DECORATOR =====
def check_channels(func):
    def wrapper(call_or_message, *args, **kwargs):
        if hasattr(call_or_message, 'from_user'):
            user_id = call_or_message.from_user.id
        else:
            user_id = call_or_message.chat.id

        if not is_joined_all(user_id):
            if hasattr(call_or_message, 'id'):
                bot.answer_callback_query(call_or_message.id, "❌ Join all channels first!")
            else:
                bot.send_message(user_id, "❌ Join all channels first!", reply_markup=join_channel_buttons())
            return
        return func(call_or_message, *args, **kwargs)
    return wrapper

# ===== BUTTONS =====
def join_channel_buttons():
    markup = InlineKeyboardMarkup(row_width=1)
    for ch in CHANNELS:
        markup.add(InlineKeyboardButton(f"🔴 Join {ch}", url=f"https://t.me/{ch[1:]}"))
    return markup

def unlock_buttons(user_id):
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🔴 UNLOCK VIDEO (5💎)", callback_data="unlock_video"),
        InlineKeyboardButton("🟢 UNLOCK FILE (10💎)", callback_data="unlock_file"),
        InlineKeyboardButton("🔵 PAID ACCESS", callback_data="paid_access"),
        InlineKeyboardButton("🔗 Copy Referral Link", url=f"https://t.me/{bot.get_me().username}?start={user_id}")
    )
    return markup

# ===== COMMANDS =====
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    add_user(user_id)
    update_user_dp(user_id)

    args = message.text.split()
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id != user_id:
                add_referral(referrer_id)
        except:
            pass

    if not is_joined_all(user_id):
        bot.send_message(user_id, "❌ Join all channels first!", reply_markup=join_channel_buttons())
        return

    points = get_points(user_id)
    bot.send_message(user_id,
        f"👋 Welcome!\n💎 Points: {points}\nReferral: https://t.me/{bot.get_me().username}?start={user_id}",
        reply_markup=unlock_buttons(user_id)
    )

@bot.message_handler(commands=['stats'])
def stats(message):
    user_id = message.from_user.id
    cursor.execute("SELECT total_users, total_video_unlock, total_file_unlock FROM stats")
    total_users, video_unlock, file_unlock = cursor.fetchone()
    cursor.execute("SELECT points, referrals FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    points, referrals = row if row else (0,0)

    text = f"📊 Bot Stats:\n🚀 Total Users: {total_users}\n🎥 Video Unlocks: {video_unlock}\n📁 File Unlocks: {file_unlock}\n\n"
    text += f"🧑 Your Stats:\n💎 Points: {points}\n👥 Referrals: {referrals}"
    bot.send_message(user_id, text)

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    cursor.execute("SELECT user_id, points, dp FROM users ORDER BY points DESC LIMIT 10")
    rows = cursor.fetchall()
    for i,row in enumerate(rows,1):
        uid, points, dp = row
        text = f"{i}. User: {uid} - Points: {points}"
        if dp:
            bot.send_photo(message.chat.id, dp, caption=text)
        else:
            bot.send_message(message.chat.id, text)

# ===== CALLBACK HANDLER =====
@bot.callback_query_handler(func=lambda call: True)
@check_channels
def callback_query(call):
    user_id = call.from_user.id
    if call.data == "unlock_video":
        if unlock_item(user_id,"video"):
            cursor.execute("SELECT file_id FROM items WHERE type='video'")
            row = cursor.fetchone()
            if row:
                bot.send_video(user_id, row[0], protect_content=True, supports_streaming=True)
            bot.answer_callback_query(call.id, "🎥 Video Unlocked! ✅")
        else:
            bot.answer_callback_query(call.id, "🚫 Not enough points! Need 5💎")
    elif call.data == "unlock_file":
        if unlock_item(user_id,"file"):
            cursor.execute("SELECT file_id FROM items WHERE type='file'")
            row = cursor.fetchone()
            if row:
                bot.send_document(user_id, row[0], protect_content=True)
            bot.answer_callback_query(call.id, "📁 File Unlocked! ✅")
        else:
            bot.answer_callback_query(call.id, "🚫 Not enough points! Need 10💎")
    elif call.data == "paid_access":
        bot.answer_callback_query(call.id, f"💰 Paid Access: Contact Admin @{ADMIN_ID}")

# ===== ADMIN COMMANDS =====
admin_waiting = {}

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID)
def admin_commands(message):
    global admin_waiting
    text = message.text.lower()
    args = text.split()
    if text.startswith("/addvideo"):
        admin_waiting['video'] = message.from_user.id
        bot.send_message(ADMIN_ID, "Send the video to upload for users!")
    elif text.startswith("/addfile"):
        admin_waiting['file'] = message.from_user.id
        bot.send_message(ADMIN_ID, "Send the file/document to upload for users!")
    elif text.startswith("/addbalance") and len(args)==3:
        try:
            uid = int(args[1])
            pts = int(args[2])
            cursor.execute("UPDATE users SET points = points + ? WHERE user_id=?", (pts, uid))
            conn.commit()
            bot.send_message(ADMIN_ID, f"✅ Added {pts}💎 to user {uid}")
        except:
            bot.send_message(ADMIN_ID, "❌ Error! Usage: /addbalance <user_id> <points>")
    elif text.startswith("/removebalance") and len(args)==3:
        try:
            uid = int(args[1])
            pts = int(args[2])
            cursor.execute("UPDATE users SET points = points - ? WHERE user_id=?", (pts, uid))
            conn.commit()
            bot.send_message(ADMIN_ID, f"✅ Removed {pts}💎 from user {uid}")
        except:
            bot.send_message(ADMIN_ID, "❌ Error! Usage: /removebalance <user_id> <points>")

@bot.message_handler(content_types=['video','document'])
def handle_file_upload(message):
    global admin_waiting
    if admin_waiting.get('video') == message.from_user.id and message.content_type=='video':
        cursor.execute("REPLACE INTO items (type, file_id) VALUES (?,?)", ("video", message.video.file_id))
        conn.commit()
        bot.send_message(ADMIN_ID, "✅ Video uploaded successfully!")
        del admin_waiting['video']
    elif admin_waiting.get('file') == message.from_user.id and message.content_type=='document':
        cursor.execute("REPLACE INTO items (type, file_id) VALUES (?,?)", ("file", message.document.file_id))
        conn.commit()
        bot.send_message(ADMIN_ID, "✅ File uploaded successfully!")
        del admin_waiting['file']

# ===== RUN BOT =====
print("Bot Running...")
bot.infinity_polling()
