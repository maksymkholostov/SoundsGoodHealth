/**
 * predict_feedback.js
 * Handles feedback collection, confusion matrix display, and statistics
 */

// Tracking variables for statistics
let confusionMatrix = {}; // Initialize as empty object
let totalPredictions = 0;
let correctPredictions = 0;

/**
 * Updates feedback options with direct-click buttons
 */
function updateFeedbackOptions() {
    try {
        console.log('>>> updateFeedbackOptions: STARTING with aggressive container recreation approach');
        
        // Get reference to parent container for later insertion
        let feedbackForm = document.getElementById('feedbackForm');
        if (!feedbackForm) {
            console.warn("Feedback form container 'feedbackForm' not found. Looking for fallback container.");
            // Try to find a suitable container
            const feedbackSection = document.getElementById('feedbackSection');
            if (feedbackSection) {
                // Create the feedback form if it doesn't exist
                feedbackForm = document.createElement('div');
                feedbackForm.id = 'feedbackForm';
                feedbackForm.className = 'mui-feedback-form';
                feedbackSection.appendChild(feedbackForm);
                console.log("Created missing feedbackForm container inside feedbackSection");
            } else {
                console.error("Could not find or create a suitable parent container for feedback options");
                return;
            }
        }
        
        // Find container, but we'll recreate it regardless
        const existingContainer = document.getElementById('feedbackOptions');
        if (existingContainer) {
            try {
                existingContainer.parentNode.removeChild(existingContainer);
                console.log(">>> Removed existing feedbackOptions container to recreate it");
            } catch (e) {
                console.error(">>> Error removing feedbackOptions:", e);
            }
        }
        
        // Create a brand new container with the same ID
        const feedbackOptionsContainer = document.createElement('div');
        feedbackOptionsContainer.id = 'feedbackOptions';
        feedbackOptionsContainer.className = 'mui-feedback-options';
        feedbackOptionsContainer.setAttribute('style', 'display: block !important; visibility: visible !important; min-height: 50px !important;');
        
        // Insert at the beginning of the form
        if (feedbackForm.firstChild) {
            feedbackForm.insertBefore(feedbackOptionsContainer, feedbackForm.firstChild);
        } else {
            feedbackForm.appendChild(feedbackOptionsContainer);
        }
        console.log(">>> Created and inserted new feedbackOptions container");

        // --- Use the correct global list, populated based on the selected model --- 
        const classesForFeedback = window.globalClassNamesForFeedback || []; // Use the list set by API/UI core
        console.log("updateFeedbackOptions: Using classes for feedback:", classesForFeedback);
        // --- End Use Correct List --- 

        if (classesForFeedback && classesForFeedback.length > 0) {
            console.log(`📋 DEBUG [predict_feedback.js]: Populating feedback options with ${classesForFeedback.length} classes.`);
            
            // Create a container for buttons
            const buttonsContainer = document.createElement('div');
            buttonsContainer.className = 'feedback-buttons';
            buttonsContainer.setAttribute('style', 'display: flex !important; gap: 10px !important; margin-top: 10px !important; flex-wrap: wrap !important;');
            
            // Add label
            const labelEl = document.createElement('div');
            labelEl.textContent = 'Which sound did you make?';
            labelEl.setAttribute('style', 'font-weight: bold !important; margin-bottom: 10px !important; display: block !important;');
            feedbackOptionsContainer.appendChild(labelEl);
            
            try {
                // Sort classes (with error handling)
                let sortedClasses = [...classesForFeedback]; // Make a copy
                try {
                    sortedClasses.sort((idA, idB) => { 
                        const nameA = window.IdMapper?.getClassName(idA) || idA;
                        const nameB = window.IdMapper?.getClassName(idB) || idB;
                        return nameA.localeCompare(nameB);
                    });
                } catch (sortError) {
                    console.warn("Error sorting class names, using unsorted list:", sortError);
                }
                
                // Create buttons for each class
                sortedClasses.forEach(soundClassId => { 
                    try {
                        const button = document.createElement('button');
                        // Look up display name using IdMapper 
                        let displayName = soundClassId; 
                        if (window.IdMapper && typeof window.IdMapper.getClassName === 'function') {
                            try {
                                const mappedName = window.IdMapper.getClassName(soundClassId);
                                displayName = mappedName !== soundClassId ? mappedName : soundClassId;
                            } catch (nameError) {
                                console.warn(`Error getting class name for ${soundClassId}:`, nameError);
                            }
                        } else {
                            console.warn("IdMapper not available for feedback button name lookup.");
                        }
                        
                        button.textContent = displayName; 
                        button.className = 'mui-button feedback-sound-btn';
                        button.dataset.sound = soundClassId; 
                        button.setAttribute('style', 'min-width: 60px !important; margin: 5px !important; display: inline-block !important;');
                        
                        button.addEventListener('click', function(event) {
                            event.preventDefault();
                            try {
                                handleDirectFeedback(soundClassId);
                            } catch (clickError) {
                                console.error(`Error handling click for ${soundClassId}:`, clickError);
                            }
                        });
                        
                        buttonsContainer.appendChild(button);
                    } catch (buttonError) {
                        console.error(`Error creating button for ${soundClassId}:`, buttonError);
                    }
                });
            } catch (loopError) {
                console.error("Error during button creation loop:", loopError);
                // Add fallback message to indicate error
                const errorMsg = document.createElement('p');
                errorMsg.textContent = "Error loading feedback options. Please try again.";
                errorMsg.style.color = 'red';
                feedbackOptionsContainer.appendChild(errorMsg);
            }
            
            // --- Add Skip Button --- 
            try {
                const skipButton = document.createElement('button');
                skipButton.textContent = 'Skip';
                skipButton.className = 'mui-button mui-button-secondary feedback-skip-btn'; // Use secondary style
                skipButton.setAttribute('style', 'margin-left: auto !important; display: inline-block !important;');
                
                skipButton.addEventListener('click', function(event) {
                    event.preventDefault();
                    try {
                        handleSkipFeedback(); // Call the new handler
                    } catch (skipError) {
                        console.error("Error handling skip:", skipError);
                        // Fallback if handler fails
                        if (window.resumeListeningAfterFeedback) {
                            window.resumeListeningAfterFeedback();
                        }
                    }
                });
                buttonsContainer.appendChild(skipButton);
            } catch (skipButtonError) {
                console.error("Error creating skip button:", skipButtonError);
            }
            // --- END Skip Button --- 
            
            feedbackOptionsContainer.appendChild(buttonsContainer);
            console.log(`>>> updateFeedbackOptions: Appended buttonsContainer to feedbackOptionsContainer. Child count: ${feedbackOptionsContainer.childElementCount}`);
        } else {
            console.log('📋 DEBUG [predict_feedback.js]: No sound classes available in globalClassNamesForFeedback to populate feedback options.');
            const noClassesMessage = document.createElement('p');
            noClassesMessage.className = 'text-muted';
            noClassesMessage.textContent = 'No relevant classes found for feedback.';
            feedbackOptionsContainer.appendChild(noClassesMessage);
        }
        
        console.log('>>> updateFeedbackOptions: FINISHING with newly created container.');

        // Create container for confusion matrix if it doesn't exist (keep this part as-is)
        if (!document.getElementById('confusionMatrixContainer')) {
            try {
                const matrixContainer = document.createElement('div');
                matrixContainer.id = 'confusionMatrixContainer';
                matrixContainer.className = 'mui-confusion-matrix-container';
                matrixContainer.style.marginTop = '20px';
                matrixContainer.style.display = 'none'; // Initially hidden until we have data
                
                const matrixTitle = document.createElement('h4');
                matrixTitle.textContent = 'Confusion Matrix & Statistics';
                matrixTitle.style.fontSize = '16px';
                matrixContainer.appendChild(matrixTitle);
                
                const table = document.createElement('table');
                table.className = 'mui-table mui-confusion-matrix';
                table.style.width = '100%';
                table.style.borderCollapse = 'collapse';
                table.style.marginTop = '10px';
                table.style.marginBottom = '10px';
                
                // Add table header
                const thead = document.createElement('thead');
                thead.id = 'confusionMatrixThead';
                table.appendChild(thead);
                
                // Add table body
                const tbody = document.createElement('tbody');
                tbody.id = 'confusionMatrixTbody';
                table.appendChild(tbody);
                
                matrixContainer.appendChild(table);
                
                // Add statistics display
                const statsDiv = document.createElement('div');
                statsDiv.id = 'predictionStats';
                statsDiv.className = 'mui-prediction-stats';
                statsDiv.style.marginTop = '10px';
                statsDiv.style.fontSize = '14px';
                matrixContainer.appendChild(statsDiv);
                
                // Find a suitable parent for the confusion matrix
                let matrixParent = null;
                
                // First try to find the predictionHistoryCard's parent
                const predictionHistoryCard = document.getElementById('predictionHistoryCard');
                if (predictionHistoryCard && predictionHistoryCard.parentNode) {
                    matrixParent = predictionHistoryCard.parentNode;
                }
                
                // If that doesn't work, try the main predictor container
                if (!matrixParent) {
                    matrixParent = document.getElementById('predictorInterfaceCard') || 
                                  document.getElementById('predictor-container') ||
                                  document.querySelector('.mui-card');
                }
                
                // Fallback to body if nothing else works
                if (!matrixParent) {
                    matrixParent = document.body;
                }
                
                // Add to DOM in the appropriate location
                matrixParent.appendChild(matrixContainer);
                console.log("Created confusion matrix container and added to:", matrixParent.id || matrixParent.className || "unknown parent");
            } catch (matrixError) {
                console.error("Error creating confusion matrix:", matrixError);
            }
        }
    } catch (mainError) {
        console.error("Critical error in updateFeedbackOptions:", mainError);
        // Try to show an error message
        try {
            const feedbackSection = document.getElementById('feedbackSection');
            if (feedbackSection) {
                feedbackSection.innerHTML = '<div style="color: red; padding: 10px;">Error loading feedback options. Please refresh the page.</div>';
            }
        } catch (e) {
            // Last resort - we tried our best
        }
    }
}

