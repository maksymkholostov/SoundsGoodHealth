// --- Globals (Initialized in training_init_ui.js) ---
// let selectedDictionaryId = null;
// let selectedModel = null;
let trainingInterval = null;
let lastCompletedModelId = null; // Added global variable
let lastTrainingParams = null; // Store training parameters for use in status checking

// --- API Interaction and State Management Functions ---

function startTraining() {
    // Use global selectedDictionaryId and selectedModel from training_init_ui.js
    if (!selectedDictionaryId || !selectedModel) {
        alert('Please select both a dictionary and a model type.');
        return;
    }

    const form = document.getElementById('trainingForm');
    if (!form) {
        console.error("Training form element not found!");
        alert('Error: Could not find training form element.');
        return;
    }

    const formData = new FormData(form);
    const jsonData = {};
    formData.forEach((value, key) => {
        if (key === 'max_depth' && value === '') {
             jsonData[key] = null;
        } else if (key === 'use_class_weights') {
            jsonData[key] = true; // Checkbox: 'on' if checked, absent otherwise. Assume true if present.
        } else if (!isNaN(value) && value !== '') {
             jsonData[key] = value.includes('.') ? parseFloat(value) : parseInt(value);
         } else if (value !== '') {
             jsonData[key] = value;
         }
        if (key === 'dict_name') return;
    });
     // Ensure checkbox is false if not present in formData
     if (!formData.has('use_class_weights')) {
         jsonData['use_class_weights'] = false;
     }

    // --- ADD the dictionary_id to the payload ---
    jsonData['dictionary_id'] = selectedDictionaryId;

    // Store training parameters globally for status checking
    lastTrainingParams = jsonData;

    console.log("Sending training request with data:", jsonData);

    // --- Reset UI (Calls functions in training_ui_render.js) ---
    const stepsList = document.getElementById('trainingStepsList');
    if (stepsList) stepsList.innerHTML = '';
    const modelResults = document.getElementById('modelResults');
    if (modelResults) modelResults.innerHTML = ''; // Clear previous results
    const errorContainer = document.getElementById('errorContainer');
    if (errorContainer) errorContainer.style.display = 'none'; // Hide errors
    const errorDetails = document.getElementById('errorDetails');
    if (errorDetails) errorDetails.innerHTML = '';
    const suggestionsList = document.getElementById('suggestionsList');
    if (suggestionsList) suggestionsList.innerHTML = '';
    const logMessagesEl = document.getElementById('logMessages');
    if (logMessagesEl) logMessagesEl.textContent = ''; // Clear logs

    // Hide sections that will be populated later
    const modelResultsContainer = document.getElementById('modelResultsContainer');
    if (modelResultsContainer) modelResultsContainer.style.display = 'none';
    const epochTable = document.getElementById('epochResultsTable');
    if (epochTable) epochTable.style.display = 'none';
    const dataSummary = document.getElementById('trainingDataSummary');
    if (dataSummary) dataSummary.style.display = 'none';
    const mfccDetails = document.getElementById('mfccNormalizationDetails');
    if (mfccDetails) mfccDetails.style.display = 'none';
    const errorsDetails = document.getElementById('processingErrorsDetails');
    if (errorsDetails) errorsDetails.style.display = 'none';

    // Remove completion message/button from previous runs
    const logDiv = document.getElementById('trainingLog');
     if (logDiv) {
         const existingAlert = logDiv.querySelector('.alert.mt-3.mb-3');
         if (existingAlert) existingAlert.remove();
         const existingRestartBtn = logDiv.querySelector('.mui-button.mt-3');
         if (existingRestartBtn && existingRestartBtn.textContent.includes('Train Another Model')) {
              existingRestartBtn.remove();
         }
     }

    // Show training status section and initial state
    const trainingStatus = document.getElementById('trainingStatus');
    const statusMessage = document.getElementById('statusMessage');
    const trainingProgress = document.getElementById('trainingProgress');

    if (trainingStatus && statusMessage && trainingProgress) {
        trainingStatus.style.display = 'block';
        statusMessage.textContent = 'Initializing...';
        trainingProgress.style.width = '2%';
        trainingProgress.classList.add('mui-progress-bar-animated', 'mui-progress-bar-striped');
        trainingProgress.classList.remove('bg-success', 'bg-danger'); // Reset color
        trainingProgress.setAttribute('aria-valuenow', 2);
        trainingStatus.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
         console.error("Required training status elements not found!");
         alert('Error: Could not find training status display elements.');
         return;
    }

    // Add initial training step (Uses function from training_ui_render.js)
    addTrainingStep('Training Initialization', false, 'Preparing to start the training process');

    // Disable form elements
    const dictionarySelectEl = document.getElementById('dictionarySelect');
    if (dictionarySelectEl) dictionarySelectEl.disabled = true;
    document.querySelectorAll('.mui-model-card button').forEach(btn => btn.disabled = true);
    const startTrainingBtnEl = document.getElementById('startTrainingBtn');
    if (startTrainingBtnEl) startTrainingBtnEl.disabled = true;

    // --- API Request ---
    fetch('/api/ml/train/model', { // Correct URL from previous step
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(jsonData) // jsonData now includes dictionary_id
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(errData => {
                // Store potential model ID even on error, if available (e.g., if it failed after creation)
                if (errData && errData.model_id) {
                     lastCompletedModelId = errData.model_id;
                }
                // Check if error is due to existing training
                if (errData.error && errData.error.includes('already has a model training')) {
                    // Extract model ID from error message if possible
                    const modelIdMatch = errData.error.match(/ID: ([a-zA-Z0-9_]+)\)/);
                    if (modelIdMatch) {
                        lastCompletedModelId = modelIdMatch[1];
                        console.log("Extracted existing model ID from error:", lastCompletedModelId);
                    }
                    alert('A model is already training. Please wait for it to complete before starting a new training.');
                }
                throw new Error(errData.error || `HTTP error! status: ${response.status}`);
            }).catch((err) => {
                 // If parsing errData fails or it has no error message
                 if (err && err.model_id) { // Check if the caught error itself has model_id
                     lastCompletedModelId = err.model_id;
                 }
                 throw new Error(err.message || `HTTP error! status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        // Check if the response contains an 'id' (model version ID) to indicate success
        if (data && data.id) {
            console.log("Training started successfully via API. Model ID:", data.id);
            lastCompletedModelId = data.id; // Store the model ID for final results fetch
            if (statusMessage) statusMessage.textContent = 'Training started...';
            if (trainingProgress) trainingProgress.style.width = '5%';
            // Update first step (Uses function from training_ui_render.js)
            const firstStep = document.querySelector('#trainingStepsList .list-group-item');
            if (firstStep) {
                updateTrainingStep(firstStep, true, 'Training environment ready, request sent.');
            }
            // Add next step (Uses function from training_ui_render.js)
            addTrainingStep('Data Preparation', false, 'Waiting for server to load and prepare dataset');
            // Start polling
            startStatusPolling();
        } else {
            // If no ID, assume error, potentially store model_id if present in error response
            if (data && data.model_id) {
                lastCompletedModelId = data.model_id;
            }
            throw new Error(data.error || 'Unknown error starting training (missing model ID).');
        }
    })
    .catch(error => {
        console.error('Error starting training process (may occur after initial request):', error);
        // If an error happens *after* the model ID was received, 
        // the checkTrainingStatus -> fetchFinalResults flow should handle UI updates.
        // We only need to handle the case where the initial start failed *before* we got an ID.
        if (!lastCompletedModelId) {
             alert('Error starting training: ' + error.message);
             // Reset UI fully if start failed without getting an ID
             const trainingStatus = document.getElementById('trainingStatus');
             if (trainingStatus) trainingStatus.style.display = 'none';
             const stepsListUI = document.getElementById('trainingStepsList');
             if (stepsListUI) stepsListUI.innerHTML = `<div class="alert alert-danger">Failed to start training: ${error.message}</div>`;
             // Re-enable form
             const dictionarySelectEl = document.getElementById('dictionarySelect');
             if (dictionarySelectEl) dictionarySelectEl.disabled = false;
             document.querySelectorAll('.mui-model-card button').forEach(btn => btn.disabled = false);
             const startTrainingBtnEl = document.getElementById('startTrainingBtn');
             if (startTrainingBtnEl) startTrainingBtnEl.disabled = false;
        } else {
            // If we had an ID, but an error occurred later in the chain, 
            // log it but assume the polling/final fetch will handle the UI.
            console.warn("Error occurred in startTraining chain after model ID was received. Relying on polling/final fetch for UI.");
        }
    });
}

function startStatusPolling() {
    // Use global trainingInterval from training_init_ui.js
    if (trainingInterval) {
        console.log("Clearing existing training interval before starting new one.");
        clearInterval(trainingInterval);
        trainingInterval = null;
    }
    console.log("Starting status polling (every 2 seconds)");
    // Initial check immediately, then poll
    checkTrainingStatus(); // Check now
    trainingInterval = setInterval(checkTrainingStatus, 2000); // Check every 2s
}


function checkTrainingStatus() {
    console.log("Checking training status...");
    const statusMessageEl = document.getElementById('statusMessage');
    const trainingProgressEl = document.getElementById('trainingProgress');
    const trainingStatusDiv = document.getElementById('trainingStatus');

    fetch('/api/ml/train/status') // Ensure API endpoint is correct
    .then(response => {
         if (!response.ok) throw new Error(`Status check failed: ${response.status}`);
         return response.json();
    })
    .then(data => {
        console.log("Training status response:", data);
        // --- MODIFIED CHECK --- 
        // Check if the response *contains* the expected keys, not just data.success
        if (typeof data.is_training !== 'boolean') {
            // Log the unexpected structure for debugging
            console.warn("Status check response missing 'is_training' boolean:", data);
            throw new Error("Status check returned unexpected data format.");
        }
        // --- END MODIFIED CHECK --- 

        if (data.is_training) {
            if (trainingStatusDiv && trainingStatusDiv.style.display === 'none') {
                 trainingStatusDiv.style.display = 'block'; // Ensure visible
                 if (!trainingInterval) startStatusPolling(); // Restart polling if needed
            }

            // --- Fetch detailed stats using model ID --- 
            // Try to get model ID from the status response if we don't have it
            if (!lastCompletedModelId && data.model_id) {
                lastCompletedModelId = data.model_id;
                console.log("Retrieved model ID from status response:", lastCompletedModelId);
            }
            
            if (lastCompletedModelId) { // Ensure we have the ID of the *current* job
                fetch(`/api/ml/train/stats/${lastCompletedModelId}`) 
                .then(response => {
                    if (!response.ok) throw new Error(`Stats fetch failed: ${response.status}`);
                    return response.json();
                 })
                .then(statsData => {
                    console.log("Live training stats response:", statsData);
                    // Check if data is valid and contains log lines
                    if (!statsData.success || !Array.isArray(statsData.log_lines)) {
                        // Don't throw an error, just log warning, maybe log file isn't ready yet
                        console.warn("Invalid stats data received or log_lines missing:", statsData);
                        return; // Skip UI update if data is bad
                    }

                    // Process the received log lines (list of epoch metric dicts)
                    const epochHistoryList = statsData.log_lines;

                    // Update UI based on the latest epoch data
                    if (epochHistoryList.length > 0) {
                        const latestEpoch = epochHistoryList[epochHistoryList.length - 1];
                        const totalEpochs = lastTrainingParams?.epochs || 30; // Get total epochs from training params if available
                        
                        // Update Progress Bar & Status Message
                        if (statusMessageEl && trainingProgressEl) {
                            const currentEpochNum = latestEpoch.epoch;
                            let statusText = `Training ${selectedModel?.toUpperCase() || 'Model'} (Epoch ${currentEpochNum}/${totalEpochs})`;
                            const progress = Math.min(95, Math.floor((currentEpochNum / totalEpochs) * 90) + 5);
                            statusMessageEl.innerHTML = statusText;
                            trainingProgressEl.style.width = `${progress}%`;
                            trainingProgressEl.setAttribute('aria-valuenow', progress);
                            // Ensure progress bar is animated
                             if (!trainingProgressEl.classList.contains('mui-progress-bar-animated')) {
                                 trainingProgressEl.classList.add('mui-progress-bar-animated', 'mui-progress-bar-striped');
                                 trainingProgressEl.classList.remove('bg-success', 'bg-danger');
                             }
                        }
                        
                        // Update Epoch Table (replace content with latest full history)
                        displayEpochTable(epochHistoryList);
                        
                        // TODO: Update other elements if needed (logs, steps, etc.)
                        // updateTrainingStepsFromStats(latestEpoch); // Adapt this if needed
                    }
                    
                })
                .catch(error => {
                    // Avoid stopping the main status poll on a stats fetch error
                    console.error('Error fetching live training stats:', error);
                    if (statusMessageEl) {
                        // Show a less intrusive status update error
                        const currentText = statusMessageEl.textContent;
                        if (!currentText.includes("Error fetching stats")) { // Avoid repeating error
                             statusMessageEl.innerHTML += ' <span class="text-warning small">(Stats unavailable)</span>';
                        }
                    }
                });
            } else {
                 console.warn("Training is active, but no model ID available to fetch live stats.")
            }

        } else {
            // --- Training is NOT running ---
            console.log("Training completed or not running.");
            if (trainingInterval) {
                clearInterval(trainingInterval);
                trainingInterval = null;
                console.log("Stopped status polling.");
            }

            // --- FETCH FINAL RESULTS using the stored model ID --- 
            // Try to get model ID from the status response if we don't have it
            if (!lastCompletedModelId && data.model_id) {
                lastCompletedModelId = data.model_id;
                console.log("Retrieved model ID from completed status response:", lastCompletedModelId);
            }
            
            if (lastCompletedModelId) {
                 console.log("Fetching final results for model:", lastCompletedModelId);
                 fetchFinalResults(lastCompletedModelId);
            } else {
                 console.error("Training finished, but no model ID was stored. Cannot fetch final results.");
                 console.error("Current lastCompletedModelId value:", lastCompletedModelId);
                 console.error("Training status data received:", data);
                 if (statusMessageEl) statusMessageEl.textContent = 'Training finished (Unknown Model ID)';
                 // Handle UI reset / re-enable form as needed
                  handleTrainingCompletionUI(null); // Call with null data
            }
        }
    })
    .catch(error => {
        console.error('Error checking training status:', error);
        if (trainingInterval) {
            clearInterval(trainingInterval);
            trainingInterval = null;
            console.log("Stopped status polling due to status check error.");
        }
         if (statusMessageEl) statusMessageEl.innerHTML = `<span class="text-danger">Status check failed: ${error.message}</span>`;
         // Re-enable form as a fallback
         handleTrainingCompletionUI(null); // Indicate completion (with error)
    });
}

// Function to reset the feature cache (API call)
function resetFeatureCache() {
    // Use global selectedDictionary from training_init_ui.js
    if (!selectedDictionary) {
        alert('Please select a dictionary first.');
        return;
    }

    if (confirm(`Reset feature cache for "${selectedDictionary}"? This requires re-extraction.`)) {
        // Show loading state on buttons (defined in training_init_ui.js)
        const btn1 = document.getElementById('resetFeatureCache');
        const btn2 = document.getElementById('resetFeatureCacheBtn');
        const originalText1 = btn1 ? btn1.innerHTML : '';
        const originalText2 = btn2 ? btn2.innerHTML : '';
        const setLoading = (btn, text) => {
            if (btn) { btn.disabled = true; btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> ${text}`; }
        };
        const resetLoading = (btn, originalText) => {
             if (btn) { btn.disabled = false; btn.innerHTML = originalText; }
        };

        setLoading(btn1, 'Resetting...');
        setLoading(btn2, 'Resetting...');

        fetch("/api/reset-feature-cache", { // Ensure API endpoint is correct
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dict_name: selectedDictionary })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Feature cache reset successfully! Reloading page...');
                // Reload page to reflect the need for feature extraction
                 // Use the globally defined trainingPageUrlBase from the HTML
                window.location.href = trainingPageUrlBase + "?dictionary=" + selectedDictionary + "&check_features=true";
            } else {
                throw new Error(data.message || 'Unknown error resetting cache.');
            }
        })
        .catch(error => {
            console.error('Error resetting feature cache:', error);
            alert('Failed to reset feature cache: ' + error.message);
            resetLoading(btn1, originalText1); // Reset buttons on error
            resetLoading(btn2, originalText2);
        });
    }
}

