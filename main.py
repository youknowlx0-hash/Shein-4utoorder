import telebot
from telebot import types
import json, os
from config import ADMINS, CHANNELS, POINTS_FOR_VIDEO, POINTS_FOR_FILE

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
bot = telebot.TeleBot(BOT_TOKEN)

# ---------------- FILE SYSTEM ----------------
def load(file, default):
    if not os.path.exists(file):
        with open(file,"w") as f:
            json.dump(default,f)
    with open(file) as f:
        return json.load(f)

def save(file,data):
    with open(file,"w") as f:
        json.dump(data,f,indent=2)

users = load("users.json", {})
admin_state = {}
items = load("items.json", {"file": None, "video": None})

# ---------------- USER SYSTEM ----------------
def get_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {
            "balance":0,
            "refers":[],
            "referred_by":None,
            "redeemed_file":0,
            "redeemed_video":0
        }
        save("users.json", users)
    return users[uid]

def is_admin(uid):
    return int(uid) in ADMINS

# ---------------- CHANNEL CHECK ----------------
def check_join(uid):
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch, uid)
            if member.status in ["left","kicked"]:
                return False
        except:
            return False
    return True

def force_join(chat_id):
    kb = types.InlineKeyboardMarkup()
    for ch in CHANNELS:
        kb.add(types.InlineKeyboardButton(
            f"Join {ch}",
            url=f"https://t.me/{ch.replace('@','')}"
        ))
    kb.add(types.InlineKeyboardButton("I Joined", callback_data="verify"))
    bot.send_message(chat_id,"Please join all channels:", reply_markup=kb)

# ---------------- MENU ----------------
def menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Profile","Refer")
    kb.row("File","Video")
    kb.row("Paid Access","Help")
    bot.send_message(chat_id,"Bot Ready",reply_markup=kb)

# ---------------- START ----------------
@bot.message_handler(commands=["start"])
def start(m):
    uid = str(m.from_user.id)
    user = get_user(uid)
    args = m.text.split()

    if not check_join(m.from_user.id):
        force_join(m.chat.id)
        return

    # Referral Logic
    if len(args) > 1:
        ref_id = args[1]
        if ref_id != uid and user["referred_by"] is None:
            ref_user = get_user(ref_id)
            if uid not in ref_user["refers"]:
                user["referred_by"] = ref_id
                ref_user["refers"].append(uid)
                ref_user["balance"] += 1
                save("users.json", users)
                try:
                    bot.send_message(
                        int(ref_id),
                        f"New Referral! {m.from_user.first_name} joined. +1 Point"
                    )
                except: pass
    save("users.json", users)
    menu(m.chat.id)

# ---------------- VERIFY ----------------
@bot.callback_query_handler(func=lambda c:c.data=="verify")
def verify(c):
    if check_join(c.from_user.id):
        bot.answer_callback_query(c.id,"Verified")
        menu(c.from_user.id)
    else:
        bot.answer_callback_query(c.id,"Join all channels",True)

# ---------------- JOIN DECORATOR ----------------
def join_required(func):
    def wrapper(m):
        if not check_join(m.from_user.id):
            force_join(m.chat.id)
            return
        return func(m)
    return wrapper

# ---------------- PROFILE ----------------
@bot.message_handler(func=lambda m:m.text=="Profile")
@join_required
def profile(m):
    u = get_user(m.from_user.id)
    bot.send_message(
        m.chat.id,
        f"Profile\n\nBalance: {u['balance']}\nRefers: {len(u['refers'])}\n"
        f"Redeemed File: {u['redeemed_file']}\nRedeemed Video: {u['redeemed_video']}\n\n"
        f"Referral Link:\nhttps://t.me/{bot.get_me().username}?start={m.from_user.id}"
    )

# ---------------- REFER ----------------
@bot.message_handler(func=lambda m:m.text=="Refer")
@join_required
def refer(m):
    bot.send_message(
        m.chat.id,
        f"Your referral link:\nhttps://t.me/{bot.get_me().username}?start={m.from_user.id}"
    )

