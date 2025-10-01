// --- UI Rendering and Update Functions ---

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


// function displayModelResults(results) {
//     // ... ENTIRE DUPLICATE FUNCTION REMOVED ... 
// }


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
         expectedPhases.push(allKnownPhases[i]);
     }

     // If completed or error, ensure all relevant steps are included
     if (isCompleted || currentPhase === 'Completed' || currentPhase === 'Error') {
         const finalPhases = [];
         const endPhase = currentPhase === 'Error' ? 'Error' : 'Completed';
         let savingReached = false;
          allKnownPhases.forEach(p => {
              if(p === 'Completed' || p === 'Error') return; // Skip final states for now
              if(stats.total_augmented === 0 && p === 'Data Augmentation') return; // Skip augmentation if it didn't run
              finalPhases.push(p);
              if(p === 'Saving') savingReached = true;
          });
          if(!savingReached && (endPhase === 'Completed')) finalPhases.push('Saving'); // Add saving if completed but somehow skipped
          finalPhases.push(endPhase); // Add the final state
          expectedPhases.splice(0, expectedPhases.length, ...finalPhases); // Replace expected with this calculated list
     }
      // Ensure augmentation is removed if it didn't happen
     if (stats.total_augmented === 0) {
        const augIndex = expectedPhases.indexOf('Data Augmentation');
        if (augIndex > -1) expectedPhases.splice(augIndex, 1);
     }


     // --- Update/Add/Remove Step Elements ---
     const existingStepElements = Array.from(stepsList.querySelectorAll('.list-group-item'));
     let elementIndex = 0;

     expectedPhases.forEach(phase => {
         const phaseInfo = phaseMap[phase];
         if (!phaseInfo) return; // Skip if phase is somehow unknown

         let stepElement = existingStepElements[elementIndex];
         const isCurrentActivePhase = phase === currentPhase && !isCompleted && currentPhase !== 'Completed' && currentPhase !== 'Error';
         const isPastPhase = allKnownPhases.indexOf(phase) < currentPhaseIndex || currentPhase === 'Completed' || currentPhase === 'Error' && phase !== 'Error';
          const isErrorPhase = phase === 'Error'; // Specifically the error step itself

         const stepIsCompleted = isPastPhase || (phase === currentPhase && (isCompleted || currentPhase === 'Completed' || currentPhase === 'Error'));

         // Generate details string based on phase and stats
         let details = '';
         // (Switch statement for details generation - same as before, ensure stats properties are checked safely)
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
                     const totalEpochs = stats.cnn_params?.epochs || 50;
                     details = `Epoch ${currentEpoch}/${totalEpochs}`;
                     if (stats.history.val_accuracy?.length > 0) {
                         details += ` (Val Acc: ${(stats.history.val_accuracy.slice(-1)[0] * 100).toFixed(1)}%)`;
                     }
                     if (stats.early_stopped && stepIsCompleted && !isErrorPhase) { // Check not error phase
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
     while (existingStepElements.length > elementIndex) {
         existingStepElements.pop().remove();
     }
}

function displayDataSummary(stats) {
     const dataSummaryContainer = document.getElementById('trainingDataSummary');
     const classTableBody = document.getElementById('classBreakdownTable')?.querySelector('tbody');
     if (!dataSummaryContainer || !classTableBody) return;

     dataSummaryContainer.style.display = 'block';
     classTableBody.innerHTML = ''; // Clear previous

     const classNames = Object.keys(stats.original_counts || {});
     if (classNames.length === 0) {
         classTableBody.innerHTML = '<tr><td colspan="5" class="text-muted text-center small">No class data available.</td></tr>';
         document.getElementById('originalCount').textContent = 0;
         document.getElementById('processedCount').textContent = 0;
         document.getElementById('augmentedCount').textContent = 0;
         document.getElementById('stretchedCount').textContent = 0;
         document.getElementById('skippedCount').textContent = 0;
         document.getElementById('totalCount').textContent = 0;
         return;
     }

     let totalOriginal = 0, totalProcessed = 0, totalAugmented = 0, totalStretched = 0, totalSkipped = 0;
     classNames.sort(); // Alphabetical order

     classNames.forEach(className => {
         const original = stats.original_counts?.[className] || 0;
         const processed = stats.processed_counts?.[className] || 0;
         const augmented = stats.augmented_counts?.[className] || 0;
         const stretched = stats.stretched_counts?.[className] || 0;
         const skipped = stats.skipped_counts?.[className] || 0;
         const totalTrainingClass = processed + augmented;

         totalOriginal += original; totalProcessed += processed; totalAugmented += augmented;
         totalStretched += stretched; totalSkipped += skipped;

         const row = classTableBody.insertRow();
         row.innerHTML = `
             <td>${className}</td>
             <td>${original}</td>
             <td>${processed}</td>
             <td>${augmented}</td>
             <td>${totalTrainingClass}</td>`;
     });

     const totalTraining = totalProcessed + totalAugmented;

     // Add footer total row
     const footer = classTableBody.tFoot; // Get existing or create if needed
     if(footer) footer.innerHTML = ''; // Clear previous footer
     const tfoot = footer || classTableBody.createTFoot();
     const totalRow = tfoot.insertRow();
     totalRow.className = 'table-light fw-bold';
     totalRow.innerHTML = `
             <td>Total</td>
             <td>${totalOriginal}</td>
             <td>${totalProcessed}</td>
             <td>${totalAugmented}</td>
             <td>${totalTraining}</td>`;

     // Update summary counts above table
     document.getElementById('originalCount').textContent = totalOriginal;
     document.getElementById('processedCount').textContent = totalProcessed;
     document.getElementById('augmentedCount').textContent = totalAugmented;
     document.getElementById('stretchedCount').textContent = totalStretched;
     document.getElementById('skippedCount').textContent = totalSkipped;
     document.getElementById('totalCount').textContent = totalTraining;
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


function displayEpochTable(epochDetails) {
     const epochTableContainer = document.getElementById('epochResultsTable');
     const tableBody = document.getElementById('epochResultsBody');
     if (!epochTableContainer || !tableBody) return;

     if (!epochDetails || epochDetails.length === 0) {
         epochTableContainer.style.display = 'none'; return;
     }

     epochTableContainer.style.display = 'block';
     tableBody.innerHTML = ''; // Clear previous

     epochDetails.forEach(epoch => {
         const row = tableBody.insertRow();
         const formatPercent = (val) => (val !== null && val !== undefined) ? (val * 100).toFixed(2) + '%' : 'N/A';
         const formatLoss = (val) => (val !== null && val !== undefined) ? val.toFixed(4) : 'N/A';
         const improvedBadge = epoch.improved === true ? '<span class="badge bg-success">Yes</span>' :
                              (epoch.improved === false ? '<span class="badge bg-warning text-dark">No</span>' : '<span class="badge bg-secondary">N/A</span>');

         row.innerHTML = `
             <td>${epoch.epoch}</td>
             <td>${formatPercent(epoch.accuracy)}</td>
             <td>${formatLoss(epoch.loss)}</td>
             <td>${formatPercent(epoch.val_accuracy)}</td>
             <td>${formatLoss(epoch.val_loss)}</td>
             <td>${improvedBadge}</td>`;
     });
}


function updateFeatureVectorDisplay() {
    // This function now just updates the text content based on a predefined structure
    // The actual feature vector structure comes from the backend processing logic
    const featureVectorElement = document.getElementById('complete-feature-vector');
    const featureCountElement = document.getElementById('feature-vector-count');
    if (!featureVectorElement || !featureCountElement) return;

    // Example structure - replace with actual features if known, or keep generic
    const featureVectorParts = [
        'mfcc_mean_1...N', 'mfcc_std_1...N',
        'mfcc_delta_mean_2...N', 'mfcc_delta_std_2...N',
        'mfcc_delta2_mean_2...N', 'mfcc_delta2_std_2...N',
        'pitch_stats', 'rms_stats', 'zcr_stats',
        'spectral_centroid_stats', 'spectral_rolloff_stats',
        'formant_stats (optional)', 'etc...'
    ];
     // A placeholder count - ideally, the backend would provide the actual count
     const estimatedFeatureCount = 78; // Example based on typical extraction

    featureVectorElement.textContent = featureVectorParts.join(', ');
    featureCountElement.textContent = estimatedFeatureCount; // Update count
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
     // Assumes addSuggestion function exists (should be in training_init_ui.js now)
     if (typeof addSuggestion === 'function') {
         if (errorCounts.short_audio > 0) {
             addSuggestion('Record longer audio samples (> 0.5s).', suggestionsList, addedSuggestions);
             addSuggestion('Check files listed in Processing Errors table.', suggestionsList, addedSuggestions);
         }
         if (errorCounts.inhomogeneous_shape > 0) {
             addSuggestion('Try reducing Batch Size (e.g., 16 or 8).', suggestionsList, addedSuggestions);
             addSuggestion('Ensure audio files have similar lengths.', suggestionsList, addedSuggestions);
         }
         if (errorCounts.memory > 0) {
             addSuggestion('Reduce Batch Size significantly (e.g., 8 or 4).', suggestionsList, addedSuggestions);
             addSuggestion('Reduce number of Epochs.', suggestionsList, addedSuggestions);
             addSuggestion('Close other applications.', suggestionsList, addedSuggestions);
         }
         addSuggestion('Check Detailed Logs for specific messages.', suggestionsList, addedSuggestions);
         if (selectedModel !== 'rf') { // selectedModel is global
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
            return log.level === 'ERROR' || errorKeywords.some(kw => lowerMsg.includes(kw));
        })
        .map(log => `${log.level || 'LOG'}: ${log.message}`);
}


function updateMfccStats(stats) {
    const mfccDetailsContainer = document.getElementById('mfccNormalizationDetails');
    if (!mfccDetailsContainer) return;
    if (!stats?.mfcc_stats) {
        // Keep container hidden or show message if it was already visible
         // mfccDetailsContainer.style.display = 'none';
        return;
    }

    mfccDetailsContainer.style.display = 'block'; // Ensure visible

    const tableBody = document.getElementById('mfccStatsTableBody');
    const coeffChartContainer = document.getElementById('mfccCoefficientsChart');
    const deltaChartContainer = document.getElementById('mfccDeltasChart');
    if (!tableBody) return; // Need table body at minimum

    tableBody.innerHTML = ''; // Clear previous stats
    const formatStat = (val) => (val !== null && val !== undefined) ? val.toFixed(4) : '-';
    const addRow = (name, before, after) => {
        tableBody.insertRow().innerHTML = `<td><strong>${name}</strong></td><td>${formatStat(before)}</td><td>${formatStat(after)}</td>`;
    };

    const beforeNorm = stats.mfcc_stats.before_normalization || {};
    const afterNorm = stats.mfcc_stats.after_normalization || {};
    const coeffs = stats.mfcc_stats.coefficients || [];
    const deltasBefore = stats.mfcc_stats.delta_stats?.before_normalization;
    const deltasAfter = stats.mfcc_stats.delta_stats?.after_normalization;
    const delta2Before = stats.mfcc_stats.delta2_stats?.before_normalization;
    const delta2After = stats.mfcc_stats.delta2_stats?.after_normalization;


    // Add overall MFCC stats
    addRow('MFCC Mean', beforeNorm.mean, afterNorm.mean);
    addRow('MFCC Std Dev', beforeNorm.std, afterNorm.std);
    addRow('MFCC Min', beforeNorm.min, afterNorm.min);
    addRow('MFCC Max', beforeNorm.max, afterNorm.max);

    // Add Delta stats if available
    if (deltasBefore || deltasAfter) {
        const sep = tableBody.insertRow();
        sep.innerHTML = '<td colspan="3" class="table-secondary small fw-bold">Delta Features (Overall)</td>';
        addRow('Delta Mean', deltasBefore?.mean, deltasAfter?.mean);
        addRow('Delta Std Dev', deltasBefore?.std, deltasAfter?.std);
        addRow('Delta Min', deltasBefore?.min, deltasAfter?.min);
        addRow('Delta Max', deltasBefore?.max, deltasAfter?.max);
    }

    // Add Delta-Delta stats if available
     if (delta2Before || delta2After) {
        const sep = tableBody.insertRow();
        sep.innerHTML = '<td colspan="3" class="table-secondary small fw-bold">Delta-Delta Features (Overall)</td>';
        addRow('Delta2 Mean', delta2Before?.mean, delta2After?.mean);
        addRow('Delta2 Std Dev', delta2Before?.std, delta2After?.std);
         addRow('Delta2 Min', delta2Before?.min, delta2After?.min);
         addRow('Delta2 Max', delta2Before?.max, delta2After?.max);
    }


    // Update Charts (using raw coefficients 'before' normalization for visualization)
    if (coeffs.length > 0 && coeffChartContainer) {
        updateMfccChart(coeffChartContainer, 'mfccCoeffChart', coeffs, 'MFCC Coeffs (Raw)', true);
    } else if (coeffChartContainer) {
        coeffChartContainer.innerHTML = '<p class="text-muted small p-3">Coefficient chart data unavailable.</p>';
    }

     // Update Delta chart using delta 'before' stats if available
     // The backend needs to provide the *individual* delta values before normalization for this chart.
     // If only *overall* delta stats are available, we can't chart individual deltas.
     // Example: Assuming stats.mfcc_stats.deltas_raw_values exists
     const deltasRaw = stats.mfcc_stats.deltas_raw_values || [];
     if (deltasRaw.length > 0 && deltaChartContainer) {
         updateMfccChart(deltaChartContainer, 'mfccDeltaChart', deltasRaw, 'Delta Features (Raw)', false);
     } else if (deltaChartContainer) {
          deltaChartContainer.innerHTML = '<p class="text-muted small p-3">Delta chart data unavailable.</p>';
     }
      // Similarly for delta-delta chart
}


function updateMfccChart(container, chartVar, data, title, highlightFirst) {
    if (!container || !data || data.length === 0 || typeof Chart === 'undefined') {
        if (container) container.innerHTML = `<p class="text-muted small p-3">Chart data unavailable.</p>`;
        return;
    }

    if (window[chartVar]) window[chartVar].destroy(); // Destroy previous chart instance

    const labels = data.map((_, i) => `${title.split(' ')[0]} ${i + 1}`);
    const bgColors = data.map((_, i) => (highlightFirst && i === 0) ? 'rgba(255, 193, 7, 0.7)' : 'rgba(63, 81, 181, 0.7)'); // MUI primary, less opaque
    const borderColors = data.map((_, i) => (highlightFirst && i === 0) ? 'rgba(255, 193, 7, 1)' : 'rgba(63, 81, 181, 1)');

    container.innerHTML = ''; // Clear container
    const canvas = document.createElement('canvas');
    container.appendChild(canvas);
    const ctx = canvas.getContext('2d');


    window[chartVar] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: title, // Use title for dataset label
                data: data,
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: { beginAtZero: false, ticks: { font: { size: 10 } } },
                x: { ticks: { font: { size: 10 } } }
            },
            plugins: {
                title: { display: true, text: title, font: { size: 14 } },
                legend: { display: false }, // Usually hide for single dataset bar chart
                tooltip: {
                    callbacks: {
                        title: (ctx) => `${labels[ctx[0].dataIndex]}${(highlightFirst && ctx[0].dataIndex === 0 && title.includes('MFCC')) ? ' (Energy)' : ''}`,
                        label: (ctx) => `Value: ${ctx.raw.toFixed(4)}`,
                        afterLabel: (ctx) => (highlightFirst && ctx.dataIndex === 0 && title.includes('MFCC')) ? 'Note: Handled separately' : null
                    }
                }
            }
        }
    });
}
