// WebSocket Client with auto-reconnect

class WebSocketClient {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.isConnecting = false;
        this.isManualClose = false;
        this.messageHandlers = [];
        this.pingInterval = null;
    }
    
    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
            console.log('WebSocket already connecting or connected');
            return;
        }
        
        this.isConnecting = true;
        this.isManualClose = false;
        
        try {
            // Add token to URL if available
            const token = localStorage.getItem(CONFIG.STORAGE_KEYS.TOKEN);
            const wsUrl = token ? `${this.url}?token=${token}` : this.url;
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnecting = false;
                this.reconnectAttempts = 0;
                
                // Start ping/pong for keepalive
                this.startPing();
                
                // Notify handlers
                this.notifyHandlers({ type: 'connection', status: 'connected' });
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected', event.code, event.reason);
                this.isConnecting = false;
                
                // Stop ping
                this.stopPing();
                
                // Notify handlers
                this.notifyHandlers({ type: 'connection', status: 'disconnected' });
                
                // Reconnect if not manual close
                if (!this.isManualClose) {
                    this.reconnect();
                }
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.isConnecting = false;
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error);
                }
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.isConnecting = false;
            this.reconnect();
        }
    }
    
    /**
     * Disconnect from WebSocket server
     */
    disconnect() {
        this.isManualClose = true;
        this.stopPing();
        
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
    
    /**
     * Reconnect to WebSocket server
     */
    reconnect() {
        if (this.isManualClose) {
            return;
        }
        
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            
            console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                if (!this.isManualClose) {
                    this.connect();
                }
            }, delay);
        } else {
            console.error('Max reconnect attempts reached');
            this.notifyHandlers({ 
                type: 'error', 
                message: 'Failed to reconnect to WebSocket server' 
            });
        }
    }
    
    /**
     * Send message to server
     */
    send(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
            return true;
        } else {
            console.warn('WebSocket not connected, cannot send message');
            return false;
        }
    }
    
    /**
     * Start ping/pong for keepalive
     */
    startPing() {
        this.stopPing();
        
        this.pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send({ type: 'ping' });
            }
        }, 30000); // Ping every 30 seconds
    }
    
    /**
     * Stop ping/pong
     */
    stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }
    
    /**
     * Handle incoming message
     */
    handleMessage(data) {
        console.log('WebSocket message received:', data.type);
        
        // Handle pong
        if (data.type === 'pong') {
            return;
        }
        
        // Notify all handlers
        this.notifyHandlers(data);
    }
    
    /**
     * Add message handler
     */
    addHandler(handler) {
        if (typeof handler === 'function') {
            this.messageHandlers.push(handler);
        }
    }
    
    /**
     * Remove message handler
     */
    removeHandler(handler) {
        const index = this.messageHandlers.indexOf(handler);
        if (index > -1) {
            this.messageHandlers.splice(index, 1);
        }
    }
    
    /**
     * Notify all handlers
     */
    notifyHandlers(data) {
        this.messageHandlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error('Handler error:', error);
            }
        });
    }
    
    /**
     * Get connection status
     */
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Global WebSocket client instance
let wsClient = null;

/**
 * Initialize WebSocket client
 */
function initWebSocket() {
    if (wsClient) {
        return wsClient;
    }
    
    // Determine WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/notifications`;
    
    wsClient = new WebSocketClient(wsUrl);
    
    // Add default handler for notifications
    wsClient.addHandler((data) => {
        switch (data.type) {
            case 'signal':
                handleSignalNotification(data);
                break;
            case 'trade':
                handleTradeNotification(data);
                break;
            case 'system_event':
                handleSystemEventNotification(data);
                break;
            case 'connection':
                handleConnectionStatus(data);
                break;
            case 'error':
                handleErrorNotification(data);
                break;
        }
    });
    
    return wsClient;
}

/**
 * Handle signal notification
 */
function handleSignalNotification(data) {
    console.log('Signal notification:', data);
    
    // Show toast notification
    if (window.Utils && Utils.showToast) {
        Utils.showToast(`New signal: ${data.data.summary}`, 'info');
    }
    
    // Update UI if on relevant page
    if (window.Router && Router.getCurrentRoute() === '/intelligence') {
        // Refresh signals list
        // TODO: Implement signal list refresh
    }
}

/**
 * Handle trade notification
 */
function handleTradeNotification(data) {
    console.log('Trade notification:', data);
    
    // Show toast notification
    if (window.Utils && Utils.showToast) {
        Utils.showToast(`Trade executed: ${data.data.symbol} ${data.data.direction}`, 'success');
    }
    
    // Update UI if on relevant page
    if (window.Router && Router.getCurrentRoute() === '/trading') {
        // Refresh trades list
        // TODO: Implement trades list refresh
    }
}

/**
 * Handle system event notification
 */
function handleSystemEventNotification(data) {
    console.log('System event:', data);
    
    // Show toast for important events
    if (data.data.status === 'error' || data.data.status === 'unhealthy') {
        if (window.Utils && Utils.showToast) {
            Utils.showToast(`System alert: ${data.data.message}`, 'warning');
        }
    }
}

/**
 * Handle connection status
 */
function handleConnectionStatus(data) {
    console.log('Connection status:', data.status);
    
    if (data.status === 'connected') {
        console.log('WebSocket connected successfully');
    } else if (data.status === 'disconnected') {
        console.log('WebSocket disconnected');
    }
}

/**
 * Handle error notification
 */
function handleErrorNotification(data) {
    console.error('WebSocket error:', data.message);
    
    if (window.Utils && Utils.showToast) {
        Utils.showToast(data.message, 'error');
    }
}

// Export for global access
window.WebSocketClient = WebSocketClient;
window.initWebSocket = initWebSocket;
window.wsClient = wsClient;
