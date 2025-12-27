# Claude Code Notes - Sound Box

## Important Reminders

- **ALWAYS use `./start.sh`** to start the server - it uses the venv with all dependencies
- **Don't try `python app.py`** directly - it won't have torch/audiocraft installed
- Theme colors: **purple (#a855f7)** as primary accent, **cyan (#00d4ff)** as secondary - NO orange
- Server runs on: **http://localhost:5309**

## Quick Start

```bash
./start.sh          # Start server (uses venv)
./setup.sh          # Initial setup (requires sudo)
npx playwright test # Run tests
```

## App Overview

Sound Box is an AI audio generation app powered by Meta's MusicGen and AudioGen models. Users can:
- Generate music and sound effects from text prompts
- Listen to community-generated audio via radio stations
- Vote, favorite, and review tracks
- Create playlists (in progress)

### Authentication

- Integrates with Graphlings accounts (graphlings.net)
- Uses `@anthropic/claude-accounts-sdk` for auth
- Anonymous users get limited functionality (can listen, but not vote/generate)
- Auth state managed via `currentUserId` and `isUserAuthenticated()`

## App Tabs

### Radio Tab (`#content-radio`)
- **Station cards** - Click to start streaming (All Music, Ambient, Retro, Happy, Lo-Fi, Favorites)
- **Now Playing widget** - Large RadioWidget showing current track with visualizer
- **Vote/favorite buttons** - Rate tracks, add to favorites
- **Fullscreen mode** - Click expand for immersive visualizer experience

### Library Tab (`#content-library`)
- Browse all generated audio
- Search with FTS5 full-text search
- Filter by type (music/sound), sort options
- Play individual tracks
- Add to playlists

### Generate Tab (`#content-generate`)
- Text prompt input for generation
- Model selector (MusicGen for music, AudioGen for sounds)
- Duration selector
- Shows generation progress
- Requires authentication

### Playlist Tab (`#content-playlist`)
- Create and manage playlists
- View playlist contents
- Play entire playlists
- (Backend implementation in progress - see plan file)

### API Tab (`#content-api`)
- Documentation for embedding widgets
- Live widget demos at different sizes
- Code snippets for integration

## Widget Architecture

### RadioWidget (`static/js/radio-widget.js`)
Factory that creates widget instances. Entry point for all widgets.

```javascript
// Create a widget
const widget = RadioWidget.create('#container', {
    size: 'medium',      // minimal, small, medium, large, fullscreen
    template: 'default',
    apiBaseUrl: '',
    userId: null,
    autoPlay: false,
    connectToExisting: true  // Share audio with other widgets
});
```

**Size modes:**
- **minimal** (320x70) - Compact bar: play, skip, track info, vote buttons
- **small** (320x80) - Grid layout with progress bar
- **medium** (420x140) - Full controls with small visualizer background
- **large** (600x200) - Prominent track info, all controls, visualizer
- **fullscreen** - Immersive mode with full visualizer, auto-dim UI

### RadioWidgetCore (`static/js/radio-widget-core.js`)
Shared singleton managing actual playback state. All widgets connect to same core.

**Key responsibilities:**
- Audio element management
- Queue/playlist management
- Track loading from API
- Volume/mute state (persisted to localStorage)
- Event emission for UI updates

**Events emitted:**
- `trackChange` - New track playing
- `playStateChange` - Play/pause toggled
- `queueUpdate` - Queue modified
- `volumeChange` - Volume level changed
- `muteChange` - Mute toggled
- `timeUpdate` - Playback progress
- `vote` - Vote registered
- `favorite` - Favorite toggled

### RadioWidgetVisualizer (`static/js/radio-widget-visualizer.js`)
Canvas-based audio visualizations for fullscreen mode.

**Modes:** bars, wave, circle, particles, lissajous, tempest, pong, breakout, snake, random

**Features:**
- Web Audio API analyzer integration
- Auto-adjusting complexity based on FPS
- Color themes (purple, blue, green, cyan, pink, rainbow)

### Mini-Player (`#mini-player`)
Persistent player shown at bottom when on non-Radio tabs while audio is playing.
- Play/pause, skip, expand/collapse
- Quick vote buttons
- Links back to Radio tab

## File Structure

```
app-soundbox/
├── app.py                    # Flask server, AI generation endpoints
├── database.py               # SQLite operations, FTS5 search
├── start.sh                  # Server startup script
├── setup.sh                  # Initial setup
├── venv/                     # Python virtualenv (torch, audiocraft, flask)
├── soundbox.db               # SQLite database
├── templates/
│   └── index.html            # Main SPA template (12k+ lines)
├── static/
│   ├── js/
│   │   ├── radio-widget.js           # Widget factory & UI rendering
│   │   ├── radio-widget-core.js      # Playback state management
│   │   ├── radio-widget-visualizer.js # Canvas visualizations
│   │   ├── radio-widget-events.js    # Event emitter utility
│   │   └── radio-widget-bridge.js    # Bridge for external embedding
│   ├── css/
│   │   ├── radio-widget.css          # Base widget styles
│   │   ├── radio-widget-sizes.css    # Size-specific layouts
│   │   ├── radio-widget-templates.css # Theme templates
│   │   └── radio-widget-fullscreen.css # Fullscreen mode styles
│   ├── graphlings/           # Branding assets (favicon, logo)
│   └── output/               # Generated audio files
└── tests/
    └── *.spec.js             # Playwright tests
```

## API Endpoints

### Audio
- `GET /api/radio/tracks` - Get tracks for radio (with search/filter)
- `GET /api/generation/<id>` - Get single track metadata
- `GET /stream/<filename>` - Stream audio file
- `GET /download/<filename>` - Download audio file

### Generation
- `POST /api/generate` - Generate new audio (requires auth)
- `GET /api/status/<task_id>` - Check generation status

### User Actions
- `POST /api/vote` - Vote on track
- `POST /api/favorite` - Toggle favorite
- `GET /api/favorites` - Get user's favorites

### Playlists (in progress)
- See plan file: `~/.claude/plans/immutable-soaring-hollerith.md`

## Database Schema

**generations** - All generated audio
- id, prompt, model, duration, filename, created_at
- upvotes, downvotes, play_count
- user_id, tags

**favorites** - User favorites
- user_id, generation_id, created_at

**votes** - User votes
- user_id, generation_id, vote_value, created_at

## CSS Theme Variables

```css
:root {
    --bg-dark: #0a0e17;
    --bg-card: #111827;
    --accent: #a855f7;      /* Primary purple */
    --cyan: #00d4ff;        /* Secondary cyan */
    --text: #f1f5f9;
    --text-muted: #64748b;
    --success: #10b981;
    --error: #ef4444;
}
```

## Fullscreen Mode Features

- **Auto-dim UI** - Controls fade after 4s inactivity, reappear on interaction
- **Visualization modes** - 10 different visualizers (bars, wave, particles, games, etc.)
- **Color themes** - 6 color schemes
- **FPS counter** - Performance monitoring (green/yellow/red)
- **Keyboard shortcuts** - Space (play), arrows (skip/volume), Esc (exit), M (mute)

## State Persistence

Saved to localStorage:
- `soundbox_volume` - Volume level (0.0-1.0)
- `soundbox_muted` - Mute state (true/false)
- `soundbox_anon_id` - Anonymous user ID for non-auth users

## Recent Changes

### Dec 27, 2025
- **Responsive UI overhaul:**
  - Mobile tab dropdown for screens < 480px
  - Browse Categories modal with red X close button
  - Compact CC0 license widget on mobile
  - Simplified two-phase layout (900px breakpoint)
  - Vertical Music/SFX filter tabs
- Theme consistency: changed library cyan accents to purple
- No-cache headers for development
- Synced mute buttons between mobile/desktop

### Dec 2025 (Earlier)
- Theme standardization: removed orange, using purple/cyan
- Fullscreen auto-dim UI after inactivity
- Fixed volume/mute state not reflecting in UI on page load
- Added tooltips to all widget buttons
- Mini-player button alignment fix
- Graphlings favicon (local assets)