// --- NEW FUNCTION to fetch and display final results --- 
function fetchFinalResults(modelId) {
     const statusMessageEl = document.getElementById('statusMessage');
     const trainingProgressEl = document.getElementById('trainingProgress');

     fetch(`/api/ml/train/results/${modelId}`) // Use the new endpoint
     .then(response => {
         if (!response.ok) {
             return response.json().then(errData => {
                 throw new Error(errData.error || `Final results fetch failed: ${response.status}`);
             }).catch(() => {
                 throw new Error(`Final results fetch failed: ${response.status}`);
             });
         }
         return response.json();
     })
     .then(modelData => {
         console.log("Final model data:", modelData);
         // Use the received modelData (which is the ModelVersion dict) to update UI
         handleTrainingCompletionUI(modelData);
     })
     .catch(error => {
         console.error('Error fetching final training results:', error);
         if (statusMessageEl) statusMessageEl.innerHTML = `<span class="text-warning">Could not load final results: ${error.message}</span>`;
         // Still treat as completion, but show error
         handleTrainingCompletionUI({ error: error.message }); // Pass error info
     });
}

// --- NEW FUNCTION to handle UI updates on completion --- 
function handleTrainingCompletionUI(modelData) {
    const isErrorState = !modelData || modelData.status === 'failed' || modelData.error;
    const statusMessageEl = document.getElementById('statusMessage');
    const trainingProgressEl = document.getElementById('trainingProgress');
    const trainingStatusDiv = document.getElementById('trainingStatus');
    const logDiv = document.getElementById('trainingLog');

    // Final UI Updates (Progress Bar)
    if (trainingProgressEl) {
        trainingProgressEl.style.width = '100%';
        trainingProgressEl.classList.remove('mui-progress-bar-animated', 'mui-progress-bar-striped');
        trainingProgressEl.classList.toggle('bg-danger', isErrorState);
        trainingProgressEl.classList.toggle('bg-success', !isErrorState);
        trainingProgressEl.setAttribute('aria-valuenow', 100);
    }

    // Final Status Message
    if (statusMessageEl) {
        let completionMessage = 'Training complete!';
        if (isErrorState) {
            completionMessage = `<span class="text-danger">Training finished with errors.</span>`;
            if (modelData && modelData.metadata && modelData.metadata.error) {
                 completionMessage += `: ${modelData.metadata.error}`;
            }
        } else if (!modelData) {
            completionMessage = 'Training process finished (final results unavailable).';
        }
        statusMessageEl.innerHTML = completionMessage;
    }

    // Update steps, results, etc. based on modelData
    // NOTE: This part assumes your training_ui_render.js functions can handle the modelData structure
    if (modelData && !modelData.error) {
        // TODO: Potentially adapt updateTrainingStepsFromStats or create a new function
        // For now, mark last step as complete
        const lastStep = document.querySelector('#trainingStepsList .list-group-item:last-child');
        if (lastStep) updateTrainingStep(lastStep, true, 'Training finished.');

        // Display final metrics from modelData.metrics
        if (modelData.metrics) {
            displayModelResults(modelData.metrics); // Adapt if needed
        }

        // --- Display Training Analysis and Suggestions ---
        const analysisSummaryEl = document.getElementById('modelAnalysisSummary');
        const suggestionsListEl = document.getElementById('modelImprovementSuggestions');
        if (analysisSummaryEl && suggestionsListEl && modelData.metadata?.training_analysis) {
             const analysis = modelData.metadata.training_analysis;
             const finalAccuracy = modelData.metrics?.accuracy || 0;
             const likelyConverged = analysis.likely_converged;
             let summaryMsg = '';
             let suggestions = [];

             // Basic readiness check
             if (finalAccuracy > 0.85 && likelyConverged) {
                 summaryMsg = '<span class="text-success"><span class="material-icons me-1" style="font-size: 1em; vertical-align: text-bottom;">check_circle</span>Model appears ready for inference.</span>';
             } else if (finalAccuracy > 0.7) {
                 summaryMsg = '<span class="text-warning"><span class="material-icons me-1" style="font-size: 1em; vertical-align: text-bottom;">warning</span>Model performance is moderate. Consider improvements or test carefully.</span>';
             } else {
                  summaryMsg = '<span class="text-danger"><span class="material-icons me-1" style="font-size: 1em; vertical-align: text-bottom;">error</span>Model accuracy is low. Inference may be unreliable.</span>';
             }

             // Add suggestions
             if (finalAccuracy < 0.8) {
                 suggestions.push('Consider adding more varied training examples for each class.');
                 suggestions.push('Experiment with data augmentation settings.');
             }
             if (!likelyConverged) {
                 suggestions.push('Training may not have fully converged. Consider increasing the number of epochs.');
             }
             if (suggestions.length === 0 && finalAccuracy >= 0.95) {
                  suggestions.push('Model performance looks good! Continue monitoring during inference.');
             }

             analysisSummaryEl.innerHTML = summaryMsg;
             suggestionsListEl.innerHTML = suggestions.map(s => `<li>${s}</li>`).join('');
        } else {
            // Clear previous analysis if no new data
            if(analysisSummaryEl) analysisSummaryEl.innerHTML = '';
            if(suggestionsListEl) suggestionsListEl.innerHTML = '';
             if(modelData.metadata && !modelData.metadata.training_analysis) {
                 console.warn("No training analysis data found in model metadata.");
             }
        }
        // --- End Training Analysis --- 

        // --- Display Epoch Table if history exists --- 
        if (modelData.metadata && modelData.metadata.training_history) {
             // The history is now a list of objects: [{epoch: 1, loss:..., improved: true}, ...]
             const epochHistoryList = modelData.metadata.training_history;
             if (epochHistoryList.length > 0) {
                 // Pass directly to displayEpochTable
                 displayEpochTable(epochHistoryList); 
             }
         }
        // --- End Epoch Table Display ---

        // Add other UI updates based on modelData if necessary (e.g., data summary, logs if available)
    } else {
         // Handle UI when modelData is missing or indicates error
         const resultsContainer = document.getElementById('modelResultsContainer');
         if (resultsContainer) resultsContainer.style.display = 'none';
         const stepsListUI = document.getElementById('trainingStepsList');
         const errorMsg = modelData?.error || 'Unknown error during training.';
         if (stepsListUI) {
              const lastStep = stepsListUI.querySelector('.list-group-item:last-child');
              if(lastStep) updateTrainingStep(lastStep, false, `Failed: ${errorMsg}`, true);
              else stepsListUI.innerHTML += `<div class="alert alert-danger">Training failed: ${errorMsg}</div>`;
         }
    }

    // Add completion alert and restart button
    if (logDiv) {
        logDiv.querySelector('.alert.mt-3.mb-3')?.remove();
        logDiv.querySelector('.mui-button.mt-3')?.remove();

        const messageDiv = document.createElement('div');
        messageDiv.className = `alert ${isErrorState ? 'alert-warning' : 'alert-success'} mt-3 mb-3`;
        if (isErrorState) {
            messageDiv.innerHTML = `<span class="material-icons me-2">warning</span> Training finished with errors. ${modelData?.metadata?.error || 'Check server logs.'}`;
        } else {
            messageDiv.innerHTML = `<span class="material-icons me-2">check_circle</span> Training completed!`; // Removed predict link for now
        }
        logDiv.appendChild(messageDiv);

        const restartBtn = document.createElement('button');
        restartBtn.className = 'mui-button mui-button-contained mt-3';
        restartBtn.innerHTML = '<span class="material-icons" style="font-size: 16px; margin-right: 4px;">refresh</span>Train Another Model';
        restartBtn.onclick = () => window.location.reload();
        logDiv.appendChild(restartBtn);
    }

    // Re-enable form elements
    const dictionarySelectEl = document.getElementById('dictionarySelect');
    if (dictionarySelectEl) dictionarySelectEl.disabled = false;
    document.querySelectorAll('.mui-model-card button').forEach(btn => btn.disabled = false);
    const startTrainingBtnEl = document.getElementById('startTrainingBtn');
    if (startTrainingBtnEl) startTrainingBtnEl.disabled = false;
}
