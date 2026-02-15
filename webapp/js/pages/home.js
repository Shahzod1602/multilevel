/**
 * Home page — greeting, practice cards, prepare & learn grid.
 */
const HomePage = {
    render(container) {
        const user = App.userData;
        const firstName = user?.user?.first_name || 'Student';

        container.innerHTML = `
            <div class="greeting">
                <h1>Hi, ${this.escapeHtml(firstName)}</h1>
                <p>Ready to practice your speaking?</p>
            </div>

            <div class="section-title">Practice Speaking</div>
            <div class="practice-cards">
                <div class="practice-card" data-action="practice" data-part="1">
                    <div class="icon purple">1</div>
                    <h3>Part 1</h3>
                    <span class="text-xs text-secondary">Introduction</span>
                </div>
                <div class="practice-card" data-action="practice" data-part="2">
                    <div class="icon green">2</div>
                    <h3>Part 2</h3>
                    <span class="text-xs text-secondary">Long Turn</span>
                </div>
                <div class="practice-card" data-action="practice" data-part="3">
                    <div class="icon orange">3</div>
                    <h3>Part 3</h3>
                    <span class="text-xs text-secondary">Discussion</span>
                </div>
            </div>

            <div class="section-title">Prepare & Learn</div>
            <div class="feature-grid">
                <div class="feature-card" data-action="mock-test">
                    <div class="icon" style="background:#EDE9FE;font-size:20px">&#128221;</div>
                    <h3>Mock Test</h3>
                    <p>Full speaking test</p>
                </div>
                <div class="feature-card" data-action="tips">
                    <div class="icon" style="background:#D5F5E3;font-size:20px">&#128161;</div>
                    <h3>Tips & Strategy</h3>
                    <p>Expert advice</p>
                </div>
                <div class="feature-card" data-action="pronunciation">
                    <div class="icon" style="background:#FEF3C7;font-size:20px">&#127908;</div>
                    <h3>Pronunciation</h3>
                    <p>Sound practice</p>
                </div>
                <div class="feature-card" data-action="scoring">
                    <div class="icon" style="background:#DBEAFE;font-size:20px">&#127942;</div>
                    <h3>Scoring Guide</h3>
                    <p>Band descriptors</p>
                </div>
            </div>
        `;

        // Practice card clicks
        container.querySelectorAll('.practice-card').forEach(card => {
            card.addEventListener('click', () => {
                const part = parseInt(card.dataset.part);
                App.navigate('practice', { part });
            });
        });

        // Feature card clicks
        container.querySelectorAll('.feature-card').forEach(card => {
            card.addEventListener('click', () => {
                App.navigate(card.dataset.action);
            });
        });
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};
