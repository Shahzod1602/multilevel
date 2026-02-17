/**
 * Audio recorder using MediaRecorder API.
 * Supports maxDuration for auto-stop.
 */
const Recorder = {
    mediaRecorder: null,
    chunks: [],
    stream: null,
    startTime: null,
    timerInterval: null,
    onTick: null,
    onStop: null,
    maxDuration: null,
    mimeType: '',

    async start(onTick, onStop, maxDuration) {
        this.onTick = onTick;
        this.onStop = onStop;
        this.maxDuration = maxDuration || null;
        this.chunks = [];

        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });

            // Try webm/opus first, fall back to webm, then any available
            const mimeTypes = [
                'audio/webm;codecs=opus',
                'audio/webm',
                'audio/ogg;codecs=opus',
                'audio/mp4',
            ];
            let mimeType = '';
            for (const type of mimeTypes) {
                if (MediaRecorder.isTypeSupported(type)) {
                    mimeType = type;
                    break;
                }
            }

            this.mimeType = mimeType || 'audio/webm';
            this.mediaRecorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : {});

            this.mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) this.chunks.push(e.data);
            };

            this.mediaRecorder.onstop = () => {
                const blob = new Blob(this.chunks, { type: this.mimeType });
                this.cleanup();
                if (this.onStop) this.onStop(blob);
            };

            this.mediaRecorder.start(); // Collect all data at once for valid file
            this.startTime = Date.now();

            // Timer
            this.timerInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
                if (this.onTick) this.onTick(elapsed);

                // Auto-stop when maxDuration reached
                if (this.maxDuration && elapsed >= this.maxDuration) {
                    this.stop();
                }
            }, 1000);

            return true;
        } catch (err) {
            console.error('Recorder error:', err);
            return false;
        }
    },

    stop() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
        }
    },

    cleanup() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            this.timerInterval = null;
        }
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
    },

    isRecording() {
        return this.mediaRecorder && this.mediaRecorder.state === 'recording';
    },

    getElapsed() {
        if (!this.startTime) return 0;
        return Math.floor((Date.now() - this.startTime) / 1000);
    },

    formatTime(seconds) {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${s.toString().padStart(2, '0')}`;
    }
};
