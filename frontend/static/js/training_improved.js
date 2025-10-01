// Improved training page with real-time updates and better performance

class TrainingManager {
    constructor() {
        this.selectedDictionary = null;
        this.selectedDictionaryId = null;
        this.featureCheckInterval = null;
        this.extractionEventSource = null;
        this.isExtracting = false;
    }

    init() {
        this.setupEventListeners();
        this.checkInitialDictionary();
    }

    setupEventListeners() {
        const dictSelect = document.getElementById('dictionarySelect');
        if (dictSelect) {
            dictSelect.addEventListener('change', (e) => this.handleDictionaryChange(e));
        }

        // Extract features button (if we add one)
        const extractBtn = document.getElementById('extractFeaturesBtn');
        if (extractBtn) {
            extractBtn.addEventListener('click', () => this.startFeatureExtraction());
        }
    }

    async handleDictionaryChange(event) {
        const select = event.target;
        const selectedOption = select.options[select.selectedIndex];
        
        if (!selectedOption || !selectedOption.value) {
            this.clearFeatureStatus();
            return;
        }

        this.selectedDictionary = selectedOption.value;
        this.selectedDictionaryId = selectedOption.getAttribute('data-id');

        // Show loading state
        this.showFeatureStatusLoading();

        // Check feature status via AJAX (no page reload!)
        await this.checkFeatureStatus();
    }

    showFeatureStatusLoading() {
        const statusSection = document.querySelector('.feature-status-section');
        if (!statusSection) {
            // Create status section if it doesn't exist
            const dictInfo = document.getElementById('dictionaryInfo');
            if (dictInfo) {
                const statusHTML = `
                    <div class="feature-status-section" style="margin-top: 24px; border-top: 1px solid rgba(0,0,0,0.1); padding-top: 24px;">
                        <h3 style="font-size: 1rem; font-weight: 500; margin-bottom: 16px;">Feature Extraction Status:</h3>
                        <div class="feature-status-content">
                            <div class="d-flex align-items-center">
                                <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                                <span>Checking feature status...</span>
                            </div>
                        </div>
                    </div>
                `;
                dictInfo.insertAdjacentHTML('afterend', statusHTML);
            }
        } else {
            const content = statusSection.querySelector('.feature-status-content');
            if (content) {
                content.innerHTML = `
                    <div class="d-flex align-items-center">
                        <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                        <span>Checking feature status...</span>
                    </div>
                `;
            }
        }
    }

