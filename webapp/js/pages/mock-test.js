/**
 * Mock Test page — full 4-part speaking test simulation.
 */
const MockTestPage = {
    sessionId: null,
    test: null,
    parts: ["1.1", "1.2", "2", "3"],
    currentPartIndex: 0,
    currentIndex: 0,
    responses: [],
    state: 'idle',
    showTranscription: true,
    selectedVoice: null,
    mood: 'normal',
    recordingStartTime: null,
    autoAdvanceTimer: null,
    currentAudio: null,
    debateSide: null,

    get currentPart() {
        return this.parts[this.currentPartIndex];
    },

    get currentPartData() {
        return this.test?.parts?.[this.currentPart] || {};
    },

    get currentQuestions() {
        return this.currentPartData.questions || [];
    },

    async render(container) {
        this.currentPartIndex = 0;
        this.currentIndex = 0;
        this.responses = [];
        this.state = 'idle';
        this.showTranscription = true;
        this.selectedVoice = null;
        this.mood = 'normal';
        this.recordingStartTime = null;
        this.debateSide = null;
        this.test = null;
        this.clearAutoAdvance();

        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Preparing mock test...</span></div>`;

        try {
            const result = await API.post('/api/sessions/start', { type: 'mock', part: '1.1' });
            this.sessionId = result.session_id;
            this.test = result.test;

            this.renderIntro(container);
        } catch (err) {
            const isLimit = err.message.includes('Daily mock limit');
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>${isLimit ? 'Limit Reached' : 'Error'}</h2>
                </div>
                ${isLimit ? `
                    <div class="upgrade-prompt">
                        <div class="upgrade-icon">&#128274;</div>
                        <h3>Daily Mock Limit Reached</h3>
                        <p>You've used all your mock tests for today.</p>
                        <p class="mt-8">Upgrade to <strong>Premium</strong> for 5 mock tests per day!</p>
                        <button class="btn btn-primary mt-12" id="upgrade-btn">Contact Admin to Upgrade</button>
                        <button class="btn btn-outline mt-8" id="home-btn">Back to Home</button>
                    </div>
                ` : `
                    <div class="card text-center">
                        <p class="text-secondary">${err.message}</p>
                    </div>
                `}
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
            container.querySelector('#home-btn')?.addEventListener('click', () => App.navigate('home'));
            container.querySelector('#upgrade-btn')?.addEventListener('click', () => {
                if (window.Telegram?.WebApp) {
                    window.Telegram.WebApp.openTelegramLink('https://t.me/abdushukur_d');
                }
            });
        }
    },

    renderIntro(container) {
        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Mock Speaking Test</h2>
            </div>

            <div class="card text-center">
                <h3>Full Multilevel Speaking Test</h3>
                <p class="text-secondary mt-8">This simulates the real exam with all 4 parts.</p>
                <p class="text-secondary mt-8">
                    Part 1.1: 3 questions (30s each)<br>
                    Part 1.2: Pictures + 3 questions (30s each)<br>
                    Part 2: 3 questions (60s each)<br>
                    Part 3: Debate (120s)
                </p>
            </div>

            <div class="card mt-12">
                <div class="setting-row">
                    <div>
                        <h3>Transcription</h3>
                        <p class="text-secondary text-sm">Show your speech text after each answer</p>
                    </div>
                    <div class="toggle ${this.showTranscription ? 'active' : ''}" id="transcription-toggle"></div>
                </div>
            </div>

            <div class="card mt-12">
                <h3>Examiner Voice</h3>
                <p class="text-secondary text-sm mt-4">Choose a voice to read questions aloud</p>
                <div class="voice-grid mt-12">
                    <div class="voice-card" data-voice="sarah">
                        <div class="voice-icon female">S</div>
                        <div class="voice-info">
                            <span class="voice-name">Sarah</span>
                            <span class="voice-desc">Confident</span>
                        </div>
                        <div class="voice-radio"></div>
                    </div>
                    <div class="voice-card" data-voice="lily">
                        <div class="voice-icon female">L</div>
                        <div class="voice-info">
                            <span class="voice-name">Lily</span>
                            <span class="voice-desc">British</span>
                        </div>
                        <div class="voice-radio"></div>
                    </div>
                    <div class="voice-card" data-voice="charlie">
                        <div class="voice-icon male">C</div>
                        <div class="voice-info">
                            <span class="voice-name">Charlie</span>
                            <span class="voice-desc">Deep</span>
                        </div>
                        <div class="voice-radio"></div>
                    </div>
                    <div class="voice-card" data-voice="roger">
                        <div class="voice-icon male">R</div>
                        <div class="voice-info">
                            <span class="voice-name">Roger</span>
                            <span class="voice-desc">Casual</span>
                        </div>
                        <div class="voice-radio"></div>
                    </div>
                </div>
            </div>

            <div class="card mt-12">
                <h3>Examiner Mood</h3>
                <p class="text-secondary text-sm mt-4">How is the examiner feeling today?</p>
                <div class="mood-selector mt-12">
                    <button class="mood-btn" data-mood="happy">
                        <span class="mood-emoji">😊</span>
                        <span class="mood-label">Happy</span>
                    </button>
                    <button class="mood-btn active" data-mood="normal">
                        <span class="mood-emoji">😐</span>
                        <span class="mood-label">Normal</span>
                    </button>
                    <button class="mood-btn" data-mood="angry">
                        <span class="mood-emoji">😠</span>
                        <span class="mood-label">Angry</span>
                    </button>
                </div>
            </div>

            <button class="btn btn-primary mt-16" id="start-btn">Start Test</button>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));

        // Mood selector
        container.querySelectorAll('.mood-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                container.querySelectorAll('.mood-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.mood = btn.dataset.mood;
            });
        });

        // Transcription toggle
        const toggle = container.querySelector('#transcription-toggle');
        toggle.addEventListener('click', () => {
            this.showTranscription = !this.showTranscription;
            toggle.classList.toggle('active', this.showTranscription);
        });

        // Voice selection
        container.querySelectorAll('.voice-card').forEach(card => {
            card.addEventListener('click', () => {
                const voice = card.dataset.voice;
                if (this.selectedVoice === voice) {
                    this.selectedVoice = null;
                    card.classList.remove('selected');
                } else {
                    container.querySelectorAll('.voice-card').forEach(c => c.classList.remove('selected'));
                    this.selectedVoice = voice;
                    card.classList.add('selected');
                }
            });
        });

        container.querySelector('#start-btn').addEventListener('click', () => {
            this.renderQuestion(container);
        });
    },

    renderQuestion(container) {
        this.clearAutoAdvance();
        const part = this.currentPart;
        const questions = this.currentQuestions;

        // Part 3: debate flow
        if (part === "3") {
            if (!this.debateSide) {
                this.renderDebateSelection(container);
            } else {
                this.renderDebateRecording(container);
            }
            return;
        }

        // Check if out of questions for current part
        if (this.currentIndex >= questions.length) {
            if (this.currentPartIndex < this.parts.length - 1) {
                this.currentPartIndex++;
                this.currentIndex = 0;
                this.debateSide = null;
                this.renderPartTransition(container);
                return;
            }
            this.showResults(container);
            return;
        }

        const q = questions[this.currentIndex];
        const totalQ = questions.length;

        // Part 1.2: show images
        const imagesHtml = (part === "1.2" && this.currentPartData.images)
            ? `<div class="picture-gallery">
                ${this.currentPartData.images.map((img, i) => `
                    <div class="picture-card">
                        <img src="${img}" alt="Picture ${i + 1}" loading="lazy">
                    </div>
                `).join('')}
              </div>`
            : '';

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part ${part}</h2>
                <button class="finish-test-btn" id="finish-btn">Finish</button>
            </div>

            ${imagesHtml}

            <div class="question-card">
                <span class="part-badge">Part ${part} - Q${this.currentIndex + 1}/${totalQ}</span>
                <p class="question-text mt-12">${q.question}</p>
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
            this.clearAutoAdvance();
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        container.querySelector('#finish-btn').addEventListener('click', () => {
            this.clearAutoAdvance();
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        this.setupRecordBtn(container);
        this.playQuestion(q.question);
    },

    renderDebateSelection(container) {
        const partData = this.currentPartData;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part 3 - Debate</h2>
                <button class="finish-test-btn" id="finish-btn">Finish</button>
            </div>

            <div class="debate-card">
                <h3>${partData.topic}</h3>
                <div class="debate-table">
                    <div class="debate-col for">
                        <div class="debate-col-header">For</div>
                        ${(partData.for_points || []).map(p => `<div class="debate-point">${p}</div>`).join('')}
                    </div>
                    <div class="debate-col against">
                        <div class="debate-col-header">Against</div>
                        ${(partData.against_points || []).map(p => `<div class="debate-point">${p}</div>`).join('')}
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
        container.querySelector('#finish-btn').addEventListener('click', () => App.navigate('home'));

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
        const partData = this.currentPartData;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part 3 - Debate</h2>
                <button class="finish-test-btn" id="finish-btn">Finish</button>
            </div>

            <div class="card text-center">
                <span class="part-badge">Arguing ${this.debateSide === 'for' ? 'FOR' : 'AGAINST'}</span>
                <p class="question-text mt-12">${partData.topic}</p>
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
            this.clearAutoAdvance();
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        container.querySelector('#finish-btn').addEventListener('click', () => {
            this.clearAutoAdvance();
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        this.setupRecordBtn(container);
        this.playQuestion(partData.topic);
    },

    renderPartTransition(container) {
        this.clearAutoAdvance();
        const part = this.currentPart;
        const partDescriptions = {
            "1.2": 'You will see pictures and answer questions about them (30s each).',
            "2": 'You will discuss topics with extended responses (60s each).',
            "3": 'You will debate a topic — choose For or Against and argue your position (120s).',
        };

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Mock Test</h2>
                <button class="finish-test-btn" id="finish-btn">Finish</button>
            </div>
            <div class="card text-center">
                <h3>Moving to Part ${part}</h3>
                <p class="text-secondary mt-8">${partDescriptions[part] || ''}</p>
            </div>
            <button class="btn btn-primary mt-16" id="continue-btn">Continue</button>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
        container.querySelector('#finish-btn').addEventListener('click', () => App.navigate('home'));
        container.querySelector('#continue-btn').addEventListener('click', () => {
            this.renderQuestion(container);
        });
    },

    async playQuestion(text) {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }

        if (!this.selectedVoice) return;

        try {
            const initData = API.getInitData();
            const resp = await fetch('/api/tts', {
                method: 'POST',
                headers: {
                    'Authorization': `tma ${initData}`,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text, voice: this.selectedVoice }),
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
        const part = this.currentPart;
        const isDebate = (part === "3");

        transcriptionArea.innerHTML = `<div class="loading"><div class="spinner"></div><span>${this.showTranscription ? 'Transcribing...' : 'Saving response...'}</span></div>`;

        try {
            const questionText = isDebate
                ? this.currentPartData.topic
                : this.currentQuestions[this.currentIndex].question;

            const extMap = {'audio/webm': '.webm', 'audio/ogg': '.ogg', 'audio/mp4': '.m4a', 'audio/mpeg': '.mp3'};
            const ext = extMap[(Recorder.mimeType || '').split(';')[0]] || '.ogg';
            const formData = new FormData();
            formData.append('audio', blob, `recording${ext}`);
            formData.append('question', questionText);
            formData.append('part', part);
            if (isDebate && this.debateSide) {
                formData.append('debate_side', this.debateSide);
            }

            const result = await API.postForm(`/api/sessions/${this.sessionId}/respond`, formData);

            this.responses.push({
                part: part,
                question: questionText,
                transcription: result.transcription,
                duration: result.duration,
            });

            if (this.showTranscription) {
                const words = result.transcription.split(/\s+/).filter(w => w.length > 0).length;
                const wpm = result.duration > 0 ? Math.round((words / result.duration) * 60) : 0;

                transcriptionArea.innerHTML = `
                    <div class="transcription-card">
                        <h3>Your Response</h3>
                        <p class="text">${result.transcription}</p>
                        <p class="wpm-stats mt-8">${words} words · ${wpm} WPM · ${result.duration}s</p>
                    </div>
                `;
            } else {
                transcriptionArea.innerHTML = `
                    <div class="card text-center">
                        <p class="text-secondary">Response saved</p>
                    </div>
                `;
            }

            if (isDebate) {
                // Debate done — go to results
                actionArea.innerHTML = `<button class="btn btn-primary mt-12" id="next-btn">See Results</button>`;
                actionArea.querySelector('#next-btn').addEventListener('click', () => {
                    this.showResults(container);
                });
            } else {
                this.showNextWithAutoAdvance(actionArea, container);
            }

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
        this.clearAutoAdvance();
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Generating feedback...</span></div>`;

        try {
            const result = await API.post(`/api/sessions/${this.sessionId}/complete`, { mood: this.mood });
            const scores = result.scores || {};
            const overall = Math.round(scores.overall || 0);

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Mock Test Results</h2>
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
                    <p class="text">${result.feedback || 'No detailed feedback.'}</p>
                </div>

                ${this.renderGrammarCorrections(result.grammar_corrections)}
                ${this.renderPronunciationTips(result.pronunciation_issues)}

                <div id="sample-answer-area"></div>

                <button class="btn btn-primary mt-12" id="home-btn">Back to Home</button>
            `;

            // Sample answer button
            const sampleArea = container.querySelector('#sample-answer-area');
            sampleArea.innerHTML = `<button class="btn btn-sample mt-12" id="sample-btn">Show Sample Answer</button>`;
            container.querySelector('#sample-btn').addEventListener('click', async () => {
                sampleArea.innerHTML = `<div class="loading"><div class="spinner"></div><span>Generating sample...</span></div>`;
                try {
                    const part2Qs = this.test?.parts?.["2"]?.questions || [];
                    const firstQ = part2Qs[0] || this.test?.parts?.["1.1"]?.questions?.[0];
                    if (!firstQ) throw new Error('No question');
                    const sampleResult = await API.post('/api/sample-answer', { question: firstQ.question, part: "2" });
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
