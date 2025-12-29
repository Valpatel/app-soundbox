# Sound Box Backup & Sync Guide

This guide explains how to backup your Sound Box installation for easy restoration on a new computer.

## Quick Start with Syncthing

[Syncthing](https://syncthing.net/) is recommended for automatic, encrypted peer-to-peer sync between machines.

### Folders to Sync

Add these folders to Syncthing for complete backup:

| Folder | Size | Description |
|--------|------|-------------|
| `generated/` | Variable (grows over time) | All generated audio files |
| `models/` | ~2GB | Piper TTS voice models |
| `soundbox.db` | Small | SQLite database with metadata |

### Folders NOT to Sync (Reinstall Instead)

| Folder | Why |
|--------|-----|
| `venv/` | Python packages - reinstall with `setup.sh` |
| `node_modules/` | Node packages - reinstall with `npm install` |
| `~/.cache/huggingface/` | AudioCraft models - download on first use |

## Directory Structure

```
app-soundbox/
├── generated/           # SYNC - All audio files
│   ├── *.wav           # Generated music/SFX/speech
│   └── voice_samples/  # TTS voice preview samples
├── models/              # SYNC - AI models
│   └── voices/         # Piper TTS voice files (.onnx)
├── soundbox.db          # SYNC - Database
├── spectrograms/        # Optional - Can regenerate
├── venv/                # DO NOT SYNC - Reinstall
└── node_modules/        # DO NOT SYNC - Reinstall
```

## Setup on New Computer

### Option 1: Fresh Install + Restore Data

```bash
# 1. Clone the repository
git clone <your-repo-url> app-soundbox
cd app-soundbox

# 2. Run setup (installs all dependencies)
./setup.sh

# 3. Sync/copy your data folders
#    - Copy generated/ from backup
#    - Copy models/ from backup
#    - Copy soundbox.db from backup

# 4. Start the app
./start.sh
```

### Option 2: Full Directory Sync

If syncing the entire `app-soundbox/` folder:

```bash
# After sync completes, reinstall dependencies
cd app-soundbox
rm -rf venv node_modules  # Clear old environment
./setup.sh                # Reinstall everything
./start.sh                # Start app
```

## Syncthing Configuration

### Recommended .stignore File

Create `.stignore` in your Sound Box folder:

```
// Python environment - reinstall instead
venv/
__pycache__/
*.pyc
*.pyo

// Node modules - reinstall instead
node_modules/

// Temporary files
*.log
*.tmp
.last-run.json

// Test artifacts
playwright-report/
test-results/

// IDE files
.vscode/
.idea/
*.swp
*.swo
```

### Sync Priority

For fastest setup on new machine, sync in this order:
1. `soundbox.db` (small, contains all metadata)
2. `models/voices/` (~2GB, needed for TTS)
3. `generated/` (can be large, but app works without it)

## AudioCraft Models Location

AudioCraft models (MusicGen, AudioGen) are stored in:
- Linux/Mac: `~/.cache/huggingface/hub/`
- Windows: `C:\Users\<user>\.cache\huggingface\hub\`

These are ~5GB and will auto-download on first use. To pre-download:

```bash
source venv/bin/activate
python -c "
from audiocraft.models import MusicGen, AudioGen
MusicGen.get_pretrained('facebook/musicgen-medium')
AudioGen.get_pretrained('facebook/audiogen-medium')
"
```

To sync these between machines, add `~/.cache/huggingface/` to Syncthing.

## Database Backup

The SQLite database can be backed up while the app is running:

```bash
# Create backup
sqlite3 soundbox.db ".backup soundbox-backup.db"

# Or use the copy command (app should be stopped)
cp soundbox.db soundbox-backup.db
```

## Restore Checklist

- [ ] Clone/copy repository
- [ ] Run `./setup.sh`
- [ ] Copy `soundbox.db` to project root
- [ ] Copy `generated/` folder
- [ ] Copy `models/voices/` folder
- [ ] Run `./start.sh`
- [ ] Verify at http://localhost:5309

## Storage Estimates

| Component | Approximate Size |
|-----------|------------------|
| Code + Dependencies | ~3GB |
| Piper Voices (all English) | ~2GB |
| AudioCraft Models | ~5GB |
| Generated Audio | Varies (10MB-100GB+) |

Total fresh install: ~10GB + your audio library
