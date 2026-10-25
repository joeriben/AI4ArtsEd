#!/bin/bash
#
# Update Cloudflared Configuration
# Usage: ./update_cloudflared_config.sh [config_file]
#
# Reads sudo password from stdin and updates cloudflared config
# Example: echo 'YOUR_PASSWORD' | ./update_cloudflared_config.sh /path/to/new_config.yml
#

set -e

CONFIG_FILE="${1:-/tmp/cloudflared_new.yml}"
TARGET_PATH="/etc/cloudflared/config.yml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

echo "Updating cloudflared configuration..."
echo "Source: $CONFIG_FILE"
echo "Target: $TARGET_PATH"

# Read password from stdin and execute commands
sudo -S sh -c "
    cp '$TARGET_PATH' '${TARGET_PATH}.backup.$(date +%Y%m%d_%H%M%S)' && \
    cp '$CONFIG_FILE' '$TARGET_PATH' && \
    systemctl restart cloudflared && \
    echo 'Cloudflared configuration updated and service restarted.'
"

# Check status
sleep 2
sudo -S systemctl status cloudflared --no-pager | head -15
