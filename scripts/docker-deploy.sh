#!/bin/bash
# Sound Box - Docker deployment script
# Usage: ./scripts/docker-deploy.sh [build|push|deploy|start|stop|logs|status]
#
# Commands:
#   build              Build the Docker image locally
#   push               Push to GitHub Container Registry (ghcr.io)
#   deploy HOST        Deploy to a remote host via SSH (stops old instance, pulls, starts)
#   start              Start locally with docker compose
#   stop               Stop locally with docker compose
#   logs               Follow container logs
#   status             Show container status
#   fix-docker [HOST]  Fix common Docker daemon issues (BuildKit DB corruption, etc.)
#
# Examples:
#   ./scripts/docker-deploy.sh build
#   ./scripts/docker-deploy.sh push
#   ./scripts/docker-deploy.sh deploy gb10-02
#   ./scripts/docker-deploy.sh start

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Image name (override with SOUNDBOX_IMAGE env var)
IMAGE="${SOUNDBOX_IMAGE:-ghcr.io/valpatel/soundbox:latest}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Ensure Docker daemon is running, fix common issues if not
ensure_docker() {
    local host="${1:-}"
    local run="eval"
    if [ -n "$host" ]; then
        run="ssh $host"
    fi

    if $run "sudo docker info" &>/dev/null; then
        return 0
    fi

    warn "Docker daemon not running${host:+ on $host}, attempting to fix..."

    # Reset failed state (prevents "start request repeated too quickly")
    $run "sudo systemctl reset-failed docker" 2>/dev/null || true

    # Fix BuildKit database corruption (most common issue)
    $run "sudo rm -rf /var/lib/docker/buildkit" 2>/dev/null || true

    # Start Docker
    if $run "sudo systemctl start docker" 2>&1; then
        ok "Docker daemon started${host:+ on $host}"
    else
        error "Failed to start Docker${host:+ on $host}. Check: sudo journalctl -xeu docker.service"
        exit 1
    fi
}

# Ensure logged into GHCR
ensure_ghcr_login() {
    local host="${1:-}"
    local run="eval"
    if [ -n "$host" ]; then
        run="ssh $host"
    fi

    # Check if already logged in
    if $run "sudo docker pull $IMAGE" &>/dev/null 2>&1; then
        return 0
    fi

    info "Logging into GitHub Container Registry${host:+ on $host}..."
    if $run "gh auth token 2>/dev/null | sudo docker login ghcr.io --username mvalancy --password-stdin" 2>&1 | grep -q "Login Succeeded"; then
        ok "GHCR login successful"
    else
        error "GHCR login failed. Ensure 'gh auth login' is configured${host:+ on $host}."
        exit 1
    fi
}

