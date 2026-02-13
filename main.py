import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3, os, time, random

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = telebot.TeleBot(BOT_TOKEN)

# ===== DATABASE =====
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    referrals INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS stats (
    total_users INTEGER DEFAULT 0,
    total_video_unlock INTEGER DEFAULT 0,
    total_file_unlock INTEGER DEFAULT 0
)''')

conn.commit()

# ===== CHANNELS LIST =====
with open("channels.txt","r") as f:
    CHANNELS = [line.strip() for line in f.readlines() if line.strip()]

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

def add_referral(referrer_id):
    cursor.execute("SELECT points, referrals FROM users WHERE user_id=?", (referrer_id,))
    row = cursor.fetchone()
    if row:
        new_ref = row[1]+1
        new_points = row[0]+1
        cursor.execute("UPDATE users SET referrals=?, points=? WHERE user_id=?",(new_ref,new_points,referrer_id))
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

# ===== COMMANDS =====
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    add_user(user_id)

    args = message.text.split()
    if len(args) > 1:
        try:
            referrer_id = int(args[1])
            if referrer_id != user_id:
                add_referral(referrer_id)
        except:
            pass

    if not is_joined_all(user_id):
        markup = InlineKeyboardMarkup()
        for ch in CHANNELS:
            markup.add(InlineKeyboardButton(f"🔴 Join {ch}", url=f"https://t.me/{ch[1:]}"))
        bot.send_message(user_id, "❌ Join all channels first!", reply_markup=markup)
        return

    points = get_points(user_id)
    bot.send_message(user_id,
        f"👋 Welcome!\n"
        f"💎 Your Points: {points}\n"
        f"📌 Referral Link: https://t.me/{bot.get_me().username}?start={user_id}\n\n"
        f"Unlock Options:\n"
        f"🎥 Video - 5 Points\n"
        f"📁 File - 10 Points\n"
        f"👑 Full Access - 15 Points"
    )

@bot.message_handler(commands=['stats'])
def show_stats(message):
    cursor.execute("SELECT total_users, total_video_unlock, total_file_unlock FROM stats")
    row = cursor.fetchone()
    total_users, video_unlock, file_unlock = row
    bot.send_message(message.chat.id,
                     f"📊 Bot Stats:\n"
                     f"🚀 Total Users: {total_users}\n"
                     f"🎥 Video Unlocks: {video_unlock}\n"
                     f"📁 File Unlocks: {file_unlock}")

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    cursor.execute("SELECT user_id, points FROM users ORDER BY points DESC LIMIT 10")
    rows = cursor.fetchall()
    text = "🏆 Top 10 Referrals:\n"
    for i,row in enumerate(rows,1):
        text += f"{i}. User: {row[0]} - Points: {row[1]}\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['addbalance'])
def add_balance(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        uid = int(parts[1]); pts = int(parts[2])
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id=?",(pts,uid))
        conn.commit()
        bot.send_message(message.chat.id,f"✅ Added {pts} Points to {uid}")
    except:
        bot.send_message(message.chat.id,"Usage: /addbalance user_id points")

@bot.message_handler(commands=['removebalance'])
def remove_balance(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        uid = int(parts[1]); pts = int(parts[2])
        cursor.execute("SELECT points FROM users WHERE user_id=?", (uid,))
        current = cursor.fetchone()[0]
        new_points = max(0, current - pts)
        cursor.execute("UPDATE users SET points=? WHERE user_id=?", (new_points, uid))
        conn.commit()
        bot.send_message(message.chat.id,f"✅ Removed {pts} Points from {uid}")
    except:
        bot.send_message(message.chat.id,"Usage: /removebalance user_id points")

# ===== REDEEM =====
@bot.message_handler(func=lambda m: True)
def handle_redeem(message):
    user_id = message.from_user.id
    text = message.text.lower()
    if not is_joined_all(user_id):
        bot.send_message(user_id,"❌ Join all channels first!")
        return

    pts = get_points(user_id)
    if "video" in text:
        if unlock_item(user_id,"video"):
            bot.send_message(user_id,"🎥 Setup Video Unlocked! ✅")
        else:
            bot.send_message(user_id,f"🚫 Not enough points! You have {pts} Points, need 5")
    elif "file" in text:
        if unlock_item(user_id,"file"):
            bot.send_message(user_id,"📁 Setup File Unlocked! ✅")
        else:
            bot.send_message(user_id,f"🚫 Not enough points! You have {pts} Points, need 10")
    elif "paid" in text:
        bot.send_message(user_id,f"💰 Paid Access:\nContact Admin: @{ADMIN_ID}")
    else:
        bot.send_message(user_id,"Use keywords: video, file, paid")

# ===== RUN BOT =====
print("Bot Running...")
bot.infinity_polling()
