/**
 * Simple line chart using Canvas API.
 */
const Chart = {
    draw(canvasId, data, options = {}) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const rect = canvas.getBoundingClientRect();

        canvas.width = rect.width * dpr;
        canvas.height = rect.height * dpr;
        ctx.scale(dpr, dpr);

        const w = rect.width;
        const h = rect.height;
        const padding = { top: 20, right: 16, bottom: 30, left: 36 };

        const chartW = w - padding.left - padding.right;
        const chartH = h - padding.top - padding.bottom;

        const values = data.map(d => d.value);
        const labels = data.map(d => d.label);
        const maxVal = Math.max(...values, 1);

        // Clear
        ctx.clearRect(0, 0, w, h);

        // Grid lines
        const isDark = document.body.classList.contains('dark');
        ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)';
        ctx.lineWidth = 1;
        for (let i = 0; i <= 4; i++) {
            const y = padding.top + (chartH / 4) * i;
            ctx.beginPath();
            ctx.moveTo(padding.left, y);
            ctx.lineTo(w - padding.right, y);
            ctx.stroke();
        }

        // Y-axis labels
        ctx.fillStyle = isDark ? '#9CA3AF' : '#6B7280';
        ctx.font = '11px -apple-system, sans-serif';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 4; i++) {
            const y = padding.top + (chartH / 4) * i;
            const val = Math.round(maxVal - (maxVal / 4) * i);
            ctx.fillText(val + 'm', padding.left - 6, y + 4);
        }

        // X-axis labels
        ctx.textAlign = 'center';
        const stepX = chartW / Math.max(labels.length - 1, 1);
        labels.forEach((label, i) => {
            const x = padding.left + stepX * i;
            ctx.fillText(label, x, h - 8);
        });

        if (values.length < 2) return;

        // Line
        const points = values.map((v, i) => ({
            x: padding.left + stepX * i,
            y: padding.top + chartH - (v / maxVal) * chartH,
        }));

        // Gradient fill
        const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
        gradient.addColorStop(0, 'rgba(108, 92, 231, 0.3)');
        gradient.addColorStop(1, 'rgba(108, 92, 231, 0.02)');

        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            const cp1x = (points[i - 1].x + points[i].x) / 2;
            const cp1y = points[i - 1].y;
            const cp2x = cp1x;
            const cp2y = points[i].y;
            ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, points[i].x, points[i].y);
        }
        ctx.lineTo(points[points.length - 1].x, padding.top + chartH);
        ctx.lineTo(points[0].x, padding.top + chartH);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // Line stroke
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            const cp1x = (points[i - 1].x + points[i].x) / 2;
            const cp1y = points[i - 1].y;
            const cp2x = cp1x;
            const cp2y = points[i].y;
            ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, points[i].x, points[i].y);
        }
        ctx.strokeStyle = '#6C5CE7';
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // Dots
        points.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
            ctx.fillStyle = '#6C5CE7';
            ctx.fill();
            ctx.beginPath();
            ctx.arc(p.x, p.y, 2, 0, Math.PI * 2);
            ctx.fillStyle = '#FFFFFF';
            ctx.fill();
        });
    }
};
