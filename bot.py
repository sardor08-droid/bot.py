import sqlite3
import logging
import telebot
import json
import os
from datetime import datetime
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
from flask_cors import CORS

# Xatolarni professional darajada kuzatish (Logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ⚙️ ASOSIY STRUKTURAVIY SOZLAMALAR
BOT_TOKEN = "8471799836:AAHmSZYDxF84XY_Klx3Y4gUU4Kkzs2oZdxE"
ADMIN_ID = 7977733681  # Sardorbek - Imperator ID raqami

# Webhook ishlashi uchun threaded=False bo'lishi shart!
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# 🌐 GLOBAL TARMOQ SOZLAMALARI
CONFIG = {\
    "web_app_url": "https://sardor08-droid.github.io/nova-store/",
    "channel_url": "https://t.me/Sardor_shop_uz_bot",
    "start_photo": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe"\
}

# 🗄️ MA'LUMOTLAR OMBORI
def init_db():
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            balance INTEGER DEFAULT 0,
            spent INTEGER DEFAULT 0,
            joined_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            product_id TEXT PRIMARY KEY,
            name TEXT,
            stock INTEGER DEFAULT 0,
            price INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_label TEXT,
            target_user TEXT,
            price INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Baza bilan ishlash uchun xavfsiz funksiyalar
def db_add_user(user_id, username, name):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, name, joined_at) VALUES (?, ?, ?, ?)",
                   (user_id, username, name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    cursor.execute("UPDATE users SET username = ?, name = ? WHERE user_id = ?", (username, name, user_id))
    conn.commit()
    conn.close()

def db_get_user(user_id):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, name, balance, spent FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "name": row[2], "balance": row[3], "spent": row[4]}
    return None

