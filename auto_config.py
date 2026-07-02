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


def read_all_settings(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        config = {}

        for table in tables:
            try:
                cursor.execute("PRAGMA table_info(" + table + ");")
                columns = [col[1] for col in cursor.fetchall()]

                cursor.execute("SELECT * FROM " + table + ";")
                rows = cursor.fetchall()

                for row in rows:
                    for i, col in enumerate(columns):
                        if i < len(row):
                            val = str(row[i]) if row[i] else ""
                            if "token" in col.lower() or "bot" in col.lower():
                                config[col] = val
                            elif col.lower() in ["username", "password"]:
                                config[col] = val
                            elif col.lower() == "key" and i + 1 < len(row):
                                config[str(row[i])] = str(row[i + 1]) if row[i + 1] else ""
            except Exception:
                continue

        conn.close()
        return config, tables

    except Exception as e:
        print("Error reading database: " + str(e))
        return {}, []


def generate_env_file():
    db_path = find_database()

    if not db_path:
        print("No database found")
        return "TELEGRAM_BOT_TOKEN=\nPANEL_URL=http://localhost:2053\nPANEL_USERNAME=admin\nPANEL_PASSWORD="

    config, tables = read_all_settings(db_path)
    print("Database: " + db_path)
    print("Tables: " + str(tables))
    print("Found keys: " + str(list(config.keys())))

    bot_token = ""
    for key in config:
        if "bot_token" in key.lower() or "token" in key.lower():
            if config[key] and len(config[key]) > 10:
                bot_token = config[key]
                break

    username = config.get("username", "admin")
    password = config.get("password", "")

    lines = [
        "TELEGRAM_BOT_TOKEN=" + bot_token,
        "PANEL_URL=http://localhost:2053",
        "PANEL_USERNAME=" + username,
        "PANEL_PASSWORD=" + password,
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    print("Scanning for 3x-ui configuration...")

    db_path = find_database()

    if db_path:
        print("Database found: " + db_path)
    else:
        print("No database found")

    bot_token = ""
    config, tables = read_all_settings(db_path) if db_path else ({}, [])
    for key in config:
        if "bot_token" in key.lower() and config[key] and len(config[key]) > 10:
            bot_token = config[key]
            break

    if bot_token:
        print("Bot token found: " + bot_token[:10] + "...")
    else:
        print("No bot token found in database")

    print("\nGenerated .env content:")
    print(generate_env_file())
