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
CONFIG = {
    "web_app_url": "https://sardor08-droid.github.io/nova-store/",
    "channel_url": "https://t.me/Sardor_shop_uz_bot",
    "start_photo": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe"
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
            spent_money INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            joined_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id TEXT,
            product_name TEXT,
            price_sum INTEGER,
            target_username TEXT,
            status TEXT DEFAULT 'Bajarildi',
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            product_id TEXT PRIMARY KEY,
            product_name TEXT,
            price_soem INTEGER,
            category TEXT DEFAULT 'Boshqa'
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    cursor.execute("INSERT OR IGNORE INTO global_settings (key, value) VALUES ('total_kassa', '0')")

    default_products = [
        ("stars_1", "1 dona Stars", 380, "Stars"),
        ("stars_50", "50 TG Stars", 19000, "Stars"),
        ("stars_100", "100 TG Stars", 38000, "Stars"),
        ("premium_3m", "Telegram Premium (3 Oylik)", 150000, "Premium"),
        ("premium_6m", "Telegram Premium (6 Oylik)", 280000, "Premium"),
        ("premium_12m", "Telegram Premium (1 Yillik)", 500000, "Premium"),
        ("pubg_60uc", "PUBG 60 UC", 15000, "PUBG"),
        ("pubg_325uc", "PUBG 325 UC", 70000, "PUBG")
    ]
    for p_id, p_name, p_price, p_cat in default_products:
        cursor.execute("INSERT OR IGNORE INTO inventory (product_id, product_name, price_soem, category) VALUES (?, ?, ?, ?)", (p_id, p_name, p_price, p_cat))

    conn.commit()
    conn.close()

# 🗄️ BAZA AMALIYOTLARI OPERATORLARI
def db_add_user(user_id, username, name):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, name, joined_at) VALUES (?, ?, ?, ?)", (user_id, username, name, now))
    cursor.execute("UPDATE users SET username = ?, name = ? WHERE user_id = ?", (username, name, user_id))
    conn.commit()
    conn.close()

def db_get_user(user_id):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, name, balance, banned, spent_money, joined_at FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "username": row[0], "name": row[1], "balance": row[2],
            "banned": bool(row[3]), "spent_money": row[4], "joined_at": row[5]
        }
    return None

def db_get_user_by_username(username):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    clean_username = username.replace("@", "").strip()
    cursor.execute("SELECT user_id FROM users WHERE username LIKE ? OR username LIKE ?", (f"%{clean_username}%", f"@{clean_username}"))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def db_get_user_orders(user_id):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT order_id, product_name, price_sum, target_username, status, created_at FROM orders WHERE user_id = ? ORDER BY order_id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def db_get_inventory():
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT product_id, product_name, price_soem, category FROM inventory")
    rows = cursor.fetchall()
    conn.close()
    products = {}
    for r in rows:
        products[r[0]] = {"name": r[1], "price": r[2], "category": r[3]}
    return products

def db_execute_purchase(user_id, product_id, product_name, price_sum, target):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    if not res or res[0] < price_sum:
        conn.close()
        return False, "Balans yetarli emas"

    cursor.execute("UPDATE users SET balance = balance - ?, spent_money = spent_money + ? WHERE user_id = ?", (price_sum, price_sum, user_id))
    cursor.execute("INSERT INTO orders (user_id, product_id, product_name, price_sum, target_username, status, created_at) VALUES (?, ?, ?, ?, ?, 'Bajarildi', ?)", 
                   (user_id, product_id, product_name, price_sum, target, now))
    cursor.execute("UPDATE global_settings SET value = CAST(value AS INTEGER) + ? WHERE key = 'total_kassa'", (price_sum,))
    
    cursor.execute("SELECT last_insert_rowid()")
    order_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return True, order_id

def db_get_stats():
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE banned = 1")
    banned_users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM inventory")
    total_products = cursor.fetchone()[0]
    cursor.execute("SELECT value FROM global_settings WHERE key = 'total_kassa'")
    kassa = int(cursor.fetchone()[0])
    conn.close()
    return total_users, banned_users, total_products, kassa

def db_update_user_balance(user_id, amount):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def db_set_ban(user_id, status):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET banned = ? WHERE user_id = ?", (1 if status else 0, user_id))
    conn.commit()
    conn.close()

