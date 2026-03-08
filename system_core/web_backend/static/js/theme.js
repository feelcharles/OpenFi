// Theme Manager

const Theme = {
    // Initialize theme
    init() {
        const savedTheme = localStorage.getItem(CONFIG.STORAGE_KEYS.THEME) || CONFIG.DEFAULTS.THEME;
        this.setTheme(savedTheme);
        this.setupAutoTheme();
    },
    
    // Set theme
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem(CONFIG.STORAGE_KEYS.THEME, theme);
    },
    
    // Toggle theme
    toggle() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    },
    
    // Setup auto theme based on time
    setupAutoTheme() {
        const hour = new Date().getHours();
        const isNight = hour < 6 || hour >= 18;
        
        // Only auto-switch if user hasn't manually set a preference
        if (!localStorage.getItem(CONFIG.STORAGE_KEYS.THEME)) {
            this.setTheme(isNight ? 'dark' : 'light');
        }
    },
    
    // Get current theme
    getCurrentTheme() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    }
};

// Language Manager
const Lang = {
    current: null,
    
    // Initialize language
    init() {
        const savedLang = localStorage.getItem(CONFIG.STORAGE_KEYS.LANG) || CONFIG.DEFAULTS.LANG;
        this.current = savedLang;
        this.setLang(savedLang);
    },
    
    // Set language
    setLang(lang) {
        this.current = lang;
        localStorage.setItem(CONFIG.STORAGE_KEYS.LANG, lang);
        document.documentElement.setAttribute('lang', lang === 'zh' ? 'zh-CN' : 'en');
        // Trigger re-render if needed
        if (window.App && typeof window.App.render === 'function') {
            window.App.render();
        }
    },
    
    // Set language (alias for setLang, used in UI)
    setLanguage(lang) {
        this.setLang(lang);
        // Re-render current page
        if (window.location.hash) {
            Router.navigate(window.location.hash.substring(1));
        } else {
            Router.navigate('/');
        }
    },
    
    // Toggle language
    toggle() {
        const currentLang = this.getCurrentLang();
        const newLang = currentLang === 'zh' ? 'en' : 'zh';
        this.setLanguage(newLang);
    },
    
    // Get current language
    getCurrentLang() {
        return this.current || localStorage.getItem(CONFIG.STORAGE_KEYS.LANG) || CONFIG.DEFAULTS.LANG;
    }
};
