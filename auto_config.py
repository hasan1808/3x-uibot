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


def disable_builtin_bot():
    db_path = find_database()
    if not db_path:
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE settings SET value='false' WHERE key='tgBotEnable'")
        conn.commit()
        conn.close()
        print(" Built-in bot disabled (tgBotEnable = false)")
    except Exception as e:
        print("Error disabling bot: " + str(e))


if __name__ == "__main__":
    db_path = find_database()

    if not db_path:
        print("3x-ui database not found!")
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        with open(env_path, "w") as f:
            f.write("TELEGRAM_BOT_TOKEN=")
        exit(1)

    print("Database: " + db_path)

    token = get_bot_token()
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    with open(env_path, "w") as f:
        f.write("TELEGRAM_BOT_TOKEN=" + token)

    if token:
        print("Token loaded: " + token[:15] + "...")
        disable_builtin_bot()
        print("Fully restarting x-ui to kill old bot...")
        run("systemctl stop x-ui")
        import time
        time.sleep(3)
        run("killall -9 x-ui 2>/dev/null || true")
        run("pkill -f 'x-ui' 2>/dev/null || true")
        time.sleep(1)
        run("systemctl start x-ui")
        print("Done!")
    else:
        print("No token found. Add it in Panel UI > Settings > Telegram Bot.")
