import sqlite3
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
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
        return "Unlimited"
    from datetime import datetime
    try:
        dt = datetime.fromtimestamp(expiry / 1000)
        now = datetime.now()
        delta = dt - now
        days = delta.days
        if days < 0:
            return "Expired"
        return "{} ({} days left)".format(dt.strftime("%Y-%m-%d"), days)
    except:
        return "Unknown"


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
            import json
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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("My Subscription", callback_data="my_info")],
        [InlineKeyboardButton("Client List", callback_data="list_clients")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to 3x-ui Bot!\nChoose an option below:",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Available commands:\n"
        "/start - Main menu\n"
        "/info - Inbound info\n"
        "/clients - Client list\n"
        "/help - Help"
    )


async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_my_info(update, context)


async def clients_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_clients_list(update, context)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "my_info":
        await show_my_info_callback(query, context)
    elif query.data == "list_clients":
        await show_clients_list_callback(query, context)
    elif query.data == "back_to_menu":
        await back_to_menu(query, context)
    elif query.data.startswith("client_"):
        email = query.data.replace("client_", "")
        await show_client_details_callback(query, email, context)


async def show_my_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    inbounds = get_inbounds()
    if not inbounds:
        await update.message.reply_text("No inbounds found.")
        return

    text = "Inbound Information:\n\n"
    for inbound in inbounds:
        text += (
            "ID: {}\n"
            "Protocol: {}\n"
            "Port: {}\n"
            "Tag: {}\n"
            "---\n"
        ).format(inbound["id"], inbound["protocol"], inbound["port"], inbound["tag"])

    await update.message.reply_text(text)


async def show_my_info_callback(query, context):
    inbounds = get_inbounds()
    if not inbounds:
        await query.edit_message_text("No inbounds found.")
        return

    text = "Inbound Information:\n\n"
    for inbound in inbounds:
        text += (
            "ID: {}\n"
            "Protocol: {}\n"
            "Port: {}\n"
            "Tag: {}\n"
            "---\n"
        ).format(inbound["id"], inbound["protocol"], inbound["port"], inbound["tag"])

    keyboard = [[InlineKeyboardButton("Back", callback_data="back_to_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def show_clients_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clients = get_all_clients()
    if not clients:
        await update.message.reply_text("No clients found.")
        return

    text = "Client List:\n\n"
    for c in clients:
        up = format_bytes(c["stats"]["up"]) if c["stats"] else "0"
        down = format_bytes(c["stats"]["down"]) if c["stats"] else "0"
        expiry = format_expiry(c["expiry"]) if c["expiry"] else "Unlimited"

        text += (
            "Name: {}\n"
            "Upload: {}\n"
            "Download: {}\n"
            "Expiry: {}\n"
            "Status: {}\n"
            "---\n"
        ).format(c["email"], up, down, expiry, "Active" if c["enable"] else "Disabled")

    await update.message.reply_text(text)


async def show_clients_list_callback(query, context):
    clients = get_all_clients()
    if not clients:
        await query.edit_message_text("No clients found.")
        return

    buttons = []
    for c in clients:
        buttons.append([InlineKeyboardButton(c["email"], callback_data="client_" + c["email"])])
    buttons.append([InlineKeyboardButton("Back", callback_data="back_to_menu")])

    await query.edit_message_text("Select a client:", reply_markup=InlineKeyboardMarkup(buttons))


async def show_client_details_callback(query, email, context):
    clients = get_all_clients()
    target = None
    for c in clients:
        if c["email"] == email:
            target = c
            break

    if not target:
        await query.edit_message_text("Client not found.")
        return

    up = format_bytes(target["stats"]["up"]) if target["stats"] else "0"
    down = format_bytes(target["stats"]["down"]) if target["stats"] else "0"
    total = format_bytes(target["stats"]["total"]) if target["stats"] else "Unlimited"
    expiry = format_expiry(target["expiry"]) if target["expiry"] else "Unlimited"

    text = (
        "Client Details: {}\n\n"
        "Protocol: {}\n"
        "Port: {}\n"
        "Upload: {}\n"
        "Download: {}\n"
        "Traffic Limit: {}\n"
        "Expiry: {}\n"
        "Status: {}\n"
    ).format(
        target["email"],
        target["inbound_protocol"],
        target["inbound_port"],
        up, down, total, expiry,
        "Active" if target["enable"] else "Disabled",
    )

    keyboard = [
        [InlineKeyboardButton("Back to List", callback_data="list_clients")],
        [InlineKeyboardButton("Main Menu", callback_data="back_to_menu")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def back_to_menu(query, context):
    keyboard = [
        [InlineKeyboardButton("My Subscription", callback_data="my_info")],
        [InlineKeyboardButton("Client List", callback_data="list_clients")],
    ]
    await query.edit_message_text(
        "Welcome to 3x-ui Bot!\nChoose an option below:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("clients", clients_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    logger.info("Bot is starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
