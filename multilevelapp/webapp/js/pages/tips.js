/**
 * Tips & Strategies page.
 */
const TipsPage = {
    async render(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading tips...</span></div>`;

        const iconMap = {
            chat: '&#128172;',
            edit: '&#9998;',
            lightbulb: '&#128161;',
            book: '&#128214;',
            mic: '&#127908;',
            check: '&#9989;',
        };

        try {
            const result = await API.get('/api/content/tips');
            const tips = result.tips || [];

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Tips & Strategies</h2>
                </div>

                ${tips.map(tip => `
                    <div class="tip-card">
                        <div class="tip-icon">${iconMap[tip.icon] || '&#128161;'}</div>
                        <div>
                            <h3>${tip.title}</h3>
                            <p>${tip.content}</p>
                        </div>
                    </div>
                `).join('')}
            `;

            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Tips & Strategies</h2>
                </div>
                <div class="card"><p class="text-secondary">${err.message}</p></div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        }
    }
};
