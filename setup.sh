#!/bin/bash
# Sound Box - Complete Setup Script
# Supports: x86_64 (desktop RTX), aarch64 (Jetson Orin AGX, DGX Grace GB10)
#
# All output is teed to setup.log. If anything fails, share that file.
# Set VERBOSE=1 to disable output truncation (everything streams).
set -e
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/setup.log"
: > "$LOG_FILE"  # truncate previous log

# Tee everything to setup.log. Redirect happens once, here.
exec > >(tee -a "$LOG_FILE") 2>&1

START_TIME=$(date +%s)

echo "=============================================="
echo "       SOUND BOX - Complete Setup"
echo "       $(date)"
echo "       Log: $LOG_FILE"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Per-step result tracking (printed in end-of-setup summary).
# Each entry: "label|status|detail"  status in {ok,warn,skip,fail}
declare -a STEP_RESULTS=()
CURRENT_STEP=""
CURRENT_STEP_START=0

ts() { date '+%H:%M:%S'; }

print_step() {
    CURRENT_STEP="$1"
    CURRENT_STEP_START=$(date +%s)
    echo ""
    echo -e "${GREEN}[$(ts)] [STEP]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[$(ts)] [WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[$(ts)] [ERROR]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[$(ts)] [INFO]${NC} $1"
}

# Record a step's outcome for the end summary.
# Usage: step_result <status> [detail]   status in {ok,warn,skip,fail}
step_result() {
    local status="$1"
    local detail="${2:-}"
    local label="${CURRENT_STEP:-(unknown)}"
    local elapsed=$(( $(date +%s) - CURRENT_STEP_START ))
    [ -n "$detail" ] && detail="$detail [${elapsed}s]" || detail="${elapsed}s"
    STEP_RESULTS+=("${label}|${status}|${detail}")
}

# Run an installer command with full output (visible in terminal, captured in log).
# Returns its true exit code. Use instead of `... | tail -N` patterns so failures
# are not silently hidden.
run_install() {
    "$@"
}

# Trap to print where we died if something exits non-zero.
on_error() {
    local exit_code=$?
    local line_no=$1
    print_error "Setup failed at line $line_no (exit $exit_code). Last step: ${CURRENT_STEP:-unknown}"
    print_error "Full log: $LOG_FILE"
    print_error "Share that file when reporting an issue."
    exit "$exit_code"
}
trap 'on_error $LINENO' ERR

# ==============================================================================
# Pre-flight checks (fail fast with clear messages)
# ==============================================================================
print_step "Pre-flight checks"

# --- OS and package manager -------------------------------------------------
OS_NAME=""
if [ -f /etc/os-release ]; then
    OS_NAME=$(. /etc/os-release && echo "${PRETTY_NAME:-$NAME}")
elif command -v lsb_release &> /dev/null; then
    OS_NAME=$(lsb_release -ds)
else
    OS_NAME="$(uname -s) $(uname -r)"
fi
print_info "OS: $OS_NAME"

PKG_MGR=""
if command -v apt-get &> /dev/null; then
    PKG_MGR="apt"
elif command -v dnf &> /dev/null; then
    PKG_MGR="dnf"
elif command -v pacman &> /dev/null; then
    PKG_MGR="pacman"
elif command -v brew &> /dev/null; then
    PKG_MGR="brew"
fi

if [ -z "$PKG_MGR" ]; then
    print_error "No supported package manager found (apt/dnf/pacman/brew)."
    print_error "Install system deps manually: python3-venv python3-dev ffmpeg libsndfile1"
    print_error "Then re-run with SKIP_SYSTEM_DEPS=1 ./setup.sh"
    exit 1
fi

if [ "$PKG_MGR" != "apt" ] && [ -z "${SKIP_SYSTEM_DEPS:-}" ]; then
    print_warn "Detected $PKG_MGR but this script only knows apt-get."
    print_warn "Install equivalents of: python3-venv python3-dev ffmpeg libsndfile1 pkg-config build-essential"
    print_warn "Then re-run with SKIP_SYSTEM_DEPS=1 ./setup.sh"
    print_warn "Continuing — system-deps step will be skipped."
fi
print_info "Package manager: $PKG_MGR"

# --- sudo availability ------------------------------------------------------
NEED_SUDO=""
if [ "$PKG_MGR" = "apt" ] && [ "${SKIP_SYSTEM_DEPS:-0}" != "1" ] && [ ! -f /.dockerenv ]; then
    if [ "$EUID" -ne 0 ]; then
        if ! command -v sudo &> /dev/null; then
            print_error "sudo not found and not running as root. Need root to install system deps."
            print_error "Install sudo, run as root, or re-run with SKIP_SYSTEM_DEPS=1 ./setup.sh"
            exit 1
        fi
        # Probe sudo so the prompt happens here, not buried later
        if ! sudo -n true 2>/dev/null; then
            print_info "sudo will prompt for your password to install system packages..."
            sudo -v || { print_error "sudo authentication failed"; exit 1; }
        fi
        NEED_SUDO="sudo"
    fi
