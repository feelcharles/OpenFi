// Authentication Manager

const Auth = {
    // Check if user is authenticated
    isAuthenticated() {
        return !!localStorage.getItem(CONFIG.STORAGE_KEYS.TOKEN);
    },
    
    // Check if first time setup
    isFirstTime() {
        return localStorage.getItem(CONFIG.STORAGE_KEYS.FIRST_TIME) !== 'false';
    },
    
    // Get current user
    getCurrentUser() {
        const userStr = localStorage.getItem(CONFIG.STORAGE_KEYS.USER);
        return userStr ? JSON.parse(userStr) : null;
    },
    
    // Login
    async login(username, password) {
        try {
            const response = await API.auth.login(username, password);
            localStorage.setItem(CONFIG.STORAGE_KEYS.TOKEN, response.access_token);
            
            // Store user info
            const userInfo = {
                user_id: response.user_id,
                username: response.username,
                role: response.role,
                must_change_password: response.must_change_password || false
            };
            localStorage.setItem(CONFIG.STORAGE_KEYS.USER, JSON.stringify(userInfo));
            localStorage.setItem(CONFIG.STORAGE_KEYS.FIRST_TIME, 'false');
            
            return response;
        } catch (error) {
            throw error;
        }
    },
    
    // Logout
    async logout() {
        try {
            await API.auth.logout();
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            localStorage.removeItem(CONFIG.STORAGE_KEYS.TOKEN);
            localStorage.removeItem(CONFIG.STORAGE_KEYS.USER);
            Router.navigate('/login');
        }
    },
    
    // Setup admin (first time)
    async setupAdmin(password) {
        try {
            // 简化版本：直接标记为已设置，然后跳转到登录页
            // 实际的管理员账户需要通过后端的用户管理API创建
            localStorage.setItem(CONFIG.STORAGE_KEYS.FIRST_TIME, 'false');
            
            // 提示用户使用默认账户登录
            return {
                message: '设置完成，请使用默认账户登录',
                username: 'admin',
                note: '首次登录后请立即修改密码'
            };
        } catch (error) {
            throw error;
        }
    },
    
    // Require authentication
    requireAuth() {
        if (!this.isAuthenticated()) {
            Router.navigate('/login');
            return false;
        }
        
        // Check if password change is required
        const user = this.getCurrentUser();
        if (user && user.must_change_password) {
            Router.navigate('/change-password');
            return false;
        }
        
        return true;
    },
    
    // Change password
    async changePassword(oldPassword, newPassword) {
        try {
            const response = await API.auth.changePassword(oldPassword, newPassword);
            
            // Update user info
            const user = this.getCurrentUser();
            if (user) {
                user.must_change_password = false;
                localStorage.setItem(CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));
            }
            
            return response;
        } catch (error) {
            throw error;
        }
    }
};
