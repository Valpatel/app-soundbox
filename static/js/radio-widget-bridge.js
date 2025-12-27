/**
 * Radio Widget - Cross-App Communication Bridge
 * Enables seamless playback sync across tabs and embedded widgets
 *
 * Uses BroadcastChannel API with localStorage fallback for wider browser support
 */

class RadioWidgetBridge {
    constructor(options = {}) {
        this.tabId = this._generateTabId();
        this.isController = false;
        this.listeners = new Map();
        this.lastKnownState = null;
        this.heartbeatInterval = null;

        // Configuration
        this.channelName = options.channelName || 'graphlings-radio-sync';
        this.heartbeatMs = options.heartbeatMs || 2000;
        this.staleThresholdMs = options.staleThresholdMs || 5000;

        // Try BroadcastChannel, fall back to localStorage
        this.useLocalStorage = !('BroadcastChannel' in window);

        if (this.useLocalStorage) {
            this._initLocalStorageFallback();
        } else {
            this._initBroadcastChannel();
        }

        // Start heartbeat
        this._startHeartbeat();

        // Register this tab
        this._registerTab();

        console.log(`[RadioBridge] Initialized (${this.useLocalStorage ? 'localStorage' : 'BroadcastChannel'}) - Tab: ${this.tabId}`);
    }

    // ========================================
    // PUBLIC API
    // ========================================

    /**
     * Broadcast current playback state to other tabs
     * @param {Object} state - Current playback state
     */
    broadcastState(state) {
        this.lastKnownState = state;
        this._send({
            type: 'STATE_UPDATE',
            tabId: this.tabId,
            state,
            timestamp: Date.now()
        });
    }

    /**
     * Request to take control of playback
     * Other tabs should pause when this is received
     */
    requestControl() {
        this._send({
            type: 'CONTROL_REQUEST',
            tabId: this.tabId,
            timestamp: Date.now()
        });
        this.isController = true;
    }

    /**
     * Announce that this tab has relinquished control
     */
    releaseControl() {
        this.isController = false;
        this._send({
            type: 'CONTROL_RELEASED',
            tabId: this.tabId,
            timestamp: Date.now()
        });
    }

    /**
     * Request current state from controller tab
     */
    requestState() {
        this._send({
            type: 'STATE_REQUEST',
            tabId: this.tabId,
            timestamp: Date.now()
        });
    }

    /**
     * Send a command to the controller tab
     * @param {string} command - Command name (play, pause, next, etc.)
     * @param {*} payload - Optional command payload
     */
    sendCommand(command, payload = null) {
        this._send({
            type: 'COMMAND',
            command,
            payload,
            tabId: this.tabId,
            timestamp: Date.now()
        });
    }

