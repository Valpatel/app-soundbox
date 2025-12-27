/**
 * Pong Visualization
 * Classic Pong game with audio-reactive paddles and ball
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._drawPong = function(width, height) {
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
    };

    Visualizer.prototype._resetPongBall = function(width, height, direction) {
        this.pongBall.x = width / 2;
        this.pongBall.y = height / 2;
        this.pongBall.vx = direction * (2 + Math.random());
        this.pongBall.vy = (Math.random() - 0.5) * 3;
        this.pongTrail = [];
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
