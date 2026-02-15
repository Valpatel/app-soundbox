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
- Rate limits enforced per-IP; localhost exempt except MCP-proxied requests
- `IP_WHITELIST` env var for elevated (creator-tier) limits
- Original Graphlings auth code preserved but disabled (set OPEN_ACCESS_MODE=false to re-enable)
- `var OPEN_ACCESS_MODE` in frontend (not const!) for cross-script-block access
- Auth state managed via `currentUserId` and `isUserAuthenticated()`

### MCP Security Model

- **X-MCP-Proxy detection** - MCP server sets `X-MCP-Proxy: true` header on all forwarded requests; Flask uses this to deny localhost privileges to MCP-proxied requests
- **Rate limiting** - MCP-proxied requests rate limited under shared `mcp-proxy` identity (not exempt like direct localhost)
- **SSE localhost binding** - SSE transport binds to `127.0.0.1` only; requires reverse proxy for network access
- **MCP_API_KEY** - Required for SSE transport authentication (Bearer token); stdio transport always trusted
- **Input validation** - All IDs validated against hex regex (`^[a-fA-F0-9]{8,64}$`), parameters clamped to safe ranges (duration 1-60, page 1-1000, etc.)
- **Manifest info redaction** - `/api/manifest` hides hostname, GPU model name, and MCP port; `/status` exposes full details

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
├── app.py                    # Flask server, AI generation endpoints (~4800 lines)
├── mcp_server.py             # MCP server for AI agent tool use (6 tools)
├── database.py               # SQLite operations, FTS5 search
├── start.sh                  # Server startup script (uses venv)
├── setup.sh                  # Multi-platform setup (x86_64/ARM64/Jetson/DGX)
├── service.sh                # Systemd service management (soundbox + MCP + mDNS)
├── .env                      # Configuration (OPEN_ACCESS_MODE, IP_WHITELIST, MCP_PORT, MCP_API_KEY, etc)
├── .env.example              # Template for .env
├── .mcp.json                 # Claude Code MCP auto-discovery (stdio transport)
├── venv/                     # Python virtualenv (torch, audiocraft, flask, mcp)
├── soundbox.db               # SQLite database
├── avahi/
│   └── soundbox.service      # mDNS LAN discovery (XML, installed by service.sh)
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
│   ├── openapi.json          # OpenAPI 3.1 spec (13 endpoints)
│   ├── graphlings/           # Branding assets (favicon, logo)
│   └── output/               # Generated audio files
├── tests/
│   ├── discovery.spec.js     # Service discovery tests (18 tests)
│   ├── open-access.spec.js   # Open access mode + API tests
│   ├── *.spec.js             # 19 Playwright test suites (250+ tests)
│   └── utils/test-helpers.js  # Shared test utilities
└── docs/                     # Full documentation (see docs/ hierarchy)
```

## API Endpoints

### Discovery
- `GET /api/manifest` - Service discovery hub (capabilities, endpoints, stats)
- `GET /.well-known/agent-card.json` - A2A agent discovery card
- `GET /openapi.json` - OpenAPI 3.1 specification

### Audio
- `GET /api/radio/shuffle` - Random tracks for radio
- `GET /api/library` - Search/browse audio library
- `GET /api/library/<id>` - Get single track metadata
- `GET /audio/<filename>` - Stream audio file
- `GET /download/<filename>` - Download audio file

### Generation
- `POST /generate` - Generate new audio
- `GET /job/<job_id>` - Check generation status
- `GET /status` - System status, GPU info, queue

### User Actions
- `POST /api/library/<id>/vote` - Vote on track
- `POST /api/favorites/<id>` - Toggle favorite
- `GET /api/favorites` - Get user's favorites

### MCP Tools (via mcp_server.py)
- `generate_audio` - Submit generation (optionally wait for completion)
- `check_job` - Poll job status
- `search_library` - Search/browse audio library
- `get_status` - System status, GPU info, queue
- `get_radio_track` - Random/curated tracks
- `download_audio` - Get download URL for a track

**Security:** MCP requests are proxied with `X-MCP-Proxy: true` header, so they don't receive localhost privileges. SSE transport requires `MCP_API_KEY`. All inputs validated and clamped.

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

### Feb 14, 2026 (Security Audit)
- **MCP proxy detection**: `X-MCP-Proxy: true` header prevents MCP-proxied requests from gaining localhost privileges
- **Rate limit fix**: MCP-proxied requests rate limited under `mcp-proxy` identity instead of being exempt
- **SSE localhost binding**: MCP SSE server binds to `127.0.0.1` only, not `0.0.0.0`
- **MCP_API_KEY**: Required for SSE transport authentication; SSE rejects all connections when unset
- **Input validation**: All MCP tool inputs validated — hex ID regex, parameter clamping (duration, pagination, counts)
- **Manifest redaction**: `/api/manifest` no longer exposes hostname, GPU model name, or MCP port

### Feb 14, 2026 (Service Discovery)
- **Service Discovery**: 5 complementary layers for different client types
  - `/api/manifest` - Universal discovery hub (capabilities, endpoints, stats)
  - `/.well-known/agent-card.json` - A2A agent protocol with 5 skills
  - `mcp_server.py` - MCP server with 6 tools (generate, search, status, etc.)
  - `/openapi.json` - OpenAPI 3.1 spec for 13 key endpoints
  - `avahi/soundbox.service` - mDNS LAN broadcast (`_soundbox._tcp`)
- **`.mcp.json`**: Claude Code auto-discovers MCP server via stdio
- **`service.sh`**: Now manages 3 services (soundbox + soundbox-mcp + Avahi mDNS)
- **Discovery tests**: 18 Playwright tests covering all discovery endpoints
- **Docs overhaul**: New `docs/systems/service-discovery.md`, updated all docs

### Feb 14, 2026 (Open Access)
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
