/**
 * predict_ui_core.js
 * Core UI functionality for the SoundsGood application
 * Handles DOM manipulation, styling, and basic UI operations
 */

// State tracking
let currentPrediction = null;
let activeSound = null;

// Initialize all UI components
document.addEventListener('DOMContentLoaded', async function() {
    console.log('📋 DEBUG [predict_ui_core.js]: DOM fully loaded and parsed');

    // Wait for ID Mapper first
    try {
        console.log('📋 DEBUG [predict_ui_core.js]: Waiting for ID Mapper init...');
        if (window.IdMapper && typeof window.IdMapper.init === 'function') {
            await window.IdMapper.init(); // Wait for the mappings to load
            console.log('📋 DEBUG [predict_ui_core.js]: ID Mapper initialized successfully.');
            console.log('📋 DEBUG IdMapper Status:', window.IdMapper.getDebugInfo()); // Log status after await
        } else {
            console.error('IdMapper or IdMapper.init not found!');
            throw new Error('IdMapper dependency missing.');
        }
    } catch (error) {
        console.error('Failed to initialize IdMapper:', error);
        alert("Critical Error: Failed to load necessary ID mappings. Some names may appear as IDs.");
        // Continue loading UI anyway, but names might be broken
    }

    // Proceed with rest of UI initialization
    applyMuiStyles();
});

/**
 * Apply Material UI styles to elements throughout the application
 */
function applyMuiStyles() {
    console.log('📋 DEBUG [predict_ui_core.js]: Applying MUI styles...');
    
    // Update model selection cards to enhance visual appeal
    enhanceCardTransitions();
    
    // Update any buttons with Material Icons
    updateButtonIcons();
    
    // Enhanced styling for form elements, particularly the dictionary dropdown
    enhanceFormControls();
    
    // Setup event listeners for UI elements
    setupUIInteractions();
    
    // Convert any legacy classes or elements that might be dynamically added
    convertLegacyClasses();
    
    // Add subtle animations and transitions
    addVisualEnhancements();
    
    console.log('📋 DEBUG [predict_ui_core.js]: Finished applying MUI styles.');
}

/**
 * Enhance card transitions and hover effects
 */
function enhanceCardTransitions() {
    document.querySelectorAll('.mui-model-card').forEach(card => {
        // Add shadow depth on hover
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px)';
            this.style.boxShadow = '0 12px 20px rgba(0,0,0,0.15)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = '';
            this.style.boxShadow = '';
        });
        
        // Add a subtle highlight to card headers
        const header = card.querySelector('.mui-card-header');
        if (header) {
            header.style.transition = 'background-color 0.3s ease';
            card.addEventListener('mouseenter', function() {
                header.style.backgroundColor = 'rgba(63, 81, 181, 0.08)';
            });
            
            card.addEventListener('mouseleave', function() {
                header.style.backgroundColor = '';
            });
        }
    });
}

/**
 * Enhanced styling for form controls, especially select elements
 */
function enhanceFormControls() {
    // Style select elements
    document.querySelectorAll('.mui-form-select').forEach(select => {
        // Set minimum width for select elements
        select.style.minWidth = '250px';
        select.style.height = 'auto';
        
        // Add transition effects
        select.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
        
        // Add focus effects
        select.addEventListener('focus', function() {
            this.style.borderColor = 'var(--primary-color, #3f51b5)';
            this.style.boxShadow = '0 0 0 3px rgba(63, 81, 181, 0.25)';
        });
        
        select.addEventListener('blur', function() {
            this.style.borderColor = '';
            this.style.boxShadow = '';
        });
    });
    
    // Enhance form labels
    document.querySelectorAll('.mui-form-label').forEach(label => {
        label.style.color = 'var(--primary-dark-color, #303f9f)';
        label.style.fontWeight = '500';
    });
}

/**
 * Add visual enhancements and subtle animations
 */
