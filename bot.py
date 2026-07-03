import sqlite3
import os
import json
import uuid as uuid_lib
import random
import string
import logging
import subprocess
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
from config import TELEGRAM_BOT_TOKEN, ADMIN_TELEGRAM_ID, SERVER_DOMAIN

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


def run_cmd(cmd):
    env = os.environ.copy()
    env["PATH"] = "/usr/bin:/bin:/usr/local/bin"
    subprocess.run(cmd, capture_output=True, env=env)


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
        # if ts < year 2020 in ms → it's a duration (startAfterFirstUse)
        if ts < 1600000000000:
            days = ts / 86400000
            return "{} روز از اولین اتصال".format(int(days))
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


def get_inbound_by_id(inbound_id):
    db = get_db()
    if not db:
        return None
    try:
        cursor = db.cursor()
        cursor.execute("SELECT id, settings, port, protocol FROM inbounds WHERE id=?", (inbound_id,))
        row = cursor.fetchone()
        db.close()
        if not row:
            return None
        settings = {}
        try:
            settings = json.loads(row[1]) if row[1] else {}
        except:
            pass
        return {"id": row[0], "settings": settings, "port": row[2], "protocol": row[3]}
    except:
        db.close()
        return None


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


def find_client_full(email):
    inbounds = get_inbounds()
    for inbound in inbounds:
        for c in inbound["settings"].get("clients", []):
            if c.get("email") == email:
                traffic = get_client_traffic(email)
                return {
                    "client": c, "inbound": inbound, "traffic": traffic,
                    "email": email, "enable": c.get("enable", True),
                    "expiry": c.get("expiryTime", 0), "total_gb": c.get("totalGB", 0),
                    "limit_ip": c.get("limitIp", 0), "sub_id": c.get("subId", ""),
                    "tg_id": c.get("tgId", 0), "uuid": c.get("id", ""),
                    "flow": c.get("flow", ""),
                    "inbound_port": inbound["port"], "inbound_protocol": inbound["protocol"],
                }
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


def get_config_link(client):
    domain = SERVER_DOMAIN or "YOUR_SERVER_IP"
    uuid = client["uuid"]
    port = client["inbound_port"]
    email = client["email"]
    return "vless://{}@{}:{}?type=tcp&security=none&#{}".format(uuid, domain, port, email)


def get_panel_setting(key):
    db = get_db()
    if not db:
        return None
    try:
        cursor = db.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        db.close()
        return row[0] if row else None
    except:
        db.close()
        return None


def get_subscription_link(client):
    domain = SERVER_DOMAIN or "YOUR_SERVER_IP"
    sub_port = get_panel_setting("subPort")
    port = int(sub_port) if sub_port else client["inbound_port"]
    sub_id = client.get("sub_id", "")
    if sub_id:
        base_path = get_panel_setting("webBasePath") or ""
        return "http://{}:{}{}sub/{}".format(domain, port, base_path, sub_id)
    return None


def calc_usage_percent(c):
    total = c["total_gb"]
    if not total or total == 0:
        return None
    up = 0; down = 0
    if c["traffic"]:
        up = c["traffic"].get("up", 0)
        down = c["traffic"].get("down", 0)
    used = up + down
    return (used / total) * 100


def make_client_text(c):
    up = 0; down = 0; total = c["total_gb"]
    if c["traffic"]:
        up = c["traffic"].get("up", 0)
        down = c["traffic"].get("down", 0)
        if not total: total = c["traffic"].get("total", 0)
    expiry = format_expiry(c["expiry"])
    status = "فعال" if c["enable"] else "غیرفعال"
    pct = calc_usage_percent(c)
    usage_line = ""
    if pct is not None:
        bar_len = 10
        filled = int(pct / 10)
        bar = "█" * filled + "░" * (bar_len - filled)
        usage_line = "\nمصرف: {:05.1f}%\n{}".format(pct, bar)
    return (
        "نام کاربری: {}\n"
        "پروتکل: {}\n"
        "پورت: {}\n"
        "آپلود: {}\n"
        "دانلود: {}\n"
        "حجم کل: {}{}\n"
        "انقضا: {}\n"
        "وضعیت: {}\n"
    ).format(
        c["email"], c["inbound_protocol"], c["inbound_port"],
        format_bytes(up), format_bytes(down),
        format_bytes(total) if total else "نامحدود", usage_line, expiry, status,
    )


