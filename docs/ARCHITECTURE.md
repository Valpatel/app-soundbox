# Architecture Overview

How Sound Box works internally. Use this guide to understand the system before diving into specific components.

```mermaid
graph TB
    subgraph Clients
        UI[Web UI]
        API[API Client]
        Widget[Radio Widget]
    end

    subgraph "Flask Server"
        Routes[Route Handlers]
        Auth[Auth Middleware]
        Limiter[Rate Limiter]
    end

    subgraph "Background Threads"
        Loader[Model Loader]
        Worker[Queue Worker]
        Backup[Backup Scheduler]
    end

    subgraph "AI Models"
        MusicGen[MusicGen]
        AudioGen[AudioGen]
        MAGNeT[MAGNeT]
        Piper[Piper TTS]
    end

    subgraph Storage
        DB[(SQLite + FTS5)]
        Audio[generated/]
        Voices[models/voices/]
    end

    UI --> Routes
    API --> Routes
    Widget --> Routes
    Routes --> Auth
    Auth --> Limiter

    Routes --> Worker
    Worker --> MusicGen
    Worker --> AudioGen
    Worker --> MAGNeT
    Routes --> Piper

    Worker --> DB
    Worker --> Audio
    Piper --> Audio
    Piper --> Voices
    Backup --> DB
    Backup --> Audio
```

## Core Components

### Flask Application (`app.py`)

The main entry point (~4,400 lines). Handles:

- **HTTP Routes** - REST API endpoints for all operations
- **Authentication** - Token validation against external auth service (Valnet)
- **Rate Limiting** - Per-endpoint limits using Flask-Limiter
- **Job Submission** - Validates requests, adds to priority queue
- **Static Serving** - Audio files, spectrograms, widget assets

### Database Layer (`database.py`)

SQLite with FTS5 full-text search (~800 lines). Provides:

- **Schema Management** - Tables, indexes, migrations
- **CRUD Operations** - Generations, votes, playlists
- **Full-Text Search** - FTS5 virtual table for prompt search
- **Category System** - Keyword-based auto-categorization
- **Query Sanitization** - FTS5 injection prevention

### Backup System (`backup.py`)

Automated backup with tiered retention:

- **Database Backup** - SQLite's backup command (safe while running)
- **Audio Sync** - rsync with hardlinks to previous backup
- **Retention Policy** - 14 days daily, then weekly for 2 months

---

## Threading Model

Sound Box uses multiple background threads for concurrent operations.

```mermaid
flowchart LR
    subgraph "Main Thread"
        Flask[Flask Server]
    end

    subgraph "Background Threads"
        ML[Model Loader<br/>daemon=True]
        QW[Queue Worker<br/>daemon=True]
        BS[Backup Scheduler<br/>daemon=True]
    end

    Flask -->|"start on boot"| ML
    Flask -->|"start on boot"| QW
    Flask -->|"start if BACKUP_DIR"| BS

    QW -->|"spawns per-job"| PT[Progress Tracker<br/>daemon=True]
```

| Thread | Purpose | Lifecycle |
|--------|---------|-----------|
| Main | Flask web server, handles all HTTP | Process lifetime |
| Model Loader | Preloads commonly-used AI models on startup | Exits after loading |
| Queue Worker | Processes generation jobs from priority queue | Process lifetime |
| Progress Tracker | Updates job progress during generation | Per-job, exits on completion |
| Backup Scheduler | Runs nightly backups via APScheduler | Process lifetime (if enabled) |

### Thread Safety

- `queue_lock` - Protects `jobs` dict and job state transitions
- `model_lock` - Protects model loading/unloading operations
- `voice_models_lock` - Protects TTS voice model cache

---

## Request Flow

### Audio Generation

```mermaid
sequenceDiagram
    participant C as Client
    participant F as Flask
    participant Q as Queue Worker
    participant M as AI Model
    participant DB as Database

    C->>+F: POST /generate
    F->>F: Validate token
    F->>F: Check rate limits
    F->>F: Check user queue limit
    F->>F: Add to PriorityQueue
    F-->>-C: {job_id, position}

    loop Until job processed
        C->>F: GET /job/{id}
        F-->>C: {status, progress}
    end

    Q->>Q: Pick next job (priority + affinity)
    Q->>M: Load model if needed
    Q->>M: Generate audio
    M-->>Q: Audio tensor
    Q->>Q: Quality analysis
    Q->>Q: Save to generated/
    Q->>DB: Insert metadata
    Q->>Q: Generate spectrogram

    C->>F: GET /job/{id}
    F-->>C: {status: completed, audio_url}
    C->>F: GET /audio/{file}
    F-->>C: Audio file
```

