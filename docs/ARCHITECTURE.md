# Sound Box Architecture

## Overview

Sound Box is an AI-powered audio generation service that creates music and sound effects from text prompts using Meta's AudioCraft models.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Browser                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │   Radio     │  │   Library   │  │  Generate   │              │
│  │   Player    │  │   Browser   │  │    Form     │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/REST
┌──────────────────────────▼──────────────────────────────────────┐
│                      Flask Server (app.py)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    API Endpoints                          │   │
│  │  /generate  /job/{id}  /api/library  /api/radio  etc.    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │              Priority Queue System                        │   │
│  │  Admin(0) → Premium(1) → Standard(2) → Free(3)           │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼─────────────────────────────────┐   │
│  │              AudioCraft Models (GPU)                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                │   │
│  │  │   MusicGen      │  │   AudioGen      │                │   │
│  │  │   (Small)       │  │   (Medium)      │                │   │
│  │  │   ~1GB VRAM     │  │   ~1.5GB VRAM   │                │   │
│  │  └─────────────────┘  └─────────────────┘                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│   SQLite DB   │  │  generated/   │  │ spectrograms/ │
│ (soundbox.db) │  │  (WAV files)  │  │  (PNG files)  │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Technology Stack

### Backend
- **Python 3.10+** - Core runtime
- **Flask** - Web framework
- **PyTorch 2.0+** - Deep learning with CUDA
- **AudioCraft** - Meta's audio generation models
- **SQLite3** - Database with FTS5 full-text search
- **librosa** - Audio analysis
- **matplotlib** - Spectrogram visualization

### Frontend
- **Vanilla JavaScript** - No framework, lightweight
- **HTML5 Audio API** - Playback
- **CSS3 Variables** - Theming support
- **Graphlings SDK** - Authentication integration

## Threading Model

The application uses three concurrent threads:

```
┌─────────────────────────────────────────────────────────┐
│                    Main Thread                           │
│  - Flask HTTP request handlers                          │
│  - API endpoint logic                                   │
│  - Database queries                                     │
│  - File serving                                         │
└─────────────────────────────────────────────────────────┘
                           │
          ┌────────────────┴────────────────┐
          ▼                                 ▼
┌─────────────────────────┐    ┌─────────────────────────┐
│   Model Loader Thread   │    │   Queue Worker Thread   │
│  - Preload MusicGen     │    │  - Monitor job queue    │
│  - Preload AudioGen     │    │  - Execute generation   │
│  - Background loading   │    │  - Quality analysis     │
│  - Status updates       │    │  - Auto-retry           │
└─────────────────────────┘    └─────────────────────────┘
```

### Thread Safety

The `queue_lock` (threading.Lock) protects:
- `jobs` dictionary - all active/completed job states
- `job_queue` - priority queue of pending jobs
- `current_job` - ID of currently processing job

All operations that read or modify job state acquire this lock first.

## Data Flow

### Generation Request
```
1. User submits prompt via /generate
       ↓
2. Job added to priority queue
       ↓
3. Queue worker picks up job (FIFO within tier)
       ↓
4. AudioCraft model generates audio
       ↓
5. Quality analysis (clipping, silence, noise)
       ↓
6. If quality < 50: retry (max 2 times)
       ↓
7. Save WAV to generated/
       ↓
8. Generate spectrogram PNG
       ↓
9. Save metadata to SQLite
       ↓
10. Client polls /job/{id} for completion
```

### Quality Analysis Pipeline
```
Audio Generated
      ↓
┌─────────────────────────────────────────┐
│ Quality Checks (0-100 score)            │
│  - Clipping: values > 0.98 for > 5%     │
│  - Silence: RMS < 0.005                 │
│  - High-freq noise: energy > 14kHz      │
│  - Spectral flatness: pure noise check  │
└─────────────────────────────────────────┘
      ↓
Score < 50 AND has issues?
      ↓
  Yes: Retry (max 2)
  No: Accept and save
```

## Priority Queue System

Jobs are processed in priority order, FIFO within each tier:

| Priority | Tier     | Use Case                |
|----------|----------|-------------------------|
| 0        | Admin    | System/testing          |
| 1        | Premium  | Paid users              |
| 2        | Standard | Authenticated users     |
| 3        | Free     | Anonymous requests      |

## File Organization

```
app-soundbox/
├── app.py              # Flask server (1,601 lines)
│   ├── Model loading and caching
│   ├── Job queue processing
│   ├── API endpoint handlers
│   ├── Quality analysis
│   └── File serving
│
├── database.py         # SQLite layer (1,339 lines)
│   ├── Schema definitions
│   ├── CRUD operations
│   ├── Full-text search (FTS5)
│   ├── Auto-categorization
│   └── Migration utilities
│
├── prompts.py          # Prompt generation (905 lines)
│   ├── Category definitions
│   ├── Keyword mappings
│   └── Random prompt templates
│
├── batch_generate.py   # Batch utility (461 lines)
│   ├── Parallel generation
│   ├── CLI interface
│   └── Progress tracking
│
└── templates/
    └── index.html      # Frontend SPA (7,977 lines)
        ├── Radio player
        ├── Library browser
        ├── Generator interface
        └── Modals & toasts
```

## Key Design Decisions

### 1. Single-File Frontend
All HTML, CSS, and JavaScript in one file for simplicity. No build step required.

### 2. SQLite with FTS5
Full-text search built into the database for fast prompt searching without external dependencies.

### 3. Priority Queue
Fair processing while allowing priority for authenticated or premium users.

### 4. Auto-Retry on Poor Quality
Automatic quality detection prevents bad generations from polluting the library.

### 5. Crowdsourced Categorization
Users can suggest categories; consensus (3+ votes) auto-applies changes.

### 6. Private Feedback
All feedback is private (no public comments) to maintain quality discussion.

## Performance Considerations

- **GPU Memory**: Models share VRAM; only one generation runs at a time
- **Database Indexes**: Optimized for common queries (model, date, category, votes)
- **Denormalized Counts**: Vote counts stored directly on generations for fast queries
- **Pagination**: All list endpoints support pagination (max 100 items)
- **Spectrogram Caching**: Generated once, served from disk thereafter
