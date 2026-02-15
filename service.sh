#!/bin/bash
# Sound Box - systemd service management
# Usage: ./service.sh [install|uninstall|enable|disable|start|stop|restart|status|logs]

set -e

SERVICE_NAME="soundbox"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CURRENT_USER=$(whoami)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

case "${1}" in
    install)
        echo "Installing Sound Box systemd service..."

        # Generate service file
        cat << EOF | sudo tee "$SERVICE_FILE" > /dev/null
[Unit]
Description=Sound Box - AI Audio Generation Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/venv/bin/python ${SCRIPT_DIR}/app.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
EnvironmentFile=-${SCRIPT_DIR}/.env

# Resource limits
Nice=10
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME"

        echo -e "${GREEN}Service installed and started!${NC}"
        echo ""
        echo "Management commands:"
        echo "  ./service.sh status    - Check status"
        echo "  ./service.sh stop      - Stop server"
        echo "  ./service.sh restart   - Restart server"
        echo "  ./service.sh logs      - View logs"
        echo "  ./service.sh disable   - Disable auto-start"
        echo "  ./service.sh uninstall - Remove service"
        ;;

    uninstall)
        echo "Uninstalling Sound Box service..."
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        sudo rm -f "$SERVICE_FILE"
        sudo systemctl daemon-reload
        echo -e "${GREEN}Service uninstalled.${NC}"
        ;;

    enable)
        sudo systemctl enable "$SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME"
        echo -e "${GREEN}Service enabled and started.${NC}"
        ;;

    disable)
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        sudo systemctl disable "$SERVICE_NAME"
        echo -e "${YELLOW}Service disabled (won't start on boot).${NC}"
        ;;

    start)
        sudo systemctl start "$SERVICE_NAME"
        echo -e "${GREEN}Service started.${NC}"
        ;;

    stop)
        sudo systemctl stop "$SERVICE_NAME"
        echo -e "${YELLOW}Service stopped.${NC}"
        ;;

    restart)
        sudo systemctl restart "$SERVICE_NAME"
        echo -e "${GREEN}Service restarted.${NC}"
        ;;

    status)
        systemctl status "$SERVICE_NAME" --no-pager || true
        ;;

    logs)
        journalctl -u "$SERVICE_NAME" -f --no-pager -n 50
        ;;

    *)
        echo "Sound Box Service Manager"
        echo ""
        echo "Usage: ./service.sh <command>"
        echo ""
        echo "Commands:"
        echo "  install    - Install and enable systemd service (starts on boot)"
        echo "  uninstall  - Stop and remove the service completely"
        echo "  enable     - Enable auto-start on boot and start now"
        echo "  disable    - Disable auto-start and stop"
        echo "  start      - Start the service"
        echo "  stop       - Stop the service"
        echo "  restart    - Restart the service"
        echo "  status     - Show service status"
        echo "  logs       - Follow service logs (Ctrl+C to stop)"
        ;;
esac
