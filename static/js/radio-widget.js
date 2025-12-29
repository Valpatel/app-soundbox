/**
 * Radio Widget - Main Entry Point
 * Factory for creating radio widget instances
 */

/**
 * RadioWidget Factory
 * Creates and manages radio widget instances
 */
const RadioWidget = {
    // Track all instances for cross-widget sync
    _instances: new Map(),
    _instanceCount: 0,

    /**
     * Create a new radio widget instance
     * @param {string|HTMLElement} container - Container element or selector
     * @param {Object} options - Widget options
     * @param {string} [options.size='medium'] - Size mode
     * @param {string} [options.template='default'] - Style template
     * @param {string} [options.apiBaseUrl=''] - API base URL
     * @param {string} [options.userId=null] - User ID
     * @param {boolean} [options.autoPlay=false] - Auto-play on load
     * @param {boolean} [options.connectToExisting=true] - Connect to existing playback
     * @returns {RadioWidgetInstance} Widget instance
     */
    create(container, options = {}) {
        const containerEl = typeof container === 'string'
            ? document.querySelector(container)
            : container;

        if (!containerEl) {
            console.error('[RadioWidget] Container not found:', container);
            return null;
        }

        const instance = new RadioWidgetInstance(containerEl, {
            size: options.size || 'medium',
            template: options.template || 'default',
            apiBaseUrl: options.apiBaseUrl || '',
            userId: options.userId || null,
            autoPlay: options.autoPlay || false,
            connectToExisting: options.connectToExisting !== false,
            audioElement: options.audioElement || null
        });

        const id = `widget_${++this._instanceCount}`;
        this._instances.set(id, instance);
        instance._id = id;

        return instance;
    },

    /**
     * Create a minimal radio widget
     * @param {string|HTMLElement} container - Container element or selector
     * @param {Object} options - Widget options
     * @returns {RadioWidgetInstance} Widget instance
     */
    createMinimal(container, options = {}) {
        return this.create(container, { ...options, size: 'minimal' });
    },

    /**
     * Get an existing widget instance by ID
     * @param {string} id - Widget ID
     * @returns {RadioWidgetInstance|null} Widget instance or null
     */
    get(id) {
        return this._instances.get(id) || null;
    },

    /**
     * Destroy a widget instance
     * @param {string} id - Widget ID
     */
    destroy(id) {
        const instance = this._instances.get(id);
        if (instance) {
            instance.destroy();
            this._instances.delete(id);
        }
    },

    /**
     * Destroy all widget instances
     */
    destroyAll() {
        this._instances.forEach((instance) => instance.destroy());
        this._instances.clear();
    }
};


/**
 * Radio Widget Instance
 * Individual widget with its own UI and shared core
 */
class RadioWidgetInstance {
    constructor(container, options) {
        this.container = container;
        this.options = options;
        this.size = options.size;
        this.template = options.template;

        // Get or create shared audio core
        if (options.connectToExisting && RadioWidgetInstance._sharedCore) {
            this.core = RadioWidgetInstance._sharedCore;
        } else {
            this.core = new RadioWidgetCore({
                apiBaseUrl: options.apiBaseUrl,
                userId: options.userId,
                autoPlay: options.autoPlay,
                audioElement: options.audioElement || null
            });
            if (!options.audioElement) {
                RadioWidgetInstance._sharedCore = this.core;
            }
        }

        // Set up container
        this.container.classList.add('radio-widget', `radio-widget-${this.size}`);
        this.container.setAttribute('data-template', this.template);

        // Render initial UI
        this._render();

        // Subscribe to core events
        this._setupEventListeners();
    }

    // Shared core instance for cross-widget sync
    static _sharedCore = null;

    // ========================================
    // PLAYBACK CONTROLS (delegate to core)
    // ========================================

    play() { this.core.play(); }
    pause() { this.core.pause(); }
    toggle() { this.core.toggle(); }
    next() { this.core.next(); }
    previous() { this.core.previous(); }
    skip() { this.core.skip(); }
    setVolume(level) { this.core.setVolume(level); }
    toggleMute() { this.core.toggleMute(); }
    seek(time) { this.core.seek(time); }

    // ========================================
    // QUEUE MANAGEMENT (delegate to core)
    // ========================================

    loadStation(station, options) { return this.core.loadStation(station, options); }
    setMood(mood) { return this.core.setMood(mood); }
    addToQueue(track, playNext) { return this.core.addToQueue(track, playNext); }
    removeFromQueue(index) { this.core.removeFromQueue(index); }
    clearQueue() { this.core.clearQueue(); }
    getQueue() { return this.core.getQueue(); }
    getCurrentTrack() { return this.core.getCurrentTrack(); }

    _selectStation(stationId) {
        // Map station IDs to search terms
        const stationMap = {
            'all': '',
            'ambient': 'ambient soundscape',
            'retro': 'chiptune 8-bit retro',
            'happy': 'happy bouncy upbeat',
            'lofi': 'lo-fi hip hop chill'
        };

        const search = stationMap[stationId] || '';

        // Update button text
        const labelMap = {
            'all': 'All Music',
            'ambient': 'Ambient',
            'retro': 'Retro',
            'happy': 'Happy',
            'lofi': 'Lo-Fi'
        };

        this.container.querySelectorAll('.rw-current-station').forEach(el => {
            el.textContent = labelMap[stationId] || 'All Music';
        });

        // Mark active station
        this.container.querySelectorAll('.rw-station-option').forEach(opt => {
            opt.classList.toggle('active', opt.dataset.station === stationId);
        });

        // Load the station using the core's loadQueue method
        if (this.core.loadQueue) {
            this.core.loadQueue(stationId, { search });
        } else if (window.startStation) {
            // Fallback to main app's station function
            window.startStation(stationId === 'all' ? 'all' : stationId);
        }
    }

