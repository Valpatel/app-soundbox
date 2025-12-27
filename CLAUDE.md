# Claude Code Notes - Sound Box

## Quick Start

### Starting the Server
```bash
./start.sh
```
Or directly:
```bash
./venv/bin/python app.py
```

Server runs on: http://localhost:5309

### Initial Setup (requires sudo)
```bash
./setup.sh
```

## Project Structure

- **app.py** - Main Flask server (port 5309)
- **database.py** - SQLite database operations
- **venv/** - Python virtual environment with all dependencies (torch, audiocraft, flask, etc.)

## Key Files

### Frontend
- `templates/index.html` - Main HTML template
- `static/js/radio-widget.js` - Radio widget factory and UI
- `static/js/radio-widget-core.js` - Core playback state management
- `static/js/radio-widget-visualizer.js` - Fullscreen audio visualizations
- `static/css/radio-widget.css` - Base widget styles
- `static/css/radio-widget-fullscreen.css` - Fullscreen mode styles

### Backend
- `app.py` - Flask routes, audio generation with MusicGen/AudioGen
- `database.py` - SQLite with FTS5 search

## Testing
```bash
npx playwright test
```

## Recent Changes

### Visualization Performance Optimization (Dec 2025)
- All visualizations (bars, wave, circle, particles) scale with `targetComplexity`
- FPS monitoring auto-adjusts complexity:
  - FPS < 25: Aggressive reduction (shadows off, fewer elements)
  - FPS < 40: Moderate reduction
  - FPS > 55: Gradually restore full quality
- Expensive operations disabled at low complexity:
  - Shadow blur effects
  - Gradient fills
  - Particle trails and connections
  - Bar reflections
  - Multiple wave layers

### Fullscreen Mode Features
- FPS counter (top right, color-coded)
- Exit button (X at top right)
- Visualization mode selector with color themes
- Controls dock at bottom (rating, playback, actions, volume)
- Graphlings.net branding

### Visualization Modes (Dec 2025)
- **Bars** - Classic frequency bars with mirror effect and reflections
- **Wave** - Layered oscilloscope-style waveforms
- **Circle** - Rotating radial frequency display with pulsing center
- **Particles** - Music-reactive particle system with trails and connections
- **Lissajous** - Mathematical curves (Lissajous + spirograph) modulated by audio
- **Tempest** - Vector arcade game style with rotating tunnel, enemies, and bullets
- **Pong** - AI vs AI Pong game with audio-reactive ball speed
- **Breakout** - AI plays Breakout, paddle follows audio, ball speed reactive
- **Snake** - AI Snake game, speed and direction influenced by audio
- **Random** - Auto-switches between all modes every 10-20 seconds
