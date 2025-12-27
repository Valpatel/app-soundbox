/**
 * Breakout Visualization
 * Classic brick-breaking game with audio-reactive paddle
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._drawBreakout = function(width, height) {
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

        // AI paddle tracks the ball with prediction
        const paddleY = height - 40;
        let predictedX = this.breakoutBall.x;

        if (this.breakoutBall.vy > 0) {
            const timeToReach = (paddleY - this.breakoutBall.y) / (this.breakoutBall.vy * (4 + avgFreq * 6));
            predictedX = this.breakoutBall.x + this.breakoutBall.vx * (4 + avgFreq * 6) * timeToReach;

            while (predictedX < 0 || predictedX > width) {
                if (predictedX < 0) predictedX = -predictedX;
                if (predictedX > width) predictedX = 2 * width - predictedX;
            }
        }

        const targetPaddle = predictedX / width;
        const paddleSpeed = 0.15 + bassFreq * 0.1;
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
    };

    Visualizer.prototype._initBreakoutBricks = function(rows, cols) {
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
    };

    Visualizer.prototype._checkBreakoutBrickCollisions = function(brickWidth, brickHeight) {
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
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
