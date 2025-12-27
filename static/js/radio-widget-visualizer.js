/**
 * Radio Widget Audio Visualizer
 * Canvas-based audio visualizations with epic intro and parallax effects
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
    // PRIVATE METHODS
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

    _updateFpsDisplay() {
        const fpsEl = document.getElementById('rw-fps-counter');
        if (!fpsEl) return;

        fpsEl.textContent = `${this.fps} FPS`;

        // Update color class based on FPS and current theme
        fpsEl.classList.remove('fps-good', 'fps-ok', 'fps-bad');

        if (this.fps >= 50) {
            fpsEl.classList.add('fps-good');
            fpsEl.style.color = this.colors.primary; // Use theme color for good
        } else if (this.fps >= 30) {
            fpsEl.classList.add('fps-ok');
            fpsEl.style.color = '#eab308'; // Yellow for ok
        } else {
            fpsEl.classList.add('fps-bad');
            fpsEl.style.color = '#ef4444'; // Red for bad
        }
    }

    _draw() {
        if (!this.isActive) return;

        this.animationId = requestAnimationFrame(this._draw);

        // FPS monitoring
        const now = performance.now();
        const delta = now - this.lastTime;
        this.lastTime = now;
        this.time += delta / 1000;

        this.frameCount++;
        if (now - this.lastFpsUpdate > 500) { // Update every 500ms for smoother display
            this.fps = Math.round(this.frameCount * (1000 / (now - this.lastFpsUpdate)));
            this.frameCount = 0;
            this.lastFpsUpdate = now;

            // Update FPS display
            this._updateFpsDisplay();

            // Adjust complexity based on FPS
            if (this.fps < 25) {
                this.targetComplexity = Math.max(0.2, this.targetComplexity - 0.15);
                this._initParallaxLayers(); // Reinit with fewer particles
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
                // Tiny glowing speck in center
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
                // Growing orb with rings
                const eased = this._easeOutElastic(this.introProgress);
                const maxRadius = Math.min(width, height) * 0.3;
                const radius = maxRadius * eased;

                // Outer glow
                this.ctx.save();
                this.ctx.shadowColor = this.colors.primary;
                this.ctx.shadowBlur = 50 + this.introProgress * 50;

                // Main orb
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
                // Explosion outward
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

    _drawBars(width, height) {
        if (!this.dataArray) return;

        const bufferLength = this.dataArray.length;
        // Skip bars at low complexity for performance
        const step = this.targetComplexity >= 0.7 ? 1 : this.targetComplexity >= 0.4 ? 2 : 4;
        const barWidth = (width / bufferLength) * 2.5 * step;
        const avgFreq = this.dataArray.reduce((a, b) => a + b, 0) / bufferLength / 255;

        // Reduce shadow blur at low complexity (expensive operation)
        const shadowEnabled = this.targetComplexity >= 0.5;
        const drawReflections = this.targetComplexity >= 0.6;

        // Mirror effect - draw from center outward (no gap in middle)
        for (let side = 0; side < 2; side++) {
            for (let i = 0; i < bufferLength / 2; i += step) {
                const barHeight = (this.dataArray[i] / 255) * height * 0.6;

                const gradient = this.ctx.createLinearGradient(0, height, 0, height - barHeight);
                gradient.addColorStop(0, this.colors.primary);
                gradient.addColorStop(0.5, this.colors.secondary);
                gradient.addColorStop(1, this.colors.tertiary);

                this.ctx.fillStyle = gradient;
                if (shadowEnabled) {
                    this.ctx.shadowColor = this.colors.primary;
                    this.ctx.shadowBlur = 15 * avgFreq * this.targetComplexity;
                }

                // Calculate bar position - side 0 goes right, side 1 goes left
                const barIndex = i / step;
                const barX = side === 0
                    ? width / 2 + barIndex * barWidth
                    : width / 2 - (barIndex + 1) * barWidth;
                const barY = height - barHeight;
                const radius = Math.min(barWidth / 2, 4);

                this.ctx.beginPath();
                this.ctx.roundRect(barX, barY, barWidth - 2, barHeight, [radius, radius, 0, 0]);
                this.ctx.fill();

                // Reflection (skip at low complexity)
                if (drawReflections) {
                    this.ctx.globalAlpha = 0.2;
                    this.ctx.fillStyle = gradient;
                    this.ctx.beginPath();
                    this.ctx.roundRect(barX, height, barWidth - 2, barHeight * 0.3, [0, 0, radius, radius]);
                    this.ctx.fill();
                    this.ctx.globalAlpha = 1;
                }
            }
        }

        this.ctx.shadowBlur = 0;
    }

    _drawWave(width, height) {
        if (!this.dataArray) return;

        const bufferLength = this.dataArray.length;
        // Skip points at low complexity
        const step = this.targetComplexity >= 0.7 ? 1 : this.targetComplexity >= 0.4 ? 2 : 3;
        const sliceWidth = (width / bufferLength) * step;
        const avgFreq = this.dataArray.reduce((a, b) => a + b, 0) / bufferLength / 255;

        // Scale number of waves with complexity (1-5 waves)
        const numWaves = Math.max(1, Math.floor(5 * this.targetComplexity));
        const shadowEnabled = this.targetComplexity >= 0.5;

        // Multiple layered waves
        for (let wave = numWaves - 1; wave >= 0; wave--) {
            this.ctx.beginPath();
            this.ctx.lineWidth = 3 - wave * 0.4;

            const colors = [this.colors.primary, this.colors.secondary, this.colors.tertiary];
            this.ctx.strokeStyle = colors[wave % 3];
            this.ctx.globalAlpha = 0.2 + (wave * 0.15);
            if (shadowEnabled) {
                this.ctx.shadowColor = colors[wave % 3];
                this.ctx.shadowBlur = (10 + avgFreq * 20) * this.targetComplexity;
            }

            const offset = wave * 10;
            const amplitude = 0.4 + wave * 0.1;

            let x = 0;
            for (let i = 0; i < bufferLength; i += step) {
                const v = this.dataArray[i] / 255;
                const y = (height / 2) + offset + (v - 0.5) * height * amplitude +
                          Math.sin(this.time * 2 + i * 0.05 + wave) * 10;

                if (i === 0) {
                    this.ctx.moveTo(x, y);
                } else {
                    // Smooth curve
                    const prevX = x - sliceWidth;
                    const cpX = prevX + sliceWidth / 2;
                    this.ctx.quadraticCurveTo(cpX, y, x, y);
                }
                x += sliceWidth;
            }

            this.ctx.stroke();
        }

        this.ctx.globalAlpha = 1;
        this.ctx.shadowBlur = 0;
    }

    _drawCircle(width, height) {
        if (!this.dataArray) return;

        const centerX = width / 2;
        const centerY = height / 2;
        const baseRadius = Math.min(width, height) * 0.2;
        const bufferLength = this.dataArray.length;
        const avgFreq = this.dataArray.reduce((a, b) => a + b, 0) / bufferLength / 255;

        // Scale complexity - fewer rings and skip frequency bins at low complexity
        const numRings = Math.max(1, Math.floor(3 * this.targetComplexity));
        const step = this.targetComplexity >= 0.7 ? 1 : this.targetComplexity >= 0.4 ? 2 : 4;
        const shadowEnabled = this.targetComplexity >= 0.5;

        // Rotating outer ring
        this.ctx.save();
        this.ctx.translate(centerX, centerY);
        this.ctx.rotate(this.time * 0.5);
        this.ctx.translate(-centerX, -centerY);

        for (let ring = 0; ring < numRings; ring++) {
            const ringRadius = baseRadius * (1 + ring * 0.4);
            const colors = [this.colors.primary, this.colors.secondary, this.colors.tertiary];
            this.ctx.strokeStyle = colors[ring];
            this.ctx.lineWidth = 2 + avgFreq * 2;
            this.ctx.lineCap = 'round';
            this.ctx.globalAlpha = 0.6 - ring * 0.15;

            if (shadowEnabled) {
                this.ctx.shadowColor = colors[ring];
                this.ctx.shadowBlur = (10 + avgFreq * 15) * this.targetComplexity;
            }

            for (let i = 0; i < bufferLength; i += step) {
                const angle = (i / bufferLength) * Math.PI * 2;
                const barHeight = (this.dataArray[i] / 255) * baseRadius * (0.5 + ring * 0.2);

                const innerX = centerX + Math.cos(angle) * ringRadius;
                const innerY = centerY + Math.sin(angle) * ringRadius;
                const outerX = centerX + Math.cos(angle) * (ringRadius + barHeight);
                const outerY = centerY + Math.sin(angle) * (ringRadius + barHeight);

                this.ctx.beginPath();
                this.ctx.moveTo(innerX, innerY);
                this.ctx.lineTo(outerX, outerY);
                this.ctx.stroke();
            }
        }

        this.ctx.restore();

        // Pulsing center orb
        const pulseRadius = baseRadius * 0.6 + avgFreq * 40;
        const gradient = this.ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, pulseRadius);
        gradient.addColorStop(0, this.colors.tertiary + 'cc');
        gradient.addColorStop(0.5, this.colors.secondary + '66');
        gradient.addColorStop(1, 'transparent');

        this.ctx.globalAlpha = 0.8;
        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY, pulseRadius, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.globalAlpha = 1;
        this.ctx.shadowBlur = 0;
    }

    _initParticles() {
        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;

        this.particles = [];
        for (let i = 0; i < this.maxParticles * this.targetComplexity; i++) {
            this.particles.push(this._createParticle(width, height));
        }
    }

    _createParticle(width = 800, height = 600) {
        const colors = [this.colors.primary, this.colors.secondary, this.colors.tertiary];
        return {
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 2,
            vy: (Math.random() - 0.5) * 2,
            size: Math.random() * 4 + 1,
            color: colors[Math.floor(Math.random() * 3)],
            life: 1,
            trail: []
        };
    }

    _drawParticles(width, height) {
        if (!this.dataArray) {
            this._drawStaticParticles(width, height);
            return;
        }

        const avgFreq = this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255;
        const bassFreq = this.dataArray.slice(0, 10).reduce((a, b) => a + b, 0) / 10 / 255;

        // Scale features with complexity
        const drawTrails = this.targetComplexity >= 0.6;
        const trailLength = Math.floor(10 * this.targetComplexity);
        const shadowEnabled = this.targetComplexity >= 0.5;
        const drawConnections = this.targetComplexity >= 0.4;

        // Update and draw particles with trails
        for (const p of this.particles) {
            // Store trail (only if enabled)
            if (drawTrails) {
                p.trail.push({ x: p.x, y: p.y });
                if (p.trail.length > trailLength) p.trail.shift();
            }

            // Update velocity
            p.vx += (Math.random() - 0.5) * bassFreq * 0.8;
            p.vy += (Math.random() - 0.5) * bassFreq * 0.8;

            // Limit velocity
            const maxVel = 4 + bassFreq * 3;
            const vel = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
            if (vel > maxVel) {
                p.vx = (p.vx / vel) * maxVel;
                p.vy = (p.vy / vel) * maxVel;
            }

            p.x += p.vx;
            p.y += p.vy;

            // Wrap
            if (p.x < 0) p.x = width;
            if (p.x > width) p.x = 0;
            if (p.y < 0) p.y = height;
            if (p.y > height) p.y = 0;

            // Draw trail (skip at low complexity)
            if (drawTrails && p.trail.length > 1) {
                this.ctx.beginPath();
                this.ctx.moveTo(p.trail[0].x, p.trail[0].y);
                for (let i = 1; i < p.trail.length; i++) {
                    this.ctx.lineTo(p.trail[i].x, p.trail[i].y);
                }
                this.ctx.strokeStyle = p.color;
                this.ctx.lineWidth = p.size * 0.5;
                this.ctx.globalAlpha = 0.3;
                this.ctx.stroke();
            }

            // Draw particle
            const size = p.size * (1 + avgFreq);
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
            this.ctx.fillStyle = p.color;
            this.ctx.globalAlpha = 0.7 + avgFreq * 0.3;
            if (shadowEnabled) {
                this.ctx.shadowColor = p.color;
                this.ctx.shadowBlur = (15 + bassFreq * 20) * this.targetComplexity;
            }
            this.ctx.fill();
        }

        this.ctx.shadowBlur = 0;
        this.ctx.globalAlpha = 1;

        // Draw connections (skip at low complexity)
        if (drawConnections) {
            this._drawParticleConnections(width, height, avgFreq);
        }
    }

    _drawStaticParticles(width, height) {
        if (this.particles.length === 0) this._initParticles();

        for (const p of this.particles) {
            p.x += p.vx * 0.3;
            p.y += p.vy * 0.3;

            if (p.x < 0) p.x = width;
            if (p.x > width) p.x = 0;
            if (p.y < 0) p.y = height;
            if (p.y > height) p.y = 0;

            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fillStyle = p.color;
            this.ctx.globalAlpha = 0.4;
            this.ctx.fill();
        }
        this.ctx.globalAlpha = 1;
    }

    _drawParticleConnections(width, height, avgFreq) {
        const connectionDistance = 80 + avgFreq * 60;
        // Skip particles based on complexity to reduce O(n²) comparisons
        const step = this.targetComplexity >= 0.7 ? 1 : this.targetComplexity >= 0.4 ? 2 : 3;
        // Use simpler stroke at low complexity (gradients are expensive)
        const useGradients = this.targetComplexity >= 0.7;

        for (let i = 0; i < this.particles.length; i += step) {
            for (let j = i + 1; j < this.particles.length; j += step) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                // Skip sqrt for performance - compare squared distances
                const distSq = dx * dx + dy * dy;
                const maxDistSq = connectionDistance * connectionDistance;

                if (distSq < maxDistSq) {
                    const distance = Math.sqrt(distSq);

                    if (useGradients) {
                        const gradient = this.ctx.createLinearGradient(
                            this.particles[i].x, this.particles[i].y,
                            this.particles[j].x, this.particles[j].y
                        );
                        gradient.addColorStop(0, this.particles[i].color);
                        gradient.addColorStop(1, this.particles[j].color);
                        this.ctx.strokeStyle = gradient;
                    } else {
                        this.ctx.strokeStyle = this.particles[i].color;
                    }

                    this.ctx.lineWidth = 1;
                    this.ctx.globalAlpha = (1 - distance / connectionDistance) * 0.4;
                    this.ctx.beginPath();
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.stroke();
                }
            }
        }
        this.ctx.globalAlpha = 1;
    }

    // ========================================
    // LISSAJOUS / MATH LINES VISUALIZATION
    // ========================================

    _drawLissajous(width, height) {
        const centerX = width / 2;
        const centerY = height / 2;
        const maxRadius = Math.min(width, height) * 0.4;

        // Get audio data for modulation
        const avgFreq = this.dataArray ?
            this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255 : 0.5;
        const bassFreq = this.dataArray ?
            this.dataArray.slice(0, 20).reduce((a, b) => a + b, 0) / 20 / 255 : 0.5;
        const trebleFreq = this.dataArray ?
            this.dataArray.slice(-20).reduce((a, b) => a + b, 0) / 20 / 255 : 0.5;

        // Modulate lissajous parameters with audio
        const a = 3 + Math.floor(bassFreq * 5);
        const b = 2 + Math.floor(trebleFreq * 4);
        const delta = this.lissajousPhase + avgFreq * Math.PI;

        // Number of curves based on complexity
        const numCurves = Math.max(1, Math.floor(5 * this.targetComplexity));

        for (let curve = 0; curve < numCurves; curve++) {
            const curveOffset = (curve / numCurves) * Math.PI * 2;
            const radius = maxRadius * (0.3 + (curve / numCurves) * 0.7);

            this.ctx.beginPath();
            this.ctx.strokeStyle = curve % 3 === 0 ? this.colors.primary :
                                   curve % 3 === 1 ? this.colors.secondary :
                                   this.colors.tertiary;
            this.ctx.lineWidth = 2 - curve * 0.2;
            this.ctx.globalAlpha = 0.6 - curve * 0.08;

            if (this.targetComplexity >= 0.5) {
                this.ctx.shadowColor = this.ctx.strokeStyle;
                this.ctx.shadowBlur = 10 * avgFreq;
            }

            const steps = Math.floor(360 * this.targetComplexity);
            for (let i = 0; i <= steps; i++) {
                const t = (i / steps) * Math.PI * 2;
                const x = centerX + radius * Math.sin((a + curve * 0.5) * t + delta + curveOffset);
                const y = centerY + radius * Math.sin((b + curve * 0.3) * t + curveOffset);

                if (i === 0) {
                    this.ctx.moveTo(x, y);
                } else {
                    this.ctx.lineTo(x, y);
                }
            }
            this.ctx.stroke();
        }

        // Spirograph overlay
        if (this.targetComplexity >= 0.6) {
            this._drawSpirograph(width, height, avgFreq);
        }

        this.ctx.shadowBlur = 0;
        this.ctx.globalAlpha = 1;
        this.lissajousPhase += 0.02;
    }

    _drawSpirograph(width, height, intensity) {
        const centerX = width / 2;
        const centerY = height / 2;
        const R = Math.min(width, height) * 0.25;
        const r = R * (0.3 + intensity * 0.4);
        const d = r * 0.8;

        this.ctx.beginPath();
        this.ctx.strokeStyle = this.colors.tertiary;
        this.ctx.lineWidth = 1;
        this.ctx.globalAlpha = 0.4;

        const steps = Math.floor(200 * this.targetComplexity);
        for (let i = 0; i <= steps; i++) {
            const t = (i / steps) * Math.PI * 8 + this.time;
            const x = centerX + (R - r) * Math.cos(t) + d * Math.cos((R - r) / r * t);
            const y = centerY + (R - r) * Math.sin(t) - d * Math.sin((R - r) / r * t);

            if (i === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        }
        this.ctx.stroke();
    }

    // ========================================
    // TEMPEST VECTOR VISUALIZATION
    // Classic arcade-style tube shooter with vector graphics
    // ========================================

    _drawTempest(width, height) {
        const centerX = width / 2;
        const centerY = height / 2;
        const outerRadius = Math.min(width, height) * 0.42;
        const innerRadius = outerRadius * 0.03; // Tiny vanishing point like the arcade

        const avgFreq = this.dataArray ?
            this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255 : 0.5;
        const bassFreq = this.dataArray ?
            this.dataArray.slice(0, 20).reduce((a, b) => a + b, 0) / 20 / 255 : 0.5;
        const trebleFreq = this.dataArray ?
            this.dataArray.slice(-20).reduce((a, b) => a + b, 0) / 20 / 255 : 0.5;

        // Get segments based on current level shape
        const segments = this._getTempestSegments();

        // Scale depth levels with complexity for performance
        const depthLevels = Math.floor(6 + 10 * this.targetComplexity);

        // Subtle rotation like the game
        this.tempestAngle += 0.002;

        // Use classic Tempest colors - bright vector-style
        const webColor = '#00ffff';  // Cyan for the web
        const laneColor = '#0088ff'; // Blue for lane dividers

        // PERFORMANCE: Batch all web lines into single paths
        // Draw rings (the horizontal web lines)
        this.ctx.strokeStyle = webColor;
        this.ctx.lineWidth = 1.5;
        this.ctx.globalAlpha = 0.9;

        if (this.targetComplexity >= 0.4) {
            this.ctx.shadowColor = webColor;
            this.ctx.shadowBlur = 8;
        }

        for (let d = 0; d < depthLevels; d++) {
            const depthRatio = d / depthLevels;
            // Exponential perspective - lines closer together near center
            const radius = innerRadius + (outerRadius - innerRadius) * Math.pow(depthRatio, 0.6);

            // Alpha fades toward center (depth)
            this.ctx.globalAlpha = 0.3 + depthRatio * 0.7;

            // Draw complete ring as single path
            this.ctx.beginPath();
            for (let i = 0; i <= segments; i++) {
                const angle = this._getTempestAngle(i, segments) + this.tempestAngle;
                const x = centerX + Math.cos(angle) * radius;
                const y = centerY + Math.sin(angle) * radius;
                if (i === 0) {
                    this.ctx.moveTo(x, y);
                } else {
                    this.ctx.lineTo(x, y);
                }
            }
            this.ctx.stroke();
        }

        // Draw lane dividers (lines from center to edge) - batched
        this.ctx.strokeStyle = laneColor;
        this.ctx.lineWidth = 1.5;
        this.ctx.globalAlpha = 0.8;

        if (this.targetComplexity >= 0.4) {
            this.ctx.shadowColor = laneColor;
            this.ctx.shadowBlur = 6;
        }

        this.ctx.beginPath();
        for (let i = 0; i < segments; i++) {
            const angle = this._getTempestAngle(i, segments) + this.tempestAngle;
            const innerX = centerX + Math.cos(angle) * innerRadius;
            const innerY = centerY + Math.sin(angle) * innerRadius;
            const outerX = centerX + Math.cos(angle) * outerRadius;
            const outerY = centerY + Math.sin(angle) * outerRadius;

            this.ctx.moveTo(innerX, innerY);
            this.ctx.lineTo(outerX, outerY);
        }
        this.ctx.stroke();

        // Draw rim (outer edge) brighter
        this.ctx.strokeStyle = '#ffff00'; // Yellow rim like the game
        this.ctx.lineWidth = 2.5;
        this.ctx.globalAlpha = 1;
        if (this.targetComplexity >= 0.4) {
            this.ctx.shadowColor = '#ffff00';
            this.ctx.shadowBlur = 12;
        }

        this.ctx.beginPath();
        for (let i = 0; i <= segments; i++) {
            const angle = this._getTempestAngle(i, segments) + this.tempestAngle;
            const x = centerX + Math.cos(angle) * outerRadius;
            const y = centerY + Math.sin(angle) * outerRadius;
            if (i === 0) {
                this.ctx.moveTo(x, y);
            } else {
                this.ctx.lineTo(x, y);
            }
        }
        this.ctx.stroke();

        // Update player position based on audio (smoother)
        const targetPos = this.tempestPlayerPos + (trebleFreq - 0.5) * 0.12;
        this.tempestPlayerPos += (targetPos - this.tempestPlayerPos) * 0.3;
        if (this.tempestPlayerPos < 0) this.tempestPlayerPos += 1;
        if (this.tempestPlayerPos > 1) this.tempestPlayerPos -= 1;

        // Snap player to nearest segment
        const playerSegment = Math.round(this.tempestPlayerPos * segments) % segments;
        const playerAngle = this._getTempestAngle(playerSegment + 0.5, segments) + this.tempestAngle;

        // Draw player ship (Blaster - the classic claw)
        const px = centerX + Math.cos(playerAngle) * (outerRadius + 8);
        const py = centerY + Math.sin(playerAngle) * (outerRadius + 8);

        this._drawTempestPlayer(px, py, playerAngle, bassFreq, segments);

        // Spawn and update enemies
        this._updateTempestEnemies(centerX, centerY, innerRadius, outerRadius, segments, bassFreq);

        // Update and draw bullets
        this._updateTempestBullets(centerX, centerY, innerRadius, outerRadius, segments, playerSegment);

        // Draw explosions
        this._drawTempestExplosions(centerX, centerY, innerRadius, outerRadius);

        // Draw HUD - classic arcade style
        this.ctx.shadowBlur = 0;
        this.ctx.font = 'bold 16px "Courier New", monospace';
        this.ctx.textAlign = 'left';

        // Level indicator
        this.ctx.fillStyle = '#00ff00';
        this.ctx.globalAlpha = 0.9;
        this.ctx.fillText(`LEVEL ${this.tempestLevel + 1}`, 20, 30);

        // Score
        this.ctx.fillStyle = '#ffff00';
        this.ctx.fillText(`${this.tempestScore.toString().padStart(6, '0')}`, 20, 52);

        // Level up every 500 points
        if (this.tempestScore > 0 && this.tempestScore % 500 === 0) {
            this.tempestLevel = Math.min(this.tempestLevel + 1, this.tempestShapes.length - 1);
            this.tempestCurrentShape = this.tempestShapes[this.tempestLevel % this.tempestShapes.length];
        }

        this.ctx.shadowBlur = 0;
        this.ctx.globalAlpha = 1;
    }

    _getTempestSegments() {
        // Classic Tempest levels had different web shapes
        switch (this.tempestCurrentShape) {
            case 'hexagon': return 6;
            case 'octagon': return 8;
            case 'star': return 10;
            case 'square': return 4;
            case 'circle':
            default: return 16;
        }
    }

    _getTempestAngle(segment, totalSegments) {
        return (segment / totalSegments) * Math.PI * 2 - Math.PI / 2; // Start from top
    }

    _drawTempestPlayer(x, y, angle, intensity, segments) {
        this.ctx.save();
        this.ctx.translate(x, y);
        this.ctx.rotate(angle + Math.PI / 2);

        // Classic Blaster claw - yellow vector lines
        const size = 18 + intensity * 6;

        this.ctx.strokeStyle = '#ffff00';
        this.ctx.fillStyle = '#ffff00';
        this.ctx.lineWidth = 2.5;
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.globalAlpha = 1;

        if (this.targetComplexity >= 0.4) {
            this.ctx.shadowColor = '#ffff00';
            this.ctx.shadowBlur = 15 + intensity * 10;
        }

        // The Blaster shape - classic claw pointing into tunnel
        this.ctx.beginPath();
        // Left claw
        this.ctx.moveTo(-size * 0.8, 0);
        this.ctx.lineTo(-size * 0.4, -size * 0.6);
        this.ctx.lineTo(0, -size * 0.2);
        // Right claw
        this.ctx.lineTo(size * 0.4, -size * 0.6);
        this.ctx.lineTo(size * 0.8, 0);
        // Center point (tip into tunnel)
        this.ctx.moveTo(0, -size * 0.2);
        this.ctx.lineTo(0, size * 0.4);
        this.ctx.stroke();

        // Center dot
        this.ctx.beginPath();
        this.ctx.arc(0, 0, 3, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.restore();
    }

    _updateTempestEnemies(cx, cy, innerRadius, outerRadius, segments, bassFreq) {
        // Spawn enemies from the center on bass hits (Flippers, Tankers, Spikers)
        if (bassFreq > 0.45 && Math.random() < 0.15 * this.targetComplexity) {
            const segment = Math.floor(Math.random() * segments);
            const types = ['flipper', 'tanker', 'spiker'];
            this.tempestEnemies.push({
                segment: segment,
                depth: 0, // 0 = center, 1 = outer edge
                speed: 0.006 + Math.random() * 0.01 + this.tempestLevel * 0.002,
                type: types[Math.floor(Math.random() * types.length)],
                flip: 0, // For flipper animation
                lane: segment // Flippers can change lanes
            });
        }

        // Update and draw enemies
        this.tempestEnemies = this.tempestEnemies.filter(enemy => {
            enemy.depth += enemy.speed;

            if (enemy.depth >= 1) {
                return false;
            }

            // Flippers randomly change lanes
            if (enemy.type === 'flipper' && Math.random() < 0.02) {
                enemy.flip += 1;
                enemy.lane = (enemy.lane + (Math.random() < 0.5 ? 1 : -1) + segments) % segments;
                enemy.segment = enemy.lane;
            }

            const angle = this._getTempestAngle(enemy.segment + 0.5, segments) + this.tempestAngle;
            const radius = innerRadius + (outerRadius - innerRadius) * Math.pow(enemy.depth, 0.6);
            const x = cx + Math.cos(angle) * radius;
            const y = cy + Math.sin(angle) * radius;
            const size = 3 + enemy.depth * 14;

            this.ctx.save();
            this.ctx.translate(x, y);
            this.ctx.rotate(angle + Math.PI / 2);

            // Different enemy types with classic Tempest colors
            switch (enemy.type) {
                case 'flipper':
                    // Red flipper - walks along lanes
                    this.ctx.strokeStyle = '#ff0000';
                    this.ctx.fillStyle = '#ff0000';
                    if (this.targetComplexity >= 0.4) {
                        this.ctx.shadowColor = '#ff0000';
                        this.ctx.shadowBlur = 8;
                    }
                    this.ctx.lineWidth = 2;
                    this.ctx.globalAlpha = 0.9;

                    // Flipper shape - walking legs
                    const flipAngle = Math.sin(this.time * 8 + enemy.flip) * 0.5;
                    this.ctx.beginPath();
                    this.ctx.moveTo(-size * 0.5, -size * 0.3);
                    this.ctx.lineTo(0, size * 0.3);
                    this.ctx.lineTo(size * 0.5, -size * 0.3);
                    this.ctx.moveTo(-size * 0.3 + flipAngle * size * 0.2, size * 0.3);
                    this.ctx.lineTo(size * 0.3 - flipAngle * size * 0.2, size * 0.3);
                    this.ctx.stroke();
                    break;

                case 'tanker':
                    // Green tanker - splits when shot
                    this.ctx.strokeStyle = '#00ff00';
                    this.ctx.fillStyle = '#00ff00';
                    if (this.targetComplexity >= 0.4) {
                        this.ctx.shadowColor = '#00ff00';
                        this.ctx.shadowBlur = 8;
                    }
                    this.ctx.lineWidth = 2;
                    this.ctx.globalAlpha = 0.9;

                    // Diamond shape
                    this.ctx.beginPath();
                    this.ctx.moveTo(0, -size * 0.5);
                    this.ctx.lineTo(size * 0.4, 0);
                    this.ctx.lineTo(0, size * 0.5);
                    this.ctx.lineTo(-size * 0.4, 0);
                    this.ctx.closePath();
                    this.ctx.stroke();
                    break;

                case 'spiker':
                    // Purple spiker - leaves spikes on the lane
                    this.ctx.strokeStyle = '#ff00ff';
                    this.ctx.fillStyle = '#ff00ff';
                    if (this.targetComplexity >= 0.4) {
                        this.ctx.shadowColor = '#ff00ff';
                        this.ctx.shadowBlur = 8;
                    }
                    this.ctx.lineWidth = 2;
                    this.ctx.globalAlpha = 0.9;

                    // Spiky shape
                    this.ctx.beginPath();
                    for (let i = 0; i < 6; i++) {
                        const a = (i / 6) * Math.PI * 2;
                        const r = i % 2 === 0 ? size * 0.5 : size * 0.25;
                        const px = Math.cos(a) * r;
                        const py = Math.sin(a) * r;
                        if (i === 0) this.ctx.moveTo(px, py);
                        else this.ctx.lineTo(px, py);
                    }
                    this.ctx.closePath();
                    this.ctx.stroke();
                    break;
            }

            this.ctx.restore();
            return true;
        });
    }

    _updateTempestBullets(cx, cy, innerRadius, outerRadius, segments, playerSegment) {
        const bassFreq = this.dataArray ?
            this.dataArray.slice(0, 10).reduce((a, b) => a + b, 0) / 10 / 255 : 0.5;

        // Auto-fire on beat - yellow bolts like the game
        if (bassFreq > 0.35 && Math.random() < 0.25) {
            this.tempestBullets.push({
                segment: playerSegment,
                depth: 1,
                speed: 0.08 // Fast bullets
            });
        }

        // Update and draw bullets
        this.tempestBullets = this.tempestBullets.filter(bullet => {
            bullet.depth -= bullet.speed;

            if (bullet.depth <= 0.05) return false;

            // Check collision with enemies
            for (let i = this.tempestEnemies.length - 1; i >= 0; i--) {
                const enemy = this.tempestEnemies[i];
                if (enemy.segment === bullet.segment &&
                    Math.abs(enemy.depth - bullet.depth) < 0.12) {
                    // Hit! Create explosion
                    const angle = this._getTempestAngle(enemy.segment + 0.5, segments) + this.tempestAngle;
                    const radius = innerRadius + (outerRadius - innerRadius) * Math.pow(enemy.depth, 0.6);
                    this.tempestExplosions.push({
                        x: cx + Math.cos(angle) * radius,
                        y: cy + Math.sin(angle) * radius,
                        life: 1,
                        size: 12 + enemy.depth * 18,
                        color: enemy.type === 'flipper' ? '#ff0000' :
                               enemy.type === 'tanker' ? '#00ff00' : '#ff00ff'
                    });
                    this.tempestEnemies.splice(i, 1);
                    this.tempestScore += 10 + this.tempestLevel * 5;
                    return false;
                }
            }

            const angle = this._getTempestAngle(bullet.segment + 0.5, segments) + this.tempestAngle;
            const radius = innerRadius + (outerRadius - innerRadius) * Math.pow(bullet.depth, 0.6);
            const x = cx + Math.cos(angle) * radius;
            const y = cy + Math.sin(angle) * radius;

            // Draw bullet - bright yellow bolt
            const prevRadius = innerRadius + (outerRadius - innerRadius) * Math.pow(bullet.depth + 0.08, 0.6);
            const px = cx + Math.cos(angle) * prevRadius;
            const py = cy + Math.sin(angle) * prevRadius;

            this.ctx.strokeStyle = '#ffff00';
            this.ctx.lineWidth = 3;
            this.ctx.globalAlpha = 0.9;
            this.ctx.lineCap = 'round';

            if (this.targetComplexity >= 0.4) {
                this.ctx.shadowColor = '#ffff00';
                this.ctx.shadowBlur = 12;
            }

            this.ctx.beginPath();
            this.ctx.moveTo(px, py);
            this.ctx.lineTo(x, y);
            this.ctx.stroke();

            return true;
        });
    }

    _drawTempestExplosions(cx, cy, innerRadius, outerRadius) {
        this.tempestExplosions = this.tempestExplosions.filter(exp => {
            exp.life -= 0.06;
            if (exp.life <= 0) return false;

            const particleCount = Math.floor(6 + 6 * this.targetComplexity);
            const color = exp.color || '#ffff00';

            // Vector-style explosion - radiating lines
            this.ctx.strokeStyle = color;
            this.ctx.lineWidth = 2;
            this.ctx.globalAlpha = exp.life;

            if (this.targetComplexity >= 0.4) {
                this.ctx.shadowColor = color;
                this.ctx.shadowBlur = 10;
            }

            this.ctx.beginPath();
            for (let i = 0; i < particleCount; i++) {
                const angle = (i / particleCount) * Math.PI * 2;
                const innerDist = exp.size * (1 - exp.life) * 0.5;
                const outerDist = exp.size * (1 - exp.life) * 1.5;

                const ix = exp.x + Math.cos(angle) * innerDist;
                const iy = exp.y + Math.sin(angle) * innerDist;
                const ox = exp.x + Math.cos(angle) * outerDist;
                const oy = exp.y + Math.sin(angle) * outerDist;

                this.ctx.moveTo(ix, iy);
                this.ctx.lineTo(ox, oy);
            }
            this.ctx.stroke();

            return true;
        });
    }

    // ========================================
    // PONG GAME VISUALIZATION
    // ========================================

    _drawPong(width, height) {
        const paddleWidth = 15;
        const paddleHeight = height * 0.15;
        const ballSize = 12;
        const margin = 30;

        const avgFreq = this.dataArray ?
            this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255 : 0.5;
        const bassFreq = this.dataArray ?
            this.dataArray.slice(0, 20).reduce((a, b) => a + b, 0) / 20 / 255 : 0.5;
        const trebleFreq = this.dataArray ?
            this.dataArray.slice(-20).reduce((a, b) => a + b, 0) / 20 / 255 : 0.5;

        // Initialize ball position if needed
        if (this.pongBall.x === 0) {
            this.pongBall.x = width / 2;
            this.pongBall.y = height / 2;
        }

        // AI paddle movement based on audio
        const leftTarget = this.pongBall.y / height;
        const rightTarget = this.pongBall.y / height;
        this.pongPaddles.left += (leftTarget - this.pongPaddles.left) * (0.05 + bassFreq * 0.1);
        this.pongPaddles.right += (rightTarget - this.pongPaddles.right) * (0.05 + trebleFreq * 0.1);

        // Clamp paddles
        const halfPaddle = (paddleHeight / 2) / height;
        this.pongPaddles.left = Math.max(halfPaddle, Math.min(1 - halfPaddle, this.pongPaddles.left));
        this.pongPaddles.right = Math.max(halfPaddle, Math.min(1 - halfPaddle, this.pongPaddles.right));

        // Update ball with audio-reactive speed
        const speed = 3 + avgFreq * 8;
        this.pongBall.x += this.pongBall.vx * speed;
        this.pongBall.y += this.pongBall.vy * speed;

        // Ball collision with top/bottom
        if (this.pongBall.y <= ballSize || this.pongBall.y >= height - ballSize) {
            this.pongBall.vy *= -1;
            this.pongBall.y = Math.max(ballSize, Math.min(height - ballSize, this.pongBall.y));
        }

        // Ball collision with paddles
        const leftPaddleY = this.pongPaddles.left * height;
        const rightPaddleY = this.pongPaddles.right * height;

        if (this.pongBall.x <= margin + paddleWidth + ballSize &&
            this.pongBall.y >= leftPaddleY - paddleHeight/2 &&
            this.pongBall.y <= leftPaddleY + paddleHeight/2) {
            this.pongBall.vx = Math.abs(this.pongBall.vx);
            this.pongBall.vy += (this.pongBall.y - leftPaddleY) / paddleHeight * 2;
        }

        if (this.pongBall.x >= width - margin - paddleWidth - ballSize &&
            this.pongBall.y >= rightPaddleY - paddleHeight/2 &&
            this.pongBall.y <= rightPaddleY + paddleHeight/2) {
            this.pongBall.vx = -Math.abs(this.pongBall.vx);
            this.pongBall.vy += (this.pongBall.y - rightPaddleY) / paddleHeight * 2;
        }

        // Score and reset
        if (this.pongBall.x < 0) {
            this.pongScore.right++;
            this._resetPongBall(width, height, 1);
        }
        if (this.pongBall.x > width) {
            this.pongScore.left++;
            this._resetPongBall(width, height, -1);
        }

        // Store trail
        if (this.targetComplexity >= 0.6) {
            this.pongTrail.push({ x: this.pongBall.x, y: this.pongBall.y });
            if (this.pongTrail.length > 20) this.pongTrail.shift();
        }

        // Draw center line
        this.ctx.strokeStyle = this.colors.secondary;
        this.ctx.lineWidth = 2;
        this.ctx.globalAlpha = 0.3;
        this.ctx.setLineDash([10, 10]);
        this.ctx.beginPath();
        this.ctx.moveTo(width / 2, 0);
        this.ctx.lineTo(width / 2, height);
        this.ctx.stroke();
        this.ctx.setLineDash([]);

        // Draw score
        this.ctx.font = 'bold 48px monospace';
        this.ctx.fillStyle = this.colors.primary;
        this.ctx.globalAlpha = 0.5;
        this.ctx.textAlign = 'center';
        this.ctx.fillText(this.pongScore.left.toString(), width * 0.25, 60);
        this.ctx.fillText(this.pongScore.right.toString(), width * 0.75, 60);

        // Draw trail
        if (this.pongTrail.length > 1) {
            this.ctx.strokeStyle = this.colors.tertiary;
            this.ctx.lineWidth = 2;
            this.ctx.globalAlpha = 0.3;
            this.ctx.beginPath();
            this.ctx.moveTo(this.pongTrail[0].x, this.pongTrail[0].y);
            for (let i = 1; i < this.pongTrail.length; i++) {
                this.ctx.lineTo(this.pongTrail[i].x, this.pongTrail[i].y);
            }
            this.ctx.stroke();
        }

        // Draw paddles with glow
        this.ctx.fillStyle = this.colors.primary;
        this.ctx.globalAlpha = 1;
        if (this.targetComplexity >= 0.5) {
            this.ctx.shadowColor = this.colors.primary;
            this.ctx.shadowBlur = 15 + bassFreq * 20;
        }

        // Left paddle
        this.ctx.beginPath();
        this.ctx.roundRect(margin, leftPaddleY - paddleHeight/2, paddleWidth, paddleHeight, 4);
        this.ctx.fill();

        // Right paddle
        this.ctx.fillStyle = this.colors.secondary;
        if (this.targetComplexity >= 0.5) {
            this.ctx.shadowColor = this.colors.secondary;
        }
        this.ctx.beginPath();
        this.ctx.roundRect(width - margin - paddleWidth, rightPaddleY - paddleHeight/2, paddleWidth, paddleHeight, 4);
        this.ctx.fill();

        // Draw ball with glow
        this.ctx.fillStyle = this.colors.tertiary;
        if (this.targetComplexity >= 0.5) {
            this.ctx.shadowColor = this.colors.tertiary;
            this.ctx.shadowBlur = 20 + avgFreq * 30;
        }
        this.ctx.beginPath();
        this.ctx.arc(this.pongBall.x, this.pongBall.y, ballSize + avgFreq * 5, 0, Math.PI * 2);
        this.ctx.fill();

        this.ctx.shadowBlur = 0;
        this.ctx.globalAlpha = 1;
    }

    _resetPongBall(width, height, direction) {
        this.pongBall.x = width / 2;
        this.pongBall.y = height / 2;
        this.pongBall.vx = direction * (2 + Math.random());
        this.pongBall.vy = (Math.random() - 0.5) * 3;
        this.pongTrail = [];
    }

    // ========================================
    // BREAKOUT GAME VISUALIZATION
    // ========================================

    _drawBreakout(width, height) {
        const paddleWidth = width * 0.15;
        const paddleHeight = 15;
        const ballSize = 10;
        const brickRows = 5;
        const brickCols = 10;
        const brickWidth = (width - 40) / brickCols;
        const brickHeight = 25;

        const avgFreq = this.dataArray ?
            this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255 : 0.5;
        const bassFreq = this.dataArray ?
            this.dataArray.slice(0, 20).reduce((a, b) => a + b, 0) / 20 / 255 : 0.5;

        // Initialize bricks if needed
        if (this.breakoutBricks.length === 0) {
            this._initBreakoutBricks(brickRows, brickCols);
        }

        // Initialize ball position if needed
        if (this.breakoutBall.x === 0) {
            this.breakoutBall.x = width / 2;
            this.breakoutBall.y = height - 100;
        }

        // AI paddle tracks the ball with some prediction
        // Calculate where ball will be when it reaches paddle height
        const paddleY = height - 40;
        let predictedX = this.breakoutBall.x;

        if (this.breakoutBall.vy > 0) { // Ball is moving down
            const timeToReach = (paddleY - this.breakoutBall.y) / (this.breakoutBall.vy * (4 + avgFreq * 6));
            predictedX = this.breakoutBall.x + this.breakoutBall.vx * (4 + avgFreq * 6) * timeToReach;

            // Account for wall bounces
            while (predictedX < 0 || predictedX > width) {
                if (predictedX < 0) predictedX = -predictedX;
                if (predictedX > width) predictedX = 2 * width - predictedX;
            }
        }

        // Move paddle toward predicted position with some smoothing
        const targetPaddle = predictedX / width;
        const paddleSpeed = 0.15 + bassFreq * 0.1; // Faster reaction on bass
        this.breakoutPaddle += (targetPaddle - this.breakoutPaddle) * paddleSpeed;
        this.breakoutPaddle = Math.max(0.1, Math.min(0.9, this.breakoutPaddle));

        // Update ball
        const speed = 4 + avgFreq * 6;
        this.breakoutBall.x += this.breakoutBall.vx * speed;
        this.breakoutBall.y += this.breakoutBall.vy * speed;

        // Wall collisions
        if (this.breakoutBall.x <= ballSize || this.breakoutBall.x >= width - ballSize) {
            this.breakoutBall.vx *= -1;
        }
        if (this.breakoutBall.y <= ballSize) {
            this.breakoutBall.vy *= -1;
        }

        // Paddle collision
        const paddleX = this.breakoutPaddle * width - paddleWidth / 2;
        // paddleY already defined above
        if (this.breakoutBall.y >= paddleY - ballSize &&
            this.breakoutBall.y <= paddleY + paddleHeight &&
            this.breakoutBall.x >= paddleX &&
            this.breakoutBall.x <= paddleX + paddleWidth) {
            this.breakoutBall.vy = -Math.abs(this.breakoutBall.vy);
            const hitPos = (this.breakoutBall.x - paddleX) / paddleWidth;
            this.breakoutBall.vx = (hitPos - 0.5) * 8;
        }

        // Ball lost
        if (this.breakoutBall.y > height) {
            this.breakoutBall.x = width / 2;
            this.breakoutBall.y = height - 100;
            this.breakoutBall.vy = -Math.abs(this.breakoutBall.vy);
        }

        // Brick collisions
        this._checkBreakoutBrickCollisions(brickWidth, brickHeight);

        // Draw bricks
        for (const brick of this.breakoutBricks) {
            if (!brick.alive) continue;

            const x = 20 + brick.col * brickWidth;
            const y = 60 + brick.row * brickHeight;

            this.ctx.fillStyle = brick.color;
            this.ctx.globalAlpha = 0.9;
            if (this.targetComplexity >= 0.5) {
                this.ctx.shadowColor = brick.color;
                this.ctx.shadowBlur = 10 + bassFreq * 15;
            }
            this.ctx.beginPath();
            this.ctx.roundRect(x + 2, y + 2, brickWidth - 4, brickHeight - 4, 4);
            this.ctx.fill();
        }

        // Draw paddle
        this.ctx.fillStyle = this.colors.tertiary;
        this.ctx.globalAlpha = 1;
        if (this.targetComplexity >= 0.5) {
            this.ctx.shadowColor = this.colors.tertiary;
            this.ctx.shadowBlur = 15 + bassFreq * 20;
        }
        this.ctx.beginPath();
        this.ctx.roundRect(paddleX, paddleY, paddleWidth, paddleHeight, 4);
        this.ctx.fill();

        // Draw ball
        this.ctx.fillStyle = this.colors.primary;
        if (this.targetComplexity >= 0.5) {
            this.ctx.shadowColor = this.colors.primary;
            this.ctx.shadowBlur = 20 + avgFreq * 30;
        }
        this.ctx.beginPath();
        this.ctx.arc(this.breakoutBall.x, this.breakoutBall.y, ballSize + avgFreq * 3, 0, Math.PI * 2);
        this.ctx.fill();

        // Draw score
        this.ctx.font = 'bold 24px monospace';
        this.ctx.fillStyle = this.colors.secondary;
        this.ctx.globalAlpha = 0.7;
        this.ctx.textAlign = 'right';
        this.ctx.shadowBlur = 0;
        this.ctx.fillText(`Score: ${this.breakoutScore}`, width - 30, 40);

        // Reset bricks if all destroyed
        if (this.breakoutBricks.every(b => !b.alive)) {
            this._initBreakoutBricks(brickRows, brickCols);
        }

        this.ctx.shadowBlur = 0;
        this.ctx.globalAlpha = 1;
    }

    _initBreakoutBricks(rows, cols) {
        this.breakoutBricks = [];
        const colors = [this.colors.primary, this.colors.secondary, this.colors.tertiary];
        for (let row = 0; row < rows; row++) {
            for (let col = 0; col < cols; col++) {
                this.breakoutBricks.push({
                    row, col,
                    alive: true,
                    color: colors[row % 3]
                });
            }
        }
    }

    _checkBreakoutBrickCollisions(brickWidth, brickHeight) {
        for (const brick of this.breakoutBricks) {
            if (!brick.alive) continue;

            const bx = 20 + brick.col * brickWidth;
            const by = 60 + brick.row * brickHeight;

            if (this.breakoutBall.x >= bx && this.breakoutBall.x <= bx + brickWidth &&
                this.breakoutBall.y >= by && this.breakoutBall.y <= by + brickHeight) {
                brick.alive = false;
                this.breakoutBall.vy *= -1;
                this.breakoutScore += 10;
                break;
            }
        }
    }

    // ========================================
    // SNAKE GAME VISUALIZATION
    // ========================================

    _drawSnake(width, height) {
        const gridSize = 20;
        const cols = Math.floor(width / gridSize);
        const rows = Math.floor(height / gridSize);

        const avgFreq = this.dataArray ?
            this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255 : 0.5;
        const bassFreq = this.dataArray ?
            this.dataArray.slice(0, 20).reduce((a, b) => a + b, 0) / 20 / 255 : 0.5;

        // Initialize snake if needed
        if (this.snake.length === 0) {
            this.snake = [
                { x: Math.floor(cols / 2), y: Math.floor(rows / 2) }
            ];
            this.snakeFood = this._randomSnakeFood(cols, rows);
        }

        // Move based on time and audio (faster with louder audio)
        const now = performance.now();
        const moveInterval = 150 - avgFreq * 80; // 150ms to 70ms
        if (now - this.snakeLastMove > moveInterval) {
            this.snakeLastMove = now;

            // AI: Turn toward food
            const head = this.snake[0];
            if (this.snakeFood) {
                const dx = this.snakeFood.x - head.x;
                const dy = this.snakeFood.y - head.y;

                // Change direction based on audio and food position
                if (Math.random() < 0.3 + bassFreq * 0.5) {
                    if (Math.abs(dx) > Math.abs(dy)) {
                        this.snakeDir = { x: dx > 0 ? 1 : -1, y: 0 };
                    } else {
                        this.snakeDir = { x: 0, y: dy > 0 ? 1 : -1 };
                    }
                }
            }

            // Move snake
            const newHead = {
                x: (head.x + this.snakeDir.x + cols) % cols,
                y: (head.y + this.snakeDir.y + rows) % rows
            };
            this.snake.unshift(newHead);

            // Check food collision
            if (this.snakeFood && newHead.x === this.snakeFood.x && newHead.y === this.snakeFood.y) {
                this.snakeScore += 10;
                this.snakeFood = this._randomSnakeFood(cols, rows);
            } else {
                this.snake.pop();
            }

            // Check self-collision (reset if hit)
            for (let i = 1; i < this.snake.length; i++) {
                if (this.snake[i].x === newHead.x && this.snake[i].y === newHead.y) {
                    this.snake = [{ x: Math.floor(cols / 2), y: Math.floor(rows / 2) }];
                    break;
                }
            }
        }

        // Draw grid (subtle)
        this.ctx.strokeStyle = 'rgba(255,255,255,0.05)';
        this.ctx.lineWidth = 1;
        for (let x = 0; x <= cols; x++) {
            this.ctx.beginPath();
            this.ctx.moveTo(x * gridSize, 0);
            this.ctx.lineTo(x * gridSize, rows * gridSize);
            this.ctx.stroke();
        }
        for (let y = 0; y <= rows; y++) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y * gridSize);
            this.ctx.lineTo(cols * gridSize, y * gridSize);
            this.ctx.stroke();
        }

        // Draw snake
        for (let i = 0; i < this.snake.length; i++) {
            const segment = this.snake[i];
            const isHead = i === 0;
            const alpha = 1 - (i / this.snake.length) * 0.5;

            this.ctx.fillStyle = isHead ? this.colors.tertiary : this.colors.primary;
            this.ctx.globalAlpha = alpha;
            if (this.targetComplexity >= 0.5) {
                this.ctx.shadowColor = this.ctx.fillStyle;
                this.ctx.shadowBlur = isHead ? 20 + bassFreq * 20 : 10;
            }
            this.ctx.beginPath();
            this.ctx.roundRect(
                segment.x * gridSize + 2,
                segment.y * gridSize + 2,
                gridSize - 4,
                gridSize - 4,
                isHead ? 6 : 4
            );
            this.ctx.fill();
        }

        // Draw food
        if (this.snakeFood) {
            const pulse = Math.sin(this.time * 5) * 0.3 + 1;
            this.ctx.fillStyle = this.colors.secondary;
            this.ctx.globalAlpha = 1;
            if (this.targetComplexity >= 0.5) {
                this.ctx.shadowColor = this.colors.secondary;
                this.ctx.shadowBlur = 15 + avgFreq * 20;
            }
            this.ctx.beginPath();
            this.ctx.arc(
                this.snakeFood.x * gridSize + gridSize / 2,
                this.snakeFood.y * gridSize + gridSize / 2,
                (gridSize / 2 - 2) * pulse,
                0, Math.PI * 2
            );
            this.ctx.fill();
        }

        // Draw score
        this.ctx.font = 'bold 24px monospace';
        this.ctx.fillStyle = this.colors.primary;
        this.ctx.globalAlpha = 0.7;
        this.ctx.textAlign = 'right';
        this.ctx.shadowBlur = 0;
        this.ctx.fillText(`Score: ${this.snakeScore}`, width - 30, 40);

        this.ctx.shadowBlur = 0;
        this.ctx.globalAlpha = 1;
    }

    _randomSnakeFood(cols, rows) {
        return {
            x: Math.floor(Math.random() * cols),
            y: Math.floor(Math.random() * rows)
        };
    }

    // ========================================
    // RANDOM MODE (AUTO-SWITCH)
    // ========================================

    _drawRandom(width, height) {
        // Switch mode every 10-20 seconds based on audio
        const avgFreq = this.dataArray ?
            this.dataArray.reduce((a, b) => a + b, 0) / this.dataArray.length / 255 : 0.5;

        this.randomModeTimer += 1;
        const switchInterval = 600 - avgFreq * 300; // 10-20 seconds at 60fps

        if (this.randomModeTimer >= switchInterval) {
            this.randomModeTimer = 0;
            // Pick a random mode different from current
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

    // Easing functions
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
