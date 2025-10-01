// Global variables used by both UI and processing logic
let selectedModel = null;
let selectedDictionary = null; // Name
let selectedDictionaryId = null; // <--- ADDED global variable for ID
// let trainingInterval = null; // REMOVED declaration - Declared in training_api_state.js

document.addEventListener('DOMContentLoaded', function() {
    // --- Initialize UI Components ---
    // Bootstrap tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Bootstrap Tabs (for MFCC details)
    const triggerTabList = [].slice.call(document.querySelectorAll('#mfccTabs button'));
    triggerTabList.forEach(function (triggerEl) {
      const tabTrigger = new bootstrap.Tab(triggerEl);
      triggerEl.addEventListener('click', function (event) {
        event.preventDefault();
        tabTrigger.show();
      });
    });

    // --- Event Listeners ---
    // Dictionary selection
    const dictionarySelect = document.getElementById('dictionarySelect');
    if (dictionarySelect) {
        dictionarySelect.addEventListener('change', function() {
            selectedDictionary = this.value; // Get name from value

            // Get ID from selected option's data-id attribute
            const selectedOption = this.options[this.selectedIndex];
            selectedDictionaryId = selectedOption ? selectedOption.getAttribute('data-id') : null; // <-- Store ID

            const dictNameInput = document.getElementById('dictName');
            if(dictNameInput) dictNameInput.value = selectedDictionary; // Keep hidden input updated if needed elsewhere

            if (selectedDictionary && selectedDictionaryId) { // Check both name and ID
                // Use optimized AJAX check instead of page reload
                updateDictionaryInfo(selectedDictionary); // Update counts, etc.
                const dictInfoDiv = document.getElementById('dictionaryInfo');
                if(dictInfoDiv) dictInfoDiv.style.display = 'block';
                
                // Enable model selection buttons
                document.querySelectorAll('.mui-model-card button').forEach(btn => {
                    btn.disabled = false;
                });
                
                // Trigger optimized feature status check
                if (window.trainingManager) {
                    // Use the optimized manager if available
                    window.trainingManager.selectedDictionary = selectedDictionary;
                    window.trainingManager.selectedDictionaryId = selectedDictionaryId;
                    window.trainingManager.checkFeatureStatus();
                } else {
                    // Fallback: Load feature status via AJAX
                    checkFeatureStatusOptimized(selectedDictionaryId);
                }
            } else {
                // No dictionary selected or ID missing
                selectedDictionaryId = null; // Clear ID
                const dictInfoDiv = document.getElementById('dictionaryInfo');
                 if(dictInfoDiv) dictInfoDiv.style.display = 'none';
                // Disable model selection buttons
                document.querySelectorAll('.mui-model-card button').forEach(btn => {
                    btn.disabled = true;
                });
                // Hide training parameters
                 const trainingParamsDiv = document.getElementById('trainingParameters');
                 if(trainingParamsDiv) trainingParamsDiv.style.display = 'none';
                 selectedModel = null; // Reset selected model
                 updateTrainingParamsTitle(); // Update title
                 // Remove model card highlighting
                 document.querySelectorAll('.mui-model-card').forEach(card => {
                    card.classList.remove('border', 'border-primary', 'border-3');
                 });
            }
        });

        // Initial UI state based on pre-selected dictionary (if any)
        if (dictionarySelect.value) {
             selectedDictionary = dictionarySelect.value; // Sync JS name variable
             const selectedOption = dictionarySelect.options[dictionarySelect.selectedIndex];
             selectedDictionaryId = selectedOption ? selectedOption.getAttribute('data-id') : null; // <-- Get ID on load
             updateDictionaryInfo(selectedDictionary);
             const dictInfoDiv = document.getElementById('dictionaryInfo');
             if(dictInfoDiv) dictInfoDiv.style.display = 'block';
             document.querySelectorAll('.mui-model-card button').forEach(btn => {
                 btn.disabled = false;
             });
             const dictNameInput = document.getElementById('dictName');
             if(dictNameInput) dictNameInput.value = selectedDictionary;
        } else {
             selectedDictionaryId = null; // Ensure ID is null initially
            // No dictionary initially selected
            document.querySelectorAll('.mui-model-card button').forEach(btn => {
                btn.disabled = true;
            });
        }
    }

    // Model selection buttons (event delegation could be an alternative)
    document.querySelectorAll('.mui-model-card button[onclick^="selectModel"]').forEach(button => {
        const modelType = button.getAttribute('onclick').match(/selectModel\('(.+?)'\)/)[1];
        if (modelType) {
            button.removeAttribute('onclick'); // Remove inline handler
            button.addEventListener('click', () => selectModel(modelType));
        }
    });


    // Start training button
    const startTrainingBtn = document.getElementById('startTrainingBtn');
    if (startTrainingBtn) {
        // Call startTraining function (defined in training_process.js)
        startTrainingBtn.addEventListener('click', startTraining);
    }

    // Reset Feature Cache buttons
    const resetCacheButton = document.getElementById('resetFeatureCache');
    if (resetCacheButton) {
         // Call resetFeatureCache function (defined in training_process.js)
        resetCacheButton.addEventListener('click', resetFeatureCache);
    }
    const resetCacheButtonParams = document.getElementById('resetFeatureCacheBtn');
    if (resetCacheButtonParams) {
        // Call resetFeatureCache function (defined in training_process.js)
        resetCacheButtonParams.addEventListener('click', resetFeatureCache);
    }

    // Toggle Detailed Logs button
     const toggleLogBtn = document.querySelector('#trainingLog button'); // More specific selector
     if (toggleLogBtn && toggleLogBtn.textContent.includes("Toggle Detailed Logs")) {
         toggleLogBtn.removeAttribute('onclick'); // Remove inline handler
         toggleLogBtn.addEventListener('click', toggleLogDetails);
     }


    // Toggle MFCC details card header
    const toggleMfccBtn = document.querySelector('#mfccNormalizationDetails .mui-card-header[data-bs-toggle="collapse"]');
    if (toggleMfccBtn) {
         // Bootstrap handles the collapse, we just need to manage the icon state via events
         const content = document.getElementById('mfccDetailsContent');
         const icon = document.getElementById('mfccToggleIcon');

         if(content && icon) {
             const handleMfccCollapseToggle = () => {
                 if (content.classList.contains('show')) {
                     icon.textContent = 'expand_more'; // Material icon name for down arrow
                 } else {
                     icon.textContent = 'chevron_right'; // Material icon name for right arrow
                 }
             };
             // Set initial state
             handleMfccCollapseToggle();
             // Update on toggle
             content.addEventListener('shown.bs.collapse', handleMfccCollapseToggle);
             content.addEventListener('hidden.bs.collapse', handleMfccCollapseToggle);
         }
    }

    // --- Initial State Check ---
    // Update feature vector display on load if element exists
    if (document.getElementById('complete-feature-vector')) {
        // Call updateFeatureVectorDisplay (defined in training_process.js)
        updateFeatureVectorDisplay();
    }

    // Check if training is already in progress on page load
    // DISABLED: Using optimized training API instead which handles its own status
    // checkTrainingStatus();
});

