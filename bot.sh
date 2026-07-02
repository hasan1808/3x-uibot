#!/bin/bash

SERVICE_NAME="3x-ui-bot"
INSTALL_DIR="/opt/3x-ui-bot"

case "$1" in
    start)
        echo "استارت ربات..."
        systemctl start $SERVICE_NAME
        ;;
    stop)
        echo "توقف ربات..."
        systemctl stop $SERVICE_NAME
        ;;
    restart)
        echo "ریستارت ربات..."
        systemctl restart $SERVICE_NAME
        ;;
    status)
        systemctl status $SERVICE_NAME
        ;;
    logs)
        journalctl -u $SERVICE_NAME -f
        ;;
    config)
        nano $INSTALL_DIR/.env
        ;;
    *)
        echo "استفاده: $0 {start|stop|restart|status|logs|config}"
        exit 1
        ;;
esac
