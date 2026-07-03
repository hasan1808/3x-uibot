import sqlite3
import os
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DB_PATHS = [
    "/etc/x-ui/x-ui.db",
    "/usr/local/x-ui/x-ui.db",
    "/opt/x-ui/x-ui.db",
]


def find_database():
    for path in DB_PATHS:
        if os.path.exists(path):
            return path
    return None


def get_db():
    db_path = find_database()
    if not db_path:
        return None
    return sqlite3.connect(db_path)


def format_bytes(b):
    if not b or b == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while b >= 1024 and i < len(units) - 1:
        b /= 1024
        i += 1
    return "{:.2f} {}".format(b, units[i])


def format_expiry(ts):
    if not ts or ts == 0:
        return "نامحدود"
    try:
        dt = datetime.fromtimestamp(ts / 1000)
        now = datetime.now()
        delta = dt - now
        days = delta.days
        if days < 0:
            return "منقضی شده"
        return "{} ({} روز)".format(dt.strftime("%Y-%m-%d"), days)
    except:
        return "نامشخص"


def get_inbounds():
    db = get_db()
    if not db:
        return []
    try:
        cursor = db.cursor()
        cursor.execute("SELECT id, settings, port, protocol FROM inbounds")
        rows = cursor.fetchall()
        db.close()

        inbounds = []
        for row in rows:
            settings = {}
            try:
                settings = json.loads(row[1]) if row[1] else {}
            except:
                pass
            inbounds.append({
                "id": row[0],
                "settings": settings,
                "port": row[2],
                "protocol": row[3],
            })
        return inbounds
    except Exception as e:
        logger.error("DB error: %s", e)
        if db:
            db.close()
        return []


def get_client_traffic(email):
    db = get_db()
    if not db:
        return None
    try:
        cursor = db.cursor()
        try:
            cursor.execute("PRAGMA table_info(client_traffics)")
            cols = [r[1] for r in cursor.fetchall()]
        except:
            cols = []
        db.close()

        keys = {}
        if cols:
            db2 = get_db()
            if db2:
                cursor2 = db2.cursor()
                cursor2.execute("SELECT * FROM client_traffics WHERE email=?", (email,))
                row = cursor2.fetchone()
                db2.close()
                if row:
                    for i, col in enumerate(cols):
                        keys[col] = row[i]
                return keys

        return None
    except:
        db.close()
        return None


def build_client(c, inbound):
    email = c.get("email", "")
    traffic = get_client_traffic(email)
    return {
        "email": email,
        "enable": c.get("enable", True),
        "expiry": c.get("expiryTime", 0),
        "total_gb": c.get("totalGB", 0),
        "limit_ip": c.get("limitIp", 0),
        "sub_id": c.get("subId", ""),
        "tg_id": c.get("tgId", 0),
        "uuid": c.get("id", ""),
        "flow": c.get("flow", ""),
        "inbound_port": inbound["port"],
        "inbound_protocol": inbound["protocol"],
        "traffic": traffic,
    }


def extract_uuid_from_config(config_text):
    import re
    text = config_text.strip()

    matched = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', text, re.I)
    if matched:
        return matched.group(0).lower()
    return None


def search_clients(query):
    query = query.strip().lower()
    if not query:
        return []

    uuid_from_config = extract_uuid_from_config(query)

    inbounds = get_inbounds()
    results = []

    for inbound in inbounds:
        for c in inbound["settings"].get("clients", []):
            email = (c.get("email") or "").lower()
            uid = (c.get("id") or "").lower()
            sub_id = (c.get("subId") or "").lower()
            comment = (c.get("comment") or "").lower()

            if email == query or uid == query or sub_id == query or comment == query:
                return [build_client(c, inbound)]
            if uuid_from_config and uuid_from_config == uid:
                return [build_client(c, inbound)]
            if query in email or query in uid or query in sub_id or query in comment:
                results.append(build_client(c, inbound))

    return results


def search_client_by_email(email):
    results = search_clients(email)
    if results:
        return results[0]
    return None


