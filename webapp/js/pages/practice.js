/**
 * Practice page — single-part practice with recording, transcription, results.
 */
const PracticePage = {
    sessionId: null,
    questions: [],
    images: [],
    partData: null,
    currentIndex: 0,
    part: '1.1',
    responses: [],
    state: 'idle',
    debateSide: null,

    async render(container, params = {}) {
        this.part = params.part || '1.1';
        this.currentIndex = 0;
        this.responses = [];
        this.state = 'idle';
        this.questions = [];
        this.images = [];
        this.partData = null;
        this.debateSide = null;

        await this.startSession(container);
    },

    async startSession(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Preparing questions...</span></div>`;

        try {
            const payload = { type: 'practice', part: this.part };
            const result = await API.post('/api/sessions/start', payload);
            this.sessionId = result.session_id;
            this.questions = result.questions || [];
            this.images = result.images || [];
            this.partData = result.part_data || null;

            // Part 3 debate — go to debate flow
            if (this.part === "3" && this.partData) {
                this.renderDebateSelection(container);
                return;
            }

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

    renderQuestion(container) {
        const q = this.questions[this.currentIndex];
        const progress = `${this.currentIndex + 1} / ${this.questions.length}`;

        // Part 1.2: show images
        const imagesHtml = (this.part === "1.2" && this.images.length)
            ? `<div class="picture-gallery">
                ${this.images.map((img, i) => `
                    <div class="picture-card">
                        <img src="${img}" alt="Picture ${i + 1}" loading="lazy">
                    </div>
                `).join('')}
              </div>`
            : '';

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part ${this.part} Practice</h2>
            </div>

            ${imagesHtml}

            <div class="question-card">
                <span class="part-badge">Question ${progress}</span>
                <p class="question-text mt-12">${q}</p>
            </div>

            <div class="recorder-area" id="recorder-area">
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

    renderDebateSelection(container) {
        const pd = this.partData;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part 3 - Debate</h2>
            </div>

            <div class="debate-card">
                <h3>${pd.topic}</h3>
                <div class="debate-table">
                    <div class="debate-col for">
                        <div class="debate-col-header">For</div>
                        ${(pd.for_points || []).map(p => `<div class="debate-point">${p}</div>`).join('')}
                    </div>
                    <div class="debate-col against">
                        <div class="debate-col-header">Against</div>
                        ${(pd.against_points || []).map(p => `<div class="debate-point">${p}</div>`).join('')}
                    </div>
                </div>
            </div>

            <p class="text-center text-secondary mt-12">Choose your side:</p>
            <div style="display:flex;gap:10px;margin-top:12px">
                <button class="btn debate-btn for" id="for-btn">For</button>
                <button class="btn debate-btn against" id="against-btn">Against</button>
            </div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));

        container.querySelector('#for-btn').addEventListener('click', () => {
            this.debateSide = 'for';
            this.renderDebateRecording(container);
        });
        container.querySelector('#against-btn').addEventListener('click', () => {
            this.debateSide = 'against';
            this.renderDebateRecording(container);
        });
    },

    renderDebateRecording(container) {
        const pd = this.partData;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part 3 - Debate</h2>
            </div>

            <div class="card text-center">
                <span class="part-badge">Arguing ${this.debateSide === 'for' ? 'FOR' : 'AGAINST'}</span>
                <p class="question-text mt-12">${pd.topic}</p>
                <p class="text-sm text-secondary mt-8">You have 120 seconds to argue your position.</p>
            </div>

            <div class="recorder-area" id="recorder-area">
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
                Recorder.stop();
                this.state = 'processing';
                btn.classList.remove('recording');
                btn.classList.add('disabled');
                hint.textContent = 'Processing...';
                return;
            }

            if (this.state === 'processing') return;

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
        const isDebate = (this.part === "3");

        transcriptionArea.innerHTML = `<div class="loading"><div class="spinner"></div><span>Transcribing...</span></div>`;

        try {
            const questionText = isDebate
                ? this.partData.topic
                : this.questions[this.currentIndex];

            const extMap = {'audio/webm': '.webm', 'audio/ogg': '.ogg', 'audio/mp4': '.m4a', 'audio/mpeg': '.mp3'};
            const ext = extMap[(Recorder.mimeType || '').split(';')[0]] || '.ogg';
            const formData = new FormData();
            formData.append('audio', blob, `recording${ext}`);
            formData.append('question', questionText);
            formData.append('part', this.part);
            if (isDebate && this.debateSide) {
                formData.append('debate_side', this.debateSide);
            }

            const result = await API.postForm(`/api/sessions/${this.sessionId}/respond`, formData);

            this.responses.push({
                question: questionText,
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

            if (isDebate) {
                // Debate done — go to results
                actionArea.innerHTML = `
                    <button class="btn btn-primary mt-12" id="next-btn">Get Feedback</button>
                `;
                actionArea.querySelector('#next-btn').addEventListener('click', () => {
                    this.showResults(container);
                });
            } else {
                const isLast = this.currentIndex >= this.questions.length - 1;
                const showFollowUp = this.part === "2";

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
                                question: questionText,
                                answer: result.transcription,
                                part: "2",
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
            }

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

    cefrBadge(score) {
        if (score == null) return '';
        score = Math.round(score);
        let level, cls;
        if (score >= 65) { level = 'C1'; cls = 'c1'; }
        else if (score >= 51) { level = 'B2'; cls = 'b2'; }
        else if (score >= 38) { level = 'B1'; cls = 'b1'; }
        else { level = 'Below B1'; cls = 'below-b1'; }
        return `<span class="cefr-badge ${cls}">${level}</span>`;
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
            const overall = Math.round(scores.overall || 0);

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Results</h2>
                </div>

                <div class="results-card">
                    <div class="score-main">
                        <div class="score">${overall}</div>
                        <div class="label">Overall Score ${this.cefrBadge(scores.overall)}</div>
                    </div>
                    <div class="score-breakdown">
                        <div class="score-item">
                            <div class="value">${Math.round(scores.fluency || 0)}</div>
                            <div class="name">Fluency</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${Math.round(scores.lexical || 0)}</div>
                            <div class="name">Lexical</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${Math.round(scores.grammar || 0)}</div>
                            <div class="name">Grammar</div>
                        </div>
                        <div class="score-item">
                            <div class="value">${Math.round(scores.pronunciation || 0)}</div>
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
                    const q = this.questions[0] || this.partData?.topic || '';
                    const sampleResult = await API.post('/api/sample-answer', { question: q, part: this.part });
                    sampleArea.innerHTML = `
                        <div class="sample-card">
                            <h3>Sample Answer (Score 60+)</h3>
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
