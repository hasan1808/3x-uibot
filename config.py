import os

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SERVER_DOMAIN = os.getenv("SERVER_DOMAIN", "")
try:
    ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
except:
    ADMIN_TELEGRAM_ID = 0
try:
    SUBSCRIPTION_PORT = int(os.getenv("SUBSCRIPTION_PORT", "0"))
except:
    SUBSCRIPTION_PORT = 0