def backup_db():
    db_path = find_database()
    if not db_path:
        return
    from shutil import copy2
    from datetime import datetime
    backup_path = db_path + ".backup." + datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        copy2(db_path, backup_path)
        return backup_path
    except:
        return None


def create_user_in_db(email, total_gb, expiry_days, inbound_id=None):
    db_path = find_database()
    if not db_path:
        return None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if inbound_id:
            cursor.execute("SELECT id, settings, port, protocol FROM inbounds WHERE id=?", (inbound_id,))
        else:
            cursor.execute("SELECT id, settings, port, protocol FROM inbounds WHERE protocol='vless' LIMIT 1")
        row = cursor.fetchone()
        if not row:
            cursor.execute("SELECT id, settings, port, protocol FROM inbounds LIMIT 1")
            row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        inbound_id_actual = row[0]
        settings = json.loads(row[1]) if row[1] else {}
        port = row[2]; protocol = row[3]

        new_uuid = str(uuid_lib.uuid4())
        sub_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        now_ms = int(datetime.now().timestamp() * 1000)

        new_client = {
            "comment": "", "created_at": now_ms, "email": email,
            "enable": True, "expiryTime": expiry_days * 86400 * 1000 if expiry_days > 0 else 0,
            "flow": "",
            "id": new_uuid, "limitIp": 0, "reset": 0,
            "startAfterFirstUse": True,
            "subId": sub_id, "tgId": 0,
            "totalGB": total_gb * 1073741824, "updated_at": now_ms,
        }

        if "clients" not in settings:
            settings["clients"] = []
        settings["clients"].append(new_client)
        cursor.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(settings), inbound_id_actual))
        conn.commit()
        conn.close()
        run_cmd(["systemctl", "restart", "x-ui"])

        return {
            "email": email, "uuid": new_uuid, "sub_id": sub_id,
            "port": port, "inbound_port": port, "protocol": protocol,
            "total_gb": total_gb, "expiry_days": expiry_days,
            "inbound_id": inbound_id_actual,
        }
    except Exception as e:
        logger.error("Create user error: %s", e)
        return None


def update_client_field(email, field, value):
    db_path = find_database()
    if not db_path:
        return False
    backup_db()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, settings FROM inbounds")
        rows = cursor.fetchall()
        for row in rows:
            inbound_id = row[0]
            settings = json.loads(row[1]) if row[1] else {}
            changed = False
            for c in settings.get("clients", []):
                if c.get("email") == email:
                    c[field] = value
                    c["updated_at"] = int(datetime.now().timestamp() * 1000)
                    changed = True
                    break
            if changed:
                cursor.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(settings), inbound_id))
                conn.commit()
                conn.close()
                run_cmd(["systemctl", "restart", "x-ui"])
                return True
        conn.close()
        return False
    except Exception as e:
        logger.error("Update error: %s", e)
        return False


def toggle_client_enable(email):
    db_path = find_database()
    if not db_path:
        return None
    backup_db()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, settings FROM inbounds")
        rows = cursor.fetchall()
        for row in rows:
            inbound_id = row[0]
            settings = json.loads(row[1]) if row[1] else {}
            for c in settings.get("clients", []):
                if c.get("email") == email:
                    new_val = not c.get("enable", True)
                    c["enable"] = new_val
                    c["updated_at"] = int(datetime.now().timestamp() * 1000)
                    cursor.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(settings), inbound_id))
                    conn.commit()
                    conn.close()
                    run_cmd(["systemctl", "restart", "x-ui"])
                    return new_val
        conn.close()
        return None
    except Exception as e:
        logger.error("Toggle error: %s", e)
        return None


def delete_client_from_db(email):
    db_path = find_database()
    if not db_path:
        return False
    backup_db()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, settings FROM inbounds")
        rows = cursor.fetchall()
        for row in rows:
            inbound_id = row[0]
            settings = json.loads(row[1]) if row[1] else {}
            clients = settings.get("clients", [])
            new_clients = [c for c in clients if c.get("email") != email]
            if len(new_clients) < len(clients):
                settings["clients"] = new_clients
                cursor.execute("UPDATE inbounds SET settings=? WHERE id=?", (json.dumps(settings), inbound_id))
                conn.commit()
                conn.close()
                run_cmd(["systemctl", "restart", "x-ui"])
                return True
        conn.close()
        return False
    except Exception as e:
        logger.error("Delete error: %s", e)
        return False