fi

# --- Network connectivity ---------------------------------------------------
# Use curl since we need it for downloads anyway; fall back to wget.
HAS_NET=false
if command -v curl &> /dev/null && curl -s -m 5 -o /dev/null https://pypi.org/; then
    HAS_NET=true
elif command -v wget &> /dev/null && wget -q --timeout=5 --tries=1 -O - https://pypi.org/ > /dev/null; then
    HAS_NET=true
fi
if [ "$HAS_NET" = false ]; then
    print_warn "No connectivity to pypi.org detected (5s timeout)."
    print_warn "If behind a corporate proxy, set HTTPS_PROXY / HTTP_PROXY before re-running."
    print_warn "Continuing — pip installs will likely fail with network errors."
fi

# --- Disk space (need ~10 GB for venv + model weights) ----------------------
DISK_FREE_KB=$(df -P "$SCRIPT_DIR" | awk 'NR==2 {print $4}')
DISK_FREE_GB=$(( DISK_FREE_KB / 1024 / 1024 ))
print_info "Free disk: ${DISK_FREE_GB} GB at $SCRIPT_DIR"
if [ "$DISK_FREE_GB" -lt 10 ]; then
    print_warn "Less than 10 GB free. Models alone are ~5 GB. Setup may fail mid-download."
fi

step_result ok "$PKG_MGR / ${DISK_FREE_GB}GB free"
echo ""

# ==============================================================================
# Check Python version (3.10+ required)
# ==============================================================================
print_step "Checking Python version"
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Install python3 3.10+ and try again."
    step_result fail "python3 not on PATH"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MINOR" -lt 10 ]; then
    print_error "Python 3.10+ required, found Python $PYTHON_VERSION"
    step_result fail "$PYTHON_VERSION (need >=3.10)"
    exit 1
fi
if [ "$PYTHON_MINOR" -ge 13 ]; then
    print_warn "Python $PYTHON_VERSION is newer than tested (3.10–3.12). audiocraft/transformers may have compatibility issues."
fi
print_info "Python: $PYTHON_VERSION"
step_result ok "$PYTHON_VERSION"

# ==============================================================================
# Detect system architecture and GPU
# ==============================================================================
print_step "Detecting architecture and GPU"
ARCH=$(uname -m)
print_info "Architecture: $ARCH"

HAS_GPU=false
GPU_TYPE=""  # nvidia-desktop, nvidia-jetson, nvidia-dgx
CUDA_VERSION=""

detect_gpu() {
    if ! command -v nvidia-smi &> /dev/null; then
        print_warn "No NVIDIA GPU detected - will use CPU (much slower)"
        return
    fi

    HAS_GPU=true
    local gpu_name
    gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    local driver_version
    driver_version=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)

    echo -e "${GREEN}[OK]${NC} NVIDIA GPU: $gpu_name (Driver: $driver_version)"

    # Detect CUDA version
    if command -v nvcc &> /dev/null; then
        CUDA_VERSION=$(nvcc --version 2>/dev/null | grep "release" | sed 's/.*release \([0-9]*\.[0-9]*\).*/\1/')
        print_info "CUDA: $CUDA_VERSION"
    fi

    # Classify GPU type
    if echo "$gpu_name" | grep -qi "orin\|tegra"; then
        GPU_TYPE="nvidia-jetson"
        print_info "Platform: NVIDIA Jetson (Orin)"
    elif echo "$gpu_name" | grep -qi "GB10\|GB20\|GH200\|Grace"; then
        GPU_TYPE="nvidia-dgx"
        print_info "Platform: NVIDIA DGX/Grace"
    else
        GPU_TYPE="nvidia-desktop"
        print_info "Platform: NVIDIA Desktop GPU"
    fi
}

detect_gpu

# Allow forcing CUDA installation (e.g., Docker builds where nvidia-smi is unavailable)
if [ "${FORCE_CUDA}" = "1" ] && [ "$HAS_GPU" = false ]; then
    print_info "FORCE_CUDA=1: Installing CUDA-enabled PyTorch (GPU not detected at build time)"
    HAS_GPU=true
    GPU_TYPE="${GPU_TYPE:-nvidia-desktop}"
fi
step_result ok "$ARCH ${GPU_TYPE:-cpu}"

# ==============================================================================
# STEP 1: System Dependencies
# ==============================================================================
print_step "Installing system dependencies"