def search_client_by_telegram_id(tg_id):
    tid = str(tg_id)

    # Search in inbounds settings JSON
    inbounds = get_inbounds()
    for inbound in inbounds:
        for c in inbound["settings"].get("clients", []):
            if str(c.get("tgId", "")) == tid or str(c.get("subId", "")) == tid:
                email = c.get("email", "")
                traffic = get_client_traffic(email)
                return {
                    "email": email,
                    "enable": c.get("enable", True),
                    "expiry": c.get("expiryTime", 0),
                    "total_gb": c.get("totalGB", 0),
                    "limit_ip": c.get("limitIp", 0),
                    "sub_id": c.get("subId", ""),
                    "tg_id": c.get("tgId", 0),
                    "uuid": c.get("id", ""),
                    "inbound_port": inbound["port"],
                    "inbound_protocol": inbound["protocol"],
                    "traffic": traffic,
                }

    return None


def get_all_clients():
    inbounds = get_inbounds()
    clients = []
    for inbound in inbounds:
        for c in inbound["settings"].get("clients", []):
            email = c.get("email", "")
            traffic = get_client_traffic(email)
            clients.append({
                "email": email,
                "enable": c.get("enable", True),
                "expiry": c.get("expiryTime", 0),
                "total_gb": c.get("totalGB", 0),
                "limit_ip": c.get("limitIp", 0),
                "sub_id": c.get("subId", ""),
                "tg_id": c.get("tgId", 0),
                "inbound_port": inbound["port"],
                "inbound_protocol": inbound["protocol"],
                "traffic": traffic,
            })
    return clients