/**
 * Handles direct feedback when a sound button is clicked
 */
function handleDirectFeedback(actualSoundId) {
    console.log(`--- handleDirectFeedback called with actualSoundId: ${actualSoundId} ---`);

    if (!window.currentPrediction || !window.currentPrediction.class_id) {
        console.error("Cannot submit feedback: No valid current prediction available");
        showFeedbackMessage('error', 'No prediction to provide feedback for');
        return;
    }

    const predictedSoundId = window.currentPrediction.class_id;
    // Lookup names for logging/display, fallback to ID if lookup fails
    const predictedSoundName = window.IdMapper?.getClassName(predictedSoundId) || predictedSoundId;
    const actualSoundName = window.IdMapper?.getClassName(actualSoundId) || actualSoundId;

    const isCorrect = predictedSoundId === actualSoundId; // Compare IDs
    console.log(`Feedback recorded: Predicted ID=${predictedSoundId}, Actual ID=${actualSoundId}, Correct=${isCorrect}`);

    // --- Update confusion matrix using IDs as keys ---
    if (!confusionMatrix[actualSoundId]) {
        confusionMatrix[actualSoundId] = {};
        console.log(`Initializing confusion matrix row for actual ID: ${actualSoundId}`);
    }
    if (confusionMatrix[actualSoundId][predictedSoundId] === undefined) {
        confusionMatrix[actualSoundId][predictedSoundId] = 0;
        console.log(`Initializing confusion matrix cell for actual ID: ${actualSoundId}, predicted ID: ${predictedSoundId}`);
    }
    confusionMatrix[actualSoundId][predictedSoundId]++;
    console.log("Updated confusionMatrix:", JSON.stringify(confusionMatrix)); // Log matrix state
    console.log("Confusion matrix updated.");
    // --- End Update confusion matrix ---

    // Update statistics
    totalPredictions++;
    if (isCorrect) {
        correctPredictions++;
    }
    console.log(`Stats updated: Total=${totalPredictions}, Correct=${correctPredictions}`);

    // Update UI elements (pass IDs where appropriate, names for display)
    updateHistoryItemWithFeedback(predictedSoundId, actualSoundId); // Pass IDs
    updateConfusionMatrix(); // Will now use ID-based matrix keys
    
    // --- Show the confusion matrix explicitly ---
    const confusionMatrixContainer = document.getElementById('confusionMatrixContainer');
    if (confusionMatrixContainer) {
        confusionMatrixContainer.style.display = 'block';
        console.log("Explicitly showing confusion matrix");
    }
    
    // --- Hide the Latest Prediction display ---
    const latestPredictionDiv = document.getElementById('latestPrediction');
    if (latestPredictionDiv) {
        latestPredictionDiv.style.display = 'none';
        console.log("Hide the Latest Prediction display");
    }
    
    // --- Hide feedback options ---
    const feedbackOptionsEl = document.getElementById('feedbackOptions');
    if (feedbackOptionsEl) {
        feedbackOptionsEl.style.display = 'none'; // Hide the buttons
        // IMPORTANT: Clear the container to prevent duplicate/recycled buttons
        feedbackOptionsEl.innerHTML = '';
        console.log("Hid and cleared feedback options buttons after selection.");
    }
    
    // --- Create and display the new feedback message ---
    const feedbackSection = document.getElementById('feedbackSection');
    if (feedbackSection) {
        // Clear any existing content
        feedbackSection.innerHTML = '';
        
        // Create new message container
        const feedbackMessageContainer = document.createElement('div');
        feedbackMessageContainer.className = 'mui-feedback-result';
        feedbackMessageContainer.style.padding = '15px';
        feedbackMessageContainer.style.marginTop = '10px';
        feedbackMessageContainer.style.border = '1px solid #eee';
        feedbackMessageContainer.style.borderRadius = '5px';
        feedbackMessageContainer.style.backgroundColor = isCorrect ? 'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)';
        
        // Format confidence value
        const confidenceValue = window.currentPrediction.confidence !== undefined ? 
            `${(window.currentPrediction.confidence * 100).toFixed(1)}%` : 'unknown';
        
        // Set feedback text based on correctness
        if (isCorrect) {
            feedbackMessageContainer.innerHTML = `
                <p style="font-size: 16px; margin-bottom: 10px;">
                    <strong>We were right!</strong> Thank you for pronouncing the word 
                    <strong>${actualSoundName}</strong> so clearly! We guessed it correctly 
                    with a confidence of <strong>${confidenceValue}</strong>.
                </p>
            `;
        } else {
            feedbackMessageContainer.innerHTML = `
                <p style="font-size: 16px; margin-bottom: 10px;">
                    <strong>We were wrong!</strong> You said <strong>${actualSoundName}</strong>
                    but we thought it was <strong>${predictedSoundName}</strong> with a 
                    confidence of <strong>${confidenceValue}</strong>.
                </p>
            `;
        }
        
        // Add the instruction for continuing
        const continueInstructions = document.createElement('p');
        continueInstructions.style.marginTop = '15px';
        continueInstructions.innerHTML = 'Please <strong>press SPACE</strong> to try again, or click <strong>End Session</strong> to start over.';
        feedbackMessageContainer.appendChild(continueInstructions);
        
        // Add to the feedback section
        feedbackSection.appendChild(feedbackMessageContainer);
        feedbackSection.style.display = 'block';
        feedbackSection.style.visibility = 'visible';
        
        console.log(`Created and displayed detailed ${isCorrect ? 'success' : 'error'} feedback message.`);
    } else {
        console.warn("Element 'feedbackSection' not found.");
    }
    
    // --- Make sure stats & prediction history remain visible ---
    const predictionHistoryCard = document.getElementById('predictionHistoryCard');
    if (predictionHistoryCard) {
        predictionHistoryCard.style.display = 'block';
        console.log("Ensuring prediction history remains visible");
    }
    
    // --- Update indicator for SPACE continuation ---
    console.log(`Checking prompt condition: pauseForFeedback=${window.pauseForFeedback}, isWaitingForFeedback=${window.isWaitingForFeedback}`);
    if (window.pauseForFeedback && window.isWaitingForFeedback) {
        // Update main indicator text
        const listeningIndicator = document.getElementById('listeningIndicator');
        if(listeningIndicator) {
            listeningIndicator.innerHTML = '<span class="material-icons">pause_circle_outline</span><strong>Press SPACE to continue listening.</strong>';
            listeningIndicator.style.display = 'block';
            // Make it more noticeable
            listeningIndicator.style.backgroundColor = 'rgba(33, 150, 243, 0.2)';
            listeningIndicator.style.padding = '10px';
            listeningIndicator.style.fontWeight = 'bold';
            console.log("Updated listeningIndicator to prompt for SPACE.");
        }
        
        // Ensure isWaitingForFeedback remains true
        window.isWaitingForFeedback = true;
        
        // Completely cancel any pending feedback options updates
        if (window.feedbackOptionsTimeout) {
            clearTimeout(window.feedbackOptionsTimeout);
            window.feedbackOptionsTimeout = null;
            console.log("Cleared any pending feedback options timeouts.");
        }
    } else {
        console.log("Conditions NOT met for prompting (e.g., not in feedback mode).");
    }
    
    // --- Set focus back to the main predictor card for spacebar --- 
    const predictorCard = document.getElementById('predictorInterfaceCard');
    if(predictorCard) {
        predictorCard.focus(); // Try focusing the card
        console.log("Set focus to predictorInterfaceCard.");
    } else {
        document.body.focus(); // Fallback to body
        console.log("Set focus to document body (fallback).");
    }
    
    console.log("--- handleDirectFeedback finished. ---");
}

