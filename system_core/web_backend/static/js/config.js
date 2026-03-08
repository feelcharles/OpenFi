// OpenFi Configuration

const CONFIG = {
    API_BASE_URL: window.location.origin,
    API_VERSION: 'v1',
    WS_URL: `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`,
    
    // Storage keys
    STORAGE_KEYS: {
        TOKEN: 'openfi_token',
        USER: 'openfi_user',
        THEME: 'openfi_theme',
        LANG: 'openfi_lang',
        FIRST_TIME: 'openfi_first_time'
    },
    
    // Default settings
    DEFAULTS: {
        THEME: 'light',
        LANG: 'en',  // Default to English
        REFRESH_INTERVAL: 30000, // 30 seconds
        MAX_KEYWORDS: 20,
        MAX_WATCHLIST: 10,
        MAX_FOCUS: 3,
        MAX_AGENTS: 5,
        MAX_ACCOUNTS: 3
    },
    
    // API Endpoints (对接现有后端)
    ENDPOINTS: {
        AUTH: {
            LOGIN: '/api/v1/auth/login',
            LOGOUT: '/api/v1/auth/logout',
            REGISTER: '/api/v1/auth/register',
            SETUP: '/api/v1/auth/setup-admin'
        },
        USER: {
            ME: '/api/v1/users/me',
            UPDATE: '/api/v1/users/me',
            DOWNLOAD_DATA: '/api/v1/users/me/data',
            RESET_DATA: '/api/v1/users/me/reset'
        },
        DASHBOARD: {
            METRICS: '/api/v1/dashboard/metrics',
            STATUS: '/api/v1/dashboard/system-status',
            SIGNALS: '/api/v1/dashboard/recent-signals'
        },
        INTELLIGENCE: {
            OVERVIEW: '/api/v1/dashboard/metrics',  // 使用现有的 metrics
            NEWS: '/api/v1/dashboard/recent-signals',  // 使用现有的 signals
            CALENDAR: '/api/v1/intelligence/calendar',  // 待实现
            SENTIMENT: '/api/v1/intelligence/sentiment',  // 待实现
            RESEARCH: '/api/v1/intelligence/research'  // 待实现
        },
        MARKET: {
            WATCHLIST: '/api/v1/market/watchlist',  // 待实现
            QUOTE: '/api/v1/market/quote',  // 待实现
            CHART: '/api/v1/market/chart'  // 待实现
        },
        QUANT: {
            EA_LIST: '/api/v1/ea-profiles',  // 使用现有的 EA profiles
            FACTOR_LIST: '/api/v1/quant/factors',  // 待实现
            BACKTEST: '/api/v1/quant/backtest',  // 待实现
            SCREENING: '/api/v1/quant/screening'  // 待实现
        },
        AGENTS: {
            LIST: '/api/v1/agents',
            CREATE: '/api/v1/agents',
            UPDATE: '/api/v1/agents',
            DELETE: '/api/v1/agents',
            TEST: '/api/v1/agents/test'
        },
        TRADING: {
            TRADES: '/api/v1/trades',  // 使用现有的 trades
            TRADE_BY_ID: '/api/v1/trades',  // 使用现有的 trades/{id}
            ACCOUNTS: '/api/v1/trading/accounts',  // 待实现
            POSITIONS: '/api/v1/trading/positions',  // 待实现
            ORDERS: '/api/v1/trading/orders'  // 待实现
        },
        SYSTEM: {
            STATUS: '/api/v1/dashboard/system-status',  // 使用现有的 system-status
            CONFIG: '/api/v1/config',  // 使用现有的 config
            LOGS: '/api/v1/system/logs',  // 待实现
            RESET: '/api/v1/system/reset'  // 待实现
        }
    },
    
    // Module colors for mobile view
    MODULE_COLORS: {
        intelligence: ['#667eea', '#764ba2'],
        market: ['#f093fb', '#f5576c'],
        quant: ['#4facfe', '#00f2fe'],
        ai: ['#43e97b', '#38f9d7'],
        trading: ['#fa709a', '#fee140'],
        system: ['#30cfd0', '#330867']
    }
};