function addVisualEnhancements() {
    // Add a subtle entrance animation for cards
    document.querySelectorAll('.mui-model-card').forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
        
        // Stagger the animations slightly
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 100 * index);
    });
    
    // Add visual enhancements to the page header
    const pageHeader = document.querySelector('.mui-page-header');
    if (pageHeader) {
        pageHeader.style.borderBottom = '1px solid rgba(0,0,0,0.08)';
        pageHeader.style.paddingBottom = '1.5rem';
    }
    
    // Enhance helper text styling
    document.querySelectorAll('.mui-helper-text').forEach(helper => {
        helper.style.opacity = '0.75';
        helper.style.fontSize = '0.875rem';
        helper.style.marginTop = '0.5rem';
    });
}

/**
 * Update button icons and ensure proper alignment
 */
function updateButtonIcons() {
    // Ensure all Material Icons in buttons have consistent spacing
    document.querySelectorAll('.mui-button .material-icons').forEach(icon => {
        if (!icon.style.marginRight) {
            icon.style.marginRight = '8px';
        }
    });
    
    // Make sure the predict button has the proper icon
    const predictButton = document.getElementById('predictButton');
    if (predictButton) {
        if (!predictButton.querySelector('.material-icons')) {
            predictButton.innerHTML = '<span class="material-icons" style="margin-right: 8px;">mic</span> Predict';
        }
        
        // Add hover effect
        predictButton.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 6px 12px rgba(0,0,0,0.15)';
        });
        
        predictButton.addEventListener('mouseleave', function() {
            this.style.transform = '';
            this.style.boxShadow = '';
        });
    }
}

/**
 * Set up UI interactions for enhanced user experience
 */
function setupUIInteractions() {
    // Update status indicators for toggles
    const ambientNoiseSwitch = document.getElementById('ambientNoiseSwitch');
    if (ambientNoiseSwitch) {
        ambientNoiseSwitch.addEventListener('change', function() {
            const status = document.getElementById('ambientNoiseStatus');
            if (status) {
                status.textContent = this.checked ? 'On' : 'Off';
                status.style.backgroundColor = this.checked ? 'rgba(76, 175, 80, 0.1)' : 'rgba(0,0,0,0.1)';
                status.style.color = this.checked ? '#4CAF50' : '#666';
            }
        });
    }
    
    const predictionModeToggle = document.getElementById('predictionModeToggle');
    if (predictionModeToggle) {
        predictionModeToggle.addEventListener('change', function() {
            const status = document.getElementById('predictionModeStatus');
            if (status) {
                status.textContent = this.checked ? 'Paused' : 'Continuous';
                status.style.backgroundColor = this.checked ? 'rgba(63, 81, 181, 0.1)' : 'rgba(0,0,0,0.1)';
                status.style.color = this.checked ? '#3F51B5' : '#666';
            }
        });
    }
}

/**
 * Convert any legacy classes that might be present
 */
function convertLegacyClasses() {
    // Convert classes from Bootstrap to MUI
    const classMap = {
        'form-select': 'mui-form-select',
        'form-label': 'mui-form-label',
        'text-danger': 'mui-error-text',
        'text-muted': 'mui-helper-text',
        'btn': 'mui-button',
        'btn-primary': 'mui-button',
        'btn-secondary': 'mui-button-outlined',
        'btn-sm': '',
        'btn-warning': 'mui-debug-button'
    };
    
    // Process each mapping
    Object.entries(classMap).forEach(([oldClass, newClass]) => {
        document.querySelectorAll('.' + oldClass).forEach(el => {
            if (newClass && !el.classList.contains(newClass)) {
                el.classList.add(newClass);
            }
            el.classList.remove(oldClass);
        });
    });
    
    // Convert Bootstrap alerts to MUI alerts
    document.querySelectorAll('.alert').forEach(alert => {
        if (!alert.classList.contains('mui-alert')) {
            alert.classList.add('mui-alert');
            
            if (alert.classList.contains('alert-warning')) {
                alert.classList.add('mui-alert-warning');
                alert.classList.remove('alert-warning');
            } else if (alert.classList.contains('alert-danger')) {
                alert.classList.add('mui-alert-error');
                alert.classList.remove('alert-danger');
            } else if (alert.classList.contains('alert-success')) {
                alert.classList.add('mui-alert-success');
                alert.classList.remove('alert-success');
            } else if (alert.classList.contains('alert-info')) {
                alert.classList.add('mui-alert-info');
                alert.classList.remove('alert-info');
            }
            
            alert.classList.remove('alert');
        }
    });
}