# 🔄 DATABASE AUTO-BACKUP
def auto_backup_database():
    try:
        if os.path.exists("store_management.db"):
            with open("store_management.db", "rb") as f:
                bot.send_document(
                    chat_id=ADMIN_ID, 
                    document=f, 
                    caption=f"🗄 **AVTO-ZAXIRA (BACKUP)**\n⏰ Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n⚠️ Render o'chib ketsa, ushbu faylni qayta yuklash mumkin."
                )
    except Exception as e:
        logging.error(f"Backup xatolik: {e}")


# 🌐 FLASK WEB SERVER VA CORS INTEGRATSIYASI (404 VA 409 NING TO'LIQ YECHIMI)
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Telegram Webhook so'rovlarini qabul qiluvchi maxsus manzil
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    return "Xato manzil", 403

# Render asosiiy manzili - Webhook shu yerda avtomat ulanadi
@app.route('/')
def home():
    render_url = f"https://bot-py-15ln.onrender.com/{BOT_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=render_url)
    return "Imperator markazi (Webhook) muvaffaqiyatli ishlamoqda!", 200

# Mini App API manzillari
@app.route('/api/user-data', methods=['POST', 'OPTIONS'])
def get_mini_app_user_data():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
        
    try:
        data = request.get_json()
        if not data or 'user_id' not in data:
            return jsonify({"success": False, "message": "Identifikatsiya xatosi."}), 400
        
        u_id = int(data['user_id'])
        user_info = db_get_user(u_id)
        
        if not user_info:
            return jsonify({"success": False, "message": "Foydalanuvchi bot ro'yxatidan o'tmagan."}), 404
            
        if user_info['banned']:
            return jsonify({"success": False, "message": "Siz botdan bloklangansiz!"}), 403

        all_products = db_get_inventory()
        
        return jsonify({
            "success": True,
            "user": {
                "id": u_id,
                "name": user_info["name"],
                "username": user_info["username"],
                "balance": user_info["balance"],
                "spent": user_info["spent_money"]
            },
            "products": all_products
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Server xatoligi: {str(e)}"}), 500

@app.route('/api/verify-user', methods=['POST', 'OPTIONS'])
def verify_mini_app_user():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
    return jsonify({"success": True, "message": "Foydalanuvchi tasdiqlandi"}), 200

@app.route('/api/purchase', methods=['POST', 'OPTIONS'])
def process_mini_app_purchase():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'}), 200
        
    try:
        data = request.get_json()
        u_id = int(data.get('user_id'))
        p_id = data.get('product_id')
        target = data.get('target', "O'ziga")

        user_info = db_get_user(u_id)
        if not user_info or user_info['banned']:
            return jsonify({"success": False, "message": "Tranzaksiya taqiqlangan!"}), 403

        products = db_get_inventory()
        if p_id not in products:
            return jsonify({"success": False, "message": "Mahsulot omborda topilmadi!"}), 404

        product_item = products[p_id]
        price = product_item["price"]
        p_name = product_item["name"]

        success, result = db_execute_purchase(u_id, p_id, p_name, price, target)

        if success:
            order_id = result
            user_msg = (
                f"🥳 **Xarid muvaffaqiyatli yakunlandi!**\n=========================\n"
                f"🧾 **Chek №:** `{order_id}`\n📦 **Mahsulot:** {p_name}\n"
                f"💰 **Yechilgan mablag':** `{price:,} so'm`\n🎯 **Qabul qiluvchi:** `{target}`\n"
                f"⏰ **Vaqt:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"⚡️ Mahsulot tez orada yetkaziladi!"
            )
            try:
                bot.send_message(u_id, user_msg, parse_mode="Markdown")
            except Exception: pass

            admin_msg = (
                f"🚨 **YANGI BUYURTMA №{order_id}!**\n=========================\n"
                f"👤 **Mijoz:** {user_info['name']} ({u_id})\n"
                f"📦 **Tovar:** `{p_name}`\n💰 **Narxi:** `{price:,} so'm`\n"
                f"🎯 **Yuborish kerak:** `{target}`\n"
                f"⏰ **Vaqt:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            kb = InlineKeyboardMarkup()
            kb.add(
                InlineKeyboardButton("👤 Mijozni tekshirish", callback_data=f"crm_inspect_{u_id}"),
                InlineKeyboardButton("✅ Bajarildi deb belgilash", callback_data=f"crm_done_{order_id}")
            )
            bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown", reply_markup=kb)

            auto_backup_database()
            return jsonify({"success": True, "order_id": order_id, "new_balance": user_info["balance"] - price})
        else:
            return jsonify({"success": False, "message": result}), 400

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# 🟢 FOYDALANUVCHI QISMI
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
    first_name = message.from_user.first_name

    db_add_user(user_id, username, first_name)
    user_data = db_get_user(user_id)

    if user_data and user_data["banned"]:
        bot.send_message(user_id, "❌ Siz tizimdan bloklangansiz!")
        return

    timestamp = int(datetime.now().timestamp())
    dynamic_web_app_url = f"{CONFIG['web_app_url']}?user_id={user_id}&t={timestamp}"

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(text="🛍 Nova Store-ni ochish 🛍", web_app=telebot.types.WebAppInfo(url=dynamic_web_app_url)),
        InlineKeyboardButton(text="🔈 Yangiliklar kanali", url=CONFIG["channel_url"])
    )

    welcome_text = (
        f"👋 Salom **{first_name}**!\n\n"
        f"⭐️ **Nova Store** rasmiy botiga xush kelibsiz.\n"
        f"Do'konimiz butunlay yangilandi va to'liq **Mini App** tizimiga o'tkazildi.\n\n"
        f"👇 Xarid qilishni boshlash uchun pastdagi tugmani bosing!"
    )
    try:
        bot.send_photo(chat_id=user_id, photo=CONFIG["start_photo"], caption=welcome_text, parse_mode="Markdown", reply_markup=kb)
    except Exception:
        bot.send_message(user_id, welcome_text, parse_mode="Markdown", reply_markup=kb)


# 👑 IMPERATOR PANEL (ADMIN PANEL)
@bot.message_handler(commands=['admin'])
def super_admin_panel(message):
    if message.chat.id != ADMIN_ID: return
    
    total_users, banned_users, total_products, kassa = db_get_stats()

    admin_text = (
        f"👑 **IMPERATOR BOSHQARUV MARKAZI**\n"
        f"==================================\n\n"
        f"📊 **Umumiy statistika:**\n"
        f"👥 Jami mijozlar: `{total_users} ta`\n"
        f"🚫 Bloklanganlar: `{banned_users} ta`\n"
        f"📦 Tovar turlari: `{total_products} ta`\n"
        f"💰 Umumiy Kassa: `{kassa:,} so'm`\n\n"
        f"⚙️ Boshqarish uchun kerakli bo'limni tanlang:"
    )
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👤 CRM (Mijoz qidirish)", callback_data="pnl_user_inspect"),
        InlineKeyboardButton("💰 Moliya (Balans)", callback_data="pnl_balance_ctrl"),
        InlineKeyboardButton("📦 Omborxona (Inventory)", callback_data="pnl_inventory_ctrl"),
        InlineKeyboardButton("📢 Smart Reklama", callback_data="pnl_broadcast"),
        InlineKeyboardButton("🗄 Baza Zaxirasi (Backup)", callback_data="pnl_backup_now")
    )
    bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(commands=['backup'])
def manual_backup(message):
    if message.chat.id == ADMIN_ID:
        auto_backup_database()

@bot.callback_query_handler(func=lambda call: call.data.startswith("pnl_"))
def admin_sub_navigation(call):
    if call.message.chat.id != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    panel = call.data
    
    if panel == "pnl_user_inspect":
        msg = bot.send_message(ADMIN_ID, "🔍 Izlanayotgan mijozning **Telegram ID** yoki **@username**'ini kiriting:")
        bot.register_next_step_handler(msg, process_crm_user_inspect)
        
    elif panel == "pnl_balance_ctrl":
        msg = bot.send_message(ADMIN_ID, "💰 **Balansni o'zgartirish formatini kiriting:**\n`ID_RAQAMI | SUMMA`\n\n*Misol (Pul qo'shish):* `7977733681 | 50000`\n*Misol (Pul ayirish):* `7977733681 | -20000`")
        bot.register_next_step_handler(msg, process_admin_balance_change)
        
    elif panel == "pnl_inventory_ctrl":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("➕ Tovar Qo'shish", callback_data="inv_add"),
            InlineKeyboardButton("🗑️ Tovar O'chirish", callback_data="inv_del"),
            InlineKeyboardButton("📋 Tovar Ro'yxati", callback_data="inv_view_list")
        )
        bot.send_message(ADMIN_ID, "📦 **Omborxonani boshqarish:**", reply_markup=kb)
        
    elif panel == "pnl_broadcast":
        msg = bot.send_message(ADMIN_ID, "📢 **Barcha foydalanuvchilarga yuboriladigan postni yuboring:**\n(Bu yerda rasm, video, matn yoki inline tugmali tayyor xabar bo'lishi mumkin)")
        bot.register_next_step_handler(msg, process_admin_broadcast)
        
    elif panel == "pnl_backup_now":
        auto_backup_database()
        bot.send_message(ADMIN_ID, "✅ Ma'lumotlar bazasi zaxiralandi.")

