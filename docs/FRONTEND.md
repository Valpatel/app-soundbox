# Sound Box Frontend

## Overview

Single-page application (SPA) built with vanilla JavaScript, no frameworks. All HTML, CSS, and JavaScript contained in `templates/index.html` (~8,000 lines).

## Application Structure

```
┌─────────────────────────────────────────────────────────────┐
│                       Navigation Tabs                        │
│   ┌────────┐  ┌─────────┐  ┌──────────┐  ┌───────────┐     │
│   │ Radio  │  │ Library │  │ Generate │  │ Favorites │     │
│   └────────┘  └─────────┘  └──────────┘  └───────────┘     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                     Tab Content Area                        │
│   - Radio: Station presets, player, now playing            │
│   - Library: Grid/list view, search, filters, pagination   │
│   - Generate: Prompt input, model select, duration slider  │
│   - Favorites: User's saved tracks                         │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                    Fixed Footer (Radio Tab)                 │
│   ┌─────────┐  ┌───────────────────┐  ┌─────────────────┐  │
│   │ Controls│  │ Progress/Waveform │  │ Vote/Fav/Tag    │  │
│   └─────────┘  └───────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## State Variables

### Core Application State

```javascript
let currentTab = 'radio';       // Active tab: 'radio', 'library', 'generate', 'favorites'
let currentModel = 'music';     // Model type: 'music' or 'audio'
let modelStatus = {             // Model loading status
  music: 'pending',             // 'pending', 'loading', 'ready', 'error'
  audio: 'pending'
};
let modelsReady = false;        // True when at least one model is ready
let currentUserId = null;       // Graphlings user ID (if authenticated)
let isAdultAccount = false;     // Content filter flag
```

### Generation State

```javascript
let currentJobId = null;        // Active generation job ID
let modelPrompts = {            // Per-model prompt memory
  music: '',
  audio: ''
};
```

### Radio Player State

```javascript
let radioQueue = [];            // Upcoming tracks
let currentRadioTrack = null;   // Currently playing track object
let playHistory = [];           // Track IDs to avoid repeats
let recentlyPlayed = [];        // Full track objects for "previous"
let isFetchingMore = false;     // Prevent duplicate fetches
let currentRadioVote = 0;       // User's vote on current track (-1, 0, 1)
let isCurrentTrackFavorited = false;
let currentStation = null;      // Radio station preset (e.g., 'shuffle', 'top-rated')
```

### Library State

```javascript
let libraryPage = 1;            // Current page number
let libraryTotal = 0;           // Total items
let libraryPages = 1;           // Total pages
let userVotes = {};             // Map of generation_id -> vote value
let userFavorites = new Set();  // Set of favorited generation IDs
let libraryItemsData = {};      // Cache of library items by ID
let libraryViewMode = 'list';   // 'list' or 'grid'
let currentCategory = '';       // Active category filter
let currentTypeTab = 'all';     // 'all', 'music', or 'audio'
let currentQuickFilter = '';    // Quick filter preset
let searchDebounceTimer = null; // Debounce for search input
```

### Feedback/Modal State

```javascript
let feedbackModalState = {
  genId: null,
  vote: 0,
  reasons: [],
  notes: '',
  suggestedModel: null
};
```

## Key Functions

### Tab Navigation

- `switchTab(tabName)` - Switch between main tabs
- `localStorage.getItem('soundbox_tab')` - Persists active tab

### Generation

- `generate()` - Submit generation request
- `pollJobStatus()` - Poll for job completion
- `selectModel(model)` - Switch between music/audio
- `setPrompt(text)` - Set prompt from example

### Radio Player

- `initRadioPlayer()` - Initialize audio player
- `playTrack(track)` - Start playing a track
- `playNextTrack()` - Skip to next track
- `playPreviousTrack()` - Play previous track
- `loadMoreTracks()` - Fetch more tracks from API
- `selectStation(station)` - Switch radio station

### Library

- `loadLibrary(resetPage)` - Fetch library items
- `renderLibraryItems(items)` - Render item list
- `renderPagination()` - Generate pagination controls
- `applyQuickFilter(filter)` - Apply preset filters

### Voting & Favorites

- `vote(genId, value)` - Submit vote (-1, 0, 1)
- `toggleFavorite(genId)` - Add/remove favorite
- `showFeedbackModal(genId, currentVote)` - Open feedback form

### Tag Suggestions

- `showTagSuggestionModal(item)` - Open tag suggestion form
- `submitTagSuggestion()` - Submit category suggestion
- `tagCurrentTrack()` - Tag radio track

### Utilities

- `showFeedbackToast(message, type)` - Show toast notification
- `showErrorToast(message)` - Show error toast
- `escapeHtml(text)` - Escape HTML for safe display
- `getEffectiveUserId()` - Get user or device ID
- `getDeviceId()` - Get/create persistent device ID

## CSS Theming

### Color Variables

```css
:root {
  /* Backgrounds */
  --bg-dark: #0a0e17;           /* Main background */
  --bg-card: #111827;           /* Card background */
  --bg-input: #0d1117;          /* Input background */

  /* Accent Colors */
  --accent: #a855f7;            /* Primary purple */
  --accent-glow: rgba(168, 85, 247, 0.4);
  --cyan: #00d4ff;              /* Secondary cyan */
  --cyan-glow: rgba(0, 212, 255, 0.3);

  /* Text */
  --text-dim: #94a3b8;          /* Secondary text */
  --text-muted: #64748b;        /* Muted text */

  /* Borders */
  --border: rgba(255, 255, 255, 0.1);
  --border-hover: rgba(255, 255, 255, 0.15);

  /* Gradients */
  --gradient-accent: linear-gradient(135deg, #a855f7 0%, #6366f1 100%);
  --gradient-cyan: linear-gradient(135deg, #00d4ff 0%, #0ea5e9 100%);
}
```

## Event Flow

### Generation Flow

```
User clicks Generate
    ↓
generate() called
    ↓
POST /generate with prompt, duration, model, loop, priority
    ↓
Receive job_id
    ↓
pollJobStatus() every 500ms
    ↓
On completion: play audio, show spectrogram
```

### Radio Playback Flow

```
User selects station
    ↓
selectStation() calls API (e.g., /api/radio/shuffle)
    ↓
Populate radioQueue with tracks
    ↓
playTrack() starts first track
    ↓
On track end: playNextTrack()
    ↓
When queue < 3: loadMoreTracks()
```

### Voting Flow

```
User clicks upvote/downvote
    ↓
vote(genId, value) called
    ↓
If downvote: showFeedbackModal()
    ↓
POST /api/library/{id}/vote
    ↓
Update UI with new counts
```

## Local Storage

| Key | Purpose |
|-----|---------|
| `soundbox_tab` | Remember active tab |
| `soundbox_device_id` | Unique device identifier |
| `soundbox_view_mode` | Library view preference (list/grid) |

## Integration Points

### Graphlings Authentication

The app integrates with Graphlings.net for optional user authentication:

```javascript
// Listen for auth events from Graphlings widget
window.addEventListener('graphlings-user', (e) => {
  currentUserId = e.detail.userId;
  isAdultAccount = e.detail.isAdult;
});
```

### Audio Playback

Uses HTML5 Audio API with custom controls:

```javascript
const audioEl = document.getElementById('audio');
audioEl.play();
audioEl.pause();
audioEl.currentTime = 0;
```

## Responsive Breakpoints

```css
@media (max-width: 768px)  { /* Mobile: single column */ }
@media (max-width: 480px)  { /* Small mobile: compact UI */ }
```

## Performance Notes

- Library items cached in `libraryItemsData` object
- Votes batch-fetched to minimize API calls
- Search input debounced (300ms delay)
- Radio queue pre-fetches tracks to avoid gaps
- Spectrogram images lazy-loaded on hover
