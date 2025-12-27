/**
 * Radio Widget Core
 * Encapsulated state management and playback logic
 */

class RadioWidgetCore {
    /**
     * Create a new radio widget instance
     * @param {Object} options - Configuration options
     * @param {string} [options.apiBaseUrl=''] - Base URL for API calls
     * @param {string} [options.userId=null] - User ID for votes/favorites
     * @param {HTMLAudioElement} [options.audioElement=null] - Existing audio element to use
     * @param {boolean} [options.autoPlay=false] - Auto-play on track load
     */
    constructor(options = {}) {
        // Configuration
        this.apiBaseUrl = options.apiBaseUrl || '';
        this.userId = options.userId || null;
        this.autoPlay = options.autoPlay || false;

        // Constants
        this.MAX_HISTORY = 50;
        this.MIN_QUEUE_SIZE = 3;

        // State
        this.queue = [];
        this.currentTrack = null;
        this.playHistory = [];       // Track IDs to avoid repeats
        this.recentlyPlayed = [];    // Full track objects for "previous"
        this.isPlaying = false;
        this.volume = 1.0;
        this.isMuted = false;
        this.currentStation = null;
        this.currentMood = null;
        this.isFetchingMore = false;

        // User interaction state
        this.currentVote = 0;        // -1, 0, or 1
        this.isFavorited = false;

        // Event emitter
        if (typeof RadioWidgetEvents !== 'undefined') {
            this._events = new RadioWidgetEvents();
        } else {
            // Inline fallback if events module not loaded
            this._events = {
                _listeners: new Map(),
                on(event, cb) {
                    if (!this._listeners.has(event)) this._listeners.set(event, new Set());
                    this._listeners.get(event).add(cb);
                    return () => this.off(event, cb);
                },
                off(event, cb) {
                    if (this._listeners.has(event)) this._listeners.get(event).delete(cb);
                },
                emit(event, ...args) {
                    if (this._listeners.has(event)) {
                        this._listeners.get(event).forEach(cb => {
                            try { cb(...args); } catch (e) { console.error(e); }
                        });
                    }
                },
                removeAllListeners() { this._listeners.clear(); }
            };
        }

        // Audio element
        this.audioElement = options.audioElement || this._createAudioElement();
        this._setupAudioListeners();

        // Restore persisted state
        this._restoreState();
    }

    // ========================================
    // EVENT API
    // ========================================

    /**
     * Subscribe to an event
     * @param {string} event - Event name
     * @param {Function} callback - Event handler
     * @returns {Function} Unsubscribe function
     */
    on(event, callback) {
        return this._events.on(event, callback);
    }

    /**
     * Unsubscribe from an event
     * @param {string} event - Event name
     * @param {Function} callback - Event handler
     */
    off(event, callback) {
        this._events.off(event, callback);
    }

    // ========================================
    // PLAYBACK CONTROLS
    // ========================================

    /**
     * Start or resume playback
     */
    play() {
        if (this.audioElement.src) {
            this._autoUnmute();
            this.audioElement.play().catch(err => {
                console.error('[RadioWidget] Play failed:', err);
                this._events.emit('error', { type: 'playback', error: err });
            });
        } else if (this.queue.length > 0) {
            this.next();
        }
    }

    /**
     * Pause playback
     */
    pause() {
        this.audioElement.pause();
    }

    /**
     * Toggle play/pause
     */
    toggle() {
        if (this.isPlaying) {
            this.pause();
        } else {
            this.play();
        }
    }

    /**
     * Skip to next track
     */
    next() {
        this._playNextTrack();
    }

    /**
     * Go to previous track
     */
    previous() {
        if (this.recentlyPlayed.length === 0) {
            this._events.emit('error', { type: 'navigation', message: 'No previous tracks' });
            return;
        }

        // Put current track back in queue
        if (this.currentTrack) {
            this.queue.unshift(this.currentTrack);
        }

        // Get previous track
        const previousTrack = this.recentlyPlayed.pop();
        this._setCurrentTrack(previousTrack);
    }

    /**
     * Skip current track (alias for next)
     */
    skip() {
        this.next();
    }

    /**
     * Set volume level
     * @param {number} level - Volume from 0.0 to 1.0
     */
    setVolume(level) {
        this.volume = Math.max(0, Math.min(1, level));
        this.audioElement.volume = this.volume;
        localStorage.setItem('soundbox_volume', this.volume);
        this._events.emit('volumeChange', this.volume);
    }

