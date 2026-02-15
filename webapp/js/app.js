/**
 * Main app — router, initialization, Telegram WebApp integration.
 */
const App = {
    currentPage: 'home',
    userData: null,
    container: null,

    async init() {
        this.container = document.getElementById('page-container');

        // Telegram WebApp setup
        if (window.Telegram?.WebApp) {
            const tg = window.Telegram.WebApp;
            tg.ready();
            tg.expand();
            tg.setHeaderColor('#F5F5F7');
            tg.setBackgroundColor('#F5F5F7');
        }

        // Load user data
        try {
            this.userData = await API.get('/api/user/me');

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

        // Navigate to home
        this.navigate('home');
    },

    navigate(page, params = {}) {
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
            default:
                HomePage.render(this.container);
        }
    }
};

// Start app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