    // ========================================
    // EVENT API (delegate to core)
    // ========================================

    on(event, callback) { return this.core.on(event, callback); }
    off(event, callback) { this.core.off(event, callback); }

    // ========================================
    // UI CONTROLS
    // ========================================

    /**
     * Change widget size
     * @param {string} size - New size mode
     */
    setSize(size) {
        this.container.classList.remove(`radio-widget-${this.size}`);
        this.size = size;
        this.container.classList.add(`radio-widget-${this.size}`);
        this._render();
        this.core._events.emit('sizeChange', size);
    }

    /**
     * Change style template
     * @param {string} template - Template name
     */
    setTemplate(template) {
        this.template = template;
        this.container.setAttribute('data-template', template);
        this.core._events.emit('templateChange', template);
    }

    /**
     * Enter fullscreen mode
     */
    enterFullscreen() {
        if (this.container.requestFullscreen) {
            this.container.requestFullscreen();
            this.setSize('fullscreen');
        }
    }

    /**
     * Exit fullscreen mode
     */
    exitFullscreen() {
        console.log('[RadioWidget] exitFullscreen called, fullscreenElement:', document.fullscreenElement);
        if (document.fullscreenElement) {
            if (document.exitFullscreen) {
                document.exitFullscreen();
            } else if (document.webkitExitFullscreen) {
                document.webkitExitFullscreen();
            } else if (document.mozCancelFullScreen) {
                document.mozCancelFullScreen();
            } else if (document.msExitFullscreen) {
                document.msExitFullscreen();
            }
            // Size change handled by fullscreenchange event listener in index.html
        }
    }

    /**
     * Destroy this widget instance
     * @param {Object} options - Cleanup options
     * @param {boolean} [options.preserveAudio=false] - Keep audio playing (for shared audio elements)
     */
    destroy(options = {}) {
        // Clean up visualizer (pass preserveAudio to avoid closing AudioContext)
        if (this.visualizer) {
            this.visualizer.destroy({ preserveAudio: options.preserveAudio });
            this.visualizer = null;
        }

        // Clean up keyboard handler
        if (this._keyHandler) {
            document.removeEventListener('keydown', this._keyHandler);
            this._keyHandler = null;
        }

        // Clean up auto-dim handlers
        if (this._dimTimer) {
            clearTimeout(this._dimTimer);
            this._dimTimer = null;
        }
        if (this._mouseMoveHandler) {
            this.container.removeEventListener('mousemove', this._mouseMoveHandler);
            this._mouseMoveHandler = null;
        }
        if (this._clickHandler) {
            this.container.removeEventListener('click', this._clickHandler);
            this.container.removeEventListener('touchstart', this._clickHandler);
            this._clickHandler = null;
        }

        this.container.classList.remove('radio-widget', `radio-widget-${this.size}`, 'ui-dimmed', 'ui-active');
        this.container.innerHTML = '';
        this.core._events.emit('destroy');
    }

    // ========================================
    // PRIVATE METHODS
    // ========================================

    _setupEventListeners() {
        // Update UI on track change
        this.core.on('trackChange', (track) => this._updateNowPlaying(track));
        this.core.on('playStateChange', (isPlaying) => this._updatePlayState(isPlaying));
        this.core.on('queueUpdate', (queue) => this._updateQueue(queue));
        this.core.on('volumeChange', (volume) => this._updateVolume(volume));
        this.core.on('muteChange', (muted) => this._updateMute(muted));
        this.core.on('timeUpdate', (data) => this._updateProgress(data));
        this.core.on('vote', (data) => this._updateVote(data));
        this.core.on('favorite', (data) => this._updateFavorite(data));

        // Handle fullscreen change
        document.addEventListener('fullscreenchange', () => {
            if (!document.fullscreenElement && this.size === 'fullscreen') {
                this.setSize('large');
            }
        });
    }

    _render() {
        const layout = this._getLayout();
        this.container.innerHTML = this._renderLayout(layout);
        this._attachControlHandlers();

        // Update with current state
        if (this.core.currentTrack) {
            this._updateNowPlaying(this.core.currentTrack);
        }
        this._updatePlayState(this.core.isPlaying);
        this._updateVolume(this.core.volume);
        this._updateMute(this.core.isMuted);
    }

    _getLayout() {
        const LAYOUTS = {
            'minimal': ['playButton', 'skipButtons', 'trackInfo', 'voteButtons'],
            'small': ['playButton', 'trackInfo', 'voteButtons', 'progressBar'],
            'medium': ['stationSelector', 'visualizerSmall', 'trackInfo', 'progressBar', 'playButton', 'skipButtons', 'voteButtons', 'volumeControl'],
            'large': ['stationSelector', 'visualizerSmall', 'trackInfo', 'progressBar', 'playButton', 'skipButtons', 'voteButtons', 'volumeControl', 'favoriteButton'],
            // Fullscreen: clean layout with visualizer + bottom dock with all controls
            'fullscreen': ['visualizer']
        };
        return LAYOUTS[this.size] || LAYOUTS['medium'];
    }

