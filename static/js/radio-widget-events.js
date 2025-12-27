/**
 * Radio Widget Event Emitter
 * Simple event system for widget state changes
 */

class RadioWidgetEvents {
    constructor() {
        this._listeners = new Map();
    }

    /**
     * Register an event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     * @returns {Function} Unsubscribe function
     */
    on(event, callback) {
        if (!this._listeners.has(event)) {
            this._listeners.set(event, new Set());
        }
        this._listeners.get(event).add(callback);

        // Return unsubscribe function
        return () => this.off(event, callback);
    }

    /**
     * Register a one-time event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    once(event, callback) {
        const wrapper = (...args) => {
            this.off(event, wrapper);
            callback(...args);
        };
        this.on(event, wrapper);
    }

    /**
     * Remove an event listener
     * @param {string} event - Event name
     * @param {Function} callback - Callback function
     */
    off(event, callback) {
        if (this._listeners.has(event)) {
            this._listeners.get(event).delete(callback);
        }
    }

    /**
     * Emit an event
     * @param {string} event - Event name
     * @param {...any} args - Arguments to pass to listeners
     */
    emit(event, ...args) {
        if (this._listeners.has(event)) {
            this._listeners.get(event).forEach(callback => {
                try {
                    callback(...args);
                } catch (err) {
                    console.error(`[RadioWidget] Error in ${event} listener:`, err);
                }
            });
        }
    }

    /**
     * Remove all listeners for an event (or all events)
     * @param {string} [event] - Event name (optional)
     */
    removeAllListeners(event) {
        if (event) {
            this._listeners.delete(event);
        } else {
            this._listeners.clear();
        }
    }

    /**
     * Get listener count for an event
     * @param {string} event - Event name
     * @returns {number} Number of listeners
     */
    listenerCount(event) {
        return this._listeners.has(event) ? this._listeners.get(event).size : 0;
    }
}

// Event name constants for type safety
const RADIO_EVENTS = {
    // Playback events
    TRACK_CHANGE: 'trackChange',
    PLAY_STATE_CHANGE: 'playStateChange',
    TIME_UPDATE: 'timeUpdate',
    ENDED: 'ended',

    // Queue events
    QUEUE_UPDATE: 'queueUpdate',
    QUEUE_EMPTY: 'queueEmpty',

    // Volume events
    VOLUME_CHANGE: 'volumeChange',
    MUTE_CHANGE: 'muteChange',

    // Mood/Station events
    MOOD_CHANGE: 'moodChange',
    STATION_CHANGE: 'stationChange',

    // User interaction events
    VOTE: 'vote',
    FAVORITE: 'favorite',

    // Error events
    ERROR: 'error',
    LOAD_ERROR: 'loadError',

    // Widget lifecycle events
    READY: 'ready',
    DESTROY: 'destroy',
    SIZE_CHANGE: 'sizeChange',
    TEMPLATE_CHANGE: 'templateChange'
};

// Export for ES modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RadioWidgetEvents, RADIO_EVENTS };
}
