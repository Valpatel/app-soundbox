/**
 * Radio Widget Audio Visualizer
 * Canvas-based audio visualizations with epic intro and parallax effects
 *
 * Core class - visualization modes are loaded from separate files in /visualizations/
 */

class RadioWidgetVisualizer {
    constructor(canvas, audioElement) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.audioElement = audioElement;
        this.animationId = null;
        this.isActive = false;

        // Audio analysis
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.source = null;

        // Visualization settings
        this.mode = 'random';
        this.colors = {
            primary: '#a855f7',
            secondary: '#6366f1',
            tertiary: '#22d3ee'
        };
        this.currentTheme = 'purple';

        // Intro animation state
        this.introPhase = 'speck'; // 'speck', 'grow', 'explode', 'active'
        this.introProgress = 0;
        this.introStartTime = 0;

        // Parallax layers
        this.bgParticles = [];
        this.midParticles = [];
        this.fgParticles = [];

        // Particles for particle mode
        this.particles = [];
        this.maxParticles = 150;

        // Lissajous state
        this.lissajousTrail = [];
        this.lissajousPhase = 0;

        // Pong game state
        this.pongBall = { x: 0, y: 0, vx: 3, vy: 2 };
        this.pongPaddles = { left: 0.5, right: 0.5 };
        this.pongScore = { left: 0, right: 0 };
        this.pongTrail = [];

        // Tempest state
        this.tempestAngle = 0;
        this.tempestEnemies = [];
        this.tempestBullets = [];
        this.tempestPlayerPos = 0;
        this.tempestLevel = 0;
        this.tempestScore = 0;
        this.tempestExplosions = [];
        this.tempestShapes = ['circle', 'hexagon', 'octagon', 'star', 'square'];
        this.tempestCurrentShape = 'circle';

        // Breakout state
        this.breakoutBall = { x: 0, y: 0, vx: 4, vy: -4 };
        this.breakoutPaddle = 0.5;
        this.breakoutBricks = [];
        this.breakoutScore = 0;

        // Snake state
        this.snake = [];
        this.snakeDir = { x: 1, y: 0 };
        this.snakeFood = null;
        this.snakeScore = 0;
        this.snakeLastMove = 0;

        // Random mode state
        this.randomMode = 'bars';
        this.randomModeTimer = 0;
        this.allModes = ['bars', 'wave', 'circle', 'particles', 'lissajous', 'tempest', 'pong', 'breakout', 'snake'];

        // FPS monitoring
        this.fps = 60;
        this.frameCount = 0;
        this.lastFpsUpdate = 0;
        this.targetComplexity = 1.0;

        // Time tracking
        this.time = 0;
        this.lastTime = performance.now();

        // Bind methods
        this._draw = this._draw.bind(this);
        this._resize = this._resize.bind(this);

