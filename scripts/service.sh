#!/bin/bash
# Sound Box - systemd service management
# Usage: ./scripts/service.sh [install|uninstall|enable|disable|start|stop|restart|status|logs]

set -e

SERVICE_NAME="soundbox"
MCP_SERVICE_NAME="soundbox-mcp"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
MCP_SERVICE_FILE="/etc/systemd/system/${MCP_SERVICE_NAME}.service"
AVAHI_SERVICE_FILE="/etc/avahi/services/soundbox.service"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CURRENT_USER=$(whoami)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

case "${1}" in
    install)
        echo "Installing Sound Box systemd services..."

        # Main Sound Box service
        cat << EOF | sudo tee "$SERVICE_FILE" > /dev/null
[Unit]
Description=Sound Box - AI Audio Generation Server
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/app.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
EnvironmentFile=-${PROJECT_DIR}/.env

# Resource limits
Nice=10
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

        # MCP Server service (SSE transport for network agents)
        cat << EOF | sudo tee "$MCP_SERVICE_FILE" > /dev/null
[Unit]
Description=Sound Box - MCP Server (AI Agent Tools)
After=network.target ${SERVICE_NAME}.service
Wants=${SERVICE_NAME}.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/mcp_server.py --transport sse
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
EnvironmentFile=-${PROJECT_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF

        # Install Avahi mDNS service for LAN discovery
        if [ -d /etc/avahi/services ]; then
            sudo cp "${PROJECT_DIR}/avahi/soundbox.service" "$AVAHI_SERVICE_FILE"
            echo -e "${GREEN}Avahi mDNS service installed${NC}"
        else
            echo -e "${YELLOW}Avahi not found - skipping mDNS discovery${NC}"
        fi

        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME" "$MCP_SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME" "$MCP_SERVICE_NAME"

        echo -e "${GREEN}Services installed and started!${NC}"
        echo ""
        echo "  Sound Box:  http://localhost:5309"
        echo "  MCP Server: http://localhost:${MCP_PORT:-5310} (SSE)"
        echo ""
        echo "Management commands:"
        echo "  ./scripts/service.sh status    - Check status"
        echo "  ./scripts/service.sh stop      - Stop server"
        echo "  ./scripts/service.sh restart   - Restart server"
        echo "  ./scripts/service.sh logs      - View logs"
        echo "  ./scripts/service.sh disable   - Disable auto-start"
        echo "  ./scripts/service.sh uninstall - Remove service"
        ;;

    uninstall)
        echo "Uninstalling Sound Box services..."
        sudo systemctl stop "$MCP_SERVICE_NAME" 2>/dev/null || true
        sudo systemctl disable "$MCP_SERVICE_NAME" 2>/dev/null || true
        sudo rm -f "$MCP_SERVICE_FILE"
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
        sudo rm -f "$SERVICE_FILE"
        sudo rm -f "$AVAHI_SERVICE_FILE"
        sudo systemctl daemon-reload
        echo -e "${GREEN}All Sound Box services uninstalled.${NC}"
        ;;

    enable)
        sudo systemctl enable "$SERVICE_NAME" "$MCP_SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME" "$MCP_SERVICE_NAME"
        echo -e "${GREEN}Services enabled and started.${NC}"
        ;;

    disable)
        sudo systemctl stop "$MCP_SERVICE_NAME" 2>/dev/null || true
        sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        sudo systemctl disable "$SERVICE_NAME" "$MCP_SERVICE_NAME"
        echo -e "${YELLOW}Services disabled (won't start on boot).${NC}"
        ;;

    start)
        sudo systemctl start "$SERVICE_NAME" "$MCP_SERVICE_NAME"
        echo -e "${GREEN}Services started.${NC}"
        ;;

    stop)
        sudo systemctl stop "$MCP_SERVICE_NAME" 2>/dev/null || true
        sudo systemctl stop "$SERVICE_NAME"
        echo -e "${YELLOW}Services stopped.${NC}"
        ;;

    restart)
        sudo systemctl restart "$SERVICE_NAME" "$MCP_SERVICE_NAME"
        echo -e "${GREEN}Services restarted.${NC}"
        ;;

    status)
        echo "=== Sound Box ==="
        systemctl status "$SERVICE_NAME" --no-pager || true
        echo ""
        echo "=== MCP Server ==="
        systemctl status "$MCP_SERVICE_NAME" --no-pager || true
        ;;

    logs)
        journalctl -u "$SERVICE_NAME" -u "$MCP_SERVICE_NAME" -f --no-pager -n 50
        ;;

    *)
        echo "Sound Box Service Manager"
        echo ""
        echo "Usage: ./scripts/service.sh <command>"
        echo ""
        echo "Commands:"
        echo "  install    - Install and enable all services (main + MCP + mDNS)"
        echo "  uninstall  - Stop and remove all services completely"
        echo "  enable     - Enable auto-start on boot and start now"
        echo "  disable    - Disable auto-start and stop"
        echo "  start      - Start all services"
        echo "  stop       - Stop all services"
        echo "  restart    - Restart all services"
        echo "  status     - Show service status"
        echo "  logs       - Follow service logs (Ctrl+C to stop)"
        ;;
esac
