/**
 * API Client for OpenFi Web Backend
 * 
 * Provides HTTP request methods with automatic authentication,
 * error handling, timeout support, and retry logic.
 * 
 * @module API
 */

// Performance monitoring
const PerformanceMonitor = {
    metrics: [],
    maxMetrics: 100,
    
    /**
     * Record API call performance
     * @param {string} endpoint - API endpoint
     * @param {number} duration - Request duration in ms
     * @param {boolean} success - Whether request succeeded
     */
    record(endpoint, duration, success) {
        this.metrics.push({
            endpoint,
            duration,
            success,
            timestamp: Date.now()
        });
        
        // Keep only last 100 metrics
        if (this.metrics.length > this.maxMetrics) {
            this.metrics.shift();
        }
        
        // Log slow requests (> 3 seconds)
        if (duration > 3000) {
            console.warn(`Slow API request: ${endpoint} took ${duration}ms`);
        }
    },
    
    /**
     * Get performance statistics
     * @returns {Object} Performance stats
     */
    getStats() {
        if (this.metrics.length === 0) {
            return { count: 0, avgDuration: 0, successRate: 0 };
        }
        
        const totalDuration = this.metrics.reduce((sum, m) => sum + m.duration, 0);
        const successCount = this.metrics.filter(m => m.success).length;
        
        return {
            count: this.metrics.length,
            avgDuration: Math.round(totalDuration / this.metrics.length),
            successRate: Math.round((successCount / this.metrics.length) * 100),
            slowRequests: this.metrics.filter(m => m.duration > 3000).length
        };
    },
    
    /**
     * Clear all metrics
     */
    clear() {
        this.metrics = [];
    }
};

