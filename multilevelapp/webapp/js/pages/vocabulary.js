/**
 * Vocabulary Bank page — useful phrases for each speaking part.
 */
const VocabularyPage = {
    async render(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading vocabulary...</span></div>`;

        try {
            const data = await API.get('/api/content/vocabulary');
            const categories = data.categories || [];

            const categoriesHtml = categories.map(cat => `
                <div class="vocab-category">
                    <h3>${cat.title}</h3>
                    <p class="text-xs text-secondary mb-8">${cat.description}</p>
                    ${cat.items.map(item => `
                        <div class="vocab-item">
                            <div class="vocab-phrase">${item.phrase}</div>
                            <div class="vocab-example">${item.example}</div>
                        </div>
                    `).join('')}
                </div>
            `).join('');

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Vocabulary Bank</h2>
                </div>

                <div class="card text-center mb-12">
                    <p class="text-sm text-secondary">Useful phrases and expressions for each part of the speaking test.</p>
                </div>

                ${categoriesHtml}
            `;

            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Vocabulary Bank</h2>
                </div>
                <div class="card text-center"><p class="text-secondary">Failed to load: ${err.message}</p></div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        }
    }
};