/**
 * Convert elements from old class to new MUI class
 */
function convertElementsToMui(oldClass, newClass) {
    document.querySelectorAll('.' + oldClass).forEach(el => {
        if (!el.classList.contains(newClass)) {
            el.classList.add(newClass);
            el.classList.remove(oldClass);
        }
    });
}

/**
 * Reset listening UI elements to initial state
 */
function resetListeningUI() {
    console.log('📋 DEBUG [predict_ui_core.js]: resetListeningUI START');
    
    const predictButton = document.getElementById('predictButton');
    const listeningIndicator = document.getElementById('listeningIndicator');
    const speechDetectedIndicator = document.getElementById('speechDetectedIndicator');
    const latestPredictionDiv = document.getElementById('latestPrediction');
    const predictionHistoryCard = document.getElementById('predictionHistoryCard');
    const feedbackSection = document.getElementById('feedbackSection');
    
    console.log(` Found elements: predictButton=${!!predictButton}, listeningIndicator=${!!listeningIndicator}, latestPredictionDiv=${!!latestPredictionDiv}, predictionHistoryCard=${!!predictionHistoryCard}, feedbackSection=${!!feedbackSection}`);
    
    if (predictButton) {
        predictButton.innerHTML = '<span class="material-icons" style="margin-right: 8px;">mic</span> Predict'; 
        predictButton.classList.remove('mui-button-danger'); 
        predictButton.disabled = !window.selectedModelId; 
        console.log(' Reset predictButton appearance.');
    }

    if (listeningIndicator) {
        listeningIndicator.style.display = 'none';
        console.log(' Hid listeningIndicator.');
    }
    if (speechDetectedIndicator) {
         speechDetectedIndicator.style.display = 'none';
         console.log(' Hid speechDetectedIndicator.');
    }
    
    // Hide results/feedback sections using display
    if (latestPredictionDiv) {
         latestPredictionDiv.style.display = 'none';
         console.log(` Hid latestPredictionDiv. Display style: ${latestPredictionDiv.style.display}`);
         
         // ADDED: Clear prediction content
         const predictedClass = document.getElementById('predictedClass');
         const confidenceValue = document.getElementById('confidenceValue');
         if (predictedClass) predictedClass.textContent = '';
         if (confidenceValue) confidenceValue.textContent = '';
         console.log(' Cleared prediction text content');
    }
    // CHANGED: Keep prediction history card visible to retain the table
    // Do NOT hide it when session ends
    if (predictionHistoryCard) {
         // predictionHistoryCard.style.display = 'none';  // COMMENTED OUT
         console.log(` Keeping predictionHistoryCard visible to retain output table`);
    }
    if (feedbackSection) {
         feedbackSection.style.display = 'none';
         console.log(` Hid feedbackSection. Display style: ${feedbackSection.style.display}`);
         
         // ADDED: Reset feedback options visibility
         const feedbackOptions = document.getElementById('feedbackOptions');
         if (feedbackOptions) {
             feedbackOptions.style.display = 'block';
             console.log(' Reset feedbackOptions visibility');
         }
    }

    console.log('📋 DEBUG [predict_ui_core.js]: Listening UI reset COMPLETE.');
}

/**
 * Initialize listening UI state
 */
