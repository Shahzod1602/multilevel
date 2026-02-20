/**
 * Scoring Guide page — CEFR level descriptors.
 */
const ScoringPage = {
    render(container) {
        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Scoring Guide</h2>
            </div>

            <div class="card">
                <h3>Multilevel Speaking is scored on 4 criteria:</h3>
                <p class="text-secondary mt-8">Each criterion is scored 0-75. The overall score is the average, mapped to a CEFR level.</p>
            </div>

            <h3 class="mt-16 mb-8">CEFR Level Descriptors</h3>
            <table class="band-table">
                <thead>
                    <tr><th>Score</th><th>Level</th><th>Description</th></tr>
                </thead>
                <tbody>
                    <tr><td>65-75</td><td><span class="cefr-badge c1">C1</span></td><td>Advanced — can express ideas fluently and spontaneously</td></tr>
                    <tr><td>51-64</td><td><span class="cefr-badge b2">B2</span></td><td>Upper-Intermediate — can interact with fluency and spontaneity</td></tr>
                    <tr><td>38-50</td><td><span class="cefr-badge b1">B1</span></td><td>Intermediate — can deal with most everyday situations</td></tr>
                    <tr><td>0-37</td><td><span class="cefr-badge below-b1">Below B1</span></td><td>Basic — limited command in familiar situations</td></tr>
                </tbody>
            </table>

            <h3 class="mt-16 mb-8">Test Structure</h3>

            <div class="card">
                <h3 style="color:var(--primary)">Part 1.1 — Interview</h3>
                <p class="text-sm text-secondary mt-8">3 questions, 30 seconds each. General questions about yourself, your life, and interests.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-green)">Part 1.2 — Picture Description</h3>
                <p class="text-sm text-secondary mt-8">2 pictures with 3 questions, 30 seconds each. Describe what you see and answer related questions.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-orange)">Part 2 — Discussion</h3>
                <p class="text-sm text-secondary mt-8">3 questions, 60 seconds each. Discuss topics in more depth with extended responses.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-blue)">Part 3 — Debate</h3>
                <p class="text-sm text-secondary mt-8">1 topic with For/Against points. Choose a side and argue for 120 seconds.</p>
            </div>

            <h3 class="mt-16 mb-8">Criteria Breakdown</h3>

            <div class="card">
                <h3 style="color:var(--primary)">Fluency & Coherence</h3>
                <p class="text-sm text-secondary mt-8">How smoothly and logically you speak. Avoid long pauses, self-correction, and repetition. Use linking words naturally.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-green)">Lexical Resource</h3>
                <p class="text-sm text-secondary mt-8">Range and accuracy of vocabulary. Use topic-specific words, collocations, and paraphrasing.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-orange)">Grammatical Range & Accuracy</h3>
                <p class="text-sm text-secondary mt-8">Variety of sentence structures and grammatical accuracy. Use complex sentences, conditionals, passive voice.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-blue)">Pronunciation</h3>
                <p class="text-sm text-secondary mt-8">Clarity, intonation, word stress, and connected speech. Clear and natural pronunciation is key.</p>
            </div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
    }
};
