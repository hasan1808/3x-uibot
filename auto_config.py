import sqlite3
import os

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


def get_bot_token():
    db_path = find_database()
    if not db_path:
        return ""

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key='tgBotToken'")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            return str(row[0])
    except Exception as e:
        print("Error: " + str(e))

    return ""


if __name__ == "__main__":
    token = get_bot_token()
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    with open(env_path, "w") as f:
        f.write("TELEGRAM_BOT_TOKEN=" + token)

    if token:
        print("Done! Bot token saved.")
    else:
        print("No bot token found in database.")
