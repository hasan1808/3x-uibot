import sqlite3
import os
import json
import uuid as uuid_lib
import random
import string
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
from config import TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID

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


def is_admin(user_id):
    return ADMIN_TELEGRAM_ID > 0 and user_id == ADMIN_TELEGRAM_ID


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
                "id": row[0], "settings": settings,
                "port": row[2], "protocol": row[3],
            })
        return inbounds
    except Exception as e:
        logger.error("DB error: %s", e)
        if db: db.close()
        return []


def get_client_traffic(email):
    db = get_db()
    if not db:
        return None
    try:
        cursor = db.cursor()
        cursor.execute("PRAGMA table_info(client_traffics)")
        cols = [r[1] for r in cursor.fetchall()]
        db.close()
        if cols:
            db2 = get_db()
            if db2:
                cursor2 = db2.cursor()
                cursor2.execute("SELECT * FROM client_traffics WHERE email=?", (email,))
                row = cursor2.fetchone()
                db2.close()
                if row:
                    keys = {}
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
        "email": email, "enable": c.get("enable", True),
        "expiry": c.get("expiryTime", 0), "total_gb": c.get("totalGB", 0),
        "limit_ip": c.get("limitIp", 0), "sub_id": c.get("subId", ""),
        "tg_id": c.get("tgId", 0), "uuid": c.get("id", ""),
        "flow": c.get("flow", ""),
        "inbound_port": inbound["port"], "inbound_protocol": inbound["protocol"],
        "traffic": traffic,
    }


def extract_uuid_from_config(config_text):
    import re
    matched = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', config_text.strip(), re.I)
    return matched.group(0).lower() if matched else None


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
    return results[0] if results else None


def search_client_by_telegram_id(tg_id):
    tid = str(tg_id)
    inbounds = get_inbounds()
    for inbound in inbounds:
        for c in inbound["settings"].get("clients", []):
            if str(c.get("tgId", "")) == tid or str(c.get("subId", "")) == tid:
                email = c.get("email", "")
                traffic = get_client_traffic(email)
                return {
                    "email": email, "enable": c.get("enable", True),
                    "expiry": c.get("expiryTime", 0), "total_gb": c.get("totalGB", 0),
                    "limit_ip": c.get("limitIp", 0), "sub_id": c.get("subId", ""),
                    "tg_id": c.get("tgId", 0), "uuid": c.get("id", ""),
                    "inbound_port": inbound["port"], "inbound_protocol": inbound["protocol"],
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
                "email": email, "enable": c.get("enable", True),
                "expiry": c.get("expiryTime", 0), "total_gb": c.get("totalGB", 0),
                "limit_ip": c.get("limitIp", 0), "sub_id": c.get("subId", ""),
                "tg_id": c.get("tgId", 0),
                "inbound_port": inbound["port"], "inbound_protocol": inbound["protocol"],
                "traffic": traffic,
            })
    return clients


def make_client_text(c):
    up = 0; down = 0; total = c["total_gb"]
    if c["traffic"]:
        up = c["traffic"].get("up", 0)
        down = c["traffic"].get("down", 0)
        if not total: total = c["traffic"].get("total", 0)
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
        c["email"], c["inbound_protocol"], c["inbound_port"],
        format_bytes(up), format_bytes(down),
        format_bytes(total) if total else "نامحدود", expiry, status,
    )
    return text


