/**
 * API client with Telegram Mini App auth.
 */
const API = {
    baseUrl: '',

    getInitData() {
        if (window.Telegram && window.Telegram.WebApp) {
            return window.Telegram.WebApp.initData;
        }
        return '';
    },

    async request(path, options = {}) {
        const initData = this.getInitData();
        const headers = {
            'Authorization': `tma ${initData}`,
            ...options.headers,
        };

        // Don't set Content-Type for FormData (browser sets boundary automatically)
        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        const resp = await fetch(`${this.baseUrl}${path}`, {
            ...options,
            headers,
        });

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
