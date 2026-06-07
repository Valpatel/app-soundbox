#!/usr/bin/env bash
# test-setup-docker.sh — smoke-test setup.sh inside a fresh Ubuntu container.
#
# WHAT IT DOES
#   - Pulls ubuntu:24.04 (Python 3.12 baseline)
#   - Copies the repo to a scratch dir so the container's setup.log + venv/ never
#     touch the host repo
#   - Installs the minimum host packages setup.sh assumes are already present
#     (sudo curl wget git python3 python3-venv python3-dev), then runs
#     `bash setup.sh` with SKIP_SERVICES=1 SKIP_TESTS=1 and stdin redirected
#     from /dev/null so the model-download read prompt receives EOF and skips
#     (we deliberately do NOT pass --auto / NONINTERACTIVE=1, since those would
#     force the ~5 GB AudioCraft download that takes forever on CPU)
#   - Captures the exit code and the container-side setup.log
#   - As the final assertion, runs `./venv/bin/python -c "import app, database, mcp_server"`
#     inside the same container
#
# WHY
#   setup.sh was hardened to handle a wide range of fresh installs (x86_64 desktop,
#   Jetson, GB10/Blackwell, CPU-only). This script gives us a way to prove it still
#   works on a vanilla Ubuntu 24.04 base without touching the host. CI can run it
#   on every PR that touches setup.sh.
#
# USAGE
#   ./scripts/test-setup-docker.sh                # default: ubuntu:24.04, CPU-only
#   BASE_IMAGE=ubuntu:22.04 ./scripts/test-setup-docker.sh
#   KEEP_SCRATCH=1 ./scripts/test-setup-docker.sh # don't rm the scratch copy on exit

set -euo pipefail

BASE_IMAGE="${BASE_IMAGE:-ubuntu:24.04}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH_PARENT="${TMPDIR:-/tmp}/soundbox-setup-smoke-$$"
KEEP_SCRATCH="${KEEP_SCRATCH:-0}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[smoke]${NC} $*"; }
ok()   { echo -e "${GREEN}[smoke PASS]${NC} $*"; }
warn() { echo -e "${YELLOW}[smoke WARN]${NC} $*"; }
fail() { echo -e "${RED}[smoke FAIL]${NC} $*" >&2; }

