// System Configuration Module

const SystemConfig = {
    currentConfig: null,
    currentFile: null,
    isDirty: false,
    autoSaveTimer: null,
    autoSaveDelay: 1000, // 1 second after last change
    
    // Initialize system config page
    init() {
        this.loadConfigList();
        this.setupAutoSave();
    },
    
    // Load list of configuration files
    async loadConfigList() {
        const configFiles = [
            { name: 'llm_config.yaml', title: 'LLM Configuration', description: 'AI model settings and API keys' },
            { name: 'fetch_sources.yaml', title: 'Data Sources', description: 'Market data and news sources' },
            { name: 'ea_config.yaml', title: 'EA Configuration', description: 'Expert Advisor settings' },
            { name: 'factor_config.yaml', title: 'Factor Configuration', description: 'Quantitative factors' },
            { name: 'push_config.yaml', title: 'Push Notifications', description: 'Alert and notification settings' },
            { name: 'security_config.yaml', title: 'Security', description: 'Security and authentication' },
            { name: 'alerting_config.yaml', title: 'Alerting', description: 'Alert rules and thresholds' }
        ];
        
        const container = document.getElementById('configList');
        if (!container) return;
        
        container.innerHTML = configFiles.map(file => `
            <div class="config-item" onclick="SystemConfig.loadConfig('${file.name}')">
                <div class="config-item-header">
                    <h3>${file.title}</h3>
                    <span class="config-badge">YAML</span>
                </div>
                <p class="config-item-desc">${file.description}</p>
                <div class="config-item-footer">
                    <span class="config-file-name">${file.name}</span>
                </div>
            </div>
        `).join('');
    },
    
    // Load specific configuration file
    async loadConfig(filename) {
        try {
            Utils.showToast(Utils.t('system.loadingConfig') || 'Loading configuration...', 'info', 1000);
            
            const response = await API.system.getConfig(filename);
            this.currentConfig = response.content || response;
            this.currentFile = filename;
            this.isDirty = false;
            
            this.renderEditor();
            Utils.showToast(Utils.t('system.configLoaded') || 'Configuration loaded', 'success');
        } catch (error) {
            console.error('Failed to load config:', error);
            Utils.showToast(error.message || 'Failed to load configuration', 'error');
        }
    },
    
    // Render configuration editor
    renderEditor() {
        const editorContainer = document.getElementById('configEditor');
        if (!editorContainer) return;
        
        editorContainer.innerHTML = `
            <div class="editor-header">
                <div class="editor-title">
                    <h2>${this.currentFile}</h2>
                    <span class="save-status" id="saveStatus">
                        ${this.isDirty ? 'Unsaved changes' : 'Saved'}
                    </span>
                </div>
                <div class="editor-actions">
                    <button class="btn btn-secondary" onclick="SystemConfig.reloadConfig()">
                        🔄 ${Utils.t('common.reload') || 'Reload'}
                    </button>
                    <button class="btn btn-primary" onclick="SystemConfig.saveConfig()" ${!this.isDirty ? 'disabled' : ''}>
                        💾 ${Utils.t('common.save') || 'Save'}
                    </button>
                </div>
            </div>
            
            <div class="editor-content">
                <textarea 
                    id="configTextarea" 
                    class="config-textarea"
                    spellcheck="false"
                    oninput="SystemConfig.onConfigChange()"
                >${this.currentConfig}</textarea>
            </div>
            
            <div class="editor-footer">
                <div class="editor-info">
                    <span>📝 YAML format</span>
                    <span>•</span>
                    <span>Auto-save enabled</span>
                    <span>•</span>
                    <span id="charCount">${this.currentConfig.length} characters</span>
                </div>
            </div>
        `;
    },
    
    // Handle configuration changes
    onConfigChange() {
        const textarea = document.getElementById('configTextarea');
        if (!textarea) return;
        
        this.currentConfig = textarea.value;
        this.isDirty = true;
        
        // Update save status
        this.updateSaveStatus('Unsaved changes', 'warning');
        
        // Update character count
        const charCount = document.getElementById('charCount');
        if (charCount) {
            charCount.textContent = `${this.currentConfig.length} characters`;
        }
        
        // Enable save button
        const saveBtn = document.querySelector('.editor-actions .btn-primary');
        if (saveBtn) {
            saveBtn.disabled = false;
        }
        
        // Trigger auto-save
        this.scheduleAutoSave();
    },
    
    // Schedule auto-save
    scheduleAutoSave() {
        // Clear existing timer
        if (this.autoSaveTimer) {
            clearTimeout(this.autoSaveTimer);
        }
        
        // Show auto-save pending status
        this.updateSaveStatus('Auto-saving...', 'info');
        
        // Schedule new auto-save
        this.autoSaveTimer = setTimeout(() => {
            this.autoSave();
        }, this.autoSaveDelay);
    },
    
    // Auto-save configuration
    async autoSave() {
        if (!this.isDirty) return;
        
        try {
            await API.system.updateConfig(this.currentFile, this.currentConfig);
            this.isDirty = false;
            
            // Update save status
            this.updateSaveStatus('Auto-saved', 'success');
            
            // Disable save button
            const saveBtn = document.querySelector('.editor-actions .btn-primary');
            if (saveBtn) {
                saveBtn.disabled = true;
            }
            
            // Show toast notification
            Utils.showToast(
                Utils.t('system.autoSaved') || 'Configuration auto-saved',
                'success',
                2000
            );
            
            // Reset status after 3 seconds
            setTimeout(() => {
                if (!this.isDirty) {
                    this.updateSaveStatus('Saved', 'success');
                }
            }, 3000);
            
        } catch (error) {
            console.error('Auto-save failed:', error);
            this.updateSaveStatus('Auto-save failed', 'error');
            Utils.showToast(
                error.message || 'Auto-save failed',
                'error'
            );
        }
    },
    
    // Manual save configuration
    async saveConfig() {
        if (!this.isDirty) return;
        
        try {
            this.updateSaveStatus('Saving...', 'info');
            
            await API.system.updateConfig(this.currentFile, this.currentConfig);
            this.isDirty = false;
            
            // Update save status
            this.updateSaveStatus('Saved', 'success');
            
            // Disable save button
            const saveBtn = document.querySelector('.editor-actions .btn-primary');
            if (saveBtn) {
                saveBtn.disabled = true;
            }
            
            // Show success toast
            Utils.showToast(
                Utils.t('system.configSaved') || 'Configuration saved successfully',
                'success'
            );
            
        } catch (error) {
            console.error('Save failed:', error);
            this.updateSaveStatus('Save failed', 'error');
            Utils.showToast(
                error.message || 'Failed to save configuration',
                'error'
            );
        }
    },
    
    // Reload configuration
    async reloadConfig() {
        if (this.isDirty) {
            const confirmed = confirm(
                Utils.t('system.confirmReload') || 
                'You have unsaved changes. Reload anyway?'
            );
            if (!confirmed) return;
        }
        
        await this.loadConfig(this.currentFile);
    },
    
    // Update save status indicator
    updateSaveStatus(text, type) {
        const statusEl = document.getElementById('saveStatus');
        if (!statusEl) return;
        
        // Add animation class
        statusEl.classList.add('save-status-animate');
        
        statusEl.textContent = text;
        statusEl.className = `save-status save-status-${type} save-status-animate`;
        
        // Remove animation class after animation completes
        setTimeout(() => {
            statusEl.classList.remove('save-status-animate');
        }, 500);
    },
    
    // Setup auto-save
    setupAutoSave() {
        // Warn user before leaving with unsaved changes
        window.addEventListener('beforeunload', (e) => {
            if (this.isDirty) {
                e.preventDefault();
                e.returnValue = '';
                return '';
            }
        });
    },
    
    // Render system configuration page
    render() {
        return `
            <div class="system-page">
                <div class="system-header">
                    <div class="system-title">
                        <button class="btn-back" onclick="Router.navigate('/home')">← ${Utils.t('common.back') || 'Back'}</button>
                        <h1>🔧 ${Utils.t('modules.system.title') || 'System Configuration'}</h1>
                    </div>
                    <div class="system-actions">
                        <button class="btn-icon" onclick="Lang.toggle()" title="${Utils.t('common.language')}">🌐</button>
                        <button class="btn-icon" onclick="Theme.toggle()" title="${Utils.t('common.theme')}">🌓</button>
                    </div>
                </div>
                
                <div class="system-content">
                    <div class="config-sidebar">
                        <h2>${Utils.t('system.configFiles') || 'Configuration Files'}</h2>
                        <div id="configList" class="config-list">
                            <!-- Config list will be loaded here -->
                        </div>
                    </div>
                    
                    <div class="config-main">
                        <div id="configEditor" class="config-editor-container">
                            <div class="config-placeholder">
                                <div class="placeholder-icon">📄</div>
                                <h3>${Utils.t('system.selectConfig') || 'Select a configuration file'}</h3>
                                <p>${Utils.t('system.selectConfigDesc') || 'Choose a file from the left to edit'}</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
};

// Export for global access
window.SystemConfig = SystemConfig;