    /**
     * Listen for bridge events
     * @param {string} event - Event type
     * @param {Function} callback - Event handler
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, new Set());
        }
        this.listeners.get(event).add(callback);
        return () => this.off(event, callback);
    }

    /**
     * Remove event listener
     */
    off(event, callback) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            callbacks.delete(callback);
        }
    }

    /**
     * Get list of active tabs
     * @returns {Array} Active tab info
     */
    getActiveTabs() {
        const tabs = JSON.parse(localStorage.getItem(`${this.channelName}_tabs`) || '{}');
        const now = Date.now();
        const activeTabs = [];

        for (const [tabId, info] of Object.entries(tabs)) {
            if (now - info.lastSeen < this.staleThresholdMs) {
                activeTabs.push({
                    tabId,
                    isController: info.isController,
                    lastSeen: info.lastSeen
                });
            }
        }

        return activeTabs;
    }

    /**
     * Check if another tab is currently controlling playback
     * @returns {boolean} True if another tab is controller
     */
    hasActiveController() {
        const tabs = this.getActiveTabs();
        return tabs.some(tab => tab.isController && tab.tabId !== this.tabId);
    }

    /**
     * Cleanup resources
     */
    destroy() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }

        if (this.channel) {
            this.channel.close();
        }

        if (this.useLocalStorage) {
            window.removeEventListener('storage', this._storageHandler);
        }

        this._unregisterTab();
        this.listeners.clear();
    }

    // ========================================
    // PRIVATE METHODS
    // ========================================

    _generateTabId() {
        return `tab_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    _initBroadcastChannel() {
        this.channel = new BroadcastChannel(this.channelName);
        this.channel.onmessage = (event) => this._handleMessage(event.data);
    }

    _initLocalStorageFallback() {
        this._storageHandler = (event) => {
            if (event.key === `${this.channelName}_message`) {
                try {
                    const data = JSON.parse(event.newValue);
                    if (data && data.tabId !== this.tabId) {
                        this._handleMessage(data);
                    }
                } catch (e) {
                    // Ignore parse errors
                }
            }
        };
        window.addEventListener('storage', this._storageHandler);
    }

    _send(message) {
        if (this.useLocalStorage) {
            // Use localStorage for cross-tab communication
            localStorage.setItem(
                `${this.channelName}_message`,
                JSON.stringify(message)
            );
            // Clear it shortly after to allow same message to be sent again
            setTimeout(() => {
                localStorage.removeItem(`${this.channelName}_message`);
            }, 50);
        } else {
            this.channel.postMessage(message);
        }
    }

    _handleMessage(data) {
        if (data.tabId === this.tabId) return; // Ignore our own messages

        switch (data.type) {
            case 'STATE_UPDATE':
                this._emit('stateUpdate', data.state, data.tabId);
                break;

            case 'CONTROL_REQUEST':
                // Another tab wants control
                if (this.isController) {
                    this.isController = false;
                    this._emit('controlLost', data.tabId);
                }
                break;

            case 'CONTROL_RELEASED':
                this._emit('controlReleased', data.tabId);
                break;

            case 'STATE_REQUEST':
                // Another tab is asking for current state
                if (this.isController && this.lastKnownState) {
                    this.broadcastState(this.lastKnownState);
                }
                break;

            case 'COMMAND':
                // Remote command from another tab
                if (this.isController) {
                    this._emit('command', data.command, data.payload, data.tabId);
                }
                break;

            case 'HEARTBEAT':
                // Just update the tab registry
                break;
        }
    }

    _emit(event, ...args) {
        const callbacks = this.listeners.get(event);
        if (callbacks) {
            callbacks.forEach(cb => {
                try {
                    cb(...args);
                } catch (e) {
                    console.error('[RadioBridge] Event handler error:', e);
                }
            });
        }
    }

    _registerTab() {
        const tabs = JSON.parse(localStorage.getItem(`${this.channelName}_tabs`) || '{}');
        tabs[this.tabId] = {
            isController: this.isController,
            lastSeen: Date.now()
        };
        localStorage.setItem(`${this.channelName}_tabs`, JSON.stringify(tabs));
    }

    _unregisterTab() {
        const tabs = JSON.parse(localStorage.getItem(`${this.channelName}_tabs`) || '{}');
        delete tabs[this.tabId];
        localStorage.setItem(`${this.channelName}_tabs`, JSON.stringify(tabs));
    }

    _startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            this._registerTab();
            this._cleanupStaleTabs();

            this._send({
                type: 'HEARTBEAT',
                tabId: this.tabId,
                isController: this.isController,
                timestamp: Date.now()
            });
        }, this.heartbeatMs);
    }

    _cleanupStaleTabs() {
        const tabs = JSON.parse(localStorage.getItem(`${this.channelName}_tabs`) || '{}');
        const now = Date.now();
        let changed = false;

        for (const [tabId, info] of Object.entries(tabs)) {
            if (now - info.lastSeen > this.staleThresholdMs) {
                delete tabs[tabId];
                changed = true;
            }
        }

        if (changed) {
            localStorage.setItem(`${this.channelName}_tabs`, JSON.stringify(tabs));
        }
    }
}


/**
 * Sync Manager - High-level sync functionality for widget core
 */
class RadioWidgetSyncManager {
    constructor(widgetCore, options = {}) {
        this.core = widgetCore;
        this.bridge = new RadioWidgetBridge(options);
        this.syncEnabled = options.syncEnabled !== false;
        this.autoTakeControl = options.autoTakeControl !== false;

        if (this.syncEnabled) {
            this._setupSync();
        }
    }

    _setupSync() {
        // When we start playing, request control
        this.core.on('playStateChange', (isPlaying) => {
            if (isPlaying && this.autoTakeControl) {
                this.bridge.requestControl();
            }
            this._broadcastCurrentState();
        });

        // Broadcast state changes
        this.core.on('trackChange', () => this._broadcastCurrentState());
        this.core.on('queueUpdate', () => this._broadcastCurrentState());
        this.core.on('timeUpdate', (data) => {
            // Only broadcast time updates every 5 seconds to reduce noise
            if (Math.floor(data.currentTime) % 5 === 0) {
                this._broadcastCurrentState();
            }
        });

        // Handle incoming state updates (when we're not controller)
        this.bridge.on('stateUpdate', (state, fromTab) => {
            if (!this.bridge.isController) {
                this._applyRemoteState(state);
            }
        });

        // Handle control loss
        this.bridge.on('controlLost', () => {
            // Another tab took over - pause our playback
            this.core.pause();
        });

        // Handle remote commands (when we're controller)
        this.bridge.on('command', (command, payload, fromTab) => {
            this._handleRemoteCommand(command, payload);
        });

        // Request current state on init
        this.bridge.requestState();
    }

    _broadcastCurrentState() {
        if (!this.bridge.isController) return;

        this.bridge.broadcastState({
            track: this.core.currentTrack,
            queue: this.core.queue.slice(0, 10), // Only first 10 items
            isPlaying: this.core.isPlaying,
            currentTime: this.core.getCurrentTime(),
            volume: this.core.volume,
            isMuted: this.core.isMuted
        });
    }

    _applyRemoteState(state) {
        // Update UI to reflect remote state
        if (state.track) {
            this.core._events.emit('trackChange', state.track);
        }
        if (state.queue) {
            this.core._events.emit('queueUpdate', state.queue);
        }
        this.core._events.emit('playStateChange', state.isPlaying);
        this.core._events.emit('volumeChange', state.volume);
        this.core._events.emit('muteChange', state.isMuted);
    }

    _handleRemoteCommand(command, payload) {
        switch (command) {
            case 'play':
                this.core.play();
                break;
            case 'pause':
                this.core.pause();
                break;
            case 'next':
                this.core.next();
                break;
            case 'previous':
                this.core.previous();
                break;
            case 'setVolume':
                this.core.setVolume(payload);
                break;
            case 'toggleMute':
                this.core.toggleMute();
                break;
            case 'seek':
                this.core.seek(payload);
                break;
        }
    }

    /**
     * Send command to controller tab
     */
    sendRemoteCommand(command, payload = null) {
        if (this.bridge.isController) {
            // We are controller, execute directly
            this._handleRemoteCommand(command, payload);
        } else {
            // Send to controller
            this.bridge.sendCommand(command, payload);
        }
    }

    destroy() {
        this.bridge.destroy();
    }
}


// Global exports
if (typeof window !== 'undefined') {
    window.RadioWidgetBridge = RadioWidgetBridge;
    window.RadioWidgetSyncManager = RadioWidgetSyncManager;
}

// ES module export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RadioWidgetBridge, RadioWidgetSyncManager };
}
