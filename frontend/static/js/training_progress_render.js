// --- UI Rendering for Training Progress and Errors ---

function addTrainingStep(step, isCompleted = false, details = '') {
    const stepsList = document.getElementById('trainingStepsList');
    if (!stepsList) return null;

    const stepItem = document.createElement('div');
    stepItem.className = `list-group-item list-group-item-action d-flex align-items-start ${isCompleted ? 'list-group-item-success' : 'list-group-item-primary'}`;

    const iconClass = isCompleted ? 'text-success' : 'text-primary spin';
    const iconName = isCompleted ? 'check_circle' : 'autorenew';

    stepItem.innerHTML = `
        <span class="material-icons me-2 ${iconClass}">${iconName}</span>
        <div class="flex-grow-1">
            ${step}
            ${details ? `<div class="mt-1 small text-muted">${details}</div>` : ''}
        </div>
    `;

    stepsList.appendChild(stepItem);
    return stepItem; // Return the created element
}

function updateTrainingStep(stepElement, isCompleted = true, newDetails = '', isError = false) {
     if (!stepElement) return;

     const iconElement = stepElement.querySelector('.material-icons');
     const detailsContainer = stepElement.querySelector('.flex-grow-1');
     let detailsElement = detailsContainer ? detailsContainer.querySelector('.small.text-muted') : null;

     // Update Classes
     stepElement.classList.remove('list-group-item-primary', 'list-group-item-success', 'list-group-item-danger', 'list-group-item-secondary');
     if (isError) {
         stepElement.classList.add('list-group-item-danger');
     } else if (isCompleted) {
         stepElement.classList.add('list-group-item-success');
     } else {
          // Should not happen if called correctly, but fallback to primary if active
          stepElement.classList.add('list-group-item-primary');
     }


     // Update Icon
     if (iconElement) {
         iconElement.classList.remove('text-primary', 'text-success', 'text-danger', 'text-muted', 'spin');
         if (isError) {
             iconElement.textContent = 'error';
             iconElement.classList.add('text-danger');
         } else if (isCompleted) {
             iconElement.textContent = 'check_circle';
             iconElement.classList.add('text-success');
         } else {
              iconElement.textContent = 'autorenew'; // Still in progress (shouldn't happen here?)
              iconElement.classList.add('text-primary', 'spin');
         }
     }

     // Update Details
     if (detailsContainer) {
          if (newDetails) {
             if (detailsElement) {
                 detailsElement.innerHTML = newDetails; // Use innerHTML for potential formatting
             } else {
                 // Create details element if it doesn't exist
                 const newDetailsDiv = document.createElement('div');
                 newDetailsDiv.className = 'mt-1 small text-muted';
                 newDetailsDiv.innerHTML = newDetails;
                 detailsContainer.appendChild(newDetailsDiv);
             }
         } else if (detailsElement) {
              // Remove details element if newDetails is empty/null
              detailsElement.remove();
         }
     }
 }

