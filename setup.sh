#!/bin/bash
# Sound Box - Complete Setup Script
# This script installs all dependencies, downloads models, and prepares the system
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

# Check for NVIDIA GPU
check_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        echo -e "${GREEN}[OK]${NC} NVIDIA GPU detected"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
        return 0
    else
        print_warn "No NVIDIA GPU detected - will use CPU (slower)"
        return 1
    fi
}

# ==============================================================================
# STEP 1: System Dependencies
# ==============================================================================
print_step "Installing system dependencies..."

sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    pkg-config \
    curl \
    wget \
    git

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
pip install --upgrade pip

echo ""

# ==============================================================================
# STEP 3: Python Dependencies
# ==============================================================================
print_step "Installing Python dependencies (this may take 5-10 minutes)..."

# Core web framework
pip install flask flask-limiter

# Check for GPU and install appropriate PyTorch
if check_gpu; then
    echo "Installing PyTorch with CUDA support..."
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

    # ONNX Runtime with GPU for Piper TTS
    pip install onnxruntime-gpu
else
    echo "Installing PyTorch CPU version..."
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
    pip install onnxruntime
fi

# AudioCraft dependencies
pip install spacy av einops numpy sentencepiece hydra-core hydra-colorlog num2words
pip install flashy julius lameenc demucs xformers transformers
pip install soundfile librosa encodec torchmetrics protobuf matplotlib scipy

# AudioCraft (without strict deps since we're using newer versions)
pip install audiocraft --no-deps

# Piper TTS
pip install piper-tts

echo ""

# ==============================================================================
# STEP 4: Create Directory Structure
# ==============================================================================
print_step "Creating directory structure..."

mkdir -p models/voices
mkdir -p generated
mkdir -p generated/voice_samples
mkdir -p spectrograms

echo "Directory structure created"
echo ""

# ==============================================================================
# STEP 5: Download Piper TTS Voices
# ==============================================================================
print_step "Downloading Piper TTS voices..."

if [ -f "scripts/download-voices.sh" ]; then
    bash scripts/download-voices.sh
else
    echo "Running inline voice download..."

    VOICES_DIR="models/voices"
    PIPER_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"

    # Essential English voices
    VOICES=(
        "en_US/lessac/medium"
        "en_US/amy/medium"
        "en_US/ryan/medium"
        "en_US/joe/medium"
        "en_GB/alan/medium"
        "en_GB/alba/medium"
    )

    for voice_path in "${VOICES[@]}"; do
        voice_name=$(echo "$voice_path" | tr '/' '-')
        onnx_file="$VOICES_DIR/${voice_name}.onnx"
        json_file="$VOICES_DIR/${voice_name}.onnx.json"

        if [ ! -f "$onnx_file" ]; then
            echo "Downloading $voice_name..."
            wget -q --show-progress -O "$onnx_file" "$PIPER_BASE/$voice_path/$voice_name.onnx" || true
            wget -q -O "$json_file" "$PIPER_BASE/$voice_path/$voice_name.onnx.json" || true
        else
            echo "Already have: $voice_name"
        fi
    done
fi

echo ""

# ==============================================================================
# STEP 6: Pre-download AudioCraft Models (Optional)
# ==============================================================================
print_step "Pre-downloading AudioCraft models (optional, ~5GB)..."

read -p "Download AudioCraft models now? This requires ~5GB and speeds up first run. [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 << 'EOF'
import torch
print("Downloading MusicGen model...")
from audiocraft.models import MusicGen
MusicGen.get_pretrained('facebook/musicgen-medium')
print("MusicGen downloaded!")

print("Downloading AudioGen model...")
from audiocraft.models import AudioGen
AudioGen.get_pretrained('facebook/audiogen-medium')
print("AudioGen downloaded!")
print("All models downloaded!")
EOF
else
    echo "Skipping model download - they will download on first use"
fi

echo ""

# ==============================================================================
# STEP 7: Initialize Database
# ==============================================================================
print_step "Initializing database..."

python3 -c "import database; database.init_db()"
echo "Database initialized"
echo ""

# ==============================================================================
# COMPLETE
# ==============================================================================
echo "=============================================="
echo -e "${GREEN}       SETUP COMPLETE!${NC}"
echo "=============================================="
echo ""
echo "To start Sound Box:"
echo "  ./start.sh"
echo ""
echo "Or manually:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "Then open: http://localhost:5309"
echo ""
echo "=============================================="
echo "Syncthing Backup Recommendation:"
echo "=============================================="
echo "Add these folders to Syncthing for full backup:"
echo "  - generated/     (all audio files)"
echo "  - models/        (AI models & voices)"
echo "  - soundbox.db    (database)"
echo ""
echo "See BACKUP.md for detailed backup instructions"
echo ""
