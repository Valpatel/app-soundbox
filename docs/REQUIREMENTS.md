# Sound Box - Feature Requirements & Business Logic

This document describes the key features, business rules, and configuration options for Sound Box.

## Table of Contents

1. [Subscription Tiers](#subscription-tiers)
2. [My Generations (Private Content)](#my-generations-private-content)
3. [Content Moderation](#content-moderation)
4. [Skip-the-Queue](#skip-the-queue)
5. [Smart GPU Scheduler](#smart-gpu-scheduler)
6. [Security & Rate Limiting](#security--rate-limiting)

---

## Subscription Tiers

Sound Box integrates with Valnet/Graphlings subscription system. All features scale by tier.

| Tier | Price | Generations/Hour | Max Duration | Storage | Aura/Month |
|------|-------|-----------------|--------------|---------|------------|
| Free | $0 | 3 | 30s | 20 | 0 |
| Supporter | $5/mo | 15 | 60s | 100 | 300 |
| Premium | $10/mo | 30 | 120s | 200 | 700 |
| Creator | $20/mo | 60 | 180s | 500 | 1500 |

### Configuration Location
- Limits: `app.py` → `GENERATION_LIMITS`
- Storage: `database.py` → `USER_STORAGE_LIMITS`
- Queue priority: `app.py` → `PRIORITY_LEVELS`

### Free Tier Requirements
- Email verification required before generating
- Limited to 2 pending jobs in queue
- Longest starvation timeout (30 min)

---

## My Generations (Private Content)

Users' generations are stored in a private "My Generations" section, organized by model type (Music, SFX, TTS).

### Key Business Rules

1. **All content is CC0 (public domain)** - Users must understand that good content may be added to the public library after admin review.

2. **Private by default** - New generations start with `is_public=FALSE` and require admin approval before appearing in the public library.

3. **Storage limits per tier** - When users exceed their storage limit, oldest non-favorited generations are auto-deleted.

4. **Favorites are protected** - Generations marked as favorites are NEVER auto-deleted.

5. **Download encouraged** - Users should download generations they want to keep long-term.

### Storage Warning Thresholds
- **80%**: Show warning in UI
- **100%**: Block new generations until cleanup or upgrade

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/my-generations` | Get user's private generations with storage info |
| `GET /api/my-generations/storage` | Get storage usage details |
| `POST /api/my-generations/cleanup` | Manually trigger cleanup of old content |

### Database Columns
```sql
generations.is_public BOOLEAN DEFAULT FALSE
generations.admin_reviewed BOOLEAN DEFAULT FALSE
```

---

## Content Moderation

Admin review workflow prevents inappropriate content from reaching the public library.

### Workflow

**User-generated content (remote requests):**
1. User generates content → `is_public=FALSE`, `admin_reviewed=FALSE`
2. Content appears in admin moderation queue
3. Admin reviews and takes action:
   - **Approve**: `is_public=TRUE`, appears in public library
   - **Reject**: `is_public=FALSE`, stays private, user keeps access
   - **Delete**: Content removed entirely (for severe violations)
4. Once reviewed: `admin_reviewed=TRUE`

**Localhost/Admin-generated content (trusted):**
1. Server-side batch generation or admin request → `is_public=TRUE`, `admin_reviewed=TRUE`
2. Content immediately appears in public library (no review needed)

This allows batch generation scripts (like kid-friendly SFX generation) to populate the library without manual review.

### Admin API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/admin/moderation` | Get pending review queue |
| `POST /api/admin/moderate/<id>` | Approve/reject/delete single item |
| `POST /api/admin/moderate/bulk` | Bulk moderation (max 50 items) |

### Access Control
- Requires `is_admin=true` flag on user object from Valnet auth

---

## Skip-the-Queue

Paying users can spend Aura (Valnet currency) to skip the queue for faster processing.

### Pricing by Duration

| Duration | Cost | Label |
|----------|------|-------|
| 1-10s | 1 Aura | Short SFX |
| 11-30s | 3 Aura | Medium clip |
| 31-60s | 5 Aura | Long SFX |
| 61-120s | 10 Aura | Song |
| 121s+ | 15 Aura | Long song |

### Configuration Location
`app.py` → `SKIP_QUEUE_PRICING` - Easy to tune list:
```python
SKIP_QUEUE_PRICING = [
    (10,  1,  "Short SFX"),      # 1-10s: 1 Aura
    (30,  3,  "Medium clip"),    # 11-30s: 3 Aura
    (60,  5,  "Long SFX"),       # 31-60s: 5 Aura
    (120, 10, "Song"),           # 61-120s: 10 Aura
    (999, 15, "Long song"),      # 121s+: 15 Aura
]
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/queue/skip-pricing` | Get pricing tiers for UI display |
| `POST /api/queue/<job_id>/skip` | Pay Aura to skip queue |

### Aura Transaction
Spending Aura calls Valnet's `/api/wallet/spend` endpoint with:
- `amount`: Aura cost
- `currency`: "aura"
- `app_id`: "soundbox"
- `item`: Description for transaction history

---

## Smart GPU Scheduler

Efficient GPU memory management for processing multiple model types.

### Model Memory Requirements
```python
MODEL_MEMORY_GB = {
    'music': 4.0,
    'audio': 5.0,
    'magnet-music': 6.0,
    'magnet-audio': 6.0,
    'tts': 0.5,
}
```

### Key Features

1. **On-demand loading** - Models load only when needed, unload when not in use
2. **Memory checking** - Uses `nvidia-smi` to check system-wide GPU memory
3. **Model affinity** - Batches jobs by model type to avoid constant switching
4. **Starvation prevention** - Tier-based timeouts ensure all jobs eventually process

### Starvation Timeouts by Tier

| Tier | Timeout |
|------|---------|
| Creator | 2 min |
| Premium | 5 min |
| Supporter | 10 min |
| Free | 30 min |

### Configuration Location
- Memory requirements: `app.py` → `MODEL_MEMORY_GB`
- Starvation timeouts: `app.py` → `_STARVATION_TIMEOUT_BY_TIER`
- Batch size: `app.py` → `_MAX_BATCH_SIZE` (default: 50)

---

## Security & Rate Limiting

### Authentication
- Bearer token authentication via Valnet accounts API
- Token cache with LRU eviction (max 1000 entries, 5 min TTL)
- No X-User-ID header bypass (removed for security)

### Rate Limits by Endpoint

| Endpoint | Limit |
|----------|-------|
| `/generate` | 60/hour |
| `/api/library` | 300/min |
| `/api/radio/shuffle` | 120/min |
| `/api/my-generations` | 120/min |
| `/api/admin/moderate` | 120/hour |
| `/api/queue/skip` | 30/hour |

### Input Validation
- Exclude list limited to 100 IDs
- Hours parameter capped at 8760 (1 year)
- FTS5 special characters escaped in search
- Generation IDs validated in batch operations

### Job Cleanup
- Background worker removes completed/failed jobs after 1 hour
- Prevents memory exhaustion from job metadata accumulation

---

## Configuration Quick Reference

| Setting | Location | Purpose |
|---------|----------|---------|
| `GENERATION_LIMITS` | app.py | Per-hour limits and max duration by tier |
| `USER_STORAGE_LIMITS` | database.py | Private storage quota by tier |
| `SKIP_QUEUE_PRICING` | app.py | Aura cost for queue skipping |
| `MODEL_MEMORY_GB` | app.py | GPU memory requirements per model |
| `_STARVATION_TIMEOUT_BY_TIER` | app.py | Queue timeout by subscription tier |
| `_MAX_BATCH_SIZE` | app.py | Jobs to process before switching models |
| `_TOKEN_CACHE_MAX_SIZE` | app.py | Max cached auth tokens |
| `_VOICE_CACHE_MAX_SIZE` | app.py | Max cached TTS voice models |

---

## API Response Examples

### My Generations Response
```json
{
  "items": [...],
  "total": 15,
  "page": 1,
  "pages": 1,
  "by_model": {
    "music": 8,
    "audio": 5,
    "voice": 2
  },
  "storage": {
    "used": 15,
    "limit": 100,
    "favorites": 3,
    "percent_used": 15.0,
    "near_limit": false,
    "at_limit": false
  },
  "license_notice": "All generations are CC0 (public domain)..."
}
```

### Skip Queue Pricing Response
```json
{
  "pricing": [
    {"max_duration": 10, "cost": 1, "label": "Short SFX"},
    {"max_duration": 30, "cost": 3, "label": "Medium clip"},
    ...
  ]
}
```
