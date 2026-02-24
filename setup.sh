#!/bin/bash
# Sound Box - Complete Setup Script
# Supports: x86_64 (desktop RTX), aarch64 (Jetson Orin AGX, DGX Grace GB10)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================="
echo "       SOUND BOX - Complete Setup"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${GREEN}[STEP]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

# ==============================================================================
# Check Python version (3.10+ required)
# ==============================================================================
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Install python3 3.10+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PYTHON_MINOR" -lt 10 ]; then
    print_error "Python 3.10+ required, found Python $PYTHON_VERSION"
    exit 1
fi
print_info "Python: $PYTHON_VERSION"

# ==============================================================================
# Detect system architecture and GPU
# ==============================================================================
ARCH=$(uname -m)
print_info "Architecture: $ARCH"
print_info "OS: $(lsb_release -ds 2>/dev/null || cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '"')"

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

echo ""

# ==============================================================================
# STEP 1: System Dependencies
# ==============================================================================
print_step "Installing system dependencies..."

sudo apt-get update -qq
sudo apt-get install -y -qq \
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
    avahi-utils 2>&1 | tail -1

# Install ffmpeg dev libs if available (some systems have them separately)
sudo apt-get install -y -qq \
    libavformat-dev \
    libavcodec-dev \
    libavutil-dev \
    libswresample-dev 2>/dev/null || true

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
pip install --upgrade pip setuptools wheel 2>&1 | tail -1

echo ""

# ==============================================================================
# STEP 3: Install PyTorch (architecture-specific)
# ==============================================================================
print_step "Installing PyTorch..."