        // Setup
        this._setupResize();
        this._initParallaxLayers();
    }

    // ========================================
    // PUBLIC API
    // ========================================

    init() {
        try {
            if (this.audioElement._visualizerContext) {
                this.audioContext = this.audioElement._visualizerContext;
                this.analyser = this.audioElement._visualizerAnalyser;
                this.source = this.audioElement._visualizerSource;
                this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
                console.log('[Visualizer] Reusing existing audio context');
                return;
            }

            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 512;
            this.analyser.smoothingTimeConstant = 0.75;

            const bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(bufferLength);

            this.source = this.audioContext.createMediaElementSource(this.audioElement);
            this.source.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);

            this.audioElement._visualizerContext = this.audioContext;
            this.audioElement._visualizerAnalyser = this.analyser;
            this.audioElement._visualizerSource = this.source;

            console.log('[Visualizer] Audio context initialized');
        } catch (err) {
            console.error('[Visualizer] Failed to initialize:', err);
        }
    }

    start() {
        console.log('[Visualizer] start() called');

        if (!this.audioContext) {
            this.init();
        }

        if (this.audioContext?.state === 'suspended') {
            console.log('[Visualizer] Resuming suspended audio context');
            this.audioContext.resume();
        }

        // Reset intro animation
        this.introPhase = 'speck';
        this.introProgress = 0;
        this.introStartTime = performance.now();

        this.isActive = true;
        this._resize();
        this._initParallaxLayers();

        console.log('[Visualizer] Canvas dimensions:', this.canvas.width, 'x', this.canvas.height);
        console.log('[Visualizer] Audio context state:', this.audioContext?.state);

        // Ensure we have valid dimensions - if not, wait and retry
        if (this.canvas.width === 0 || this.canvas.height === 0) {
            console.warn('[Visualizer] Canvas has 0 dimensions, retrying resize');
            setTimeout(() => {
                this._resize();
                console.log('[Visualizer] Retry - Canvas dimensions:', this.canvas.width, 'x', this.canvas.height);
            }, 100);
        }

        this._draw();
    }

    stop() {
        this.isActive = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }

    setMode(mode) {
        this.mode = mode;
        if (mode === 'particles') {
            this._initParticles();
        }
        // Trigger mini intro on mode change
        this.introPhase = 'grow';
        this.introProgress = 0.5;
    }

    setColors(colors) {
        this.colors = { ...this.colors, ...colors };
        this._updateParticleColors();
    }

    setColorTheme(theme) {
        const themes = {
            purple: { primary: '#a855f7', secondary: '#6366f1', tertiary: '#22d3ee' },
            blue: { primary: '#3b82f6', secondary: '#06b6d4', tertiary: '#22d3ee' },
            green: { primary: '#22c55e', secondary: '#10b981', tertiary: '#6ee7b7' },
            cyan: { primary: '#00d4ff', secondary: '#0ea5e9', tertiary: '#67e8f9' },
            pink: { primary: '#ec4899', secondary: '#f43f5e', tertiary: '#fb7185' },
            rainbow: { primary: '#a855f7', secondary: '#22c55e', tertiary: '#00d4ff' }
        };

        if (themes[theme]) {
            this.colors = themes[theme];
            this.currentTheme = theme;
            this._updateParticleColors();
        }
    }

    destroy(options = {}) {
        this.stop();
        if (this.audioContext && !options.preserveAudio) {
            this.audioContext.close();
            this.audioContext = null;
        }
    }

    // ========================================
    // PRIVATE: SETUP & RESIZE
    // ========================================

    _setupResize() {
        const resizeObserver = new ResizeObserver(() => this._resize());
        resizeObserver.observe(this.canvas.parentElement || this.canvas);
    }

    _resize() {
        const parent = this.canvas.parentElement || document.body;
        const rect = parent.getBoundingClientRect();

        // Use window dimensions if parent has no size (e.g., in fullscreen)
        const width = rect.width || window.innerWidth;
        const height = rect.height || window.innerHeight;

        this.canvas.width = width * window.devicePixelRatio;
        this.canvas.height = height * window.devicePixelRatio;

        // Reset transform before scaling (prevents accumulation on multiple resizes)
        this.ctx.setTransform(1, 0, 0, 1, 0, 0);
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

        console.log('[Visualizer] Resized to:', width, 'x', height);
        this._initParallaxLayers();
    }

    // ========================================
    // PRIVATE: PARALLAX BACKGROUND
    // ========================================

    _initParallaxLayers() {
        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;

        // Background layer - slow moving, small particles
        this.bgParticles = [];
        for (let i = 0; i < 50 * this.targetComplexity; i++) {
            this.bgParticles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                size: Math.random() * 2 + 0.5,
                speed: 0.2 + Math.random() * 0.3,
                opacity: 0.2 + Math.random() * 0.2
            });
        }

        // Mid layer - medium speed, medium particles
        this.midParticles = [];
        for (let i = 0; i < 30 * this.targetComplexity; i++) {
            this.midParticles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                size: Math.random() * 3 + 1,
                speed: 0.5 + Math.random() * 0.5,
                opacity: 0.3 + Math.random() * 0.3,
                pulse: Math.random() * Math.PI * 2
            });
        }

        // Foreground layer - fast, larger glowing particles
        this.fgParticles = [];
        for (let i = 0; i < 15 * this.targetComplexity; i++) {
            this.fgParticles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                size: Math.random() * 4 + 2,
                speed: 1 + Math.random() * 1,
                opacity: 0.5 + Math.random() * 0.3,
                glow: 10 + Math.random() * 20
            });
        }
    }

    _updateParticleColors() {
        const colors = [this.colors.primary, this.colors.secondary, this.colors.tertiary];
        [...this.bgParticles, ...this.midParticles, ...this.fgParticles, ...this.particles].forEach(p => {
            p.color = colors[Math.floor(Math.random() * 3)];
        });
    }

    _drawParallaxLayers(width, height) {
        const avgFreq = this.dataArray ?
            this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255 : 0.3;

        // Background layer - slowest
        this.ctx.globalAlpha = 0.3;
        for (const p of this.bgParticles) {
            p.y -= p.speed * (0.5 + avgFreq);
            if (p.y < -10) {
                p.y = height + 10;
                p.x = Math.random() * width;
            }

            this.ctx.fillStyle = this.colors.tertiary;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fill();
        }

        // Mid layer
        this.ctx.globalAlpha = 0.4;
        for (const p of this.midParticles) {
            p.y -= p.speed * (0.8 + avgFreq * 0.5);
            p.pulse += 0.02;
            if (p.y < -10) {
                p.y = height + 10;
                p.x = Math.random() * width;
            }

            const pulseSize = p.size * (1 + Math.sin(p.pulse) * 0.3 * avgFreq);
            this.ctx.fillStyle = this.colors.secondary;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, pulseSize, 0, Math.PI * 2);
            this.ctx.fill();
        }

        // Foreground layer - fastest with glow
        this.ctx.save();
        for (const p of this.fgParticles) {
            p.y -= p.speed * (1 + avgFreq);
            if (p.y < -20) {
                p.y = height + 20;
                p.x = Math.random() * width;
            }

            this.ctx.shadowColor = this.colors.primary;
            this.ctx.shadowBlur = p.glow * (0.5 + avgFreq);
            this.ctx.globalAlpha = p.opacity;
            this.ctx.fillStyle = this.colors.primary;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size * (1 + avgFreq * 0.5), 0, Math.PI * 2);
            this.ctx.fill();
        }
        this.ctx.restore();
        this.ctx.globalAlpha = 1;
    }

    // ========================================
    // PRIVATE: FPS MONITORING
    // ========================================

    _updateFpsDisplay() {
        const fpsEl = document.getElementById('rw-fps-counter');
        if (!fpsEl) return;

        fpsEl.textContent = `${this.fps} FPS`;

        // Update color class based on FPS and current theme
        fpsEl.classList.remove('fps-good', 'fps-ok', 'fps-bad');

        if (this.fps >= 50) {
            fpsEl.classList.add('fps-good');
            fpsEl.style.color = this.colors.primary;
        } else if (this.fps >= 30) {
            fpsEl.classList.add('fps-ok');
            fpsEl.style.color = '#eab308';
        } else {
            fpsEl.classList.add('fps-bad');
            fpsEl.style.color = '#ef4444';
        }
    }

    // ========================================
    // PRIVATE: MAIN DRAW LOOP
    // ========================================

    _draw() {
        if (!this.isActive) return;

        this.animationId = requestAnimationFrame(this._draw);

        // FPS monitoring
        const now = performance.now();
        const delta = now - this.lastTime;
        this.lastTime = now;
        this.time += delta / 1000;

        this.frameCount++;
        if (now - this.lastFpsUpdate > 500) {
            this.fps = Math.round(this.frameCount * (1000 / (now - this.lastFpsUpdate)));
            this.frameCount = 0;
            this.lastFpsUpdate = now;

            this._updateFpsDisplay();

            // Adjust complexity based on FPS
            if (this.fps < 25) {
                this.targetComplexity = Math.max(0.2, this.targetComplexity - 0.15);
                this._initParallaxLayers();
            } else if (this.fps < 40) {
                this.targetComplexity = Math.max(0.4, this.targetComplexity - 0.05);
            } else if (this.fps > 55 && this.targetComplexity < 1) {
                this.targetComplexity = Math.min(1, this.targetComplexity + 0.02);
            }
        }

        // Get frequency data
        if (this.analyser && this.dataArray) {
            this.analyser.getByteFrequencyData(this.dataArray);
        }

        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;

        // Clear with slight fade for trails
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.15)';
        this.ctx.fillRect(0, 0, width, height);

        // Update intro animation
        this._updateIntro(now);

        // Draw parallax background layers
        this._drawParallaxLayers(width, height);

        // Draw main visualization based on intro phase
        if (this.introPhase === 'active') {
            switch (this.mode) {
                case 'bars':
                    this._drawBars(width, height);
                    break;
                case 'wave':
                    this._drawWave(width, height);
                    break;
                case 'circle':
                    this._drawCircle(width, height);
                    break;
                case 'particles':
                    this._drawParticles(width, height);
                    break;
                case 'lissajous':
                    this._drawLissajous(width, height);
                    break;
                case 'tempest':
                    this._drawTempest(width, height);
                    break;
                case 'pong':
                    this._drawPong(width, height);
                    break;
                case 'breakout':
                    this._drawBreakout(width, height);
                    break;
                case 'snake':
                    this._drawSnake(width, height);
                    break;
                case 'random':
                    this._drawRandom(width, height);
                    break;
                default:
                    this._drawBars(width, height);
            }
        } else {
            this._drawIntroAnimation(width, height);
        }
    }

    // ========================================
    // PRIVATE: INTRO ANIMATION
    // ========================================

    _updateIntro(now) {
        const elapsed = now - this.introStartTime;

        switch (this.introPhase) {
            case 'speck':
                this.introProgress = Math.min(1, elapsed / 500);
                if (this.introProgress >= 1) {
                    this.introPhase = 'grow';
                    this.introProgress = 0;
                }
                break;
            case 'grow':
                this.introProgress = Math.min(1, elapsed / 1500);
                if (this.introProgress >= 1) {
                    this.introPhase = 'explode';
                    this.introProgress = 0;
                    this.introStartTime = now;
                }
                break;
            case 'explode':
                this.introProgress = Math.min(1, (now - this.introStartTime) / 800);
                if (this.introProgress >= 1) {
                    this.introPhase = 'active';
                }
                break;
        }
    }

    _drawIntroAnimation(width, height) {
        const centerX = width / 2;
        const centerY = height / 2;

        switch (this.introPhase) {
            case 'speck': {
                const size = 2 + this.introProgress * 5;
                const glow = 20 + this.introProgress * 40;

                this.ctx.save();
                this.ctx.shadowColor = this.colors.primary;
                this.ctx.shadowBlur = glow;

                const gradient = this.ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, size);
                gradient.addColorStop(0, '#ffffff');
                gradient.addColorStop(0.3, this.colors.primary);
                gradient.addColorStop(1, 'transparent');

                this.ctx.fillStyle = gradient;
                this.ctx.beginPath();
                this.ctx.arc(centerX, centerY, size, 0, Math.PI * 2);
                this.ctx.fill();
                this.ctx.restore();
                break;
            }

            case 'grow': {
                const eased = this._easeOutElastic(this.introProgress);
                const maxRadius = Math.min(width, height) * 0.3;
                const radius = maxRadius * eased;

                this.ctx.save();
                this.ctx.shadowColor = this.colors.primary;
                this.ctx.shadowBlur = 50 + this.introProgress * 50;

                const gradient = this.ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, radius);
                gradient.addColorStop(0, this.colors.tertiary + 'cc');
                gradient.addColorStop(0.5, this.colors.secondary + '88');
                gradient.addColorStop(0.8, this.colors.primary + '44');
                gradient.addColorStop(1, 'transparent');

                this.ctx.fillStyle = gradient;
                this.ctx.beginPath();
                this.ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
                this.ctx.fill();

                // Rotating rings
                for (let i = 0; i < 3; i++) {
                    const ringRadius = radius * (0.6 + i * 0.2);
                    const rotation = this.time * (1 + i * 0.5) + i * Math.PI / 3;

                    this.ctx.strokeStyle = [this.colors.primary, this.colors.secondary, this.colors.tertiary][i];
                    this.ctx.lineWidth = 2;
                    this.ctx.globalAlpha = 0.5 - i * 0.1;

                    this.ctx.beginPath();
                    this.ctx.ellipse(centerX, centerY, ringRadius, ringRadius * 0.3, rotation, 0, Math.PI * 2);
                    this.ctx.stroke();
                }

                this.ctx.globalAlpha = 1;
                this.ctx.restore();
                break;
            }

            case 'explode': {
                const eased = this._easeOutQuart(this.introProgress);
                const maxRadius = Math.max(width, height);

                // Shockwave rings
                for (let i = 0; i < 5; i++) {
                    const delay = i * 0.15;
                    const ringProgress = Math.max(0, Math.min(1, (this.introProgress - delay) / (1 - delay)));
                    if (ringProgress <= 0) continue;

                    const ringRadius = maxRadius * ringProgress * 0.8;
                    const opacity = (1 - ringProgress) * 0.8;

                    this.ctx.strokeStyle = [this.colors.primary, this.colors.secondary, this.colors.tertiary][i % 3];
                    this.ctx.lineWidth = 4 - i * 0.5;
                    this.ctx.globalAlpha = opacity;

                    this.ctx.beginPath();
                    this.ctx.arc(centerX, centerY, ringRadius, 0, Math.PI * 2);
                    this.ctx.stroke();
                }

                // Explosion particles
                const particleCount = 30;
                for (let i = 0; i < particleCount; i++) {
                    const angle = (i / particleCount) * Math.PI * 2;
                    const distance = eased * maxRadius * 0.6 * (0.5 + Math.random() * 0.5);
                    const x = centerX + Math.cos(angle) * distance;
                    const y = centerY + Math.sin(angle) * distance;
                    const size = (1 - eased) * 8 + 2;

                    this.ctx.fillStyle = [this.colors.primary, this.colors.secondary, this.colors.tertiary][i % 3];
                    this.ctx.globalAlpha = (1 - eased) * 0.8;
                    this.ctx.beginPath();
                    this.ctx.arc(x, y, size, 0, Math.PI * 2);
                    this.ctx.fill();
                }

                this.ctx.globalAlpha = 1;
                break;
            }
        }
    }

    // ========================================
    // PRIVATE: RANDOM MODE (AUTO-SWITCH)
    // ========================================

    _drawRandom(width, height) {
        const avgFreq = this.dataArray ?
            this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255 : 0.5;

        this.randomModeTimer += 1;
        const switchInterval = 600 - avgFreq * 300; // 10-20 seconds at 60fps

        if (this.randomModeTimer >= switchInterval) {
            this.randomModeTimer = 0;
            const available = this.allModes.filter(m => m !== this.randomMode);
            this.randomMode = available[Math.floor(Math.random() * available.length)];
        }

        // Draw the current random mode
        switch (this.randomMode) {
            case 'bars': this._drawBars(width, height); break;
            case 'wave': this._drawWave(width, height); break;
            case 'circle': this._drawCircle(width, height); break;
            case 'particles': this._drawParticles(width, height); break;
            case 'lissajous': this._drawLissajous(width, height); break;
            case 'tempest': this._drawTempest(width, height); break;
            case 'pong': this._drawPong(width, height); break;
            case 'breakout': this._drawBreakout(width, height); break;
            case 'snake': this._drawSnake(width, height); break;
            default: this._drawBars(width, height);
        }

        // Show mode indicator
        this.ctx.font = 'bold 14px monospace';
        this.ctx.fillStyle = this.colors.tertiary;
        this.ctx.globalAlpha = 0.5;
        this.ctx.textAlign = 'left';
        this.ctx.fillText(`Mode: ${this.randomMode}`, 20, height - 20);
        this.ctx.globalAlpha = 1;
    }

    // ========================================
    // EASING FUNCTIONS
    // ========================================

    _easeOutElastic(x) {
        const c4 = (2 * Math.PI) / 3;
        return x === 0 ? 0 : x === 1 ? 1 :
            Math.pow(2, -10 * x) * Math.sin((x * 10 - 0.75) * c4) + 1;
    }

    _easeOutQuart(x) {
        return 1 - Math.pow(1 - x, 4);
    }
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { RadioWidgetVisualizer };
}
if (typeof window !== 'undefined') {
    window.RadioWidgetVisualizer = RadioWidgetVisualizer;
}