const API = {
    /**
     * Make HTTP request with authentication, timeout, and error handling
     * 
     * @param {string} endpoint - API endpoint path
     * @param {Object} options - Fetch options
     * @param {string} options.method - HTTP method (GET, POST, PUT, DELETE)
     * @param {Object} options.headers - Additional headers
     * @param {string|FormData} options.body - Request body
     * @param {number} options.timeout - Request timeout in ms (default: 30000)
     * @returns {Promise<Object>} Response data
     * @throws {Error} Request error with descriptive message
     */
    async request(endpoint, options = {}) {
        const token = localStorage.getItem(CONFIG.STORAGE_KEYS.TOKEN);
        const startTime = performance.now();
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...(token && { 'Authorization': `Bearer ${token}` })
            }
        };
        
        const finalOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };
        
        // Add timeout support
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), options.timeout || 30000); // 30 seconds default
        finalOptions.signal = controller.signal;
        
        try {
            const response = await fetch(`${CONFIG.API_BASE_URL}${endpoint}`, finalOptions);
            clearTimeout(timeoutId);
            
            const duration = performance.now() - startTime;
            
            if (response.status === 401) {
                // Unauthorized - clear token and redirect to login
                localStorage.removeItem(CONFIG.STORAGE_KEYS.TOKEN);
                localStorage.removeItem(CONFIG.STORAGE_KEYS.USER);
                if (window.Router) {
                    Router.navigate('/login');
                }
                PerformanceMonitor.record(endpoint, duration, false);
                throw new Error('Unauthorized');
            }
            
            // Try to parse JSON response
            let data;
            try {
                data = await response.json();
            } catch (e) {
                // Response is not JSON (e.g., 502, 503 errors)
                if (!response.ok) {
                    PerformanceMonitor.record(endpoint, duration, false);
                    throw new Error(`Request failed with status ${response.status}: ${response.statusText}`);
                }
                // If response is OK but not JSON, return empty object
                data = {};
            }
            
            if (!response.ok) {
                PerformanceMonitor.record(endpoint, duration, false);
                throw new Error(data?.detail || data?.message || `Request failed with status ${response.status}`);
            }
            
            PerformanceMonitor.record(endpoint, duration, true);
            return data;
        } catch (error) {
            clearTimeout(timeoutId);
            
            const duration = performance.now() - startTime;
            
            if (error.name === 'AbortError') {
                console.error('API Timeout:', endpoint);
                PerformanceMonitor.record(endpoint, duration, false);
                throw new Error('Request timeout - please try again');
            }
            
            console.error('API Error:', error);
            PerformanceMonitor.record(endpoint, duration, false);
            throw error;
        }
    },
    
    /**
     * GET request
     * @param {string} endpoint - API endpoint path
     * @returns {Promise<Object>} Response data
     */
    get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    },
    
    /**
     * POST request
     * @param {string} endpoint - API endpoint path
     * @param {Object} data - Request body data
     * @returns {Promise<Object>} Response data
     */
    post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },
    
    /**
     * PUT request
     * @param {string} endpoint - API endpoint path
     * @param {Object} data - Request body data
     * @returns {Promise<Object>} Response data
     */
    put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },
    
    /**
     * DELETE request
     * @param {string} endpoint - API endpoint path
     * @returns {Promise<Object>} Response data
     */
    delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    },
    
    // Auth APIs
    auth: {
        /**
         * Login with username and password
         * @param {string} username - User's username
         * @param {string} password - User's password
         * @returns {Promise<Object>} Login response with access token
         */
        login(username, password) {
            return API.post(CONFIG.ENDPOINTS.AUTH.LOGIN, {
                username,
                password
            });
        },
        
        /**
         * Logout current user
         * @returns {Promise<Object>} Logout response
         */
        logout() {
            return API.post(CONFIG.ENDPOINTS.AUTH.LOGOUT);
        },
        
        /**
         * Register new user
         * @param {string} username - User's username
         * @param {string} email - User's email
         * @param {string} password - User's password
         * @returns {Promise<Object>} Registration response
         */
        register(username, email, password) {
            return API.post(CONFIG.ENDPOINTS.AUTH.REGISTER, {
                username,
                email,
                password
            });
        },
        
        /**
         * Setup admin account with initial password
         * @param {string} password - Admin password
         * @returns {Promise<Object>} Setup response
         */
        setupAdmin(password) {
            return API.post(CONFIG.ENDPOINTS.AUTH.SETUP, {
                password
            });
        },
        
        /**
         * Change user password
         * @param {string} oldPassword - Current password
         * @param {string} newPassword - New password
         * @returns {Promise<Object>} Change password response
         */
        changePassword(oldPassword, newPassword) {
            return API.post('/api/v1/auth/change-password', {
                old_password: oldPassword,
                new_password: newPassword
            });
        }
    },
    
    // User APIs
    user: {
        getMe() {
            return API.get(CONFIG.ENDPOINTS.USER.ME);
        },
        
        update(data) {
            return API.put(CONFIG.ENDPOINTS.USER.UPDATE, data);
        },
        
        downloadData() {
            return API.get(CONFIG.ENDPOINTS.USER.DOWNLOAD_DATA);
        },
        
        resetData() {
            return API.post(CONFIG.ENDPOINTS.USER.RESET_DATA);
        }
    },
    
    // Dashboard APIs (现有后端)
    dashboard: {
        getMetrics() {
            return API.get(CONFIG.ENDPOINTS.DASHBOARD.METRICS);
        },
        
        getStatus() {
            return API.get(CONFIG.ENDPOINTS.DASHBOARD.STATUS);
        },
        
        getRecentSignals(limit = 20) {
            return API.get(`${CONFIG.ENDPOINTS.DASHBOARD.SIGNALS}?limit=${limit}`);
        }
    },
    
    // Intelligence APIs
    intelligence: {
        getOverview() {
            return API.dashboard.getMetrics();  // 使用现有的 metrics
        },
        
        getNews(limit = 20) {
            return API.dashboard.getRecentSignals(limit);  // 使用现有的 signals
        },
        
        getCalendar(startDate, endDate) {
            // TODO: 待后端实现
            return Promise.resolve([]);
        },
        
        getSentiment(limit = 50) {
            // TODO: 待后端实现
            return Promise.resolve([]);
        },
        
        getResearch(limit = 20) {
            // TODO: 待后端实现
            return Promise.resolve([]);
        }
    },
    
    // Market APIs
    market: {
        getWatchlist() {
            return API.get(CONFIG.ENDPOINTS.MARKET.WATCHLIST);
        },
        
        addToWatchlist(symbol, category) {
            return API.post(CONFIG.ENDPOINTS.MARKET.WATCHLIST, {
                symbol,
                category
            });
        },
        
        removeFromWatchlist(symbol) {
            return API.delete(`${CONFIG.ENDPOINTS.MARKET.WATCHLIST}/${symbol}`);
        },
        
        getQuote(symbol) {
            return API.get(`${CONFIG.ENDPOINTS.MARKET.QUOTE}/${symbol}`);
        },
        
        getChart(symbol, interval = '1d', range = '1M') {
            return API.get(`${CONFIG.ENDPOINTS.MARKET.CHART}/${symbol}?interval=${interval}&range=${range}`);
        }
    },
    
    // Quant APIs
    quant: {
        getEAList() {
            return API.get(CONFIG.ENDPOINTS.QUANT.EA_LIST);  // 使用现有的 ea-profiles
        },
        
        uploadEA(file) {
            const formData = new FormData();
            formData.append('file', file);
            return API.request(CONFIG.ENDPOINTS.QUANT.EA_LIST, {
                method: 'POST',
                body: formData,
                headers: {}
            });
        },
        
        deleteEA(id) {
            return API.delete(`${CONFIG.ENDPOINTS.QUANT.EA_LIST}/${id}`);
        },
        
        getFactorList() {
            // TODO: 待后端实现
            return Promise.resolve([]);
        },
        
        uploadFactor(file) {
            // TODO: 待后端实现
            return Promise.resolve({ success: true });
        },
        
        deleteFactor(id) {
            // TODO: 待后端实现
            return Promise.resolve({ success: true });
        },
        
        runBacktest(config) {
            // TODO: 待后端实现
            return Promise.resolve({ success: true });
        },
        
        getScreening(factors) {
            // TODO: 待后端实现
            return Promise.resolve([]);
        }
    },
    
    // Agents APIs
    agents: {
        getList() {
            return API.get(CONFIG.ENDPOINTS.AGENTS.LIST);
        },
        
        create(agent) {
            return API.post(CONFIG.ENDPOINTS.AGENTS.CREATE, agent);
        },
        
        update(id, agent) {
            return API.put(`${CONFIG.ENDPOINTS.AGENTS.UPDATE}/${id}`, agent);
        },
        
        delete(id) {
            return API.delete(`${CONFIG.ENDPOINTS.AGENTS.DELETE}/${id}`);
        },
        
        test(id, testType) {
            return API.post(`${CONFIG.ENDPOINTS.AGENTS.TEST}/${id}`, { testType });
        }
    },
    
    // Trading APIs
    trading: {
        getTrades(params = {}) {
            const queryParams = new URLSearchParams();
            if (params.start_date) queryParams.append('start_date', params.start_date);
            if (params.end_date) queryParams.append('end_date', params.end_date);
            if (params.symbol) queryParams.append('symbol', params.symbol);
            if (params.limit) queryParams.append('limit', params.limit);
            
            const queryString = queryParams.toString();
            return API.get(`${CONFIG.ENDPOINTS.TRADING.TRADES}${queryString ? '?' + queryString : ''}`);
        },
        
        getTradeById(id) {
            return API.get(`${CONFIG.ENDPOINTS.TRADING.TRADE_BY_ID}/${id}`);
        },
        
        getAccounts() {
            // TODO: 待后端实现
            return Promise.resolve([]);
        },
        
        addAccount(account) {
            // TODO: 待后端实现
            return Promise.resolve({ success: true });
        },
        
        updateAccount(id, account) {
            // TODO: 待后端实现
            return Promise.resolve({ success: true });
        },
        
        deleteAccount(id) {
            // TODO: 待后端实现
            return Promise.resolve({ success: true });
        },
        
        getPositions(accountId) {
            // TODO: 待后端实现
            return Promise.resolve([]);
        },
        
        getOrders(accountId) {
            // TODO: 待后端实现
            return Promise.resolve([]);
        }
    },
    
    // System APIs
    system: {
        getStatus() {
            return API.get(CONFIG.ENDPOINTS.SYSTEM.STATUS);  // 使用现有的 system-status
        },
        
        getConfig(filename) {
            return API.get(`${CONFIG.ENDPOINTS.SYSTEM.CONFIG}/${filename}`);  // 使用现有的 config
        },
        
        updateConfig(filename, content) {
            return API.put(`${CONFIG.ENDPOINTS.SYSTEM.CONFIG}/${filename}`, { content });  // 使用现有的 config
        },
        
        getLogs(limit = 100) {
            // TODO: 待后端实现
            return Promise.resolve([]);
        },
        
        reset(password) {
            // TODO: 待后端实现
            return Promise.resolve({ success: true });
        }
    }
};


// Expose performance monitor globally
window.APIPerformance = PerformanceMonitor;

// Log performance stats every 5 minutes
setInterval(() => {
    const stats = PerformanceMonitor.getStats();
    if (stats.count > 0) {
        console.log('API Performance Stats:', stats);
    }
}, 300000);