/**
 * Updates the confusion matrix display with current statistics
 */
function updateConfusionMatrix() {
    const matrixContainer = document.getElementById('confusionMatrixContainer');
    const matrixTbody = document.getElementById('confusionMatrixTbody');
    const matrixThead = document.getElementById('confusionMatrixThead');
    const statsDiv = document.getElementById('predictionStats');
    
    if (!matrixContainer || !matrixTbody || !matrixThead || !statsDiv) {
        console.warn('Confusion matrix elements not found');
        return;
    }
    
    // --- Get all unique class IDs involved ---
    const actualIds = Object.keys(confusionMatrix);
    let predictedIdsSet = new Set();
    actualIds.forEach(actualId => {
        // Ensure the row itself is an object before trying to get its keys
        if (confusionMatrix[actualId] && typeof confusionMatrix[actualId] === 'object') {
             Object.keys(confusionMatrix[actualId]).forEach(predictedId => {
                predictedIdsSet.add(predictedId);
            });
        }
    });
    const allInvolvedIds = Array.from(new Set([...actualIds, ...Array.from(predictedIdsSet)]));
    allInvolvedIds.sort(); // Sort IDs for consistent order

    if (allInvolvedIds.length === 0) {
        console.log("No data yet for confusion matrix.");
        matrixContainer.style.display = 'none'; // Hide if no data
        return;
    }

    // --- Data exists, show container ---
    matrixContainer.style.display = 'block';
    console.log("Updating Confusion Matrix UI with IDs:", allInvolvedIds);

    // --- Ensure container is visible in appropriate location ---
    const predictionHistoryCard = document.getElementById('predictionHistoryCard');
    if (predictionHistoryCard && predictionHistoryCard.parentNode) {
        if (!predictionHistoryCard.parentNode.contains(matrixContainer)) {
            // If confusion matrix is not already in DOM at correct location, move it there
            predictionHistoryCard.parentNode.appendChild(matrixContainer);
            console.log("Moved confusion matrix container to be next to prediction history");
        }
        // Make sure prediction history is visible
        predictionHistoryCard.style.display = 'block';
    }

    // --- Update header row (using names) ---
    matrixThead.innerHTML = ''; // Clear previous header
    const headerRow = document.createElement('tr');
    // Add the top-left empty cell label
    const thCorner = document.createElement('th');
    thCorner.innerHTML = 'Actual &darr; / Predicted &rarr;'; // Use HTML arrows
    thCorner.style.textAlign = 'right'; // Align label
    headerRow.appendChild(thCorner);

    // Add predicted class names to header
    allInvolvedIds.forEach(predictedId => {
        const th = document.createElement('th');
        th.textContent = window.IdMapper?.getClassName(predictedId) || predictedId; // Lookup name
        th.className = 'matrix-header-predicted';
        headerRow.appendChild(th);
    });
    matrixThead.appendChild(headerRow);

    // --- Update data rows (using names for row headers) ---
    matrixTbody.innerHTML = ''; // Clear previous body
    allInvolvedIds.forEach(actualId => {
        const row = document.createElement('tr');
        const actualHeader = document.createElement('th'); // Use <th> for row headers too
        actualHeader.textContent = window.IdMapper?.getClassName(actualId) || actualId; // Lookup name
        actualHeader.className = 'matrix-header-actual';
        row.appendChild(actualHeader);

        // Add counts for each predicted class in this row
        allInvolvedIds.forEach(predictedId => {
            const cell = document.createElement('td');
            // Safely access the count using IDs
            const count = confusionMatrix[actualId]?.[predictedId] || 0;
            cell.textContent = count;
            cell.className = 'matrix-cell'; // Add class for potential styling

            // Style based on correct/incorrect
            if (actualId === predictedId) {
                cell.classList.add('matrix-cell-correct'); // Green for correct predictions
            } else if (count > 0) {
                 cell.classList.add('matrix-cell-incorrect'); // Red for incorrect predictions
            }

            row.appendChild(cell);
        });

        matrixTbody.appendChild(row);
    });

    // Update statistics
    const accuracy = totalPredictions > 0 ? (correctPredictions / totalPredictions) * 100 : 0;
    statsDiv.innerHTML = `
        <div class="mui-stat-item"><strong>Total Predictions:</strong> ${totalPredictions}</div>
        <div class="mui-stat-item"><strong>Correct Predictions:</strong> ${correctPredictions}</div>
        <div class="mui-stat-item"><strong>Accuracy:</strong> ${accuracy.toFixed(1)}%</div>
    `;
    console.log(`Stats updated: Total=${totalPredictions}, Correct=${correctPredictions}, Accuracy=${accuracy.toFixed(1)}%`);
}

