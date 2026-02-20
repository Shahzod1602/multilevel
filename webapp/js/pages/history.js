/**
 * History page — past sessions list and detail view.
 */
const HistoryPage = {
    async render(container, params = {}) {
        if (params.sessionId) {
            await this.renderDetail(container, params.sessionId);
            return;
        }
        await this.renderList(container);
    },

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

    async renderList(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading history...</span></div>`;

        try {
            const result = await API.get('/api/history');
            const sessions = result.sessions || [];

            if (!sessions.length) {
                container.innerHTML = `
                    <div class="page-header">
                        <button class="back-btn" id="back-btn">&#8592;</button>
                        <h2>History</h2>
                    </div>
                    <div class="card text-center">
                        <p class="text-secondary">No completed sessions yet.</p>
                        <p class="text-xs text-secondary mt-8">Start practicing to see your history here!</p>
                    </div>
                `;
                container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
                return;
            }

            const rows = sessions.map(s => {
                const date = s.completed_at ? new Date(s.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '-';
                const score = s.score_overall != null ? Math.round(s.score_overall) : '-';
                const typeLabel = s.type === 'mock' ? 'Mock Test' : `Part ${s.part}`;
                return `
                    <div class="history-item" data-session-id="${s.id}">
                        <div class="history-left">
                            <div class="history-icon ${s.type === 'mock' ? 'mock' : 'practice'}">${s.type === 'mock' ? 'M' : s.part}</div>
                            <div>
                                <div class="history-title">${typeLabel}</div>
                                <div class="text-xs text-secondary">${date}</div>
                            </div>
                        </div>
                        <div style="display:flex;align-items:center;gap:8px">
                            <div class="history-score">${score}</div>
                            ${this.cefrBadge(s.score_overall)}
                        </div>
                    </div>
                `;
            }).join('');

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>History</h2>
                </div>
                <div class="history-list">${rows}</div>
            `;

            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));

            container.querySelectorAll('.history-item').forEach(item => {
                item.addEventListener('click', () => {
                    const id = item.dataset.sessionId;
                    App.navigate('history', { sessionId: parseInt(id) });
                });
            });
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>History</h2>
                </div>
                <div class="card"><p class="text-secondary">${err.message}</p></div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        }
    },

    async renderDetail(container, sessionId) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading session...</span></div>`;

        try {
            const s = await API.get(`/api/history/${sessionId}`);
            const date = s.completed_at ? new Date(s.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';
            const typeLabel = s.type === 'mock' ? 'Mock Test' : `Part ${s.part} Practice`;
            const overall = Math.round(s.score_overall || 0);

            const responsesHtml = (s.responses || []).map((r, i) => `
                <div class="history-response">
                    <div class="history-q">Q${i + 1}: ${r.question_text}</div>
                    <div class="history-a">${r.transcription || 'No transcription'}</div>
                    <div class="text-xs text-secondary">${r.duration}s</div>
                </div>
            `).join('');

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>${typeLabel}</h2>
                </div>

                <p class="text-sm text-secondary mb-12">${date}</p>

                <div class="results-card">
                    <div class="score-main">
                        <div class="score">${overall}</div>
                        <div class="label">Overall Score ${this.cefrBadge(s.score_overall)}</div>
                    </div>
                    <div class="score-breakdown">
                        <div class="score-item">
                            <div class="value">${Math.round(s.score_fluency || 0)}</div>
                            <div class="name">Fluency</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${Math.round(s.score_lexical || 0)}</div>
                            <div class="name">Lexical</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${Math.round(s.score_grammar || 0)}</div>
                            <div class="name">Grammar</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${Math.round(s.score_pronunciation || 0)}</div>
                            <div class="name">Pronunciation</div>
                        </div>
                    </div>
                </div>

                ${s.feedback ? `
                <div class="feedback-card">
                    <h3>Examiner Feedback</h3>
                    <p class="text">${s.feedback}</p>
                </div>
                ` : ''}

                <h3 class="mt-16 mb-8">Questions & Answers</h3>
                <div class="history-responses">${responsesHtml}</div>
            `;

            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('history'));
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Session Detail</h2>
                </div>
                <div class="card"><p class="text-secondary">${err.message}</p></div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('history'));
        }
    }
};
