/**
 * Lissajous Visualization
 * Mathematical curves modulated by audio with spirograph overlay
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._drawLissajous = function(width, height) {
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
    };

    Visualizer.prototype._drawSpirograph = function(width, height, intensity) {
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
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