/**
 * Shows a feedback message (correct/incorrect)
 * @param {string} message - The message to display
 * @param {string} type - The type of message (success/error)
 */
function showFeedbackMessage(message, type = 'success') {
    const container = document.getElementById('feedbackMessage');
    if (!container) return;
    
    // Clear any existing messages
    while (container.firstChild && container.contains(container.firstChild)) {
        container.removeChild(container.firstChild);
    }
    
    const messageEl = document.createElement('div');
    messageEl.className = `feedback-message ${type}`;
    messageEl.textContent = message;
    container.appendChild(messageEl);
    
    // Auto-clear after 3 seconds
    setTimeout(() => {
        if (container && messageEl && container.contains(messageEl)) {
            container.removeChild(messageEl);
        }
    }, 3000);
}

/**
 * Updates history item with feedback results
 */
function updateHistoryItemWithFeedback(predictedClassId, actualClassId) { // Use IDs
    const predictionHistoryList = document.getElementById('predictionHistory');
    // Find the history item corresponding to the current prediction ID
    // Need a way to link feedback to the specific history item. Add prediction ID to history item?
    // For now, assume it's the *last* item (most recent prediction)
    if (!predictionHistoryList || predictionHistoryList.children.length === 0) {
        console.warn("Prediction history list is empty, cannot update feedback.");
        return;
    }

    const lastItem = predictionHistoryList.firstElementChild;
    if (!lastItem) {
        console.warn("Could not find first element child in prediction history list.");
        return;
    }
    
    const feedbackDisplay = lastItem.querySelector('.feedback-display');
    // Ensure the history item has the prediction ID stored, e.g., in a data attribute
    const historyPredictionId = lastItem.dataset.predictionId; // Assumes prediction ID was stored when item was created

    if (!historyPredictionId) {
         console.warn("History item missing 'data-prediction-id', cannot reliably match feedback. Updating last item anyway.");
         // Proceed to update last item as fallback, but log the prediction ID mismatch risk
    } else if (historyPredictionId !== window.currentPrediction?.prediction_id) { // Requires prediction_id in currentPrediction
        console.warn(`History item ID (${historyPredictionId}) doesn't match current prediction ID (${window.currentPrediction?.prediction_id}). Feedback might be misaligned.`);
         // Don't update if IDs don't match? Or still update last item? Sticking with updating last item for now.
    }


    if (feedbackDisplay) {
        const isCorrect = predictedClassId === actualClassId;
        
        // Convert class IDs to human-readable names using IdMapper
        let predictedClassName = predictedClassId;
        let actualClassName = actualClassId;
        
        if (window.IdMapper && typeof window.IdMapper.getClassName === 'function') {
            const mappedPredicted = window.IdMapper.getClassName(predictedClassId);
            const mappedActual = window.IdMapper.getClassName(actualClassId);
            
            if (mappedPredicted) predictedClassName = mappedPredicted;
            if (mappedActual) actualClassName = mappedActual;
            
            console.log(`Using mapped names for feedback - Predicted: ${predictedClassName}, Actual: ${actualClassName}`);
        }
        
        feedbackDisplay.innerHTML = `
            <span class="mui-chip ${isCorrect ? 'mui-chip-success' : 'mui-chip-error'}">
                ${isCorrect ? 
                    '<span class="material-icons">check</span> Correct' : 
                    `<span class="material-icons">close</span> Incorrect (was: ${actualClassName})`}
            </span>
        `;
        console.log(`Updated history item feedback: ${isCorrect ? 'Correct' : 'Incorrect, actual was ' + actualClassName}`);
    } else {
         console.warn('Could not find feedback display element in the last history item.');
    }
}

