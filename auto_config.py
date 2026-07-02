import sqlite3
import os
import yaml
import json

PANEL_DB_PATHS = [
    "/etc/x-ui/x-ui.db",
    "/usr/local/x-ui/x-ui.db",
    "/opt/x-ui/x-ui.db",
]

PANEL_CONFIG_PATHS = [
    "/etc/x-ui/x-ui.yml",
    "/usr/local/x-ui/x-ui.yml",
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


def find_config():
    for path in PANEL_CONFIG_PATHS:
        if os.path.exists(path):
            return path
    return None


def read_from_database(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        config = {}

        if "settings" in tables:
            cursor.execute("SELECT key, value FROM settings;")
            for row in cursor.fetchall():
                key, value = row
                config[key] = value

        if "clients" in tables:
            cursor.execute("SELECT email, telegram_id, sub_id FROM clients LIMIT 1;")
            row = cursor.fetchone()
            if row:
                config["client_email"] = row[0]
                config["telegram_id"] = row[1]
                config["sub_id"] = row[2]

        conn.close()
        return config

    except Exception as e:
        print(f"Error reading database: {e}")
        return {}


def read_from_config(config_path):
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config if config else {}
    except Exception as e:
        print(f"Error reading config: {e}")
        return {}


def get_panel_url():
    xray_configs = [
        "/etc/x-ui/xray_config.json",
        "/usr/local/x-ui/xray_config.json",
    ]
    for path in xray_configs:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    config = json.load(f)
                for inbound in config.get("inbounds", []):
                    port = inbound.get("port")
                    if port:
                        return f"http://localhost:{port}"
            except:
                pass
    return None


def find_bot_token():
    db_path = find_database()
    if db_path:
        config = read_from_database(db_path)
        for key in ["bot_token", "telegram_bot_token", "botToken"]:
            if key in config and config[key]:
                return config[key]
    return None


def find_panel_credentials():
    db_path = find_database()
    if db_path:
        config = read_from_database(db_path)
        username = None
        password = None
        for key in ["username", "panel_username", "login_user"]:
            if key in config and config[key]:
                username = config[key]
                break
        for key in ["password", "panel_password", "login_password"]:
            if key in config and config[key]:
                password = config[key]
                break
        return username, password
    return None, None


def generate_env_file():
    bot_token = find_bot_token()
    username, password = find_panel_credentials()

    lines = []

    if bot_token:
        lines.append(f"TELEGRAM_BOT_TOKEN={bot_token}")
    else:
        lines.append("TELEGRAM_BOT_TOKEN=")

    lines.append("PANEL_URL=http://localhost:2053")

    if username:
        lines.append(f"PANEL_USERNAME={username}")
    else:
        lines.append("PANEL_USERNAME=admin")

    if password:
        lines.append(f"PANEL_PASSWORD={password}")
    else:
        lines.append("PANEL_PASSWORD=")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Scanning for 3x-ui configuration...")

    db_path = find_database()
    config_path = find_config()

    if db_path:
        print(f"Database found: {db_path}")
    else:
        print("No database found")

    if config_path:
        print(f"Config found: {config_path}")
    else:
        print("No config found")

    bot_token = find_bot_token()
    if bot_token:
        print(f"Bot token found: {bot_token[:10]}...")
    else:
        print("No bot token found in database")

    print("\nGenerated .env content:")
    print(generate_env_file())