cleanup() {
    if [ "$KEEP_SCRATCH" = "1" ]; then
        log "KEEP_SCRATCH=1 — leaving $SCRATCH_PARENT in place"
    elif [ -d "$SCRATCH_PARENT" ]; then
        # The container ran as root, so venv/ etc. is root-owned. We use docker
        # to chown back so a normal `rm -rf` works without sudo on the host.
        log "Cleaning scratch dir $SCRATCH_PARENT"
        docker run --rm -v "$SCRATCH_PARENT:/scratch" "$BASE_IMAGE" \
            chown -R "$(id -u):$(id -g)" /scratch 2>/dev/null || true
        rm -rf "$SCRATCH_PARENT"
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 1. Sanity checks
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    fail "docker not on PATH"
    exit 1
fi
if ! [ -f "$REPO_ROOT/setup.sh" ]; then
    fail "setup.sh not found at $REPO_ROOT/setup.sh"
    exit 1
fi

log "Base image:    $BASE_IMAGE"
log "Repo root:     $REPO_ROOT"
log "Scratch dir:   $SCRATCH_PARENT"

# ---------------------------------------------------------------------------
# 2. Pull base image (no-op if already cached)
# ---------------------------------------------------------------------------
log "Pulling $BASE_IMAGE (no-op if cached)"
docker pull "$BASE_IMAGE" >/dev/null

# ---------------------------------------------------------------------------
# 3. Copy the repo to a scratch dir so the container's writes (venv/, setup.log,
#    soundbox.db, etc.) never land in the host repo
# ---------------------------------------------------------------------------
mkdir -p "$SCRATCH_PARENT"
SCRATCH_REPO="$SCRATCH_PARENT/repo"
log "Copying repo to $SCRATCH_REPO (excluding venv/, node_modules/, .git/)"
# rsync would be cleaner but isn't guaranteed; use cp with explicit excludes via tar.
# We must keep .gitignore etc., but venv/node_modules/__pycache__ would bloat the copy.
mkdir -p "$SCRATCH_REPO"
# Disable -e/pipefail for the copy: tar exits 1 on "file changed as we read it"
# (e.g. .codegraph.db, setup.log being touched by the host), which is harmless —
# we already excluded the heavy/volatile paths.
set +e
( cd "$REPO_ROOT" && tar --warning=no-file-changed \
                         --exclude='./venv' \
                         --exclude='./node_modules' \
                         --exclude='./.git' \
                         --exclude='./static/output' \
                         --exclude='./__pycache__' \
                         --exclude='*.pyc' \
                         --exclude='./setup.log' \
                         --exclude='./.codegraph.db' \
                         --exclude='./*.db' \
                         --exclude='./models' \
                         --exclude='./hf-cache' \
                         -cf - . ) | ( cd "$SCRATCH_REPO" && tar -xf - )
set -e

# ---------------------------------------------------------------------------
# 4. Run setup.sh inside the container.
#    - SKIP_SERVICES=1 + SKIP_TESTS=1 short-circuit those steps explicitly
#      (setup.sh also auto-detects /.dockerenv but the env vars make intent clear)
#    - We do NOT pass --auto / NONINTERACTIVE=1: that would force the AudioCraft
#      model download (~5 GB, CPU-only) which would blow the 15 min budget. With
#      neither set, setup.sh hits its interactive `read -n 1` prompt, stdin is
#      /dev/null so it returns EOF, $REPLY is empty, the [Yy] regex fails, and
#      models are deferred to first use (which is what we want for a smoke test).
#    - FORCE_CUDA=0 keeps the CPU wheel path on a non-GPU container
# ---------------------------------------------------------------------------
START_TS=$(date +%s)
log "Running setup.sh in container (this typically takes 8–12 min on CPU)"

# Use --network host so corp proxies / DNS work the same as the host. Run as
# root (container default) so setup.sh's apt-get install works without sudo.
EXIT_CODE=0
docker run --rm \
    --network host \
    -v "$SCRATCH_REPO:/work" \
    -w /work \
    -e DEBIAN_FRONTEND=noninteractive \
    -e SKIP_SERVICES=1 \
    -e SKIP_TESTS=1 \
    -e FORCE_CUDA=0 \
    "$BASE_IMAGE" \
    bash -c '
        set -e
        echo "[container] OS: $(. /etc/os-release && echo "$PRETTY_NAME")"
        echo "[container] Installing host prerequisites that setup.sh assumes exist"
        apt-get update -qq
        apt-get install -y -qq --no-install-recommends \
            sudo ca-certificates curl wget git \
            python3 python3-venv python3-dev python3-pip \
            >/dev/null
        echo "[container] Python: $(python3 --version)"
        echo "[container] ----- running setup.sh -----"
        # Feed "n" to the AudioCraft model-download `read -n 1 -r` prompt. Using
        # /dev/null instead would make `read` return non-zero on EOF, which trips
        # setup.sh'\''s `set -e` and aborts. SKIP_SERVICES=1 already short-circuits
        # the only other read prompt so this single "n" is sufficient.
        echo n | bash setup.sh
        SETUP_EXIT=$?
        echo "[container] ----- setup.sh exit=$SETUP_EXIT -----"
        echo "[container] ----- import smoke -----"
        ./venv/bin/python -c "import app, database, mcp_server; print(\"[container] imports OK\")"
        echo "[container] ----- DONE -----"
    ' || EXIT_CODE=$?

END_TS=$(date +%s)
ELAPSED=$(( END_TS - START_TS ))
ELAPSED_MIN=$(( ELAPSED / 60 ))
ELAPSED_SEC=$(( ELAPSED % 60 ))

# ---------------------------------------------------------------------------
# 5. Surface the container-side setup.log on failure (and always tail the tail)
# ---------------------------------------------------------------------------
CONTAINER_LOG="$SCRATCH_REPO/setup.log"
if [ -f "$CONTAINER_LOG" ]; then
    log "Container setup.log: $CONTAINER_LOG ($(wc -l <"$CONTAINER_LOG") lines)"
fi

if [ "$EXIT_CODE" -ne 0 ]; then
    fail "Container exited with $EXIT_CODE after ${ELAPSED_MIN}m${ELAPSED_SEC}s"
    if [ -f "$CONTAINER_LOG" ]; then
        echo "----- last 80 lines of container setup.log -----"
        tail -n 80 "$CONTAINER_LOG"
        echo "------------------------------------------------"
    fi
    exit "$EXIT_CODE"
fi

ok "setup.sh + import smoke passed in ${ELAPSED_MIN}m${ELAPSED_SEC}s on $BASE_IMAGE"
exit 0
