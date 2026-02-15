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

    selectedTopic: null,

    async render(container, params = {}) {
        this.part = params.part || 1;
        this.currentIndex = 0;
        this.responses = [];
        this.state = 'idle';
        this.selectedTopic = null;

        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading topics...</span></div>`;

        try {
            const topicResult = await API.get(`/api/topics?part=${this.part}`);
            const topics = topicResult.topics || [];

            if (topics.length > 1) {
                this.renderTopicSelector(container, topics);
            } else {
                await this.startSession(container);
            }
        } catch (err) {
            // Fallback: start without topic filter
            await this.startSession(container);
        }
    },

    renderTopicSelector(container, topics) {
        const topicCards = topics.map(t => `
            <div class="topic-chip" data-topic="${t}">${t}</div>
        `).join('');

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part ${this.part} Practice</h2>
            </div>
            <div class="card">
                <h3>Choose a Topic</h3>
                <p class="text-secondary text-sm">Select a topic or start with random questions</p>
                <div class="topic-grid mt-12">${topicCards}</div>
            </div>
            <button class="btn btn-primary mt-12" id="random-btn">Random Questions</button>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));

        container.querySelectorAll('.topic-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                container.querySelectorAll('.topic-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                this.selectedTopic = chip.dataset.topic;
            });
        });

        container.querySelector('#random-btn').addEventListener('click', async () => {
            await this.startSession(container);
        });

        // Double-click or tap on selected topic starts session
        container.querySelectorAll('.topic-chip').forEach(chip => {
            chip.addEventListener('click', async () => {
                if (this.selectedTopic === chip.dataset.topic) {
                    await this.startSession(container);
                }
                this.selectedTopic = chip.dataset.topic;
                container.querySelectorAll('.topic-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
            });
        });
    },

    async startSession(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Preparing questions...</span></div>`;

        try {
            const payload = { type: 'practice', part: this.part };
            if (this.selectedTopic) payload.topic = this.selectedTopic;

            const result = await API.post('/api/sessions/start', payload);
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
                <button class="btn btn-primary mt-12" id="home-btn">Back to Home</button>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
            container.querySelector('#home-btn').addEventListener('click', () => App.navigate('home'));
        }
    },

    prepTimer: null,

    renderQuestion(container) {
        const q = this.questions[this.currentIndex];
        const progress = `${this.currentIndex + 1} / ${this.questions.length}`;

        const isCueCard = this.part === 2;
        const questionHtml = isCueCard
            ? this.renderCueCard(q.question)
            : `<div class="question-card">
                <span class="part-badge">Question ${progress}</span>
                <p class="question-text mt-12">${q.question}</p>
              </div>`;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part ${this.part} Practice</h2>
            </div>

            ${questionHtml}

            ${isCueCard ? '<div id="prep-timer-area"></div>' : ''}

            <div class="recorder-area ${isCueCard ? 'hidden' : ''}" id="recorder-area">
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
            if (this.prepTimer) { clearInterval(this.prepTimer); this.prepTimer = null; }
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        this.setupRecordButton(container);

        if (isCueCard) {
            this.startPrepTimer(container);
        }
    },

    renderCueCard(question) {
        const bullets = [
            'what it is / who it is',
            'when and where it happened',
            'how you felt about it',
            'and explain why it is important to you'
        ];
        return `
            <div class="cue-card">
                <span class="part-badge">Part 2 - Cue Card</span>
                <p class="question-text mt-12">${question}</p>
                <div class="cue-bullets mt-12">
                    <p class="cue-label">You should say:</p>
                    <ul>
                        ${bullets.map(b => `<li>${b}</li>`).join('')}
                    </ul>
                </div>
            </div>
        `;
    },

    startPrepTimer(container) {
        const prepArea = container.querySelector('#prep-timer-area');
        const recorderArea = container.querySelector('#recorder-area');
        let seconds = 60;

        prepArea.innerHTML = `
            <div class="prep-countdown">
                <div class="prep-label">Preparation Time</div>
                <div class="prep-time" id="prep-time">1:00</div>
                <p class="text-sm text-secondary">Think about what you want to say</p>
                <button class="btn btn-outline mt-12" id="skip-prep">Skip & Start Speaking</button>
            </div>
        `;

        const updateTimer = () => {
            const m = Math.floor(seconds / 60);
            const s = seconds % 60;
            const el = container.querySelector('#prep-time');
            if (el) el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
        };

        const endPrep = () => {
            if (this.prepTimer) { clearInterval(this.prepTimer); this.prepTimer = null; }
            prepArea.innerHTML = '';
            recorderArea.classList.remove('hidden');
        };

        container.querySelector('#skip-prep').addEventListener('click', endPrep);

        this.prepTimer = setInterval(() => {
            seconds--;
            if (seconds <= 0) {
                endPrep();
            } else {
                updateTimer();
            }
        }, 1000);
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

            const words = result.transcription.split(/\s+/).filter(w => w.length > 0).length;
            const wpm = result.duration > 0 ? Math.round((words / result.duration) * 60) : 0;

            transcriptionArea.innerHTML = `
                <div class="transcription-card">
                    <h3>Your Response</h3>
                    <p class="text">${result.transcription}</p>
                    <p class="wpm-stats mt-8">${words} words · ${wpm} WPM · ${result.duration}s</p>
                </div>
            `;

            const isLast = this.currentIndex >= this.questions.length - 1;
            const showFollowUp = this.part === 3;

            actionArea.innerHTML = `
                ${showFollowUp ? '<button class="btn btn-outline mt-12" id="followup-btn">Get Follow-up Question</button>' : ''}
                <button class="btn btn-primary mt-12" id="next-btn">
                    ${isLast ? 'Get Feedback' : 'Next Question'}
                </button>
            `;

            if (showFollowUp) {
                actionArea.querySelector('#followup-btn').addEventListener('click', async () => {
                    const followBtn = actionArea.querySelector('#followup-btn');
                    followBtn.textContent = 'Generating...';
                    followBtn.disabled = true;
                    try {
                        const fuResult = await API.post('/api/follow-up', {
                            question: q.question,
                            answer: result.transcription,
                            part: 3,
                        });
                        followBtn.remove();
                        const fuDiv = document.createElement('div');
                        fuDiv.className = 'followup-card mt-12';
                        fuDiv.innerHTML = `
                            <h3>Follow-up Question</h3>
                            <p class="question-text">${fuResult.follow_up_question}</p>
                            <p class="text-xs text-secondary mt-8">You can answer this or skip to the next question</p>
                        `;
                        actionArea.insertBefore(fuDiv, actionArea.querySelector('#next-btn'));
                    } catch (e) {
                        followBtn.textContent = 'Failed - Try Again';
                        followBtn.disabled = false;
                    }
                });
            }

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

    renderGrammarCorrections(corrections) {
        if (!corrections || !corrections.length) return '';
        const items = corrections.map(c => `
            <div class="grammar-item">
                <div class="grammar-original">${c.original}</div>
                <div class="grammar-arrow">&#8594;</div>
                <div class="grammar-corrected">${c.corrected}</div>
                <div class="grammar-explanation">${c.explanation}</div>
            </div>
        `).join('');
        return `
            <div class="grammar-card">
                <h3>Grammar Corrections</h3>
                ${items}
            </div>
        `;
    },

    renderPronunciationTips(issues) {
        if (!issues || !issues.length) return '';
        const items = issues.map(i => `
            <div class="pron-item">
                <span class="pron-word">${i.word}</span>
                <span class="pron-tip">${i.tip}</span>
            </div>
        `).join('');
        return `
            <div class="pronunciation-card">
                <h3>Pronunciation Tips</h3>
                ${items}
            </div>
        `;
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

                ${this.renderGrammarCorrections(result.grammar_corrections)}
                ${this.renderPronunciationTips(result.pronunciation_issues)}

                <div id="sample-answer-area"></div>

                <button class="btn btn-primary mt-12" id="home-btn">Back to Home</button>
                <button class="btn btn-outline mt-8" id="retry-btn">Practice Again</button>
            `;

            // Sample answer button
            const sampleArea = container.querySelector('#sample-answer-area');
            sampleArea.innerHTML = `<button class="btn btn-sample mt-12" id="sample-btn">Show Sample Answer</button>`;
            container.querySelector('#sample-btn').addEventListener('click', async () => {
                sampleArea.innerHTML = `<div class="loading"><div class="spinner"></div><span>Generating sample...</span></div>`;
                try {
                    const q = this.questions[0];
                    const sampleResult = await API.post('/api/sample-answer', { question: q.question, part: this.part });
                    sampleArea.innerHTML = `
                        <div class="sample-card">
                            <h3>Sample Answer (Band 7+)</h3>
                            <p class="text">${sampleResult.sample_answer}</p>
                        </div>
                    `;
                } catch (e) {
                    sampleArea.innerHTML = `<div class="card"><p class="text-secondary">Failed to load sample answer.</p></div>`;
                }
            });

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