if [ "${SKIP_SYSTEM_DEPS:-0}" = "1" ] || [ "$PKG_MGR" != "apt" ]; then
    print_info "Skipping (SKIP_SYSTEM_DEPS=1 or non-apt package manager)"
    step_result skip "pkg manager: $PKG_MGR"
else
    # apt-get is verbose by default; we keep that verbosity (tee'd to log) so
    # users can see exactly which package broke if something fails. Failures
    # propagate via set -e + pipefail.
    print_info "Running: apt-get update"
    $NEED_SUDO apt-get update

    print_info "Running: apt-get install (core packages)"
    $NEED_SUDO apt-get install -y \
        python3 \
        python3-venv \
        python3-pip \
        python3-dev \
        ffmpeg \
        libsndfile1 \
        pkg-config \
        curl \
        wget \
        git \
        build-essential \
        avahi-daemon \
        avahi-utils

    # ffmpeg dev libs are genuinely optional (some bases don't carry separate -dev
    # variants). Failure here is non-fatal but logged as a warning.
    print_info "Running: apt-get install (ffmpeg dev libs, optional)"
    if ! $NEED_SUDO apt-get install -y \
            libavformat-dev \
            libavcodec-dev \
            libavutil-dev \
            libswresample-dev; then
        print_warn "ffmpeg dev libs not available on this distro (audiocraft may still work)"
    fi
    step_result ok "apt packages installed"
fi
echo ""

# ==============================================================================
# STEP 2: Python Virtual Environment
# ==============================================================================
print_step "Setting up Python virtual environment..."

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created new virtual environment"
else
    echo "Using existing virtual environment"
fi

source venv/bin/activate
print_info "pip: upgrading pip, setuptools, wheel"
pip install --upgrade pip setuptools wheel
step_result ok "venv ready, pip $(pip --version | awk '{print $2}')"

# ==============================================================================
# STEP 3: Install PyTorch (architecture-specific)
# ==============================================================================
print_step "Installing PyTorch"

# Candidate CUDA wheel indexes, newest first. Edit this list when PyTorch
# publishes a new CUDA variant; the script will pick it up automatically.
# CPU-only fallback last.
PYTORCH_CUDA_INDEXES=("cu128" "cu126" "cu124" "cu121")
PYTORCH_VARIANT=""

try_pytorch_index() {
    local variant="$1"
    local url="https://download.pytorch.org/whl/$variant"
    print_info "Trying PyTorch wheels: $variant ($url)"
    # Note: we do NOT silence stderr here. If a wheel install fails, the user
    # sees pip's actual error (network, ABI mismatch, etc.) in the log.
    if pip install torch torchaudio --index-url "$url"; then
        PYTORCH_VARIANT="$variant"
        return 0
    fi
    print_warn "  $variant: install failed (see log for pip's error)"
    return 1
}

install_pytorch() {
    if [ "$HAS_GPU" = true ]; then
        print_info "Selecting CUDA wheels for $ARCH / ${GPU_TYPE}"
        for variant in "${PYTORCH_CUDA_INDEXES[@]}"; do
            # cu121 is x86_64-only — skip on aarch64 (PyTorch never built those).
            if [ "$ARCH" = "aarch64" ] && [ "$variant" = "cu121" ]; then
                continue
            fi
            if try_pytorch_index "$variant"; then
                return 0
            fi
        done
        print_warn "All CUDA wheel indexes failed. Falling back to default PyPI."
        print_warn "This may install a CPU-only build even though you have a GPU."
        if pip install torch torchaudio; then
            PYTORCH_VARIANT="default-pypi"
            return 0
        fi
        return 1
    fi

    # CPU only
    print_info "Installing PyTorch CPU build"
    if [ "$ARCH" = "x86_64" ]; then
        pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
        PYTORCH_VARIANT="cpu"
    else
        pip install torch torchaudio
        PYTORCH_VARIANT="default-pypi"
    fi
}

install_pytorch

# Verify installation
print_info "Verifying PyTorch installation"
PYTORCH_VERIFY_OUTPUT=$(python3 -c "
import torch
print(f'PyTorch {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA version: {torch.version.cuda}')
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    props = torch.cuda.get_device_properties(0)
    print(f'GPU memory: {props.total_memory / 1e9:.1f} GB')
    print(f'Compute capability: sm_{props.major}{props.minor}')
    x = torch.randn(100, 100, device='cuda')
    _ = torch.matmul(x, x)
    print('CUDA matmul test: PASSED')
else:
    print('Running on CPU (generation will be slow)')
" 2>&1) || {
    print_warn "PyTorch verification failed:"
    echo "$PYTORCH_VERIFY_OUTPUT"
    step_result warn "$PYTORCH_VARIANT, verification failed"
    PYTORCH_VERIFY_OUTPUT=""
}
[ -n "$PYTORCH_VERIFY_OUTPUT" ] && echo "$PYTORCH_VERIFY_OUTPUT" | sed 's/^/  /'