# ---------------- FILE ----------------
@bot.message_handler(func=lambda m:m.text=="File")
@join_required
def file_unlock(m):
    u = get_user(m.from_user.id)
    if u['balance'] < POINTS_FOR_FILE:
        bot.send_message(m.chat.id,f"Not enough points. Need {POINTS_FOR_FILE} points")
        return
    if not items.get("file"):
        bot.send_message(m.chat.id,"File not uploaded yet by admin")
        return
    u['balance'] -= POINTS_FOR_FILE
    u['redeemed_file'] += 1
    save("users.json", users)
    bot.send_document(m.from_user.id, items["file"])
    bot.send_message(m.chat.id,"File unlocked!")

# ---------------- VIDEO ----------------
@bot.message_handler(func=lambda m:m.text=="Video")
@join_required
def video_unlock(m):
    u = get_user(m.from_user.id)
    if u['balance'] < POINTS_FOR_VIDEO:
        bot.send_message(m.chat.id,f"Not enough points. Need {POINTS_FOR_VIDEO} points")
        return
    if not items.get("video"):
        bot.send_message(m.chat.id,"Video not uploaded yet by admin")
        return
    u['balance'] -= POINTS_FOR_VIDEO
    u['redeemed_video'] += 1
    save("users.json", users)
    bot.send_video(m.from_user.id, items["video"])
    bot.send_message(m.chat.id,"Video unlocked!")

# ---------------- PAID ACCESS ----------------
@bot.message_handler(func=lambda m:m.text=="Paid Access")
def paid_access(m):
    bot.send_message(m.chat.id,f"Contact admin for paid access: {', '.join([str(a) for a in ADMINS])}")

# ---------------- HELP ----------------
@bot.message_handler(func=lambda m:m.text=="Help")
def help_cmd(m):
    bot.send_message(
        m.chat.id,
        "HELP:\n\n"
        "Profile - Check your points, referrals, redeemed items.\n"
        "Refer - Share your referral link to earn points.\n"
        "File - Unlock file using points (10 points).\n"
        "Video - Unlock setup/tutorial video using points (5 points).\n"
        "Paid Access - Contact admin for paid file/video.\n"
        "Help - Show this message.\n\n"
        "Join all channels before using features!"
    )

# ---------------- ADMIN PANEL ----------------
@bot.message_handler(commands=["adminpanel"])
def adminpanel(m):
    if not is_admin(m.from_user.id): return
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Add Balance","Remove Balance")
    kb.row("Top 10 Leaderboard","Add Video")
    bot.send_message(m.chat.id,"Admin Panel",reply_markup=kb)

# ---------------- ADMIN ACTIONS ----------------
@bot.message_handler(func=lambda m:m.from_user.id in ADMINS)
def admin_actions(m):
    text = m.text.lower()
    if text=="add balance":
        admin_state[m.from_user.id]="ADD"
        bot.send_message(m.chat.id,"Send: USER_ID AMOUNT")
    elif text=="remove balance":
        admin_state[m.from_user.id]="REM"
        bot.send_message(m.chat.id,"Send: USER_ID AMOUNT")
    elif text=="add video":
        admin_state[m.from_user.id]="VID"
        bot.send_message(m.chat.id,"Send video to upload for users")
    elif text=="top 10 leaderboard":
        leaderboard = sorted(users.items(), key=lambda x:x[1]['balance'], reverse=True)[:10]
        msg = "Top 10 Users:\n"
        for u in leaderboard:
            msg += f"{u[0]} - Points: {u[1]['balance']}\n"
        bot.send_message(m.chat.id,msg)

@bot.message_handler(func=lambda m:m.from_user.id in admin_state)
def admin_input(m):
    state = admin_state[m.from_user.id]
    try:
        if state=="ADD":
            uid,amt=m.text.split()
            get_user(uid)['balance'] += int(amt)
            save("users.json", users)
            bot.send_message(m.chat.id,"Balance added!")
        elif state=="REM":
            uid,amt=m.text.split()
            get_user(uid)['balance'] = max(0,get_user(uid)['balance']-int(amt))
            save("users.json", users)
            bot.send_message(m.chat.id,"Balance removed!")
        elif state=="VID":
            if m.content_type=="video":
                items["video"] = m.video.file_id
                save("items.json", items)
                bot.send_message(m.chat.id,"Video uploaded!")
            else:
                bot.send_message(m.chat.id,"Please send a video!")
    except:
        bot.send_message(m.chat.id,"Error: check format")
    admin_state.pop(m.from_user.id)

# ---------------- RUN BOT ----------------
print("Bot Running...")
bot.infinity_polling()
