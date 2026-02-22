/**
 * Payment page — card details, copy, send screenshot flow.
 */
const PaymentPage = {
    plan: 'weekly',

    async render(container, params = {}) {
        this.plan = params.plan || 'weekly';

        const plans = {
            weekly: { name: 'Weekly Plan', amount: '7,000', amountNum: 7000 },
            monthly: { name: 'Monthly Plan', amount: '20,000', amountNum: 20000 },
        };
        const planInfo = plans[this.plan] || plans.weekly;

        container.innerHTML = `
            <div class="page-header">
                <button class="back-btn" id="back-btn">&#8592;</button>
                <h2>Payment Details</h2>
            </div>

            <div class="payment-card-box">
                <div class="payment-row">
                    <div class="payment-label">Card Number</div>
                    <div class="payment-value-row">
                        <div class="payment-value" id="card-number">5614 6819 1914 7144</div>
                        <button class="copy-btn-inline" id="copy-card">Copy</button>
                    </div>
                </div>
                <div class="payment-row">
                    <div class="payment-label">Card Holder</div>
                    <div class="payment-value">Nematov Shahzod</div>
                </div>
                <div class="payment-row">
                    <div class="payment-label">Amount</div>
                    <div class="payment-value">${planInfo.amount} so'm</div>
                </div>
                <div class="payment-row">
                    <div class="payment-label">Plan</div>
                    <div class="payment-value">${planInfo.name}</div>
                </div>
            </div>

            <div class="payment-instructions mt-16">
                <h3>How to pay</h3>
                <ol>
                    <li>Transfer <strong>${planInfo.amount} so'm</strong> to the card above</li>
                    <li>Take a screenshot of the payment</li>
                    <li>Send the screenshot to admin</li>
                </ol>
            </div>

            <button class="btn btn-primary mt-16" id="send-screenshot-btn">Send Screenshot to Admin</button>
            <button class="btn btn-outline mt-8" id="cancel-btn">Cancel</button>

            <div id="payment-status" class="mt-12"></div>
        `;

        container.querySelector('#back-btn').addEventListener('click', () => App.navigate('premium'));
        container.querySelector('#cancel-btn').addEventListener('click', () => App.navigate('premium'));

        // Copy card number
        container.querySelector('#copy-card').addEventListener('click', () => {
            const cardNum = '5614681919147144';
            const btn = container.querySelector('#copy-card');
            if (navigator.clipboard) {
                navigator.clipboard.writeText(cardNum).then(() => {
                    btn.textContent = 'Copied!';
                    setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
                });
            } else {
                btn.textContent = 'Copied!';
                setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
            }
        });

        // Send screenshot button
        container.querySelector('#send-screenshot-btn').addEventListener('click', async () => {
            const btn = container.querySelector('#send-screenshot-btn');
            const statusDiv = container.querySelector('#payment-status');
            btn.disabled = true;
            btn.textContent = 'Processing...';

            try {
                await API.post('/api/subscription/request', { plan: this.plan });
                statusDiv.innerHTML = `
                    <div class="card text-center" style="border-left:4px solid var(--accent-green);">
                        <p style="font-weight:600;">Request submitted!</p>
                        <p class="text-secondary text-sm mt-8">Now send the payment screenshot to admin.</p>
                    </div>
                `;
                btn.textContent = 'Request Sent';

                // Open admin chat
                if (window.Telegram?.WebApp) {
                    window.Telegram.WebApp.openTelegramLink('https://t.me/abdushukur_d');
                }
            } catch (err) {
                statusDiv.innerHTML = `
                    <div class="card text-center" style="border-left:4px solid var(--accent-red);">
                        <p class="text-secondary">${err.message}</p>
                    </div>
                `;
                btn.disabled = false;
                btn.textContent = 'Send Screenshot to Admin';
            }
        });
    }
};
