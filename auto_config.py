import sqlite3
import os
import subprocess

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


def run(cmd):
    try:
        subprocess.run(cmd, shell=True, capture_output=True)
    except:
        pass


def disable_builtin_bot():
    db_path = find_database()
    if not db_path:
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("UPDATE settings SET value='false' WHERE key='tgBotEnable'")
        cursor.execute("UPDATE settings SET value='' WHERE key='tgBotToken'")
        cursor.execute("UPDATE settings SET value='' WHERE key='tgBotChatId'")
        conn.commit()
        conn.close()

        print(" Built-in bot removed from database")
        print(" Restarting x-ui panel...")

        run("systemctl restart x-ui")

        print(" Done! Built-in bot disabled permanently.")
    except Exception as e:
        print("Error: " + str(e))


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
        print("Error reading token: " + str(e))

    return ""


if __name__ == "__main__":
    db_path = find_database()

    if not db_path:
        print("Error: 3x-ui database not found")
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        with open(env_path, "w") as f:
            f.write("TELEGRAM_BOT_TOKEN=")
        exit(1)

    print("Database found at: " + db_path)

    token = get_bot_token()
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    with open(env_path, "w") as f:
        f.write("TELEGRAM_BOT_TOKEN=" + token)

    if token:
        print("Bot token loaded: " + token[:15] + "...")
        disable_builtin_bot()
    else:
        print("Warning: No bot token found in panel settings.")
        print("Go to Panel UI > Settings > Telegram Bot and set your token.")