/**
 * Simplified handler for the submit feedback button (backward compatibility)
 */
function submitFeedback(event) {
    if (event) event.preventDefault();
    
    console.log('submitFeedback: Checking for selected feedback option');
    
    // Check if any radio button is selected (for backward compatibility)
    const selectedOption = document.querySelector('input[name="feedbackSound"]:checked');
    if (selectedOption) {
        handleDirectFeedback(selectedOption.value);
    } else {
        console.warn('No feedback option selected');
        showFeedbackMessage('error', 'Please select which sound you made');
    }
}

/**
 * Resets the feedback form
 */
function resetFeedbackForm() {
    console.log('📋 DEBUG [predict_feedback.js]: Resetting feedback form.');
    document.querySelectorAll('input[name="feedbackSound"]').forEach(input => {
        input.checked = false;
    });
    const submitBtn = document.getElementById('submitFeedbackBtn');
    if (submitBtn) submitBtn.disabled = true;
    
    const feedbackForm = document.querySelector('.mui-feedback-form');
    if (feedbackForm) {
        const existingAlert = feedbackForm.querySelector('.mui-alert');
        if (existingAlert) {
            feedbackForm.removeChild(existingAlert);
        }
    }
}

// --- ADDED: Handler for Skip Button --- 
/**
 * Handles the skip feedback action
 */