PYTORCH_VER=$(python3 -c 'import torch; print(torch.__version__)' 2>/dev/null || echo "unknown")
step_result ok "torch $PYTORCH_VER via $PYTORCH_VARIANT"
echo ""

# ==============================================================================
# STEP 4: Python Dependencies
# ==============================================================================
print_step "Installing Python dependencies"

# Install a logical group with a single pip call; failures propagate via set -e.
# Full pip output goes to setup.log; on the terminal we summarize at end.
pip_group() {
    local label="$1"; shift
    print_info "Installing: $label"
    pip install "$@"
}

pip_group "core web framework"     flask flask-limiter python-dotenv requests
pip_group "MCP server"             "mcp[cli]" httpx
pip_group "audio analysis"         numpy librosa matplotlib soundfile scipy
pip_group "audiocraft deps (1/3)"  spacy einops sentencepiece hydra-core hydra-colorlog num2words
pip_group "audiocraft deps (2/3)"  transformers encodec torchmetrics protobuf
pip_group "audiocraft deps (3/3)"  av flashy julius lameenc

# Optional: demucs has heavy native deps and may not have wheels for some
# platforms. Failure is non-fatal — Sound Box runs without it.
print_info "Installing: demucs (optional)"
if ! pip install demucs; then
    print_warn "demucs install failed — continuing without it"
fi

# xformers: Provides faster attention for AudioCraft.
# Native install fails on ARM64 (no wheels) and sometimes on niche x86_64
# configs. When that happens we drop in a minimal stub so AudioCraft can still
# import; it then falls back to PyTorch native SDPA at runtime.
print_info "Installing: xformers (with stub fallback)"
if ! pip install xformers; then
    print_warn "xformers native install failed — installing compatibility stub"
    print_warn "xformers native install failed - creating compatibility stub"
    SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
    XFORMERS_DIR="$SITE_PACKAGES/xformers"
    mkdir -p "$XFORMERS_DIR/ops/fmha"
    cat > "$XFORMERS_DIR/__init__.py" << 'STUBEOF'
"""Minimal xformers stub for platforms without native xformers support."""
STUBEOF
    cat > "$XFORMERS_DIR/ops/__init__.py" << 'STUBEOF'
"""Stub xformers.ops - provides minimal implementations for audiocraft compatibility.

AudioCraft imports xformers.ops unconditionally at module level.
This stub provides torch-based fallbacks for the two operations actually used:
  - ops.unbind (audiocraft/modules/transformer.py)
  - ops.memory_efficient_attention (only used when backend='xformers')
"""
import torch

class _MemoryEfficientAttentionOp:
    pass
class _MemoryEfficientAttentionCutlassOp(_MemoryEfficientAttentionOp):
    pass

class LowerTriangularMask:
    pass

def unbind(x, dim=0):
    return torch.unbind(x, dim=dim)

def memory_efficient_attention(q, k, v, attn_bias=None, p=0.0, **kwargs):
    is_causal = isinstance(attn_bias, LowerTriangularMask)
    return torch.nn.functional.scaled_dot_product_attention(
        q, k, v,
        attn_mask=None if is_causal else attn_bias,
        dropout_p=p,
        is_causal=is_causal,
    )

def fmha(*args, **kwargs):
    raise NotImplementedError("xformers not available - using PyTorch native attention")
STUBEOF
    cat > "$XFORMERS_DIR/ops/fmha/__init__.py" << 'STUBEOF'
"""Stub for xformers.ops.fmha"""
class attn_bias:
    class LowerTriangularMask:
        pass
    class BlockDiagonalMask:
        pass
    class LowerTriangularMaskWithTensorBias:
        pass
class _MemoryEfficientAttentionOp:
    pass
class cutlass:
    class FwOp(_MemoryEfficientAttentionOp):
        pass
def memory_efficient_attention(*args, **kwargs):
    raise NotImplementedError("xformers not available")
STUBEOF
    print_info "xformers stub installed (AudioCraft will use PyTorch native attention)"
fi

# AudioCraft itself. --no-deps because we installed the deps individually
# above with versions known to coexist; letting pip resolve them again can
# drag in conflicting torch/transformers versions.
pip_group "audiocraft" --no-deps audiocraft