function updateTrainingStepsFromStats(stats, isCompleted = false) {
     // Phase mapping to step text/icons (keep consistent)
     const phaseMap = {
         'Initialization': { text: 'Training Initialization', icon: 'settings' },
         'Data Preparation': { text: 'Data Preparation', icon: 'inventory_2' },
         'Data Augmentation': { text: 'Data Augmentation', icon: 'auto_fix_high' },
         'Model Building': { text: 'Model Building', icon: 'build' },
         'Training Epochs': { text: 'Model Training', icon: 'model_training' },
         'Validation': { text: 'Model Validation', icon: 'fact_check' },
         'Saving': { text: 'Model Saving', icon: 'save' },
         'Completed': { text: 'Training Completed', icon: 'check_circle' },
         'Error': { text: 'Training Error', icon: 'error' }
     };

     const currentPhase = stats.status_phase || 'Initialization';
     const stepsList = document.getElementById('trainingStepsList');
     if (!stepsList) return;

     // Determine expected phases based on current state
     const expectedPhases = [];
     const allKnownPhases = Object.keys(phaseMap);
     let currentPhaseIndex = allKnownPhases.indexOf(currentPhase);
     if (currentPhaseIndex === -1) currentPhaseIndex = 0; // Default to Initialization if phase unknown

     // Include all phases up to and including the current one
     for (let i = 0; i <= currentPhaseIndex; i++) {
         // Skip augmentation phase if it didn't run (based on stats)
         if (allKnownPhases[i] === 'Data Augmentation' && stats.total_augmented === 0) {
             continue;
         }
         expectedPhases.push(allKnownPhases[i]);
     }

     // If completed or error, ensure all relevant steps are included correctly
     if (isCompleted || currentPhase === 'Completed' || currentPhase === 'Error') {
         const finalPhases = [];
         const endPhase = currentPhase === 'Error' ? 'Error' : 'Completed';
         let savingReached = false;
          allKnownPhases.forEach(p => {
              if(p === 'Completed' || p === 'Error') return; // Skip final states for now
              if(stats.total_augmented === 0 && p === 'Data Augmentation') return; // Explicitly skip augmentation if it didn't run
              finalPhases.push(p);
              if(p === 'Saving') savingReached = true;
          });
          // Add 'Saving' step if training completed successfully but phase didn't reach it (e.g., RF model)
          if(!savingReached && endPhase === 'Completed' && stats.model_type !== 'rf') { // Assuming RF doesn't have a 'Saving' phase like CNN
            finalPhases.push('Saving');
          }
          finalPhases.push(endPhase); // Add the actual final state
          expectedPhases.splice(0, expectedPhases.length, ...finalPhases); // Replace expected with this calculated list
     }


     // --- Update/Add/Remove Step Elements ---
     const existingStepElements = Array.from(stepsList.querySelectorAll('.list-group-item'));
     let elementIndex = 0;

     expectedPhases.forEach(phase => {
         const phaseInfo = phaseMap[phase];
         if (!phaseInfo) return; // Skip if phase is somehow unknown

         let stepElement = existingStepElements[elementIndex];
         const isCurrentActivePhase = phase === currentPhase && !isCompleted && currentPhase !== 'Completed' && currentPhase !== 'Error';
         const isPastPhase = allKnownPhases.indexOf(phase) < currentPhaseIndex && phase !== currentPhase; // Check if phase is strictly before current
         const isErrorPhase = phase === 'Error'; // Specifically the error step itself

         // Determine if the step is considered completed
         const stepIsCompleted = isPastPhase || (phase === currentPhase && (isCompleted || currentPhase === 'Completed' || currentPhase === 'Error')) || (currentPhase === 'Completed' && phase !== 'Completed') || (currentPhase === 'Error' && phase !== 'Error') ;


         // Generate details string based on phase and stats
         let details = '';
          switch (phase) {
             case 'Initialization':
                 details = stepIsCompleted ? 'Environment ready.' : 'Preparing...';
                 break;
             case 'Data Preparation':
                  if (stats.total_processed !== undefined) {
                      details = `Processed: ${stats.total_processed}`;
                      if (stats.total_stretched > 0) details += `, Stretched: ${stats.total_stretched}`;
                      if (stats.total_skipped > 0) details += `, Skipped: ${stats.total_skipped}`;
                      if (stepIsCompleted && Object.keys(stats.original_counts || {}).length > 0) {
                         const totalOriginal = Object.values(stats.original_counts || {}).reduce((s, c) => s + c, 0);
                         details += ` <small>(${stats.total_processed}/${totalOriginal} original)</small>`;
                      }
                  } else {
                      details = stepIsCompleted ? 'Dataset ready.' : 'Loading...';
                  }
                  break;
              case 'Data Augmentation': // Already skipped if total_augmented is 0
                  const totalAugmented = stats.total_augmented || 0;
                   if (stepIsCompleted) {
                        const totalOriginalForAug = Object.values(stats.original_counts || {}).reduce((s, c) => s + c, 0);
                        const augFactor = totalOriginalForAug > 0 ? (totalAugmented / totalOriginalForAug).toFixed(1) : 0;
                        details = `Added ${totalAugmented} samples (${augFactor}x increase).`;
                   } else {
                        details = `Generating samples...`;
                   }
                 break;
             case 'Model Building':
                 const modelType = stats.model_type?.toUpperCase() || 'ML';
                 details = stepIsCompleted ? `${modelType} model built (${stats.num_classes || '?'} classes).` : `Configuring ${modelType}...`;
                 break;
             case 'Training Epochs':
                  if (stats.history?.epochs !== undefined) {
                     const currentEpoch = stats.history.epochs;
                     const totalEpochs = stats.cnn_params?.epochs || 50; // Default max epochs
                     details = `Epoch ${currentEpoch}/${totalEpochs}`;
                     if (stats.history.val_accuracy?.length > 0) {
                         details += ` (Val Acc: ${(stats.history.val_accuracy.slice(-1)[0] * 100).toFixed(1)}%)`;
                     }
                     // Add early stopping note if it happened and training is completed/errored
                     if (stats.early_stopped && (isCompleted || isErrorPhase) && currentEpoch < totalEpochs) {
                          details += ' - Stopped early';
                     }
                 } else {
                      details = stepIsCompleted ? 'Epochs completed.' : 'Running epochs...';
                 }
                 break;
             case 'Validation':
                 const valAccuracy = stats.metrics?.val_accuracy;
                 details = stepIsCompleted ? `Final Val Acc: ${valAccuracy ? (valAccuracy * 100).toFixed(2) + '%' : 'N/A'}` : 'Validating...';
                 break;
             case 'Saving':
                 const saveModelType = stats.model_type?.toUpperCase() || 'ML';
                 details = stepIsCompleted ? `${saveModelType} model saved.` : 'Saving model...';
                 break;
              case 'Completed':
                  details = 'Finished successfully!';
                  break;
              case 'Error':
                  details = stats.error_message || 'An error occurred.';
                  break;
         }


         // Check if step element exists at this index
         if (stepElement) {
             // Update existing element
             const currentText = stepElement.querySelector('.flex-grow-1')?.firstChild?.textContent?.trim();
             if (currentText === phaseInfo.text) {
                 // Text matches, just update state and details
                 updateTrainingStep(stepElement, stepIsCompleted, details, isErrorPhase); // Pass isError flag
             } else {
                 // Text mismatch, likely means steps changed. Remove subsequent elements and add new one.
                 console.warn("Step mismatch, rebuilding from:", phaseInfo.text);
                 while (existingStepElements.length > elementIndex) {
                     existingStepElements.pop().remove();
                 }
                 stepElement = addTrainingStep(phaseInfo.text, stepIsCompleted, details);
                  updateTrainingStep(stepElement, stepIsCompleted, details, isErrorPhase); // Ensure correct styling
             }
         } else {
             // Add new step element
             stepElement = addTrainingStep(phaseInfo.text, stepIsCompleted, details);
              updateTrainingStep(stepElement, stepIsCompleted, details, isErrorPhase); // Ensure correct styling
         }
         elementIndex++;
     });

     // Remove any extra step elements from the previous state
     while (stepsList.children.length > elementIndex) {
         stepsList.removeChild(stepsList.lastChild);
     }
}


