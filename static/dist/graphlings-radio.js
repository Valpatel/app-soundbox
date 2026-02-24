/**
 * Sound Box - Embeddable Radio Widget
 * Version: 1.0.0
 *
 * Include this script to add an AI-powered music player to your website.
 * Visit https://localhost:5309 for more info.
 *
 * Usage:
 *   <div id="my-radio"></div>
 *   <script src="https://localhost:5309/widget/graphlings-radio.js"></script>
 *   <script>
 *     GraphlingsRadio.init('#my-radio', {
 *       size: 'medium',      // 'ultra-minimal', 'minimal', 'small', 'medium', 'large'
 *       template: 'default', // Theme: 'default', 'neon', 'sunset', 'ocean', etc.
 *       station: 'shuffle',  // Station to play: 'shuffle', 'ambient', 'lofi', etc.
 *       autoPlay: false      // Whether to auto-play on load
 *     });
 *   </script>
 */

(function(window, document) {
    'use strict';

    const VERSION = '1.0.0';
    const API_BASE = 'https://localhost:5309';
    const WIDGET_CSS_URL = `${API_BASE}/widget/graphlings-radio.css`;

    // ========================================
    // EVENT EMITTER
    // ========================================
    class RadioWidgetEvents {
        constructor() {
            this._listeners = new Map();
        }

        on(event, callback) {
            if (!this._listeners.has(event)) {
                this._listeners.set(event, new Set());
            }
            this._listeners.get(event).add(callback);
            return () => this.off(event, callback);
        }

        off(event, callback) {
            const callbacks = this._listeners.get(event);
            if (callbacks) {
                callbacks.delete(callback);
            }
        }

        emit(event, ...args) {
            const callbacks = this._listeners.get(event);
            if (callbacks) {
                callbacks.forEach(cb => {
                    try {
                        cb(...args);
                    } catch (e) {
                        console.error('[GraphlingsRadio] Event handler error:', e);
                    }
                });
            }
        }

        clear() {
            this._listeners.clear();
        }
    }

    // ========================================
    // CORE PLAYER
    // ========================================
    class GraphlingsRadioCore {
        constructor(options = {}) {
            this._events = new RadioWidgetEvents();
            this.queue = [];
            this.currentTrack = null;
            this.playHistory = [];
            this.isPlaying = false;
            this.volume = 1.0;
            this.isMuted = false;
            this.isLoading = false;
            this.currentStation = null;

            this.apiBaseUrl = options.apiBaseUrl || API_BASE;
            this.userId = options.userId || null;

            // Create audio element
            this.audioElement = document.createElement('audio');
            this.audioElement.preload = 'auto';
            this.audioElement.crossOrigin = 'anonymous';

            // Set up audio event listeners
            this._setupAudioListeners();
        }

        _setupAudioListeners() {
            this.audioElement.addEventListener('play', () => {
                this.isPlaying = true;
                this._events.emit('playStateChange', true);
            });

            this.audioElement.addEventListener('pause', () => {
                this.isPlaying = false;
                this._events.emit('playStateChange', false);
            });

            this.audioElement.addEventListener('ended', () => {
                this.next();
            });

            this.audioElement.addEventListener('timeupdate', () => {
                this._events.emit('timeUpdate', {
                    currentTime: this.audioElement.currentTime,
                    duration: this.audioElement.duration
                });
            });

            this.audioElement.addEventListener('error', (e) => {
                console.error('[GraphlingsRadio] Audio error:', e);
                this._events.emit('error', { type: 'audio', error: e });
                this.next();
            });

            this.audioElement.addEventListener('loadstart', () => {
                this.isLoading = true;
                this._events.emit('loading', true);
            });

            this.audioElement.addEventListener('canplay', () => {
                this.isLoading = false;
                this._events.emit('loading', false);
            });
        }

        // Playback controls
        play() {
            if (this.audioElement.src) {
                this.audioElement.play().catch(e => {
                    console.error('[GraphlingsRadio] Play failed:', e);
                });
            } else if (this.queue.length > 0) {
                this._playTrack(this.queue.shift());
            }
        }

        pause() {
            this.audioElement.pause();
        }

        toggle() {
            if (this.isPlaying) {
                this.pause();
            } else {
                this.play();
            }
        }

        next() {
            if (this.currentTrack) {
                this.playHistory.push(this.currentTrack);
            }

            if (this.queue.length > 0) {
                this._playTrack(this.queue.shift());
            } else {
                this._fetchMoreTracks();
            }
        }

        previous() {
            if (this.playHistory.length > 0) {
                if (this.currentTrack) {
                    this.queue.unshift(this.currentTrack);
                }
                this._playTrack(this.playHistory.pop());
            }
        }

        skip() {
            this.next();
        }

        setVolume(level) {
            this.volume = Math.max(0, Math.min(1, level));
            this.audioElement.volume = this.isMuted ? 0 : this.volume;
            this._events.emit('volumeChange', this.volume);
        }

        toggleMute() {
            this.isMuted = !this.isMuted;
            this.audioElement.volume = this.isMuted ? 0 : this.volume;
            this._events.emit('muteChange', this.isMuted);
        }

        seek(time) {
            if (this.audioElement.duration) {
                this.audioElement.currentTime = Math.max(0, Math.min(time, this.audioElement.duration));
            }
        }

        getCurrentTime() {
            return this.audioElement.currentTime;
        }

        getDuration() {
            return this.audioElement.duration || 0;
        }

        // Queue management
        async loadStation(station, options = {}) {
            this.currentStation = station;
            this.queue = [];

            try {
                const params = new URLSearchParams({
                    station: station,
                    limit: options.limit || 10
                });

                const response = await fetch(`${this.apiBaseUrl}/api/radio?${params}`);
                if (!response.ok) throw new Error('Failed to load station');

                const data = await response.json();
                this.queue = data.queue || [];
                this._events.emit('queueUpdate', this.queue);

                if (options.autoPlay !== false && this.queue.length > 0) {
                    this._playTrack(this.queue.shift());
                }

                return this.queue;
            } catch (e) {
                console.error('[GraphlingsRadio] Failed to load station:', e);
                this._events.emit('error', { type: 'network', error: e });
                return [];
            }
        }

        async _fetchMoreTracks() {
            if (!this.currentStation) return;

            try {
                const params = new URLSearchParams({
                    station: this.currentStation,
                    limit: 5
                });

                const response = await fetch(`${this.apiBaseUrl}/api/radio?${params}`);
                if (!response.ok) throw new Error('Failed to fetch more tracks');

                const data = await response.json();
                const newTracks = data.queue || [];
                this.queue.push(...newTracks);
                this._events.emit('queueUpdate', this.queue);

                if (newTracks.length > 0 && !this.isPlaying) {
                    this._playTrack(this.queue.shift());
                }
            } catch (e) {
                console.error('[GraphlingsRadio] Failed to fetch more tracks:', e);
            }
        }

        _playTrack(track) {
            if (!track) return;

            this.currentTrack = track;
            const audioUrl = `${this.apiBaseUrl}/audio/${track.filename}`;
            this.audioElement.src = audioUrl;
            this.audioElement.play().catch(e => {
                console.error('[GraphlingsRadio] Play failed:', e);
            });

            this._events.emit('trackChange', track);
            this._events.emit('queueUpdate', this.queue);

            // Record play for analytics
            this._recordPlay(track);
        }

        async _recordPlay(track) {
            try {
                await fetch(`${this.apiBaseUrl}/api/track/${track.generation_id}/play`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source: 'embed',
                        user_id: this.userId
                    })
                });
            } catch (e) {
                // Silently fail analytics
            }
        }

        getQueue() {
            return this.queue;
        }

        getCurrentTrack() {
            return this.currentTrack;
        }

        on(event, callback) {
            return this._events.on(event, callback);
        }

        off(event, callback) {
            this._events.off(event, callback);
        }

        destroy() {
            this.pause();
            this.audioElement.src = '';
            this._events.clear();
        }
    }

    // ========================================
    // WIDGET UI
    // ========================================
    class GraphlingsRadioWidget {
        constructor(container, options = {}) {
            this.container = typeof container === 'string'
                ? document.querySelector(container)
                : container;

            if (!this.container) {
                console.error('[GraphlingsRadio] Container not found');
                return;
            }

            this.options = {
                size: options.size || 'medium',
                template: options.template || 'default',
                station: options.station || 'shuffle',
                autoPlay: options.autoPlay || false,
                showBranding: options.showBranding !== false,
                ...options
            };

            this.core = new GraphlingsRadioCore({
                apiBaseUrl: options.apiBaseUrl || API_BASE,
                userId: options.userId
            });

            this._injectStyles();
            this._render();
            this._setupEventListeners();

            // Load initial station
            if (this.options.station) {
                this.core.loadStation(this.options.station, {
                    autoPlay: this.options.autoPlay
                });
            }
        }

        _injectStyles() {
            // Check if styles already injected
            if (document.getElementById('graphlings-radio-styles')) return;

            const link = document.createElement('link');
            link.id = 'graphlings-radio-styles';
            link.rel = 'stylesheet';
            link.href = WIDGET_CSS_URL;
            document.head.appendChild(link);
        }

        _render() {
            this.container.className = `radio-widget radio-widget-${this.options.size}`;
            this.container.setAttribute('data-template', this.options.template);

            const html = `
                ${this._renderPlayButton()}
                ${this._renderSkipButtons()}
                ${this._renderTrackInfo()}
                ${['small', 'medium', 'large'].includes(this.options.size) ? this._renderProgressBar() : ''}
                ${['medium', 'large'].includes(this.options.size) ? this._renderVolumeControl() : ''}
                ${['large'].includes(this.options.size) ? this._renderQueuePreview() : ''}
                ${this.options.showBranding ? this._renderBranding() : ''}
            `;

            this.container.innerHTML = html;
            this._attachControlHandlers();
        }

        _renderPlayButton() {
            return `
                <button class="rw-play-btn" data-action="toggle" title="Play/Pause">
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
            if (this.options.size === 'ultra-minimal') return '';
            return `
                <div class="rw-skip-buttons">
                    <button class="rw-btn rw-prev-btn" data-action="previous" title="Previous">
                        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
                    </button>
                    <button class="rw-btn rw-next-btn" data-action="next" title="Next">
                        <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                    </button>
                </div>
            `;
        }

        _renderTrackInfo() {
            if (this.options.size === 'ultra-minimal') return '';
            return `
                <div class="rw-track-info">
                    <span class="rw-track-title">Click play to start</span>
                    <span class="rw-track-duration"></span>
                </div>
            `;
        }

        _renderProgressBar() {
            return `
                <div class="rw-progress-container">
                    <span class="rw-time-current">0:00</span>
                    <div class="rw-progress-bar">
                        <div class="rw-progress-fill"></div>
                    </div>
                    <span class="rw-time-total">0:00</span>
                </div>
            `;
        }

        _renderVolumeControl() {
            return `
                <div class="rw-volume-control">
                    <button class="rw-btn rw-mute-btn" data-action="toggleMute" title="Mute">
                        <svg class="rw-icon-volume" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
                        </svg>
                        <svg class="rw-icon-muted" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                        </svg>
                    </button>
                    <input type="range" class="rw-volume-slider" min="0" max="100" value="100" data-action="volume">
                </div>
            `;
        }

        _renderQueuePreview() {
            return `
                <div class="rw-queue-preview" data-count="3">
                    <h4>Up Next</h4>
                    <div class="rw-queue-items">
                        <div class="rw-queue-empty">Loading...</div>
                    </div>
                </div>
            `;
        }

        _renderBranding() {
            return `
                <div class="rw-branding">
                    <a href="https://valpatel.com" target="_blank" rel="noopener noreferrer" class="rw-branding-link" title="Powered by Valpatel Software">
                        <img src="https://localhost:5309/static/graphlings/logo-104.png" alt="Valpatel" class="rw-branding-logo">
                        <span class="rw-branding-text">Powered by Sound Box</span>
                    </a>
                </div>
            `;
        }

        _attachControlHandlers() {
            // Play/pause
            this.container.querySelectorAll('[data-action="toggle"]').forEach(btn => {
                btn.addEventListener('click', () => this.core.toggle());
            });

            // Skip buttons
            this.container.querySelectorAll('[data-action="previous"]').forEach(btn => {
                btn.addEventListener('click', () => this.core.previous());
            });
            this.container.querySelectorAll('[data-action="next"]').forEach(btn => {
                btn.addEventListener('click', () => this.core.next());
            });

            // Mute
            this.container.querySelectorAll('[data-action="toggleMute"]').forEach(btn => {
                btn.addEventListener('click', () => this.core.toggleMute());
            });

            // Volume slider
            this.container.querySelectorAll('[data-action="volume"]').forEach(slider => {
                slider.addEventListener('input', (e) => {
                    this.core.setVolume(parseInt(e.target.value) / 100);
                });
            });

            // Progress bar seek
            const progressBar = this.container.querySelector('.rw-progress-bar');
            if (progressBar) {
                progressBar.addEventListener('click', (e) => {
                    const rect = progressBar.getBoundingClientRect();
                    const percent = (e.clientX - rect.left) / rect.width;
                    this.core.seek(percent * this.core.getDuration());
                });
            }
        }

        _setupEventListeners() {
            this.core.on('trackChange', (track) => this._updateNowPlaying(track));
            this.core.on('playStateChange', (isPlaying) => this._updatePlayState(isPlaying));
            this.core.on('queueUpdate', (queue) => this._updateQueue(queue));
            this.core.on('volumeChange', (volume) => this._updateVolume(volume));
            this.core.on('muteChange', (muted) => this._updateMute(muted));
            this.core.on('timeUpdate', (data) => this._updateProgress(data));
            this.core.on('loading', (loading) => this._updateLoading(loading));
        }

        _updateNowPlaying(track) {
            const titleEl = this.container.querySelector('.rw-track-title');
            const durationEl = this.container.querySelector('.rw-track-duration');

            if (titleEl) {
                const title = track.prompt || 'Unknown track';
                titleEl.textContent = title.length > 60 ? title.slice(0, 60) + '...' : title;
            }
            if (durationEl) durationEl.textContent = track.duration ? `${track.duration}s` : '';
        }

        _updatePlayState(isPlaying) {
            const playBtn = this.container.querySelector('.rw-play-btn');
            if (playBtn) {
                playBtn.classList.toggle('playing', isPlaying);
            }
        }

        _updateQueue(queue) {
            const queueItems = this.container.querySelector('.rw-queue-items');
            if (!queueItems) return;

            const count = 3;
            queueItems.innerHTML = queue.slice(0, count).map((track, i) => `
                <div class="rw-queue-item">
                    <span class="rw-queue-num">${i + 1}</span>
                    <span class="rw-queue-title">${this._escapeHtml((track.prompt || 'Unknown').slice(0, 50))}</span>
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

        _updateLoading(loading) {
            this.container.classList.toggle('loading', loading);
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

        // Public API
        play() { this.core.play(); }
        pause() { this.core.pause(); }
        toggle() { this.core.toggle(); }
        next() { this.core.next(); }
        previous() { this.core.previous(); }
        setVolume(level) { this.core.setVolume(level); }
        toggleMute() { this.core.toggleMute(); }

        setStation(station) {
            return this.core.loadStation(station, { autoPlay: true });
        }

        setTemplate(template) {
            this.container.setAttribute('data-template', template);
        }

        on(event, callback) {
            return this.core.on(event, callback);
        }

        destroy() {
            this.core.destroy();
            this.container.innerHTML = '';
            this.container.className = '';
        }
    }

    // ========================================
    // PUBLIC API
    // ========================================
    const GraphlingsRadio = {
        version: VERSION,
        _instances: new Map(),
        _instanceId: 0,

        /**
         * Initialize a radio widget
         * @param {string|HTMLElement} container - Container element or CSS selector
         * @param {Object} options - Widget options
         * @returns {GraphlingsRadioWidget} Widget instance
         */
        init(container, options = {}) {
            const widget = new GraphlingsRadioWidget(container, options);
            const id = `graphlings_radio_${++this._instanceId}`;
            this._instances.set(id, widget);
            widget._id = id;
            return widget;
        },

        /**
         * Get a widget instance by ID
         */
        get(id) {
            return this._instances.get(id) || null;
        },

        /**
         * Destroy a widget instance
         */
        destroy(id) {
            const widget = this._instances.get(id);
            if (widget) {
                widget.destroy();
                this._instances.delete(id);
            }
        },

        /**
         * Destroy all widget instances
         */
        destroyAll() {
            this._instances.forEach(widget => widget.destroy());
            this._instances.clear();
        }
    };

    // Export to window
    window.GraphlingsRadio = GraphlingsRadio;

    // Auto-init widgets with data-graphlings-radio attribute
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-graphlings-radio]').forEach(el => {
            const options = {};
            if (el.dataset.size) options.size = el.dataset.size;
            if (el.dataset.template) options.template = el.dataset.template;
            if (el.dataset.station) options.station = el.dataset.station;
            if (el.dataset.autoplay === 'true') options.autoPlay = true;
            GraphlingsRadio.init(el, options);
        });
    });

})(window, document);
