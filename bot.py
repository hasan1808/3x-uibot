import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from config import TELEGRAM_BOT_TOKEN, PANEL_URL, PANEL_USERNAME, PANEL_PASSWORD
from panel_api import PanelAPI, format_bytes, format_expiry

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

panel = None


def get_panel():
    global panel
    if panel is None:
        panel = PanelAPI(PANEL_URL, PANEL_USERNAME, PANEL_PASSWORD)
    return panel


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("اطلاعات اشتراک من", callback_data="my_info")],
        [InlineKeyboardButton("لیست کلاینت‌ها", callback_data="list_clients")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "به ربات مدیریت 3x-ui خوش آمدید!\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "دستورات موجود:\n"
        "/start - شروع و نمایش منو\n"
        "/info - نمایش اطلاعات اشتراک\n"
        "/clients - لیست کلاینت‌ها\n"
        "/help - راهنما"
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
    try:
        p = get_panel()
        inbounds = p.get_inbounds()

        if not inbounds:
            await update.message.reply_text("هیچ اینبانتی یافت نشد.")
            return

        text = "اطلاعات اینبانت‌ها:\n\n"
        for inbound in inbounds:
            client_count = len(inbound.get("clientStats", []))
            text += (
                f"ID: {inbound.get('id')}\n"
                f"پروتکل: {inbound.get('protocol')}\n"
                f"پورت: {inbound.get('port')}\n"
                f"تعداد کلاینت: {client_count}\n"
                f"---\n"
            )

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")


async def show_my_info_callback(query, context):
    try:
        p = get_panel()
        inbounds = p.get_inbounds()

        if not inbounds:
            await query.edit_message_text("هیچ اینبانتی یافت نشد.")
            return

        text = "اطلاعات اینبانت‌ها:\n\n"
        for inbound in inbounds:
            client_count = len(inbound.get("clientStats", []))
            text += (
                f"ID: {inbound.get('id')}\n"
                f"پروتکل: {inbound.get('protocol')}\n"
                f"پورت: {inbound.get('port')}\n"
                f"تعداد کلاینت: {client_count}\n"
                f"---\n"
            )

        keyboard = [[InlineKeyboardButton("بازگشت", callback_data="back_to_menu")]]
        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        await query.edit_message_text(f"خطا: {e}")


async def show_clients_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        p = get_panel()
        inbounds = p.get_inbounds()

        text = "لیست کلاینت‌ها:\n\n"
        for inbound in inbounds:
            settings = p._parse_settings(inbound.get("settings", ""))
            for client in settings.get("clients", []):
                email = client.get("email", "نامشخص")
                stats = None
                for cs in inbound.get("clientStats", []):
                    if cs.get("email") == email:
                        stats = cs
                        break

                up = format_bytes(stats.get("up", 0)) if stats else "0"
                down = format_bytes(stats.get("down", 0)) if stats else "0"
                expiry = format_expiry(client.get("expiry")) if client.get("expiry") else "نامحدود"

                text += (
                    f"نام: {email}\n"
                    f"آپلود: {up}\n"
                    f"دانلود: {down}\n"
                    f"انقضا: {expiry}\n"
                    f"---\n"
                )

        await update.message.reply_text(text)
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")


async def show_clients_list_callback(query, context):
    try:
        p = get_panel()
        inbounds = p.get_inbounds()

        buttons = []
        for inbound in inbounds:
            settings = p._parse_settings(inbound.get("settings", ""))
            for client in settings.get("clients", []):
                email = client.get("email", "نامشخص")
                buttons.append(
                    [InlineKeyboardButton(email, callback_data=f"client_{email}")]
                )

        buttons.append([InlineKeyboardButton("بازگشت", callback_data="back_to_menu")])

        text = "یک کلاینت را انتخاب کنید:\n"
        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(buttons)
        )
    except Exception as e:
        await query.edit_message_text(f"خطا: {e}")


async def show_client_details_callback(query, email, context):
    try:
        p = get_panel()
        result = p.find_client_by_email(email)

        if not result:
            await query.edit_message_text(f"کلاینت {email} یافت نشد.")
            return

        client = result["client"]
        stats = result["stats"]
        inbound = result["inbound"]

        up = format_bytes(stats.get("up", 0)) if stats else "0"
        down = format_bytes(stats.get("down", 0)) if stats else "0"
        total = up + " / " + down
        expiry = format_expiry(client.get("expiry")) if client.get("expiry") else "نامحدود"
        limit = format_bytes(client.get("limit", 0)) if client.get("limit") else "نامحدود"

        text = (
            f"جزئیات کلاینت: {email}\n\n"
            f"پروتکل: {inbound.get('protocol')}\n"
            f"پورت: {inbound.get('port')}\n"
            f"آپلود: {up}\n"
            f"دانلود: {down}\n"
            f"محدودیت ترافیک: {limit}\t\n"
            f"تاریخ انقضا: {expiry}\n"
        )

        keyboard = [
            [InlineKeyboardButton("بازگشت", callback_data="list_clients")],
            [InlineKeyboardButton("منوی اصلی", callback_data="back_to_menu")],
        ]
        await query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        await query.edit_message_text(f"خطا: {e}")


async def back_to_menu(query, context):
    keyboard = [
        [InlineKeyboardButton("اطلاعات اشتراک من", callback_data="my_info")],
        [InlineKeyboardButton("لیست کلاینت‌ها", callback_data="list_clients")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "به ربات مدیریت 3x-ui خوش آمدید!\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup,
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
