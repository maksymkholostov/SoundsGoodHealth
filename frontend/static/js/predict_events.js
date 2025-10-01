/**
 * predict_events.js
 * Handles event listeners, UI interactions and application initialization
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('📋 DEBUG [predict_events.js]: DOM fully loaded and parsed');

    if (typeof currentUserId === 'undefined') {
        console.error('CRITICAL ERROR: currentUserId not defined globally in HTML.');
        document.body.innerHTML = '<div class="alert alert-danger">Page Configuration Error: User ID missing.</div>';
        return;
    }
    console.log(`📋 DEBUG [predict_events.js]: User ID found: ${currentUserId}`);

    // Set up all event listeners
    setupEventListeners();
    
    // Load available dictionaries with retry logic to ensure function is available
    let retryCount = 0;
    const maxRetries = 10;
    const retryDelay = 500;
    
    function tryLoadDictionaries() {
        if (typeof window.loadAvailableDictionaries === 'function') {
            console.log('📋 DEBUG [predict_events.js]: Loading dictionaries...');
            window.loadAvailableDictionaries();
        } else {
            retryCount++;
            if (retryCount < maxRetries) {
                console.log(`📋 DEBUG [predict_events.js]: loadAvailableDictionaries not ready yet, retry ${retryCount}/${maxRetries}...`);
                setTimeout(tryLoadDictionaries, retryDelay);
            } else {
                console.error("CRITICAL ERROR: loadAvailableDictionaries function is not available after multiple retries - dictionaries cannot be loaded");
                // Try to show error to user
                const dictSelect = document.getElementById('dictionarySelect');
                if (dictSelect) {
                    dictSelect.innerHTML = '<option selected disabled>Error loading dictionaries - please refresh page</option>';
                }
            }
        }
    }
    
    // Start trying after a short initial delay
    setTimeout(tryLoadDictionaries, 500);
});

/**
 * Set up all event listeners for the UI
 */
