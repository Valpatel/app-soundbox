#!/bin/bash
set -e

echo "=== AudioCraft Setup Script ==="

# Install system dependencies
echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    pkg-config

# Create virtual environment
echo "Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies (this may take several minutes)..."

# Core dependencies
pip install flask

# PyTorch with CUDA
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# AudioCraft dependencies
pip install spacy av einops numpy sentencepiece hydra-core hydra-colorlog num2words
pip install flashy julius lameenc demucs xformers transformers
pip install soundfile librosa encodec torchmetrics protobuf matplotlib

# AudioCraft (without strict deps since we're using newer versions)
pip install audiocraft --no-deps

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To run the app:"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "Then open http://localhost:5309 in your browser"
