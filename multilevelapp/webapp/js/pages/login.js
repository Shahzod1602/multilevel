/**
 * Login page — only used in native mobile app (Capacitor).
 * Telegram Mini App skips this entirely (initData auth is automatic).
 *
 * Flow:
 *   1. Generate random state → POST /api/auth/start → { state }
 *   2. Persist state in localStorage so it survives backgrounding while
 *      the user is in Telegram.
 *   3. Open Telegram bot deep link; bot's /start mlogin_<state> registers
 *      the user-id against the state.
 *   4. App polls /api/auth/exchange?state=... AND retries on every foreground
 *      resume — Android pauses background JS timers.
 *   5. On success, save JWT and re-init the app.
 */
const LoginPage = {
    pollHandle: null,
    pollExpiresAt: 0,
    STATE_KEY: 'login_state',
    EXPIRES_KEY: 'login_expires',

    async render(container) {
        this.stopPolling();
        container.innerHTML = `
            <div class="login-page">
                <div class="login-card">
                    <div class="login-logo">Multilevel Speaking</div>
                    <h1>Welcome</h1>
                    <p class="login-sub">Sign in with your Telegram account to continue.</p>

                    <button id="login-tg-btn" class="login-btn">
                        Login with Telegram
                    </button>

                    <div id="login-status" class="login-status hidden">
                        <div class="login-spinner"></div>
                        <div id="login-status-text">Waiting for Telegram…</div>
                        <button id="login-recheck-btn" class="login-cancel">I've confirmed — check now</button>
                        <button id="login-cancel-btn" class="login-cancel">Cancel</button>
                    </div>

                    <p class="login-hint">
                        You'll be sent to Telegram briefly to confirm. Return to this app afterwards — it will log you in automatically.
                    </p>
                </div>
            </div>
        `;

        container.querySelector('#login-tg-btn').addEventListener('click', () => this.startLogin());
        container.querySelector('#login-cancel-btn').addEventListener('click', () => this.cancelLogin());
        container.querySelector('#login-recheck-btn').addEventListener('click', () => this.tryExchangeOnce(true));

        const stored = this.loadState();
        if (stored.state && Date.now() < stored.expiresAt) {
            this.showWaiting();
            this.startPolling();
            this.tryExchangeOnce();
        }
    },

    saveState(state, expiresAt) {
        try {
            localStorage.setItem(this.STATE_KEY, state);
            localStorage.setItem(this.EXPIRES_KEY, String(expiresAt));
        } catch (e) {}
    },

    loadState() {
        try {
            return {
                state: localStorage.getItem(this.STATE_KEY),
                expiresAt: parseInt(localStorage.getItem(this.EXPIRES_KEY) || '0', 10),
            };
        } catch (e) {
            return { state: null, expiresAt: 0 };
        }
    },

    clearState() {
        try {
            localStorage.removeItem(this.STATE_KEY);
            localStorage.removeItem(this.EXPIRES_KEY);
        } catch (e) {}
    },

    async startLogin() {
        const btn = document.getElementById('login-tg-btn');
        btn.disabled = true;
        this.showWaiting();

        try {
            const { state } = await API.post('/api/auth/start', {});
            const expiresAt = Date.now() + 5 * 60 * 1000;
            this.saveState(state, expiresAt);
            this.pollExpiresAt = expiresAt;

            const tgUrl = `https://t.me/${Config.botUsername}?start=mlogin_${state}`;
            this.openExternal(tgUrl);

            this.startPolling();
        } catch (err) {
            this.setStatus('Could not start login: ' + err.message);
            btn.disabled = false;
        }
    },

    openExternal(url) {
        window.open(url, '_blank');
    },

    showWaiting() {
        const status = document.getElementById('login-status');
        if (status) status.classList.remove('hidden');
        this.setStatus('Waiting for Telegram…');
    },

    async tryExchangeOnce(manual = false) {
        const { state, expiresAt } = this.loadState();
        if (!state) return false;
        if (Date.now() > expiresAt) {
            this.clearState();
            this.setStatus('Login timed out. Try again.');
            const btn = document.getElementById('login-tg-btn');
            if (btn) btn.disabled = false;
            return false;
        }
        try {
            const resp = await API.get(`/api/auth/exchange?state=${encodeURIComponent(state)}`);
            if (resp && resp.token) {
                this.stopPolling();
                this.clearState();
                API.setJwt(resp.token);
                App.init();
                return true;
            }
        } catch (e) {
            if (manual) this.setStatus('Not confirmed yet — try again in a moment.');
        }
        return false;
    },

    startPolling() {
        this.stopPolling();
        const tick = () => {
            const { expiresAt } = this.loadState();
            if (Date.now() > expiresAt) {
                this.stopPolling();
                this.clearState();
                this.setStatus('Login timed out. Try again.');
                const btn = document.getElementById('login-tg-btn');
                if (btn) btn.disabled = false;
                return;
            }
            this.tryExchangeOnce();
        };
        this.pollHandle = setInterval(tick, 2000);
    },

    stopPolling() {
        if (this.pollHandle) {
            clearInterval(this.pollHandle);
            this.pollHandle = null;
        }
    },

    cancelLogin() {
        this.stopPolling();
        this.clearState();
        document.getElementById('login-status')?.classList.add('hidden');
        const btn = document.getElementById('login-tg-btn');
        if (btn) btn.disabled = false;
    },

    setStatus(text) {
        const el = document.getElementById('login-status-text');
        if (el) el.textContent = text;
    },
};

window.LoginPage = LoginPage;
