#!/bin/bash

set -e

INSTALL_DIR="/opt/3x-ui-bot"
SERVICE_NAME="3x-ui-bot"

echo "========================================="
echo "   3x-ui Telegram Bot Installer"
echo "========================================="
echo ""

echo "[1/6] Creating install directory..."
mkdir -p $INSTALL_DIR

echo "[2/6] Copying files..."
cp bot.py config.py requirements.txt $INSTALL_DIR/
cp bot.sh $INSTALL_DIR/
chmod +x $INSTALL_DIR/bot.sh

echo "[3/6] Installing Python and dependencies..."
# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
fi

if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    kill -9 $(pgrep -f apt-get) 2>/dev/null || true
    sleep 2
    apt-get update -qq 2>/dev/null || true
    apt-get install -y -qq python3 python3-pip sqlite3 2>/dev/null || true
    # Try multiple venv package names
    apt-get install -y -qq python3-venv 2>/dev/null || \
    apt-get install -y -qq python3.11-venv 2>/dev/null || \
    apt-get install -y -qq python3.10-venv 2>/dev/null || \
    apt-get install -y -qq python3.9-venv 2>/dev/null || true
elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "fedora" ]; then
    yum install -y -q python3 python3-pip sqlite 2>/dev/null || true
    python3 -m ensurepip --upgrade 2>/dev/null || true
else
    apt-get update -qq 2>/dev/null || true
    apt-get install -y -qq python3 python3-pip sqlite3 python3-venv 2>/dev/null || true
fi

echo "[4/6] Creating virtual environment and installing packages..."
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

echo "[5/6] Configuring bot token..."
DB_PATH=""
for p in /etc/x-ui/x-ui.db /usr/local/x-ui/x-ui.db /opt/x-ui/x-ui.db; do
    [ -f "$p" ] && DB_PATH="$p" && break
done

TOKEN=""
if [ -n "$DB_PATH" ]; then
    DB_TOKEN=$(sqlite3 "$DB_PATH" "SELECT value FROM settings WHERE key='tgBotToken';")
    if [ -n "$DB_TOKEN" ]; then
        echo "  Bot token found in panel database: ${DB_TOKEN:0:15}..."
        read -p "  Use this token? (Y/n): " USE_DB_TOKEN
        if [ "$USE_DB_TOKEN" != "n" ] && [ "$USE_DB_TOKEN" != "N" ]; then
            TOKEN="$DB_TOKEN"
        fi
    fi
fi

if [ -z "$TOKEN" ]; then
    echo ""
    echo "  Enter your Telegram bot token."
    echo "  (Get it from @BotFather in Telegram)"
    read -p "  Bot token: " TOKEN
fi

echo ""
echo "  Enter your Telegram user ID (admin)."
echo "  (Use @userinfobot in Telegram to get your ID)"
read -p "  Admin Telegram ID: " ADMIN_ID

echo ""
echo "  Enter your server domain or IP address."
echo "  (Used for generating config links)"
read -p "  Server domain/IP: " SERVER_DOMAIN

cat > $INSTALL_DIR/.env << EOF
TELEGRAM_BOT_TOKEN=$TOKEN
ADMIN_TELEGRAM_ID=$ADMIN_ID
SERVER_DOMAIN=$SERVER_DOMAIN
EOF

# If SERVER_DOMAIN is empty, remove it from .env
if [ -z "$SERVER_DOMAIN" ]; then
    sed -i '/^SERVER_DOMAIN=/d' $INSTALL_DIR/.env
fi

chmod 600 $INSTALL_DIR/.env
echo "  .env file created"

if [ -n "$DB_PATH" ]; then
    echo "  Disabling built-in bot in panel..."
    sqlite3 "$DB_PATH" "UPDATE settings SET value='false' WHERE key='tgBotEnable';"
    echo "  Built-in bot disabled"
    systemctl restart x-ui 2>/dev/null || true
fi

echo "[6/6] Creating systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=3x-ui Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
Environment=PATH=$INSTALL_DIR/venv/bin
ExecStart=$INSTALL_DIR/venv/bin/python3 bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME

echo ""
echo "========================================="
echo "   Installation completed!"
echo "========================================="
echo ""
echo "Starting the bot..."
systemctl restart $SERVICE_NAME
sleep 3

if systemctl is-active --quiet $SERVICE_NAME; then
    echo " Bot is running!"
    echo ""
    echo "Commands:"
    echo "  /opt/3x-ui-bot/bot.sh status   - Check status"
    echo "  /opt/3x-ui-bot/bot.sh logs     - View logs"
    echo "  /opt/3x-ui-bot/bot.sh restart  - Restart"
    echo "  /opt/3x-ui-bot/bot.sh config   - Edit token"
else
    echo " Bot failed. Check logs: journalctl -u $SERVICE_NAME -f"
fi
