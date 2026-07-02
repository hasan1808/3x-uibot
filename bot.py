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


def format_expiry(expiry):
    if not expiry or expiry == 0:
        return "نامحدود"
    try:
        dt = datetime.fromtimestamp(expiry / 1000)
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
        cursor.execute("SELECT id, settings, port, protocol, tag FROM inbounds")
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
                "tag": row[4],
            })
        return inbounds
    except Exception as e:
        logger.error("DB error: %s", e)
        db.close()
        return []


def get_client_stats(email):
    db = get_db()
    if not db:
        return None
    try:
        cursor = db.cursor()
        cursor.execute(
            "SELECT up, down, total, expiry, enable FROM client_traffics WHERE email=?",
            (email,),
        )
        row = cursor.fetchone()
        db.close()
        if row:
            return {
                "up": row[0],
                "down": row[1],
                "total": row[2],
                "expiry": row[3],
                "enable": row[4],
            }
        return None
    except:
        db.close()
        return None


def find_client_by_email(email):
    inbounds = get_inbounds()
    for inbound in inbounds:
        for client in inbound["settings"].get("clients", []):
            if client.get("email") == email:
                stats = get_client_stats(email)
                return {
                    "email": email,
                    "password": client.get("password", ""),
                    "limit_ip": client.get("limitIp", 0),
                    "expiry": client.get("expiry", 0),
                    "enable": client.get("enable", True),
                    "stats": stats,
                    "inbound_port": inbound["port"],
                    "inbound_protocol": inbound["protocol"],
                    "sub_id": client.get("subId", ""),
                }
    return None


def find_client_by_telegram_id(telegram_id):
    db = get_db()
    if not db:
        return None

    # Try clients table first
    try:
        cursor = db.cursor()
        cursor.execute("SELECT email FROM clients WHERE telegram_id=?", (str(telegram_id),))
        row = cursor.fetchone()
        if row:
            db.close()
            return find_client_by_email(row[0])
    except:
        pass

    # Fallback: search in inbounds settings for subId
    db.close()
    inbounds = get_inbounds()
    tid = str(telegram_id)
    for inbound in inbounds:
        for client in inbound["settings"].get("clients", []):
            if client.get("subId") == tid:
                email = client.get("email", "")
                stats = get_client_stats(email)
                return {
                    "email": email,
                    "password": client.get("password", ""),
                    "limit_ip": client.get("limitIp", 0),
                    "expiry": client.get("expiry", 0),
                    "enable": client.get("enable", True),
                    "stats": stats,
                    "inbound_port": inbound["port"],
                    "inbound_protocol": inbound["protocol"],
                    "sub_id": tid,
                }
    return None


def get_all_clients():
    inbounds = get_inbounds()
    clients = []
    for inbound in inbounds:
        for client in inbound["settings"].get("clients", []):
            email = client.get("email", "")
            stats = get_client_stats(email)
            clients.append({
                "email": email,
                "password": client.get("password", ""),
                "limit_ip": client.get("limitIp", 0),
                "expiry": client.get("expiry", 0),
                "enable": client.get("enable", True),
                "stats": stats,
                "inbound_port": inbound["port"],
                "inbound_protocol": inbound["protocol"],
            })
    return clients


