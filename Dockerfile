# CUDA 13.0 provides NVRTC that supports Blackwell sm_121 (GB10/GB20)
# Available for both linux/amd64 and linux/arm64
FROM nvidia/cuda:13.0.0-runtime-ubuntu24.04

# Avoid interactive prompts during apt-get
ENV DEBIAN_FRONTEND=noninteractive

# System dependencies (includes sudo for setup.sh compatibility)
RUN apt-get update -qq && apt-get install -y -qq \
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
    sudo \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy app code
COPY . .

# Run setup.sh in non-interactive mode to handle all platform-specific logic:
# - Creates venv and installs PyTorch with correct CUDA wheels
# - Installs all Python deps (audiocraft, piper, xformers stub, etc.)
# - Downloads Piper TTS voices
# - Pre-downloads AudioCraft models (~5GB)
# - Initializes the database
#
# FORCE_CUDA: install CUDA-enabled PyTorch even without GPU at build time
# FORCE_NVRTC_FIX: replace PyTorch's bundled NVRTC 12.8 with system NVRTC 13.0
#                  (required for Blackwell sm_121 which NVRTC 12.8 doesn't support)
# SKIP_SERVICES: no systemd in Docker
# SKIP_TESTS: no need for Playwright in production image
RUN FORCE_CUDA=1 FORCE_NVRTC_FIX=1 SKIP_SERVICES=1 SKIP_TESTS=1 bash setup.sh --auto

# Create directories for volume mounts
RUN mkdir -p generated spectrograms data

EXPOSE 5309

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:5309/status || exit 1

CMD ["./start.sh"]