def db_get_user_by_username(username):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    # Katta-kichik harflarni farqlamay qidirish uchun LIKE ishlatamiz
    cursor.execute("SELECT user_id FROM users WHERE username LIKE ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def db_update_balance(user_id, amount):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def db_create_order(user_id, label, target, price):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, product_label, target_user, price, created_at) VALUES (?, ?, ?, ?, ?)",
                   (user_id, label, target, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    o_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return o_id

# ⚡️ FLASK BACKEND SERVER (WEBHOOK & API HUB)
app = Flask(__name__)
CORS(app)

@app.route("/", methods=['GET'])
def index_route():
    return "<h1>Nova Store Quantum Core Online</h1>", 200

# TELEGRAM WEBHOOK MANZILI
@app.route("/" + BOT_TOKEN, methods=['POST'])
def get_message():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '', 200
    return '', 403

# 💎 JONLI FOYDALANUVCHI STATISTIKASI API SI
@app.route("/api/user-data", methods=['POST', 'OPTIONS'])
def get_user_data_api():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    try:
        data = request.get_json() or {}
        u_id = data.get("user_id")
        user_info = db_get_user(u_id)
        if user_info:
            return jsonify({"success": True, "user": user_info}), 200
        return jsonify({"success": False, "message": "Foydalanuvchi topilmadi"}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# 🔎 FOYDALANUVCHINI USERNAME ORQALI HAQIQIY TEKSHIRUVCHI API
@app.route("/api/verify-user", methods=['POST', 'OPTIONS'])
def verify_user_api():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    try:
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        
        if not username:
            return jsonify({"success": False, "message": "Username kiritilmadi!"}), 400

        # Baza orqali qidiramiz
        target_uid = db_get_user_by_username(username)
        
        if target_uid:
            target_info = db_get_user(target_uid)
            if target_info:
                return jsonify({
                    "success": True, 
                    "username": username,
                    "name": target_info["name"]
                }), 200
                
        return jsonify({"success": False, "message": "Bu foydalanuvchi bot ro'yxatida yo'q! Avval botga kirib /start bosishi kerak."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# 🤖 TELEGRAM BOT KODLARI BOSHLANISHI
@bot.message_handler(commands=['start'])
def send_welcome(message):
    u_id = message.from_user.id
    u_name = message.from_user.first_name
    u_user = message.from_user.username or ""
    
    # Bazaga yozish/yangilash
    db_add_user(u_id, u_user, u_name)
    
    # VIP Menyu tugmalari
    markup = InlineKeyboardMarkup()
    btn1 = InlineKeyboardButton("🛍️ Do'konni ochish", web_app=telebot.types.WebAppInfo(url=CONFIG["web_app_url"]))
    btn2 = InlineKeyboardButton("💳 Balansni to'ldirish", callback_data="deposit_panel")
    btn3 = InlineKeyboardButton("📊 Mening profilim", callback_data="my_profile")
    markup.add(btn1)
    markup.add(btn2, btn3)
    
    caption = f"✨ **Salom, {u_name}! Nova Store do'koniga xush kelibsiz!**\n\n" \
              f"Bu yerda siz Telegram Stars va Premium obunalarini eng arzon narxlarda xarid qilishingiz mumkin. " \
              f"Pastdagi tugma orqali do'konimizni oching!"
              
    bot.send_photo(message.chat.id, CONFIG["start_photo"], caption=caption, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    u_id = call.from_user.id
    user_info = db_get_user(u_id)
    if not user_info:
        bot.answer_callback_query(call.id, "Iltimos, avval /start bosing!", show_alert=True)
        return

    if call.data == "my_profile":
        text = f"👤 **Sizning Profilingiz:**\n\n" \
               f"🆔 Telegram ID: `{user_info['user_id']}`\n" \
               f"📝 Ismingiz: {user_info['name']}\n" \
               f"💎 Username: @{user_info['username'] if user_info['username'] else 'Yoq'}\n" \
               f"💰 Balans: {user_info['balance']:,} so'm\n" \
               f"🛒 Sarflangan mablag': {user_info['spent']:,} so'm"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        
    elif call.data == "deposit_panel":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ To'lovni tasdiqlash (Skrinshot yuborish)", callback_data="send_receipt"))
        text = f"💳 **Hisobni to'ldirish uchun to'lov ma'lumotlari:**\n\n" \
               f"📍 Karta raqami: `8600123456789012` (Sardorbek M.)\n" \
               f"💵 To'lov miqdorini o'zingiz belgilang.\n\n" \
               f"⚠️ *To'lovni amalga oshirib, chekni (skrinshot) pastdagi tugma orqali adminga yuboring.*"
        bot.send_message(call.message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)
        
    elif call.data == "send_receipt":
        msg = bot.send_message(call.message.chat.id, "📸 Iltimos, to'lov cheki skrinshotini rasmini yuboring:")
        bot.register_next_step_handler(msg, process_receipt)
        bot.answer_callback_query(call.id)

def process_receipt(message):
    if message.content_type != 'photo':
        bot.send_message(message.chat.id, "❌ Bu rasm emas. Iltimos, qaytadan urinib ko'ring yoki adminga yozing.")
        return
    
    # Admin tekshiruvi uchun yuboriladi
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Tasdiqlash (10k)", callback_data=f"accept_dep_{message.from_user.id}_10000"),
        InlineKeyboardButton("✅ (50k)", callback_data=f"accept_dep_{message.from_user.id}_50000")
    )
    markup.add(
        InlineKeyboardButton("✅ (100k)", callback_data=f"accept_dep_{message.from_user.id}_100000"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_dep_{message.from_user.id}")
    )
    
    bot.send_message(ADMIN_ID, f"🔔 **Yangi to'lov cheki keldi!**\nFoydalanuvchi: {message.from_user.first_name} (ID: {message.from_user.id})")
    bot.copy_message(ADMIN_ID, message.chat.id, message.message_id, reply_markup=markup)
    bot.send_message(message.chat.id, "⏳ Rahmat! To'lov cheki adminga yuborildi. Tez orada balansingiz to'ldiriladi.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('accept_dep_', 'reject_dep_')))
def handle_admin_decision(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Siz imperator emassiz! ❌", show_alert=True)
        return
        
    parts = call.data.split('_')
    action = parts[0]
    target_uid = int(parts[2])
    
    if action == "accept":
        amount = int(parts[3])
        db_update_balance(target_uid, amount)
        bot.send_message(target_uid, f"🎉 **Hisobingiz muvaffaqiyatli to'ldirildi!**\n💰 Qo'shildi: {amount:,} so'm.\nDo'konimizdan foydalanishingiz mumkin!")
        bot.edit_message_caption(f"✅ Tasdiqlandi: {amount:,} so'm yozildi.", call.message.chat.id, call.message.message_id)
    else:
        bot.send_message(target_uid, "❌ To'lovingiz admin tomonidan rad etildi. Muammo bo'lsa @Sardor_admin ga yozing.")
        bot.edit_message_caption("❌ To'lov rad etildi.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)

# 🛍️ MINI APP DAN KELGAN XARIDLARNI QABUL QILISH
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_data(message):
    try:
        u_id = message.from_user.id
        raw_data = message.web_app_data.data
        data = json.loads(raw_data)
        
        user_info = db_get_user(u_id)
        action = data.get("action")
        target = data.get("target", "")
        
        # Narxlarni aniqlash
        price = 0
        label = ""
        
        if action == "buy_premium":
            p_id = data.get("product_id")
            if p_id == "premium_3m":
                price, label = 150000, "Telegram Premium (3 Oylik)"
            elif p_id == "premium_6m":
                price, label = 280000, "Telegram Premium (6 Oylik)"
        elif action == "buy_custom_stars":
            amount = int(data.get("amount", 0))
            # Dinamik hisoblash yoki standart 380 so'm
            price = amount * 380
            label = f"{amount} Stars (Yulduzlar)"

        if price == 0:
            bot.send_message(message.chat.id, "❌ Noma'lum mahsulot turi!")
            return

        # Balans yetarliligini tekshirish
        if user_info["balance"] < price:
            bot.send_message(message.chat.id, f"❌ Xarid uchun mablag' yetarli emas!\n💵 Kerak: {price:,} so'm\n💰 Sizda: {user_info['balance']:,} so'm\nIltimos, avval hisobingizni to'ldiring.")
            return

        # Hisobdan yechish va buyurtma yaratish
        conn = sqlite3.connect("store_management.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET balance = balance - ?, spent = spent + ? WHERE user_id = ?", (price, price, u_id))
        cursor.execute("INSERT INTO orders (user_id, product_label, target_user, price, created_at) VALUES (?, ?, ?, ?, ?)",
                       (u_id, label, target, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Mijozga xabar
        bot.send_message(message.chat.id, f"✅ **Buyurtma qabul qilindi!**\n\n📦 Mahsulot: {label}\n👤 Kimga: {target}\n💵 Narxi: {price:,} so'm\n🆔 Buyurtma ID: #{order_id}\n\nTez orada admin xizmatni faollashtiradi!")
        
        # Adminga buyurtma paneli
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("✅ Bajarildi", callback_data=f"order_done_{order_id}_{u_id}"),
            InlineKeyboardButton("❌ Bekor qilish (Pulni qaytarish)", callback_data=f"order_cancel_{order_id}_{u_id}")
        )
        
        bot.send_message(ADMIN_ID, f"🛍️ **YANGI BUYURTMA KELDI!**\n\n🆔 ID: #{order_id}\n👤 Kimdan: {user_info['name']} (ID: {u_id})\n📦 Xizmat: {label}\n🎯 Kimga (Target): {target}\n💵 Summa: {price:,} so'm", reply_markup=markup)

    except Exception as e:
        bot.send_message(message.chat.id, f"🚨 Tizimda xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('order_done_', 'order_cancel_')))
def handle_order_status(call):
    if call.from_user.id != ADMIN_ID:
        return
        
    parts = call.data.split('_')
    action = parts[1]
    order_id = int(parts[2])
    client_uid = int(parts[3])
    
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    
    if action == "done":
        cursor.execute("UPDATE orders SET status = 'completed' WHERE order_id = ?", (order_id,))
        conn.commit()
        bot.send_message(client_uid, f"🚀 **Xushxabar! #{order_id}-sonli buyurtmangiz muvaffaqiyatli bajarildi!**\nSiz kiritgan profilni tekshirib ko'ring. Bizni tanlaganingiz uchun rahmat!")
        bot.edit_message_text(f"✅ #{order_id}-sonli buyurtma bajarildi deb belgilandi.", call.message.chat.id, call.message.message_id)
    else:
        # Pulni qaytarish uchun avval buyurtma narxini bilib olamiz
        cursor.execute("SELECT price, product_label FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        if row:
            refund_price = row[0]
            cursor.execute("UPDATE orders SET status = 'canceled' WHERE order_id = ?", (order_id,))
            cursor.execute("UPDATE users SET balance = balance + ?, spent = spent - ? WHERE user_id = ?", (refund_price, refund_price, client_uid))
            conn.commit()
            bot.send_message(client_uid, f"❌ **Sizning #{order_id}-sonli buyurtmangiz bekor qilindi.**\n💰 {refund_price:,} so'm mablag' balansingizga to'liq qaytarildi!")
            bot.edit_message_text(f"❌ #{order_id}-sonli buyurtma bekor qilindi va pul egasiga qaytarildi.", call.message.chat.id, call.message.message_id)
            
    conn.close()
    bot.answer_callback_query(call.id)

# ⚙️ OMBORELEMENTLARI (ADMIN UCHUN)
@bot.message_handler(commands=['panel'])
def admin_panel_main(message):
    if message.from_user.id != ADMIN_ID: return
    text = "👑 **Imperator Boshqaruv Paneli:**\n\n" \
           "💬 `/reklama` - Barcha foydalanuvchilarga xabar yuborish\n" \
           "➕ `/plus ID SUMMA` - Foydalanuvchiga pul qo'shish\n" \
           "➖ `/minus ID SUMMA` - Foydalanuvchidan pul ayirish\n" \
           "📦 `/tovar` - Omborga tovar kiritish (Format: ID|NOMI|SONI|NARXI)"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['reklama'])
def start_broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    msg = bot.send_message(message.chat.id, "📢 Reklama xabarini matn, rasm yoki video ko'rinishida yuboring:")
    bot.register_next_step_handler(msg, process_admin_broadcast)

def process_admin_broadcast(message):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    all_users = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    count = 0
    bot.send_message(ADMIN_ID, "⏳ Reklama tarqatilmoqda, kuting...")
    
    for u_id in all_users:
        if u_id == ADMIN_ID: continue
        try:
            bot.copy_message(chat_id=u_id, from_chat_id=ADMIN_ID, message_id=message.message_id)
            count += 1
        except:
            continue
    bot.send_message(ADMIN_ID, f"✅ Reklama tarqatish yakunlandi! {count} ta faol foydalanuvchiga yetkazildi.")

@bot.message_handler(commands=['plus'])
def admin_plus_money(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, target_id, money = message.text.split()
        db_update_balance(int(target_id), int(money))
        bot.send_message(message.chat.id, f"✅ ID: {target_id} ga {int(money):,} so'm qo'shildi!")
        bot.send_message(int(target_id), f"💸 Hisobingiz admin tomonidan {int(money):,} so'mga to'ldirildi!")
    except:
        bot.send_message(message.chat.id, "❌ Format xato! Masalan: `/plus 7977733681 50000`")

@bot.message_handler(commands=['minus'])
def admin_minus_money(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, target_id, money = message.text.split()
        db_update_balance(int(target_id), -int(money))
        bot.send_message(message.chat.id, f"✅ ID: {target_id} dan {int(money):,} so'm ayirildi!")
    except:
        bot.send_message(message.chat.id, "❌ Format xato! Masalan: `/minus 7977733681 20000`")

@bot.message_handler(commands=['tovar'])
def add_inventory_item(message):
    if message.from_user.id != ADMIN_ID: return
    msg = bot.send_message(message.chat.id, "Formatni kiriting (p_id|nomi|soni|narxi):")
    bot.register_next_step_handler(msg, process_inventory_add)

def process_inventory_add(message):
    try:
        p_id, name, stock, price = message.text.split('|')
        conn = sqlite3.connect("store_management.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO inventory (product_id, name, stock, price) VALUES (?, ?, ?, ?)",
                       (p_id.strip(), name.strip(), int(stock), int(price)))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, "✅ Tovar omborga muvaffaqiyatli qo'shildi!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Xato! Formatni noto'g'ri kiritgansiz: {e}")

# 🚀 SERVERNI ISHGA TUSHIRISH (RENDER REJIMIGA MOS)
if __name__ == "__main__":
    # Webhookni tozalash va qayta o'rnatish
    bot.remove_webhook()
    # Render avtomat port beradi, bo'lmasa 5000 portda ishlaydi
    server_port = int(os.environ.get('PORT', 5000))
    
    try:
        # Webhook o'rnatish URL manzilini Render havolangiz bilan bog'laymiz
        bot.set_webhook(url="https://bot-py-15ln.onrender.com/" + BOT_TOKEN)
        logging.info("Webhook muvaffaqiyatli o'rnatildi!")
    except Exception as e:
        logging.error(f"Webhook o'rnatishda xatolik: {e}")

    app.run(host="0.0.0.0", port=server_port)