function handleSkipFeedback() {
    console.log("--- handleSkipFeedback called --- ");
    
    // Simply resume listening without recording feedback
    if (window.pauseForFeedback && window.isWaitingForFeedback && typeof window.resumeListeningAfterFeedback === 'function') {
        console.log("Skip button pressed. Calling resumeListeningAfterFeedback().");
        window.resumeListeningAfterFeedback(); 
    } else {
         console.log("Conditions NOT met for resuming via skip (e.g., not in feedback mode).");
    }
    
    console.log("--- handleSkipFeedback finished --- ");
}
// --- END ADDED --- 

// Export functions to global scope
window.updateFeedbackOptions = updateFeedbackOptions;
window.handleDirectFeedback = handleDirectFeedback;
window.updateConfusionMatrix = updateConfusionMatrix;
window.showFeedbackMessage = showFeedbackMessage;
window.updateHistoryItemWithFeedback = updateHistoryItemWithFeedback;
window.submitFeedback = submitFeedback;
window.resetFeedbackForm = resetFeedbackForm;
window.handleSkipFeedback = handleSkipFeedback; // Export new handler

// Add feedback options monitoring system, similar to face monitoring
let feedbackOptionsMonitorInterval = null;

/**
 * Starts monitoring to ensure feedback options always render
 */