def make_client_text(c):
    up = 0
    down = 0
    total = c["total_gb"]
    if c["traffic"]:
        up = c["traffic"].get("up", 0)
        down = c["traffic"].get("down", 0)
        if not total:
            total = c["traffic"].get("total", 0)

    expiry = format_expiry(c["expiry"])
    status = "فعال" if c["enable"] else "غیرفعال"

    text = (
        "نام کاربری: {}\n"
        "پروتکل: {}\n"
        "پورت: {}\n"
        "آپلود: {}\n"
        "دانلود: {}\n"
        "حجم کل: {}\n"
        "انقضا: {}\n"
        "وضعیت: {}\n"
    ).format(
        c["email"],
        c["inbound_protocol"],
        c["inbound_port"],
        format_bytes(up),
        format_bytes(down),
        format_bytes(total) if total else "نامحدود",
        expiry,
        status,
    )
    return text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    client = search_client_by_telegram_id(user_id)

    if client:
        text = make_client_text(client)
        keyboard = [[InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await show_main_menu(update.message)


async def show_main_menu(message):
    keyboard = [
        [InlineKeyboardButton("اطلاعات من", callback_data="my_info")],
        [InlineKeyboardButton("جستجوی خودکار", callback_data="search_email")],
        [InlineKeyboardButton("لیست کاربران", callback_data="list_clients")],
    ]
    await message.reply_text(
        "به ربات مدیریت 3x-ui خوش آمدید!\n"
        "کافیه ایمیل، UUID یا لینک کانفیگت رو بفرستی تا اطلاعات کاربر رو پیدا کنم.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - منوی اصلی\n"
        "/info - اطلاعات اینباندها\n"
        "/clients - لیست کاربران\n"
        "/search <متن> - جستجوی کاربر\n"
        "/help - راهنما\n\n"
        "می‌توانید جستجو کنید با:\n"
        " نام کاربری (کامل یا قسمتی)\n"
        " UUID کاربر\n"
        " لینک کانفیگ (vmess:// vless:// trojan:// ...)\n"
        " کامنت یا توضیحات"
    )


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inbounds = get_inbounds()
    if not inbounds:
        await update.message.reply_text("هیچ اینباندی یافت نشد.")
        return

    text = "اطلاعات اینباندها:\n\n"
    for inbound in inbounds:
        text += "شناسه: {} | پروتکل: {} | پورت: {}\n---\n".format(
            inbound["id"], inbound["protocol"], inbound["port"]
        )
    await update.message.reply_text(text)


async def clients_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clients = get_all_clients()
    if not clients:
        await update.message.reply_text("هیچ کاربری یافت نشد.")
        return

    text = "لیست کاربران:\n\n"
    for c in clients:
        up = format_bytes(c["traffic"]["up"]) if c["traffic"] else "0"
        down = format_bytes(c["traffic"]["down"]) if c["traffic"] else "0"
        expiry = format_expiry(c["expiry"])
        text += "نام: {} | آپلود: {} | دانلود: {} | انقضا: {} | {}\n---\n".format(
            c["email"], up, down, expiry, "فعال" if c["enable"] else "غیرفعال"
        )

    await update.message.reply_text(text)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("مثال: /search example@email.com")
        return

    query = " ".join(context.args)
    await show_search_results(update.message, query)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "my_info":
        await show_my_info_callback(query, context)
    elif query.data == "search_email":
        context.user_data["awaiting_email"] = True
        await query.edit_message_text("ایمیل، UUID یا لینک کانفیگ را بفرستید:")
    elif query.data == "list_clients":
        await show_clients_list_callback(query, context)
    elif query.data == "back_to_menu":
        await back_to_menu(query, context)
    elif query.data.startswith("client_"):
        email = query.data.replace("client_", "")
        client = search_client_by_email(email)
        if not client:
            await query.edit_message_text("کاربر یافت نشد.")
            return

        text = make_client_text(client)
        keyboard = [
            [InlineKeyboardButton("بازگشت به لیست", callback_data="list_clients")],
            [InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_search_results(message, query):
    results = search_clients(query)

    if not results:
        keyboard = [[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]
        await message.reply_text(
            "نتیجه‌ای برای '{}' یافت نشد.\n"
            "می‌توانید ایمیل، UUID یا لینک کانفیگ بفرستید.".format(query),
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if len(results) == 1:
        text = make_client_text(results[0])
        keyboard = [[InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")]]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    buttons = []
    for r in results:
        label = r["email"] + " (" + r["inbound_protocol"] + ")"
        buttons.append([InlineKeyboardButton(label, callback_data="client_" + r["email"])])
    buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])

    await message.reply_text(
        "{} نتیجه برای '{}':".format(len(results), query),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    if context.user_data.get("awaiting_email"):
        context.user_data["awaiting_email"] = False
        await show_search_results(update.message, query)
        return

    results = search_clients(query)
    if results:
        if len(results) == 1:
            text = make_client_text(results[0])
            keyboard = [[InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")]]
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            buttons = []
            for r in results:
                buttons.append([InlineKeyboardButton(r["email"], callback_data="client_" + r["email"])])
            buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])
            await update.message.reply_text(
                "چند نتیجه یافت شد. یکی را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
    else:
        await update.message.reply_text("دستور نامعتبر. /help یا /start را بزنید.")


async def show_my_info_callback(query, context):
    user_id = query.from_user.id
    client = search_client_by_telegram_id(user_id)

    if client:
        text = make_client_text(client)
    else:
        text = "اکانتی برای شما یافت نشد.\nاز گزینه جستجو با ایمیل/UUID استفاده کنید."

    keyboard = [[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_clients_list_callback(query, context):
    clients = get_all_clients()
    if not clients:
        await query.edit_message_text("هیچ کاربری یافت نشد.")
        return

    buttons = []
    for c in clients:
        buttons.append([InlineKeyboardButton(c["email"], callback_data="client_" + c["email"])])
    buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])

    await query.edit_message_text(
        "یک کاربر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def back_to_menu(query, context):
    keyboard = [
        [InlineKeyboardButton("اطلاعات من", callback_data="my_info")],
        [InlineKeyboardButton("جستجوی خودکار", callback_data="search_email")],
        [InlineKeyboardButton("لیست کاربران", callback_data="list_clients")],
    ]
    await query.edit_message_text(
        "به ربات مدیریت 3x-ui خوش آمدید!\n"
        "کافیه ایمیل، UUID یا لینک کانفیگت رو بفرستی تا اطلاعات کاربر رو پیدا کنم.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def main():
    import time

    logger.info("Bot is starting... waiting 15s for old session to expire...")
    time.sleep(15)

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("clients", clients_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