def create_user_in_db(email, total_gb, expiry_days):
    db_path = find_database()
    if not db_path:
        return None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id, settings, port, protocol FROM inbounds WHERE protocol='vless' LIMIT 1")
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT id, settings, port, protocol FROM inbounds LIMIT 1")
            row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        inbound_id = row[0]
        settings = json.loads(row[1]) if row[1] else {}
        port = row[2]
        protocol = row[3]

        new_uuid = str(uuid_lib.uuid4())
        sub_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        now_ms = int(datetime.now().timestamp() * 1000)
        expiry_ms = expiry_days * 86400 * 1000 if expiry_days > 0 else 0

        new_client = {
            "comment": "",
            "created_at": now_ms,
            "email": email,
            "enable": True,
            "expiryTime": expiry_ms,
            "flow": "",
            "id": new_uuid,
            "limitIp": 0,
            "reset": 0,
            "subId": sub_id,
            "tgId": 0,
            "totalGB": total_gb * 1073741824,
            "updated_at": now_ms,
        }

        if "clients" not in settings:
            settings["clients"] = []
        settings["clients"].append(new_client)

        cursor.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(settings), inbound_id))
        conn.commit()
        conn.close()

        # Restart x-ui to apply
        import subprocess
        subprocess.run(["/usr/bin/systemctl", "restart", "x-ui"], capture_output=True)

        return {
            "email": email, "uuid": new_uuid, "sub_id": sub_id,
            "port": port, "protocol": protocol,
            "total_gb": total_gb, "expiry_days": expiry_days,
        }
    except Exception as e:
        logger.error("Create user error: %s", e)
        return None


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
    if is_admin(message.chat.id):
        keyboard.append([InlineKeyboardButton("ساخت کاربر جدید", callback_data="new_user")])
    await message.reply_text(
        "به ربات مدیریت 3x-ui خوش آمدید!",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - منوی اصلی\n"
        "/info - اطلاعات اینباندها\n"
        "/clients - لیست کاربران\n"
        "/search <متن> - جستجوی کاربر\n"
        "/add - ساخت کاربر جدید (فقط ادمین)\n"
        "/help - راهنما\n\n"
        "جستجو با: نام کاربری، UUID یا لینک کانفیگ"
    )


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inbounds = get_inbounds()
    if not inbounds:
        await update.message.reply_text("هیچ اینباندی یافت نشد.")
        return
    text = "اطلاعات اینباندها:\n\n"
    for inbound in inbounds:
        text += "شناسه: {} | پروتکل: {} | پورت: {}\n---\n".format(
            inbound["id"], inbound["protocol"], inbound["port"])
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
            c["email"], up, down, expiry, "فعال" if c["enable"] else "غیرفعال")
    await update.message.reply_text(text)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("مثال: /search example@email.com")
        return
    await show_search_results(update.message, " ".join(context.args))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "my_info":
        await show_my_info_callback(query, context)
    elif query.data == "search_email":
        context.user_data["awaiting_email"] = True
        await query.edit_message_text("UUID یا لینک کانفیگ را بفرستید:")
    elif query.data == "list_clients":
        await show_clients_list_callback(query, context)
    elif query.data == "back_to_menu":
        await back_to_menu(query, context)
    elif query.data == "new_user":
        if not is_admin(query.from_user.id):
            await query.edit_message_text("این بخش فقط برای ادمین است.")
            return
        context.user_data["creating_user"] = True
        context.user_data["step"] = "email"
        await query.edit_message_text("ایمیل کاربر جدید را وارد کنید:")
    elif query.data == "cancel_create":
        context.user_data["creating_user"] = False
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
            "نتیجه‌ای برای '{}' یافت نشد.\n".format(query) +
            "می‌توانید ایمیل، UUID یا لینک کانفیگ بفرستید.",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if len(results) == 1:
        text = make_client_text(results[0])
        keyboard = [[InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")]]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    buttons = []
    for r in results:
        buttons.append([InlineKeyboardButton(r["email"], callback_data="client_" + r["email"])])
    buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])
    await message.reply_text(
        "{} نتیجه یافت شد:".format(len(results)),
        reply_markup=InlineKeyboardMarkup(buttons))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    if context.user_data.get("creating_user"):
        if not is_admin(user_id):
            context.user_data["creating_user"] = False
            return

        step = context.user_data.get("step")

        if step == "email":
            if not text:
                await update.message.reply_text("ایمیل معتبر نیست. دوباره وارد کنید:")
                return
            context.user_data["new_email"] = text
            context.user_data["step"] = "traffic"
            await update.message.reply_text(
                "حجم ترافیک (GB) را وارد کنید (0 = نامحدود):")

        elif step == "traffic":
            try:
                gb = int(text)
                if gb < 0: raise ValueError
            except:
                await update.message.reply_text("عدد معتبر وارد کنید (0 = نامحدود):")
                return
            context.user_data["new_traffic"] = gb
            context.user_data["step"] = "expiry"
            await update.message.reply_text(
                "مدت اعتبار (روز) را وارد کنید (0 = نامحدود):")

        elif step == "expiry":
            try:
                days = int(text)
                if days < 0: raise ValueError
            except:
                await update.message.reply_text("عدد معتبر وارد کنید (0 = نامحدود):")
                return

            email = context.user_data["new_email"]
            total_gb = context.user_data["new_traffic"]
            context.user_data["creating_user"] = False

            await update.message.reply_text("در حال ایجاد کاربر...")

            result = create_user_in_db(email, total_gb, days)

            if result:
                expiry_text = "نامحدود" if days == 0 else "{} روز".format(days)
                traffic_text = "نامحدود" if total_gb == 0 else "{} GB".format(total_gb)
                msg = (
                    "کاربر با موفقیت ساخته شد!\n\n"
                    "ایمیل: {}\n"
                    "UUID: {}\n"
                    "Sub ID: {}\n"
                    "حجم: {}\n"
                    "اعتبار: {}\n"
                    "پورت: {} ({})\n"
                ).format(result["email"], result["uuid"], result["sub_id"],
                         traffic_text, expiry_text, result["port"], result["protocol"])
                keyboard = [[InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")]]
                await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                keyboard = [[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]
                await update.message.reply_text(
                    "خطا در ساخت کاربر!",
                    reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Normal text handling - search
    if context.user_data.get("awaiting_email"):
        context.user_data["awaiting_email"] = False
        await show_search_results(update.message, text)
        return

    results = search_clients(text)
    if results:
        if len(results) == 1:
            t = make_client_text(results[0])
            keyboard = [[InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")]]
            await update.message.reply_text(t, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            buttons = []
            for r in results:
                buttons.append([InlineKeyboardButton(r["email"], callback_data="client_" + r["email"])])
            buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])
            await update.message.reply_text(
                "چند نتیجه یافت شد:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text("دستور نامعتبر. /help یا /start را بزنید.")


async def show_my_info_callback(query, context):
    user_id = query.from_user.id
    client = search_client_by_telegram_id(user_id)
    if client:
        text = make_client_text(client)
    else:
        text = "اکانتی برای شما یافت نشد.\nاز گزینه جستجو استفاده کنید."
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
    await query.edit_message_text("یک کاربر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(buttons))


async def back_to_menu(query, context):
    keyboard = [
        [InlineKeyboardButton("اطلاعات من", callback_data="my_info")],
        [InlineKeyboardButton("جستجوی خودکار", callback_data="search_email")],
        [InlineKeyboardButton("لیست کاربران", callback_data="list_clients")],
    ]
    if is_admin(query.from_user.id):
        keyboard.append([InlineKeyboardButton("ساخت کاربر جدید", callback_data="new_user")])
    await query.edit_message_text(
        "به ربات مدیریت 3x-ui خوش آمدید!",
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