    async checkFeatureStatus() {
        if (!this.selectedDictionaryId) return;

        try {
            const response = await fetch(`/api/features/status/${this.selectedDictionaryId}`, {
                method: 'GET',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to check feature status');
            }

            const data = await response.json();
            if (data.success) {
                this.displayFeatureStatus(data.status);
            } else {
                this.showFeatureStatusError(data.error || 'Unknown error');
            }
        } catch (error) {
            console.error('Error checking feature status:', error);
            this.showFeatureStatusError(error.message);
        }
    }

    displayFeatureStatus(status) {
        const statusSection = document.querySelector('.feature-status-section');
        if (!statusSection) return;

        const content = statusSection.querySelector('.feature-status-content');
        if (!content) return;

        const hasAllFeatures = status.files_missing_features === 0;
        const alertClass = hasAllFeatures ? 'mui-alert-success' : 'mui-alert-warning';
        
        content.innerHTML = `
            <div class="mui-alert ${alertClass}">
                <div class="mui-feature-status">
                    <div class="mui-feature-item">
                        <strong>Total Files:</strong> ${status.total_files}
                    </div>
                    <div class="mui-feature-item">
                        <strong>With Features:</strong> ${status.files_with_features}
                    </div>
                    <div class="mui-feature-item">
                        <strong>Missing Features:</strong> ${status.files_missing_features}
                    </div>
                    ${status.percentage !== undefined ? `
                    <div class="mui-feature-item">
                        <strong>Progress:</strong> ${status.percentage}%
                    </div>` : ''}
                </div>
            </div>
        `;

        // Add extraction button if features are missing
        if (status.files_missing_features > 0 && !this.isExtracting) {
            content.innerHTML += `
                <div style="margin-top: 16px;">
                    <div class="mui-alert mui-alert-info" style="display: flex; align-items: center; justify-content: space-between;">
                        <p style="margin: 0;">
                            <span class="material-icons" style="vertical-align: middle; margin-right: 8px;">warning</span>
                            ${status.files_missing_features} files need feature extraction before training.
                        </p>
                        <button id="extractMissingBtn" class="mui-button mui-button-contained" onclick="trainingManager.startFeatureExtraction()">
                            <span class="material-icons" style="font-size: 16px; margin-right: 4px;">build</span>
                            Extract Features
                        </button>
                    </div>
                </div>
            `;
        } else if (hasAllFeatures) {
            content.innerHTML += `
                <div class="mui-alert mui-alert-success" style="margin-top: 16px;">
                    <p style="margin: 0;">
                        <span class="material-icons" style="vertical-align: middle; margin-right: 8px;">check_circle</span>
                        All features extracted! Ready for training.
                    </p>
                </div>
            `;
            
            // Enable model selection
            this.enableModelSelection();
        }

        // If extraction is in progress, show progress
        if (this.isExtracting) {
            this.showExtractionProgress();
        }
    }

    async startFeatureExtraction() {
        console.log('[EXTRACT] startFeatureExtraction called');
        console.log('[EXTRACT] selectedDictionaryId:', this.selectedDictionaryId);
        console.log('[EXTRACT] isExtracting:', this.isExtracting);
        
        if (!this.selectedDictionaryId || this.isExtracting) {
            console.error('[EXTRACT] Aborting: selectedDictionaryId missing or already extracting');
            return;
        }

        this.isExtracting = true;

        try {
            // Show extraction progress UI immediately
            this.showExtractionProgress();
            this.updateExtractionProgress(0, 'Starting feature extraction...');

            console.log('[EXTRACT] Calling API:', `/api/features/trigger/${this.selectedDictionaryId}`);
            
            // Trigger extraction for all missing features in the dictionary
            const triggerResponse = await fetch(`/api/features/trigger/${this.selectedDictionaryId}`, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            console.log('[EXTRACT] API response status:', triggerResponse.status);

            const triggerData = await triggerResponse.json();
            console.log('[EXTRACT] API response data:', triggerData);
            console.log('[EXTRACT] count:', triggerData.count, 'progress_id:', triggerData.progress_id, 'message:', triggerData.message);
            
            if (!triggerData.success) {
                console.error('[EXTRACT] API returned error:', triggerData.error);
                throw new Error(triggerData.error || 'Failed to start extraction');
            }

            if (triggerData.count === 0) {
                this.showMessage('All recordings already have features!', 'success');
                this.isExtracting = false;
                this.checkFeatureStatus(); // Refresh status
                return;
            }

            // Start monitoring progress via SSE
            if (triggerData.progress_id) {
                this.startProgressMonitoring(triggerData.progress_id, triggerData.count);
            } else {
                // Fallback if no progress_id
                this.showMessage(`Started extraction for ${triggerData.count} recordings`, 'info');
                this.pollFeatureStatus();
            }

        } catch (error) {
            console.error('Error starting extraction:', error);
            this.showMessage(`Error: ${error.message}`, 'error');
            this.isExtracting = false;
        }
    }

    startProgressMonitoring(progressId, totalCount) {
        // Close any existing connection
        if (this.extractionEventSource) {
            this.extractionEventSource.close();
        }

        // Create SSE connection to monitor progress
        this.extractionEventSource = new EventSource(`/api/features/progress/${progressId}`, {
            withCredentials: true
        });

        // Handle SSE events
        this.extractionEventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleProgressUpdate(data, totalCount);
            } catch (error) {
                console.error('Error parsing SSE data:', error);
            }
        };

        this.extractionEventSource.onerror = (error) => {
            console.error('SSE error:', error);
            this.extractionEventSource.close();
            this.handleExtractionError('Connection lost. Extraction may still be running in background.');
        };
    }

