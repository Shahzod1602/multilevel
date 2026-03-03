/**
 * Main app — router, initialization, Telegram WebApp integration.
 */
const App = {
    currentPage: 'home',
    userData: null,
    container: null,
    isSubscribed: false,

    // Cache subscription status to avoid checking on every navigation
    _subCheckedAt: 0,
    _subCacheTtl: 5 * 60 * 1000, // 5 minutes

    async _checkSubscription(force = false) {
        const now = Date.now();
        if (!force && this.isSubscribed && (now - this._subCheckedAt) < this._subCacheTtl) {
            return true;
        }
        try {
            const subData = await API.get('/api/check-subscription');
            this.isSubscribed = subData.subscribed;
            this._channelUrl = subData.channel_url;
            this._subCheckedAt = now;
        } catch (err) {
            console.warn('Subscription check failed:', err);
            this.isSubscribed = false;
        }
        return this.isSubscribed;
    },

    async init() {
        this.container = document.getElementById('page-container');

        // Telegram WebApp setup
        if (window.Telegram?.WebApp) {
            const tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();
            tg.setHeaderColor('#F5F5F7');
            tg.setBackgroundColor('#F5F5F7');
        } else {
            console.warn('Telegram WebApp not available');
        }

        // Load user data and check subscription in parallel
        try {
            const [userData, subData] = await Promise.all([
                API.get('/api/user/me'),
                API.get('/api/check-subscription'),
            ]);

            this.userData = userData;
            this.isSubscribed = subData.subscribed;
            this._channelUrl = subData.channel_url;
            this._subCheckedAt = Date.now();

            // Apply dark mode from settings
            if (this.userData?.settings?.dark_mode) {
                document.body.classList.add('dark');
                if (window.Telegram?.WebApp) {
                    window.Telegram.WebApp.setHeaderColor('#0F0F1A');
                    window.Telegram.WebApp.setBackgroundColor('#0F0F1A');
                }
            }
        } catch (err) {
            console.warn('Failed to load user data:', err);
        }

        if (!this.isSubscribed) {
            this.showSubscriptionWall();
            return;
        }

        // Navigate to home
        this.navigate('home');
    },

    showSubscriptionWall() {
        const navbar = document.getElementById('navbar');
        if (navbar) navbar.classList.add('hidden');

        const channelUrl = this._channelUrl || 'https://t.me/MultilevelSpeaking9';

        this.container.innerHTML = `
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:80vh;padding:24px;text-align:center;">
                <div style="font-size:64px;margin-bottom:16px;">📢</div>
                <h2 style="margin:0 0 8px;font-size:22px;">Kanalga obuna bo'ling</h2>
                <p style="color:#6B7280;margin:0 0 24px;font-size:15px;line-height:1.5;">
                    Ilovadan foydalanish uchun avval kanalga obuna bo'lishingiz kerak.
                </p>
                <a href="${channelUrl}" target="_blank"
                   style="display:inline-block;background:#7C3AED;color:#fff;padding:14px 32px;border-radius:12px;text-decoration:none;font-weight:600;font-size:16px;margin-bottom:16px;">
                    Kanalga o'tish
                </a>
                <button id="check-sub-btn"
                        style="background:#F3F4F6;color:#374151;padding:12px 28px;border-radius:12px;border:none;font-size:15px;font-weight:500;cursor:pointer;">
                    Tekshirish
                </button>
            </div>
        `;

        document.getElementById('check-sub-btn').addEventListener('click', async () => {
            const btn = document.getElementById('check-sub-btn');
            btn.textContent = 'Tekshirilmoqda...';
            btn.disabled = true;

            try {
                const subscribed = await this._checkSubscription(true); // force re-check
                if (subscribed) {
                    this.navigate('home');
                } else {
                    btn.textContent = 'Obuna topilmadi. Qayta tekshirish';
                    btn.disabled = false;
                }
            } catch (err) {
                btn.textContent = 'Xatolik. Qayta tekshirish';
                btn.disabled = false;
            }
        });
    },

    async navigate(page, params = {}) {
        // Check subscription with cache (avoid Telegram API call on every nav)
        const subscribed = await this._checkSubscription();
        if (!subscribed) {
            this.showSubscriptionWall();
            return;
        }

        this.currentPage = page;

        // Show/hide navbar based on page
        const mainPages = ['home', 'progress', 'profile'];
        const navbar = document.getElementById('navbar');
        if (mainPages.includes(page)) {
            navbar.classList.remove('hidden');
            Navbar.render(page);
        } else {
            navbar.classList.add('hidden');
        }

        // Scroll to top
        window.scrollTo(0, 0);

        // Route to page
        switch (page) {
            case 'home':
                HomePage.render(this.container);
                break;
            case 'progress':
                ProgressPage.render(this.container);
                break;
            case 'profile':
                ProfilePage.render(this.container);
                break;
            case 'practice':
                PracticePage.render(this.container, params);
                break;
            case 'mock-test':
                MockTestPage.render(this.container);
                break;
            case 'tips':
                TipsPage.render(this.container);
                break;
            case 'scoring':
                ScoringPage.render(this.container);
                break;
            case 'pronunciation':
                PronunciationPage.render(this.container);
                break;
            case 'history':
                HistoryPage.render(this.container, params);
                break;
            case 'leaderboard':
                LeaderboardPage.render(this.container);
                break;
            case 'vocabulary':
                VocabularyPage.render(this.container);
                break;
            case 'admin':
                AdminPage.render(this.container);
                break;
            case 'premium':
                PremiumPage.render(this.container);
                break;
            case 'payment':
                PaymentPage.render(this.container, params);
                break;
            default:
                HomePage.render(this.container);
        }
    }
};

// Start app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
