/**
 * Scoring Guide page — IELTS band descriptors.
 */
const ScoringPage = {
    render(container) {
        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Scoring Guide</h2>
            </div>

            <div class="card">
                <h3>IELTS Speaking is scored on 4 criteria:</h3>
                <p class="text-secondary mt-8">Each criterion is scored 0-9. The overall band is the average rounded to the nearest 0.5.</p>
            </div>

            <h3 class="mt-16 mb-8">Band Score Descriptors</h3>
            <table class="band-table">
                <thead>
                    <tr><th>Band</th><th>Level</th><th>Description</th></tr>
                </thead>
                <tbody>
                    <tr><td>9</td><td>Expert</td><td>Full command of the language</td></tr>
                    <tr><td>8</td><td>Very Good</td><td>Fully operational command, occasional inaccuracies</td></tr>
                    <tr><td>7</td><td>Good</td><td>Operational command with occasional errors</td></tr>
                    <tr><td>6</td><td>Competent</td><td>Effective command despite inaccuracies</td></tr>
                    <tr><td>5</td><td>Modest</td><td>Partial command, likely to make errors</td></tr>
                    <tr><td>4</td><td>Limited</td><td>Basic competence in familiar situations</td></tr>
                    <tr><td>3</td><td>Extremely Limited</td><td>Only general meaning conveyed</td></tr>
                </tbody>
            </table>

            <h3 class="mt-16 mb-8">Criteria Breakdown</h3>

            <div class="card">
                <h3 style="color:var(--primary)">Fluency & Coherence</h3>
                <p class="text-sm text-secondary mt-8">How smoothly and logically you speak. Avoid long pauses, self-correction, and repetition. Use linking words naturally.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-green)">Lexical Resource</h3>
                <p class="text-sm text-secondary mt-8">Range and accuracy of vocabulary. Use topic-specific words, collocations, and paraphrasing. Avoid repetition of the same words.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-orange)">Grammatical Range & Accuracy</h3>
                <p class="text-sm text-secondary mt-8">Variety of sentence structures and grammatical accuracy. Use complex sentences, conditionals, passive voice, and relative clauses.</p>
            </div>

            <div class="card">
                <h3 style="color:var(--accent-blue)">Pronunciation</h3>
                <p class="text-sm text-secondary mt-8">Clarity, intonation, word stress, and connected speech. You don't need a native accent — clear and natural pronunciation is key.</p>
            </div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
    }
};