function initializeListeningUI() {
    const predictButton = document.getElementById('predictButton');
    const listeningIndicator = document.getElementById('listeningIndicator');
    
    if (predictButton) {
        predictButton.innerHTML = '<span class="material-icons" style="margin-right: 8px;">stop</span> Stop';
        predictButton.style.backgroundColor = '#f44336';
    }

    if (listeningIndicator) {
        listeningIndicator.style.display = 'flex';
        listeningIndicator.innerHTML = '<span class="material-icons" style="margin-right: 8px;">mic</span> Listening...';
    }
}

/**
 * Show speech detected indicator
 */
function showSpeechDetected(isDetected) {
    const speechDetectedIndicator = document.getElementById('speechDetectedIndicator');
    
    if (speechDetectedIndicator) {
        if (isDetected) {
            speechDetectedIndicator.style.display = 'flex';
            speechDetectedIndicator.innerHTML = '<span class="material-icons" style="margin-right: 8px;">record_voice_over</span> Speech Detected!';
        } else {
            speechDetectedIndicator.style.display = 'none';
        }
    }
}

/**
 * Update sound classes in the UI
 */
function updateSoundClasses(classes) {
    const soundsList = document.getElementById('soundsList');
    if (!soundsList) {
        console.error("Element 'soundsList' not found for updating classes.");
        return;
    }
    soundsList.innerHTML = ''; // Clear previous badges

    console.log('📋 DEBUG [predict_ui_core.js]: Updating sound classes UI with:', classes);

    if (classes && Array.isArray(classes) && classes.length > 0) {
        // Update global list used for display
        window.soundClasses = [...classes]; 
        
        classes.forEach(soundClassId => {
            const badge = document.createElement('span');
            badge.className = 'mui-sound-badge';
            
            // --- Use IdMapper to get the name --- 
            let displayName = soundClassId; // Default to ID
            if (window.IdMapper && typeof window.IdMapper.getClassName === 'function') {
                const mappedName = window.IdMapper.getClassName(soundClassId);
                if (mappedName !== soundClassId) { // Use mapped name only if it's different from ID
                    displayName = mappedName;
                } else {
                     // Optional: Log if mapping didn't find a name, but still use ID
                     console.warn(`IdMapper couldn't find name for class ID: ${soundClassId}`);
                }
            } else {
                // Optional: Log if IdMapper itself isn't available
                 console.warn("IdMapper not available for class name lookup.");
            }
            // --- End IdMapper usage ---
            
            badge.innerHTML = `<span class="material-icons" style="font-size: 16px; margin-right: 4px;">label</span> ${displayName}`; // Use displayName
            badge.dataset.classId = soundClassId; // Store original ID in data attribute if needed
            soundsList.appendChild(badge);
        });
        
        // Show card if it was previously hidden
        const soundClassesCard = document.getElementById('soundClassesCard');
        if (soundClassesCard) {
            soundClassesCard.style.display = 'block';
        }
    } else {
        console.warn('📋 DEBUG [predict_ui_core.js]: No sound classes provided to updateSoundClasses.');
        showNoSoundsWarning();
        window.soundClasses = []; // Reset global list
    }
}

/**
 * Show warning when no sound classes are available
 */
function showNoSoundsWarning() {
    const soundsList = document.getElementById('soundsList');
    if (!soundsList) return;

    soundsList.innerHTML = `
        <div class="mui-alert mui-alert-warning">
            <span class="material-icons">warning</span>
            <span>No sound classes available for the selected model (${window.selectedModelId || 'Unknown'}).</span>
        </div>
    `;
    window.soundClasses = []; // Ensure global list is empty
}

/**
 * Populate dictionary dropdown with available dictionaries
 */