    /**
     * Get current volume
     * @returns {number} Current volume (0.0 - 1.0)
     */
    getVolume() {
        return this.volume;
    }

    /**
     * Toggle mute state
     */
    toggleMute() {
        this.isMuted = !this.isMuted;
        this.audioElement.muted = this.isMuted;
        localStorage.setItem('soundbox_muted', this.isMuted);
        this._events.emit('muteChange', this.isMuted);
    }

    /**
     * Set mute state
     * @param {boolean} muted - Mute state
     */
    setMuted(muted) {
        this.isMuted = muted;
        this.audioElement.muted = this.isMuted;
        localStorage.setItem('soundbox_muted', this.isMuted);
        this._events.emit('muteChange', this.isMuted);
    }

    /**
     * Seek to position in current track
     * @param {number} time - Time in seconds
     */
    seek(time) {
        if (this.audioElement.src) {
            this.audioElement.currentTime = Math.max(0, Math.min(time, this.audioElement.duration || 0));
        }
    }

    /**
     * Get current playback time
     * @returns {number} Current time in seconds
     */
    getCurrentTime() {
        return this.audioElement.currentTime;
    }

    /**
     * Get track duration
     * @returns {number} Duration in seconds
     */
    getDuration() {
        return this.audioElement.duration || 0;
    }

    // ========================================
    // QUEUE MANAGEMENT
    // ========================================

    /**
     * Load a station/playlist
     * @param {string} station - Station type: 'shuffle', 'favorites', 'top-rated', 'recent'
     * @param {Object} [options] - Station options
     * @param {string} [options.model] - Model filter ('music', 'sfx', 'all')
     * @param {string} [options.search] - Search keywords
     */
    async loadStation(station, options = {}) {
        this.currentStation = station;
        this.playHistory = [];
        this.recentlyPlayed = [];

        this._events.emit('stationChange', { station, options });

        try {
            let tracks;
            switch (station) {
                case 'shuffle':
                    tracks = await this._fetchShuffledTracks(options);
                    break;
                case 'favorites':
                    tracks = await this._fetchFavorites(options);
                    break;
                case 'top-rated':
                    tracks = await this._fetchTopRated(options);
                    break;
                case 'recent':
                    tracks = await this._fetchRecent(options);
                    break;
                default:
                    throw new Error(`Unknown station: ${station}`);
            }

            if (tracks && tracks.length > 0) {
                this.queue = tracks;
                this._events.emit('queueUpdate', this.queue);
                this.next();
            } else {
                this._events.emit('queueEmpty', { station, options });
            }
        } catch (err) {
            console.error('[RadioWidget] Failed to load station:', err);
            this._events.emit('error', { type: 'station', error: err });
        }
    }

    /**
     * Set mood for dynamic track selection
     * @param {string|Object} mood - Mood name or config object
     */
    async setMood(mood) {
        const moodConfig = typeof mood === 'string' ? this._getMoodConfig(mood) : mood;
        this.currentMood = moodConfig;

        this._events.emit('moodChange', moodConfig);

        // Clear queue and load mood-appropriate tracks
        this.queue = [];
        const options = {
            search: moodConfig.search || moodConfig.genres?.join(' OR '),
            model: moodConfig.model || 'music'
        };

        try {
            const tracks = await this._fetchShuffledTracks(options);
            if (tracks && tracks.length > 0) {
                this.queue = tracks;
                this._events.emit('queueUpdate', this.queue);

                // If fadeTransition requested, crossfade
                if (moodConfig.fadeTransition && this.isPlaying) {
                    await this._crossfadeToNext();
                } else {
                    this.next();
                }
            }
        } catch (err) {
            console.error('[RadioWidget] Failed to set mood:', err);
            this._events.emit('error', { type: 'mood', error: err });
        }
    }

    /**
     * Add a track to the queue
     * @param {Object|number} track - Track object or track ID
     * @param {boolean} [playNext=false] - Add to front of queue
     */
    async addToQueue(track, playNext = false) {
        let trackObj = track;

        // If just an ID, fetch track details
        if (typeof track === 'number' || typeof track === 'string') {
            trackObj = await this._fetchTrackById(track);
        }

        if (!trackObj) return;

        if (playNext) {
            this.queue.unshift(trackObj);
        } else {
            this.queue.push(trackObj);
        }

        this._events.emit('queueUpdate', this.queue);
    }