def reset_client_traffic(email):
    db_path = find_database()
    if not db_path:
        return False
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE client_traffics SET up=0, down=0 WHERE email=?", (email,))
        conn.commit()
        conn.close()
        return True
    except:
        return False


def restart_xray():
    run_cmd(["systemctl", "restart", "x-ui"])


async def show_client_detail(query_or_msg, email, is_callback=True):
    client = find_client_full(email)
    if not client:
        txt = "کاربر یافت نشد."
        if is_callback:
            await query_or_msg.edit_message_text(txt)
        else:
            await query_or_msg.reply_text(txt)
        return

    text = make_client_text(client)
    conf_link = get_config_link(client)

    buttons = [
        [InlineKeyboardButton("دریافت کانفیگ", callback_data="config_" + email)],
        [InlineKeyboardButton("QR کد", callback_data="qr_" + email)],
    ]

    if is_admin(query_or_msg.from_user.id if is_callback else query_or_msg.chat.id):
        s = "غیرفعال" if client["enable"] else "فعال"
        buttons.append([
            InlineKeyboardButton("تغییر حجم", callback_data="vol_" + email),
            InlineKeyboardButton("تغییر مدت", callback_data="exp_" + email),
        ])
        buttons.append([
            InlineKeyboardButton(s + " کردن", callback_data="tog_" + email),
            InlineKeyboardButton("ریست ترافیک", callback_data="rst_" + email),
        ])
        buttons.append([
            InlineKeyboardButton("حذف کاربر", callback_data="del_" + email),
        ])

    buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])

    if is_callback:
        await query_or_msg.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await query_or_msg.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    client = search_client_by_telegram_id(user_id)
    if client:
        await show_client_detail(update.message, client["email"], is_callback=False)
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
        keyboard.append([InlineKeyboardButton("📤 بکاپ دیتابیس", callback_data="backup_db")])
        keyboard.append([InlineKeyboardButton("⏳ کاربران در حال اتمام", callback_data="expiring")])
    await message.reply_text("به ربات مدیریت 3x-ui خوش آمدید!", reply_markup=InlineKeyboardMarkup(keyboard))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start - منوی اصلی\n/info - اطلاعات اینباندها\n/clients - لیست کاربران\n"
        "/search <متن> - جستجوی کاربر\n/backup - بکاپ دیتابیس (ادمین)\n"
        "/expiring - کاربران رو به اتمام (ادمین)\n/help - راهنما\n\n"
        "جستجو با: نام کاربری، UUID یا لینک کانفیگ\n"
        "🤖 اعلان خودکار انقضا هر روز ساعت ۸ صبح ارسال می‌شود."
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


async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین!")
        return
    await update.message.reply_text("در حال تهیه بکاپ...")
    db_path = find_database()
    if not db_path:
        await update.message.reply_text("دیتابیس پیدا نشد!")
        return
    from shutil import copy2
    backup_path = db_path + ".backup.tmp"
    try:
        copy2(db_path, backup_path)
        with open(backup_path, "rb") as f:
            await update.message.reply_document(document=f, filename="x-ui.db.backup")
        os.remove(backup_path)
    except Exception as e:
        await update.message.reply_text("خطا در بکاپ: {}".format(e))


async def expiring_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("فقط ادمین!")
        return
    clients = get_all_clients()
    now_ms = int(datetime.now().timestamp() * 1000)
    expiring = []
    for c in clients:
        e = c["expiry"]
        if e == 0:
            continue
        if e < 1600000000000:
            continue
        remaining_days = (e - now_ms) / 86400000
        if 0 < remaining_days <= 7:
            expiring.append((remaining_days, c))
    expiring.sort(key=lambda x: x[0])
    if not expiring:
        await update.message.reply_text("هیچ کاربری در حال اتمام نیست.")
        return
    text = "کاربران در حال اتمام (۷ روز آینده):\n\n"
    for days, c in expiring:
        text += "{} - {} روز\n".format(c["email"], int(days))
    await update.message.reply_text(text)


PAGE_SIZE = 15