### Text-to-Speech

TTS bypasses the queue for instant response:

```mermaid
sequenceDiagram
    participant C as Client
    participant F as Flask
    participant P as Piper TTS
    participant V as Voice Cache

    C->>+F: POST /api/tts/generate
    F->>F: Validate text & voice
    F->>V: Get voice model
    alt Not in cache
        V->>V: Load from disk
        V->>V: Add to LRU cache
    end
    V-->>F: Voice model
    F->>P: Synthesize
    P-->>F: Audio bytes
    F->>F: Save to generated/
    F-->>-C: {audio_url}
```

---

## Priority Queue System

Jobs are processed based on subscription tier with model affinity optimization.

```mermaid
graph TD
    subgraph "Priority Levels"
        P0[0: Admin]
        P1[1: Creator - $20/mo]
        P2[2: Premium - $10/mo]
        P3[3: Supporter - $5/mo]
        P4[4: Free]
    end

    subgraph "Queue Worker Logic"
        A{Same model<br/>as current?}
        A -->|Yes| B[Process immediately<br/>batch up to 3]
        A -->|No| C{Starving jobs?<br/>>60s wait}
        C -->|Yes| D[Force model switch]
        C -->|No| E[Continue batching]
    end

    P0 --> A
    P1 --> A
    P2 --> A
    P3 --> A
    P4 --> A
```

### Model Affinity

The queue worker prefers jobs matching the currently-loaded model to avoid expensive model switches:

1. **Batch Processing** - Process up to 3 jobs of same model type
2. **Starvation Prevention** - Force switch after 60s of same-model jobs
3. **Priority Override** - Higher priority always wins within batch

### Queue Skip (Aura)

Users can pay Aura (in-app currency) to skip the queue:

| Duration | Cost |
|----------|------|
| 1-10s | 1 Aura |
| 11-30s | 3 Aura |
| 31-60s | 5 Aura |
| 61-120s | 10 Aura |
| 121s+ | 15 Aura |

---

## AI Models

### Model Specifications

| Model | Type | VRAM | Use Case |
|-------|------|------|----------|
| MusicGen | Music | 4GB | Background music, melodies, loops |
| AudioGen | SFX | 5GB | Sound effects, ambience, nature |
| MAGNeT | Experimental | 6GB | Alternative generation algorithm |
| Piper TTS | Speech | 0.5GB | Voiceovers, narration |

### On-Demand Loading

Models are loaded only when needed to conserve GPU memory:

```mermaid
stateDiagram-v2
    [*] --> unloaded: Startup
    unloaded --> loading: Job arrives
    loading --> ready: Load complete
    ready --> generating: Start job
    generating --> ready: Job complete
    ready --> unloading: Memory pressure
    unloading --> unloaded: Unload complete
```

- **Preloading** - AudioGen preloaded if 5GB+ free VRAM
- **Idle Timeout** - Models unloaded after extended inactivity
- **Memory Check** - Uses nvidia-smi to detect other GPU consumers (e.g., Ollama)

### Quality Analysis

Generated audio is analyzed before saving:

```
Quality checks performed:
1. Clipping detection (>5% samples near +/-1.0)
2. Silence detection (RMS < 0.005)
3. High-frequency noise (>14kHz energy ratio)
4. Spectral flatness (pure noise detection)

Score 0-100, retry if score < 50
```

---

## Database Schema

```mermaid
erDiagram
    generations ||--o{ votes : has
    generations ||--o{ favorites : has
    generations ||--o{ playlist_tracks : in
    generations ||--o{ tag_suggestions : has
    generations ||--o{ play_events : tracks
    playlists ||--o{ playlist_tracks : contains

    generations {
        text id PK
        text filename UK
        text prompt
        text model
        int duration
        json category
        text user_id
        bool is_public
        int upvotes
        int downvotes
        int plays
        timestamp created_at
    }

    votes {
        int id PK
        text generation_id FK
        text user_id
        int vote
        json feedback_reasons
        timestamp created_at
    }

    playlists {
        text id PK
        text user_id
        text name
        text description
        timestamp created_at
    }

    favorites {
        int id PK
        text user_id
        text generation_id FK
        timestamp created_at
    }
```

