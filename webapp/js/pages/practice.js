/**
 * Practice page — question display, audio recording, transcription, results.
 */
const PracticePage = {
    sessionId: null,
    questions: [],
    currentIndex: 0,
    part: 1,
    responses: [],
    state: 'idle', // idle, recording, processing, results

    async render(container, params = {}) {
        this.part = params.part || 1;
        this.currentIndex = 0;
        this.responses = [];
        this.state = 'idle';

        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Preparing questions...</span></div>`;

        try {
            const result = await API.post('/api/sessions/start', {
                type: 'practice',
                part: this.part,
            });

            this.sessionId = result.session_id;
            this.questions = result.questions || [];

            if (!this.questions.length) {
                container.innerHTML = `
                    <div class="page-header">
                        <button class="back-btn" id="back-btn">&#8592;</button>
                        <h2>Part ${this.part}</h2>
                    </div>
                    <div class="card text-center">
                        <p class="text-secondary">No questions available for Part ${this.part}.</p>
                    </div>
                `;
                container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
                return;
            }

            this.renderQuestion(container);
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Error</h2>
                </div>
                <div class="card text-center">
                    <p class="text-secondary">${err.message}</p>
                </div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        }
    },

    renderQuestion(container) {
        const q = this.questions[this.currentIndex];
        const progress = `${this.currentIndex + 1} / ${this.questions.length}`;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part ${this.part} Practice</h2>
            </div>

            <div class="question-card">
                <span class="part-badge">Question ${progress}</span>
                <p class="question-text mt-12">${q.question}</p>
            </div>

            <div class="recorder-area">
                <button class="record-btn" id="record-btn">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                    </svg>
                </button>
                <div class="timer" id="timer">0:00</div>
                <p class="text-sm text-secondary mt-8" id="record-hint">Tap to start recording</p>
            </div>

            <div id="transcription-area"></div>
            <div id="action-area"></div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => {
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        this.setupRecordButton(container);
    },

    setupRecordButton(container) {
        const btn = container.querySelector('#record-btn');
        const timer = container.querySelector('#timer');
        const hint = container.querySelector('#record-hint');

        btn.addEventListener('click', async () => {
            if (this.state === 'recording') {
                // Stop recording
                Recorder.stop();
                this.state = 'processing';
                btn.classList.remove('recording');
                btn.classList.add('disabled');
                hint.textContent = 'Processing...';
                return;
            }

            if (this.state === 'processing') return;

            // Start recording
            const started = await Recorder.start(
                (seconds) => {
                    timer.textContent = Recorder.formatTime(seconds);
                },
                (blob) => {
                    this.handleRecording(blob, container);
                }
            );

            if (started) {
                this.state = 'recording';
                btn.classList.add('recording');
                hint.textContent = 'Tap to stop recording';
            } else {
                hint.textContent = 'Microphone access denied';
            }
        });
    },

    async handleRecording(blob, container) {
        const transcriptionArea = container.querySelector('#transcription-area');
        const actionArea = container.querySelector('#action-area');
        const hint = container.querySelector('#record-hint');
        const btn = container.querySelector('#record-btn');

        transcriptionArea.innerHTML = `<div class="loading"><div class="spinner"></div><span>Transcribing...</span></div>`;

        try {
            const q = this.questions[this.currentIndex];
            const extMap = {'audio/webm': '.webm', 'audio/ogg': '.ogg', 'audio/mp4': '.m4a', 'audio/mpeg': '.mp3'};
            const ext = extMap[(Recorder.mimeType || '').split(';')[0]] || '.ogg';
            const formData = new FormData();
            formData.append('audio', blob, `recording${ext}`);
            formData.append('question', q.question);
            formData.append('part', this.part);

            const result = await API.postForm(`/api/sessions/${this.sessionId}/respond`, formData);

            this.responses.push({
                question: q.question,
                transcription: result.transcription,
                duration: result.duration,
            });

            transcriptionArea.innerHTML = `
                <div class="transcription-card">
                    <h3>Your Response</h3>
                    <p class="text">${result.transcription}</p>
                    <p class="text-xs text-secondary mt-8">Duration: ${result.duration}s</p>
                </div>
            `;

            const isLast = this.currentIndex >= this.questions.length - 1;
            actionArea.innerHTML = `
                <button class="btn btn-primary mt-12" id="next-btn">
                    ${isLast ? 'Get Feedback' : 'Next Question'}
                </button>
            `;

            actionArea.querySelector('#next-btn').addEventListener('click', () => {
                if (isLast) {
                    this.showResults(container);
                } else {
                    this.currentIndex++;
                    this.state = 'idle';
                    this.renderQuestion(container);
                }
            });

            this.state = 'idle';
            btn.classList.remove('disabled');
            hint.textContent = 'Record again or continue';

        } catch (err) {
            transcriptionArea.innerHTML = `
                <div class="card text-center">
                    <p class="text-secondary">Failed: ${err.message}</p>
                </div>
            `;
            this.state = 'idle';
            btn.classList.remove('disabled');
            hint.textContent = 'Tap to try again';
        }
    },

    async showResults(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Generating feedback...</span></div>`;

        try {
            const result = await API.post(`/api/sessions/${this.sessionId}/complete`);
            const scores = result.scores || {};

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Results</h2>
                </div>

                <div class="results-card">
                    <div class="score-main">
                        <div class="score">${(scores.overall || 0).toFixed(1)}</div>
                        <div class="label">Overall Band Score</div>
                    </div>
                    <div class="score-breakdown">
                        <div class="score-item">
                            <div class="value">${(scores.fluency || 0).toFixed(1)}</div>
                            <div class="name">Fluency</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${(scores.lexical || 0).toFixed(1)}</div>
                            <div class="name">Lexical</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${(scores.grammar || 0).toFixed(1)}</div>
                            <div class="name">Grammar</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${(scores.pronunciation || 0).toFixed(1)}</div>
                            <div class="name">Pronunciation</div>
                        </div>
                    </div>
                </div>

                <div class="feedback-card">
                    <h3>Examiner Feedback</h3>
                    <p class="text">${result.feedback || 'No detailed feedback available.'}</p>
                </div>

                <button class="btn btn-primary mt-12" id="home-btn">Back to Home</button>
                <button class="btn btn-outline mt-8" id="retry-btn">Practice Again</button>
            `;

            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
            container.querySelector('#home-btn').addEventListener('click', () => App.navigate('home'));
            container.querySelector('#retry-btn').addEventListener('click', () => {
                App.navigate('practice', { part: this.part });
            });

        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Error</h2>
                </div>
                <div class="card text-center">
                    <p class="text-secondary">${err.message}</p>
                </div>
                <button class="btn btn-primary mt-12" id="home-btn">Back to Home</button>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
            container.querySelector('#home-btn').addEventListener('click', () => App.navigate('home'));
        }
    }
};
