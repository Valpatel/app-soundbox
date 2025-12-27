/**
 * Bar EQ Visualization
 * Classic equalizer bars with mirror effect
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._drawBars = function(width, height) {
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
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