# 👤 CRM INTERFEJSI
def process_crm_user_inspect(message):
    try:
        input_data = message.text.strip()
        if input_data.isdigit():
            target_id = int(input_data)
        else:
            target_id = db_get_user_by_username(input_data)
            
        if not target_id:
            bot.send_message(ADMIN_ID, "❌ Bunday foydalanuvchi ma'lumotlar bazasidan topilmadi!")
            return
            
        user_info = db_get_user(target_id)
        orders = db_get_user_orders(target_id)
        
        history_text = ""
        if orders:
            for index, order in enumerate(orders[:15], 1):
                history_text += f"{index}. 📦 {order[1]} | `{order[2]:,}` so'm | {order[3]} | {order[5]}\n"
        else:
            history_text = "🤷‍♂️ Xaridlar tarixi mavjud emas."

        inspect_response = (
            f"👤 **MIJOZ PROFILLI (CRM 360°):**\n"
            f"==================================\n"
            f"🆔 **Telegram ID:** `{target_id}`\n"
            f"🏷 **Ism:** {user_info['name']}\n"
            f"🌐 **Username:** {user_info['username']}\n"
            f"📅 **Qo'shilgan vaqti:** `{user_info['joined_at']}`\n"
            f"🚫 **Holati:** {'🔴 Bloklangan' if user_info['banned'] else '🟢 Faol'}\n"
            f"==================================\n"
            f"💰 **Joriy Balans:** `{user_info['balance']:,} so'm`\n"
            f"💸 **Jami xarid qilgan summasi:** `{user_info['spent_money']:,} so'm`\n\n"
            f"🛒 **Oxirgi xaridlari:**\n{history_text}"
        )
        
        kb = InlineKeyboardMarkup()
        act = "unban" if user_info['banned'] else "ban"
        txt = "🟢 Blokdan ochish" if user_info['banned'] else "🔴 Bloklash"
        kb.add(
            InlineKeyboardButton(txt, callback_data=f"crmaction_{act}_{target_id}"),
            InlineKeyboardButton("💰 Balansni boshqarish", callback_data=f"crmaction_bal_{target_id}")
        )
        bot.send_message(ADMIN_ID, inspect_response, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Qidiruvda xatolik: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("crm_"))
