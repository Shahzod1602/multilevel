/**
 * Pronunciation practice page.
 */
const PronunciationPage = {
    render(container) {
        const sounds = [
            { symbol: '/th/', word: 'think', tip: 'Place tongue between teeth, blow air out' },
            { symbol: '/r/', word: 'right', tip: 'Curl tongue back slightly, don\'t touch the roof' },
            { symbol: '/l/', word: 'light', tip: 'Touch tongue tip to ridge behind upper teeth' },
            { symbol: '/v/', word: 'very', tip: 'Upper teeth touch lower lip, voice it' },
            { symbol: '/w/', word: 'water', tip: 'Round lips, then open quickly' },
            { symbol: '/s/ vs /z/', word: 'Sue vs Zoo', tip: '/s/ is voiceless, /z/ is voiced' },
            { symbol: '/ae/', word: 'cat', tip: 'Open mouth wide, tongue low and front' },
            { symbol: '/schwa/', word: 'about', tip: 'The most common English sound — relaxed, neutral' },
        ];

        const stressRules = [
            { rule: 'Two-syllable nouns', example: 'RE-cord, PRE-sent', note: 'Stress usually on first syllable' },
            { rule: 'Two-syllable verbs', example: 're-CORD, pre-SENT', note: 'Stress usually on second syllable' },
            { rule: '-tion/-sion words', example: 'edu-CA-tion', note: 'Stress on syllable before suffix' },
            { rule: 'Compound nouns', example: 'AIR-port', note: 'Stress on first word' },
        ];

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Pronunciation</h2>
            </div>

            <div class="card">
                <h3>Key English Sounds</h3>
                <p class="text-sm text-secondary">Focus on sounds that are difficult for non-native speakers.</p>
            </div>

            ${sounds.map(s => `
                <div class="tip-card">
                    <div class="tip-icon" style="font-weight:700;font-size:14px">${s.symbol}</div>
                    <div>
                        <h3>${s.word}</h3>
                        <p>${s.tip}</p>
                    </div>
                </div>
            `).join('')}

            <h3 class="mt-20 mb-8">Word Stress Rules</h3>

            ${stressRules.map(r => `
                <div class="card">
                    <h3 style="font-size:14px">${r.rule}</h3>
                    <p class="text-sm" style="color:var(--primary);font-weight:600;margin:4px 0">${r.example}</p>
                    <p class="text-xs text-secondary">${r.note}</p>
                </div>
            `).join('')}

            <h3 class="mt-20 mb-8">Intonation Tips</h3>
            <div class="card">
                <p class="text-sm text-secondary">
                    &#8593; <strong>Rising</strong> — Yes/No questions: "Do you like it?"<br><br>
                    &#8595; <strong>Falling</strong> — Statements & Wh-questions: "I went to school." / "Where do you live?"<br><br>
                    &#8593;&#8595; <strong>Rise-Fall</strong> — Lists: "I bought apples, bananas, and oranges."
                </p>
            </div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
    }
};
