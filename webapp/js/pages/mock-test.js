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
    selectedVoice: null,
    level: 'intermediate',
    mood: 'normal',
    recordingStartTime: null,
    autoAdvanceTimer: null,
    currentAudio: null,

    async render(container) {
        this.currentPart = 1;
        this.currentIndex = 0;
        this.responses = [];
        this.state = 'idle';
        this.showTranscription = true;
        this.selectedVoice = null;
        this.level = 'intermediate';
        this.mood = 'normal';
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
            const isLimit = err.message.includes('Daily limit');
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
                    window.Telegram.WebApp.openTelegramLink('https://t.me/IELTSPEAK_bot');
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
                <h3>Full IELTS Speaking Test</h3>
                <p class="text-secondary mt-8">This simulates the real exam with all 3 parts.</p>
                <p class="text-secondary mt-8">
                    Part 1: 4 questions (30s each)<br>
                    Part 2: 1 topic (2 min)<br>
                    Part 3: 4 questions (1 min each)
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

        // Voice selection (radio style — tap to select, tap again to deselect)
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

    prepTimer: null,

    renderQuestion(container) {
        this.clearAutoAdvance();
        if (this.prepTimer) { clearInterval(this.prepTimer); this.prepTimer = null; }
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
        const isCueCard = this.currentPart === 2;

        const questionHtml = isCueCard
            ? `<div class="cue-card">
                <span class="part-badge">Part 2 - Cue Card</span>
                <p class="question-text mt-12">${q.question}</p>
                <div class="cue-bullets mt-12">
                    <p class="cue-label">You should say:</p>
                    <ul>
                        <li>what it is / who it is</li>
                        <li>when and where it happened</li>
                        <li>how you felt about it</li>
                        <li>and explain why it is important to you</li>
                    </ul>
                </div>
              </div>`
            : `<div class="question-card">
                <span class="part-badge">Part ${this.currentPart} - Q${this.currentIndex + 1}/${totalQ}</span>
                <p class="question-text mt-12">${q.question}</p>
              </div>`;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Part ${this.currentPart}</h2>
                <button class="finish-test-btn" id="finish-btn">Finish</button>
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
            this.clearAutoAdvance();
            if (this.prepTimer) { clearInterval(this.prepTimer); this.prepTimer = null; }
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        container.querySelector('#finish-btn').addEventListener('click', () => {
            this.clearAutoAdvance();
            if (this.prepTimer) { clearInterval(this.prepTimer); this.prepTimer = null; }
            if (Recorder.isRecording()) Recorder.stop();
            App.navigate('home');
        });

        this.setupRecordBtn(container);
        this.playQuestion(q.question);

        if (isCueCard) {
            this.startPrepTimer(container);
        }
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
                const m = Math.floor(seconds / 60);
                const s = seconds % 60;
                const el = container.querySelector('#prep-time');
                if (el) el.textContent = `${m}:${s.toString().padStart(2, '0')}`;
            }
        }, 1000);
    },

    async playQuestion(text) {
        // Stop any currently playing audio
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }

        // Skip if no voice selected
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
            App.navigate('home');
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
        const showFollowUp = this.currentPart === 3;

        actionArea.innerHTML = `
            ${showFollowUp ? '<button class="btn btn-outline mt-12" id="followup-btn">Get Follow-up Question</button>' : ''}
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

        if (showFollowUp) {
            actionArea.querySelector('#followup-btn').addEventListener('click', async () => {
                this.clearAutoAdvance();
                const followBtn = actionArea.querySelector('#followup-btn');
                followBtn.textContent = 'Generating...';
                followBtn.disabled = true;
                // Remove countdown during follow-up
                const countdownEl = actionArea.querySelector('#countdown-text');
                if (countdownEl) countdownEl.textContent = '';
                try {
                    const q = this.allQuestions[this.currentPart][this.currentIndex];
                    const lastResponse = this.responses[this.responses.length - 1];
                    const fuResult = await API.post('/api/follow-up', {
                        question: q.question,
                        answer: lastResponse?.transcription || '',
                        part: 3,
                    });
                    followBtn.remove();
                    const fuDiv = document.createElement('div');
                    fuDiv.className = 'followup-card mt-12';
                    fuDiv.innerHTML = `
                        <h3>Follow-up Question</h3>
                        <p class="question-text">${fuResult.follow_up_question}</p>
                        <p class="text-xs text-secondary mt-8">Answer or skip to next</p>
                    `;
                    actionArea.insertBefore(fuDiv, nextBtn);
                } catch (e) {
                    followBtn.textContent = 'Failed';
                    followBtn.disabled = false;
                }
            });
        }

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
            const result = await API.post(`/api/sessions/${this.sessionId}/complete`, { level: this.level, mood: this.mood });
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
                    const firstQ = this.allQuestions[1]?.[0] || this.allQuestions[2]?.[0] || this.allQuestions[3]?.[0];
                    if (!firstQ) throw new Error('No question');
                    const sampleResult = await API.post('/api/sample-answer', { question: firstQ.question, part: 2 });
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
