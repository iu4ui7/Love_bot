
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3

API_TOKEN = '7748147189:AAFojk85jB-haF_-u000U2JQ2I_kfhjfH8'
bot = telebot.TeleBot(API_TOKEN)

# إنشاء اتصال بالقاعدة
def get_db():
    conn = sqlite3.connect("love_baghdad_bot.db", check_same_thread=False)
    return conn, conn.cursor()

# بدء التسجيل
@bot.message_handler(commands=['start'])
def start(message):
    conn, cur = get_db()
    cur.execute("INSERT OR IGNORE INTO users (telegram_id, step) VALUES (?, ?)", (message.chat.id, "name"))
    conn.commit()
    bot.send_message(message.chat.id, "أهلاً بيك في Love Baghdad! شنو اسمك؟")

# استلام الاسم
@bot.message_handler(func=lambda m: True)
def collect_info(message):
    conn, cur = get_db()
    cur.execute("SELECT step FROM users WHERE telegram_id = ?", (message.chat.id,))
    result = cur.fetchone()
    if not result:
        return
    step = result[0]

    if step == "name":
        cur.execute("UPDATE users SET name = ?, step = ? WHERE telegram_id = ?", (message.text, "gender", message.chat.id))
        conn.commit()
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("ذكر", callback_data="gender_m"), InlineKeyboardButton("أنثى", callback_data="gender_f"))
        bot.send_message(message.chat.id, "اختار جنسك:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("gender_"))
def set_gender(call):
    gender = call.data.split("_")[1]
    conn, cur = get_db()
    cur.execute("UPDATE users SET gender = ?, step = ? WHERE telegram_id = ?", (gender, "photo", call.from_user.id))
    conn.commit()
    bot.send_message(call.from_user.id, "أرسل صورتك الشخصية (صورة وحدة فقط).")

@bot.message_handler(content_types=['photo'])
def receive_photo(message):
    conn, cur = get_db()
    cur.execute("SELECT step FROM users WHERE telegram_id = ?", (message.chat.id,))
    result = cur.fetchone()
    if result and result[0] == "photo":
        file_id = message.photo[-1].file_id
        cur.execute("UPDATE users SET photo_file_id = ?, step = ? WHERE telegram_id = ?", (file_id, "done", message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, "تم حفظ ملفك! اكتب /browse لتشوف ناس غيرك.")

@bot.message_handler(commands=['browse'])
def browse_users(message):
    conn, cur = get_db()
    cur.execute("SELECT gender FROM users WHERE telegram_id = ?", (message.chat.id,))
    my_gender = cur.fetchone()
    if not my_gender:
        return bot.send_message(message.chat.id, "سجل أولاً باستخدام /start")

    # عرض أول شخص ما مسوي عليه لايك
    cur.execute("""
        SELECT u.telegram_id, u.name, u.photo_file_id
        FROM users u
        WHERE u.telegram_id != ?
        AND u.step = 'done'
        AND u.telegram_id NOT IN (
            SELECT to_user FROM likes WHERE from_user = ?
        )
        LIMIT 1
    """, (message.chat.id, message.chat.id))
    person = cur.fetchone()
    if person:
        uid, name, photo = person
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("أعجبني", callback_data=f"like_{uid}"),
            InlineKeyboardButton("تخطي", callback_data="pass")
        )
        bot.send_photo(message.chat.id, photo, caption=f"{name}", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "ماكو أحد حالياً، جرّب بعدين!")

@bot.callback_query_handler(func=lambda call: call.data.startswith("like_") or call.data == "pass")
def handle_likes(call):
    conn, cur = get_db()
    if call.data == "pass":
        bot.answer_callback_query(call.id, "تم التخطي.")
        browse_users(call.message)
        return

    liked_id = int(call.data.split("_")[1])
    user_id = call.from_user.id
    # نسجل اللايك
    cur.execute("INSERT INTO likes (from_user, to_user) VALUES (?, ?)", (user_id, liked_id))
    # هل الشخص الآخر معجب بيك؟
    cur.execute("SELECT 1 FROM likes WHERE from_user = ? AND to_user = ?", (liked_id, user_id))
    if cur.fetchone():
        cur.execute("UPDATE likes SET matched = 1 WHERE from_user = ? AND to_user = ?", (user_id, liked_id))
        cur.execute("UPDATE likes SET matched = 1 WHERE from_user = ? AND to_user = ?", (liked_id, user_id))
        bot.send_message(user_id, "صار تطابق! تقدر تبدي محادثة.")
        bot.send_message(liked_id, "صار تطابق! تقدر تبدي محادثة.")
    conn.commit()
    browse_users(call.message)

bot.polling()
