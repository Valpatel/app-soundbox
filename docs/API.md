# Sound Box API Reference

**Base URL:** `http://localhost:5309`

## Generation Endpoints

### POST /generate
Submit an audio generation request.

**Request Body:**
```json
{
  "prompt": "peaceful ambient piano melody",
  "duration": 15,
  "model": "music",
  "loop": false,
  "priority": "standard",
  "user_id": "user_abc123"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| prompt | string | Yes | - | Text description of desired audio |
| duration | int | No | 8 | Length in seconds (1-120) |
| model | string | No | "music" | "music" or "audio" |
| loop | bool | No | false | Create seamless loop |
| priority | string | No | "standard" | "admin", "premium", "standard", or "free" |
| user_id | string | No | - | User identifier |

**Response:**
```json
{
  "success": true,
  "job_id": "abc123def456",
  "position": 3
}
```

---

### GET /job/{job_id}
Poll for job status and progress.

**Response (in progress):**
```json
{
  "id": "abc123def456",
  "status": "processing",
  "progress": "Generating audio...",
  "progress_pct": 65,
  "position": 0,
  "retry_count": 0
}
```

**Response (completed):**
```json
{
  "id": "abc123def456",
  "status": "completed",
  "progress": "Complete",
  "progress_pct": 100,
  "filename": "abc123def456.wav",
  "spectrogram": "abc123def456.png",
  "quality": 85,
  "position": 0,
  "retry_count": 0
}
```

**Response (failed):**
```json
{
  "id": "abc123def456",
  "status": "failed",
  "error": "Generation failed: CUDA out of memory",
  "retry_count": 2
}
```

**Status Values:** `queued`, `processing`, `completed`, `failed`

---

### GET /status
Get system status including model loading state and GPU info.

**Response:**
```json
{
  "models": {
    "music": "ready",
    "audio": "ready",
    "magnet-music": "pending",
    "magnet-audio": "pending"
  },
  "gpu": {
    "name": "NVIDIA GeForce RTX 4090",
    "available": true,
    "busy": false,
    "memory_used_gb": 6.39,
    "memory_total_gb": 23.51,
    "memory_percent": 27.2
  },
  "queue_length": 0,
  "estimated_wait": 0.0
}
```

**Model Status Values:** `pending`, `loading`, `ready`, `error`

---

### GET /queue-status
Get current queue state with job previews.

**Response:**
```json
{
  "queue_length": 2,
  "current_job": "def456",
  "jobs": [
    {
      "id": "abc123",
      "status": "queued",
      "prompt": "epic orchestral...",
      "priority": "standard",
      "position": 1
    },
    {
      "id": "def456",
      "status": "processing",
      "prompt": "thunder sound effect...",
      "priority": "premium",
      "position": 0
    }
  ]
}
```

---

### GET /api/queue
Get detailed queue status with all job information for queue explorer UI.

**Response:**
```json
{
  "jobs": [
    {
      "id": "abc123",
      "status": "processing",
      "prompt": "epic orchestral music with dramatic...",
      "model": "music",
      "duration": 15,
      "priority": "premium",
      "created": "2025-12-25T10:30:00",
      "progress": "Generating audio...",
      "progress_pct": 45,
      "user_id": "user_xyz",
      "position": 1
    }
  ],
  "current_job": "abc123",
  "total": 1
}
```

---

### POST /api/queue/{job_id}/cancel
Cancel a queued job (before processing starts).

**Request Body:**
```json
{
  "user_id": "user_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Job cancelled"
}
```

---

## Library Endpoints

### GET /api/library
Get paginated library with filtering and search.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page (max 100) |
| model | string | - | Filter: "music" or "audio" |
| search | string | - | Full-text search query |
| sort | string | "recent" | "recent", "popular", "rating" |
| category | string | - | Filter by category |
| user_id | string | - | Filter by creator |

**Response:**
```json
{
  "items": [
    {
      "id": "abc123",
      "filename": "abc123.wav",
      "prompt": "peaceful ambient melody",
      "model": "music",
      "duration": 15,
      "is_loop": 0,
      "quality_score": 85,
      "spectrogram": "abc123.png",
      "upvotes": 12,
      "downvotes": 1,
      "category": "[\"ambient\", \"peaceful\"]",
      "user_id": "user_xyz",
      "created_at": "2025-12-25 10:30:00"
    }
  ],
  "total": 5239,
  "page": 1,
  "pages": 262,
  "per_page": 20
}
```

**Note:** The `category` field is returned as a JSON-encoded string, not a parsed array. The `is_loop` field is returned as integer (0 or 1).

---

### GET /api/library/{gen_id}
Get single generation details.

**Response:**
```json
{
  "id": "abc123",
  "filename": "abc123.wav",
  "prompt": "peaceful ambient melody",
  "model": "music",
  "duration": 15,
  "is_loop": 0,
  "quality_score": 85,
  "spectrogram": "abc123.png",
  "upvotes": 12,
  "downvotes": 1,
  "category": "[\"ambient\", \"peaceful\"]",
  "user_id": "user_xyz",
  "created_at": "2025-12-25 10:30:00"
}
```

---

### GET /api/library/counts
Get total counts by model type.

**Response:**
```json
{
  "total": 5239,
  "music": 1249,
  "audio": 3990
}
```

---

### GET /api/library/category-counts
Get counts per category.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| model | string | Filter: "music" or "audio" |

**Response:**
```json
{
  "ambient": 245,
  "electronic": 312,
  "piano": 89,
  "notification": 156,
  "explosion": 78
}
```

---

### POST /api/library/{gen_id}/vote
Cast or update a vote with optional feedback.

**Request Body:**
```json
{
  "vote": 1,
  "user_id": "user_abc123",
  "feedback_reasons": ["great_quality", "creative_prompt"],
  "notes": "Perfect for my game project",
  "suggested_model": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| vote | int | -1 (down), 0 (remove), 1 (up) |
| user_id | string | Voter identifier |
| feedback_reasons | array | Optional feedback tags |
| notes | string | Private notes (not public) |
| suggested_model | string | Reclassification suggestion |

**Response:**
```json
{
  "success": true,
  "upvotes": 13,
  "downvotes": 1
}
```

---

### POST /api/library/votes
Batch get user's votes for multiple generations.

**Request Body:**
```json
{
  "user_id": "user_abc123",
  "generation_ids": ["abc123", "def456", "ghi789"]
}
```

**Response:**
```json
{
  "abc123": 1,
  "def456": -1,
  "ghi789": 0
}
```

---

### GET /api/library/{gen_id}/feedback
Get aggregated feedback for a generation.

**Response:**
```json
{
  "positive_reasons": {
    "great_quality": 5,
    "creative_prompt": 3
  },
  "negative_reasons": {
    "too_short": 1
  },
  "total_votes": 9
}
```

---

## Radio Endpoints

### GET /api/radio/shuffle
Get random tracks for radio playback.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| model | string | - | Filter: "music" or "audio" |
| search | string | - | Keyword filter |
| count | int | 10 | Number of tracks |

**Response:**
```json
{
  "tracks": [
    {
      "id": "abc123",
      "filename": "abc123.wav",
      "prompt": "upbeat electronic",
      "duration": 30
    }
  ]
}
```

---

### GET /api/radio/next
Get next track for continuous playback (excludes recent).

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| model | string | Filter by model |
| exclude | string | Comma-separated IDs to skip |

---

### GET /api/radio/favorites
Shuffle play user's favorites.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| user_id | string | User identifier |
| count | int | Number of tracks |

---

### GET /api/radio/top-rated
Get top-rated tracks by vote differential.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| model | string | - | Filter by model |
| count | int | 20 | Number of tracks |

---

### GET /api/radio/new
Get recently created tracks.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| model | string | - | Filter by model |
| hours | int | 168 | Lookback period in hours (168 = 7 days) |
| count | int | 10 | Number of tracks (max 50) |

---

## Favorites Endpoints

### POST /api/favorites/{gen_id}
Add generation to favorites.

**Request Body:**
```json
{
  "user_id": "user_abc123"
}
```

**Response:**
```json
{
  "success": true
}
```

---

### DELETE /api/favorites/{gen_id}
Remove from favorites.

**Request Body:**
```json
{
  "user_id": "user_abc123"
}
```

---

### GET /api/favorites
Get user's favorites with pagination.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| user_id | string | User identifier |
| page | int | Page number |
| per_page | int | Items per page |
| model | string | Filter by model |

---

### POST /api/favorites/check
Batch check which generations are favorited.

**Request Body:**
```json
{
  "user_id": "user_abc123",
  "generation_ids": ["abc123", "def456"]
}
```

**Response:**
```json
{
  "abc123": true,
  "def456": false
}
```

---

## Tag Suggestion Endpoints

### POST /api/library/{gen_id}/suggest-tag
Suggest a category for a generation.

**Request Body:**
```json
{
  "category": "ambient",
  "user_id": "user_abc123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Suggestion recorded. 2/3 users have suggested this category.",
  "current_votes": 2,
  "threshold": 3,
  "consensus_reached": false
}
```

When consensus is reached (3+ votes):
```json
{
  "success": true,
  "message": "Category applied! Consensus reached.",
  "consensus_reached": true
}
```

---

### GET /api/library/{gen_id}/tag-suggestions
Get all tag suggestions for a generation.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| user_id | string | To check user's own suggestions |

**Response:**
```json
{
  "suggestions": {
    "ambient": 2,
    "peaceful": 1
  },
  "user_suggestions": ["ambient"],
  "current_categories": ["electronic"],
  "threshold": 3
}
```

---

### GET /api/categories/{model}
Get all available categories for a model type.

**Response:**
```json
{
  "categories": {
    "ambient": "Ambient",
    "electronic": "Electronic",
    "piano": "Piano",
    "cinematic": "Cinematic"
  }
}
```

---

## Utility Endpoints

### GET /audio/{filename}
Serve generated audio file.

**Response:** Audio file (WAV format)

---

### GET /spectrogram/{filename}
Serve spectrogram image.

**Response:** Image file (PNG format)

---

### GET /download/{filename}
Download audio with clean filename.

**Response:** Audio file with prompt-based filename (e.g., `peaceful-ambient-melody_abc123.wav`)

---

### GET /generate-spectrogram/{audio_filename}
Generate spectrogram on demand for an existing audio file.

**Response:**
```json
{
  "spectrogram": "abc123.png"
}
```

**Errors:**
- `404` - Audio file not found
- `500` - Spectrogram generation failed

---

### GET /history
Get file-based generation history (legacy endpoint, prefer /api/library).

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| model | string | Filter: "music" or "audio" |
| user_id | string | Filter by creator |

**Response:**
```json
[
  {
    "filename": "abc123.wav",
    "prompt": "peaceful ambient melody",
    "model": "music",
    "duration": 15,
    "loop": false,
    "rating": 4,
    "created": "2025-12-25T10:30:00",
    "quality_score": 85,
    "quality_issues": [],
    "spectrogram": "abc123.png",
    "user_id": "user_xyz"
  }
]
```

---

### POST /rate
Rate a generation (legacy endpoint, prefer /api/library/{gen_id}/vote).

**Request Body:**
```json
{
  "filename": "abc123.wav",
  "rating": 4
}
```

**Response:**
```json
{
  "success": true
}
```

---

### POST /random-prompt
Generate a creative random prompt.

**Request Body:**
```json
{
  "model": "music"
}
```

**Response:**
```json
{
  "prompt": "upbeat synthwave with retro 80s vibes and pulsing bass"
}
```

---

### POST /api/log-error
Log client-side errors to backend.

**Request Body:**
```json
{
  "message": "Audio playback failed",
  "stack": "Error at line 123...",
  "url": "/api/radio/shuffle"
}
```

---

### GET /api/stats
Get database statistics.

**Response:**
```json
{
  "total_generations": 5239,
  "total_votes": 1523,
  "total_favorites": 342,
  "categories": {
    "music": 77,
    "audio": 52
  }
}
```

---

## Error Responses

All endpoints return errors in this format:

```json
{
  "error": "Error message description"
}
```

**HTTP Status Codes:**
- `200` - Success
- `400` - Bad request (invalid parameters)
- `404` - Resource not found
- `500` - Server error
