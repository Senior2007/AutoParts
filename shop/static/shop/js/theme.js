const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.dataset.theme = savedTheme;
document.documentElement.style.colorScheme = savedTheme;

document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('theme-toggle');
    toggle.checked = savedTheme === 'dark';

    toggle.addEventListener('change', () => {
        const theme = toggle.checked ? 'dark' : 'light';
        document.documentElement.dataset.theme = theme;
        document.documentElement.style.colorScheme = theme;
        localStorage.setItem('theme', theme);
    });
});
