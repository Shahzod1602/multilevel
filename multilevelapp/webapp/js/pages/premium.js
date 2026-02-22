/**
 * Premium page — subscription plans, current plan status, upgrade flow.
 */
const PremiumPage = {
    async render(container) {
        container.innerHTML = `<div class="loading"><div class="spinner"></div><span>Loading plans...</span></div>`;

        let limits = null;
        try {
            limits = await API.get('/api/subscription');
        } catch (e) {
            container.innerHTML = `
                <div class="page-header">
                    <button class="back-btn" id="back-btn">&#8592;</button>
                    <h2>Premium</h2>
                </div>
                <div class="card text-center"><p class="text-secondary">Failed to load subscription info.</p></div>
            `;
            container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));
            return;
        }

        const isPending = limits.pending != null;
        const isActive = limits.status === 'active' && limits.plan !== 'free';

        let statusCardHtml = '';
        if (isPending) {
            statusCardHtml = `
                <div class="premium-status-card pending">
                    <div class="premium-status-icon">&#9203;</div>
                    <div class="premium-status-title">Payment Under Review</div>
                    <div class="premium-status-desc">Your ${limits.pending.plan} plan request is being processed.</div>
                </div>
            `;
        } else if (isActive) {
            const planLabel = limits.plan === 'weekly' ? 'Weekly Plan' : 'Monthly Plan';
            statusCardHtml = `
                <div class="premium-status-card active">
                    <div class="premium-status-icon">&#11088;</div>
                    <div class="premium-status-title">${planLabel}</div>
                    <div class="premium-status-desc">${limits.days_left} days remaining</div>
                    <div class="premium-usage-row mt-12">
                        <div class="premium-usage-item">
                            <div class="premium-usage-label">Mock Tests</div>
                            <div class="usage-bar"><div class="usage-bar-fill" style="width:${Math.min(100, (limits.mock_used / limits.mock_limit) * 100)}%"></div></div>
                            <div class="premium-usage-count">${limits.mock_used}/${limits.mock_limit}</div>
                        </div>
                        <div class="premium-usage-item">
                            <div class="premium-usage-label">Practice</div>
                            <div class="usage-bar"><div class="usage-bar-fill" style="width:${Math.min(100, (limits.practice_used / limits.practice_limit) * 100)}%"></div></div>
                            <div class="premium-usage-count">${limits.practice_used}/${limits.practice_limit}</div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            statusCardHtml = `
                <div class="premium-status-card free">
                    <div class="premium-status-icon">&#127381;</div>
                    <div class="premium-status-title">Free Plan</div>
                    <div class="premium-status-desc">Until limits exhausted</div>
                    <div class="premium-usage-row mt-12">
                        <div class="premium-usage-item">
                            <div class="premium-usage-label">Mock Tests</div>
                            <div class="usage-bar"><div class="usage-bar-fill" style="width:${Math.min(100, (limits.mock_used / limits.mock_limit) * 100)}%"></div></div>
                            <div class="premium-usage-count">${limits.mock_used}/${limits.mock_limit}</div>
                        </div>
                        <div class="premium-usage-item">
                            <div class="premium-usage-label">Practice</div>
                            <div class="usage-bar"><div class="usage-bar-fill" style="width:${Math.min(100, (limits.practice_used / limits.practice_limit) * 100)}%"></div></div>
                            <div class="premium-usage-count">${limits.practice_used}/${limits.practice_limit}</div>
                        </div>
                    </div>
                </div>
            `;
        }

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Premium</h2>
            </div>

            ${statusCardHtml}

            <div class="section-title mt-20">Upgrade Your Plan</div>

            <div class="plan-card" data-plan="weekly">
                <div class="plan-header">
                    <div class="plan-name">Weekly</div>
                    <div class="plan-price">7,000 <span class="plan-currency">so'm</span></div>
                </div>
                <ul class="plan-features">
                    <li>7 Mock Tests per week</li>
                    <li>50 Practice sessions per week</li>
                    <li>Rebuyable after expiry</li>
                </ul>
                <button class="btn btn-primary plan-btn" id="get-weekly" ${isPending ? 'disabled' : ''}>
                    ${isPending ? 'Pending...' : 'Get Weekly'}
                </button>
            </div>

            <div class="plan-card best-value" data-plan="monthly">
                <div class="best-value-badge">Best Value</div>
                <div class="plan-header">
                    <div class="plan-name">Monthly</div>
                    <div class="plan-price">20,000 <span class="plan-currency">so'm</span></div>
                </div>
                <ul class="plan-features">
                    <li>24 Mock Tests per month</li>
                    <li>200 Practice sessions per month</li>
                    <li>Save 42% vs weekly</li>
                </ul>
                <button class="btn btn-primary plan-btn" id="get-monthly" ${isPending ? 'disabled' : ''}>
                    ${isPending ? 'Pending...' : 'Get Monthly'}
                </button>
            </div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('home'));

        if (!isPending) {
            container.querySelector('#get-weekly').addEventListener('click', () => {
                App.navigate('payment', { plan: 'weekly' });
            });
            container.querySelector('#get-monthly').addEventListener('click', () => {
                App.navigate('payment', { plan: 'monthly' });
            });
        }
    }
};
