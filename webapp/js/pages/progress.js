/**
 * Progress page — weekly calendar, streak, chart, stats.
 */
const ProgressPage = {
    cefrBadge(score) {
        if (score == null) return '';
        score = Math.round(score);
        let level, cls;
        if (score >= 65) { level = 'C1'; cls = 'c1'; }
        else if (score >= 51) { level = 'B2'; cls = 'b2'; }
        else if (score >= 38) { level = 'B1'; cls = 'b1'; }
        else { level = 'Below B1'; cls = 'below-b1'; }
        return `<span class="cefr-badge ${cls}">${level}</span>`;
    },

    async render(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading progress...</span></div>`;

        try {
            const [weekly, streak] = await Promise.all([
                API.get('/api/progress/weekly'),
                API.get('/api/progress/streak'),
            ]);

            const days = weekly.days || [];
            const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

            const today = new Date();
            const todayStr = today.toISOString().split('T')[0];

            const calendarHtml = days.map(d => {
                const date = new Date(d.date + 'T00:00:00');
                const dayName = dayNames[date.getDay()];
                const dayNum = date.getDate();
                const isToday = d.date === todayStr;
                const isActive = d.minutes > 0;
                return `
                    <div class="day-item ${isToday ? 'today' : ''} ${isActive ? 'active' : ''}">
                        <div class="day-name">${dayName}</div>
                        <div class="day-num">${dayNum}</div>
                    </div>
                `;
            }).join('');

            // Chart data
            const chartData = days.map(d => {
                const date = new Date(d.date + 'T00:00:00');
                return {
                    label: dayNames[date.getDay()],
                    value: d.minutes,
                };
            });

            // Target level mapping
            const targetLevel = streak.target_level || 'B2';
            const targetScoreMap = { 'C1': 65, 'B2': 51, 'B1': 38, 'Below B1': 0 };
            const targetScore = targetScoreMap[targetLevel] || 51;

            container.innerHTML = `
                <h2>Your Progress</h2>

                <div class="week-calendar">${calendarHtml}</div>

                <div class="streak-card">
                    <div class="text-sm" style="opacity:0.9">Study Streak</div>
                    <div class="streak-number">${streak.streak}</div>
                    <div class="text-sm" style="opacity:0.8">${streak.streak === 1 ? 'day' : 'days'} in a row</div>
                </div>

                <div class="stats-row">
                    <div class="stat-card">
                        <div class="stat-value">${streak.total_sessions}</div>
                        <div class="stat-label">Sessions</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${streak.total_hours}h</div>
                        <div class="stat-label">Practice</div>
                    </div>
                </div>

                ${streak.average_score != null ? `
                <div class="target-card">
                    <div class="target-header">
                        <span>Score Progress</span>
                    </div>
                    <div class="target-scores">
                        <div class="target-actual">
                            <div class="target-score-value">${Math.round(streak.average_score)}</div>
                            <div class="target-score-label">Current Avg ${this.cefrBadge(streak.average_score)}</div>
                        </div>
                        <div class="target-arrow">${streak.average_score >= targetScore ? '&#10003;' : '&#8594;'}</div>
                        <div class="target-goal">
                            <div class="target-score-value">${targetScore}</div>
                            <div class="target-score-label">Target ${this.cefrBadge(targetScore)}</div>
                        </div>
                    </div>
                    <div class="target-progress-bar">
                        <div class="target-progress-fill" style="width: ${Math.min(100, Math.round((streak.average_score / 75) * 100))}%"></div>
                    </div>
                </div>
                ` : ''}

                <div class="chart-container">
                    <h3>Weekly Study (minutes)</h3>
                    <canvas id="progress-chart" style="width:100%;height:200px"></canvas>
                </div>

                ${this.renderRecentSessions(weekly.recent_sessions || [])}
            `;

            // Draw chart after DOM is ready
            requestAnimationFrame(() => {
                Chart.draw('progress-chart', chartData);
            });

        } catch (err) {
            container.innerHTML = `
                <h2>Your Progress</h2>
                <div class="card text-center">
                    <p class="text-secondary">Could not load progress data.</p>
                    <p class="text-xs text-secondary mt-8">${err.message}</p>
                </div>
            `;
        }
    },

    renderRecentSessions(sessions) {
        if (!sessions.length) return '';

        const rows = sessions.map(s => {
            const date = s.completed_at ? new Date(s.completed_at).toLocaleDateString() : '-';
            const score = s.score_overall != null ? Math.round(s.score_overall) : '-';
            return `
                <div class="settings-item">
                    <div class="left">
                        <div class="icon-circle" style="background:var(--primary-bg);color:var(--primary)">
                            ${s.part || '?'}
                        </div>
                        <div>
                            <div class="label">Part ${s.part || '?'} ${s.type === 'mock' ? '(Mock)' : ''}</div>
                            <div class="text-xs text-secondary">${date}</div>
                        </div>
                    </div>
                    <div style="font-weight:700;color:var(--primary)">${score}</div>
                </div>
            `;
        }).join('');

        return `
            <h3 class="mt-16 mb-8">Recent Sessions</h3>
            <div class="settings-list">${rows}</div>
        `;
    }
};
