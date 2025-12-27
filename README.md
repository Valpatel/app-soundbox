# Sound Box

AI-powered music and sound effects generator built on Meta's AudioCraft models. An example Graphlings.net integrated app.

## Features

- **Music Generation** - Create original music from text prompts using MusicGen
- **Sound Effects** - Generate ambient sounds and SFX using AudioGen
- **Loop Mode** - Seamless looping with crossfade for game-ready audio
- **Quality Analysis** - Automatic audio quality scoring with auto-retry
- **Spectrograms** - Visual mel spectrogram display for each generation
- **Priority Queue** - Multi-tier job queue (admin → premium → standard → free)
- **Library & Voting** - Browse, search, and rate generations with feedback
- **Radio Mode** - Shuffle play through generated audio with station presets
- **Crowdsourced Tags** - Community category suggestions with consensus voting
- **SQLite + FTS5** - Full-text search and efficient metadata storage
- **Random Prompts** - Extensive vocabulary for creative prompt inspiration

## Graphlings Integration

Sound Box integrates with [Graphlings.net](https://graphlings.net) for:

- **User Authentication** - Sign in with Graphlings account
- **Theme Sync** - Automatically matches the user's selected Graphlings theme
- **User History** - Generations are associated with authenticated users
- **Future: Wallet Integration** - Sprite/Aura costs for premium generations

```javascript
// Theme sync from Graphlings widget
window.graphlings.on('widgetReady', function(data) {
    if (data.theme && THEMES[data.theme]) {
        applyTheme(data.theme);
    }
    if (data.authenticated && data.user) {
        currentUserId = data.user.id;
        loadHistory();
    }
});
```

## Requirements

- Python 3.10+
- NVIDIA GPU with CUDA support (8GB+ VRAM recommended)
- CUDA 12.1 or compatible version
- FFmpeg

## Quick Start

```bash
# Clone the repository
git clone git@github.com:Valpatel/app-soundbox.git
cd app-soundbox

# Run setup script (installs system deps, creates venv, installs Python packages)
# Note: May require sudo for system dependencies
chmod +x setup.sh
./setup.sh

# Start the server
./start.sh
```

Open http://localhost:5309 in your browser.

## Manual Setup

If you prefer manual installation:

```bash
# System dependencies (Ubuntu/Debian)
sudo apt-get install -y ffmpeg libavformat-dev libavcodec-dev \
    libavdevice-dev libavutil-dev libavfilter-dev \
    libswscale-dev libswresample-dev pkg-config

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install flask
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install librosa numpy matplotlib soundfile
pip install audiocraft --no-deps
pip install spacy av einops sentencepiece hydra-core hydra-colorlog num2words
pip install flashy julius lameenc demucs xformers transformers encodec torchmetrics protobuf
```

## Configuration

Copy `.env.example` to `.env` and customize as needed:

```bash
cp .env.example .env
```

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `5309` |
| `FLASK_DEBUG` | Enable debug mode with auto-reload | `false` |

## API Reference

See [docs/API.md](docs/API.md) for the complete API reference with all endpoints.

### Generate Audio
```
POST /generate
Content-Type: application/json

{
    "prompt": "upbeat electronic music with synth arpeggios",
    "duration": 10,
    "model": "music",  // "music" or "audio"
    "loop": true,
    "priority": "standard",
    "user_id": "optional-graphlings-user-id"
}

Response:
{
    "success": true,
    "job_id": "abc123...",
    "position": 1
}
```

### Check Job Status
```
GET /job/<job_id>

Response:
{
    "id": "abc123...",
    "status": "completed",  // "queued", "processing", "completed", "failed"
    "progress": "Done!",
    "progress_pct": 100,
    "filename": "abc123.wav",
    "spectrogram": "abc123.png",
    "quality": {
        "score": 85,
        "issues": [],
        "is_good": true
    }
}
```

### Get History
```
GET /history?user_id=xxx&model=music

Response: [
    {
        "filename": "abc123.wav",
        "prompt": "upbeat electronic music",
        "model": "music",
        "duration": 10,
        "loop": true,
        "rating": 1,
        "quality_score": 85,
        "spectrogram": "abc123.png"
    }
]
```

### Rate Generation
```
POST /rate
Content-Type: application/json

{
    "filename": "abc123.wav",
    "rating": 1  // 1 (thumbs up), -1 (thumbs down), or null (remove)
}
```

### Random Prompt
```
POST /random-prompt
Content-Type: application/json

{
    "model": "music"  // "music" or "audio"
}

Response:
{
    "success": true,
    "prompt": "melancholic synthwave with warm pads"
}
```

### System Status
```
GET /status

Response:
{
    "models": {
        "music": "ready",
        "audio": "ready"
    },
    "gpu": {
        "available": true,
        "name": "NVIDIA GeForce RTX 4090",
        "memory_used_gb": 4.2,
        "memory_total_gb": 24.0,
        "memory_percent": 17.5,
        "busy": false
    },
    "queue_length": 0,
    "estimated_wait": 0
}
```

## Project Structure

```
app-soundbox/
├── app.py              # Flask server with AudioCraft integration
├── database.py         # SQLite database layer with FTS5 search
├── prompts.py          # Category definitions and random prompts
├── batch_generate.py   # Utility for bulk content generation
├── templates/
│   └── index.html      # Frontend SPA with Graphlings integration
├── static/
│   ├── js/             # RadioWidget JavaScript modules
│   └── css/            # Widget and app stylesheets
├── tests/              # Playwright test suites
├── docs/               # Documentation
│   ├── API.md          # Complete API reference
│   ├── DATABASE.md     # Schema and queries
│   ├── ARCHITECTURE.md # System design
│   ├── FRONTEND.md     # UI documentation
│   ├── DEPLOYMENT.md   # Installation guide
│   └── TROUBLESHOOTING.md
├── generated/          # Output audio files (created at runtime)
├── spectrograms/       # Spectrogram images (created at runtime)
├── soundbox.db         # SQLite database (created at runtime)
├── setup.sh            # One-command setup script
├── start.sh            # Server startup script
├── requirements.txt    # Python dependencies
├── CLAUDE.md           # AI assistant context notes
└── README.md           # This file
```

## Models

Sound Box uses Meta's AudioCraft models:

| Model | Size | Use Case | Generation Speed |
|-------|------|----------|-----------------|
| MusicGen Small | ~1GB | Music generation | ~1.5s per second of audio |
| AudioGen Medium | ~1.5GB | Sound effects | ~0.5s per second of audio |

Models are loaded on startup in a background thread. Check `/status` to see loading progress.

## Quality Analysis

Generated audio is automatically analyzed for:

- **Clipping** - Detects harsh distortion from values near ±1.0
- **Silence** - Flags very low audio levels
- **High-frequency noise** - Detects static or harsh artifacts
- **Spectral flatness** - Identifies pure noise vs tonal content

Low-quality generations are automatically retried up to 2 times.

## Priority Queue

Jobs are processed based on priority tier:

1. **Admin** (priority 0) - Immediate processing
2. **Premium** (priority 1) - High priority
3. **Standard** (priority 2) - Default tier
4. **Free** (priority 3) - Lowest priority

Within each tier, jobs are processed in FIFO order.

## Development

```bash
# Run with auto-reload (not recommended for production)
FLASK_DEBUG=1 python app.py

# Run production mode
python app.py
```

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for detailed solutions.

**Quick checks:**

- **Models fail to load** - Check GPU memory: `nvidia-smi`
- **CUDA not detected** - Verify: `python -c "import torch; print(torch.cuda.is_available())"`
- **No audio output** - Check FFmpeg: `ffmpeg -version`
- **Database errors** - Initialize: `python database.py init`

## License

MIT License - See LICENSE file for details.

## Credits

- [AudioCraft](https://github.com/facebookresearch/audiocraft) by Meta AI
- [Graphlings.net](https://graphlings.net) platform integration
- Built with Flask, PyTorch, and librosa
