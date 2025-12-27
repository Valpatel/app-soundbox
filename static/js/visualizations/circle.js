/**
 * Circle Visualization
 * Radial frequency bars with rotating rings and pulsing orb
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._drawCircle = function(width, height) {
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
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
