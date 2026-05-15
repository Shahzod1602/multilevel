/**
 * API client.
 * Supports two environments:
 *   - Telegram Mini App: uses initData header `tma <init_data>`
 *   - Native mobile app (Capacitor): uses JWT header `Bearer <jwt>`
 */
const API = {
    baseUrl: '',
    jwtToken: null,

    isCapacitor() {
        return !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
    },

    isTelegram() {
        return !!(window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData);
    },

    setBaseUrl(url) {
        this.baseUrl = url || '';
    },

    setJwt(token) {
        this.jwtToken = token;
        try {
            if (token) {
                localStorage.setItem('jwt', token);
            } else {
                localStorage.removeItem('jwt');
            }
        } catch (e) {}
    },

    loadJwt() {
        try {
            this.jwtToken = localStorage.getItem('jwt');
        } catch (e) {
            this.jwtToken = null;
        }
        return this.jwtToken;
    },

    getInitData() {
        if (window.Telegram && window.Telegram.WebApp) {
            return window.Telegram.WebApp.initData;
        }
        return '';
    },

    buildAuthHeader() {
        if (this.isTelegram()) {
            return `tma ${this.getInitData()}`;
        }
        if (this.jwtToken) {
            return `Bearer ${this.jwtToken}`;
        }
        return '';
    },

    async request(path, options = {}) {
        const authHeader = this.buildAuthHeader();
        const headers = { ...(options.headers || {}) };
        if (authHeader) headers['Authorization'] = authHeader;

        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        const resp = await fetch(`${this.baseUrl}${path}`, {
            ...options,
            headers,
        });

        if (resp.status === 401 && this.isCapacitor()) {
            this.setJwt(null);
            if (window.App && typeof window.App.navigate === 'function') {
                window.App.navigate('login');
            }
        }

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(err.detail || `HTTP ${resp.status}`);
        }

        return resp.json();
    },

    get(path) {
        return this.request(path);
    },

    post(path, data) {
        return this.request(path, {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    put(path, data) {
        return this.request(path, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },

    postForm(path, formData) {
        return this.request(path, {
            method: 'POST',
            body: formData,
        });
    },
};
