#!/bin/bash

echo "========================================="
echo "   Disabling 3x-ui Built-in Bot"
echo "========================================="

DB_PATHS=(
    "/etc/x-ui/x-ui.db"
    "/usr/local/x-ui/x-ui.db"
    "/opt/x-ui/x-ui.db"
)

CONFIG_PATHS=(
    "/etc/x-ui/x-ui.yml"
    "/usr/local/x-ui/x-ui.yml"
)

disable_bot_in_database() {
    local db_path=$1
    echo "Checking database: $db_path"

    if [ ! -f "$db_path" ]; then
        echo "  Database not found, skipping..."
        return
    fi

    cp "$db_path" "${db_path}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "  Backup created"

    sqlite3 "$db_path" "UPDATE settings SET value='false' WHERE key='bot_enable';" 2>/dev/null
    sqlite3 "$db_path" "UPDATE settings SET value='' WHERE key='bot_token';" 2>/dev/null

    echo "  Built-in bot disabled in database"
}

disable_bot_in_config() {
    local config_path=$1
    echo "Checking config: $config_path"

    if [ ! -f "$config_path" ]; then
        echo "  Config not found, skipping..."
        return
    fi

    cp "$config_path" "${config_path}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "  Backup created"

    if command -v sed &> /dev/null; then
        sed -i 's/bot_enable: true/bot_enable: false/g' "$config_path"
        sed -i 's/bot_token:.*/bot_token: ""/g' "$config_path"
        echo "  Built-in bot disabled in config"
    fi
}

for db_path in "${DB_PATHS[@]}"; do
    disable_bot_in_database "$db_path"
done

for config_path in "${CONFIG_PATHS[@]}"; do
    disable_bot_in_config "$config_path"
done

echo ""
echo "Restarting x-ui service..."
systemctl restart x-ui 2>/dev/null || true

echo ""
echo "========================================="
echo "   Built-in bot disabled!"
echo "========================================="