function displayProcessingErrors(fileErrors) {
    const errorsDetailsContainer = document.getElementById('processingErrorsDetails');
    const tableBody = document.getElementById('errorFilesTableBody');
    if (!errorsDetailsContainer || !tableBody) return;

    if (!fileErrors || fileErrors.length === 0) {
        errorsDetailsContainer.style.display = 'none'; return;
    }

    errorsDetailsContainer.style.display = 'block';
    tableBody.innerHTML = ''; // Clear previous

    fileErrors.forEach(error => {
        const filePath = error.file || 'Unknown File';
        const fileName = filePath.split(/[\\/]/).pop();
        const row = tableBody.insertRow();
        row.className = error.fatal ? 'table-danger' : 'table-warning';
        row.innerHTML = `
            <td title="${filePath}">${fileName}</td>
            <td>${error.class || '-'}</td>
            <td>${error.type || 'Unknown'}</td>
            <td>${error.error || 'No details'}</td>
            <td>${error.resolution || (error.fatal ? '<strong class="text-danger">Skipped</strong>' : 'Fallback')}</td>`;
    });
}

function displayTrainingErrors(errors) {
     // Assumes addSuggestion is available (defined in training_init_ui.js)
     const errorContainer = document.getElementById('errorContainer');
     const errorDetails = document.getElementById('errorDetails');
     const suggestionsList = document.getElementById('suggestionsList');
     if (!errorContainer || !errorDetails || !suggestionsList) return;

     if (!errors || errors.length === 0) {
          errorContainer.style.display = 'none'; return;
     }

     errorContainer.style.display = 'block';
     errorDetails.innerHTML = '';
     suggestionsList.innerHTML = '';

     // --- Categorize and Summarize ---
     const errorCounts = { short_audio: 0, inhomogeneous_shape: 0, memory: 0, other: 0 };
     const shortFiles = new Set();
     const otherMessages = new Set();

     errors.forEach(msg => {
         const errorMsg = String(msg); // Ensure string
         if (errorMsg.includes('Audio must have length greater than')) {
             errorCounts.short_audio++;
             const match = errorMsg.match(/^(.*?):/);
             if (match) shortFiles.add(match[1].split(/[\\/]/).pop());
         } else if (errorMsg.includes('inhomogeneous shape') || errorMsg.includes('same shape')) {
             errorCounts.inhomogeneous_shape++;
             otherMessages.add("Inconsistent feature dimensions.");
         } else if (errorMsg.toLowerCase().includes('memory') || errorMsg.toLowerCase().includes('oom')) {
             errorCounts.memory++;
             otherMessages.add("Potential memory exhaustion.");
         } else {
             errorCounts.other++;
             // Limit displayed generic errors for brevity
             if (otherMessages.size < 5) otherMessages.add(errorMsg.substring(0, 150) + (errorMsg.length > 150 ? '...' : ''));
         }
     });

     // --- Build Summary ---
     let summary = '<div class="mb-2 small">';
     if (errorCounts.short_audio > 0) {
         summary += `<p><strong>${errorCounts.short_audio} file(s) too short.</strong> ${shortFiles.size > 0 ? `Examples: ${Array.from(shortFiles).slice(0,3).join(', ')}...` : ''}</p>`;
     }
     if (errorCounts.inhomogeneous_shape > 0) {
         summary += `<p><strong>${errorCounts.inhomogeneous_shape} feature shape error(s).</strong></p>`;
     }
     if (errorCounts.memory > 0) {
          summary += `<p><strong>${errorCounts.memory} memory error(s) likely occurred.</strong></p>`;
     }
      if (errorCounts.other > 0) {
         summary += `<p><strong>${errorCounts.other} other error(s) occurred:</strong></p><ul class="list-unstyled ps-3">`;
         otherMessages.forEach(m => summary += `<li>- ${m}</li>`);
         summary += `</ul>`;
     }
     summary += '</div>';
     errorDetails.innerHTML = summary;

     // --- Add Suggestions ---
     const addedSuggestions = new Set(); // To avoid duplicates
     // Assumes addSuggestion function exists (should be in training_init_ui.js)
     if (typeof addSuggestion === 'function') {
         if (errorCounts.short_audio > 0) {
             addSuggestion('Record longer audio samples (> 0.5s).', suggestionsList, addedSuggestions);
             addSuggestion('Check files listed in Processing Errors table.', suggestionsList, addedSuggestions);
         }
         if (errorCounts.inhomogeneous_shape > 0) {
             addSuggestion('Try reducing Batch Size (e.g., 16 or 8).', suggestionsList, addedSuggestions);
             addSuggestion('Ensure audio files have similar lengths.', suggestionsList, addedSuggestions);
             addSuggestion('Consider Resetting Feature Cache if settings changed.', suggestionsList, addedSuggestions);
         }
         if (errorCounts.memory > 0) {
             addSuggestion('Reduce Batch Size significantly (e.g., 8 or 4).', suggestionsList, addedSuggestions);
             addSuggestion('Reduce number of Epochs.', suggestionsList, addedSuggestions);
             addSuggestion('Close other applications.', suggestionsList, addedSuggestions);
         }
         addSuggestion('Check Detailed Logs for specific messages.', suggestionsList, addedSuggestions);
         // Use global selectedModel variable (declared in training_init_ui.js)
         if (typeof selectedModel !== 'undefined' && selectedModel !== 'rf') {
             addSuggestion('Try Random Forest model (often more robust).', suggestionsList, addedSuggestions);
         }
         addSuggestion('Ensure dictionary has enough valid data per class.', suggestionsList, addedSuggestions);

         if (suggestionsList.children.length === 0) { // Fallback suggestion
              addSuggestion('Review error details and logs carefully.', suggestionsList, addedSuggestions);
         }
     } else {
          console.error("addSuggestion function not found. Cannot add suggestions.");
     }
}


function extractErrorsFromLogs(logs) {
    if (!logs || !Array.isArray(logs)) return [];
    const errorKeywords = ['error', 'failed', 'exception', 'traceback', 'warning'];
    return logs
        .filter(log => {
            if (!log || typeof log.message !== 'string') return false;
            const lowerMsg = log.message.toLowerCase();
            // Consider a log message an error if level is ERROR or it contains error keywords (case-insensitive)
            return log.level === 'ERROR' || errorKeywords.some(kw => lowerMsg.includes(kw));
        })
        .map(log => `${log.level || 'LOG'}: ${log.message}`); // Prepend level for context
}
