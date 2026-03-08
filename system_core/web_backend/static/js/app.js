// Main Application

const App = {
    container: null,
    isMobile: false,
    
    // Initialize app
    async init() {
        this.container = document.getElementById('app');
        this.isMobile = Utils.isMobile();
        
        // Initialize theme and language
        Theme.init();
        Lang.init();
        
        // Setup routes
        this.setupRoutes();
        
        // Initialize router
        Router.init();
        
        // Setup window resize handler
        window.addEventListener('resize', Utils.debounce(() => {
            const wasMobile = this.isMobile;
            this.isMobile = Utils.isMobile();
            if (wasMobile !== this.isMobile) {
                this.render();
            }
        }, 250));
    },
    
    // Setup routes
    setupRoutes() {
        console.log('Setting up routes...');
        
        // Welcome/First time (no auth required)
        Router.add('/', () => {
            console.log('Route: /');
            if (Auth.isFirstTime()) {
                this.renderWelcome();
            } else if (!Auth.isAuthenticated()) {
                Router.navigate('/login');
            } else {
                Router.navigate('/home');
            }
        }, false);
        
        // Welcome page (no auth required)
        Router.add('/welcome', () => {
            console.log('Route: /welcome');
            this.renderWelcome();
        }, false);
        
        // Setup page (no auth required)
        Router.add('/setup', () => {
            console.log('Route: /setup');
            this.renderSetup();
        }, false);
        
        // Login (no auth required)
        Router.add('/login', () => {
            console.log('Route: /login');
            this.renderLogin();
        }, false);
        
        // Change Password (auth required)
        Router.add('/change-password', () => {
            console.log('Route: /change-password');
            this.renderChangePassword();
        }, true);
        
        // Home (auth required)
        Router.add('/home', () => {
            console.log('Route: /home');
            this.renderHome();
        }, true);
        
        // Intelligence (auth required)
        Router.add('/intelligence', () => {
            console.log('Route: /intelligence');
            this.renderIntelligence();
        }, true);
        
        // Market (auth required)
        Router.add('/market', () => {
            console.log('Route: /market');
            this.renderMarket();
        }, true);
        
        // Quant (auth required)
        Router.add('/quant', () => {
            console.log('Route: /quant');
            this.renderQuant();
        }, true);
        
        // AI & Agents (auth required)
        Router.add('/ai', () => {
            console.log('Route: /ai');
            this.renderAI();
        }, true);
        
        // Trading (auth required)
        Router.add('/trading', () => {
            console.log('Route: /trading');
            this.renderTrading();
        }, true);
        
        // System (auth required)
        Router.add('/system', () => {
            console.log('Route: /system');
            this.renderSystem();
        }, true);
        
        console.log('Routes registered:', Object.keys(Router.routes));
    },
    
    // Render welcome page
    renderWelcome() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="welcome-page">
                <div class="welcome-container">
                    <!-- Language Selector -->
                    <div class="language-selector">
                        <button class="lang-btn ${Lang.current === 'en' ? 'active' : ''}" onclick="Lang.setLanguage('en')">
                            English
                        </button>
                        <button class="lang-btn ${Lang.current === 'zh' ? 'active' : ''}" onclick="Lang.setLanguage('zh')">
                            中文
                        </button>
                    </div>
                    
                    <div class="welcome-logo">OF</div>
                    <h1 class="welcome-title">${Utils.t('welcome.title')}</h1>
                    <h2 class="welcome-tagline">${Utils.t('welcome.tagline')}</h2>
                    <div class="welcome-subtitles">
                        <p class="welcome-subtitle">${Utils.t('welcome.subtitle1')}</p>
                        <p class="welcome-subtitle">${Utils.t('welcome.subtitle2')}</p>
                        <p class="welcome-subtitle">${Utils.t('welcome.subtitle3')}</p>
                    </div>
                    
                    <div class="welcome-features">
                        <h3>${Utils.t('welcome.features')}</h3>
                        <ul>
                            <li>${Utils.t('welcome.feature1')}</li>
                            <li>${Utils.t('welcome.feature2')}</li>
                            <li>${Utils.t('welcome.feature3')}</li>
                            <li>${Utils.t('welcome.feature4')}</li>
                            <li>${Utils.t('welcome.feature5')}</li>
                        </ul>
                    </div>
                    
                    <button class="btn btn-primary btn-block" onclick="Router.navigate('/setup')">
                        ${Utils.t('welcome.getStarted')}
                    </button>
                </div>
            </div>
        `;
    },
    
    // Render setup page
    renderSetup() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="auth-page">
                <div class="auth-container">
                    <!-- Language Selector -->
                    <div class="language-selector">
                        <button class="lang-btn ${Lang.current === 'en' ? 'active' : ''}" onclick="Lang.setLanguage('en')">EN</button>
                        <button class="lang-btn ${Lang.current === 'zh' ? 'active' : ''}" onclick="Lang.setLanguage('zh')">中文</button>
                    </div>
                    
                    <div class="auth-logo">OF</div>
                    <div class="auth-header">
                        <h2 class="auth-title">${Utils.t('auth.setupAdmin')}</h2>
                        <p class="auth-subtitle">${Utils.t('auth.mustChangePassword')}</p>
                    </div>
                    
                    <form id="setupForm">
                        <div class="form-group">
                            <label class="form-label">${Utils.t('auth.password')}</label>
                            <input type="password" class="form-input" id="password" required minlength="8" maxlength="72" placeholder="${Utils.t('auth.passwordRequirement')}">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">${Utils.t('auth.confirmPassword')}</label>
                            <input type="password" class="form-input" id="confirmPassword" required minlength="8" maxlength="72" placeholder="${Utils.t('auth.confirmPassword')}">
                        </div>
                        
                        <button type="submit" class="btn btn-primary btn-block">${Utils.t('common.confirm')}</button>
                    </form>
                </div>
            </div>
        `;
        
        document.getElementById('setupForm').onsubmit = async (e) => {
            e.preventDefault();
            const password = document.getElementById('password').value.trim();
            const confirmPassword = document.getElementById('confirmPassword').value.trim();
            
            // Client-side validation
            if (!password || password.length < 8) {
                Utils.showToast(Utils.t('auth.passwordRequirement') || 'Password must be at least 8 characters', 'error');
                return;
            }
            
            if (password.length > 72) {
                Utils.showToast('Password must not exceed 72 characters', 'error');
                return;
            }
            
            if (password !== confirmPassword) {
                Utils.showToast(Utils.t('auth.passwordMismatch') || 'Passwords do not match', 'error');
                return;
            }
            
            try {
                const result = await Auth.setupAdmin(password);
                Utils.showToast(Utils.t('auth.setupSuccess') || 'Setup complete! Please login with admin account', 'success');
                setTimeout(() => {
                    Router.navigate('/login');
                }, 2000);
            } catch (error) {
                Utils.showToast(error.message, 'error');
            }
        };
    },
    
    // Render login page
    renderLogin() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="auth-page">
                <div class="auth-container">
                    <!-- Language Selector -->
                    <div class="language-selector">
                        <button class="lang-btn ${Lang.current === 'en' ? 'active' : ''}" onclick="Lang.setLanguage('en')">EN</button>
                        <button class="lang-btn ${Lang.current === 'zh' ? 'active' : ''}" onclick="Lang.setLanguage('zh')">中文</button>
                    </div>
                    
                    <div class="auth-logo">OF</div>
                    <div class="auth-header">
                        <h2 class="auth-title">OpenFi ${Utils.t('auth.login')}</h2>
                        <p class="auth-subtitle">${Utils.t('welcome.subtitle')}</p>
                    </div>
                    
                    <div class="alert-box">
                        <strong>📌 ${Utils.t('auth.defaultCredentials')}:</strong><br>
                        ${Utils.t('auth.username')}: admin<br>
                        ${Utils.t('auth.password')}: admin123<br>
                        <span style="color: #d32f2f;">⚠ ${Utils.t('auth.mustChangePassword')}</span>
                    </div>
                    
                    <form id="loginForm">
                        <div class="form-group">
                            <label class="form-label">${Utils.t('auth.username')}</label>
                            <input type="text" class="form-input" id="username" required value="admin">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">${Utils.t('auth.password')}</label>
                            <input type="password" class="form-input" id="password" required>
                        </div>
                        
                        <button type="submit" class="btn btn-primary btn-block">${Utils.t('auth.login')}</button>
                    </form>
                </div>
            </div>
        `;
        
        document.getElementById('loginForm').onsubmit = async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value.trim();
            const password = document.getElementById('password').value;
            
            // Client-side validation
            if (!username || username.length < 3) {
                Utils.showToast('Username must be at least 3 characters', 'error');
                return;
            }
            
            if (!password) {
                Utils.showToast('Password is required', 'error');
                return;
            }
            
            try {
                const response = await Auth.login(username, password);
                Utils.showToast(Utils.t('auth.loginSuccess') || 'Login successful', 'success');
                
                // Check if password change is required
                if (response.must_change_password) {
                    Router.navigate('/change-password');
                } else {
                    Router.navigate('/home');
                }
            } catch (error) {
                Utils.showToast(error.message || Utils.t('auth.loginFailed') || 'Login failed', 'error');
            }
        };
    },
    
    // Render change password page
    renderChangePassword() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="auth-page">
                <div class="auth-container">
                    <div class="auth-logo">OF</div>
                    <div class="auth-header">
                        <h2 class="auth-title">修改密码</h2>
                        <p class="auth-subtitle">首次登录需要修改默认密码</p>
                    </div>
                    
                    <div class="alert-box">
                        <strong>⚠ 安全提示：</strong>
                        请设置一个强密码（至少8个字符）
                    </div>
                    
                    <form id="changePasswordForm">
                        <div class="form-group">
                            <label class="form-label">当前密码</label>
                            <input type="password" class="form-input" id="oldPassword" required minlength="8" maxlength="72">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">新密码</label>
                            <input type="password" class="form-input" id="newPassword" required minlength="8" maxlength="72">
                        </div>
                        
                        <div class="form-group">
                            <label class="form-label">确认新密码</label>
                            <input type="password" class="form-input" id="confirmPassword" required minlength="8" maxlength="72">
                        </div>
                        
                        <button type="submit" class="btn btn-primary btn-block">修改密码</button>
                    </form>
                </div>
            </div>
        `;
        
        document.getElementById('changePasswordForm').onsubmit = async (e) => {
            e.preventDefault();
            const oldPassword = document.getElementById('oldPassword').value;
            const newPassword = document.getElementById('newPassword').value.trim();
            const confirmPassword = document.getElementById('confirmPassword').value.trim();
            
            // Client-side validation
            if (!oldPassword) {
                Utils.showToast('Current password is required', 'error');
                return;
            }
            
            if (!newPassword || newPassword.length < 8) {
                Utils.showToast('New password must be at least 8 characters', 'error');
                return;
            }
            
            if (newPassword.length > 72) {
                Utils.showToast('New password must not exceed 72 characters', 'error');
                return;
            }
            
            if (newPassword !== confirmPassword) {
                Utils.showToast('新密码不匹配', 'error');
                return;
            }
            
            if (newPassword === oldPassword) {
                Utils.showToast('新密码不能与旧密码相同', 'error');
                return;
            }
            
            try {
                await Auth.changePassword(oldPassword, newPassword);
                Utils.showToast('密码修改成功', 'success');
                setTimeout(() => {
                    Router.navigate('/home');
                }, 1500);
            } catch (error) {
                Utils.showToast(error.message || '密码修改失败', 'error');
            }
        };
    },
    
    // Render home page
    renderHome() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="app-container">
                <div class="app-header">
                    <h1 class="app-title">OpenFi</h1>
                    <div class="app-actions">
                        <button class="btn-icon" onclick="Lang.toggle()" title="${Utils.t('common.language')}">🌐</button>
                        <button class="btn-icon" onclick="Theme.toggle()" title="${Utils.t('common.theme') || 'Theme'}">🌓</button>
                        <button class="btn-icon" onclick="Auth.logout()" title="${Utils.t('common.logout')}">🚪</button>
                    </div>
                </div>
                
                <div class="modules-grid">
                    <!-- Intelligence Module - Large -->
                    <div class="module-card intelligence large" onclick="Router.navigate('/intelligence')">
                        <div class="module-header">
                            <div class="module-info">
                                <div class="module-icon">📰</div>
                                <div class="module-title">${Utils.t('modules.intelligence.title')}</div>
                                <div class="module-subtitle">${Utils.t('modules.intelligence.subtitle')}</div>
                            </div>
                            <div class="status-indicator"></div>
                        </div>
                        <div class="module-content">
                            <div class="event-list">
                                <div class="event-item">
                                    <span class="event-badge">${Lang.current === 'zh' ? '重要' : 'Important'}</span>
                                    <span>${Lang.current === 'zh' ? '美联储利率决议即将公布' : 'Fed rate decision coming soon'}</span>
                                </div>
                                <div class="event-item">
                                    <span class="event-badge">${Lang.current === 'zh' ? '关注' : 'Watch'}</span>
                                    <span>${Lang.current === 'zh' ? '黄金价格突破关键阻力位' : 'Gold breaks key resistance'}</span>
                                </div>
                                <div class="event-item">
                                    <span class="event-badge">${Lang.current === 'zh' ? '提示' : 'Info'}</span>
                                    <span>${Lang.current === 'zh' ? '欧元区GDP数据好于预期' : 'Eurozone GDP beats expectations'}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Market Module -->
                    <div class="module-card market" onclick="Router.navigate('/market')">
                        <div class="module-header">
                            <div class="module-info">
                                <div class="module-icon">📈</div>
                                <div class="module-title">${Utils.t('modules.market.title')}</div>
                                <div class="module-subtitle">${Utils.t('modules.market.subtitle')}</div>
                            </div>
                            <div class="status-indicator"></div>
                        </div>
                    </div>
                    
                    <!-- Quant Module -->
                    <div class="module-card quant" onclick="Router.navigate('/quant')">
                        <div class="module-header">
                            <div class="module-info">
                                <div class="module-icon">⚙️</div>
                                <div class="module-title">${Utils.t('modules.quant.title')}</div>
                                <div class="module-subtitle">${Utils.t('modules.quant.subtitle')}</div>
                            </div>
                            <div class="status-indicator"></div>
                        </div>
                    </div>
                    
                    <!-- AI Module -->
                    <div class="module-card ai" onclick="Router.navigate('/ai')">
                        <div class="module-header">
                            <div class="module-info">
                                <div class="module-icon">🤖</div>
                                <div class="module-title">${Utils.t('modules.ai.title')}</div>
                                <div class="module-subtitle">${Utils.t('modules.ai.subtitle')}</div>
                            </div>
                            <div class="status-indicator"></div>
                        </div>
                    </div>
                    
                    <!-- Trading Module -->
                    <div class="module-card trading" onclick="Router.navigate('/trading')">
                        <div class="module-header">
                            <div class="module-info">
                                <div class="module-icon">💰</div>
                                <div class="module-title">${Utils.t('modules.trading.title')}</div>
                                <div class="module-subtitle">${Utils.t('modules.trading.subtitle')}</div>
                            </div>
                            <div class="status-indicator"></div>
                        </div>
                    </div>
                    
                    <!-- System Module -->
                    <div class="module-card system" onclick="Router.navigate('/system')">
                        <div class="module-header">
                            <div class="module-info">
                                <div class="module-icon">🔧</div>
                                <div class="module-title">系统</div>
                                <div class="module-subtitle">系统设置与配置</div>
                            </div>
                            <div class="status-indicator"></div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Load module status
        this.loadModuleStatus();
    },
    
    // Load module status
    async loadModuleStatus() {
        try {
            const status = await API.dashboard.getStatus();
            // Update status indicators based on API response
            // This is a placeholder - implement based on your API structure
        } catch (error) {
            console.error('Failed to load module status:', error);
        }
    },
    
    // Render Intelligence page with real data loading
    async renderIntelligence() {
        // Show loading state
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading Intelligence...</p>
            </div>
        `;
        
        try {
            // Load data
            const data = await API.intelligence.getOverview();
            
            // Render with data
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="app-container">
                    <div class="app-header">
                        <h1 class="app-title">${Utils.t('modules.intelligence.title')}</h1>
                        <button class="btn-icon" onclick="Router.navigate('/home')">🏠</button>
                    </div>
                    <div class="content-loaded">
                        <p>Intelligence data loaded successfully</p>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    </div>
                </div>
            `;
        } catch (error) {
            // Show error
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="error-container">
                    <h2>Failed to load Intelligence</h2>
                    <p>${error.message}</p>
                    <button class="btn btn-primary" onclick="Router.navigate('/home')">Back to Home</button>
                </div>
            `;
        }
    },
    
    async renderMarket() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading Market...</p>
            </div>
        `;
        
        try {
            const data = await API.market.getWatchlist();
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="app-container">
                    <div class="app-header">
                        <h1 class="app-title">${Utils.t('modules.market.title')}</h1>
                        <button class="btn-icon" onclick="Router.navigate('/home')">🏠</button>
                    </div>
                    <div class="content-loaded">
                        <p>Market data loaded successfully</p>
                    </div>
                </div>
            `;
        } catch (error) {
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="error-container">
                    <h2>Failed to load Market</h2>
                    <p>${error.message}</p>
                    <button class="btn btn-primary" onclick="Router.navigate('/home')">Back to Home</button>
                </div>
            `;
        }
    },
    
    async renderQuant() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading Quant Engine...</p>
            </div>
        `;
        
        try {
            const data = await API.quant.getEAList();
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="app-container">
                    <div class="app-header">
                        <h1 class="app-title">${Utils.t('modules.quant.title')}</h1>
                        <button class="btn-icon" onclick="Router.navigate('/home')">🏠</button>
                    </div>
                    <div class="content-loaded">
                        <p>Quant data loaded successfully</p>
                    </div>
                </div>
            `;
        } catch (error) {
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="error-container">
                    <h2>Failed to load Quant Engine</h2>
                    <p>${error.message}</p>
                    <button class="btn btn-primary" onclick="Router.navigate('/home')">Back to Home</button>
                </div>
            `;
        }
    },
    
    async renderAI() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading AI & Agents...</p>
            </div>
        `;
        
        try {
            const data = await API.agents.getList();
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="app-container">
                    <div class="app-header">
                        <h1 class="app-title">${Utils.t('modules.ai.title')}</h1>
                        <button class="btn-icon" onclick="Router.navigate('/home')">🏠</button>
                    </div>
                    <div class="content-loaded">
                        <p>AI data loaded successfully</p>
                    </div>
                </div>
            `;
        } catch (error) {
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="error-container">
                    <h2>Failed to load AI & Agents</h2>
                    <p>${error.message}</p>
                    <button class="btn btn-primary" onclick="Router.navigate('/home')">Back to Home</button>
                </div>
            `;
        }
    },
    
    async renderTrading() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            <div class="loading">
                <div class="spinner"></div>
                <p>Loading Trading...</p>
            </div>
        `;
        
        try {
            const data = await API.trading.getTrades({ limit: 20 });
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="app-container">
                    <div class="app-header">
                        <h1 class="app-title">${Utils.t('modules.trading.title')}</h1>
                        <button class="btn-icon" onclick="Router.navigate('/home')">🏠</button>
                    </div>
                    <div class="content-loaded">
                        <p>Trading data loaded successfully</p>
                    </div>
                </div>
            `;
        } catch (error) {
            this.container.innerHTML = `
                <link rel="stylesheet" href="/static/css/modern.css">
                <div class="error-container">
                    <h2>Failed to load Trading</h2>
                    <p>${error.message}</p>
                    <button class="btn btn-primary" onclick="Router.navigate('/home')">Back to Home</button>
                </div>
            `;
        }
    },
    
    renderSystem() {
        this.container.innerHTML = `
            <link rel="stylesheet" href="/static/css/modern.css">
            ${SystemConfig.render()}
        `;
        
        // Initialize system config
        SystemConfig.init();
    }
};

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => App.init());
} else {
    App.init();
}

// Export for global access
window.app = App;