// Translations
const TRANSLATIONS = {
    en: {
        // Navigation
        nav: {
            intelligence: 'Intelligence',
            market: 'Market',
            quant: 'Quant Engine',
            ai: 'AI & Agents',
            trading: 'Trading',
            system: 'System'
        },
        // Common
        common: {
            loading: 'Loading...',
            save: 'Save',
            cancel: 'Cancel',
            delete: 'Delete',
            edit: 'Edit',
            add: 'Add',
            confirm: 'Confirm',
            back: 'Back',
            refresh: 'Refresh',
            search: 'Search',
            settings: 'Settings',
            logout: 'Logout',
            language: 'Language'
        },
        // Welcome
        welcome: {
            title: 'OpenFi',
            tagline: 'Your Intelligent Trading Copilot',
            subtitle1: '· Cutting through noise with valuable intelligence news',
            subtitle2: '· Mastering markets with multi-dimensional analytics',
            subtitle3: '· Operating within a bank-secure private space',
            getStarted: 'Get Started',
            features: 'Core Features',
            feature1: '🎯 Smart Intelligence - AI-powered news filtering and analysis',
            feature2: '📊 Real-time Markets - Multi-asset monitoring and alerts',
            feature3: '⚡ Quant Engine - Advanced backtesting and factor screening',
            feature4: '🤖 AI Agents - Autonomous trading assistants',
            feature5: '🔒 Bank-grade Security - End-to-end encryption',
            selectLanguage: 'Select Language'
        },
        // Auth
        auth: {
            setupAdmin: 'Setup Admin Password',
            username: 'Username',
            password: 'Password',
            confirmPassword: 'Confirm Password',
            login: 'Login',
            register: 'Register',
            changePassword: 'Change Password',
            currentPassword: 'Current Password',
            newPassword: 'New Password',
            defaultCredentials: 'Default Credentials',
            securityWarning: 'Security Warning',
            mustChangePassword: 'You must change the default password on first login',
            passwordRequirement: 'Please set a strong password (at least 8 characters)'
        },
        // Modules
        modules: {
            intelligence: {
                title: 'Intelligence',
                subtitle: 'Multi-source intelligence gathering and analysis'
            },
            market: {
                title: 'Market',
                subtitle: 'Real-time market monitoring'
            },
            quant: {
                title: 'Quant Engine',
                subtitle: 'Backtesting and factor screening'
            },
            ai: {
                title: 'AI & Agents',
                subtitle: 'Intelligent agent system'
            },
            trading: {
                title: 'Trading',
                subtitle: 'Account and position management'
            },
            system: {
                title: 'System',
                subtitle: 'System settings and configuration'
            }
        },
        // System
        system: {
            configFiles: 'Configuration Files',
            selectConfig: 'Select a configuration file',
            selectConfigDesc: 'Choose a file from the left to edit',
            loadingConfig: 'Loading configuration...',
            configLoaded: 'Configuration loaded',
            autoSaved: 'Configuration auto-saved',
            configSaved: 'Configuration saved successfully',
            confirmReload: 'You have unsaved changes. Reload anyway?'
        }
    },
    zh: {
        // Navigation
        nav: {
            intelligence: '情报',
            market: '行情',
            quant: '量化引擎',
            ai: 'AI & Agents',
            trading: '交易账户',
            system: '系统'
        },
        // Common
        common: {
            loading: '加载中...',
            save: '保存',
            cancel: '取消',
            delete: '删除',
            edit: '编辑',
            add: '添加',
            confirm: '确认',
            back: '返回',
            refresh: '刷新',
            search: '搜索',
            settings: '设置',
            logout: '退出登录',
            language: '语言'
        },
        // Welcome
        welcome: {
            title: 'OpenFi',
            tagline: '您的智能交易伙伴',
            subtitle1: '· 穿透信息迷雾的智能情报',
            subtitle2: '· 驾驭多维数据的量化引擎',
            subtitle3: '· 银行级加密守护的私密空间，赋能你的每一次决策',
            getStarted: '首次使用',
            features: '核心功能',
            feature1: '🎯 智能情报 - AI驱动的新闻过滤与分析',
            feature2: '📊 实时行情 - 多资产监控与预警',
            feature3: '⚡ 量化引擎 - 高级回测与因子筛选',
            feature4: '🤖 AI代理 - 自主交易助手',
            feature5: '🔒 银行级安全 - 端到端加密',
            selectLanguage: '选择语言'
        },
        // Auth
        auth: {
            setupAdmin: '设置管理员密码',
            username: '用户名',
            password: '密码',
            confirmPassword: '确认密码',
            login: '登录',
            register: '注册',
            changePassword: '修改密码',
            currentPassword: '当前密码',
            newPassword: '新密码',
            defaultCredentials: '默认账户',
            securityWarning: '安全提示',
            mustChangePassword: '首次登录后请立即修改密码',
            passwordRequirement: '请设置一个强密码（至少8个字符）'
        },
        // Modules
        modules: {
            intelligence: {
                title: '情报',
                subtitle: '多源情报获取与分析'
            },
            market: {
                title: '行情',
                subtitle: '实时行情监控'
            },
            quant: {
                title: '量化引擎',
                subtitle: '回测与因子筛选'
            },
            ai: {
                title: 'AI & Agents',
                subtitle: '智能代理系统'
            },
            trading: {
                title: '交易账户',
                subtitle: '账户与持仓管理'
            },
            system: {
                title: '系统',
                subtitle: '系统设置与配置'
            }
        },
        // System
        system: {
            configFiles: '配置文件',
            selectConfig: '选择配置文件',
            selectConfigDesc: '从左侧选择一个文件进行编辑',
            loadingConfig: '正在加载配置...',
            configLoaded: '配置已加载',
            autoSaved: '配置已自动保存',
            configSaved: '配置保存成功',
            confirmReload: '您有未保存的更改。确定要重新加载吗？'
        }
    }
};