    _renderLayout(components) {
        const html = [];
        const controlsHtml = [];

        // Fullscreen mode: custom layout with dock at bottom
        if (this.size === 'fullscreen') {
            html.push(this._renderFullscreenLayout());
            return html.join('');
        }

        // Components that go in the controls row
        const controlComponents = ['playButton', 'skipButtons', 'voteButtons', 'volumeControl', 'favoriteButton'];
        const needsControlsRow = (this.size === 'medium' || this.size === 'large');

        for (const comp of components) {
            const isControl = controlComponents.includes(comp);
            const target = (needsControlsRow && isControl) ? controlsHtml : html;

            switch (comp) {
                case 'playButton':
                    target.push(this._renderPlayButton());
                    break;
                case 'skipButtons':
                    target.push(this._renderSkipButtons());
                    break;
                case 'trackInfo':
                    target.push(this._renderTrackInfo());
                    break;
                case 'progressBar':
                    target.push(this._renderProgressBar());
                    break;
                case 'volumeControl':
                    target.push(this._renderVolumeControl());
                    break;
                case 'eqVisualizer':
                    target.push(this._renderEqVisualizer());
                    break;
                case 'favoriteButton':
                    target.push(this._renderFavoriteButton());
                    break;
                case 'voteButtons':
                    target.push(this._renderVoteButtons());
                    break;
                case 'queuePreview':
                    target.push(this._renderQueuePreview());
                    break;
                case 'visualizer':
                    target.push(this._renderVisualizer());
                    break;
                case 'visualizerSmall':
                    target.push(this._renderVisualizerSmall());
                    break;
                case 'moodSelector':
                    target.push(this._renderMoodSelector());
                    break;
                case 'stationSelector':
                    html.push(this._renderStationSelector());
                    break;
            }
        }

        // Wrap controls in a row for medium/large
        if (needsControlsRow && controlsHtml.length > 0) {
            html.push(`<div class="rw-controls-row">${controlsHtml.join('')}</div>`);
        }

        // Add branding for embedded widgets (can be disabled)
        if (this.options.showBranding !== false) {
            html.push(this._renderBranding());
        }

        return html.join('');
    }

    _renderFullscreenLayout() {
        return `
            <!-- Full-screen visualizer canvas -->
            <canvas class="rw-visualizer-canvas"></canvas>

            <!-- FPS counter (top right) -->
            <div class="rw-fps-counter fps-good" id="rw-fps-counter">60 FPS</div>

            <!-- Exit button (top right) -->
            <button class="rw-exit-btn" data-action="exitFullscreen" title="Exit Fullscreen" data-tooltip="Exit Fullscreen">
                <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
                    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
            </button>

            <!-- Viz controls panel (top left) -->
            <div class="rw-viz-panel">
                ${this._renderVisualizerModes()}
                <!-- Color themes (shown when viz mode clicked) -->
                <div class="rw-viz-settings" id="rw-viz-settings">
                    <div class="rw-settings-label">Color Theme</div>
                    <div class="rw-color-themes">
                        <button class="rw-color-btn active" data-theme="purple" title="Purple" data-tooltip="Purple"></button>
                        <button class="rw-color-btn" data-theme="blue" title="Blue" data-tooltip="Blue"></button>
                        <button class="rw-color-btn" data-theme="green" title="Green" data-tooltip="Green"></button>
                        <button class="rw-color-btn" data-theme="cyan" title="Cyan" data-tooltip="Cyan"></button>
                        <button class="rw-color-btn" data-theme="pink" title="Pink" data-tooltip="Pink"></button>
                        <button class="rw-color-btn" data-theme="rainbow" title="Rainbow" data-tooltip="Rainbow"></button>
                    </div>
                </div>
            </div>

            <!-- Center content: Track info -->
            <div class="rw-fs-center">
                <div class="rw-now-playing-indicator">NOW PLAYING</div>
                <div class="rw-track-info rw-fs-track">
                    <span class="rw-track-title">No track playing</span>
                </div>
            </div>

            <!-- Bottom dock: all controls -->
            <div class="rw-controls-dock">
                <!-- Progress bar spanning full width -->
                <div class="rw-dock-progress">
                    <span class="rw-time-current">0:00</span>
                    <div class="rw-progress-bar">
                        <div class="rw-progress-fill"></div>
                    </div>
                    <span class="rw-time-total">0:00</span>
                </div>

                <!-- Control buttons row -->
                <div class="rw-dock-controls">
                    <!-- Left: Rating + Favorite -->
                    <div class="rw-dock-group">
                        <button class="rw-dock-btn rw-vote-up" data-action="upvote" title="Like" data-tooltip="Like">
                            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z"/></svg>
                        </button>
                        <button class="rw-dock-btn rw-favorite-btn" data-action="favorite" title="Favorite" data-tooltip="Favorite">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                            </svg>
                        </button>
                        <button class="rw-dock-btn rw-vote-down" data-action="downvote" title="Dislike" data-tooltip="Dislike">
                            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z"/></svg>
                        </button>
                    </div>

                    <!-- Center: Playback controls -->
                    <div class="rw-dock-group rw-dock-playback">
                        <button class="rw-dock-btn" data-action="previous" title="Previous" data-tooltip="Previous">
                            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
                        </button>
                        <button class="rw-play-btn rw-dock-play" data-action="toggle" title="Play/Pause" data-tooltip="Play/Pause">
                            <svg class="rw-icon rw-icon-play" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M8 5v14l11-7z"/>
                            </svg>
                            <svg class="rw-icon rw-icon-pause" viewBox="0 0 24 24" fill="currentColor">
                                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                            </svg>
                        </button>
                        <button class="rw-dock-btn" data-action="next" title="Next" data-tooltip="Next">
                            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                        </button>
                    </div>

                    <!-- Right: Actions + Volume -->
                    <div class="rw-dock-group">
                        <button class="rw-dock-btn" data-action="tag" title="Tag/Review" data-tooltip="Tag/Review">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M21.41 11.58l-9-9C12.05 2.22 11.55 2 11 2H4c-1.1 0-2 .9-2 2v7c0 .55.22 1.05.59 1.42l9 9c.36.36.86.58 1.41.58.55 0 1.05-.22 1.41-.59l7-7c.37-.36.59-.86.59-1.41 0-.55-.23-1.06-.59-1.42zM5.5 7C4.67 7 4 6.33 4 5.5S4.67 4 5.5 4 7 4.67 7 5.5 6.33 7 5.5 7z"/>
                            </svg>
                        </button>
                        <button class="rw-dock-btn" data-action="download" title="Download" data-tooltip="Download">
                            <svg viewBox="0 0 24 24" fill="currentColor">
                                <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
                            </svg>
                        </button>
                        <div class="rw-volume-wrapper">
                            <button class="rw-dock-btn rw-volume-btn" data-action="toggleMute" title="Volume" data-tooltip="Volume">
                                <svg class="rw-icon-volume" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                                </svg>
                                <svg class="rw-icon-muted" viewBox="0 0 24 24" fill="currentColor">
                                    <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                                </svg>
                            </button>
                            <div class="rw-volume-popup">
                                <input type="range" class="rw-volume-slider" min="0" max="100" value="100" data-action="volume">
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Keyboard shortcuts hint -->
            <div class="rw-shortcuts-hint">
                <kbd>Space</kbd> Play/Pause &nbsp; <kbd>←</kbd><kbd>→</kbd> Prev/Next &nbsp; <kbd>Esc</kbd> Exit
            </div>

            <!-- Branding watermark -->
            <div class="rw-fs-branding">
                <a href="https://graphlings.net" target="_blank" class="rw-fs-brand-link">
                    <img src="/static/graphlings/logo-104.png" alt="Graphlings" class="rw-fs-brand-logo">
                    <span class="rw-fs-brand-text">Graphlings.net</span>
                </a>
            </div>
        `;
    }

