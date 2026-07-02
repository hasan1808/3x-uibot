#!/bin/bash

set -e

INSTALL_DIR="/opt/3x-ui-bot"
SERVICE_NAME="3x-ui-bot"

echo "========================================="
echo "   3x-ui Telegram Bot Installer"
echo "========================================="

echo ""
echo "[1/7] Creating install directory..."
mkdir -p $INSTALL_DIR

echo "[2/7] Copying files..."
cp bot.py config.py panel_api.py requirements.txt auto_config.py disable_builtin_bot.sh $INSTALL_DIR/
cp bot.sh $INSTALL_DIR/
chmod +x $INSTALL_DIR/*.sh
chmod 600 $INSTALL_DIR/.env 2>/dev/null || true

echo "[3/7] Installing Python and dependencies..."
apt-get update
apt-get install -y python3 python3-pip python3.8-venv
apt-get install -y python3-venv 2>/dev/null || true
apt-get install -y sqlite3 2>/dev/null || true

echo "[4/7] Creating virtual environment and installing packages..."
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyyaml 2>/dev/null || true

echo "[5/7] Auto-detecting panel configuration..."
python3 auto_config.py > /tmp/auto_config_output.txt 2>&1 || true

echo "[6/7] Generating .env file..."
if [ ! -f "$INSTALL_DIR/.env" ] || [ ! -s "$INSTALL_DIR/.env" ]; then
    python3 -c "
import sys
sys.path.insert(0, '$INSTALL_DIR')
from auto_config import generate_env_file
print(generate_env_file())
" > $INSTALL_DIR/.env
    echo "  .env file generated from panel config"
else
    echo "  .env file already exists, keeping current config"
fi

chmod 600 $INSTALL_DIR/.env

echo "[7/7] Creating systemd service..."
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=3x-ui Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
ExecStart=$INSTALL_DIR/venv/bin/python3 bot.py
Restart=always
RestartSec=10

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
echo "Detected configuration:"
cat $INSTALL_DIR/.env | sed 's/PASSWORD=.*/PASSWORD=***/'
echo ""
echo "Next steps:"
echo "  1. Verify/ Edit the config file:"
echo "     nano $INSTALL_DIR/.env"
echo ""
echo "  2. Disable built-in bot (optional):"
echo "     $INSTALL_DIR/disable_builtin_bot.sh"
echo ""
echo "  3. Start the new bot:"
echo "     systemctl start $SERVICE_NAME"
echo ""
echo "  4. Check status:"
echo "     systemctl status $SERVICE_NAME"
echo ""
echo "  5. View logs:"
echo "     journalctl -u $SERVICE_NAME -f"
echo ""