function populateDictionaryDropdown(dictionaries) {
    console.log('📋 DEBUG [predict_ui_core.js]: populateDictionaryDropdown called with', dictionaries.length, 'dictionaries');
    
    // Get select element
    const selectElement = document.getElementById('dictionarySelect');
    const errorElement = document.getElementById('dictionaryLoadingError');
    const modelSelectionCard = document.getElementById('modelSelectionCard');
    
    if (!selectElement) {
        console.error("Dictionary select element 'dictionarySelect' not found.");
        return;
    }
    
    try {
        // Clear current options
        selectElement.innerHTML = '';
        
        // Handle empty dictionary list
        if (!dictionaries || dictionaries.length === 0) {
            selectElement.disabled = true;
            
            // Create default option
            const defaultOption = document.createElement('option');
            defaultOption.textContent = "No dictionaries found.";
            defaultOption.value = "";
            selectElement.appendChild(defaultOption);
            
            if (errorElement) {
                errorElement.textContent = "No dictionaries available for this user.";
                errorElement.style.display = 'block';
                errorElement.className = 'mui-error-text';
            }
            
            if (modelSelectionCard) modelSelectionCard.style.display = 'none';
        } else {
            selectElement.disabled = false;
            
            // Add default option
            const defaultOption = document.createElement('option');
            defaultOption.textContent = "-- Select a Dictionary --";
            defaultOption.value = "";
            defaultOption.selected = true;
            defaultOption.disabled = true;
            selectElement.appendChild(defaultOption);

            // Add each dictionary
            dictionaries.forEach(dict => {
                const option = document.createElement('option');
                option.value = dict.id;
                option.textContent = dict.displayName;
                selectElement.appendChild(option);
            });
            
            // Clear any previous error
            if (errorElement) {
                errorElement.style.display = 'none';
            }
            
            console.log(`📋 DEBUG [predict_ui_core.js]: Populated dictionary dropdown with ${dictionaries.length} options.`);
        }
    } catch (error) {
        console.error('Error populating dropdown:', error);
        if (errorElement) {
            errorElement.textContent = `Error: ${error.message}`;
            errorElement.style.display = 'block';
            errorElement.className = 'mui-error-text';
        }
    }
}

/**
 * Update prediction display with latest result
 */
function updatePredictionDisplay(prediction) {
    // DISABLED: We're using the table for display now, not the popup
    // This prevents duplicate predictions
    return;
    
    /*
    if (!prediction) return;
    
    const predictedClass = document.getElementById('predictedClass');
    const confidenceValue = document.getElementById('confidenceValue');
    const latestPrediction = document.getElementById('latestPrediction');
    
    if (predictedClass && confidenceValue) {
        predictedClass.textContent = prediction.class || 'Unknown';
        confidenceValue.textContent = `${Math.round(prediction.confidence * 100)}% confidence`;
        
        // Show prediction area
        if (latestPrediction) {
            latestPrediction.style.display = 'block';
        }
    }
    */
}

/**
 * Populate model dropdown with available models
 * @param {Array} models - Array of model objects
 */