    _renderPlayButton() {
        return `
            <button class="rw-play-btn" data-action="toggle" title="Play/Pause" data-tooltip="Play/Pause">
                <svg class="rw-icon rw-icon-play" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 5v14l11-7z"/>
                </svg>
                <svg class="rw-icon rw-icon-pause" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
            </button>
        `;
    }

    _renderSkipButtons() {
        return `
            <div class="rw-skip-buttons">
                <button class="rw-btn rw-prev-btn" data-action="previous" title="Previous" data-tooltip="Previous">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
                </button>
                <button class="rw-btn rw-next-btn" data-action="next" title="Next" data-tooltip="Next">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                </button>
            </div>
        `;
    }

    _renderTrackInfo() {
        const truncate = this.size === 'minimal';
        return `
            <div class="rw-track-info ${truncate ? 'rw-truncate' : ''}">
                <span class="rw-track-title">No track playing</span>
                <span class="rw-track-duration"></span>
            </div>
        `;
    }

    _renderProgressBar() {
        return `
            <div class="rw-progress-container">
                <div class="rw-progress-bar">
                    <div class="rw-progress-fill"></div>
                </div>
                <span class="rw-time-current">0:00</span>
                <span class="rw-time-total">0:00</span>
            </div>
        `;
    }

    _renderVolumeControl() {
        return `
            <div class="rw-volume-control">
                <button class="rw-btn rw-mute-btn" data-action="toggleMute" title="Mute" data-tooltip="Mute">
                    <svg class="rw-icon-volume" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                    </svg>
                    <svg class="rw-icon-muted" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                    </svg>
                </button>
                <input type="range" class="rw-volume-slider" min="0" max="100" value="100" data-action="volume" title="Volume">
            </div>
        `;
    }

    _renderEqVisualizer() {
        return `
            <div class="rw-eq-visualizer">
                <div class="rw-eq-bar"></div>
                <div class="rw-eq-bar"></div>
                <div class="rw-eq-bar"></div>
                <div class="rw-eq-bar"></div>
                <div class="rw-eq-bar"></div>
            </div>
        `;
    }

    _renderFavoriteButton() {
        return `
            <button class="rw-btn rw-favorite-btn" data-action="favorite" title="Add to favorites" data-tooltip="Favorite">
                <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                </svg>
            </button>
        `;
    }

    _renderVoteButtons() {
        return `
            <div class="rw-vote-buttons">
                <button class="rw-btn rw-vote-up" data-action="upvote" title="Like" data-tooltip="Like">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h4V9H1v12zm22-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L14.17 1 7.59 7.59C7.22 7.95 7 8.45 7 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z"/></svg>
                    <span class="rw-vote-count rw-upvotes">0</span>
                </button>
                <button class="rw-btn rw-vote-down" data-action="downvote" title="Dislike" data-tooltip="Dislike">
                    <svg viewBox="0 0 24 24" fill="currentColor"><path d="M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z"/></svg>
                    <span class="rw-vote-count rw-downvotes">0</span>
                </button>
            </div>
        `;
    }

    _renderQueuePreview() {
        const count = this.size === 'fullscreen' ? 5 : 3;
        return `
            <div class="rw-queue-preview" data-count="${count}">
                <h4>Up Next</h4>
                <div class="rw-queue-items"></div>
            </div>
        `;
    }

