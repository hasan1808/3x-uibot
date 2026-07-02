#!/bin/bash

set -e

INSTALL_DIR="/opt/3x-ui-bot"
SERVICE_NAME="3x-ui-bot"

echo "========================================="
echo "   نصب ربات مدیریت 3x-ui"
echo "========================================="

echo ""
echo "[1/5] ایجاد دایرکتوری نصب..."
mkdir -p $INSTALL_DIR

echo "[2/5] کپی فایل‌ها..."
cp bot.py config.py panel_api.py requirements.txt $INSTALL_DIR/
chmod 600 $INSTALL_DIR/.env 2>/dev/null || true

echo "[3/5] نصب پایتون و pip..."
apt-get update
apt-get install -y python3 python3-pip python3.8-venv
apt-get install -y python3-venv 2>/dev/null || true

echo "[4/5] ایجاد محیط مجازی و نصب پکیج‌ها..."
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo "[5/5] ساخت فایل سرویس systemd..."
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
echo "   نصب با موفقیت انجام شد!"
echo "========================================="
echo ""
echo "下一步:"
echo "  1. فایل تنظیمات رو پر کن:"
echo "     nano $INSTALL_DIR/.env"
echo ""
echo "  2. سرویس رو استارت کن:"
echo "     systemctl start $SERVICE_NAME"
echo ""
echo "  3. وضعیت سرویس:"
echo "     systemctl status $SERVICE_NAME"
echo ""
echo "  4. لاگ‌ها:"
echo "     journalctl -u $SERVICE_NAME -f"
echo ""
