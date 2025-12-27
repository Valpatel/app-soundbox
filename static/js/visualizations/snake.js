/**
 * Snake Visualization
 * Classic Snake game with audio-reactive movement speed
 */

(function(Visualizer) {
    'use strict';

    Visualizer.prototype._drawSnake = function(width, height) {
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
    };

    Visualizer.prototype._randomSnakeFood = function(cols, rows) {
        return {
            x: Math.floor(Math.random() * cols),
            y: Math.floor(Math.random() * rows)
        };
    };

})(window.RadioWidgetVisualizer || (window.RadioWidgetVisualizer = function() {}));
