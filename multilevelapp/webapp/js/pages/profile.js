/**
 * Profile page — user info, referral, admin button, settings, sign out.
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

        // Check admin status
        let isAdmin = false;
        try {
            await API.get('/api/admin/stats');
            isAdmin = true;
        } catch (e) {}

        // Get referral info
        let referral = null;
        try {
            referral = await API.get('/api/referral');
        } catch (e) {}

        // Get subscription info
        let limits = null;
        try {
            limits = await API.get('/api/subscription');
        } catch (e) {}

        let planCardHtml = '';
        if (limits) {
            const isActive = limits.status === 'active' && limits.plan !== 'free';
            const isPending = limits.pending != null;
            if (isActive) {
                const planLabel = limits.plan === 'weekly' ? 'Weekly' : 'Monthly';
                planCardHtml = `
                    <div class="profile-plan-card active" id="plan-card">
                        <div class="profile-plan-icon">&#11088;</div>
                        <div class="profile-plan-info">
                            <div class="profile-plan-name">${planLabel} Plan</div>
                            <div class="profile-plan-detail">${limits.days_left} days left · ${limits.mock_remaining} mocks · ${limits.practice_remaining} practice</div>
                        </div>
                        <div class="profile-plan-arrow">&#8250;</div>
                    </div>
                `;
            } else if (isPending) {
                planCardHtml = `
                    <div class="profile-plan-card pending" id="plan-card">
                        <div class="profile-plan-icon">&#9203;</div>
                        <div class="profile-plan-info">
                            <div class="profile-plan-name">Payment Under Review</div>
                            <div class="profile-plan-detail">${limits.pending.plan} plan pending</div>
                        </div>
                        <div class="profile-plan-arrow">&#8250;</div>
                    </div>
                `;
            } else {
                planCardHtml = `
                    <div class="profile-plan-card free" id="plan-card">
                        <div class="profile-plan-icon">&#127381;</div>
                        <div class="profile-plan-info">
                            <div class="profile-plan-name">Free Plan</div>
                            <div class="profile-plan-detail">${limits.mock_remaining} mocks · ${limits.practice_remaining} practice left</div>
                        </div>
                        <div class="profile-plan-arrow">&#8250;</div>
                    </div>
                `;
            }
        }

        const adminBtn = isAdmin ? `
            <button class="btn btn-primary mt-12 mb-12" id="admin-btn">Admin Panel</button>
        ` : '';

        const referralHtml = referral ? `
            <div class="referral-section mt-16">
                <h3 class="mb-8">Invite Friends</h3>
                <div class="card">
                    <p class="text-sm text-secondary mb-8">Share your code to earn bonus mock tests! Both you and your friend get +1 mock.</p>
                    <div class="referral-code-row">
                        <div class="referral-code" id="referral-code">${referral.code || '...'}</div>
                        <button class="btn-copy" id="copy-btn">Copy</button>
                    </div>
                    <div class="referral-stats mt-12">
                        <div class="referral-stat">
                            <div class="stat-value">${referral.referral_count || 0}</div>
                            <div class="stat-label">Friends invited</div>
                        </div>
                        <div class="referral-stat">
                            <div class="stat-value">${referral.bonus_mocks || 0}</div>
                            <div class="stat-label">Bonus mocks</div>
                        </div>
                    </div>
                </div>
            </div>
        ` : '';

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

            ${planCardHtml}

            ${adminBtn}

            ${referralHtml}

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
                <div class="settings-item" id="target-level-item">
                    <div class="left">
                        <div class="icon-circle" style="background:#DBEAFE;color:#2B77E7">&#127942;</div>
                        <div class="label">Target Level</div>
                    </div>
                    <select class="target-select" id="target-select">
                        ${['Below B1', 'B1', 'B2', 'C1'].map(v =>
                            `<option value="${v}" ${(settings.target_level || 'B2') === v ? 'selected' : ''}>${v}</option>`
                        ).join('')}
                    </select>
                </div>
            </div>

            <button class="btn btn-outline mt-20" id="sign-out-btn">Sign Out</button>
        `;

        // Admin button
        if (isAdmin) {
            document.getElementById('admin-btn').addEventListener('click', () => {
                App.navigate('admin');
            });
        }

        // Plan card click
        const planCard = document.getElementById('plan-card');
        if (planCard) {
            planCard.addEventListener('click', () => App.navigate('premium'));
        }

        // Referral copy
        const copyBtn = document.getElementById('copy-btn');
        if (copyBtn && referral?.code) {
            copyBtn.addEventListener('click', () => {
                const text = `Join Multilevel Speaking Practice and get a bonus mock test! Use my code: ${referral.code}`;
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(text).then(() => {
                        copyBtn.textContent = 'Copied!';
                        setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
                    });
                } else if (window.Telegram?.WebApp) {
                    window.Telegram.WebApp.showAlert('Your referral code: ' + referral.code);
                }
            });
        }

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

        // Target level selector
        document.getElementById('target-select').addEventListener('change', async (e) => {
            const val = e.target.value;
            try {
                await API.put('/api/user/settings', { target_level: val });
                if (App.userData) App.userData.settings.target_level = val;
            } catch (err) {
                console.error('Failed to save target level:', err);
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