def handle_quick_crm_actions(call):
    if call.message.chat.id != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    parts = call.data.split("_")
    action = parts[1]
    
    if action == "inspect":
        uid = int(parts[2])
        msg = call.message
        msg.text = str(uid)
        process_crm_user_inspect(msg)
    elif action == "done":
        order_id = parts[2]
        bot.edit_message_caption(chat_id=ADMIN_ID, message_id=call.message.message_id, caption=call.message.caption + "\n\n✅ **BU BUYURTMA SARDORBEK TOMONIDAN BAJARILDI!**")

@bot.callback_query_handler(func=lambda call: call.data.startswith("crmaction_"))
def handle_crm_deep_actions(call):
    if call.message.chat.id != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    _, action, uid = call.data.split("_")
    uid = int(uid)
    
    if action == "ban":
        db_set_ban(uid, True)
        bot.send_message(ADMIN_ID, f"✅ ID: {uid} muvaffaqiyatli bloklandi!")
        try: bot.send_message(uid, "❌ Siz bot ma'muriyati tomonidan tizimdan bloklandingiz!")
        except Exception: pass
    elif action == "unban":
        db_set_ban(uid, False)
        bot.send_message(ADMIN_ID, f"✅ ID: {uid} blokdan ochildi!")
        try: bot.send_message(uid, "🟢 Sizning profilingiz blokdan ochildi. Do'kondan foydalanishingiz mumkin!")
        except Exception: pass
    elif action == "bal":
        msg = bot.send_message(ADMIN_ID, f"💰 ID: `{uid}` uchun o'zgaruvchi summani yozing (Masalan: `25000`):")
        bot.register_next_step_handler(msg, lambda m: process_direct_balance(m, uid))