    /**
     * Remove a track from the queue
     * @param {number} index - Queue index to remove
     */
    removeFromQueue(index) {
        if (index >= 0 && index < this.queue.length) {
            this.queue.splice(index, 1);
            this._events.emit('queueUpdate', this.queue);
        }
    }

    /**
     * Clear the queue
     */
    clearQueue() {
        this.queue = [];
        this._events.emit('queueUpdate', this.queue);
    }

    /**
     * Get current queue
     * @returns {Array} Queue array
     */
    getQueue() {
        return [...this.queue];
    }

    /**
     * Get current track
     * @returns {Object|null} Current track or null
     */
    getCurrentTrack() {
        return this.currentTrack;
    }

    // ========================================
    // VOTING & FAVORITES
    // ========================================

    /**
     * Vote on current track
     * @param {number} value - Vote value: 1 (upvote), -1 (downvote), 0 (remove vote)
     * @param {Object} [options] - Additional options
     * @param {Array} [options.reasons] - Feedback reasons
     * @param {string} [options.suggestedModel] - Suggested reclassification
     */
    async vote(value, options = {}) {
        if (!this.currentTrack) return;

        const voterId = this.userId || this._getAnonymousId();

        try {
            const body = {
                generation_id: this.currentTrack.id,
                vote: value,
                user_id: voterId
            };

            if (options.reasons) body.reasons = options.reasons;
            if (options.suggestedModel) body.suggested_model = options.suggestedModel;

            const response = await fetch(`${this.apiBaseUrl}/api/library/vote`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            this.currentVote = value;

            // Update track vote counts
            if (this.currentTrack) {
                this.currentTrack.upvotes = data.upvotes;
                this.currentTrack.downvotes = data.downvotes;
            }

            this._events.emit('vote', {
                track: this.currentTrack,
                value,
                upvotes: data.upvotes,
                downvotes: data.downvotes
            });

        } catch (err) {
            console.error('[RadioWidget] Vote failed:', err);
            this._events.emit('error', { type: 'vote', error: err });
        }
    }

    /**
     * Toggle favorite status of current track
     */
    async toggleFavorite() {
        if (!this.currentTrack) return;

        const userId = this.userId || this._getAnonymousId();
        const action = this.isFavorited ? 'remove' : 'add';

        try {
            const response = await fetch(`${this.apiBaseUrl}/api/library/favorite`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    generation_id: this.currentTrack.id,
                    action,
                    user_id: userId
                })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            this.isFavorited = !this.isFavorited;
            this._events.emit('favorite', {
                track: this.currentTrack,
                isFavorited: this.isFavorited
            });

        } catch (err) {
            console.error('[RadioWidget] Favorite toggle failed:', err);
            this._events.emit('error', { type: 'favorite', error: err });
        }
    }

    // ========================================
    // LIFECYCLE
    // ========================================

    /**
     * Clean up resources
     * @param {Object} options - Cleanup options
     * @param {boolean} [options.preserveAudio=false] - Don't stop/clear audio (for shared audio elements)
     */
    destroy(options = {}) {
        this._events.emit('destroy');

        // Only stop audio if we're not preserving it (e.g., shared audio element)
        if (!options.preserveAudio) {
            this.audioElement.pause();
            this.audioElement.src = '';
        }

        this._events.removeAllListeners();
    }

    /**
     * Get serializable state for persistence/sync
     * @returns {Object} State object
     */
    getState() {
        return {
            queue: this.queue,
            currentTrack: this.currentTrack,
            playHistory: this.playHistory,
            isPlaying: this.isPlaying,
            volume: this.volume,
            isMuted: this.isMuted,
            currentStation: this.currentStation,
            currentMood: this.currentMood,
            currentTime: this.audioElement.currentTime
        };
    }

    /**
     * Restore state from object
     * @param {Object} state - State object
     */
    setState(state) {
        if (state.queue) this.queue = state.queue;
        if (state.currentTrack) this._setCurrentTrack(state.currentTrack, false);
        if (state.playHistory) this.playHistory = state.playHistory;
        if (typeof state.volume === 'number') this.setVolume(state.volume);
        if (typeof state.isMuted === 'boolean') this.setMuted(state.isMuted);
        if (state.currentStation) this.currentStation = state.currentStation;
        if (state.currentMood) this.currentMood = state.currentMood;
        if (typeof state.currentTime === 'number') this.seek(state.currentTime);
        if (state.isPlaying) this.play();
    }

