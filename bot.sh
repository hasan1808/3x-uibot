#!/bin/bash

SERVICE_NAME="3x-ui-bot"
INSTALL_DIR="/opt/3x-ui-bot"

case "$1" in
    start)
        echo "Starting bot..."
        systemctl start $SERVICE_NAME
        ;;
    stop)
        echo "Stopping bot..."
        systemctl stop $SERVICE_NAME
        ;;
    restart)
        echo "Restarting bot..."
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
        echo "Usage: $0 {start|stop|restart|status|logs|config}"
        exit 1
        ;;
esac