case "${1:-help}" in
    build)
        info "Building Docker image: $IMAGE"
        ensure_docker
        sudo docker build -t "$IMAGE" "$PROJECT_DIR"
        ok "Image built: $IMAGE"
        echo ""
        sudo docker images "$IMAGE"
        ;;

    push)
        info "Pushing image to GHCR: $IMAGE"
        ensure_docker
        # Login to GHCR using gh CLI token
        gh auth token | sudo docker login ghcr.io --username mvalancy --password-stdin 2>&1
        sudo docker push "$IMAGE"
        ok "Image pushed: $IMAGE"
        ;;

    deploy)
        HOST="${2:?Usage: $0 deploy HOST (e.g., $0 deploy gb10-02)}"
        info "Deploying Sound Box to $HOST..."

        # Verify SSH access
        if ! ssh -o ConnectTimeout=5 "$HOST" "true" 2>/dev/null; then
            error "Cannot SSH to $HOST"
            exit 1
        fi

        # Ensure Docker is running on remote
        ensure_docker "$HOST"

        # Login to GHCR on remote (forward local token for correct scopes)
        info "Logging into GHCR on $HOST..."
        LOCAL_TOKEN=$(gh auth token 2>/dev/null)
        if [ -n "$LOCAL_TOKEN" ]; then
            ssh "$HOST" "echo '$LOCAL_TOKEN' | sudo docker login ghcr.io --username mvalancy --password-stdin" 2>&1
        else
            ssh "$HOST" "gh auth token 2>/dev/null | sudo docker login ghcr.io --username mvalancy --password-stdin" 2>&1
        fi

        # Stop existing Sound Box (systemd service or bare process)
        info "Stopping existing Sound Box on $HOST..."
        ssh "$HOST" "sudo systemctl stop soundbox 2>/dev/null || true"
        ssh "$HOST" "sudo systemctl stop soundbox-mcp 2>/dev/null || true"
        ssh "$HOST" "sudo docker compose -f ~/Code/app-soundbox/docker-compose.yml down 2>/dev/null || true"
        # Kill any remaining app.py processes
        ssh "$HOST" "pkill -f 'python.*app.py' 2>/dev/null || true"
        sleep 2

        # Pull latest image
        info "Pulling image on $HOST..."
        ssh "$HOST" "sudo docker pull $IMAGE"

        # Copy docker-compose.yml to remote
        info "Syncing docker-compose.yml to $HOST..."
        scp "$PROJECT_DIR/docker-compose.yml" "$HOST:~/Code/app-soundbox/docker-compose.yml"

        # Ensure .env exists on remote
        if ! ssh "$HOST" "test -f ~/Code/app-soundbox/.env"; then
            warn "No .env found on $HOST, creating from .env.example..."
            scp "$PROJECT_DIR/.env.example" "$HOST:~/Code/app-soundbox/.env"
        fi

        # Start with docker compose
        info "Starting Sound Box container on $HOST..."
        ssh "$HOST" "cd ~/Code/app-soundbox && sudo docker compose up -d"

        # Wait for health check
        info "Waiting for server to become ready..."
        for i in $(seq 1 30); do
            if ssh "$HOST" "curl -sf http://localhost:5309/status" &>/dev/null; then
                ok "Sound Box is running on $HOST:5309"
                echo ""
                ssh "$HOST" "curl -s http://localhost:5309/status" | python3 -m json.tool 2>/dev/null | head -20
                echo ""
                ok "Access at: http://$HOST:5309"
                exit 0
            fi
            sleep 5
            echo -n "."
        done
        echo ""
        warn "Server not responding yet. Check logs with: ssh $HOST 'sudo docker compose -f ~/Code/app-soundbox/docker-compose.yml logs -f'"
        ;;

    start)
        info "Starting Sound Box locally..."
        ensure_docker
        sudo docker compose up -d
        ok "Container started. Access at: http://localhost:5309"
        ;;

    stop)
        info "Stopping Sound Box..."
        sudo docker compose down
        ok "Container stopped"
        ;;

    logs)
        sudo docker compose logs -f
        ;;

    status)
        sudo docker compose ps
        echo ""
        curl -s http://localhost:5309/status 2>/dev/null | python3 -m json.tool | head -20 || warn "Server not responding"
        ;;

    fix-docker)
        HOST="${2:-}"
        ensure_docker "$HOST"
        ok "Docker daemon is healthy${HOST:+ on $HOST}"
        ;;

    help|*)
        echo "Sound Box - Docker Deployment"
        echo ""
        echo "Usage: $0 COMMAND [OPTIONS]"
        echo ""
        echo "Commands:"
        echo "  build              Build Docker image locally"
        echo "  push               Push image to GitHub Container Registry"
        echo "  deploy HOST        Deploy to remote host (stop old, pull, start)"
        echo "  start              Start locally with docker compose"
        echo "  stop               Stop local container"
        echo "  logs               Follow container logs"
        echo "  status             Show container status"
        echo "  fix-docker [HOST]  Fix Docker daemon issues"
        echo ""
        echo "Quick deploy:"
        echo "  $0 build && $0 push && $0 deploy gb10-02"
        echo ""
        echo "Image: $IMAGE (override with SOUNDBOX_IMAGE env var)"
        ;;
esac
