/**
 * Leaderboard page — top users by average score.
 */
const LeaderboardPage = {
    async render(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading leaderboard...</span></div>`;

        try {
            const data = await API.get('/api/leaderboard');
            const list = data.leaderboard || [];
            const myRank = data.my_rank;
            const myAvg = data.my_avg_score;

            const myRankHtml = myRank ? `
                <div class="lb-my-rank card">
                    <div class="lb-rank">#${myRank}</div>
                    <div class="lb-info">
                        <div class="lb-name">You</div>
                        <div class="lb-sessions text-xs text-secondary">${data.my_sessions || 0} sessions</div>
                    </div>
                    <div class="lb-score">${myAvg ? Math.round(myAvg) : '-'}</div>
                </div>
            ` : `
                <div class="card text-center">
                    <p class="text-secondary text-sm">Complete at least 3 sessions to appear on the leaderboard.</p>
                </div>
            `;

            const listHtml = list.length ? list.map((u, i) => {
                const rank = i + 1;
                const medal = rank === 1 ? '&#129351;' : rank === 2 ? '&#129352;' : rank === 3 ? '&#129353;' : `#${rank}`;
                return `
                    <div class="leaderboard-row ${u.is_me ? 'is-me' : ''}">
                        <div class="lb-rank">${medal}</div>
                        <div class="lb-info">
                            <div class="lb-name">${this.escapeHtml(u.first_name || 'User')}</div>
                            <div class="lb-sessions text-xs text-secondary">${u.sessions} sessions</div>
                        </div>
                        <div class="lb-score">${Math.round(u.avg_score)}</div>
                    </div>
                `;
            }).join('') : '<div class="card text-center"><p class="text-secondary">No data yet.</p></div>';

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Leaderboard</h2>
                </div>

                ${myRankHtml}

                <div class="section-title mt-16">Top Speakers</div>
                <div class="lb-list">
                    ${listHtml}
                </div>
            `;

            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Leaderboard</h2>
                </div>
                <div class="card text-center"><p class="text-secondary">Failed to load: ${err.message}</p></div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        }
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};
