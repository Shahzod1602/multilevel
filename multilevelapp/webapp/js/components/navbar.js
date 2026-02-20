/**
 * Bottom navigation bar component.
 */
const Navbar = {
    tabs: [
        {
            id: 'home',
            label: 'Home',
            icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`
        },
        {
            id: 'progress',
            label: 'Progress',
            icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`
        },
        {
            id: 'profile',
            label: 'Profile',
            icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`
        }
    ],

    render(activeTab) {
        const navbar = document.getElementById('navbar');
        navbar.innerHTML = this.tabs.map(tab => `
            <button class="nav-item ${tab.id === activeTab ? 'active' : ''}" data-tab="${tab.id}">
                ${tab.icon}
                <span>${tab.label}</span>
            </button>
        `).join('');

        navbar.querySelectorAll('.nav-item').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                App.navigate(tab);
            });
        });
    }
};