    _renderVisualizer() {
        return `
            <canvas class="rw-visualizer-canvas"></canvas>
        `;
    }

    _renderVisualizerSmall() {
        return `
            <div class="rw-visualizer-small">
                <canvas class="rw-visualizer-canvas-small"></canvas>
            </div>
        `;
    }

    _renderStationSelector() {
        const stations = [
            { id: 'all', label: 'All', icon: 'shuffle' },
            { id: 'ambient', label: 'Ambient', icon: 'wave' },
            { id: 'retro', label: 'Retro', icon: 'chip' },
            { id: 'happy', label: 'Happy', icon: 'sun' },
            { id: 'lofi', label: 'Lo-Fi', icon: 'coffee' }
        ];

        const iconPaths = {
            shuffle: 'M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z',
            wave: 'M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9-4.03-9-9-9zm0 16c-3.86 0-7-3.14-7-7s3.14-7 7-7 7 3.14 7 7-3.14 7-7 7zm-1-11h2v6h-2z',
            chip: 'M9 9v6h6V9H9zm4 4h-2v-2h2v2zm4-9H7c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h10c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H7V6h10v14z',
            sun: 'M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z',
            coffee: 'M20 3H4v10c0 2.21 1.79 4 4 4h6c2.21 0 4-1.79 4-4v-3h2c1.11 0 2-.89 2-2V5c0-1.11-.89-2-2-2zm0 5h-2V5h2v3zM4 19h16v2H4z'
        };

        return `
            <div class="rw-station-selector">
                <button class="rw-station-dropdown-btn" data-action="toggleStations" title="Change Station" data-tooltip="Station">
                    <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                        <path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/>
                    </svg>
                    <span class="rw-current-station">All Music</span>
                    <svg class="rw-dropdown-arrow" viewBox="0 0 24 24" fill="currentColor" width="12" height="12">
                        <path d="M7 10l5 5 5-5z"/>
                    </svg>
                </button>
                <div class="rw-station-menu hidden">
                    ${stations.map(s => `
                        <button class="rw-station-option" data-station="${s.id}" title="${s.label}">
                            <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
                                <path d="${iconPaths[s.icon]}"/>
                            </svg>
                            <span>${s.label}</span>
                        </button>
                    `).join('')}
                </div>
            </div>
        `;
    }

    _renderMoodSelector() {
        const moods = ['calm', 'happy', 'energetic', 'intense', 'chill', 'suspense'];
        return `
            <div class="rw-mood-selector">
                ${moods.map(mood => `
                    <button class="rw-mood-btn" data-mood="${mood}">${mood}</button>
                `).join('')}
            </div>
        `;
    }

    _renderBranding() {
        // Show branding for embedded widgets (external use)
        // Can be disabled with showBranding: false option
        const brandUrl = this.options.brandUrl || 'https://graphlings.net';

        return `
            <div class="rw-branding">
                <a href="${brandUrl}" target="_blank" rel="noopener noreferrer" class="rw-branding-link" title="Powered by Graphlings">
                    <img src="/static/graphlings/logo-104.png" alt="Graphlings" class="rw-branding-logo">
                    <span class="rw-branding-text">Graphlings.net</span>
                </a>
            </div>
        `;
    }

    _renderVisualizerModes() {
        return `
            <div class="rw-viz-modes">
                <button class="rw-viz-mode-btn" data-viz-mode="bars" title="Bars" data-tooltip="Bars">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M4 18h2V8H4v10zm3 0h2V6H7v12zm3 0h2v-8h-2v8zm3 0h2V4h-2v14zm3 0h2v-4h-2v4z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn" data-viz-mode="wave" title="Wave" data-tooltip="Wave">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M3 12c0-1.1.9-2 2-2s2 .9 2 2-.9 2-2 2-2-.9-2-2zm4.5 0c0-1.1.9-2 2-2s2 .9 2 2-.9 2-2 2-2-.9-2-2zm4.5 0c0-1.1.9-2 2-2s2 .9 2 2-.9 2-2 2-2-.9-2-2zm4.5 0c0-1.1.9-2 2-2s2 .9 2 2-.9 2-2 2-2-.9-2-2z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn" data-viz-mode="circle" title="Circle" data-tooltip="Circle">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn" data-viz-mode="particles" title="Particles" data-tooltip="Particles">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 6c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm-1 14h2v-8h3l-4-4-4 4h3v8z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn" data-viz-mode="lissajous" title="Math Lines" data-tooltip="Math Lines">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm-5.5-2.5l7.51-3.49L17.5 6.5 9.99 9.99 6.5 17.5zm5.5-6.6c.61 0 1.1.49 1.1 1.1s-.49 1.1-1.1 1.1-1.1-.49-1.1-1.1.49-1.1 1.1-1.1z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn" data-viz-mode="tempest" title="Tempest" data-tooltip="Tempest">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn" data-viz-mode="pong" title="Pong" data-tooltip="Pong">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M2 6h2v12H2V6zm18 0h2v12h-2V6zm-9 5h2v2h-2v-2z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn" data-viz-mode="breakout" title="Breakout" data-tooltip="Breakout">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M2 4h4v2H2V4zm6 0h4v2H8V4zm6 0h4v2h-4V4zm6 0h2v2h-2V4zM2 8h4v2H2V8zm6 0h4v2H8V8zm6 0h4v2h-4V8zm6 0h2v2h-2V8zM9 18h6v2H9v-2zm-1-4h2v2H8v-2z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn" data-viz-mode="snake" title="Snake" data-tooltip="Snake">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M20 12c0-1.1-.9-2-2-2h-2c0-1.1-.9-2-2-2h-2c0-1.1-.9-2-2-2H8c-1.1 0-2 .9-2 2v2c0 1.1.9 2 2 2h2c0 1.1.9 2 2 2h2c0 1.1.9 2 2 2h2c1.1 0 2-.9 2-2v-2z"/>
                    </svg>
                </button>
                <button class="rw-viz-mode-btn active" data-viz-mode="random" title="Random" data-tooltip="Random">
                    <svg viewBox="0 0 24 24" fill="currentColor">
                        <path d="M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z"/>
                    </svg>
                </button>
            </div>
        `;
    }