async def show_client_list_page(query, context):
    clients = get_all_clients()
    if not clients:
        await query.edit_message_text("هیچ کاربری یافت نشد.")
        return
    page = context.user_data.get("list_page", 0)
    total = len(clients)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    page_clients = clients[start:end]
    buttons = [[InlineKeyboardButton(c["email"], callback_data="client_" + c["email"])] for c in page_clients]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ قبلی", callback_data="list_prev"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("بعدی ▶", callback_data="list_next"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])
    await query.edit_message_text("کاربران (صفحه {}/{}):".format(page + 1, total_pages),
                                  reply_markup=InlineKeyboardMarkup(buttons))


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "my_info":
        user_id = query.from_user.id
        client = search_client_by_telegram_id(user_id)
        if client:
            await show_client_detail(query, client["email"])
        else:
            await query.edit_message_text("اکانتی برای شما یافت نشد.\nاز گزینه جستجو استفاده کنید.",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]))
    elif data == "search_email":
        context.user_data["awaiting_email"] = True
        await query.edit_message_text("UUID یا لینک کانفیگ را بفرستید:")
    elif data == "list_clients":
        context.user_data["list_page"] = 0
        await show_client_list_page(query, context)
    elif data == "list_next":
        context.user_data["list_page"] = context.user_data.get("list_page", 0) + 1
        await show_client_list_page(query, context)
    elif data == "list_prev":
        context.user_data["list_page"] = max(0, context.user_data.get("list_page", 0) - 1)
        await show_client_list_page(query, context)
    elif data == "back_to_menu":
        await back_to_menu(query, context)
    elif data == "new_user":
        if not is_admin(query.from_user.id):
            await query.edit_message_text("این بخش فقط برای ادمین است.")
            return
        context.user_data["creating_user"] = True
        context.user_data["step"] = "email"
        await query.edit_message_text("ایمیل کاربر جدید را وارد کنید:")
    elif data == "cancel_create":
        context.user_data["creating_user"] = False
        await back_to_menu(query, context)
    elif data.startswith("inb_"):
        if not is_admin(query.from_user.id):
            return
        inbound_id = int(data.replace("inb_", ""))
        context.user_data["new_inbound_id"] = inbound_id
        context.user_data["step"] = "traffic"
        await query.edit_message_text("حجم ترافیک (GB) را وارد کنید (0 = نامحدود):")
    elif data.startswith("client_"):
        email = data.replace("client_", "")
        await show_client_detail(query, email)
    elif data.startswith("config_"):
        email = data.replace("config_", "")
        client = find_client_full(email)
        if not client:
            await query.edit_message_text("کاربر یافت نشد.")
            return
        link = get_config_link(client)
        await query.edit_message_text("لینک کانفیگ:\n\n" + link,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_" + email)]]))
    elif data.startswith("qr_"):
        email = data.replace("qr_", "")
        client = find_client_full(email)
        if not client:
            await query.edit_message_text("کاربر یافت نشد.")
            return
        link = get_config_link(client)
        qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=500x500&data=" + link
        await query.message.reply_photo(photo=qr_url, caption="QR کد - " + email)
        await query.message.delete()
    elif data.startswith("back_"):
        email = data.replace("back_", "")
        await show_client_detail(query, email)
    elif data.startswith("tog_"):
        if not is_admin(query.from_user.id):
            return
        email = data.replace("tog_", "")
        result = toggle_client_enable(email)
        if result is not None:
            await show_client_detail(query, email)
        else:
            await query.edit_message_text("خطا!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]))
    elif data.startswith("rst_"):
        if not is_admin(query.from_user.id):
            return
        email = data.replace("rst_", "")
        if reset_client_traffic(email):
            await show_client_detail(query, email)
        else:
            await query.edit_message_text("خطا در ریست ترافیک!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]))
    elif data.startswith("vol_"):
        if not is_admin(query.from_user.id):
            return
        email = data.replace("vol_", "")
        context.user_data["edit_email"] = email
        context.user_data["edit_field"] = "totalGB"
        context.user_data["awaiting_edit_value"] = True
        await query.edit_message_text("حجم جدید را بر حسب GB وارد کنید (0 = نامحدود):")
    elif data.startswith("exp_"):
        if not is_admin(query.from_user.id):
            return
        email = data.replace("exp_", "")
        context.user_data["edit_email"] = email
        context.user_data["edit_field"] = "expiryTime"
        context.user_data["awaiting_edit_value"] = True
        await query.edit_message_text("مدت اعتبار جدید را بر حسب روز وارد کنید (0 = نامحدود):")
    elif data.startswith("del_"):
        if not is_admin(query.from_user.id):
            return
        email = data.replace("del_", "")
        keyboard = [
            [InlineKeyboardButton("بله، حذف شود", callback_data="delc_" + email)],
            [InlineKeyboardButton("انصراف", callback_data="back_" + email)],
        ]
        await query.edit_message_text("آیا از حذف کاربر '{}' اطمینان دارید؟ این عمل قابل بازگشت نیست.".format(email),
                                      reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("delc_"):
        if not is_admin(query.from_user.id):
            return
        email = data.replace("delc_", "")
        if delete_client_from_db(email):
            await query.edit_message_text("کاربر '{}' با موفقیت حذف شد.".format(email),
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]))
        else:
            await query.edit_message_text("خطا در حذف کاربر!",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]))
    elif data == "backup_db":
        if not is_admin(query.from_user.id):
            return
        await query.edit_message_text("در حال تهیه بکاپ...")
        db_path = find_database()
        if not db_path:
            await query.edit_message_text("دیتابیس پیدا نشد!")
            return
        from shutil import copy2
        backup_path = db_path + ".backup.tmp"
        try:
            copy2(db_path, backup_path)
            with open(backup_path, "rb") as f:
                await query.message.reply_document(document=f, filename="x-ui.db.backup")
            os.remove(backup_path)
            await query.message.reply_text("بکاپ با موفقیت ارسال شد.",
                                           reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]))
        except Exception as e:
            await query.edit_message_text("خطا در بکاپ: {}".format(e))
    elif data == "expiring":
        if not is_admin(query.from_user.id):
            return
        clients = get_all_clients()
        now_ms = int(datetime.now().timestamp() * 1000)
        expiring = []
        for c in clients:
            e = c["expiry"]
            if e == 0 or e >= 1600000000000:
                continue
            remaining_days = (e - now_ms) / 86400000
            if 0 < remaining_days <= 7:
                expiring.append((remaining_days, c))
        expiring.sort(key=lambda x: x[0])
        if not expiring:
            await query.edit_message_text("هیچ کاربری در حال اتمام نیست.",
                                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]))
            return
        text = "کاربران در حال اتمام (۷ روز آینده):\n\n"
        for days, c in expiring:
            text += "{} - {} روز\n".format(c["email"], int(days))
        text += "\n(جهت تنظیم پیام اعلان از /notify_config استفاده کنید)"
        await query.edit_message_text(text,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]))