    pollFeatureStatus() {
        // Fallback polling method if SSE is not available
        const pollInterval = setInterval(async () => {
            if (!this.isExtracting) {
                clearInterval(pollInterval);
                return;
            }

            try {
                await this.checkFeatureStatus();
                
                // Check if extraction is complete
                const statusSection = document.querySelector('.feature-status-section');
                if (statusSection) {
                    const missingCount = statusSection.querySelector('.mui-feature-item:nth-child(3) strong')?.nextSibling?.textContent?.trim();
                    if (missingCount === '0') {
                        clearInterval(pollInterval);
                        this.handleExtractionComplete({ processed: 'all', failed: 0 });
                    }
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 3000); // Poll every 3 seconds
    }

    handleProgressUpdate(data, totalCount) {
        const progressDiv = document.getElementById('extractionProgress');
        if (!progressDiv) return;

        switch (data.type) {
            case 'progress':
                const percentage = data.percentage || 0;
                const message = data.current_file 
                    ? `Processing ${data.current_file} (${data.processed}/${data.total})`
                    : `Processed ${data.processed}/${data.total} recordings`;
                this.updateExtractionProgress(percentage, message);
                break;
            
            case 'complete':
                this.handleExtractionComplete({
                    processed: data.processed || totalCount,
                    failed: data.failed || 0,
                    total: totalCount
                });
                break;
            
            case 'error':
                this.handleExtractionError(data.message || 'Extraction failed');
                break;

            case 'timeout':
                this.handleExtractionError('Progress monitoring timeout. Extraction may still be running.');
                break;
        }
    }

    updateExtractionProgress(percentage, message) {
        const progressDiv = document.getElementById('extractionProgress');
        if (!progressDiv) {
            this.showExtractionProgress();
            return;
        }

        const progressBar = progressDiv.querySelector('.progress-bar');
        const progressText = progressDiv.querySelector('.progress-text');
        
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            progressBar.setAttribute('aria-valuenow', percentage);
        }
        
        if (progressText) {
            progressText.textContent = message;
        }
    }

    showExtractionProgress() {
        const statusContent = document.querySelector('.feature-status-content');
        if (!statusContent) return;

        const progressHTML = `
            <div id="extractionProgress" class="extraction-progress mt-3">
                <div class="progress-text mb-2">Initializing extraction...</div>
                <div class="progress">
                    <div class="progress-bar progress-bar-striped progress-bar-animated"
                         role="progressbar" style="width: 0%"
                         aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                <button class="btn btn-sm btn-outline-danger mt-2" onclick="trainingManager.cancelExtraction()">
                    Cancel
                </button>
            </div>
        `;

        // Find or create progress container
        let progressDiv = document.getElementById('extractionProgress');
        if (!progressDiv) {
            statusContent.insertAdjacentHTML('beforeend', progressHTML);
        }
    }

    updateRecordingStatus(recordingId, success) {
        // This would update the UI lists in real-time
        // For now, we'll just log it
        console.log(`Recording ${recordingId}: ${success ? 'extracted' : 'failed'}`);
    }

    handleExtractionComplete(data) {
        this.isExtracting = false;
        
        if (this.extractionEventSource) {
            this.extractionEventSource.close();
            this.extractionEventSource = null;
        }

        const message = `Extraction complete! Processed: ${data.processed}, Failed: ${data.failed}`;
        this.showMessage(message, data.failed > 0 ? 'warning' : 'success');

        // Refresh feature status
        setTimeout(() => {
            this.checkFeatureStatus();
        }, 1000);
    }

    handleExtractionError(message) {
        this.isExtracting = false;
        
        if (this.extractionEventSource) {
            this.extractionEventSource.close();
            this.extractionEventSource = null;
        }

        this.showMessage(`Extraction error: ${message}`, 'error');
        
        // Try to refresh status
        setTimeout(() => {
            this.checkFeatureStatus();
        }, 2000);
    }

    cancelExtraction() {
        if (this.extractionEventSource) {
            this.extractionEventSource.close();
            this.extractionEventSource = null;
        }
        this.isExtracting = false;
        this.showMessage('Extraction cancelled', 'info');
        this.checkFeatureStatus();
    }

    showFeatureStatusError(error) {
        const statusSection = document.querySelector('.feature-status-section');
        if (!statusSection) return;

        const content = statusSection.querySelector('.feature-status-content');
        if (content) {
            content.innerHTML = `
                <div class="mui-alert mui-alert-danger">
                    <span class="material-icons me-2">error</span>
                    Error checking feature status: ${error}
                </div>
            `;
        }
    }

    clearFeatureStatus() {
        const statusSection = document.querySelector('.feature-status-section');
        if (statusSection) {
            statusSection.remove();
        }
    }

    enableModelSelection() {
        document.querySelectorAll('.mui-model-card button').forEach(btn => {
            btn.disabled = false;
        });
    }

    showMessage(message, type = 'info') {
        // Create or update a message area
        let messageDiv = document.getElementById('trainingMessage');
        if (!messageDiv) {
            const container = document.querySelector('.mui-container');
            if (container) {
                messageDiv = document.createElement('div');
                messageDiv.id = 'trainingMessage';
                container.insertBefore(messageDiv, container.firstChild);
            }
        }

        if (messageDiv) {
            const alertClass = {
                'success': 'alert-success',
                'error': 'alert-danger',
                'warning': 'alert-warning',
                'info': 'alert-info'
            }[type] || 'alert-info';

            messageDiv.innerHTML = `
                <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;

            // Auto-hide after 5 seconds
            setTimeout(() => {
                const alert = messageDiv.querySelector('.alert');
                if (alert) {
                    alert.classList.remove('show');
                    setTimeout(() => messageDiv.innerHTML = '', 150);
                }
            }, 5000);
        }
    }

    checkInitialDictionary() {
        const dictSelect = document.getElementById('dictionarySelect');
        if (dictSelect && dictSelect.value) {
            // Trigger change event to load feature status
            dictSelect.dispatchEvent(new Event('change'));
        }
    }
}

// Initialize on page load
const trainingManager = new TrainingManager();
document.addEventListener('DOMContentLoaded', () => {
    trainingManager.init();
});