function populateModelDropdown(models) {
    console.log('📋 DEBUG [predict_ui_core.js]: populateModelDropdown called with', models.length, 'models');
    
    // ADDED: Check if container exists before setTimeout
    const containerCheck = document.getElementById('modelSelectionCard');
    console.log(`>>> populateModelDropdown: Does #modelSelectionCard exist BEFORE setTimeout? ${!!containerCheck}. Display style: ${containerCheck?.style.display}`);

    // RE-ADD Timeout Delay before accessing DOM
    setTimeout(() => {
        console.log('>>> populateModelDropdown: Attempting to get modelSelect element after short delay...');
        const modelSelect = document.getElementById('modelSelect');
        const loadingIndicator = document.getElementById('modelsLoadingMessage');
        const modelInfoCard = document.getElementById('modelInfo');
        
        if (!modelSelect) {
            console.error("Model select element 'modelSelect' not found EVEN AFTER DELAY.");
            return;
        }
        
        // Clear previous options and hide loading indicator
        modelSelect.innerHTML = ''; 
        if (loadingIndicator) loadingIndicator.style.display = 'none';
        modelSelect.disabled = true; // Disable initially
        if (modelInfoCard) modelInfoCard.style.display = 'none'; // Hide model info card
        
        // Handle empty model list
        if (!models || models.length === 0) {
            const defaultOption = document.createElement('option');
            defaultOption.textContent = "No trained models found for this dictionary.";
            defaultOption.value = "";
            defaultOption.selected = true;
            defaultOption.disabled = true;
            modelSelect.appendChild(defaultOption);
            return;
        }
        
        // Add default "Select Model" option
        const defaultOption = document.createElement('option');
        defaultOption.textContent = "-- Select a Model --";
        defaultOption.value = "";
        defaultOption.selected = true;
        defaultOption.disabled = true;
        modelSelect.appendChild(defaultOption);

        // Add each model to the dropdown
        models.forEach((model) => {
            const option = document.createElement('option');
            option.value = model.id; // Use model ID as the value
            
            const modelName = model.name || 'Unnamed Model';
            const modelType = model.type || 'unknown';
            const createdDate = model.created_at ? new Date(model.created_at).toLocaleDateString() : 'Unknown';
            option.textContent = `${modelName} (${modelType}) - Created: ${createdDate}`; // More informative text
            
            modelSelect.appendChild(option);
        });
        
        modelSelect.disabled = false; // Enable dropdown now that it has options
        
        console.log(`📋 DEBUG [predict_ui_core.js]: Populated model dropdown with ${models.length} options.`);
    }, 100); // 100ms delay
}

/**
 * Update the listening indicator UI element
 * @param {boolean} isListening - Whether we are currently listening or not
 */
function updateListeningIndicator(isListening) {
    const listeningIndicator = document.getElementById('listeningIndicator');
    if (!listeningIndicator) {
        console.warn("Element 'listeningIndicator' not found.");
        return;
    }

    if (isListening) {
        listeningIndicator.innerHTML = '<span class="material-icons">hearing</span> Listening...';
        listeningIndicator.style.display = 'block';
    } else {
        listeningIndicator.style.display = 'none';
    }
    console.log(`Updated listening indicator: isListening=${isListening}`);
}

// Export functions to global scope
window.applyMuiStyles = applyMuiStyles;
window.enhanceCardTransitions = enhanceCardTransitions;
window.updateButtonIcons = updateButtonIcons;
window.setupUIInteractions = setupUIInteractions;
window.convertLegacyClasses = convertLegacyClasses;
window.convertElementsToMui = convertElementsToMui;
window.resetListeningUI = resetListeningUI;
window.initializeListeningUI = initializeListeningUI;
window.showSpeechDetected = showSpeechDetected;
window.updateSoundClasses = updateSoundClasses;
window.showNoSoundsWarning = showNoSoundsWarning;
window.populateDictionaryDropdown = populateDictionaryDropdown;
window.populateModelDropdown = populateModelDropdown;
window.updatePredictionDisplay = updatePredictionDisplay;
window.currentPrediction = currentPrediction;
window.activeSound = activeSound;
window.updateListeningIndicator = updateListeningIndicator;

// --- ADDED: Game Mode UI Functions ---

/**
 * Displays the target sound class name for the game mode.
 * @param {string} soundId - The ID of the target sound class.
 */
function displayTargetSound(soundId) {
    const targetElement = document.getElementById('classToSay');
    if (!targetElement) {
        console.error("Element 'classToSay' not found.");
        return;
    }
    
    let displayName = '...'; // Default text
    if (soundId && window.IdMapper) {
        const mapped = window.IdMapper.getClassName(soundId) || soundId;
        displayName = mapped === soundId ? soundId.replace(/^cls_/,'') : mapped;
        console.log(`Displaying target sound: ${displayName} (ID: ${soundId})`);
    } else if (!soundId) {
        console.log("Clearing target sound display.");
    } else {
        console.warn("IdMapper not available, displaying target sound ID.");
        displayName = soundId.replace(/^cls_/,'');
    }
    targetElement.innerHTML = `Say: <span style="color: var(--accent-color);">${displayName}</span>`;
}

