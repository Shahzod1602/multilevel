/**
 * Profile page — user info, support banner, settings, sign out.
 */
const ProfilePage = {
    async render(container) {
        const user = App.userData;
        if (!user) {
            container.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
            return;
        }

        const u = user.user;
        const settings = user.settings || {};
        const stats = user.stats || {};
        const avatarContent = u.photo_url
            ? `<img src="${u.photo_url}" alt="">`
            : (u.first_name ? u.first_name.charAt(0).toUpperCase() : 'U');

        container.innerHTML = `
            <div class="profile-header">
                <div class="avatar">${avatarContent}</div>
                <h2>${this.escapeHtml(u.first_name || 'User')}</h2>
                <p class="text-secondary">@${this.escapeHtml(u.username || 'user')}</p>
            </div>

            <div class="stats-row">
                <div class="stat-card">
                    <div class="stat-value">${stats.total_sessions || 0}</div>
                    <div class="stat-label">Sessions</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">${stats.total_hours || 0}h</div>
                    <div class="stat-label">Practice</div>
                </div>
            </div>

            <div class="support-banner" id="support-btn">
                <h3>Support Us</h3>
                <p>Help us improve the app and add more features!</p>
            </div>

            <h3 class="mb-8">Settings</h3>
            <div class="settings-list">
                <div class="settings-item" id="dark-mode-toggle">
                    <div class="left">
                        <div class="icon-circle" style="background:#2D2B55;color:#A29BFE">&#127769;</div>
                        <div class="label">Dark Mode</div>
                    </div>
                    <div class="toggle ${settings.dark_mode ? 'active' : ''}" id="dark-toggle"></div>
                </div>
                <div class="settings-item" id="notif-toggle">
                    <div class="left">
                        <div class="icon-circle" style="background:#D5F5E3;color:#00B894">&#128276;</div>
                        <div class="label">Notifications</div>
                    </div>
                    <div class="toggle ${settings.notifications ? 'active' : ''}" id="notif-toggle-switch"></div>
                </div>
                <div class="settings-item" id="daily-goal-item">
                    <div class="left">
                        <div class="icon-circle" style="background:#FEF3C7;color:#FDCB6E">&#127919;</div>
                        <div class="label">Daily Goal</div>
                    </div>
                    <span class="text-secondary">${settings.daily_goal || 30} min</span>
                </div>
            </div>

            <button class="btn btn-outline mt-20" id="sign-out-btn">Sign Out</button>
        `;

        // Dark mode toggle
        document.getElementById('dark-mode-toggle').addEventListener('click', async () => {
            const toggle = document.getElementById('dark-toggle');
            const isActive = toggle.classList.toggle('active');
            document.body.classList.toggle('dark', isActive);
            try {
                await API.put('/api/user/settings', { dark_mode: isActive });
                if (App.userData) App.userData.settings.dark_mode = isActive ? 1 : 0;
            } catch (e) {
                console.error('Failed to save dark mode:', e);
            }
        });

        // Notifications toggle
        document.getElementById('notif-toggle').addEventListener('click', async () => {
            const toggle = document.getElementById('notif-toggle-switch');
            const isActive = toggle.classList.toggle('active');
            try {
                await API.put('/api/user/settings', { notifications: isActive });
                if (App.userData) App.userData.settings.notifications = isActive ? 1 : 0;
            } catch (e) {
                console.error('Failed to save notifications:', e);
            }
        });

        // Support banner
        document.getElementById('support-btn').addEventListener('click', () => {
            if (window.Telegram?.WebApp) {
                window.Telegram.WebApp.openTelegramLink('https://t.me/IELTSPEAK_bot');
            }
        });

        // Sign out
        document.getElementById('sign-out-btn').addEventListener('click', () => {
            if (window.Telegram?.WebApp) {
                window.Telegram.WebApp.close();
            }
        });
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};