    // ========================================
    // PRIVATE METHODS
    // ========================================

    _createAudioElement() {
        const audio = document.createElement('audio');
        audio.preload = 'auto';
        return audio;
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
            this._events.emit('ended', this.currentTrack);
            this._playNextTrack();
        });

        this.audioElement.addEventListener('timeupdate', () => {
            this._events.emit('timeUpdate', {
                currentTime: this.audioElement.currentTime,
                duration: this.audioElement.duration
            });
        });

        this.audioElement.addEventListener('error', (e) => {
            console.error('[RadioWidget] Audio error:', e);
            this._events.emit('loadError', { track: this.currentTrack, error: e });
            // Try next track on error
            this._playNextTrack();
        });
    }

    _restoreState() {
        // Restore volume
        const savedVolume = localStorage.getItem('soundbox_volume');
        if (savedVolume !== null) {
            this.volume = parseFloat(savedVolume);
            this.audioElement.volume = this.volume;
        }

        // Restore mute state
        this.isMuted = localStorage.getItem('soundbox_muted') === 'true';
        this.audioElement.muted = this.isMuted;
    }

    _autoUnmute() {
        if (this.isMuted) {
            this.isMuted = false;
            this.audioElement.muted = false;
            localStorage.setItem('soundbox_muted', 'false');
            this._events.emit('muteChange', false);
        }
    }

    _playNextTrack() {
        if (this.queue.length === 0) {
            this.currentTrack = null;
            this._events.emit('queueEmpty', { station: this.currentStation });
            return;
        }

        // Save current to recently played
        if (this.currentTrack) {
            this.recentlyPlayed.push(this.currentTrack);
            if (this.recentlyPlayed.length > 20) {
                this.recentlyPlayed = this.recentlyPlayed.slice(-20);
            }
        }

        const nextTrack = this.queue.shift();
        this._setCurrentTrack(nextTrack);
        this._events.emit('queueUpdate', this.queue);

        // Auto-fetch more if running low
        if (this.queue.length < this.MIN_QUEUE_SIZE) {
            this._fetchMoreTracks();
        }
    }

    _setCurrentTrack(track, autoPlay = true) {
        // Skip invalid tracks
        if (!track || !track.filename) {
            console.warn('[RadioWidget] Skipping invalid track:', track);
            this._playNextTrack();
            return;
        }

        this.currentTrack = track;

        // Add to history
        if (track.id && !this.playHistory.includes(track.id)) {
            this.playHistory.push(track.id);
            if (this.playHistory.length > this.MAX_HISTORY) {
                this.playHistory = this.playHistory.slice(-this.MAX_HISTORY);
            }
        }

        // Reset vote/favorite state
        this.currentVote = 0;
        this.isFavorited = false;

        // Load audio
        const audioUrl = track.filename.startsWith('http')
            ? track.filename
            : `${this.apiBaseUrl}/audio/${track.filename}`;
        this.audioElement.src = audioUrl;

        if (autoPlay) {
            this._autoUnmute();
            this.audioElement.play().catch(err => {
                console.error('[RadioWidget] Auto-play failed:', err);
            });
        }

        this._events.emit('trackChange', track);

        // Load vote/favorite status
        this._loadTrackVote();
        this._loadTrackFavorite();
    }

    async _loadTrackVote() {
        if (!this.currentTrack) return;

        try {
            const voterId = this.userId || this._getAnonymousId();
            const response = await fetch(`${this.apiBaseUrl}/api/library/votes`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    generation_ids: [this.currentTrack.id],
                    user_id: voterId
                })
            });

            if (!response.ok) return;

            const data = await response.json();
            this.currentVote = data.votes?.[this.currentTrack.id] || 0;
        } catch (err) {
            console.error('[RadioWidget] Failed to load vote:', err);
        }
    }

    async _loadTrackFavorite() {
        if (!this.currentTrack) return;

        try {
            const userId = this.userId || this._getAnonymousId();
            const response = await fetch(
                `${this.apiBaseUrl}/api/library/favorite/check?generation_id=${this.currentTrack.id}&user_id=${userId}`
            );

            if (!response.ok) return;

            const data = await response.json();
            this.isFavorited = data.is_favorite || false;
        } catch (err) {
            console.error('[RadioWidget] Failed to check favorite:', err);
        }
    }

    async _fetchShuffledTracks(options = {}) {
        const params = new URLSearchParams({
            model: options.model || 'music',
            count: options.count || 10
        });
        if (options.search) params.set('search', options.search);

        const response = await fetch(`${this.apiBaseUrl}/api/radio/shuffle?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        return data.tracks || [];
    }

    async _fetchFavorites(options = {}) {
        const userId = this.userId || this._getAnonymousId();
        const params = new URLSearchParams({
            user_id: userId,
            count: options.count || 10
        });
        if (options.model) params.set('model', options.model);

        const response = await fetch(`${this.apiBaseUrl}/api/radio/favorites?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        return data.tracks || [];
    }

    async _fetchTopRated(options = {}) {
        const params = new URLSearchParams({
            count: options.count || 10,
            sort: 'rating'
        });
        if (options.model) params.set('model', options.model);

        const response = await fetch(`${this.apiBaseUrl}/api/radio/shuffle?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        return data.tracks || [];
    }

    async _fetchRecent(options = {}) {
        const params = new URLSearchParams({
            count: options.count || 10,
            sort: 'recent'
        });
        if (options.model) params.set('model', options.model);

        const response = await fetch(`${this.apiBaseUrl}/api/radio/shuffle?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        return data.tracks || [];
    }

    async _fetchMoreTracks() {
        if (this.isFetchingMore) return;
        this.isFetchingMore = true;

        try {
            const excludeIds = [
                ...this.playHistory,
                ...this.queue.map(t => t.id).filter(Boolean)
            ];

            const params = new URLSearchParams({
                model: 'music',
                count: 5
            });

            if (this.currentMood?.search) {
                params.set('search', this.currentMood.search);
            }

            if (excludeIds.length > 0) {
                params.set('exclude', excludeIds.join(','));
            }

            const response = await fetch(`${this.apiBaseUrl}/api/radio/next?${params}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            if (data.tracks && data.tracks.length > 0) {
                this.queue.push(...data.tracks);
                this._events.emit('queueUpdate', this.queue);
            }
        } catch (err) {
            console.error('[RadioWidget] Failed to fetch more tracks:', err);
        } finally {
            this.isFetchingMore = false;
        }
    }

    async _fetchTrackById(id) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/library/${id}`);
            if (!response.ok) return null;
            return await response.json();
        } catch (err) {
            console.error('[RadioWidget] Failed to fetch track:', err);
            return null;
        }
    }

    async _crossfadeToNext() {
        // Simple crossfade implementation
        const fadeTime = 2000; // 2 seconds
        const steps = 20;
        const stepTime = fadeTime / steps;
        const volumeStep = this.volume / steps;

        // Fade out
        for (let i = 0; i < steps; i++) {
            await new Promise(r => setTimeout(r, stepTime));
            this.audioElement.volume = Math.max(0, this.volume - (volumeStep * (i + 1)));
        }

        // Switch track
        const nextTrack = this.queue.shift();
        if (nextTrack) {
            this._setCurrentTrack(nextTrack, false);
            this.audioElement.volume = 0;
            this.audioElement.play();

            // Fade in
            for (let i = 0; i < steps; i++) {
                await new Promise(r => setTimeout(r, stepTime));
                this.audioElement.volume = Math.min(this.volume, volumeStep * (i + 1));
            }
        }
    }

    _getMoodConfig(moodName) {
        const MOOD_MAPPINGS = {
            'intense': { search: 'intense OR epic OR battle OR action', model: 'music' },
            'calm': { search: 'ambient OR peaceful OR relaxing OR calm', model: 'music' },
            'victory': { search: 'triumphant OR celebration OR victory OR epic', model: 'music' },
            'suspense': { search: 'suspense OR tense OR mysterious OR dark', model: 'music' },
            'happy': { search: 'happy OR upbeat OR cheerful OR fun', model: 'music' },
            'sad': { search: 'sad OR melancholy OR emotional', model: 'music' },
            'energetic': { search: 'energetic OR fast OR upbeat OR driving', model: 'music' },
            'chill': { search: 'chill OR lofi OR relaxed OR ambient', model: 'music' }
        };

        return MOOD_MAPPINGS[moodName] || { search: moodName, model: 'music' };
    }

    _getAnonymousId() {
        let anonId = localStorage.getItem('soundbox_anon_id');
        if (!anonId) {
            anonId = 'anon_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('soundbox_anon_id', anonId);
        }
        return anonId;
    }
}

// Export for ES modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RadioWidgetCore };
}
