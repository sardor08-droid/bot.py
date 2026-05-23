import sqlite3
import logging
import telebot
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, jsonify
from flask_cors import CORS

# Xatolarni professional darajada konsolda kuzatish (Logging)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ⚙️ ASOSIY STRUKTURAVIY SOZLAMALAR
BOT_TOKEN = "8471799836:AAFnQAaMk0GFaL-G6jGk41eaEcdI4HnB4Ck"
ADMIN_ID = 7977733681  # Sardorbek - Sening shaxsiy imperatorlik ID raqaming

bot = telebot.TeleBot(BOT_TOKEN)

# 🌐 GLOBAL TARMOQ SOZLAMALARI
CONFIG = {
    "web_app_url": "https://sardor08-droid.github.io/nova-store/",
    "channel_url": "https://t.me/Sardor_shop_uz_bot",
    "start_photo": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe"
}

# 🌐 FLASK WEB SERVER VA CORS INTEGRATSIYASI (GITHUB UCHUN TO'LIQ RUXSAT)
app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["POST", "GET", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

@app.route('/')
def home():
    return "Bot muvaffaqiyatli ishlamoqda!", 200

@app.route('/api/verify-user', methods=['POST'])
def verify_telegram_user():
    try:
        data = request.get_json()
        if not data or 'username' not in data:
            return jsonify({"success": False, "message": "Username kiritilmagan."}), 400

        username_input = data['username'].replace("@", "").strip()

        if len(username_input) < 4:
            return jsonify({"success": False, "message": "Username xato kiritildi!"})

        # 🌐 Telegram Web sahifasidan foydalanuvchi ma'lumotlarini qidirish (Proksisiz)
        url = f"https://t.me/{username_input}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title_element = soup.find("meta", property="og:title")

            if title_element and title_element.get("content"):
                display_name = title_element.get("content")

                if "Telegram: Contact" in display_name or display_name.strip() == "":
                    return jsonify({"success": False, "message": f"@{username_input} bunday foydalanuvchi topilmadi!"})

                return jsonify({
                    "success": True,
                    "user": {
                        "id": 111222333,
                        "first_name": display_name,
                        "username": username_input
                    }
                })
            else:
                return jsonify({"success": False, "message": "Foydalanuvchi topilmadi."})
        else:
            return jsonify({"success": False, "message": "Telegram serveriga ulanishda xatolik."})

    except Exception as e:
        return jsonify({"success": False, "message": "Server xatoligi yuz berdi."}), 500


# 🗄️ MUSTAHKAM SQLITE MA'LUMOTLAR OMBORI
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
            price_soem INTEGER
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
        ("stars_1", "1 dona Stars narxi", 380),
        ("premium_3m", "Telegram Premium (3 Oylik)", 150000),
        ("premium_6m", "Telegram Premium (6 Oylik)", 280000),
        ("premium_12m", "Telegram Premium (1 Yillik)", 500000),
        ("pubg_60uc", "PUBG 60 UC", 15000),
        ("pubg_325uc", "PUBG 325 UC", 70000),
        ("stars_50", "50 TG Stars", 20000),
        ("stars_100", "100 TG Stars", 38000)
    ]
    for p_id, p_name, p_price in default_products:
        cursor.execute("INSERT OR IGNORE INTO inventory (product_id, product_name, price_soem) VALUES (?, ?, ?)", (p_id, p_name, p_price))

    conn.commit()
    conn.close()


# 🛠️ BAZA OPERATORLARI
def db_add_user(user_id, username, name):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, name, joined_at) VALUES (?, ?, ?, ?)", (user_id, username, name, now))
    conn.commit()
    conn.close()

def db_get_user(user_id):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, name, balance, banned, spent_money, joined_at FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
    order_count = cursor.fetchone()[0]
    conn.close()
    if row:
        return {
            "username": row[0], "name": row[1], "balance": row[2],
            "banned": bool(row[3]), "spent_money": row[4], "joined_at": row[5], "orders_count": order_count
        }
    return None

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
    cursor.execute("SELECT product_id, product_name, price_soem FROM inventory")
    rows = cursor.fetchall()
    conn.close()
    products = {}
    for r in rows:
        products[r[0]] = {"name": r[1], "price": r[2]}
    return products