### Full-Text Search

FTS5 virtual table for fast prompt searching:

```sql
-- Virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS generations_fts
USING fts5(prompt, content=generations, content_rowid=rowid);

-- Triggers keep FTS in sync with main table
```

### Category System

Auto-categorization based on prompt keywords:

- **Music Categories** - 50+ categories (genres, moods, instruments)
- **SFX Categories** - 30+ categories (UI, actions, environment)
- **Speech Categories** - Voice characteristics, languages

---

## File Structure

```
app-soundbox/
├── app.py              # Flask server, routes, queue worker
├── database.py         # SQLite layer, FTS5, categories
├── backup.py           # Automated backup system
├── voice_licenses.py   # TTS voice attribution data
├── requirements.txt    # Python dependencies
├── .env                # Configuration (not in repo)
│
├── templates/
│   └── index.html      # Main SPA (4,000+ lines)
│
├── static/js/
│   ├── radio-widget.js       # Embeddable player entry
│   ├── radio-widget-core.js  # Player logic
│   ├── radio-widget-visualizer.js
│   └── visualizations/       # Canvas visualizers
│       ├── bars.js
│       ├── wave.js
│       ├── circle.js
│       └── ...
│
├── models/voices/      # Piper TTS voice models (~2GB)
│   ├── en_US-lessac-medium.onnx
│   └── ...
│
├── generated/          # Output audio files (WAV)
├── spectrograms/       # Waveform images (PNG)
├── soundbox.db         # SQLite database
│
└── docs/               # This documentation
```

---

## Security

### Input Validation

- **Prompt Sanitization** - Length limits, character filtering
- **FTS5 Query Sanitization** - Prevents query injection
- **Path Traversal Prevention** - Filename validation

### Rate Limiting

Per-tier limits enforced by Flask-Limiter:

| Tier | Generations/Hour | Max Duration |
|------|------------------|--------------|
| Creator | 60 | 180s |
| Premium | 30 | 120s |
| Supporter | 15 | 60s |
| Free | 3 | 30s |

### Headers

Security headers applied to all responses:

```
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: [configured for app needs]
```

---

## External Dependencies

### Authentication (Valnet)

Token validation against external auth service:

```mermaid
sequenceDiagram
    participant C as Client
    participant S as Sound Box
    participant V as Valnet Auth

    C->>S: Request with Bearer token
    S->>V: GET /api/user/me
    V-->>S: {user_id, tier, permissions}
    S->>S: Cache user for request
```

### Graphlings Integration

Optional integration for platform-specific features:

- **User Profiles** - Link generations to Graphlings accounts
- **Aura Payments** - Virtual currency for queue skipping
- **Source Attribution** - Track which platform requested generation

---

## Performance Considerations

### GPU Memory Management

- Check system-wide free memory before loading models
- Unload idle models when memory pressure detected
- Skip preloading if other GPU consumers present (Ollama, etc.)

### Database

- Indexed columns for common queries
- FTS5 for fast text search (no LIKE scans)
- WAL mode for concurrent reads during writes

### Caching

- Voice models cached with LRU eviction (max 10)
- User auth cached per-request (not globally)
- Rate limit state stored in-memory

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Single-File Frontend** | No build step, simpler deployment, fast iteration |
| **SQLite + FTS5** | Built-in full-text search, no external dependencies |
| **Priority Queue** | Fair processing with tier-based prioritization |
| **Auto-Retry on Poor Quality** | Prevents bad generations from polluting library |
| **Crowdsourced Categorization** | Community improves metadata, consensus required |
| **Private Feedback** | No public comments, maintains quality discussion |
| **On-Demand Model Loading** | Conserves GPU memory when not actively generating |

---

## See Also

- [Queue System](systems/queue-system.md) - Priority scheduling deep dive
- [Audio Generation](systems/audio-generation.md) - Model details, quality analysis
- [Database](systems/database.md) - Schema, categories, migrations
- [API Reference](api/README.md) - Complete endpoint documentation

---

[← Back to README](../README.md)