function startFeedbackOptionsMonitoring() {
    console.log(">>> Feedback options monitoring disabled - causing too many console errors");
    return;  // Disable monitoring entirely as it's causing too many console errors
    
    // Original code below is disabled
    /*
    console.log(">>> Starting aggressive feedback options monitoring");
    
    // Clear any existing interval
    if (feedbackOptionsMonitorInterval) {
        clearInterval(feedbackOptionsMonitorInterval);
    }
    
    // Set interval to check feedback options
    feedbackOptionsMonitorInterval = setInterval(() => {
        // Only monitor when feedback is expected to be visible
        if (window.pauseForFeedback && window.isWaitingForFeedback) {
            const feedbackSection = document.getElementById('feedbackSection');
            const feedbackOptions = document.getElementById('feedbackOptions');
            
            // Check if feedback section is visible but options are missing or empty
            if (feedbackSection && 
                (!feedbackOptions || 
                 feedbackOptions.offsetHeight < 30 ||
                 feedbackOptions.children.length === 0)) {
                console.log('>>> FEEDBACK OPTIONS MISSING OR TOO SMALL: Recreating...');
                
                // Force section to be visible
                feedbackSection.style.display = 'block';
                feedbackSection.style.visibility = 'visible';
                
                // Recreate options
                if (typeof updateFeedbackOptions === 'function') {
                    updateFeedbackOptions();
                    console.log('>>> Recreated feedback options through monitoring');
                }
            }
        }
    }, 200); // Check slightly faster than the face monitor
    
    console.log(">>> Feedback options monitoring started");
    */
}

/**
 * Stops feedback options monitoring
 */
function stopFeedbackOptionsMonitoring() {
    if (feedbackOptionsMonitorInterval) {
        clearInterval(feedbackOptionsMonitorInterval);
        feedbackOptionsMonitorInterval = null;
        console.log(">>> Feedback options monitoring stopped");
    }
}

// Export monitoring functions
window.startFeedbackOptionsMonitoring = startFeedbackOptionsMonitoring;
window.stopFeedbackOptionsMonitoring = stopFeedbackOptionsMonitoring; 