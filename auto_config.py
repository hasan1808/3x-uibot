import sqlite3
import os

PANEL_DB_PATHS = [
    "/etc/x-ui/x-ui.db",
    "/usr/local/x-ui/x-ui.db",
    "/opt/x-ui/x-ui.db",
]

WEB_DB_PATHS = [
    "/var/www/html/x-ui/x-ui.db",
    "/var/www/x-ui/x-ui.db",
]


def find_database():
    for path in PANEL_DB_PATHS + WEB_DB_PATHS:
        if os.path.exists(path):
            return path
    return None


def read_settings_table(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        config = {}

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        if "settings" in tables:
            cursor.execute("SELECT key, value FROM settings;")
            for row in cursor.fetchall():
                key, value = row
                if key and value:
                    config[str(key)] = str(value)

        conn.close()
        return config, tables

    except Exception as e:
        print("Error reading database: " + str(e))
        return {}, []


def get_env_content():
    db_path = find_database()

    if not db_path:
        print("No database found")
        return "TELEGRAM_BOT_TOKEN=\nPANEL_URL=http://localhost:2053\nPANEL_USERNAME=admin\nPANEL_PASSWORD="

    config, tables = read_settings_table(db_path)
    print("Database: " + db_path)
    print("Tables: " + str(tables))
    print("Settings found: " + str(list(config.keys())))

    bot_token = config.get("telegramBotToken", "")
    if not bot_token:
        bot_token = config.get("bot_token", "")
    if not bot_token:
        for key in config:
            if "token" in key.lower() and config[key] and len(config[key]) > 10:
                bot_token = config[key]
                break

    username = config.get("username", "admin")
    password = config.get("password", "")

    if bot_token:
        print("Bot token found: " + bot_token[:10] + "...")
    else:
        print("No bot token found")

    lines = [
        "TELEGRAM_BOT_TOKEN=" + bot_token,
        "PANEL_URL=http://localhost:2053",
        "PANEL_USERNAME=" + username,
        "PANEL_PASSWORD=" + password,
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    print("Scanning for 3x-ui panel settings...")
    print("")
    print(get_env_content())
