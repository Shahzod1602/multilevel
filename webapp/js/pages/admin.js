/**
 * Admin Panel page — stats dashboard + user management.
 */
const AdminPage = {
    async render(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading admin panel...</span></div>`;

        try {
            const stats = await API.get('/api/admin/stats');

            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Admin Panel</h2>
                </div>

                <div class="admin-stats">
                    <div class="admin-stat-card">
                        <div class="stat-value">${stats.total_users}</div>
                        <div class="stat-label">Total Users</div>
                    </div>
                    <div class="admin-stat-card">
                        <div class="stat-value">${stats.active_today}</div>
                        <div class="stat-label">Active Today</div>
                    </div>
                    <div class="admin-stat-card">
                        <div class="stat-value">${stats.sessions_today}</div>
                        <div class="stat-label">Sessions Today</div>
                    </div>
                    <div class="admin-stat-card">
                        <div class="stat-value">${stats.premium_count}</div>
                        <div class="stat-label">Premium Users</div>
                    </div>
                </div>

                <h3 class="mt-20 mb-8">User Management</h3>
                <div class="search-wrapper">
                    <input type="text" class="search-input" id="search-input" placeholder="Search by name, username, or ID...">
                </div>

                <div id="users-list"></div>
            `;

            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('profile'));

            // Search
            let searchTimeout;
            const searchInput = container.querySelector('#search-input');
            const usersList = container.querySelector('#users-list');

            const doSearch = async (q) => {
                usersList.innerHTML = `<div class="loading"><div class="spinner"></div></div>`;
                try {
                    const data = await API.get(`/api/admin/users?q=${encodeURIComponent(q)}`);
                    this.renderUsers(usersList, data.users || []);
                } catch (e) {
                    usersList.innerHTML = `<div class="card"><p class="text-secondary">Error: ${e.message}</p></div>`;
                }
            };

            searchInput.addEventListener('input', () => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => doSearch(searchInput.value), 300);
            });

            // Initial load
            doSearch('');
        } catch (err) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Admin Panel</h2>
                </div>
                <div class="card text-center"><p class="text-secondary">${err.message}</p></div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('profile'));
        }
    },

    renderUsers(container, users) {
        if (!users.length) {
            container.innerHTML = `<div class="card text-center"><p class="text-secondary">No users found.</p></div>`;
            return;
        }

        container.innerHTML = users.map(u => `
            <div class="admin-user-row">
                <div class="admin-user-info">
                    <div class="admin-user-name">${this.escapeHtml(u.first_name || 'User')} <span class="text-xs text-secondary">@${this.escapeHtml(u.username || '')}</span></div>
                    <div class="text-xs text-secondary">ID: ${u.user_id} · ${u.sessions || 0} sessions</div>
                </div>
                <select class="tariff-select" data-user-id="${u.user_id}">
                    <option value="free" ${u.tariff === 'free' ? 'selected' : ''}>Free</option>
                    <option value="gold" ${u.tariff === 'gold' ? 'selected' : ''}>Gold</option>
                </select>
            </div>
        `).join('');

        // Tariff change handlers
        container.querySelectorAll('.tariff-select').forEach(sel => {
            sel.addEventListener('change', async (e) => {
                const userId = parseInt(sel.dataset.userId);
                const tariff = e.target.value;
                try {
                    await API.put(`/api/admin/users/${userId}/tariff`, { tariff });
                    sel.style.borderColor = 'var(--accent-green)';
                    setTimeout(() => { sel.style.borderColor = ''; }, 1000);
                } catch (err) {
                    sel.style.borderColor = 'var(--accent-red)';
                    console.error('Tariff update failed:', err);
                }
            });
        });
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};
