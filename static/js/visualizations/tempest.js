/**
 * Tempest Visualization
 * Classic arcade-style tube shooter with vector graphics
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._drawTempest = function(width, height) {
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
            const ix = centerX + Math.cos(angle) * innerRadius;
            const iy = centerY + Math.sin(angle) * innerRadius;
            const ox = centerX + Math.cos(angle) * outerRadius;
            const oy = centerY + Math.sin(angle) * outerRadius;

            this.ctx.moveTo(ix, iy);
            this.ctx.lineTo(ox, oy);
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
    };

    Visualizer.prototype._getTempestSegments = function() {
        switch (this.tempestCurrentShape) {
            case 'hexagon': return 6;
            case 'octagon': return 8;
            case 'star': return 10;
            case 'square': return 4;
            case 'circle':
            default: return 16;
        }
    };

    Visualizer.prototype._getTempestAngle = function(segment, totalSegments) {
        return (segment / totalSegments) * Math.PI * 2 - Math.PI / 2; // Start from top
    };

    Visualizer.prototype._drawTempestPlayer = function(x, y, angle, intensity, segments) {
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
    };

    Visualizer.prototype._updateTempestEnemies = function(cx, cy, innerRadius, outerRadius, segments, bassFreq) {
        // Spawn enemies from the center on bass hits
        if (bassFreq > 0.45 && Math.random() < 0.15 * this.targetComplexity) {
            const segment = Math.floor(Math.random() * segments);
            const types = ['flipper', 'tanker', 'spiker'];
            this.tempestEnemies.push({
                segment: segment,
                depth: 0,
                speed: 0.006 + Math.random() * 0.01 + this.tempestLevel * 0.002,
                type: types[Math.floor(Math.random() * types.length)],
                flip: 0,
                lane: segment
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
                    this.ctx.strokeStyle = '#ff0000';
                    this.ctx.fillStyle = '#ff0000';
                    if (this.targetComplexity >= 0.4) {
                        this.ctx.shadowColor = '#ff0000';
                        this.ctx.shadowBlur = 8;
                    }
                    this.ctx.lineWidth = 2;
                    this.ctx.globalAlpha = 0.9;

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
                    this.ctx.strokeStyle = '#00ff00';
                    this.ctx.fillStyle = '#00ff00';
                    if (this.targetComplexity >= 0.4) {
                        this.ctx.shadowColor = '#00ff00';
                        this.ctx.shadowBlur = 8;
                    }
                    this.ctx.lineWidth = 2;
                    this.ctx.globalAlpha = 0.9;

                    this.ctx.beginPath();
                    this.ctx.moveTo(0, -size * 0.5);
                    this.ctx.lineTo(size * 0.4, 0);
                    this.ctx.lineTo(0, size * 0.5);
                    this.ctx.lineTo(-size * 0.4, 0);
                    this.ctx.closePath();
                    this.ctx.stroke();
                    break;

                case 'spiker':
                    this.ctx.strokeStyle = '#ff00ff';
                    this.ctx.fillStyle = '#ff00ff';
                    if (this.targetComplexity >= 0.4) {
                        this.ctx.shadowColor = '#ff00ff';
                        this.ctx.shadowBlur = 8;
                    }
                    this.ctx.lineWidth = 2;
                    this.ctx.globalAlpha = 0.9;

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
    };

    Visualizer.prototype._updateTempestBullets = function(cx, cy, innerRadius, outerRadius, segments, playerSegment) {
        const bassFreq = this.dataArray ?
            this.dataArray.slice(0, 10).reduce((a, b) => a + b, 0) / 10 / 255 : 0.5;

        // Auto-fire on beat
        if (bassFreq > 0.35 && Math.random() < 0.25) {
            this.tempestBullets.push({
                segment: playerSegment,
                depth: 1,
                speed: 0.08
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
    };

    Visualizer.prototype._drawTempestExplosions = function(cx, cy, innerRadius, outerRadius) {
        this.tempestExplosions = this.tempestExplosions.filter(exp => {
            exp.life -= 0.06;
            if (exp.life <= 0) return false;

            const particleCount = Math.floor(6 + 6 * this.targetComplexity);
            const color = exp.color || '#ffff00';

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
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