def db_execute_auto_purchase(user_id, product_id, product_name, price_sum, target):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO orders (user_id, product_id, product_name, price_sum, target_username, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'Bajarildi', ?)
    """, (user_id, product_id, product_name, price_sum, target, now))

    cursor.execute("UPDATE users SET spent_money = spent_money + ? WHERE user_id = ?", (price_sum, user_id))
    cursor.execute("UPDATE global_settings SET value = CAST(value AS INTEGER) + ? WHERE key = 'total_kassa'", (price_sum,))

    cursor.execute("SELECT last_insert_rowid()")
    order_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return order_id

def db_get_all_users():
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def db_get_kassa():
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM global_settings WHERE key = 'total_kassa'")
    val = int(cursor.fetchone()[0])
    conn.close()
    return val

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

def db_add_product_to_inv(p_id, p_name, p_price):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO inventory (product_id, product_name, price_soem) VALUES (?, ?, ?)", (p_id, p_name, p_price))
    conn.commit()
    conn.close()

def db_del_product_from_inv(p_id):
    conn = sqlite3.connect("store_management.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE product_id = ?", (p_id,))
    conn.commit()
    conn.close()


# 🟢 START BUYRUG'I
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

    current_products = db_get_inventory()
    current_price = current_products["stars_1"]["price"] if "stars_1" in current_products else 380

    timestamp = int(datetime.now().timestamp())
    dynamic_web_app_url = f"{CONFIG['web_app_url']}?price={current_price}&t={timestamp}"

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(text="🛍 Nova Store-ni ochish 🛍", web_app=telebot.types.WebAppInfo(url=dynamic_web_app_url)),
        InlineKeyboardButton(text="🔈 Yangiliklar kanali", url=CONFIG["channel_url"])
    )

    welcome_text = f"👋 Salom {first_name}!\n\n⭐️ Nova Store botiga xush kelibsiz.\nXarid qilish uchun pastdagi tugmani bosing 👇"
    try:
        bot.send_photo(chat_id=user_id, photo=CONFIG["start_photo"], caption=welcome_text, reply_markup=kb)
    except Exception:
        bot.send_message(user_id, welcome_text, reply_markup=kb)


# 👑 ADMIN PANEL
@bot.message_handler(commands=['admin'])
def super_admin_panel(message):
    if message.chat.id != ADMIN_ID: return
    total_users = len(db_get_all_users())
    kassa = db_get_kassa()
    inv_count = len(db_get_inventory())

    admin_text = (
        f"👑 **ADMIN PANEL**\n==================================\n\n"
        f"👥 Mijozlar: `{total_users} ta`\n💰 Kassa: `{kassa:,} so'm`\n📦 Tovar turlari: `{inv_count} ta`"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👤 CRM (Mijoz)", callback_data="pnl_user_inspect"),
        InlineKeyboardButton("💰 Balans", callback_data="pnl_balance_ctrl"),
        InlineKeyboardButton("📦 Tovar Ombori", callback_data="pnl_inventory_ctrl"),
        InlineKeyboardButton("📢 Reklama", callback_data="pnl_broadcast"),
        InlineKeyboardButton("🚫 Ban Tizimi", callback_data="pnl_ban_manager")
    )
    bot.send_message(ADMIN_ID, admin_text, parse_mode="Markdown", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("pnl_"))
def admin_sub_navigation(call):
    if call.message.chat.id != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    panel = call.data
    if panel == "pnl_user_inspect":
        msg = bot.send_message(ADMIN_ID, "🔍 Mijozning **Telegram ID** raqamini kiriting:")
        bot.register_next_step_handler(msg, process_crm_user_inspect)
    elif panel == "pnl_balance_ctrl":
        msg = bot.send_message(ADMIN_ID, "💰 Format: `ID_RAQAMI | SUMMA` (Masalan: `7977733681 | 50000`)")
        bot.register_next_step_handler(msg, process_admin_balance_change)
    elif panel == "pnl_inventory_ctrl":
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("➕ Tovar Qo'shish", callback_data="inv_add"),
            InlineKeyboardButton("🗑️ Tovar O'chirish", callback_data="inv_del"),
            InlineKeyboardButton("📋 Ro'yxat", callback_data="inv_view_list")
        )
        bot.send_message(ADMIN_ID, "📦 **Ombor boshqaruvi:**", reply_markup=kb)
    elif panel == "pnl_broadcast":
        msg = bot.send_message(ADMIN_ID, "📢 Global postni yuboring:")
        bot.register_next_step_handler(msg, process_admin_broadcast)
    elif panel == "pnl_ban_manager":
        msg = bot.send_message(ADMIN_ID, "🚫 Bloklash uchun Telegram ID raqamini bering:")
        bot.register_next_step_handler(msg, process_admin_ban_click)

def process_crm_user_inspect(message):
    try:
        target_id = int(message.text.strip())
        user_info = db_get_user(target_id)
        if not user_info:
            bot.send_message(ADMIN_ID, "❌ Topilmadi!")
            return
        orders = db_get_user_orders(target_id)
        history_text = ""
        if orders:
            for index, order in enumerate(orders, 1):
                history_text += f"{index}. 📦 {order[1]} | `{order[2]:,} so'm` | {order[3]}\n"
        else:
            history_text = "🤷‍♂️ Xaridlar yo'q."

        inspect_response = f"🆔 ID: `{target_id}`\n🏷 Ism: {user_info['name']}\n💰 Balans: `{user_info['balance']:,} so'm`\n\n🛒 Xarid tarixi:\n{history_text}"
        kb = InlineKeyboardMarkup()
        act = "unban" if user_info['banned'] else "ban"
        txt = "🟢 Blokdan ochish" if user_info['banned'] else "🔴 Bloklash"
        kb.add(InlineKeyboardButton(txt, callback_data=f"crmaction_{act}_{target_id}"))
        bot.send_message(ADMIN_ID, inspect_response, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Xato: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("crmaction_"))
def handle_crm_ban_unban(call):
    if call.message.chat.id != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    _, action, uid = call.data.split("_")
    db_set_ban(int(uid), action == "ban")
    bot.send_message(ADMIN_ID, f"✅ Bajarildi!")

def process_admin_balance_change(message):
    try:
        parts = message.text.split("|")
        t_id = int(parts[0].strip())
        amount = int(parts[1].strip())
        db_update_user_balance(t_id, amount)
        bot.send_message(ADMIN_ID, f"✅ ID: {t_id} balansiga {amount:,} so'm muvaffaqiyatli qo'shildi!")
        bot.send_message(t_id, f"💰 Botingiz balansi admin tomonidan `{amount:,} so'm`ga yangilandi!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Xato format: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith("inv_"))
def inventory_actions_handler(call):
    if call.message.chat.id != ADMIN_ID: return
    bot.answer_callback_query(call.id)
    action = call.data
    if action == "inv_view_list":
        current_inv = db_get_inventory()
        text = "📋 **Omborda bor tovarlar:\n**"
        for key, info in current_inv.items():
            text += f"🔑 ID: `{key}` | *{info['name']}* | `{info['price']:,} so'm`\n"
        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
    elif action == "inv_add":
        msg = bot.send_message(ADMIN_ID, "Format: `id | Nomi | Narxi` \n(Misol: `stars_1 | 1 Stars | 400`)")
        bot.register_next_step_handler(msg, process_inventory_add_item)
    elif action == "inv_del":
        msg = bot.send_message(ADMIN_ID, "🗑️ O'chirish uchun tovar ID sini yozing:")
        bot.register_next_step_handler(msg, process_inventory_del_item)

def process_inventory_add_item(message):
    try:
        parts = message.text.split("|")
        db_add_product_to_inv(parts[0].strip(), parts[1].strip(), int(parts[2].strip()))
        bot.send_message(ADMIN_ID, "✅ Tovar omborga qo'shildi/yangilandi!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Xato: {e}")

def process_inventory_del_item(message):
    db_del_product_from_inv(message.text.strip())
    bot.send_message(ADMIN_ID, "✅ Tovar o'chirildi!")

def process_admin_broadcast(message):
    all_users = db_get_all_users()
    count = 0
    for u_id in all_users:
        if u_id == ADMIN_ID: continue
        try:
            bot.copy_message(chat_id=u_id, from_chat_id=ADMIN_ID, message_id=message.message_id)
            count += 1
        except Exception: continue
    bot.send_message(ADMIN_ID, f"✅ Reklama muvaffaqiyatli {count} kishiga yuborildi.")

def process_admin_ban_click(message):
    try:
        uid = int(message.text.strip())
        user_info = db_get_user(uid)
        if user_info:
            db_set_ban(uid, not user_info['banned'])
            bot.send_message(ADMIN_ID, f"✅ ID: {uid} foydalanuvchining blok holati o'zgardi!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"❌ Xato: {e}")


# 📱 MINI APP SOTUV APARATI INTEGRATSIYASI
@bot.message_handler(content_types=['web_app_data'])
def handle_mini_app_transactions(message):
    try:
        incoming_data = message.web_app_data.data
        target_user = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"
        current_products = db_get_inventory()

        if incoming_data.startswith("{") and incoming_data.endswith("}"):
            parsed_json = json.loads(incoming_data)
            if parsed_json.get("action") == "buy_custom_stars":
                stars_count = int(parsed_json.get("amount", 0))
                custom_target = parsed_json.get("target") or target_user
                ONE_STARS_PRICE = current_products["stars_1"]["price"] if "stars_1" in current_products else 380
                total_price_soem = stars_count * ONE_STARS_PRICE

                order_id = db_execute_auto_purchase(message.chat.id, f"custom_stars_{stars_count}", f"{stars_count} Stars", total_price_soem, custom_target)
                bot.send_message(message.chat.id, f"🥳 **Xarid cheki №{order_id}**\n📦 Mahsulot: {stars_count} Stars\n💸 Jami: `{total_price_soem:,} so'm` \n🎯 Kimga: {custom_target}", parse_mode="Markdown")
                bot.send_message(ADMIN_ID, f"🚨 **YANGI BUYURTMA №{order_id}!**\n📦 Tovar: {stars_count} Stars\n🎯 Kimga tashlash kerak: {custom_target}\n💰 Narxi: {total_price_soem:,} so'm\n\n⚠️ Sardorbek, profilingizdan ushbu odamga tezda Stars gift qilib yuboring!")
                return

        product_key = incoming_data.strip()
        if product_key in current_products:
            item = current_products[product_key]
            order_id = db_execute_auto_purchase(message.chat.id, product_key, item["name"], item["price"], target_user)
            bot.send_message(message.chat.id, f"🥳 **Xarid cheki №{order_id}**\n📦 Mahsulot: {item['name']}\n💰 To'lov: `{item['price']:,} so'm`", parse_mode="Markdown")
            bot.send_message(ADMIN_ID, f"🚨 **YANGI BUYURTMA №{order_id}!**\n📦 Tovar: {item['name']}\n🎯 Kimga tashlash kerak: {target_user}\n💰 Narxi: {item['price']:,} so'm")
    except Exception:
        pass

init_db()

# 🔄 RENDER SERVERI UCHUN ASOSIY ISHGA TUSHIRISH TIZIMI
if __name__ == '__main__':
    # Botni parallel ravishda ham Webhook, ham Pollingda chalkashmasligi uchun oddiy usulda yoqamiz
    import threading
    threading.Thread(target=bot.infinity_polling, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)