async def show_search_results(message, query):
    results = search_clients(query)
    if not results:
        keyboard = [[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]
        await message.reply_text("نتیجه‌ای برای '{}' یافت نشد.\n".format(query) +
                                 "می‌توانید ایمیل، UUID یا لینک کانفیگ بفرستید.",
                                 reply_markup=InlineKeyboardMarkup(keyboard))
        return
    if len(results) == 1:
        await show_client_detail(message, results[0]["email"], is_callback=False)
        return
    buttons = [[InlineKeyboardButton(r["email"], callback_data="client_" + r["email"])] for r in results]
    buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])
    await message.reply_text("{} نتیجه یافت شد:".format(len(results)), reply_markup=InlineKeyboardMarkup(buttons))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Handle admin edit value (volume / expiry)
    if context.user_data.get("awaiting_edit_value"):
        if not is_admin(user_id):
            context.user_data["awaiting_edit_value"] = False
            return
        try:
            val = int(text)
            if val < 0:
                raise ValueError
        except:
            await update.message.reply_text("عدد معتبر وارد کنید:")
            return

        email = context.user_data.get("edit_email", "")
        field = context.user_data.get("edit_field", "")
        context.user_data["awaiting_edit_value"] = False

        if field == "totalGB":
            success = update_client_field(email, "totalGB", val * 1073741824)
        elif field == "expiryTime":
            success = update_client_field(email, "expiryTime", val * 86400 * 1000 if val > 0 else 0)
        else:
            success = False

        if success:
            await show_client_detail(update.message, email, is_callback=False)
        else:
            await update.message.reply_text("خطا!")

        return

    # Handle create user flow
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
            inbounds = get_inbounds()
            if len(inbounds) == 1:
                context.user_data["new_inbound_id"] = inbounds[0]["id"]
                context.user_data["step"] = "traffic"
                await update.message.reply_text("حجم ترافیک (GB) را وارد کنید (0 = نامحدود):")
            else:
                buttons = [[InlineKeyboardButton("{}:{} ({})".format(ib["protocol"], ib["port"], ib["id"]),
                                                 callback_data="inb_" + str(ib["id"]))] for ib in inbounds]
                buttons.append([InlineKeyboardButton("انصراف", callback_data="cancel_create")])
                await update.message.reply_text("یک اینباند انتخاب کنید:",
                                                reply_markup=InlineKeyboardMarkup(buttons))
        elif step == "traffic":
            try:
                gb = int(text)
                if gb < 0: raise ValueError
            except:
                await update.message.reply_text("عدد معتبر وارد کنید (0 = نامحدود):")
                return
            context.user_data["new_traffic"] = gb
            context.user_data["step"] = "expiry"
            await update.message.reply_text("مدت اعتبار (روز) را وارد کنید (0 = نامحدود):")
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

            inbound_id = context.user_data.get("new_inbound_id")
            result = create_user_in_db(email, total_gb, days, inbound_id=inbound_id)
            if result:
                expiry_text = "نامحدود" if days == 0 else "{} روز".format(days)
                traffic_text = "نامحدود" if total_gb == 0 else "{} GB".format(total_gb)

                conf_link = get_config_link(result)
                sub_link = get_subscription_link(result)

                msg = (
                    "کاربر با موفقیت ساخته شد!\n\n"
                    "ایمیل: {}\n"
                    "UUID: {}\n"
                    "Sub ID: {}\n"
                    "حجم: {}\n"
                    "اعتبار: {}\n"
                    "پورت: {} ({})\n\n"
                    "لینک کانفیگ:\n"
                    "{}\n"
                ).format(result["email"], result["uuid"], result["sub_id"],
                         traffic_text, expiry_text, result["port"], result["protocol"],
                         conf_link)

                if sub_link:
                    msg += "\nلینک ساب:\n" + sub_link

                await update.message.reply_text(msg)

                qr_url = "https://api.qrserver.com/v1/create-qr-code/?size=500x500&data=" + conf_link
                await update.message.reply_photo(photo=qr_url, caption="QR کد")

                keyboard = [[InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")]]
                await update.message.reply_text("از دکمه زیر بازگردید:", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                keyboard = [[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]
                await update.message.reply_text("خطا در ساخت کاربر!", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Normal search
    if context.user_data.get("awaiting_email"):
        context.user_data["awaiting_email"] = False
        await show_search_results(update.message, text)
        return

    results = search_clients(text)
    if results:
        if len(results) == 1:
            await show_client_detail(update.message, results[0]["email"], is_callback=False)
        else:
            buttons = [[InlineKeyboardButton(r["email"], callback_data="client_" + r["email"])] for r in results]
            buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])
            await update.message.reply_text("چند نتیجه یافت شد:", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text("دستور نامعتبر. /help یا /start را بزنید.")


async def back_to_menu(query, context):
    keyboard = [
        [InlineKeyboardButton("اطلاعات من", callback_data="my_info")],
        [InlineKeyboardButton("جستجوی خودکار", callback_data="search_email")],
        [InlineKeyboardButton("لیست کاربران", callback_data="list_clients")],
    ]
    if is_admin(query.from_user.id):
        keyboard.append([InlineKeyboardButton("ساخت کاربر جدید", callback_data="new_user")])
        keyboard.append([InlineKeyboardButton("📤 بکاپ دیتابیس", callback_data="backup_db")])
        keyboard.append([InlineKeyboardButton("⏳ کاربران در حال اتمام", callback_data="expiring")])
    await query.edit_message_text("به ربات مدیریت 3x-ui خوش آمدید!", reply_markup=InlineKeyboardMarkup(keyboard))


NOTIFY_DAYS = [3, 1]


async def check_expiry(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Checking expiry notifications...")
    clients = get_all_clients()
    now_ms = int(datetime.now().timestamp() * 1000)
    for c in clients:
        tg_id = c.get("tg_id", 0)
        if not tg_id:
            continue
        e = c["expiry"]
        if e == 0 or e < 1600000000000:
            continue
        remaining = (e - now_ms) / 86400000
        for nd in NOTIFY_DAYS:
            if int(remaining) == nd:
                try:
                    msg = "⚠️ هشدار اشتراک\n\nکاربر: {}\n{} روز تا اتمام اشتراک باقی است.".format(c["email"], nd)
                    await context.bot.send_message(chat_id=tg_id, text=msg)
                    logger.info("Notified %s (%d days left)", c["email"], nd)
                except Exception as ex:
                    logger.warning("Failed to notify %s: %s", c["email"], ex)
                break


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
    app.add_handler(CommandHandler("backup", backup_command))
    app.add_handler(CommandHandler("expiring", expiring_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    job_queue = app.job_queue
    if job_queue:
        job_queue.run_daily(check_expiry, time=datetime.strptime("08:00", "%H:%M").time(), name="expiry_check")

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
