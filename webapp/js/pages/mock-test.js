/**
 * Mock Test page — full 3-part speaking test simulation.
 */
const MockTestPage = {
    sessionId: null,
    allQuestions: {},
    currentPart: 1,
    currentIndex: 0,
    responses: [],
    state: 'idle',
    showTranscription: true,
    recordingStartTime: null,
    autoAdvanceTimer: null,
    currentAudio: null,

    async render(container) {
        this.currentPart = 1;
        this.currentIndex = 0;
        this.responses = [];
        this.state = 'idle';
        this.showTranscription = true;
        this.recordingStartTime = null;
        this.clearAutoAdvance();

        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Preparing mock test...</span></div>`;

        try {
            const result = await API.post('/api/sessions/start', { type: 'mock', part: 1 });
            this.sessionId = result.session_id;

            const [p1, p2, p3] = await Promise.all([
                API.get('/api/questions?part=1'),
                API.get('/api/questions?part=2'),
                API.get('/api/questions?part=3'),
            ]);

            const shuffle = arr => arr.sort(() => Math.random() - 0.5);
            this.allQuestions = {
                1: shuffle(p1.questions).slice(0, 4),
                2: shuffle(p2.questions).slice(0, 1),
                3: shuffle(p3.questions).slice(0, 4),
            };

            this.renderIntro(container);
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

    renderIntro(container) {
        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Mock Speaking Test</h2>
            </div>

            <div class="card text-center">
                <h3>Full IELTS Speaking Test</h3>
                <p class="text-secondary mt-8">This simulates the real exam with all 3 parts.</p>
                <p class="text-secondary mt-8">
                    Part 1: 4 questions (30s each)<br>
                    Part 2: 1 topic (2 min)<br>
                    Part 3: 4 questions (1 min each)
                </p>
            </div>

            <div class="card mt-12">
                <h3>Transcription Mode</h3>
                <p class="text-secondary text-sm mt-8">Choose whether to see your speech transcribed after each answer.</p>
                <div class="transcription-toggle mt-12">
                    <button class="btn btn-primary" id="mode-with">With Transcription</button>
                    <button class="btn btn-outline mt-8" id="mode-without">Without Transcription</button>
                </div>
            </div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        container.querySelector('#mode-with').addEventListener('click', () => {
            this.showTranscription = true;
            this.renderQuestion(container);
        });
        container.querySelector('#mode-without').addEventListener('click', () => {
            this.showTranscription = false;
            this.renderQuestion(container);
        });
    },

    renderQuestion(container) {
        this.clearAutoAdvance();
        const questions = this.allQuestions[this.currentPart] || [];
        if (this.currentIndex >= questions.length) {
            if (this.currentPart < 3) {
                this.currentPart++;
                this.currentIndex = 0;
                this.renderPartTransition(container);
                return;
            }
            this.showResults(container);
            return;
        }

        const q = questions[this.currentIndex];
        const totalQ = questions.length;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part ${this.currentPart}</h2>
                <button class="finish-test-btn" id="finish-btn">Finish</button>
            </div>

            <div class="question-card">
                <span class="part-badge">Part ${this.currentPart} - Q${this.currentIndex + 1}/${totalQ}</span>
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
            this.clearAutoAdvance();
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        container.querySelector('#finish-btn').addEventListener('click', () => {
            this.clearAutoAdvance();
            if (Recorder.isRecording()) Recorder.stop();
            if (this.responses.length > 0) {
                this.showResults(container);
            } else {
                App.navigate('home');
            }
        });

        this.setupRecordBtn(container);
        this.playQuestion(q.question);
    },

    async playQuestion(text) {
        // Stop any currently playing audio
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }

        try {
            const initData = API.getInitData();
            const resp = await fetch('/api/tts', {
                method: 'POST',
                headers: {
                    'Authorization': `tma ${initData}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text }),
            });

            if (!resp.ok) return;

            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            this.currentAudio = new Audio(url);
            this.currentAudio.play().catch(() => {});
        } catch (err) {
            console.warn('TTS error:', err);
        }
    },

    renderPartTransition(container) {
        this.clearAutoAdvance();
        const partDescriptions = {
            2: 'You will receive a topic card. You have 1 minute to prepare and 2 minutes to speak.',
            3: 'The examiner will ask follow-up questions related to the Part 2 topic.',
        };

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Mock Test</h2>
                <button class="finish-test-btn" id="finish-btn">Finish</button>
            </div>
            <div class="card text-center">
                <h3>Moving to Part ${this.currentPart}</h3>
                <p class="text-secondary mt-8">${partDescriptions[this.currentPart] || ''}</p>
            </div>
            <button class="btn btn-primary mt-16" id="continue-btn">Continue</button>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        container.querySelector('#finish-btn').addEventListener('click', () => {
            if (this.responses.length > 0) {
                this.showResults(container);
            } else {
                App.navigate('home');
            }
        });
        container.querySelector('#continue-btn').addEventListener('click', () => {
            this.renderQuestion(container);
        });
    },

    setupRecordBtn(container) {
        const btn = container.querySelector('#record-btn');
        const timer = container.querySelector('#timer');
        const hint = container.querySelector('#record-hint');

        btn.addEventListener('click', async () => {
            if (this.state === 'recording') {
                const elapsed = (Date.now() - this.recordingStartTime) / 1000;
                if (elapsed < 5) {
                    hint.textContent = `Wait ${Math.ceil(5 - elapsed)}s more...`;
                    return;
                }
                Recorder.stop();
                this.state = 'processing';
                btn.classList.remove('recording');
                btn.classList.add('disabled');
                hint.textContent = 'Processing...';
                return;
            }
            if (this.state === 'processing') return;

            const started = await Recorder.start(
                (s) => {
                    timer.textContent = Recorder.formatTime(s);
                    if (s < 5) {
                        hint.textContent = `Recording... (min ${5 - s}s)`;
                    } else {
                        hint.textContent = 'Tap to stop';
                    }
                },
                (blob) => { this.handleRecording(blob, container); }
            );

            if (started) {
                // Stop TTS if playing
                if (this.currentAudio) {
                    this.currentAudio.pause();
                    this.currentAudio = null;
                }
                this.state = 'recording';
                this.recordingStartTime = Date.now();
                btn.classList.add('recording');
                hint.textContent = 'Recording... (min 5s)';
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

        transcriptionArea.innerHTML = `<div class="loading"><div class="spinner"></div><span>${this.showTranscription ? 'Transcribing...' : 'Saving response...'}</span></div>`;

        try {
            const q = this.allQuestions[this.currentPart][this.currentIndex];
            const extMap = {'audio/webm': '.webm', 'audio/ogg': '.ogg', 'audio/mp4': '.m4a', 'audio/mpeg': '.mp3'};
            const ext = extMap[(Recorder.mimeType || '').split(';')[0]] || '.ogg';
            const formData = new FormData();
            formData.append('audio', blob, `recording${ext}`);
            formData.append('question', q.question);
            formData.append('part', this.currentPart);

            const result = await API.postForm(`/api/sessions/${this.sessionId}/respond`, formData);

            this.responses.push({
                part: this.currentPart,
                question: q.question,
                transcription: result.transcription,
                duration: result.duration,
            });

            if (this.showTranscription) {
                transcriptionArea.innerHTML = `
                    <div class="transcription-card">
                        <h3>Your Response</h3>
                        <p class="text">${result.transcription}</p>
                    </div>
                `;
            } else {
                transcriptionArea.innerHTML = `
                    <div class="card text-center">
                        <p class="text-secondary">Response saved</p>
                    </div>
                `;
            }

            this.showNextWithAutoAdvance(actionArea, container);
            this.state = 'idle';
            btn.classList.remove('disabled');
        } catch (err) {
            transcriptionArea.innerHTML = `
                <div class="card"><p class="text-secondary">Failed: ${err.message}</p></div>
            `;
            this.state = 'idle';
            btn.classList.remove('disabled');
            hint.textContent = 'Tap to try again';
        }
    },

    showNextWithAutoAdvance(actionArea, container) {
        let countdown = 5;

        actionArea.innerHTML = `
            <button class="btn btn-primary mt-12" id="next-btn">Next <span id="countdown-text">(${countdown}s)</span></button>
        `;

        const nextBtn = actionArea.querySelector('#next-btn');
        const countdownText = actionArea.querySelector('#countdown-text');

        const goNext = () => {
            this.clearAutoAdvance();
            this.currentIndex++;
            this.state = 'idle';
            this.renderQuestion(container);
        };

        nextBtn.addEventListener('click', goNext);

        this.autoAdvanceTimer = setInterval(() => {
            countdown--;
            if (countdown <= 0) {
                goNext();
            } else {
                countdownText.textContent = `(${countdown}s)`;
            }
        }, 1000);
    },

    clearAutoAdvance() {
        if (this.autoAdvanceTimer) {
            clearInterval(this.autoAdvanceTimer);
            this.autoAdvanceTimer = null;
        }
    },

    async showResults(container) {
        this.clearAutoAdvance();
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Generating feedback...</span></div>`;

        try {
            const result = await API.post(`/api/sessions/${this.sessionId}/complete`);
            const scores = result.scores || {};

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Mock Test Results</h2>
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
                    <p class="text">${result.feedback || 'No detailed feedback.'}</p>
                </div>

                <button class="btn btn-primary mt-12" id="home-btn">Back to Home</button>
            `;

            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
            container.querySelector('#home-btn').addEventListener('click', () => App.navigate('home'));
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Error</h2>
                </div>
                <div class="card"><p class="text-secondary">${err.message}</p></div>
                <button class="btn btn-primary mt-12" id="home-btn">Home</button>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
            container.querySelector('#home-btn').addEventListener('click', () => App.navigate('home'));
        }
    }
};