# NVRTC Fix: PyTorch cu128 bundles NVRTC 12.8 which doesn't support Blackwell sm_121.
# If the system has a newer CUDA toolkit (13.0+) with compatible NVRTC, replace
# PyTorch's bundled NVRTC with the system version so JIT compilation works on GB10/etc.
fix_nvrtc_for_blackwell() {
    local SITE_PACKAGES
    SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
    local NVRTC_DIR="$SITE_PACKAGES/nvidia/cuda_nvrtc/lib"
    local SYS_NVRTC_DIR=""

    # Only needed if we have a GPU with compute capability > what PyTorch supports
    # FORCE_NVRTC_FIX=1 bypasses GPU check (e.g., Docker builds where GPU isn't available)
    local needs_fix
    if [ "${FORCE_NVRTC_FIX}" = "1" ]; then
        needs_fix="yes"
    else
        needs_fix=$(python3 -c "
import torch
if not torch.cuda.is_available():
    print('no')
else:
    cap = torch.cuda.get_device_capability(0)
    arch_list = torch.cuda.get_arch_list()
    max_sm = max(int(a.replace('sm_','')) for a in arch_list if a.startswith('sm_'))
    device_sm = cap[0] * 10 + cap[1]
    print('yes' if device_sm > max_sm else 'no')
" 2>/dev/null) || needs_fix="no"
    fi

    if [ "$needs_fix" != "yes" ]; then
        return
    fi

    print_info "GPU architecture newer than PyTorch's bundled NVRTC - checking for system CUDA..."

    # Find system NVRTC (prefer /usr/local/cuda)
    for nvrtc_search in /usr/local/cuda/targets/*/lib /usr/local/cuda/lib64 /usr/lib/*-linux-gnu; do
        if ls "$nvrtc_search"/libnvrtc.so.1[3-9]* 2>/dev/null | head -1 > /dev/null; then
            SYS_NVRTC_DIR="$nvrtc_search"
            break
        fi
    done

    if [ -z "$SYS_NVRTC_DIR" ]; then
        print_warn "No system NVRTC >= 13.0 found. GPU JIT compilation may fail on this GPU."
        print_warn "Install CUDA toolkit 13.0+ to fix: sudo apt install cuda-toolkit-13-0"
        return
    fi

    if [ ! -d "$NVRTC_DIR" ]; then
        print_warn "PyTorch NVRTC directory not found at $NVRTC_DIR"
        return
    fi

    local SYS_NVRTC
    SYS_NVRTC=$(ls "$SYS_NVRTC_DIR"/libnvrtc.so.1[3-9]* 2>/dev/null | grep -v builtins | sort -V | tail -1)
    local SYS_BUILTINS
    SYS_BUILTINS=$(ls "$SYS_NVRTC_DIR"/libnvrtc-builtins.so.1[3-9]* 2>/dev/null | sort -V | tail -1)

    if [ -n "$SYS_NVRTC" ] && [ -n "$SYS_BUILTINS" ]; then
        print_info "Upgrading PyTorch NVRTC with system version for GPU compatibility..."
        # Find existing bundled files
        local BUNDLED_NVRTC
        BUNDLED_NVRTC=$(ls "$NVRTC_DIR"/libnvrtc.so.* 2>/dev/null | grep -v builtins | grep -v BACKUP | head -1)
        local BUNDLED_BUILTINS
        BUNDLED_BUILTINS=$(ls "$NVRTC_DIR"/libnvrtc-builtins.so.* 2>/dev/null | grep -v BACKUP | head -1)

        if [ -n "$BUNDLED_NVRTC" ] && [ ! -f "${BUNDLED_NVRTC}.BACKUP" ]; then
            cp "$BUNDLED_NVRTC" "${BUNDLED_NVRTC}.BACKUP"
        fi
        if [ -n "$BUNDLED_BUILTINS" ] && [ ! -f "${BUNDLED_BUILTINS}.BACKUP" ]; then
            cp "$BUNDLED_BUILTINS" "${BUNDLED_BUILTINS}.BACKUP"
        fi

        # Replace with system NVRTC (keep original filenames so PyTorch finds them)
        cp "$SYS_NVRTC" "$BUNDLED_NVRTC"
        cp "$SYS_BUILTINS" "$BUNDLED_BUILTINS"
        echo "  NVRTC upgraded: $(basename "$SYS_NVRTC") -> $(basename "$BUNDLED_NVRTC")"
    fi
}

if [ "$HAS_GPU" = true ]; then
    fix_nvrtc_for_blackwell
fi

# ONNX Runtime for Piper TTS. Try GPU build first on NVIDIA systems; fall
# back to CPU build. Final fallback: warn (TTS will be disabled, app still runs).
print_info "Installing: onnxruntime (for Piper TTS)"
ONNX_INSTALLED=false
if [ "$HAS_GPU" = true ]; then
    if pip install onnxruntime-gpu; then
        ONNX_INSTALLED=true
    else
        print_warn "onnxruntime-gpu unavailable, trying CPU build"
    fi
fi
if [ "$ONNX_INSTALLED" = false ]; then
    if pip install onnxruntime; then
        ONNX_INSTALLED=true
    else
        print_warn "onnxruntime not available — TTS will be disabled"
    fi
fi

# Piper TTS. No wheels for some ARM64 configs; non-fatal if missing.
print_info "Installing: piper-tts (optional)"
if ! pip install piper-tts; then
    print_warn "piper-tts unavailable for $ARCH — TTS disabled"
fi

# Backup scheduler. Optional — if missing, scheduled backups won't run.
print_info "Installing: apscheduler (optional)"
if ! pip install apscheduler; then
    print_warn "apscheduler unavailable — scheduled backups disabled"
fi

# Dev/test tooling (pytest used by tests/test_*.py and test-all.sh)
pip_group "dev tooling" pytest pytest-html

step_result ok "all required packages installed"
echo ""

# ==============================================================================
# STEP 5: Create Directory Structure
# ==============================================================================
print_step "Creating directory structure"

mkdir -p models/voices
mkdir -p generated
mkdir -p generated/voice_samples
mkdir -p spectrograms

print_info "Created: models/voices, generated, generated/voice_samples, spectrograms"
step_result ok
echo ""

# ==============================================================================
# STEP 6: Create .env if missing
# ==============================================================================
print_step "Checking configuration (.env)"

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_info "Created .env from .env.example (open access mode enabled by default)"
        step_result ok "created from .env.example"
    else
        print_warn ".env.example missing — skipping .env creation"
        step_result warn "no template"
    fi
else
    print_info ".env already exists (preserved)"
    step_result ok "already exists"
fi
echo ""

# ==============================================================================
# STEP 7: Download Piper TTS Voices
# ==============================================================================
print_step "Downloading Piper TTS voices"

if command -v piper &> /dev/null || python3 -c "import piper" 2>/dev/null; then
    if [ -f "scripts/download-voices.sh" ]; then
        bash scripts/download-voices.sh
        step_result ok "via scripts/download-voices.sh"
    else
        echo "Running inline voice download..."

        VOICES_DIR="models/voices"
        PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

        # Essential English voices
        # URL path: {base}/en/{locale}/{name}/{quality}/{locale}-{name}-{quality}.onnx
        declare -A VOICE_URLS
        VOICE_URLS=(
            ["en_US-lessac-medium"]="en/en_US/lessac/medium"
            ["en_US-amy-medium"]="en/en_US/amy/medium"
            ["en_US-ryan-medium"]="en/en_US/ryan/medium"
            ["en_US-joe-medium"]="en/en_US/joe/medium"
            ["en_GB-alan-medium"]="en/en_GB/alan/medium"
            ["en_GB-alba-medium"]="en/en_GB/alba/medium"
        )

        voices_ok=0
        voices_failed=0
        for voice_name in "${!VOICE_URLS[@]}"; do
            voice_path="${VOICE_URLS[$voice_name]}"
            onnx_file="$VOICES_DIR/${voice_name}.onnx"
            json_file="$VOICES_DIR/${voice_name}.onnx.json"

            if [ ! -s "$onnx_file" ]; then
                print_info "Downloading $voice_name"
                rm -f "$onnx_file" "$json_file"
                # Voice downloads are non-fatal: a missing voice degrades TTS
                # but doesn't break Sound Box. We track failures for the summary.
                if wget -q --show-progress -O "$onnx_file" "$PIPER_BASE/$voice_path/$voice_name.onnx" \
                   && wget -q -O "$json_file" "$PIPER_BASE/$voice_path/$voice_name.onnx.json"; then
                    voices_ok=$((voices_ok + 1))
                else
                    print_warn "  failed to download $voice_name"
                    rm -f "$onnx_file" "$json_file"
                    voices_failed=$((voices_failed + 1))
                fi
            else
                print_info "Already have: $voice_name"
                voices_ok=$((voices_ok + 1))
            fi
        done
        if [ "$voices_failed" -eq 0 ]; then
            step_result ok "$voices_ok voices"
        else
            step_result warn "$voices_ok ok, $voices_failed failed"
        fi
    fi
else
    print_warn "Piper TTS not installed - skipping voice download"
    step_result skip "piper-tts not installed"
fi
echo ""

# ==============================================================================
# STEP 8: Pre-download AudioCraft Models
# ==============================================================================
print_step "Pre-downloading AudioCraft models"

# Non-interactive: auto-download if running with --auto flag, otherwise ask
if [ "${1}" = "--auto" ] || [ "${NONINTERACTIVE}" = "1" ]; then
    DOWNLOAD_MODELS="y"
else
    read -p "Download AudioCraft models now? (~5GB, speeds up first run) [y/N] " -n 1 -r
    echo
    DOWNLOAD_MODELS="$REPLY"
fi

if [[ $DOWNLOAD_MODELS =~ ^[Yy]$ ]]; then
    # The python heredoc tracks per-model success; we pass that out via exit code.
    if python3 << 'PYEOF'
import sys
ok = True
try:
    print("Downloading MusicGen model...")
    from audiocraft.models import MusicGen
    MusicGen.get_pretrained('facebook/musicgen-medium')
    print("  MusicGen downloaded")
except Exception as e:
    print(f"  MusicGen download failed: {e}")
    ok = False

try:
    print("Downloading AudioGen model...")
    from audiocraft.models import AudioGen
    AudioGen.get_pretrained('facebook/audiogen-medium')
    print("  AudioGen downloaded")
except Exception as e:
    print(f"  AudioGen download failed: {e}")
    ok = False

sys.exit(0 if ok else 1)
PYEOF
    then
        step_result ok "MusicGen + AudioGen cached"
    else
        print_warn "One or more model downloads failed — they'll retry on first use"
        step_result warn "partial / will lazy-load"
    fi
else
    print_info "Skipping model download — they will download on first use"
    step_result skip "deferred to first use"
fi
echo ""

# ==============================================================================
# STEP 9: Initialize Database
# ==============================================================================
print_step "Initializing database"

if python3 -c "import database; database.init_db()"; then
    print_info "Database initialized"
    step_result ok "soundbox.db ready"
else
    print_error "Database initialization failed"
    step_result fail "see traceback above"
    exit 1
fi
echo ""

# ==============================================================================
# STEP 10: Install systemd service (optional)
# ==============================================================================
# STEP 10: Install systemd service (optional)
# ==============================================================================
print_step "Systemd service setup"

if [ -f "/.dockerenv" ] || [ "${SKIP_SERVICES}" = "1" ]; then
    print_info "Skipping systemd service (Docker or SKIP_SERVICES=1)"
    step_result skip "Docker/SKIP_SERVICES"
elif ! command -v systemctl &> /dev/null; then
    print_info "systemctl not found — skipping (non-systemd init)"
    step_result skip "no systemd"
else
    if [ "${1}" = "--auto" ] || [ "${NONINTERACTIVE}" = "1" ]; then
        INSTALL_SERVICE="y"
    else
        read -p "Install systemd service (auto-start on boot)? [Y/n] " -n 1 -r
        echo
        INSTALL_SERVICE="${REPLY:-Y}"
    fi

    if [[ $INSTALL_SERVICE =~ ^[Yy]$ ]]; then
        if bash "$SCRIPT_DIR/scripts/service.sh" install; then
            step_result ok "soundbox + MCP + mDNS"
        else
            print_warn "service.sh install reported errors — service may not start on boot"
            step_result warn "see service.sh output"
        fi
    else
        print_info "User declined — run './scripts/service.sh install' later if needed"
        step_result skip "user declined"
    fi
fi
echo ""

# ==============================================================================
# STEP 11: Install Node.js and Playwright tests (optional)
# ==============================================================================
print_step "Test environment (Node.js + Playwright)"

if [ -f "/.dockerenv" ] || [ "${SKIP_TESTS}" = "1" ]; then
    print_info "Skipping (Docker or SKIP_TESTS=1)"
    step_result skip "Docker/SKIP_TESTS"
elif [ "$PKG_MGR" != "apt" ] && ! command -v node &> /dev/null; then
    print_warn "Node.js not installed and only apt-based install is automated — skipping."
    print_warn "Install Node.js 20+ manually, then run: npm install && npx playwright install chromium"
    step_result skip "manual install needed for $PKG_MGR"
else
    # Install Node.js if not present (apt only)
    if ! command -v node &> /dev/null; then
        print_info "Installing Node.js 20 LTS from NodeSource"
        # NodeSource setup script is verbose — full output goes to setup.log via tee.
        # sudo -E preserves PATH/HTTPS_PROXY; when already root we run bash directly.
        if [ -n "$NEED_SUDO" ]; then
            curl -fsSL https://deb.nodesource.com/setup_20.x | $NEED_SUDO -E bash -
        else
            curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        fi
        $NEED_SUDO apt-get install -y nodejs
    fi

    if command -v npm &> /dev/null; then
        print_info "Node.js $(node --version), npm $(npm --version)"

        print_info "Running: npm install"
        npm install

        # Playwright browser binaries (live in ~/.cache/ms-playwright, NOT node_modules,
        # so npm install alone does not provision them). The npx commands are
        # verbose by design (progress bars + size info); we let them stream.
        print_info "Running: npx playwright install chromium"
        if ! npx playwright install chromium; then
            print_warn "Playwright browser install failed — E2E tests will fail until resolved"
        fi

        print_info "Running: npx playwright install-deps chromium"
        if ! npx playwright install-deps chromium; then
            print_warn "Playwright system deps install failed — may need: sudo npx playwright install-deps chromium"
        fi

        # Verify chromium headless shell actually landed
        if find "$HOME/.cache/ms-playwright" -name "headless_shell" -type f 2>/dev/null | grep -q .; then
            print_info "Tests ready: npm test (or ./test-all.sh)"
            step_result ok "node $(node --version), Playwright Chromium present"
        else
            print_warn "Playwright Chromium not found at $HOME/.cache/ms-playwright/"
            print_warn "Re-run manually: npx playwright install chromium"
            step_result warn "Chromium missing"
        fi
    else
        print_warn "npm not available — skipping Playwright test setup"
        step_result warn "npm missing"
    fi
fi
echo ""

# ==============================================================================
# STEP 12: Final validation — import each critical module
# ==============================================================================
print_step "Validating installation"

# We test imports here (not earlier) because failures often surface only after
# everything is installed — a missing transitive dep can cause torch to import
# fine but audiocraft to blow up.
VALIDATION_FAILURES=()
validate_import() {
    local label="$1"
    local code="$2"
    if python3 -c "$code" > /dev/null 2>&1; then
        print_info "  ${GREEN}OK${NC}    $label"
    else
        local err
        err=$(python3 -c "$code" 2>&1 | tail -3 || true)
        print_warn "  FAIL  $label"
        echo "$err" | sed 's/^/        /'
        VALIDATION_FAILURES+=("$label")
    fi
}

validate_import "torch"                "import torch"
validate_import "torchaudio"           "import torchaudio"
validate_import "audiocraft.models"    "from audiocraft.models import MusicGen, AudioGen"
validate_import "flask"                "import flask"
validate_import "mcp"                  "import mcp"
validate_import "database.py"          "import sys; sys.path.insert(0, '.'); import database"
validate_import "app.py"               "import sys; sys.path.insert(0, '.'); import app"

if [ "${#VALIDATION_FAILURES[@]}" -eq 0 ]; then
    step_result ok "all imports succeeded"
else
    step_result warn "${#VALIDATION_FAILURES[@]} import(s) failed: ${VALIDATION_FAILURES[*]}"
fi
echo ""

# ==============================================================================
# Summary
# ==============================================================================
TOTAL_ELAPSED=$(( $(date +%s) - START_TIME ))
H=$(( TOTAL_ELAPSED / 3600 )); M=$(( (TOTAL_ELAPSED % 3600) / 60 )); S=$(( TOTAL_ELAPSED % 60 ))

echo "=============================================="
echo -e "${GREEN}       SETUP SUMMARY${NC}"
echo "=============================================="
echo "Total time: ${H}h ${M}m ${S}s"
echo "System: $ARCH | GPU: ${GPU_TYPE:-cpu} | CUDA: ${CUDA_VERSION:-none}"
echo "Log:    $LOG_FILE"
echo ""

# Per-step rollup
fail_count=0
warn_count=0
for entry in "${STEP_RESULTS[@]}"; do
    IFS='|' read -r label status detail <<<"$entry"
    case "$status" in
        ok)   marker="${GREEN}✓${NC}" ;;
        warn) marker="${YELLOW}⚠${NC}"; warn_count=$((warn_count + 1)) ;;
        skip) marker="${CYAN}-${NC}" ;;
        fail) marker="${RED}✗${NC}"; fail_count=$((fail_count + 1)) ;;
        *)    marker="?" ;;
    esac
    printf "  %b  %-45s %s\n" "$marker" "$label" "$detail"
done
echo ""

if [ "$fail_count" -gt 0 ]; then
    echo -e "${RED}Setup completed with $fail_count failure(s) and $warn_count warning(s).${NC}"
    echo "Review $LOG_FILE for full output."
elif [ "$warn_count" -gt 0 ]; then
    echo -e "${YELLOW}Setup completed with $warn_count warning(s) — optional features may be limited.${NC}"
else
    echo -e "${GREEN}Setup completed successfully.${NC}"
fi
echo ""

echo "Next steps:"
echo "  ./start.sh                     # Start the server (http://localhost:5309)"
echo "  ./scripts/service.sh status    # Service status (if installed)"
echo "  ./test-all.sh                  # Run unit + E2E tests"
echo ""
echo "Configuration: edit .env"
echo "  OPEN_ACCESS_MODE=true   (no login required, default)"
echo "  IP_WHITELIST=           (elevated rate limits for these IPs)"
echo "=============================================="
