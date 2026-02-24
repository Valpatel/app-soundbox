# Sound Box Deployment Guide

## System Requirements

### Hardware

- **GPU:** NVIDIA GPU with CUDA support (4GB+ VRAM recommended)
  - MusicGen Small: ~1GB VRAM
  - AudioGen Medium: ~1.5GB VRAM
  - Both loaded: ~2.5GB VRAM
- **RAM:** 16GB+ recommended
- **Storage:** 10GB+ for models and generated audio

### Software

- **OS:** Ubuntu 20.04+ / Debian 11+ (or Windows with WSL2)
- **Python:** 3.10 or 3.11
- **CUDA:** 12.1+ (for GPU acceleration)
- **FFmpeg:** Required for audio processing

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-org/app-soundbox.git
cd app-soundbox
```

### 2. Run Setup Script

```bash
chmod +x setup.sh
./setup.sh
```

This script:
- Installs system dependencies (FFmpeg, libav*)
- Creates Python virtual environment
- Installs PyTorch with CUDA 12.1 support
- Installs AudioCraft and dependencies

### 3. Start Server

```bash
source venv/bin/activate
python app.py
```

Server starts at `http://localhost:5309`

## Manual Installation

### 1. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y ffmpeg libavformat-dev libavcodec-dev \
    libavdevice-dev libavutil-dev libavfilter-dev \
    libswscale-dev libswresample-dev pkg-config
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 3. Install Python Dependencies

For GPU (recommended):
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
```

For CPU only (slower):
```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `5309` | HTTP port |
| `FLASK_DEBUG` | `false` | Enable debug mode (development only) |

### Database

SQLite database is created automatically at `soundbox.db` on first run.

To initialize manually:
```bash
python database.py init
```

To migrate from legacy JSON:
```bash
python database.py migrate
```

## Directory Structure

After setup:
```
app-soundbox/
├── app.py              # Main server
├── database.py         # Database layer
├── soundbox.db         # SQLite database (created on run)
├── generated/          # Output audio files (created on run)
├── spectrograms/       # Spectrogram images (created on run)
└── venv/               # Python virtual environment
```

## Model Loading

Models are loaded on startup in a background thread:

1. **MusicGen Small** (~1GB) - Loads first
2. **AudioGen Medium** (~1.5GB) - Loads second
3. **MAGNeT** (optional) - Loads if available

First startup takes 30-60 seconds for model downloads.

## Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
gunicorn -w 1 -b 0.0.0.0:5309 --timeout 300 app:app
```

**Note:** Use `-w 1` (single worker) because GPU operations require sequential access.

### Using service.sh (Recommended)

The built-in service manager installs all three services (main server, MCP, mDNS):

```bash
./scripts/service.sh install    # Install and start everything
./scripts/service.sh status     # Check all services
./scripts/service.sh logs       # Follow combined logs
./scripts/service.sh uninstall  # Remove everything
```

### Manual Systemd (Alternative)

Create `/etc/systemd/system/soundbox.service`:

```ini
[Unit]
Description=Sound Box Audio Generation Server
After=network.target

[Service]
User=soundbox
WorkingDirectory=/opt/app-soundbox
Environment="PATH=/opt/app-soundbox/venv/bin"
ExecStart=/opt/app-soundbox/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable soundbox
sudo systemctl start soundbox
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name soundbox.example.com;

    location / {
        proxy_pass http://127.0.0.1:5309;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;  # Long timeout for generation
    }

    # Serve audio files directly
    location /audio/ {
        alias /opt/app-soundbox/generated/;
    }

    location /spectrogram/ {
        alias /opt/app-soundbox/spectrograms/;
    }
}
```

## Health Check

```bash
# System status
curl http://localhost:5309/status

# Service manifest (full discovery info)
curl http://localhost:5309/api/manifest
```

Expected response (ready):
```json
{
  "models": {"music": "ready", "audio": "ready"},
  "queue_length": 0
}
```

## Backup

### Database
```bash
sqlite3 soundbox.db ".backup backup.db"
```

### Generated Files
```bash
tar -czf soundbox-backup.tar.gz generated/ spectrograms/ soundbox.db
```

## Updating

```bash
cd app-soundbox
git pull
source venv/bin/activate
pip install -r requirements.txt
python database.py migrate  # Apply any schema changes
sudo systemctl restart soundbox
```
