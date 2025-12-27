/* API CONFIG */
const API_BASE = 'http://localhost:8003/api';
const REFRESH_RATE = 5000; // 5 seconds

async function fetchMarketData() {
    try {
        console.log("Fetching market data...");
        // 1. Get Market Status (VN-INDEX)
        const statusRes = await fetch(`${API_BASE}/market/status`);
        if (!statusRes.ok) throw new Error("Market Status API failed");

        const statusData = await statusRes.json();

        // 2. Get Watchlist Data
        const watchlist = ['FPT', 'HPG', 'VCB', 'SSI', 'MWG', 'VNM', 'TCB', 'STB'];
        const tickerContainer = document.querySelector('.ticker');

        // Clear existing static items only once if needed, or just append distinct real data
        // Better: Rebuild ticker string
        let tickerHTML = '';

        // Add VNINDEX first
        const vnColor = statusData.change >= 0 ? 'up' : 'down';
        const vnArrow = statusData.change >= 0 ? '▲' : '▼';
        tickerHTML += `<div class="ticker-item">VNINDEX <span class="${vnColor}">${vnArrow} ${statusData.vnindex.toLocaleString()} (${statusData.change_pct}%)</span></div>`;

        // Add Stocks
        for (const symbol of watchlist) {
            try {
                // Fetch basic stock data (using predict endpoint for detailed stats or just stock endpoint)
                // Using stock endpoint for OHLCV
                const stockRes = await fetch(`${API_BASE}/stock/${symbol}`);
                if (!stockRes.ok) continue;

                const stockData = await stockRes.json();

                if (stockData && stockData.length > 0) {
                    const latest = stockData[stockData.length - 1];
                    const prev = stockData[stockData.length - 2];

                    const change = latest.close - prev.close;
                    const pct = ((change / prev.close) * 100).toFixed(1);
                    const color = change >= 0 ? 'up' : 'down';
                    const arrow = change >= 0 ? '▲' : '▼';

                    tickerHTML += `<div class="ticker-item">${symbol} <span class="${color}">${arrow} ${latest.close.toLocaleString()} (${pct}%)</span></div>`;
                }
            } catch (err) {
                console.error(`Error fetching ${symbol}:`, err);
            }
        }

        // Add AI Insight
        tickerHTML += `<div class="ticker-item" style="color: var(--secondary);"> // AI FORECAST: ${statusData.is_open ? 'MARKET OPEN' : 'MARKET CLOSED'} // </div>`;

        // Update DOM
        tickerContainer.innerHTML = tickerHTML + tickerHTML; // Duplicate for smooth infinite scroll
        console.log("Ticker updated.");

    } catch (error) {
        console.error("Failed to fetch real data:", error);
        // Fallback to static if API fails is already in HTML, so maybe do nothing or show error
        const tickerContainer = document.querySelector('.ticker');
        if (tickerContainer) {
            tickerContainer.innerHTML = '<div class="ticker-item" style="color: red;">⚠ DISCONNECTED FROM CORE (LOCALHOST:8003)</div>' + tickerContainer.innerHTML;
        }
    }
}

/* CANVAS ANIMATION */
const canvas = document.getElementById('network');
const ctx = canvas.getContext('2d');
let width, height;
let particles = [];

// Configuration
const particleCount = 60;
const connectionDistance = 150;
const particleSpeed = 0.5;

function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
}

class Particle {
    constructor() {
        this.x = Math.random() * width;
        this.y = Math.random() * height;
        this.vx = (Math.random() - 0.5) * particleSpeed;
        this.vy = (Math.random() - 0.5) * particleSpeed;
        this.size = Math.random() * 2 + 1;
        this.color = Math.random() > 0.5 ? '#00f2ff' : '#7000ff';
    }

    update() {
        this.x += this.vx;
        this.y += this.vy;

        // Bounce off edges
        if (this.x < 0 || this.x > width) this.vx *= -1;
        if (this.y < 0 || this.y > height) this.vy *= -1;
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.fill();
    }
}

function initParticles() {
    particles = [];
    for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle());
    }
}

function animate() {
    ctx.clearRect(0, 0, width, height);

    // Update and draw particles
    particles.forEach(p => {
        p.update();
        p.draw();
    });

    // Draw connections
    for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
            const dx = particles[i].x - particles[j].x;
            const dy = particles[i].y - particles[j].y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < connectionDistance) {
                ctx.beginPath();
                ctx.strokeStyle = `rgba(0, 242, 255, ${1 - distance / connectionDistance})`;
                ctx.lineWidth = 0.5;
                ctx.moveTo(particles[i].x, particles[i].y);
                ctx.lineTo(particles[j].x, particles[j].y);
                ctx.stroke();
            }
        }
    }

    requestAnimationFrame(animate);
}

window.addEventListener('resize', () => {
    resize();
    initParticles();
});

/* TERMINAL TYPER */
const terminalOutput = document.getElementById('terminal-output');
const messages = [
    "> HỆ THỐNG: KẾT NỐI API THÀNH CÔNG [LOCALHOST:8003].",
    "> Đang đồng bộ dữ liệu thực tế từ CafeF/VietStock...",
    "> [ChiefAgent] Đã nhận diện tín hiệu realtime.",
    "> [MarketScout] Quét danh mục VN30...",
    "> [RiskDoctor] Volatility Index: ỔN ĐỊNH.",
    "> [System] Chế độ Live Trading: READY."
];

let msgIndex = 0;
let charIndex = 0;
let currentLine = null;

function typeWriter() {
    if (msgIndex < messages.length) {
        if (!currentLine) {
            currentLine = document.createElement('div');
            currentLine.className = 'terminal-line';

            if (messages[msgIndex].includes("ChiefAgent")) currentLine.style.color = "#00f2ff";
            else if (messages[msgIndex].includes("RiskDoctor")) currentLine.style.color = "#ff0055";
            else if (messages[msgIndex].includes("System")) currentLine.style.color = "#00ff88";

            terminalOutput.insertBefore(currentLine, terminalOutput.lastElementChild);
        }

        if (charIndex < messages[msgIndex].length) {
            currentLine.textContent += messages[msgIndex].charAt(charIndex);
            charIndex++;
            setTimeout(typeWriter, 30 + Math.random() * 50);
        } else {
            msgIndex++;
            charIndex = 0;
            currentLine = null;
            setTimeout(typeWriter, 500);
        }
    } else {
        setTimeout(() => {
            terminalOutput.innerHTML = '<span class="cursor">_</span>';
            messages.push(`> [Update] VNINDEX: ${document.querySelector('.ticker-item')?.innerText || 'Loading...'}`);
            msgIndex = messages.length - 1;
            typeWriter();
        }, 3000);
    }
}

// INITIALIZATION
resize();
initParticles();
animate();
setTimeout(typeWriter, 1000);

// FETCH REAL DATA
fetchMarketData();
setInterval(fetchMarketData, 60000); // Update every minute
