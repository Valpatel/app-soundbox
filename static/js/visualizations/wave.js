/**
 * Wave Visualization
 * Multiple layered audio waves with smooth curves
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._drawWave = function(width, height) {
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
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
