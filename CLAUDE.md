# Claude Code Notes - Sound Box

## Important Reminders

- **ALWAYS use `./start.sh`** to start the server - it uses the venv with all dependencies
- **Don't try `python app.py`** directly - it won't have torch/audiocraft installed
- Theme colors: **purple (#a855f7)** as primary accent, **cyan (#00d4ff)** as secondary - NO orange
- Server runs on: **http://localhost:5309**

## Quick Start

```bash
./setup.sh          # Initial setup (requires sudo) - multi-platform
./start.sh          # Start server (uses venv)
./service.sh install # Systemd service (auto-start on boot)
./service.sh uninstall # Remove service
npm test            # Run Playwright tests
```

## App Overview

Sound Box is an AI audio generation app powered by Meta's MusicGen and AudioGen models. Users can:
- Generate music and sound effects from text prompts
- Listen to community-generated audio via radio stations
- Vote, favorite, and review tracks
- Create playlists (in progress)

### Authentication / Open Access Mode

- **Default: OPEN_ACCESS_MODE=true** - no login required, anyone can generate/vote/favorite
- Anonymous users get IP-based identity (`anon_` + SHA256(IP)[:12])
- Rate limits enforced per-IP; localhost always exempt
- `IP_WHITELIST` env var for elevated (creator-tier) limits
- Original Graphlings auth code preserved but disabled (set OPEN_ACCESS_MODE=false to re-enable)
- `var OPEN_ACCESS_MODE` in frontend (not const!) for cross-script-block access
- Auth state managed via `currentUserId` and `isUserAuthenticated()`

### Supported Platforms

- **x86_64 Desktop** (RTX 3000/4000/5000) - full support
- **ARM64 Jetson Orin AGX** - GPU CUDA wheels, xformers stub
- **ARM64 DGX Grace / GB10** (Blackwell sm_121) - requires NVRTC 13.0 fix (automated in setup.sh)
- CPU fallback for systems without GPU (much slower)

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
├── app.py                    # Flask server, AI generation endpoints (~4700 lines)
├── database.py               # SQLite operations, FTS5 search
├── start.sh                  # Server startup script (uses venv)
├── setup.sh                  # Multi-platform setup (x86_64/ARM64/Jetson/DGX)
├── service.sh                # Systemd service management (install/uninstall/etc)
├── .env                      # Configuration (OPEN_ACCESS_MODE, IP_WHITELIST, etc)
├── .env.example              # Template for .env
├── venv/                     # Python virtualenv (torch, audiocraft, flask)
├── soundbox.db               # SQLite database
├── templates/
│   └── index.html            # Main SPA template (~15k lines)
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
    ├── open-access.spec.js   # Open access mode + API tests
    ├── *.spec.js             # 19 Playwright test suites (250+ tests)
    └── utils/test-helpers.js  # Shared test utilities
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

### Feb 14, 2026
- **Open Access Mode**: Disabled all login requirements, anonymous users from IP hash
- **Multi-platform setup.sh**: Auto-detects x86_64/ARM64, GPU type, installs correct PyTorch
- **NVRTC Blackwell fix**: Replaces PyTorch's bundled NVRTC 12.8 with system CUDA 13.0 for GB10 sm_121
- **xformers stub**: Provides torch fallbacks for `ops.unbind` and `ops.memory_efficient_attention`
- **Systemd service**: `service.sh` for install/uninstall/enable/disable/start/stop/restart
- **Node.js + Playwright**: Auto-installed in setup.sh, `npm test` works
- **Open access tests**: 14 new tests including end-to-end generation flow
- **Rate limits**: Free tier bumped to 10/hr, 60s max; creator tier for whitelisted IPs

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
