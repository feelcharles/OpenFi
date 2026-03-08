// Simple Router with Hash-based routing (reliable and simple)

const Router = {
    routes: {},
    currentRoute: null,
    
    // Add route
    add(path, handler, requiresAuth = false) {
        this.routes[path] = { handler, requiresAuth };
    },
    
    // Navigate to route
    navigate(path) {
        window.location.hash = path;
    },
    
    // Initialize router
    init() {
        // Handle hash change
        window.addEventListener('hashchange', () => this.handleRoute());
        
        // Handle initial route
        this.handleRoute();
    },
    
    // Handle route
    handleRoute() {
        const hash = window.location.hash.slice(1) || '/';
        const route = this.routes[hash];
        
        if (route) {
            // Check authentication requirement
            if (route.requiresAuth && !Auth.isAuthenticated()) {
                console.log('Route requires authentication, redirecting to login');
                this.navigate('/login');
                return;
            }
            
            // Check if password change is required
            if (route.requiresAuth) {
                const user = Auth.getCurrentUser();
                if (user && user.must_change_password && hash !== '/change-password') {
                    console.log('Password change required');
                    this.navigate('/change-password');
                    return;
                }
            }
            
            this.currentRoute = hash;
            try {
                route.handler();
            } catch (error) {
                console.error('Route handler error:', error);
                this.showError('Route Error', error.message);
            }
        } else {
            console.error('Route not found:', hash);
            this.show404(hash);
        }
    },
    
    // Show error page
    showError(title, message) {
        const appContainer = document.getElementById('app');
        if (appContainer) {
            appContainer.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; min-height: 100vh; background: #f3f4f6;">
                    <div style="text-align: center; padding: 40px; background: white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                        <h2 style="color: #ef4444; margin-bottom: 10px;">${title}</h2>
                        <p style="color: #666; margin-bottom: 20px;">${message}</p>
                        <button class="btn btn-primary" onclick="window.location.href='/app'">Go Home</button>
                    </div>
                </div>
            `;
        }
    },
    
    // Show 404 page
    show404(path) {
        const appContainer = document.getElementById('app');
        if (appContainer) {
            appContainer.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; min-height: 100vh; background: #f3f4f6;">
                    <div style="text-align: center; padding: 40px; background: white; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                        <h1 style="font-size: 72px; color: #667eea; margin-bottom: 10px;">404</h1>
                        <h2 style="color: #333; margin-bottom: 10px;">Page Not Found</h2>
                        <p style="color: #666; margin-bottom: 20px;">The route "${path}" does not exist</p>
                        <button class="btn btn-primary" onclick="window.location.href='/app'">Go Home</button>
                    </div>
                </div>
            `;
        }
    },
    
    // Get current route
    getCurrentRoute() {
        return this.currentRoute;
    }
};