install_pytorch() {
    if [ "$HAS_GPU" = true ]; then
        if [ "$ARCH" = "x86_64" ]; then
            # Desktop x86_64 with NVIDIA GPU
            # Try indexes from newest to oldest CUDA for best compatibility
            echo "Installing PyTorch with CUDA support (x86_64)..."
            pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 2>/dev/null \
                || pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126 2>/dev/null \
                || pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124 2>/dev/null \
                || pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 2>/dev/null \
                || { print_warn "CUDA wheels failed, trying default..."; pip install torch torchaudio; }
        elif [ "$ARCH" = "aarch64" ]; then
            # ARM64 with NVIDIA GPU (Jetson Orin, DGX Grace/Blackwell, etc.)
            echo "Installing PyTorch for ARM64 with CUDA..."

            if [ "$GPU_TYPE" = "nvidia-jetson" ]; then
                # Jetson Orin: Try cu128 first (newest), then cu126, cu124, then Jetson-specific wheels
                echo "Trying PyTorch CUDA wheels for Jetson..."
                pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 2>/dev/null \
                    || pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126 2>/dev/null \
                    || pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124 2>/dev/null \
                    || { print_warn "Standard CUDA wheels failed, trying default pip..."; pip install torch torchaudio; }
            else
                # DGX Grace / Blackwell / other ARM64 servers
                # cu128 is required for Blackwell (sm_120+), then try cu126, cu124
                echo "Installing PyTorch for ARM64 server (trying cu128 first for Blackwell)..."
                pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128 2>/dev/null \
                    || pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126 2>/dev/null \
                    || pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124 2>/dev/null \
                    || { print_warn "CUDA wheels failed, trying default pip..."; pip install torch torchaudio; }
            fi
        fi
    else
        # CPU only
        echo "Installing PyTorch CPU version..."
        if [ "$ARCH" = "x86_64" ]; then
            pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
        else
            pip install torch torchaudio
        fi
    fi

    # Verify installation
    echo ""
    echo "Verifying PyTorch..."
    python3 -c "
import torch
print(f'  PyTorch {torch.__version__}')
print(f'  CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'  CUDA version: {torch.version.cuda}')
    print(f'  GPU: {torch.cuda.get_device_name(0)}')
    props = torch.cuda.get_device_properties(0)
    mem_gb = props.total_memory / 1e9
    print(f'  GPU Memory: {mem_gb:.1f} GB')
    print(f'  Compute capability: sm_{props.major}{props.minor}')
    # Quick CUDA test
    x = torch.randn(100, 100, device='cuda')
    y = torch.matmul(x, x)
    print(f'  CUDA test: PASSED')
else:
    print('  Running on CPU (generation will be slower)')
" || print_warn "PyTorch verification had issues - may still work"
}

install_pytorch

echo ""

# ==============================================================================
# STEP 4: Python Dependencies
# ==============================================================================
print_step "Installing Python dependencies..."

# Core web framework
pip install flask flask-limiter python-dotenv 2>&1 | tail -3

# HTTP requests
pip install requests 2>&1 | tail -1

# MCP server for AI agent integration
pip install "mcp[cli]" httpx 2>&1 | tail -1

# Audio analysis and visualization
pip install numpy librosa matplotlib soundfile scipy 2>&1 | tail -3

# AudioCraft dependencies
pip install spacy einops sentencepiece hydra-core hydra-colorlog num2words 2>&1 | tail -3
pip install transformers encodec torchmetrics protobuf 2>&1 | tail -3
pip install av flashy julius lameenc 2>&1 | tail -3

# Try to install optional heavy deps (may fail on some platforms)
pip install demucs 2>/dev/null || print_warn "demucs not available for this platform (optional)"

# xformers: Provides faster attention for AudioCraft
# If native install fails (common on ARM64), create a minimal stub
# so AudioCraft can still import and fall back to PyTorch native attention
if ! pip install xformers 2>/dev/null; then
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
    echo "  xformers stub installed for AudioCraft compatibility"
fi

# AudioCraft (without strict deps since we handle them above)
pip install audiocraft --no-deps 2>&1 | tail -1

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

# ONNX Runtime for Piper TTS
if [ "$HAS_GPU" = true ] && [ "$ARCH" = "x86_64" ]; then
    pip install onnxruntime-gpu 2>/dev/null || pip install onnxruntime
elif [ "$HAS_GPU" = true ] && [ "$ARCH" = "aarch64" ]; then
    # ARM64 GPU: try gpu version, fall back to CPU
    pip install onnxruntime-gpu 2>/dev/null || pip install onnxruntime 2>/dev/null || print_warn "onnxruntime not available (TTS may not work)"
else
    pip install onnxruntime 2>/dev/null || print_warn "onnxruntime not available (TTS may not work)"
fi

# Piper TTS
pip install piper-tts 2>/dev/null || print_warn "piper-tts not available for $ARCH (TTS disabled)"

# Backup scheduler
pip install apscheduler 2>/dev/null || print_warn "apscheduler not available (scheduled backups disabled)"

echo ""

# ==============================================================================
# STEP 5: Create Directory Structure
# ==============================================================================
print_step "Creating directory structure..."

mkdir -p models/voices
mkdir -p generated
mkdir -p generated/voice_samples
mkdir -p spectrograms

echo "Directory structure created"
echo ""

# ==============================================================================
# STEP 6: Create .env if missing
# ==============================================================================
print_step "Checking configuration..."

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Created .env from .env.example (open access mode enabled by default)"
else
    echo ".env already exists"
fi

echo ""

# ==============================================================================
# STEP 7: Download Piper TTS Voices
# ==============================================================================
print_step "Downloading Piper TTS voices..."

if command -v piper &> /dev/null || python3 -c "import piper" 2>/dev/null; then
    if [ -f "scripts/download-voices.sh" ]; then
        bash scripts/download-voices.sh
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

        for voice_name in "${!VOICE_URLS[@]}"; do
            voice_path="${VOICE_URLS[$voice_name]}"
            onnx_file="$VOICES_DIR/${voice_name}.onnx"
            json_file="$VOICES_DIR/${voice_name}.onnx.json"

            if [ ! -s "$onnx_file" ]; then
                echo "Downloading $voice_name..."
                rm -f "$onnx_file" "$json_file"
                wget -q --show-progress -O "$onnx_file" "$PIPER_BASE/$voice_path/$voice_name.onnx" || true
                wget -q -O "$json_file" "$PIPER_BASE/$voice_path/$voice_name.onnx.json" || true
            else
                echo "Already have: $voice_name"
            fi
        done
    fi
else
    print_warn "Piper TTS not installed - skipping voice download"
fi

echo ""

# ==============================================================================
# STEP 8: Pre-download AudioCraft Models
# ==============================================================================
print_step "Pre-downloading AudioCraft models..."

# Non-interactive: auto-download if running with --auto flag, otherwise ask
if [ "${1}" = "--auto" ] || [ "${NONINTERACTIVE}" = "1" ]; then
    DOWNLOAD_MODELS="y"
else
    read -p "Download AudioCraft models now? (~5GB, speeds up first run) [y/N] " -n 1 -r
    echo
    DOWNLOAD_MODELS="$REPLY"
fi

if [[ $DOWNLOAD_MODELS =~ ^[Yy]$ ]]; then
    python3 << 'PYEOF'
import torch
try:
    print("Downloading MusicGen model...")
    from audiocraft.models import MusicGen
    MusicGen.get_pretrained('facebook/musicgen-medium')
    print("MusicGen downloaded!")
except Exception as e:
    print(f"MusicGen download failed: {e}")

try:
    print("Downloading AudioGen model...")
    from audiocraft.models import AudioGen
    AudioGen.get_pretrained('facebook/audiogen-medium')
    print("AudioGen downloaded!")
except Exception as e:
    print(f"AudioGen download failed: {e}")

print("Model download complete!")
PYEOF
else
    echo "Skipping model download - they will download on first use"
fi

echo ""

# ==============================================================================
# STEP 9: Initialize Database
# ==============================================================================
print_step "Initializing database..."

python3 -c "import database; database.init_db()"
echo "Database initialized"
echo ""

# ==============================================================================
# STEP 10: Install systemd service (optional)
# ==============================================================================
# Skip in Docker (no systemd) or when SKIP_SERVICES=1
if [ -f "/.dockerenv" ] || [ "${SKIP_SERVICES}" = "1" ]; then
    print_info "Skipping systemd service (Docker or SKIP_SERVICES=1)"
else
    print_step "Setting up systemd service..."

    if [ "${1}" = "--auto" ] || [ "${NONINTERACTIVE}" = "1" ]; then
        INSTALL_SERVICE="y"
    else
        read -p "Install systemd service (auto-start on boot)? [Y/n] " -n 1 -r
        echo
        INSTALL_SERVICE="${REPLY:-Y}"
    fi

    if [[ $INSTALL_SERVICE =~ ^[Yy]$ ]]; then
        bash "$SCRIPT_DIR/scripts/service.sh" install
    else
        echo "Skipping systemd service - use './scripts/service.sh install' later"
    fi
fi

echo ""

# ==============================================================================
# STEP 11: Install Node.js and Playwright tests (optional)
# ==============================================================================
# Skip in Docker (not needed for production) or when SKIP_TESTS=1
if [ -f "/.dockerenv" ] || [ "${SKIP_TESTS}" = "1" ]; then
    print_info "Skipping test environment (Docker or SKIP_TESTS=1)"
else
    print_step "Setting up test environment..."

    # Install Node.js if not present
    if ! command -v node &> /dev/null; then
        print_info "Installing Node.js 20 LTS..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - 2>&1 | tail -1
        sudo apt-get install -y -qq nodejs 2>&1 | tail -1
    fi

    if command -v npm &> /dev/null; then
        print_info "Node.js $(node --version), npm $(npm --version)"
        npm install 2>&1 | tail -3
        npx playwright install chromium 2>&1 | tail -3 || true
        npx playwright install-deps chromium 2>&1 | tail -3 || true
        echo "  Tests ready: npm test"
    else
        print_warn "npm not available - skipping Playwright test setup"
    fi
fi

echo ""

# ==============================================================================
# COMPLETE
# ==============================================================================
echo "=============================================="
echo -e "${GREEN}       SETUP COMPLETE!${NC}"
echo "=============================================="
echo ""
echo "System: $ARCH | GPU: ${GPU_TYPE:-cpu} | CUDA: ${CUDA_VERSION:-none}"
echo ""
echo "To start Sound Box:"
echo "  ./start.sh"
echo ""
echo "Service management (if installed):"
echo "  ./scripts/service.sh status    # Check service status"
echo "  ./scripts/service.sh stop      # Stop the service"
echo "  ./scripts/service.sh disable   # Disable auto-start"
echo "  ./scripts/service.sh uninstall # Remove service completely"
echo ""
echo "Then open: http://localhost:5309"
echo ""
echo "Configuration: Edit .env to change settings"
echo "  OPEN_ACCESS_MODE=true  (no login required - default)"
echo "  IP_WHITELIST=          (elevated limits for specific IPs)"
echo ""