function setupEventListeners() {
    console.log('📋 DEBUG [predict_events.js]: Setting up event listeners');
    
    // Dictionary selection
    const dictionarySelect = document.getElementById('dictionarySelect');
    if (dictionarySelect) {
        dictionarySelect.addEventListener('change', window.handleDictionaryChange || function() {
            console.error("handleDictionaryChange function is not available");
        });
        console.log('📋 DEBUG [predict_events.js]: Added listener to dictionarySelect');
    }

    // Predict/End Button Listener
    const predictButton = document.getElementById('predictButton');
    if (predictButton) {
        predictButton.addEventListener('click', function(e) {
            console.log('>>> PREDICT/END BUTTON CLICKED (addEventListener)');
            console.log('📋 DEBUG [predict_main.js]: Direct predict button click handler');
            e.preventDefault();
            
            // Read state directly from window to avoid stale closures
            console.log(`>>> Button Click State Check: isListening=${window.isListening}, isCapturingNoise=${window.isCapturingNoise}`);
            console.log(`Predict button clicked. Current state: isListening=${window.isListening}, isCapturingNoise=${window.isCapturingNoise}`);
            
            if (window.isListening === true || window.isCapturingNoise === true) {
                console.log('Button will end prediction session');
                if (typeof window.endPredictionSession === 'function') {
                    console.log('Calling endPredictionSession()');
                    window.endPredictionSession();
                } else {
                    console.error('endPredictionSession function not available');
                }
            } else {
                console.log('Button will start prediction session');
                if (typeof window.startPredictionSession === 'function') {
                    console.log('Calling startPredictionSession()');
                    window.startPredictionSession();
                    // If Game Mode is selected, ensure the game loop starts immediately
                    const gameModeRadio = document.getElementById('gameModeRadio');
                    if (gameModeRadio && gameModeRadio.checked && typeof window.startGameLoop === 'function') {
                        console.log('Game Mode active: starting game loop after session start');
                        window.startGameLoop();
                    }
                } else {
                    console.error('startPredictionSession function not available');
                }
            }
            return false;
        });
        console.log('📋 DEBUG [predict_events.js]: Added enhanced listener to predictButton');
    }

    // Feedback Button
    const submitFeedbackBtn = document.getElementById('submitFeedbackBtn');
    if (submitFeedbackBtn) {
        submitFeedbackBtn.addEventListener('click', window.submitFeedback || function(e) {
            e.preventDefault();
            console.error("submitFeedback function is not available");
        });
        console.log('📋 DEBUG [predict_events.js]: Added listener to submitFeedbackBtn');
    }

    // Ambient Noise Switch
    const ambientNoiseSwitch = document.getElementById('ambientNoiseSwitch');
    if (ambientNoiseSwitch) {
        ambientNoiseSwitch.addEventListener('change', handleAmbientNoiseToggle);
        console.log('📋 DEBUG [predict_events.js]: Added listener to ambientNoiseSwitch');
    }

    // Prediction Mode Toggle
    const predictionModeToggle = document.getElementById('predictionModeToggle');
    if (predictionModeToggle) {
        predictionModeToggle.addEventListener('change', handlePredictionModeToggle);
        console.log('📋 DEBUG [predict_events.js]: Added listener to predictionModeToggle');
    }
    
    // Global scope toggle
    const globalViewAllToggle = document.getElementById('globalViewAllToggle');
    if (globalViewAllToggle) {
        globalViewAllToggle.addEventListener('change', function() {
            // Reload dictionaries when scope changes
            if (typeof window.loadAvailableDictionaries === 'function') {
                window.loadAvailableDictionaries();
            }
        });
    }
    
    // Run Comparison button
    const runComparisonBtn = document.getElementById('runComparisonBtn');
    if (runComparisonBtn) {
        runComparisonBtn.addEventListener('click', function() {
            console.log('Run Comparison button clicked');
            
            // Check if we have multiple models selected
            if (!window.selectedModelIds || window.selectedModelIds.length < 2) {
                alert('Please select at least 2 models to compare');
                return;
            }
            
            // Show the predictor interface and controls
            const predictorInterface = document.getElementById('predictorInterfaceCard');
            const controls = document.querySelector('.mui-controls-below-cards');
            
            if (predictorInterface) {
                predictorInterface.style.display = 'block';
                predictorInterface.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            
            if (controls) {
                controls.style.display = 'block';
            }
            
            // Enable multi-model mode
            window.useMultiModelComparison = true;
            console.log(`Comparison mode enabled with ${window.selectedModelIds.length} models`);
        });
    }

    console.log('📋 DEBUG [predict_events.js]: >>> Reached point to add document keydown listener.');
    // Spacebar listener for key actions (resume feedback or toggle session)
    document.addEventListener('keydown', function(event) {
        console.log(`>>> DOCUMENT KEYDOWN LISTENER FIRED: Key=${event.key}, Code=${event.code}`);
        
        // Check if it's the spacebar
        if (event.code === 'Space') {
            console.log(`>>> Spacebar pressed. Checking conditions...`);
            console.log(`>>>   window.isWaitingForFeedback = ${window.isWaitingForFeedback}`);
            console.log(`>>>   typeof window.resumeListeningAfterFeedback = ${typeof window.resumeListeningAfterFeedback}`);
            
            // Determine if focused element is interactive
            const activeTag = document.activeElement?.tagName?.toUpperCase();
            const isInteractive = ['INPUT','TEXTAREA','BUTTON','SELECT','A'].includes(activeTag);
            console.log(`>>>   Active element tag: ${activeTag}, isInteractive: ${isInteractive}`);

            // Don't process if the active element is a text input or similar
            if (isInteractive) {
                console.log('Spacebar pressed on interactive element, allowing default behavior.');
                return;
            }
            
            // Always prevent default behavior for spacebar when not on interactive elements
            event.preventDefault();

            // Force document body focus to ensure keypresses work
            document.body.focus();
            
            // Make 100% sure UI elements are visible
            const predictionHistoryCard = document.getElementById('predictionHistoryCard');
            if (predictionHistoryCard) {
                predictionHistoryCard.style.display = 'block';
                console.log("Ensuring prediction history visible after spacebar");
            }
            
            const confusionMatrixContainer = document.getElementById('confusionMatrixContainer');
            if (confusionMatrixContainer) {
                confusionMatrixContainer.style.display = 'block';
                console.log("Ensuring confusion matrix visible after spacebar");
            }

            // If in continuous mode (not waiting for feedback), toggle mic with spacebar
            if (!window.isWaitingForFeedback) {
                if (window.isListening === true || window.isCapturingNoise === true) {
                    if (typeof window.endPredictionSession === 'function') {
                        window.endPredictionSession();
                    }
                } else {
                    if (typeof window.startPredictionSession === 'function') {
                        window.startPredictionSession();
                    }
                }
            } else {
                // Waiting for feedback: resume listening
                console.log('>>> CONDITION MET: Waiting for feedback. Calling audio system restart function directly.');
                try {
                    // Forcibly cancel any animation frame before resuming
                    if (window.animationFrameId) {
                        cancelAnimationFrame(window.animationFrameId);
                        window.animationFrameId = null;
                        console.log("Cancelled existing animation frame before resuming");
                    }
                    
                    // CRITICAL FIX: Call directly to audio system function, avoiding circular reference
                    if (typeof window.audioResumeListeningAfterFeedback === 'function') {
                        window.audioResumeListeningAfterFeedback();
                    } else {
                        console.error("Audio system restart function not found!");
                        alert("Error restarting audio. Please refresh the page and try again.");
                    }
                } catch (error) {
                    console.error("Error when resuming listening after feedback:", error);
                    alert("Error restarting audio. Please refresh the page and try again.");
                }
            }
        }
    });
}

/**
 * Callback handler for prediction mode toggle
 * @param {Event} event - Change event
 */
function handlePredictionModeToggle(event) {
    if (typeof window.pauseForFeedback !== 'undefined') {
        window.pauseForFeedback = event.target.checked;
    }
    
    const statusElement = document.getElementById('predictionModeStatus');
    if (statusElement) {
        // Update status text: On when checked (paused), Off when unchecked (continuous)
        statusElement.textContent = window.pauseForFeedback ? 'On' : 'Off';
        
        // Toggle active class
        if (window.pauseForFeedback) {
            statusElement.classList.add('active');
        } else {
            statusElement.classList.remove('active');
        }
    }
    
    console.log(`Prediction mode set to: ${window.pauseForFeedback ? 'Paused for Feedback' : 'Continuous'}`);
    
    // If switching TO continuous mode WHILE waiting for feedback, resume listening
    if (!window.pauseForFeedback && window.isWaitingForFeedback && typeof window.resumeListeningAfterFeedback === 'function') {
        window.resumeListeningAfterFeedback();
    }
}

/**
 * Callback handler for ambient noise toggle
 * @param {Event} event - Change event
 */
async function handleAmbientNoiseToggle(event) {
    const isChecked = event.target.checked;
    console.log(`Ambient noise switch toggled: ${isChecked}`);
    const ambientNoiseStatus = document.getElementById('ambientNoiseStatus');
    
    if (ambientNoiseStatus) {
        // Update status text
        ambientNoiseStatus.textContent = isChecked ? 'On' : 'Off';
        
        // Update active class based on checked state
        if (isChecked) {
            ambientNoiseStatus.classList.add('active');
        } else {
            ambientNoiseStatus.classList.remove('active');
        }
    }
    
    if (isChecked) {
        // Start Noise Capture Process
        if (window.isListening || window.isCapturingNoise) {
            alert("Please stop listening/wait for noise capture to finish before starting a new noise capture.");
            event.target.checked = false; // Revert checkbox
            if (ambientNoiseStatus) {
                ambientNoiseStatus.classList.remove('active');
            }
            return;
        }
        
        if (!window.audioContext) {
            if (typeof window.initAudioProcessing === 'function') {
                if (!await window.initAudioProcessing()) {
                    event.target.checked = false; // Revert checkbox on init failure
                    if (ambientNoiseStatus) {
                        ambientNoiseStatus.classList.remove('active');
                    }
                    return; 
                }
            } else {
                console.error("initAudioProcessing function is not available");
                event.target.checked = false;
                if (ambientNoiseStatus) {
                    ambientNoiseStatus.classList.remove('active');
                }
                return;
            }
        }
        
        if (typeof window.startNoiseCapture === 'function') {
            window.startNoiseCapture();
        } else {
            console.error("startNoiseCapture function is not available");
            event.target.checked = false;
            if (ambientNoiseStatus) {
                ambientNoiseStatus.classList.remove('active');
            }
        }
        
        if (ambientNoiseStatus) ambientNoiseStatus.textContent = 'Measuring...';
    } else {
        // Cancel/Clear Noise Profile
        if (window.isCapturingNoise) {
            console.log("Noise capture cancelled by user.");
            if (window.noiseCaptureTimeoutId) clearTimeout(window.noiseCaptureTimeoutId);
            
            if (typeof window.endPredictionSession === 'function') {
                window.endPredictionSession(); // Use endPredictionSession for generic cleanup
            }
            
            window.isCapturingNoise = false;
        }
        
        window.ambientNoiseProfile = null;
        console.log("Ambient noise profile cleared.");
        if (ambientNoiseStatus) ambientNoiseStatus.textContent = 'Off';
    }
}

/**
 * Populate UI with a list of models
 * @param {Array} models - List of model objects
 */
function populateModelList(models) {
    const modelsList = document.getElementById('modelsList');
    if (!modelsList) return;

    modelsList.innerHTML = ''; // Clear existing list

    if (!models || models.length === 0) {
        console.log(`📋 DEBUG [predict_events.js]: No trained models to display.`);
        modelsList.innerHTML = `
            <div class="mui-alert mui-alert-info">
                <span class="material-icons">info</span>
                <span>No trained models found for the current dictionary (ID: ${window.currentDictionaryId || 'Unknown'}). Please train a model first.</span>
            </div>`;
        return;
    }

    // Sort models by creation date (newest first)
    const sortedModels = [...models].sort((a, b) => {
        const aTime = a.created_at || '0';
        const bTime = b.created_at || '0';
        return bTime.localeCompare(aTime);
    });

    console.log(`📋 DEBUG [predict_events.js]: Displaying ${sortedModels.length} sorted models`);

    // Create dictionary header (assuming only one dictionary based on current API)
    const dictionaryHeader = document.createElement('div');
    dictionaryHeader.className = 'mui-helper-text';
    dictionaryHeader.style.marginBottom = '1rem';
    dictionaryHeader.innerHTML = `
        <strong>
            <span class="material-icons" style="font-size: 16px; vertical-align: middle; margin-right: 4px;">folder</span>
            Models for Dictionary ID: ${window.currentDictionaryId || 'Unknown'}
        </strong>
    `;
    modelsList.appendChild(dictionaryHeader);

    // Create list items for each model
    sortedModels.forEach((model, index) => {
        const modelItem = createModelListItem(model, index);
        modelsList.appendChild(modelItem);
    });
    
    // Add direct click handlers after all models are added to DOM
    setTimeout(() => {
        console.log("Adding direct click handlers to all buttons and checkboxes");
        
        // Handle "Select Only" buttons
        document.querySelectorAll('.select-model-btn').forEach(button => {
            button.onclick = function() {
                const modelIdx = parseInt(this.getAttribute('data-model-index'), 10);
                const modelItem = this.closest('.mui-model-item');
                const modelId = modelItem ? modelItem.dataset.modelId : null;
                
                console.log(`DIRECT CLICK ON BUTTON: index=${modelIdx}, modelId=${modelId}`);
                
                if (modelId && typeof window.selectModel === 'function') {
                    // Clear multi-selection when selecting single model
                    window.selectedModelIds = [];
                    // Clear sound classes since we're switching models
                    window.soundClasses = [];
                    window.globalClassNamesForFeedback = [];
                    
                    document.querySelectorAll('.model-checkbox').forEach(cb => cb.checked = false);
                    if (typeof window.updateComparisonDisplay === 'function') {
                        window.updateComparisonDisplay();
                    }
                    
                    window.selectModel(modelId);
                }
                return false; // Prevent default and stop propagation
            };
        });
        
        // Handle comparison checkboxes
        document.querySelectorAll('.model-checkbox').forEach(checkbox => {
            checkbox.onchange = async function() {
                const modelId = this.getAttribute('data-model-id');
                console.log(`Checkbox changed for model: ${modelId}, checked: ${this.checked}`);
                if (typeof window.toggleModelForComparison === 'function') {
                    await window.toggleModelForComparison(modelId);
                }
            };
        });
    }, 100);
}

/**
 * Create a model list item for the UI
 * @param {Object} model - Model object
 * @param {number} index - Index in the list
 * @returns {HTMLElement} - Model list item element
 */
function createModelListItem(model, index) {
    // Use the index in the sortedModels array directly instead of findIndex
    // This ensures we always have a valid index
    const modelIdx = index; 
    
    console.log(`Creating model item #${index} for model ${model.id}`);
    console.log(`Model data:`, model);
    
    const modelItem = document.createElement('div');
    modelItem.className = 'mui-model-item';
    if (index === 0) {
        modelItem.classList.add('active');
    }
    
    // Store information for direct access
    modelItem.dataset.modelId = model.id;
    modelItem.dataset.modelIndex = modelIdx;

    const learningType = model.type ? model.type.toUpperCase() : 'UNKNOWN';
    
    // Extract time from model ID (last part after last underscore) for better distinction
    const timeFromId = model.id ? model.id.split('_').pop() : '';
    const formattedTime = timeFromId ? timeFromId.slice(0, 2) + ':' + timeFromId.slice(2, 4) + ':' + timeFromId.slice(4, 6) : '';
    
    // Get accuracy if available
    const accuracy = model.metrics && model.metrics.accuracy ? (model.metrics.accuracy * 100).toFixed(1) + '%' : '';
    
    // Build display name - check if name already contains type to avoid duplication
    const baseName = model.name || 'Model';
    let displayName;
    
    // Check if the name already starts with the model type (e.g., "RF - dict_ehoo")
    if (baseName.startsWith(`${learningType} - `)) {
        // Name already has type, use as-is
        displayName = `${baseName}${formattedTime ? ' (' + formattedTime + ')' : ''}${accuracy ? ' - ' + accuracy + ' acc' : ''}`;
    } else if (baseName.includes(learningType)) {
        // Name contains type somewhere, use as-is
        displayName = `${baseName}${formattedTime ? ' (' + formattedTime + ')' : ''}${accuracy ? ' - ' + accuracy + ' acc' : ''}`;
    } else {
        // Name doesn't have type, prepend it
        displayName = `${learningType} - ${baseName}${formattedTime ? ' (' + formattedTime + ')' : ''}${accuracy ? ' - ' + accuracy + ' acc' : ''}`;
    }
    
    const latestBadge = index === 0 ? `<span class="mui-chip mui-chip-${model.type === 'cnn' ? 'cnn' : (model.type === 'rf' ? 'rf' : 'ensemble')}">Latest</span>` : '';

    // Use direct onclick attribute with the stable index
    modelItem.innerHTML = `
        <div style="display: flex; width: 100%; justify-content: space-between; align-items: center;">
            <div>
                <h5 style="margin-bottom: 0.5rem; font-weight: 500;">
                    <span class="material-icons" style="font-size: 18px; margin-right: 6px; vertical-align: middle;">memory</span>${displayName}
                    ${latestBadge}
                </h5>
                <p style="margin-bottom: 0.25rem; font-size: 0.875rem;">
                    <small>ID: ${model.id || 'N/A'} | Version: ${model.version || 'N/A'} | Status: ${model.status || 'N/A'}</small>
                </p>
                <small class="mui-helper-text">${model.created_at ? new Date(model.created_at).toLocaleString() : 'No date'}</small>
            </div>
            <label class="mui-checkbox-label" style="margin-left: auto;">
                <input type="checkbox" class="model-checkbox" data-model-id="${model.id}" data-model-index="${modelIdx}">
                <span>Select</span>
            </label>
            <button type="button" class="delete-model-btn mui-button mui-button-danger" data-model-id="${model.id}" style="margin-left: 10px; padding: 8px 12px; min-width: auto;">
                <span class="material-icons" style="font-size: 18px;">close</span>
            </button>
        </div>
    `;
    
    // Add click handler directly to the button (more reliable)
    const selectButton = modelItem.querySelector('.select-model-btn');
    if (selectButton) {
        selectButton.onclick = function(e) {
            e.stopPropagation();
            console.log(`Button clicked - using model ID: ${model.id}`);
            
            // Clear multi-selection when selecting single model
            window.selectedModelIds = [];
            // Clear sound classes since we're switching models
            window.soundClasses = [];
            window.globalClassNamesForFeedback = [];
            
            document.querySelectorAll('.model-checkbox').forEach(cb => cb.checked = false);
            if (typeof window.updateComparisonDisplay === 'function') {
                window.updateComparisonDisplay();
            }
            
            if (typeof window.selectModel === 'function') {
                window.selectModel(model.id);
            }
            return false;
        };
    }
    
    // Add click handler for delete button
    const deleteButton = modelItem.querySelector('.delete-model-btn');
    if (deleteButton) {
        deleteButton.onclick = function(e) {
            e.stopPropagation();
            const modelId = this.getAttribute('data-model-id');
            console.log(`Delete button clicked for model: ${modelId}`);
            
            if (typeof window.deleteModel === 'function') {
                window.deleteModel(modelId);
            }
            return false;
        };
    }

    return modelItem;
}

/**
 * Handle spacebar press for resuming listening
 * This is a wrapper around the audio system's resumeListeningAfterFeedback
 */
function handleSpacebarListeningResume() {
    console.log("handleSpacebarListeningResume: Handling spacebar press to resume listening...");
    
    // Exit if we're not in feedback wait state
    if (!window.isWaitingForFeedback) {
        console.log("Not waiting for feedback, no need to resume.");
        return;
    }
    
    console.log("Preparing UI for resuming listening");
    window.isWaitingForFeedback = false; // Reset the waiting state immediately
    
    // Hide the feedback section
    const feedbackSection = document.getElementById('feedbackSection');
    if (feedbackSection) {
        feedbackSection.style.display = 'none';
        feedbackSection.style.visibility = 'hidden';
    }
    
    // Clear previous prediction display
    const predictionElement = document.getElementById('prediction');
    if (predictionElement) {
        predictionElement.innerText = '';
        predictionElement.style.display = 'none';
    }
    
    // Reset the global current prediction
    window.currentPrediction = null;
    window.lastFeedbackPredictionId = null; // Clear the last feedback ID
    
    // Also clear any highlighted items
    const allPredictionItems = document.querySelectorAll('.prediction-item');
    allPredictionItems.forEach(item => {
        item.classList.remove('selected');
        item.classList.remove('highlighted');
    });
    
    // Update the UI to show "Listening..."
    updateListeningIndicator(true);
    
    // CRITICAL FIX: Use a direct reference to the audio system's function
    // Avoid any possible name collisions or circular references
    if (typeof window.audioResumeListeningAfterFeedback === 'function') {
        console.log("Calling audio system's resumeListeningAfterFeedback function directly");
        window.audioResumeListeningAfterFeedback();
    } else {
        console.error("Audio system's resumeListeningAfterFeedback function not found!");
        alert("Error: Audio restart function not found. Please refresh the page and try again.");
    }
}

// Export functions to global scope
window.setupEventListeners = setupEventListeners;
window.handlePredictionModeToggle = handlePredictionModeToggle;
window.handleAmbientNoiseToggle = handleAmbientNoiseToggle;
window.populateModelList = populateModelList;
window.createModelListItem = createModelListItem;
window.resumeListeningAfterFeedback = handleSpacebarListeningResume; // Export with original name for compatibility 

// --- Game 2: variant toggles ---
document.addEventListener('DOMContentLoaded', function() {
    const gv1 = document.getElementById('gameVariant1');
    const gv2 = document.getElementById('gameVariant2');
    const gv3 = document.getElementById('gameVariant3');
    function applyVariant() {
        let variant = 'game1';
        if (gv2 && gv2.checked) variant = 'game2';
        if (gv3 && gv3.checked) variant = 'game3';
        if (typeof window.setGameVariant === 'function') {
            window.setGameVariant(variant);
        } else {
            // Fallback: define on the fly if missing
            window.setGameVariant = function(v){ window.currentGameVariant = v; };
            window.setGameVariant(variant);
        }
        // Console + on-page flag
        console.log(`[GameVariant] Switched to: ${variant}`);
        const status = document.getElementById('gameVariantStatus');
        if (status) {
            const label = variant === 'game1' ? 'Instant Feedback' : (variant === 'game2' ? 'Tower Stack' : 'Tile Puzzle');
            status.textContent = `Active: ${label}`;
        }
        // Force immediate visibility switch for games
        const puzzle = document.getElementById('puzzleGameContainer');
        const tower = document.getElementById('towerGameContainer');
        if (puzzle) {
            if (variant === 'game3') {
                puzzle.style.display = 'block';
                if (typeof window.initPuzzleGame === 'function') window.initPuzzleGame();
            } else {
                puzzle.style.display = 'none';
                if (typeof window.destroyPuzzleGame === 'function') window.destroyPuzzleGame();
            }
        }
        if (tower) {
            if (variant === 'game2') {
                tower.style.display = 'block';
                if (typeof window.initTowerGame === 'function') window.initTowerGame('towerGameContainer');
            } else {
                tower.style.display = 'none';
                if (typeof window.destroyTowerGame === 'function') window.destroyTowerGame();
            }
        }

        // Trim feedback space for Tower; enlarge for others
        const wrap = document.getElementById('gameFeedbackWrap');
        const iconBox = document.getElementById('gameFeedbackIcon');
        if (wrap && iconBox) {
            if (variant === 'game2') {
                wrap.style.height = '0px';
                iconBox.style.display = 'none';
            } else {
                wrap.style.height = '280px';
                iconBox.style.display = 'flex';
            }
        }

        // Refresh the Say: label with friendly name if we already have a target
        if (typeof window.displayTargetSound === 'function' && window.currentGameTargetClassId) {
            window.displayTargetSound(window.currentGameTargetClassId);
        }
    }
    if (gv1) gv1.addEventListener('change', applyVariant);
    if (gv2) gv2.addEventListener('change', function(){ applyVariant(); refreshTowerVisibility(); refreshPuzzleVisibility(); });
    if (gv3) gv3.addEventListener('change', function(){ applyVariant(); refreshTowerVisibility(); refreshPuzzleVisibility(); });
    // Defensive: capture any change on the variant radio group (even if DOM ref missed)
    document.addEventListener('change', function(ev){
        const t = ev.target;
        if (t && t.name === 'gameVariant') {
            applyVariant();
            refreshTowerVisibility();
            refreshPuzzleVisibility();
        }
    });
    // initialize on load and force immediate UI switches
    applyVariant();
    // Re-evaluate status text once DOM settled
    setTimeout(applyVariant, 50);
    setTimeout(function(){
        // Ensure correct element visibility after initial load
        const gameModeRadioInit = document.getElementById('gameModeRadio');
        if (gameModeRadioInit && gameModeRadioInit.checked) {
            refreshTowerVisibility();
            refreshPuzzleVisibility();
        }
    }, 100);

    // Play again resets current game state without affecting analysis
    const resetBtn = document.getElementById('gameResetBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function(){
            try { if (typeof window.stopGameLoop === 'function') window.stopGameLoop(); } catch(e) {}
            // Clear icon to neutral and scroll into view
            const icon = document.getElementById('gameFeedbackIcon');
            if (icon) icon.innerHTML = '<span class="material-icons" style="font-size:96px; color:#9E9E9E;">horizontal_rule</span>';
            // Re-init selected variant container (visible)
            refreshTowerVisibility();
            refreshPuzzleVisibility();
            // Center viewport on game section
            const section = document.getElementById('gamePlaySection');
            if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }

    // Center viewport when switching to Game Mode from radios
    document.querySelectorAll('input[name="predictionMode"]').forEach(r => {
        r.addEventListener('change', function(){
            if (this.id === 'gameModeRadio' && this.checked) {
                const section = document.getElementById('gamePlaySection');
                if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // Show/hide tower game canvas based on variant + game mode
    function refreshTowerVisibility(){
        const container = document.getElementById('towerGameContainer');
        if (!container) return;
        const inGame = !!window.currentGameModeActive;
        const isGame2 = (gv2 && gv2.checked);
        container.style.display = (inGame && isGame2) ? 'block' : 'none';
        if (inGame && isGame2) {
            if (typeof window.initTowerGame === 'function') window.initTowerGame('towerGameContainer');
        } else {
            if (typeof window.destroyTowerGame === 'function') window.destroyTowerGame();
        }
    }

    function refreshPuzzleVisibility(){
        const container = document.getElementById('puzzleGameContainer');
        const face = document.getElementById('faceContainer');
        if (!container) return;
        const inGame = !!window.currentGameModeActive;
        const isGame3 = (gv3 && gv3.checked);
        container.style.display = (inGame && isGame3) ? 'block' : 'none';
        if (inGame && isGame3) {
            if (typeof window.initPuzzleGame === 'function') window.initPuzzleGame();
            // Hide face so it doesn't overlap the puzzle
            if (face) face.style.display = 'none';
            if (typeof window.stopFaceHeightMonitoring === 'function') window.stopFaceHeightMonitoring();
        } else {
            if (typeof window.destroyPuzzleGame === 'function') window.destroyPuzzleGame();
            // Restore face for other variants
            if (face) face.style.display = 'block';
        }
    }
    // hook into existing mode updates if possible
    const _upd = window.updateControlsVisibility;
    if (typeof _upd === 'function') {
        window.updateControlsVisibility = function(){ _upd(); refreshTowerVisibility(); refreshPuzzleVisibility(); };
    }
    // also respond when game mode radio is toggled
    const gameModeRadio = document.getElementById('gameModeRadio');
    if (gameModeRadio) {
        gameModeRadio.addEventListener('change', function(){
            refreshTowerVisibility();
            refreshPuzzleVisibility();
            if (this.checked && typeof window.startGameLoop === 'function') {
                console.log('Game Mode toggled on: starting game loop');
                window.startGameLoop();
            }
        });
    }
    // also refresh periodically for safety
    setInterval(function(){ refreshTowerVisibility(); refreshPuzzleVisibility(); }, 800);
});