// --- UI Interaction Functions ---

function selectModel(modelType) {
    // Block CNN and Ensemble model types (only allow RF, CNN1D, and SVM)
    if (modelType === 'cnn' || modelType === 'ensemble') {
        console.warn(`Model type '${modelType}' is not currently available.`);
        alert(`The ${modelType.toUpperCase()} model type is not currently available. Please select RF, CNN1D, or SVM.`);
        return;
    }
    
    selectedModel = modelType;
    const modelTypeInput = document.getElementById('modelType');
    if(modelTypeInput) modelTypeInput.value = modelType;

    // Show the training parameters section
    const trainingParamsDiv = document.getElementById('trainingParameters');
    if(trainingParamsDiv) trainingParamsDiv.style.display = 'block';

    // --- Hide/show specific parameter sections ---
    // It's safer to query for the wrapper divs/elements containing these params
    const cnnParamSections = document.querySelectorAll('#trainingForm div[id="cnnParameters"]');
    const rfParamSections = document.querySelectorAll('#trainingForm div[id="rfParameters"]');
    const ensembleParamSections = document.querySelectorAll('#trainingForm div[id="ensembleParameters"]');
    const commonParamSection = document.getElementById('commonParameters'); // Assuming this ID exists

    // Hide all first
    cnnParamSections.forEach(el => el.style.display = 'none');
    rfParamSections.forEach(el => el.style.display = 'none');
    ensembleParamSections.forEach(el => el.style.display = 'none');
    if (commonParamSection) commonParamSection.style.display = 'none'; // Hide common initially

    // Show relevant ones
    if (modelType === 'cnn') {
        cnnParamSections.forEach(el => el.style.display = 'block');
        if (commonParamSection) commonParamSection.style.display = 'block'; // Show common for CNN
    } else if (modelType === 'cnn1d') {
        // CNN1D uses the same parameters as CNN
        cnnParamSections.forEach(el => el.style.display = 'block');
        if (commonParamSection) commonParamSection.style.display = 'block';
        // Update epochs default for CNN1D
        const epochsInput = document.getElementById('cnnEpochs');
        if (epochsInput) {
            epochsInput.value = 100;  // Default 100 epochs for CNN1D
        }
    } else if (modelType === 'rf') {
        rfParamSections.forEach(el => el.style.display = 'block');
        // Optionally show common params for RF if needed:
        // if (commonParamSection) commonParamSection.style.display = 'block';
    } else if (modelType === 'ensemble') {
        cnnParamSections.forEach(el => el.style.display = 'block');
        rfParamSections.forEach(el => el.style.display = 'block');
        ensembleParamSections.forEach(el => el.style.display = 'block');
        if (commonParamSection) commonParamSection.style.display = 'block'; // Show common for Ensemble
    }
    // --- End parameter section visibility ---


    updateTrainingParamsTitle();

    // Highlight selected model card
    document.querySelectorAll('.mui-model-card').forEach(card => {
        card.classList.remove('border', 'border-primary', 'border-3'); // Use Bootstrap classes
    });

    // Find the button corresponding to the modelType and highlight its parent card
    const selectedButton = document.querySelector(`.mui-model-card button[data-model-type="${modelType}"]`); // Requires adding data-model-type attribute to buttons in HTML
     // Fallback or adjust selector if data-model-type isn't added:
     // const selectedButton = document.querySelector(`button[onclick="selectModel('${modelType}')"]`); // If keeping onclick temporarily or using a different identifier

     // Add data-model-type="cnn", data-model-type="rf" etc. to the select buttons in the HTML
     const modelButtons = document.querySelectorAll('.mui-model-card button');
     modelButtons.forEach(btn => {
         const onclickAttr = btn.getAttribute('onclick');
         if (onclickAttr) {
             const match = onclickAttr.match(/selectModel\('(.+?)'\)/);
             if (match && match[1]) {
                 btn.dataset.modelType = match[1]; // Add data-model-type attribute
             }
         }
         // Find the button again using the data attribute
         if (btn.dataset.modelType === modelType) {
              const selectedCard = btn.closest('.mui-model-card');
              if (selectedCard) {
                  selectedCard.classList.add('border', 'border-primary', 'border-3');
              }
         }
     });


    // Scroll to training parameters
    if(trainingParamsDiv) {
        trainingParamsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function updateDictionaryInfo(dictName) {
    // Get info from the select option text
    const option = document.querySelector(`#dictionarySelect option[value="${dictName}"]`);
    if (option) {
        const text = option.textContent;
        const match = text.match(/\((\d+)\s*classes,\s*(\d+)\s*samples\)/); // More robust regex

        const classCountEl = document.getElementById('classCount');
        const sampleCountEl = document.getElementById('sampleCount');

        if (match) {
            if(classCountEl) classCountEl.textContent = match[1];
            if(sampleCountEl) sampleCountEl.textContent = match[2];
        } else {
             if(classCountEl) classCountEl.textContent = '?'; // Fallback
             if(sampleCountEl) sampleCountEl.textContent = '?'; // Fallback
        }
        // Assuming creator info isn't in the option text
        const createdByEl = document.getElementById('createdBy');
        if(createdByEl) createdByEl.textContent = 'You'; // Placeholder - fetch actual if needed

        updateTrainingParamsTitle(); // Update dependent title
    }
}

function updateTrainingParamsTitle() {
    const titleElement = document.getElementById('trainingParamsTitle');
    if (!titleElement) return;

    if (selectedModel && selectedDictionary) {
        let modelName = '';
        switch (selectedModel) {
            case 'cnn': modelName = 'CNN'; break;
            case 'rf': modelName = 'Random Forest'; break;
            case 'ensemble': modelName = 'Ensemble'; break;
            default: modelName = 'Selected Model'; break;
        }
        titleElement.textContent = `Parameters for ${modelName} on "${selectedDictionary}"`;
    } else {
         titleElement.textContent = 'Select Model & Dictionary'; // Clearer default
    }
}

// Function to toggle log details display
function toggleLogDetails() {
    const logContainer = document.getElementById('detailedLogs');
    if (logContainer) {
        const isHidden = logContainer.style.display === 'none';
        logContainer.style.display = isHidden ? 'block' : 'none';
         // If showing, scroll to bottom (handled by checkTrainingStatus update now)
         // if (isHidden) {
         //     const logMessagesEl = document.getElementById('logMessages');
         //     const logContentDiv = logMessagesEl?.parentElement;
         //     if (logContentDiv) {
         //         logContentDiv.scrollTop = logContentDiv.scrollHeight;
         //     }
         // }
    }
}

// Note: toggleMfccDetails is implicitly handled by Bootstrap JS via data attributes.
// We only need the icon update logic, which is now inside the DOMContentLoaded listener.

// Helper potentially used by displayModelResults (in training_process.js)
function clearLoadingSpinners() {
    const spinners = document.querySelectorAll('#modelResults .spinner-border');
    spinners.forEach(spinner => spinner.remove()); // Simpler removal

    // This might be too generic, consider specific classes if needed
    // const hiddenContent = document.querySelectorAll('#modelResults .content-to-show');
    // hiddenContent.forEach(content => {
    //     content.style.display = 'block';
    // });
}

// Helper used by displayTrainingErrors (in training_process.js)
function addSuggestion(text, container, addedSuggestionsSet) {
     // Ensure container is valid and it's a Set
    if (!container || !(addedSuggestionsSet instanceof Set)) {
        console.error("Invalid arguments for addSuggestion");
        return;
    }
    if (!addedSuggestionsSet.has(text)) {
        const li = document.createElement('li');
        li.textContent = text;
        container.appendChild(li);
        addedSuggestionsSet.add(text);
    }
}

// Optimized feature status check - no page reload!
async function checkFeatureStatusOptimized(dictionaryId) {
    if (!dictionaryId) return;
    
    // Show loading indicator
    const dictInfoDiv = document.getElementById('dictionaryInfo');
    if (dictInfoDiv) {
        // Check if feature status section exists
        let statusSection = document.querySelector('.feature-status-section');
        if (!statusSection) {
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
            dictInfoDiv.insertAdjacentHTML('afterend', statusHTML);
            statusSection = document.querySelector('.feature-status-section');
        }
        
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
    
    try {
        const response = await fetch(`/api/features/status/${dictionaryId}`, {
            method: 'GET',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayOptimizedFeatureStatus(data.status);
            
            // If features are missing, automatically start extraction
            if (data.status.files_missing_features > 0) {
                console.log(`${data.status.files_missing_features} files need feature extraction`);
                // Show extraction UI
                showFeatureExtractionUI(dictionaryId, data.status);
            }
        } else {
            console.error('Feature status check failed:', data.error);
            showFeatureStatusError(data.error || 'Failed to check feature status');
        }
    } catch (error) {
        console.error('Error checking feature status:', error);
        showFeatureStatusError('Network error while checking feature status');
    }
}

function displayOptimizedFeatureStatus(status) {
    const statusSection = document.querySelector('.feature-status-section');
    if (!statusSection) return;
    
    const content = statusSection.querySelector('.feature-status-content');
    if (!content) return;
    
    const hasAllFeatures = status.files_missing_features === 0;
    const alertClass = hasAllFeatures ? 'alert-success' : 'alert-warning';
    
    content.innerHTML = `
        <div class="alert ${alertClass}">
            <div class="row">
                <div class="col-md-3">
                    <strong>Total Files:</strong> ${status.total_files}
                </div>
                <div class="col-md-3">
                    <strong>With Features:</strong> ${status.files_with_features}
                </div>
                <div class="col-md-3">
                    <strong>Missing Features:</strong> ${status.files_missing_features}
                </div>
                <div class="col-md-3">
                    <strong>Progress:</strong> ${Math.round((status.files_with_features / status.total_files) * 100)}%
                </div>
            </div>
        </div>
    `;
}

function showFeatureExtractionUI(dictionaryId, status) {
    const statusSection = document.querySelector('.feature-status-section');
    if (!statusSection) return;
    
    const content = statusSection.querySelector('.feature-status-content');
    if (!content) return;
    
    // Add extraction button and info
    content.innerHTML += `
        <div class="alert alert-info mt-3">
            <h5>Feature Extraction Required</h5>
            <p>${status.files_missing_features} files need feature extraction before training can begin.</p>
            <button class="btn btn-primary" onclick="startOptimizedFeatureExtraction('${dictionaryId}')">
                <i class="fas fa-cogs"></i> Start Feature Extraction
            </button>
            <div id="extractionProgress" style="display:none; margin-top: 15px;">
                <div class="progress">
                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                         role="progressbar" style="width: 0%"></div>
                </div>
                <p class="extraction-status mt-2">Initializing...</p>
            </div>
        </div>
    `;
}

function showFeatureStatusError(error) {
    const statusSection = document.querySelector('.feature-status-section');
    if (!statusSection) return;
    
    const content = statusSection.querySelector('.feature-status-content');
    if (!content) return;
    
    content.innerHTML = `
        <div class="alert alert-danger">
            <strong>Error:</strong> ${error}
        </div>
    `;
}

// Start optimized feature extraction with progress
async function startOptimizedFeatureExtraction(dictionaryId) {
    const progressDiv = document.getElementById('extractionProgress');
    const progressBar = progressDiv.querySelector('.progress-bar');
    const statusText = progressDiv.querySelector('.extraction-status');
    
    // Show progress UI
    progressDiv.style.display = 'block';
    
    try {
        // Start extraction via optimized endpoint
        const response = await fetch(`/api/features/trigger/${dictionaryId}`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.progress_id) {
            // Start SSE connection for progress updates
            const eventSource = new EventSource(`/api/features/progress/${data.progress_id}`);
            
            eventSource.onmessage = function(event) {
                const update = JSON.parse(event.data);
                
                if (update.type === 'progress') {
                    const percent = Math.round((update.processed / update.total) * 100);
                    progressBar.style.width = percent + '%';
                    statusText.textContent = `Processing ${update.current_file} (${update.processed}/${update.total})`;
                } else if (update.type === 'complete') {
                    progressBar.style.width = '100%';
                    progressBar.classList.remove('progress-bar-animated');
                    progressBar.classList.add('bg-success');
                    statusText.textContent = 'Feature extraction complete!';
                    eventSource.close();
                    
                    // Refresh feature status after completion
                    setTimeout(() => {
                        checkFeatureStatusOptimized(dictionaryId);
                    }, 2000);
                } else if (update.type === 'error') {
                    progressBar.classList.add('bg-danger');
                    statusText.textContent = `Error: ${update.message}`;
                    eventSource.close();
                }
            };
            
            eventSource.onerror = function() {
                statusText.textContent = 'Connection lost. Extraction may still be running in background.';
                eventSource.close();
            };
        } else {
            statusText.textContent = 'Failed to start extraction: ' + (data.error || 'Unknown error');
        }
    } catch (error) {
        console.error('Error starting extraction:', error);
        statusText.textContent = 'Network error: ' + error.message;
    }
}
