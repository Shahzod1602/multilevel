/**
 * Pronunciation Drill page — listen, record, check score.
 */
const PronunciationPage = {
    drills: null,
    currentDrill: null,
    currentItemIndex: 0,
    lastBlobUrl: null,

    async render(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading drills...</span></div>`;

        try {
            const data = await API.get('/api/content/pronunciation-drills');
            this.drills = data.drills || [];
            this.renderDrillList(container);
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Pronunciation</h2>
                </div>
                <div class="card text-center"><p class="text-secondary">Failed to load: ${err.message}</p></div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        }
    },

    renderDrillList(container) {
        const icons = ['&#128264;', '&#128172;', '&#128260;'];
        const colors = ['#EDE9FE', '#D5F5E3', '#FEF3C7'];

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Pronunciation Drills</h2>
            </div>

            <div class="card text-center mb-12">
                <p class="text-sm text-secondary">Practice difficult sounds, common phrases, and minimal pairs.</p>
            </div>

            <div class="drill-grid">
                ${this.drills.map((d, i) => `
                    <div class="drill-item" data-index="${i}">
                        <div class="drill-icon" style="background:${colors[i % 3]}">${icons[i % 3]}</div>
                        <div class="drill-info">
                            <h3>${d.title}</h3>
                            <p class="text-xs text-secondary">${d.items.length} items</p>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));

        container.querySelectorAll('.drill-item').forEach(item => {
            item.addEventListener('click', () => {
                const idx = parseInt(item.dataset.index);
                this.currentDrill = this.drills[idx];
                this.currentItemIndex = 0;
                this.renderDrillPractice(container);
            });
        });
    },

    renderDrillPractice(container) {
        this.cleanupAudio();
        const drill = this.currentDrill;
        const item = drill.items[this.currentItemIndex];
        const progress = `${this.currentItemIndex + 1} / ${drill.items.length}`;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>${drill.title}</h2>
            </div>

            <div class="drill-target-card">
                <span class="part-badge">${progress}</span>
                <div class="drill-word mt-12">${item.word}</div>
                ${item.phonetic ? `<div class="drill-phonetic">${item.phonetic}</div>` : ''}
                ${item.tip ? `<div class="drill-tip text-sm text-secondary mt-8">${item.tip}</div>` : ''}
                <button class="btn btn-outline mt-12" id="listen-btn">Listen</button>
            </div>

            <div class="recorder-area" id="recorder-area">
                <button class="record-btn" id="record-btn">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                    </svg>
                </button>
                <div class="timer" id="timer">0:00</div>
                <p class="text-sm text-secondary mt-8" id="record-hint">Listen first, then record yourself</p>
            </div>

            <div id="result-area"></div>
            <div id="action-area"></div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => {
            if (Recorder.isRecording()) Recorder.stop();
            this.renderDrillList(container);
        });

        // Listen button — TTS
        container.querySelector('#listen-btn').addEventListener('click', async () => {
            const btn = container.querySelector('#listen-btn');
            btn.textContent = 'Playing...';
            btn.disabled = true;
            try {
                const initData = API.getInitData();
                const resp = await fetch('/api/tts', {
                    method: 'POST',
                    headers: {
                        'Authorization': `tma ${initData}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ text: item.word, voice: 'sarah' }),
                });
                if (resp.ok) {
                    const blob = await resp.blob();
                    const url = URL.createObjectURL(blob);
                    const audio = new Audio(url);
                    audio.play().catch(() => {});
                    audio.addEventListener('ended', () => URL.revokeObjectURL(url));
                }
            } catch (e) {
                console.warn('TTS error:', e);
            }
            btn.textContent = 'Listen';
            btn.disabled = false;
        });

        // Record button
        this.setupDrillRecord(container, item);
    },

    setupDrillRecord(container, item) {
        const btn = container.querySelector('#record-btn');
        const timer = container.querySelector('#timer');
        const hint = container.querySelector('#record-hint');
        let state = 'idle';

        btn.addEventListener('click', async () => {
            if (state === 'recording') {
                Recorder.stop();
                state = 'processing';
                btn.classList.remove('recording');
                btn.classList.add('disabled');
                hint.textContent = 'Checking...';
                return;
            }
            if (state === 'processing') return;

            const started = await Recorder.start(
                (s) => { timer.textContent = Recorder.formatTime(s); },
                (blob) => { this.handleDrillRecording(blob, item, container); },
                10 // max 10s for pronunciation drill
            );

            if (started) {
                state = 'recording';
                btn.classList.add('recording');
                hint.textContent = 'Say the word/phrase, then tap to stop';
            } else {
                hint.textContent = 'Microphone access denied';
            }
        });
    },

    async handleDrillRecording(blob, item, container) {
        const resultArea = container.querySelector('#result-area');
        const actionArea = container.querySelector('#action-area');
        const hint = container.querySelector('#record-hint');
        const btn = container.querySelector('#record-btn');

        this.cleanupAudio();
        this.lastBlobUrl = URL.createObjectURL(blob);

        resultArea.innerHTML = `<div class="loading"><div class="spinner"></div><span>Analyzing...</span></div>`;

        try {
            const extMap = {'audio/webm': '.webm', 'audio/ogg': '.ogg', 'audio/mp4': '.m4a', 'audio/mpeg': '.mp3'};
            const ext = extMap[(Recorder.mimeType || '').split(';')[0]] || '.ogg';
            const formData = new FormData();
            formData.append('audio', blob, `pron${ext}`);
            formData.append('target', item.word);

            const result = await API.postForm('/api/pronunciation/check', formData);

            const score = result.score || 0;
            const scoreClass = score >= 80 ? 'score-great' : score >= 50 ? 'score-ok' : 'score-low';

            resultArea.innerHTML = `
                <div class="pron-result-card ${scoreClass}">
                    <div class="pron-score">${score}%</div>
                    <div class="pron-target">Target: ${item.word}</div>
                    <div class="pron-heard">You said: ${result.transcription || '...'}</div>
                    ${result.feedback ? `<div class="pron-feedback text-sm mt-8">${result.feedback}</div>` : ''}
                    ${this.lastBlobUrl ? `
                    <div class="playback-row mt-8">
                        <button class="play-btn" id="play-btn">&#9654;</button>
                        <div class="playback-bar"><div class="playback-progress" id="playback-progress"></div></div>
                    </div>` : ''}
                </div>
            `;

            if (this.lastBlobUrl) this.setupPlayback(container);

            const isLast = this.currentItemIndex >= this.currentDrill.items.length - 1;
            actionArea.innerHTML = `
                <button class="btn btn-outline mt-12" id="retry-btn">Try Again</button>
                <button class="btn btn-primary mt-8" id="next-btn">${isLast ? 'Back to Drills' : 'Next'}</button>
            `;

            actionArea.querySelector('#retry-btn').addEventListener('click', () => {
                this.renderDrillPractice(container);
            });

            actionArea.querySelector('#next-btn').addEventListener('click', () => {
                if (isLast) {
                    this.renderDrillList(container);
                } else {
                    this.currentItemIndex++;
                    this.renderDrillPractice(container);
                }
            });

            btn.classList.remove('disabled');
            hint.textContent = 'Try again or continue';
        } catch (err) {
            resultArea.innerHTML = `<div class="card text-center"><p class="text-secondary">Failed: ${err.message}</p></div>`;
            btn.classList.remove('disabled');
            hint.textContent = 'Tap to try again';
        }
    },

    setupPlayback(container) {
        const playBtn = container.querySelector('#play-btn');
        const progressBar = container.querySelector('#playback-progress');
        if (!playBtn || !this.lastBlobUrl) return;

        const audio = new Audio(this.lastBlobUrl);
        let isPlaying = false;

        audio.addEventListener('timeupdate', () => {
            if (audio.duration) {
                progressBar.style.width = (audio.currentTime / audio.duration) * 100 + '%';
            }
        });

        audio.addEventListener('ended', () => {
            isPlaying = false;
            playBtn.innerHTML = '&#9654;';
            progressBar.style.width = '0%';
        });

        playBtn.addEventListener('click', () => {
            if (isPlaying) {
                audio.pause();
                isPlaying = false;
                playBtn.innerHTML = '&#9654;';
            } else {
                audio.play().catch(() => {});
                isPlaying = true;
                playBtn.innerHTML = '&#9646;&#9646;';
            }
        });
    },

    cleanupAudio() {
        if (this.lastBlobUrl) {
            URL.revokeObjectURL(this.lastBlobUrl);
            this.lastBlobUrl = null;
        }
    }
};
