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
cp bot.py config.py requirements.txt auto_config.py $INSTALL_DIR/
cp bot.sh $INSTALL_DIR/
chmod +x $INSTALL_DIR/bot.sh

echo "[3/6] Installing Python and dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3.8-venv python3-venv 2>/dev/null || true
apt-get install -y sqlite3 2>/dev/null || true

echo "[4/6] Creating virtual environment and installing packages..."
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "[5/6] Auto-detecting bot token from panel database..."
python3 auto_config.py

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
systemctl start $SERVICE_NAME

sleep 2
echo ""
echo "Bot status:"
systemctl is-active $SERVICE_NAME

if systemctl is-active --quiet $SERVICE_NAME; then
    echo ""
    echo " Bot is running! Send /start to @your_bot_username in Telegram."
    echo ""
    echo "Commands:"
    echo "  /opt/3x-ui-bot/bot.sh status  - Check status"
    echo "  /opt/3x-ui-bot/bot.sh logs    - View logs"
    echo "  /opt/3x-ui-bot/bot.sh restart - Restart bot"
else
    echo ""
    echo " Bot failed to start. Check the log:"
    echo "  journalctl -u $SERVICE_NAME -f"
fi
