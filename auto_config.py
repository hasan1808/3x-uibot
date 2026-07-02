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

    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    existing_token = ""
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    val = line.strip().split("=", 1)
                    if len(val) > 1 and val[1]:
                        existing_token = val[1]

    db_token = get_bot_token()
    token = existing_token or db_token

    if not existing_token:
        with open(env_path, "w") as f:
            f.write("TELEGRAM_BOT_TOKEN=" + token)

    if token:
        print("Token loaded: " + token[:15] + "...")
        disable_builtin_bot()
        print("Killing old bot completely...")
        run("systemctl stop x-ui")
        import time
        time.sleep(2)
        # Kill ALL x-ui processes
        run("kill $(pgrep x-ui 2>/dev/null) 2>/dev/null || true")
        run("kill -9 $(pgrep -f '/usr/local/x-ui' 2>/dev/null) 2>/dev/null || true")
        time.sleep(25)
        print("Waiting 25s for Telegram to expire old session...")
        run("systemctl start x-ui")
        print("Done!")
    else:
        print("No token found. Add it in Panel UI > Settings > Telegram Bot.")