def process_direct_balance(message, uid):
    try:
        amount = int(message.text.strip())
        db_update_user_balance(uid, amount)
        bot.send_message(ADMIN_ID, f"✅ ID: {uid} balansiga {amount:,} so'm kiritildi!")
        try: bot.send_message(uid, f"💰 Botingiz balansi ma'muriyat tomonidan yangilandi: `{amount:,} so'm`")
        except Exception: pass
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Xato kiritish: {e}")

# 💰 MOLIYA BOSHQARUVI
def process_admin_balance_change(message):
    try:
        parts = message.text.split("|")
        t_id = int(parts[0].strip())
        amount = int(parts[1].strip())
        db_update_user_balance(t_id, amount)
        bot.send_message(ADMIN_ID, f"✅ Muvaffaqiyatli! ID: {t_id} balansiga {amount:,} so'm qo'shildi/ayrildi!")
        try: bot.send_message(t_id, f"💰 Botingiz balansi admin tomonidan o'zgartirildi: `{amount:,} so'm`")
        except Exception: pass
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Xato format format: {e}")

# 📦 OMBORXONA BOSHQARUVI
@bot.callback_query_handler(func=lambda call: call.data.startswith("inv_"))
def inventory_actions_handler(call):
    if call.message.chat.id != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    action = call.data
    
    if action == "inv_view_list":
        current_inv = db_get_inventory()
        text = "📋 **Omborxonada mavjud tovarlar ro'yxati:**\n==================================\n\n"
        for key, info in current_inv.items():
            text += f"🔑 **ID:** `{key}`\n📦 **Nomi:** *{info['name']}*\n💰 **Narxi:** `{info['price']:,} so'm`\n🗂 **Toifa:** `{info['category']}`\n----------------------------------\n"
        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
        
    elif action == "inv_add":
        msg = bot.send_message(ADMIN_ID, "Formatni kiriting: `id | Nomi | Narxi | Toifa` \n\n*Misol:* `stars_500 | 500 dona Stars | 190000 | Stars`")
        bot.register_next_step_handler(msg, process_inventory_add_item)
        
    elif action == "inv_del":
        msg = bot.send_message(ADMIN_ID, "🗑️ O'chirish demoqchi bo'lgan tovarning **ID** kodini yozing:")
        bot.register_next_step_handler(msg, process_inventory_del_item)

def process_inventory_add_item(message):
    try:
        parts = message.text.split("|")
        p_id = parts[0].strip()
        p_name = parts[1].strip()
        p_price = int(parts[2].strip())
        p_cat = parts[3].strip() if len(parts) > 3 else "Boshqa"
        
        conn = sqlite3.connect("store_management.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO inventory (product_id, product_name, price_soem, category) VALUES (?, ?, ?, ?)", (p_id, p_name, p_price, p_cat))
        conn.commit()
        conn.close()
        
        bot.send_message(ADMIN_ID, f"✅ Mahsulot omborga muvaffaqiyatli qo'shildi!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Xato! Formatni noto'g'ri kiritgansiz: {e}")

def process_inventory_del_item(message):
    try:
        p_id = message.text.strip()
        conn = sqlite3.connect("store_management.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM inventory WHERE product_id = ?", (p_id,))
        conn.commit()
        conn.close()
        bot.send_message(ADMIN_ID, "✅ Tovar omborxonadan butunlay o'chirildi!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ O'chirishda xatolik: {e}")

# 📢 SMART REKLAMA
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
        except Exception:
            continue
            
    bot.send_message(ADMIN_ID, f"✅ Reklama muvaffaqiyatli {count} ta faol mijozga yetkazildi!")


init_db()

# 🚀 RENDER TIZIMI UCHUN TO'G'RI CHIQISH (THREADING VA POLLINGSISZ)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

