const GRID_SIZE = 20;
const CANVAS_SIZE = 400;
const CELL_SIZE = CANVAS_SIZE / GRID_SIZE;
const TICK_MS = 150;

const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');

let snake, direction, nextDirection, food, score, highScore, gameLoop, gameState;

function init() {
    snake = [
        { x: 10, y: 10 },
        { x: 9,  y: 10 },
        { x: 8,  y: 10 },
    ];
    direction     = { x: 1, y: 0 };
    nextDirection = { x: 1, y: 0 };
    score     = 0;
    highScore = parseInt(localStorage.getItem('snakeHighScore') || '0');
    gameState = 'idle';
    placeFood();
    updateHUD();
    render();
    hideOverlay();
    document.getElementById('game-message').textContent = 'Press START or Space to play';
}

function placeFood() {
    let pos;
    do {
        pos = {
            x: Math.floor(Math.random() * GRID_SIZE),
            y: Math.floor(Math.random() * GRID_SIZE),
        };
    } while (snake.some(s => s.x === pos.x && s.y === pos.y));
    food = pos;
}

function tick() {
    direction = nextDirection;
    const head = { x: snake[0].x + direction.x, y: snake[0].y + direction.y };

    if (head.x < 0 || head.x >= GRID_SIZE || head.y < 0 || head.y >= GRID_SIZE) {
        endGame();
        return;
    }

    if (snake.some(s => s.x === head.x && s.y === head.y)) {
        endGame();
        return;
    }

    snake.unshift(head);

    if (head.x === food.x && head.y === food.y) {
        score += 10;
        if (score > highScore) {
            highScore = score;
            localStorage.setItem('snakeHighScore', highScore);
        }
        updateHUD();
        placeFood();
    } else {
        snake.pop();
    }

    render();
}

function render() {
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

    // Subtle grid
    ctx.strokeStyle = '#0d1526';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= GRID_SIZE; i++) {
        ctx.beginPath();
        ctx.moveTo(i * CELL_SIZE, 0);
        ctx.lineTo(i * CELL_SIZE, CANVAS_SIZE);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, i * CELL_SIZE);
        ctx.lineTo(CANVAS_SIZE, i * CELL_SIZE);
        ctx.stroke();
    }

    // Food
    ctx.fillStyle = '#ef4444';
    ctx.fillRect(
        food.x * CELL_SIZE + 2,
        food.y * CELL_SIZE + 2,
        CELL_SIZE - 4,
        CELL_SIZE - 4
    );

    // Snake — head brighter, tail darker
    snake.forEach((seg, i) => {
        ctx.fillStyle = i === 0 ? '#4ade80' : i < 4 ? '#22c55e' : '#16a34a';
        ctx.fillRect(
            seg.x * CELL_SIZE + 1,
            seg.y * CELL_SIZE + 1,
            CELL_SIZE - 2,
            CELL_SIZE - 2
        );
    });
}

function updateHUD() {
    document.getElementById('score').textContent     = score;
    document.getElementById('high-score').textContent = highScore;
    document.getElementById('length').textContent    = snake.length;
}

function startGame() {
    if (gameState === 'running') return;
    init();
    gameState = 'running';
    document.getElementById('start-btn').disabled = true;
    document.getElementById('game-message').textContent = '';
    gameLoop = setInterval(tick, TICK_MS);
}

function endGame() {
    clearInterval(gameLoop);
    gameState = 'dead';
    document.getElementById('start-btn').disabled = false;
    showGameOver();
}

function showGameOver() {
    document.getElementById('final-score').textContent = `Score: ${score}`;
    document.getElementById('game-over-overlay').style.display = 'flex';
    document.getElementById('player-name').value = '';
    document.getElementById('player-name').focus();
}

function hideOverlay() {
    document.getElementById('game-over-overlay').style.display = 'none';
}

async function submitScore() {
    const name = document.getElementById('player-name').value.trim();
    if (!name) {
        document.getElementById('player-name').focus();
        return;
    }

    try {
        const resp = await fetch('/api/scores', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, score }),
        });
        if (resp.ok) {
            hideOverlay();
            await loadLeaderboard();
        } else {
            // Score submission not yet implemented — hide and continue
            hideOverlay();
        }
    } catch {
        hideOverlay();
    }
}

async function loadLeaderboard() {
    try {
        const resp   = await fetch('/api/scores');
        const scores = await resp.json();
        renderLeaderboard(scores);
    } catch {
        // Silently ignore — leaderboard is not critical
    }
}

function renderLeaderboard(scores) {
    const tbody = document.getElementById('leaderboard-body');
    if (!scores || scores.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="empty-state">No scores yet</td></tr>';
        return;
    }
    tbody.innerHTML = scores
        .map((s, i) => `
            <tr>
                <td class="rank-cell">${i + 1}</td>
                <td>${escapeHtml(s.name)}</td>
                <td>${s.score}</td>
            </tr>
        `)
        .join('');
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Keyboard controls
document.addEventListener('keydown', e => {
    switch (e.key) {
        case 'ArrowUp':
        case 'w': case 'W':
            if (direction.y !== 1) nextDirection = { x: 0, y: -1 };
            e.preventDefault();
            break;
        case 'ArrowDown':
        case 's': case 'S':
            if (direction.y !== -1) nextDirection = { x: 0, y: 1 };
            e.preventDefault();
            break;
        case 'ArrowLeft':
        case 'a': case 'A':
            if (direction.x !== 1) nextDirection = { x: -1, y: 0 };
            e.preventDefault();
            break;
        case 'ArrowRight':
        case 'd': case 'D':
            if (direction.x !== -1) nextDirection = { x: 1, y: 0 };
            e.preventDefault();
            break;
        case ' ':
            if (gameState !== 'running') startGame();
            e.preventDefault();
            break;
        case 'Enter':
            if (gameState === 'dead') submitScore();
            break;
    }
});

window.addEventListener('load', () => {
    init();
    loadLeaderboard();
});