/**
 * Shows the specified face and hides others.
 * @param {'neutral'|'happy'|'grimace'} faceType - The type of face to show.
 */
function cleanupFaceArtifactsGlobal() {
    document.querySelectorAll('[data-face-artifact="1"]').forEach(el => {
        try { el.remove(); } catch(e) {}
    });
}

function showFace(faceType) {
    console.log(`>>> showFace CALLED (icon mode) with: ${faceType}`);

    // Replace face visuals with a simple thumbs up/down icon
    const iconHost = document.getElementById('gameFeedbackIcon');
    if (!iconHost) return;
    iconHost.style.display = 'flex';
    iconHost.style.alignItems = 'center';
    iconHost.style.justifyContent = 'center';
    let icon = 'horizontal_rule';
    let color = '#9E9E9E';
    if (faceType === 'happy') { icon = 'thumb_up_alt'; color = '#43A047'; }
    else if (faceType === 'grimace') { icon = 'thumb_down_alt'; color = '#E53935'; }
    else { icon = 'horizontal_rule'; color = '#9E9E9E'; }
    iconHost.innerHTML = `<span class="material-icons" style="font-size:96px; color:${color};">${icon}</span>`;
}

// Export new functions
window.displayTargetSound = displayTargetSound;
window.showFace = showFace;
window.cleanupFaceArtifactsGlobal = cleanupFaceArtifactsGlobal;
// --- END ADDED --- 

// Add a global interval checker for face elements
let faceHeightCheckInterval = null;

/**
 * Starts a monitoring interval that aggressively ensures face elements maintain their height
 */
function startFaceHeightMonitoring() {
    console.log(">>> Starting aggressive face height monitoring...");
    
    // Clear any existing interval first
    if (faceHeightCheckInterval) {
        clearInterval(faceHeightCheckInterval);
    }
    
    // Set an interval to check and fix face container height every 100ms
    faceHeightCheckInterval = setInterval(() => {
        const faceContainer = document.getElementById('faceContainer');
        
        // If container doesn't exist OR is too small, recreate the face
        if (!faceContainer || faceContainer.offsetHeight < 100 || faceContainer.offsetWidth < 100) {
            console.log(`>>> FACE MISSING OR TOO SMALL: offsetHeight=${faceContainer?.offsetHeight}, offsetWidth=${faceContainer?.offsetWidth}`);
            
            // Recreate with current face type, default to neutral if none is active
            let activeFaceType = 'neutral';
            
            // Check if we're in the prediction response flow (game check)
            if (window.currentGameModeActive && window.currentGameTargetClassId) {
                // If we can determine if the prediction was correct/incorrect
                if (window.currentPrediction && window.currentPrediction.class_id) {
                    const isCorrect = window.currentPrediction.class_id === window.currentGameTargetClassId;
                    activeFaceType = isCorrect ? 'happy' : 'grimace';
                }
            }
            
            // Call our enhanced showFace function to recreate the face
            if (typeof window.showFace === 'function') {
                window.showFace(activeFaceType);
                console.log(`>>> Recreated ${activeFaceType} face due to missing/small container`);
            }
        }
    }, 100);
    
    console.log(">>> Face height monitoring interval started");
}

/**
 * Stops the face height monitoring interval
 */
function stopFaceHeightMonitoring() {
    if (faceHeightCheckInterval) {
        clearInterval(faceHeightCheckInterval);
        faceHeightCheckInterval = null;
        console.log(">>> Face height monitoring stopped");
    }
}

// Export additional functions
window.startFaceHeightMonitoring = startFaceHeightMonitoring;
window.stopFaceHeightMonitoring = stopFaceHeightMonitoring; 