def make_client_text(c, title=True):
    up = format_bytes(c["stats"]["up"]) if c["stats"] else "0"
    down = format_bytes(c["stats"]["down"]) if c["stats"] else "0"
    total = format_bytes(c["stats"]["total"]) if c["stats"] and c["stats"]["total"] else "نامحدود"
    expiry = format_expiry(c["expiry"]) if c["expiry"] else "نامحدود"

    text = ""
    if title:
        text += "جزئیات کاربر: {}\n\n".format(c["email"])

    text += (
        "پروتکل: {}\n"
        "پورت: {}\n"
        "آپلود: {}\n"
        "دانلود: {}\n"
        "محدودیت ترافیک: {}\n"
        "انقضا: {}\n"
        "وضعیت: {}\n"
    ).format(
        c["inbound_protocol"],
        c["inbound_port"],
        up, down, total, expiry,
        "فعال" if c["enable"] else "غیرفعال",
    )
    return text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    client = find_client_by_telegram_id(user_id)

    if client:
        text = make_client_text(client)
        keyboard = [
            [InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")],
        ]
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await show_main_menu(update.message)


async def show_main_menu(message):
    keyboard = [
        [InlineKeyboardButton("اطلاعات من", callback_data="my_info")],
        [InlineKeyboardButton("جستجو با ایمیل", callback_data="search_email")],
        [InlineKeyboardButton("لیست کاربران", callback_data="list_clients")],
    ]
    await message.reply_text(
        "به ربات مدیریت 3x-ui خوش آمدید!\n"
        "اگر اکانت ندارید، گزینه جستجو با ایمیل را انتخاب کنید.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "دستورات:\n"
        "/start - منوی اصلی\n"
        "/info - اطلاعات اینباندها\n"
        "/clients - لیست کاربران\n"
        "/search <ایمیل> - جستجوی کاربر\n"
        "/help - راهنما"
    )


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inbounds = get_inbounds()
    if not inbounds:
        await update.message.reply_text("هیچ اینباندی یافت نشد.")
        return

    text = "اطلاعات اینباندها:\n\n"
    for inbound in inbounds:
        text += (
            "شناسه: {}\n"
            "پروتکل: {}\n"
            "پورت: {}\n"
            "برچسب: {}\n"
            "---\n"
        ).format(inbound["id"], inbound["protocol"], inbound["port"], inbound["tag"])

    await update.message.reply_text(text)


async def clients_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_clients_list(update.message)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("مثال: /search user@email.com")
        return

    email = context.args[0]
    client = find_client_by_email(email)
    if not client:
        await update.message.reply_text("کاربری با ایمیل {} یافت نشد.".format(email))
        return

    text = make_client_text(client)
    keyboard = [[InlineKeyboardButton("بازگشت به منو", callback_data="back_to_menu")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "my_info":
        await show_my_info_callback(query, context)
    elif query.data == "search_email":
        context.user_data["awaiting_email"] = True
        await query.edit_message_text("ایمیل کاربر را وارد کنید:")
    elif query.data == "list_clients":
        await show_clients_list_callback(query, context)
    elif query.data == "back_to_menu":
        await back_to_menu(query, context)
    elif query.data.startswith("client_"):
        email = query.data.replace("client_", "")
        client = find_client_by_email(email)
        if not client:
            await query.edit_message_text("کاربر یافت نشد.")
            return

        text = make_client_text(client)
        keyboard = [
            [InlineKeyboardButton("بازگشت به لیست", callback_data="list_clients")],
            [InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_email"):
        context.user_data["awaiting_email"] = False
        email = update.message.text.strip()
        client = find_client_by_email(email)

        if not client:
            keyboard = [[InlineKeyboardButton("بازگشت به منو", callback_data="back_to_menu")]]
            await update.message.reply_text(
                "کاربری با ایمیل {} یافت نشد.".format(email),
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        text = make_client_text(client)
        keyboard = [[InlineKeyboardButton("بازگشت به منو", callback_data="back_to_menu")]]
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        client = find_client_by_email(update.message.text.strip())
        if client:
            text = make_client_text(client)
            keyboard = [[InlineKeyboardButton("بازگشت به منو", callback_data="back_to_menu")]]
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("دستور نامعتبر. /help را ببینید.")


async def show_my_info_callback(query, context):
    user_id = query.from_user.id
    client = find_client_by_telegram_id(user_id)

    if client:
        text = make_client_text(client)
    else:
        text = "اکانتی برای شما یافت نشد.\n"
        text += "از گزینه جستجو با ایمیل استفاده کنید."

    keyboard = [[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_clients_list(message):
    clients = get_all_clients()
    if not clients:
        await message.reply_text("هیچ کاربری یافت نشد.")
        return

    text = "لیست کاربران:\n\n"
    for c in clients:
        up = format_bytes(c["stats"]["up"]) if c["stats"] else "0"
        down = format_bytes(c["stats"]["down"]) if c["stats"] else "0"
        expiry = format_expiry(c["expiry"]) if c["expiry"] else "نامحدود"

        text += (
            "نام: {}\n"
            "آپلود: {}\n"
            "دانلود: {}\n"
            "انقضا: {}\n"
            "وضعیت: {}\n"
            "---\n"
        ).format(c["email"], up, down, expiry, "فعال" if c["enable"] else "غیرفعال")

    await message.reply_text(text)


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
        [InlineKeyboardButton("جستجو با ایمیل", callback_data="search_email")],
        [InlineKeyboardButton("لیست کاربران", callback_data="list_clients")],
    ]
    await query.edit_message_text(
        "به ربات مدیریت 3x-ui خوش آمدید!",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("clients", clients_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