    _attachControlHandlers() {
        // Play/pause
        this.container.querySelectorAll('[data-action="toggle"]').forEach(btn => {
            btn.addEventListener('click', () => this.toggle());
        });

        // Skip buttons
        this.container.querySelectorAll('[data-action="previous"]').forEach(btn => {
            btn.addEventListener('click', () => this.previous());
        });
        this.container.querySelectorAll('[data-action="next"]').forEach(btn => {
            btn.addEventListener('click', () => this.next());
        });

        // Mute
        this.container.querySelectorAll('[data-action="toggleMute"]').forEach(btn => {
            btn.addEventListener('click', () => this.toggleMute());
        });

        // Volume slider
        this.container.querySelectorAll('[data-action="volume"]').forEach(slider => {
            slider.addEventListener('input', (e) => {
                this.setVolume(parseInt(e.target.value) / 100);
            });
        });

        // Favorite - delegate to main app which has login check
        this.container.querySelectorAll('[data-action="favorite"]').forEach(btn => {
            btn.addEventListener('click', () => {
                if (window.toggleRadioFavorite) {
                    window.toggleRadioFavorite();
                } else if (window.isUserAuthenticated && !window.isUserAuthenticated()) {
                    if (window.showLoginPrompt) window.showLoginPrompt('favorite tracks');
                } else {
                    this.core.toggleFavorite();
                }
            });
        });

        // Vote buttons - delegate to main app's feedback modal if available
        this.container.querySelectorAll('[data-action="upvote"]').forEach(btn => {
            btn.addEventListener('click', () => {
                // If already liked, do nothing (can't unlike for now)
                if (btn.classList.contains('voted')) return;

                // Delegate to main app's feedback modal (shows reason selection)
                if (window.showPositiveFeedbackMenu) {
                    window.showPositiveFeedbackMenu();
                    return;
                }

                // Fallback: Check auth, then add glow animation and vote directly
                if (window.isUserAuthenticated && !window.isUserAuthenticated()) {
                    if (window.showLoginPrompt) window.showLoginPrompt('rate tracks');
                    return;
                }

                btn.classList.add('voting');
                this.core.vote(1);

                // After glow animation, keep liked state
                setTimeout(() => {
                    btn.classList.remove('voting');
                    btn.classList.add('voted');
                }, 600);
            });
        });
        this.container.querySelectorAll('[data-action="downvote"]').forEach(btn => {
            btn.addEventListener('click', () => {
                // If already disliked, do nothing
                if (btn.classList.contains('voted')) return;

                // Delegate to main app's feedback modal (shows reason selection)
                if (window.showFeedbackMenu) {
                    window.showFeedbackMenu();
                    return;
                }

                // Fallback: Check auth, then add glow animation and vote directly
                if (window.isUserAuthenticated && !window.isUserAuthenticated()) {
                    if (window.showLoginPrompt) window.showLoginPrompt('rate tracks');
                    return;
                }

                btn.classList.add('voting');
                this.core.vote(-1);

                // After glow animation, skip to next track
                setTimeout(() => {
                    btn.classList.remove('voting');
                    btn.classList.add('voted');
                    // Skip to next track after brief visual feedback
                    setTimeout(() => {
                        this.core.next();
                    }, 400);
                }, 600);
            });
        });

        // Download button - delegate to main app's download function (has login check)
        this.container.querySelectorAll('[data-action="download"]').forEach(btn => {
            btn.addEventListener('click', () => {
                if (window.downloadCurrentTrack) {
                    window.downloadCurrentTrack();
                } else if (this.core.currentTrack?.filename) {
                    // Fallback: Check auth before allowing download
                    if (window.isUserAuthenticated && !window.isUserAuthenticated()) {
                        if (window.showLoginPrompt) window.showLoginPrompt('download tracks');
                        return;
                    }
                    const a = document.createElement('a');
                    a.href = `/download/${this.core.currentTrack.filename}`;
                    a.download = this.core.currentTrack.filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                }
            });
        });

        // Tag button - delegate to main app's tag function (has login check)
        this.container.querySelectorAll('[data-action="tag"]').forEach(btn => {
            btn.addEventListener('click', () => {
                if (window.tagCurrentTrack) {
                    window.tagCurrentTrack();
                } else if (window.isUserAuthenticated && !window.isUserAuthenticated()) {
                    // Fallback: show login prompt if main function not available
                    if (window.showLoginPrompt) window.showLoginPrompt('suggest tags');
                }
            });
        });

        // Mood selector
        this.container.querySelectorAll('[data-mood]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.setMood(e.target.dataset.mood);
            });
        });

        // Station selector dropdown
        this.container.querySelectorAll('[data-action="toggleStations"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const selector = btn.closest('.rw-station-selector');
                const menu = selector?.querySelector('.rw-station-menu');
                if (menu) {
                    menu.classList.toggle('hidden');
                    selector.classList.toggle('open');
                }
            });
        });

        // Station options
        this.container.querySelectorAll('[data-station]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const stationId = e.currentTarget.dataset.station;
                this._selectStation(stationId);
                // Close dropdown
                const menu = btn.closest('.rw-station-menu');
                const selector = btn.closest('.rw-station-selector');
                if (menu) menu.classList.add('hidden');
                if (selector) selector.classList.remove('open');
            });
        });

        // Close station menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.rw-station-selector')) {
                this.container.querySelectorAll('.rw-station-menu').forEach(menu => {
                    menu.classList.add('hidden');
                });
                this.container.querySelectorAll('.rw-station-selector').forEach(sel => {
                    sel.classList.remove('open');
                });
            }
        });

        // Progress bar click to seek
        const progressBar = this.container.querySelector('.rw-progress-bar');
        if (progressBar) {
            progressBar.addEventListener('click', (e) => {
                const rect = progressBar.getBoundingClientRect();
                const percent = (e.clientX - rect.left) / rect.width;
                this.seek(percent * this.core.getDuration());
            });
        }

        // Exit fullscreen button - use event delegation for reliability
        this.container.querySelectorAll('[data-action="exitFullscreen"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                console.log('[RadioWidget] Exit fullscreen clicked');
                this.exitFullscreen();
            });
        });

        // Also add delegated handler on container as fallback
        if (this.size === 'fullscreen' && !this._exitDelegateAdded) {
            this._exitDelegateAdded = true;
            this.container.addEventListener('click', (e) => {
                const exitBtn = e.target.closest('[data-action="exitFullscreen"]');
                if (exitBtn) {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log('[RadioWidget] Exit fullscreen via delegation');
                    this.exitFullscreen();
                }
            });
        }

        // Visualizer mode buttons
        this.container.querySelectorAll('[data-viz-mode]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = e.currentTarget.dataset.vizMode;
                // Update active state
                this.container.querySelectorAll('[data-viz-mode]').forEach(b => {
                    b.classList.toggle('active', b === e.currentTarget);
                });
                // Change visualizer mode
                if (this.visualizer) {
                    this.visualizer.setMode(mode);
                }
            });
        });

        // Color theme buttons
        this.container.querySelectorAll('[data-theme]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const theme = e.currentTarget.dataset.theme;
                // Update active state
                this.container.querySelectorAll('[data-theme]').forEach(b => {
                    b.classList.toggle('active', b === e.currentTarget);
                });
                // Apply color theme to visualizer
                if (this.visualizer) {
                    this.visualizer.setColorTheme(theme);
                }
            });
        });

        // NOTE: Don't auto-init visualizer for fullscreen here - it needs to be called
        // AFTER the fullscreen transition completes (when container has proper dimensions).
        // The caller (enterRadioFullscreen) will call _initVisualizer() explicitly.

        // Keyboard shortcuts for fullscreen
        if (this.size === 'fullscreen') {
            this._keyHandler = (e) => {
                this._showUI(); // Any key press shows UI
                switch (e.key) {
                    case 'Escape':
                        this.exitFullscreen();
                        break;
                    case ' ':
                        e.preventDefault();
                        this.toggle();
                        break;
                    case 'ArrowRight':
                        this.next();
                        break;
                    case 'ArrowLeft':
                        this.previous();
                        break;
                    case 'ArrowUp':
                        this.setVolume(Math.min(1, this.core.volume + 0.1));
                        break;
                    case 'ArrowDown':
                        this.setVolume(Math.max(0, this.core.volume - 0.1));
                        break;
                    case 'm':
                        this.toggleMute();
                        break;
                }
            };
            document.addEventListener('keydown', this._keyHandler);

            // Auto-dim UI after inactivity
            this._initAutoDim();
        }
    }

    /**
     * Initialize auto-dim behavior for fullscreen mode
     */
    _initAutoDim() {
        const DIM_TIMEOUT = 4000; // 4 seconds of inactivity
        this._dimTimer = null;
        this._isUIDimmed = false;

        // Show UI and reset timer
        this._showUI = () => {
            this.container.classList.remove('ui-dimmed');
            this.container.classList.add('ui-active');
            this._isUIDimmed = false;

            // Clear existing timer
            if (this._dimTimer) {
                clearTimeout(this._dimTimer);
            }

            // Start new timer
            this._dimTimer = setTimeout(() => {
                this._dimUI();
            }, DIM_TIMEOUT);
        };

        // Dim the UI
        this._dimUI = () => {
            this.container.classList.remove('ui-active');
            this.container.classList.add('ui-dimmed');
            this._isUIDimmed = true;
        };

        // Listen for mouse movement and clicks
        this._mouseMoveHandler = () => this._showUI();
        this._clickHandler = () => this._showUI();

        this.container.addEventListener('mousemove', this._mouseMoveHandler);
        this.container.addEventListener('click', this._clickHandler);
        this.container.addEventListener('touchstart', this._clickHandler);

        // Start the initial timer
        this._showUI();
    }

    _initVisualizer() {
        const canvas = this.container.querySelector('.rw-visualizer-canvas');
        console.log('[RadioWidget] _initVisualizer called, canvas:', canvas, 'RadioWidgetVisualizer:', !!window.RadioWidgetVisualizer);
        if (!canvas || !window.RadioWidgetVisualizer) {
            console.warn('[RadioWidget] Missing canvas or visualizer class');
            return;
        }

        // Get the audio element from the core
        const audioElement = this.core.audioElement;
        console.log('[RadioWidget] Audio element:', audioElement, 'src:', audioElement?.src);
        if (!audioElement) {
            console.warn('[RadioWidget] No audio element found');
            return;
        }

        // For fullscreen, use window dimensions
        const container = this.container;
        const isFullscreen = this.size === 'fullscreen';
        const width = isFullscreen ? window.innerWidth : container.clientWidth;
        const height = isFullscreen ? window.innerHeight : container.clientHeight;

        console.log('[RadioWidget] Container dimensions:', width, 'x', height, 'isFullscreen:', isFullscreen);

        // Force canvas to full size immediately before creating visualizer
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.width = width * window.devicePixelRatio;
        canvas.height = height * window.devicePixelRatio;

        this.visualizer = new RadioWidgetVisualizer(canvas, audioElement);
        console.log('[RadioWidget] Visualizer created:', this.visualizer);

        // Start the visualizer immediately
        console.log('[RadioWidget] Starting visualizer, canvas size:', canvas.width, 'x', canvas.height);
        this.visualizer.start();

        // Also listen for resize events to update canvas size
        if (isFullscreen) {
            this._fullscreenResizeHandler = () => {
                canvas.width = window.innerWidth * window.devicePixelRatio;
                canvas.height = window.innerHeight * window.devicePixelRatio;
            };
            window.addEventListener('resize', this._fullscreenResizeHandler);
        }

        // Sync visualizer with play state
        if (this.core.isPlaying) {
            console.log('[RadioWidget] Audio playing, ensuring visualizer is started');
            this.visualizer.start();
        }
    }

    _updateNowPlaying(track) {
        const titleEl = this.container.querySelector('.rw-track-title');
        const durationEl = this.container.querySelector('.rw-track-duration');
        const upvotesEl = this.container.querySelector('.rw-upvotes');
        const downvotesEl = this.container.querySelector('.rw-downvotes');
        const upBtn = this.container.querySelector('.rw-vote-up');
        const downBtn = this.container.querySelector('.rw-vote-down');
        const favBtn = this.container.querySelector('.rw-favorite-btn');

        if (titleEl) titleEl.textContent = track.prompt || 'Unknown track';
        if (durationEl) durationEl.textContent = track.duration ? `${track.duration}s` : '';
        if (upvotesEl) upvotesEl.textContent = track.upvotes || 0;
        if (downvotesEl) downvotesEl.textContent = track.downvotes || 0;

        // Clear vote/favorite states on track change - will be restored by _loadTrackVote/_loadTrackFavorite
        if (upBtn) {
            upBtn.classList.remove('voted', 'voting');
        }
        if (downBtn) {
            downBtn.classList.remove('voted', 'voting');
        }
        if (favBtn) {
            favBtn.classList.remove('favorited');
        }
    }

    _updatePlayState(isPlaying) {
        const playBtn = this.container.querySelector('.rw-play-btn');
        const eq = this.container.querySelector('.rw-eq-visualizer');

        if (playBtn) {
            playBtn.classList.toggle('playing', isPlaying);
        }
        if (eq) {
            eq.classList.toggle('playing', isPlaying);
        }
    }

    _updateQueue(queue) {
        const queueItems = this.container.querySelector('.rw-queue-items');
        if (!queueItems) return;

        const count = parseInt(this.container.querySelector('.rw-queue-preview')?.dataset.count || 3);
        queueItems.innerHTML = queue.slice(0, count).map((track, i) => `
            <div class="rw-queue-item">
                <span class="rw-queue-num">${i + 1}</span>
                <span class="rw-queue-title">${this._escapeHtml(track.prompt || 'Unknown')}</span>
            </div>
        `).join('') || '<div class="rw-queue-empty">Queue empty</div>';
    }

    _updateVolume(volume) {
        const slider = this.container.querySelector('.rw-volume-slider');
        if (slider) {
            slider.value = Math.round(volume * 100);
        }
    }

    _updateMute(muted) {
        const muteBtn = this.container.querySelector('.rw-mute-btn');
        if (muteBtn) {
            muteBtn.classList.toggle('muted', muted);
        }
    }

    _updateProgress(data) {
        const fill = this.container.querySelector('.rw-progress-fill');
        const current = this.container.querySelector('.rw-time-current');
        const total = this.container.querySelector('.rw-time-total');

        if (fill && data.duration > 0) {
            fill.style.width = `${(data.currentTime / data.duration) * 100}%`;
        }
        if (current) {
            current.textContent = this._formatTime(data.currentTime);
        }
        if (total) {
            total.textContent = this._formatTime(data.duration);
        }
    }

    _updateVote(data) {
        const upBtn = this.container.querySelector('.rw-vote-up');
        const downBtn = this.container.querySelector('.rw-vote-down');
        const upCount = this.container.querySelector('.rw-upvotes');
        const downCount = this.container.querySelector('.rw-downvotes');

        if (upBtn) upBtn.classList.toggle('voted', data.value === 1);
        if (downBtn) downBtn.classList.toggle('voted', data.value === -1);
        if (upCount) upCount.textContent = data.upvotes || 0;
        if (downCount) downCount.textContent = data.downvotes || 0;
    }

    _updateFavorite(data) {
        const favBtn = this.container.querySelector('.rw-favorite-btn');
        if (favBtn) {
            favBtn.classList.toggle('favorited', data.isFavorited);
        }
    }

    _formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Global export for script tag usage
if (typeof window !== 'undefined') {
    window.RadioWidget = RadioWidget;
    window.RadioWidgetInstance = RadioWidgetInstance;
}

// ES module export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RadioWidget, RadioWidgetInstance };
}
