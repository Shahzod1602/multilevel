/**
 * Admin Panel page — stats dashboard + user management.
 */
const AdminPage = {
    async render(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading admin panel...</span></div>`;

        try {
            const stats = await API.get('/api/admin/stats');

            // Fetch pending subscriptions
            let pendingSubs = [];
            try {
                const subData = await API.get('/api/admin/subscriptions');
                pendingSubs = subData.subscriptions || [];
            } catch (e) {}

            const pendingHtml = pendingSubs.length > 0 ? `
                <h3 class="mt-20 mb-8">Pending Payments (${pendingSubs.length})</h3>
                <div id="pending-subs">${pendingSubs.map(s => `
                    <div class="sub-request-card" data-sub-id="${s.id}">
                        <div class="sub-request-info">
                            <div class="sub-request-name">${this.escapeHtml(s.first_name || 'User')} <span class="text-xs text-secondary">@${this.escapeHtml(s.username || '')}</span></div>
                            <div class="text-xs text-secondary">ID: ${s.user_id} · ${s.plan} · ${(s.amount || 0).toLocaleString()} so'm</div>
                        </div>
                        <div class="sub-request-actions">
                            <button class="sub-approve-btn" data-sub-id="${s.id}">Approve</button>
                            <button class="sub-reject-btn" data-sub-id="${s.id}">Reject</button>
                        </div>
                    </div>
                `).join('')}</div>
            ` : '';

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

                ${pendingHtml}

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

            // Subscription approve/reject handlers
            container.querySelectorAll('.sub-approve-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const subId = parseInt(btn.dataset.subId);
                    btn.textContent = '...';
                    btn.disabled = true;
                    try {
                        await API.put(`/api/admin/subscriptions/${subId}`, { action: 'approve' });
                        const card = btn.closest('.sub-request-card');
                        card.style.borderLeft = '4px solid var(--accent-green)';
                        card.querySelector('.sub-request-actions').innerHTML = '<span style="color:var(--accent-green);font-weight:600;">Approved</span>';
                    } catch (err) {
                        btn.textContent = 'Error';
                    }
                });
            });

            container.querySelectorAll('.sub-reject-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const subId = parseInt(btn.dataset.subId);
                    btn.textContent = '...';
                    btn.disabled = true;
                    try {
                        await API.put(`/api/admin/subscriptions/${subId}`, { action: 'reject' });
                        const card = btn.closest('.sub-request-card');
                        card.style.borderLeft = '4px solid var(--accent-red)';
                        card.querySelector('.sub-request-actions').innerHTML = '<span style="color:var(--accent-red);font-weight:600;">Rejected</span>';
                    } catch (err) {
                        btn.textContent = 'Error';
                    }
                });
            });
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
