// Optimized training API with real-time progress

class OptimizedTrainingAPI {
    constructor() {
        this.trainingEventSource = null;
        this.currentModelId = null;
        this.epochHistory = [];
    }

    async startTraining() {
        // Get selected dictionary and model
        if (!selectedDictionaryId || !selectedModel) {
            alert('Please select both a dictionary and a model type.');
            return;
        }

        const form = document.getElementById('trainingForm');
        if (!form) {
            console.error("Training form not found!");
            return;
        }

        // Gather form data
        const formData = new FormData(form);
        const jsonData = {
            dictionary_id: selectedDictionaryId,
            model_type: selectedModel,
            model_name: formData.get('model_name') || `${selectedModel}_model`,
            use_augmented: formData.has('use_augmented'),
            params: {}
        };

        // Add model-specific parameters
        formData.forEach((value, key) => {
            if (key !== 'dict_name' && key !== 'model_name' && key !== 'use_augmented') {
                if (value !== '' && !isNaN(value)) {
                    jsonData.params[key] = value.includes('.') ? parseFloat(value) : parseInt(value);
                } else if (value !== '') {
                    jsonData.params[key] = value;
                }
            }
        });

        console.log("Starting optimized training with:", jsonData);

        // Reset UI
        this.resetTrainingUI();
        this.showTrainingStatus(true);
        this.updateStatus('Initializing training...', 2);

        try {
            // Start training with optimized endpoint
            const response = await fetch('/api/ml/train/model/optimized', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(jsonData),
                credentials: 'same-origin'
            });

            const result = await response.json();
            
            // Check for error status
            if (!result.success || result.status === 'error') {
                throw new Error(result.error || 'Failed to start training');
            }

            // Get model ID from result
            this.currentModelId = result.id || result.model_id || (result.model && result.model.id);
            console.log("Training started with model ID:", this.currentModelId);
            
            if (!this.currentModelId) {
                throw new Error('No model ID received from server');
            }

            // Start real-time progress monitoring
            this.startProgressStream(this.currentModelId);

        } catch (error) {
            console.error('Error starting training:', error);
            this.handleTrainingError(error.message);
        }
    }

    startProgressStream(modelId) {
        // Skip SSE entirely - it doesn't work with Flask-Login authentication
        // Go straight to polling which works with standard fetch API
        console.log('Using polling for progress updates (SSE disabled due to auth issues)');
        this.fallbackToPolling(modelId);
    }

    handleProgressUpdate(data) {
        console.log('Progress update received:', data);
        
        switch (data.type) {
            case 'progress':
                this.updateTrainingProgress(data);
                break;
            case 'done':
                this.handleTrainingComplete(data);
                break;
            case 'error':
                this.handleTrainingError(data.message);
                break;
            case 'timeout':
                this.handleTrainingTimeout();
                break;
        }
    }

    updateTrainingProgress(data) {
        console.log('Progress update received:', data);  // Debug log
        const progress = data.progress || 0;
        const message = data.message || 'Processing...';
        
        // Update progress bar
        this.updateStatus(message, progress);

        // Update stage-specific UI
        if (data.stage === 'loading_features') {
            this.updateStep('Data Preparation', true, `Loading ${data.processed || 0}/${data.total || 0} features`);
        } else if (data.stage === 'training') {
            // Check for epoch information
            if (data.epoch !== undefined) {
                const totalEpochs = data.total_epochs || data.total || 100;
                this.updateEpochProgress(data.epoch, totalEpochs);
                
                // Always add epoch to table when we have an epoch number
                if (data.metrics) {
                    this.addEpochToTable(data.epoch, data.metrics);
                }
            }
            
            // Also check if we have batch epoch data
            if (data.all_epochs && Array.isArray(data.all_epochs) && data.all_epochs.length > 0) {
                console.log(`Processing ${data.all_epochs.length} epochs from history`);
                // Add any epochs we haven't seen yet
                data.all_epochs.forEach(epochData => {
                    if (epochData.metrics) {
                        this.addEpochToTable(epochData.epoch, epochData.metrics);
                    }
                });
            }
            
            this.updateStep('Model Training', true, message);
        } else if (data.stage === 'saving') {
            this.updateStep('Saving Model', true, 'Saving trained model to disk');
        }

        // Store metrics if available
        if (data.metrics) {
            this.displayMetrics(data.metrics);
        }
    }

    updateEpochProgress(currentEpoch, totalEpochs) {
        // Update epoch table dynamically
        const epochTable = document.getElementById('epochResultsTable');
        if (epochTable) {
            epochTable.style.display = 'block';
            
            // Add epoch data to history
            this.epochHistory.push({
                epoch: currentEpoch,
                timestamp: new Date().toISOString()
            });

            // Update waiting message
            const waitingMsg = epochTable.parentElement?.querySelector('.text-muted');
            if (waitingMsg && waitingMsg.textContent.includes('Waiting')) {
                waitingMsg.style.display = 'none';
            }
        }

        // Update main status
        const statusEl = document.getElementById('statusMessage');
        if (statusEl) {
            statusEl.innerHTML = `Training ${selectedModel?.toUpperCase() || 'Model'} (Epoch ${currentEpoch}/${totalEpochs})`;
        }
    }

    addEpochToTable(epochNum, metrics) {
        const epochTable = document.getElementById('epochResultsTable');
        if (!epochTable) return;

        const tbody = epochTable.querySelector('tbody');
        if (!tbody) return;

        // Check if epoch already exists
        const existingRow = tbody.querySelector(`tr[data-epoch="${epochNum}"]`);
        if (existingRow) {
            // Skip if already exists - don't update
            return;
        }
        
        // Add new row
        const row = document.createElement('tr');
        row.setAttribute('data-epoch', epochNum);
        row.innerHTML = `
            <td>${epochNum}</td>
            <td>${metrics.accuracy ? metrics.accuracy.toFixed(4) : '-'}</td>
            <td>${metrics.loss ? metrics.loss.toFixed(4) : '-'}</td>
            <td>${metrics.val_accuracy ? metrics.val_accuracy.toFixed(4) : '-'}</td>
            <td>${metrics.val_loss ? metrics.val_loss.toFixed(4) : '-'}</td>
            <td>${metrics.improved ? '✓' : ''}</td>
        `;
        tbody.appendChild(row);
        
        // Make table visible
        epochTable.style.display = 'block';
        
        // Scroll to bottom
        const scrollContainer = tbody.closest('.table-responsive') || tbody.parentElement;
        if (scrollContainer) {
            scrollContainer.scrollTop = scrollContainer.scrollHeight;
        }
    }

    async fallbackToPolling(modelId) {
        // Fallback to polling if SSE fails
        console.log('Falling back to polling for progress updates');
        
        const pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`/api/ml/train/progress/${modelId}`, {
                    credentials: 'same-origin'
                });
                const data = await response.json();
                
                if (data.success) {
                    this.updateTrainingProgress(data.progress);
                    
                    if (data.progress.status === 'complete' || data.progress.status === 'failed') {
                        clearInterval(pollInterval);
                        this.handleTrainingComplete({
                            status: data.progress.status,
                            metrics: data.progress.metrics
                        });
                    }
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 500); // Poll every 0.5 seconds for more frequent updates

        // Store interval ID for cleanup
        this.pollingInterval = pollInterval;
    }

    handleTrainingComplete(data) {
        console.log('Training complete:', data);
        
        // Close event source
        if (this.trainingEventSource) {
            this.trainingEventSource.close();
            this.trainingEventSource = null;
        }

        // Clear polling if active
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }

        // Update UI
        const isSuccess = data.status === 'complete';
        this.updateStatus(
            isSuccess ? 'Training complete!' : 'Training finished with errors',
            100
        );

        // Update progress bar color
        const progressBar = document.getElementById('trainingProgress');
        if (progressBar) {
            progressBar.classList.remove('mui-progress-bar-animated', 'mui-progress-bar-striped');
            progressBar.classList.add(isSuccess ? 'bg-success' : 'bg-danger');
        }

        // Fetch and display final results
        if (this.currentModelId) {
            this.fetchFinalResults(this.currentModelId);
        }

        // Re-enable form
        this.enableTrainingForm();

        // Show completion message
        this.showCompletionMessage(isSuccess);
    }

    handleTrainingError(message) {
        console.error('Training error:', message);
        
        // Update UI
        this.updateStatus(`Error: ${message}`, 0);
        
        // Update progress bar
        const progressBar = document.getElementById('trainingProgress');
        if (progressBar) {
            progressBar.classList.remove('mui-progress-bar-animated', 'mui-progress-bar-striped');
            progressBar.classList.add('bg-danger');
        }

        // Show error details
        const errorContainer = document.getElementById('errorContainer');
        if (errorContainer) {
            errorContainer.style.display = 'block';
            const errorDetails = document.getElementById('errorDetails');
            if (errorDetails) {
                errorDetails.innerHTML = `<div class="alert alert-danger">${message}</div>`;
            }
        }

        // Re-enable form
        this.enableTrainingForm();
    }

    handleTrainingTimeout() {
        this.handleTrainingError('Training timeout - process took too long');
    }

    async fetchFinalResults(modelId) {
        try {
            const response = await fetch(`/api/ml/train/results/${modelId}`);
            const data = await response.json();
            
            if (data) {
                this.displayFinalResults(data);
            }
        } catch (error) {
            console.error('Error fetching final results:', error);
        }
    }

    displayFinalResults(modelData) {
        // Display metrics
        if (modelData.metrics) {
            this.displayMetrics(modelData.metrics);
        }

        // Display training history
        if (modelData.metadata?.training_history) {
            this.displayEpochTable(modelData.metadata.training_history);
        }

        // Show model results container
        const resultsContainer = document.getElementById('modelResultsContainer');
        if (resultsContainer) {
            resultsContainer.style.display = 'block';
        }
    }

    displayMetrics(metrics) {
        const resultsDiv = document.getElementById('modelResults');
        if (!resultsDiv) return;

        resultsDiv.innerHTML = `
            <div class="metrics-grid">
                <div class="metric-card">
                    <h4>Accuracy</h4>
                    <p class="metric-value">${(metrics.accuracy * 100).toFixed(2)}%</p>
                </div>
                <div class="metric-card">
                    <h4>Precision</h4>
                    <p class="metric-value">${(metrics.precision * 100).toFixed(2)}%</p>
                </div>
                <div class="metric-card">
                    <h4>Recall</h4>
                    <p class="metric-value">${(metrics.recall * 100).toFixed(2)}%</p>
                </div>
                <div class="metric-card">
                    <h4>F1 Score</h4>
                    <p class="metric-value">${(metrics.f1_score * 100).toFixed(2)}%</p>
                </div>
            </div>
        `;
    }

    displayEpochTable(history) {
        // Implementation from original displayEpochTable function
        const epochTable = document.getElementById('epochResultsTable');
        if (!epochTable || !history || history.length === 0) return;

        epochTable.style.display = 'block';
        // ... rest of epoch table display logic
    }

    resetTrainingUI() {
        // Clear previous results
        const elements = [
            'trainingStepsList',
            'modelResults',
            'errorDetails',
            'suggestionsList',
            'logMessages'
        ];

        elements.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '';
        });

        // Hide containers
        const containers = [
            'modelResultsContainer',
            'epochResultsTable',
            'trainingDataSummary',
            'errorContainer'
        ];

        containers.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.style.display = 'none';
        });

        // Reset epoch history
        this.epochHistory = [];
    }

    showTrainingStatus(show) {
        const statusDiv = document.getElementById('trainingStatus');
        if (statusDiv) {
            statusDiv.style.display = show ? 'block' : 'none';
            if (show) {
                statusDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }

    updateStatus(message, progress) {
        const statusMessage = document.getElementById('statusMessage');
        const progressBar = document.getElementById('trainingProgress');

        if (statusMessage) {
            statusMessage.textContent = message;
        }

        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress);
            
            // Add animation for active training
            if (progress > 0 && progress < 100) {
                progressBar.classList.add('mui-progress-bar-animated', 'mui-progress-bar-striped');
            }
        }
    }

    updateStep(stepName, isComplete, details) {
        // Add or update training step in the UI
        const stepsList = document.getElementById('trainingStepsList');
        if (!stepsList) return;

        let stepItem = stepsList.querySelector(`[data-step="${stepName}"]`);
        if (!stepItem) {
            stepItem = document.createElement('div');
            stepItem.className = 'list-group-item';
            stepItem.dataset.step = stepName;
            stepsList.appendChild(stepItem);
        }

        const icon = isComplete ? '✓' : '⟳';
        const className = isComplete ? 'text-success' : 'text-info';
        
        stepItem.innerHTML = `
            <span class="${className}">${icon}</span>
            <strong>${stepName}</strong>
            ${details ? `<small class="text-muted ml-2">${details}</small>` : ''}
        `;
    }

    enableTrainingForm() {
        // Re-enable form elements
        document.getElementById('dictionarySelect').disabled = false;
        document.querySelectorAll('.mui-model-card button').forEach(btn => btn.disabled = false);
        document.getElementById('startTrainingBtn').disabled = false;
    }

    showCompletionMessage(success) {
        const logDiv = document.getElementById('trainingLog');
        if (!logDiv) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `alert ${success ? 'alert-success' : 'alert-warning'} mt-3`;
        messageDiv.innerHTML = `
            <span class="material-icons me-2">${success ? 'check_circle' : 'warning'}</span>
            ${success ? 'Training completed successfully!' : 'Training finished with errors'}
        `;
        logDiv.appendChild(messageDiv);

        // Add restart button
        const restartBtn = document.createElement('button');
        restartBtn.className = 'mui-button mui-button-contained mt-3';
        restartBtn.innerHTML = '<span class="material-icons me-1">refresh</span>Train Another Model';
        restartBtn.onclick = () => window.location.reload();
        logDiv.appendChild(restartBtn);
    }
}

// Initialize optimized training API
const optimizedTrainingAPI = new OptimizedTrainingAPI();

// Override the global startTraining function
function startTraining() {
    optimizedTrainingAPI.startTraining();
}