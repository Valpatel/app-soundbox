/**
 * Particles Visualization
 * Audio-reactive floating particles with trails and connections
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._initParticles = function() {
        const width = this.canvas.width / window.devicePixelRatio;
        const height = this.canvas.height / window.devicePixelRatio;

        this.particles = [];
        for (let i = 0; i < this.maxParticles * this.targetComplexity; i++) {
            this.particles.push(this._createParticle(width, height));
        }
    };

    Visualizer.prototype._createParticle = function(width, height) {
        width = width || 800;
        height = height || 600;
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
    };

    Visualizer.prototype._drawParticles = function(width, height) {
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
    };

    Visualizer.prototype._drawStaticParticles = function(width, height) {
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
    };

    Visualizer.prototype._drawParticleConnections = function(width, height, avgFreq) {
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
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
