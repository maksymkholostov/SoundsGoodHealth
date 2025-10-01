/**
 * predict_playback.js
 * Handles audio playback and visualization
 */

// Global variables
let playbackAudioContext = null; // Reuse context if possible
let currentlyPlayingSource = null; // Track of the source node OR the HTMLAudioElement
let predictionAudioDataMap = {}; // Map to store audio BLOBs for playback
let predictionAudioSampleRates = {}; // Map to store original sample rates

/**
 * Helper function to read the sample rate from a WAV blob
 */
async function getWavSampleRate(blob) {
    try {
        // Read first 44 bytes (WAV header)
        const headerBuffer = await blob.slice(0, 44).arrayBuffer();
        const headerView = new DataView(headerBuffer);
        // Sample rate is at byte offset 24
        return headerView.getUint32(24, true);
    } catch (e) {
        console.error("Error reading WAV sample rate:", e);
        return null;
    }
}

/**
 * Plays an audio blob from history by ID
 */
async function playHistoryAudio(audioId) {
    if (!audioId || !predictionAudioDataMap[audioId]) {
        console.error(`Audio data not found for ID: ${audioId}`);
        alert('Could not find audio data for this prediction.');
        return;
    }

    const audioBlob = predictionAudioDataMap[audioId]; // Get the BLOB
    console.log(`Attempting to play audio blob ID: ${audioId}, Size: ${audioBlob.size}, Type: ${audioBlob.type}`);

    // Stop any previously playing audio
    if (currentlyPlayingSource) {
        try {
            if (currentlyPlayingSource instanceof Audio) { // HTMLAudioElement
                 currentlyPlayingSource.pause();
                 currentlyPlayingSource.src = ''; // Release resource?
            } else if (currentlyPlayingSource.stop) { // Web Audio API SourceNode
                 currentlyPlayingSource.stop();
            }
            console.log("Stopped previous playback.");
        } catch (e) { console.warn("Error stopping previous playback:", e) }
        currentlyPlayingSource = null;
         // Release previous object URL if it exists
         if (window.lastObjectURL) {
             URL.revokeObjectURL(window.lastObjectURL);
             window.lastObjectURL = null;
         }
    }
    
    // --- Use HTMLAudioElement with Blob URL --- 
    try {
        const audioUrl = URL.createObjectURL(audioBlob);
        window.lastObjectURL = audioUrl; // Store to revoke later
        
        // Get stored sample rate if available
        let storedSampleRate = null;
        if (predictionAudioSampleRates[audioId]) {
            storedSampleRate = predictionAudioSampleRates[audioId];
            console.log(`Found stored sample rate for audio ${audioId}: ${storedSampleRate}Hz`);
        } else {
            // Fall back to WAV header extraction if needed
            storedSampleRate = await getWavSampleRate(audioBlob);
            console.log(`Extracted WAV sample rate from header: ${storedSampleRate}Hz`);
        }
        
        const player = new Audio(audioUrl);
        currentlyPlayingSource = player; // Store reference to the player
        
        // Adjust playback rate if necessary to correct for sample rate mismatch
        if (storedSampleRate) {
            // Get the browser's native audio sample rate
            // If not available via global audioContext, create a temporary one to check
            let nativeSampleRate;
            if (window.audioContext) {
                nativeSampleRate = window.audioContext.sampleRate;
            } else {
                const tempContext = new (window.AudioContext || window.webkitAudioContext)();
                nativeSampleRate = tempContext.sampleRate;
                tempContext.close();
            }
            
            // FIXED: Force the stored sample rate to 16000 if it appears incorrect
            // This addresses issues where WAV header may contain incorrect sample rate
            if (storedSampleRate !== 16000 && window.TARGET_SAMPLE_RATE === 16000) {
                console.log(`WAV sample rate (${storedSampleRate}) differs from expected TARGET_SAMPLE_RATE (${window.TARGET_SAMPLE_RATE})`);
                console.log(`Forcing sample rate to expected recording rate: 16000Hz`);
                storedSampleRate = 16000;
            }
            
            // Calculate correct playback rate - THIS IS THE KEY FIX
            const playbackRateCorrection = storedSampleRate / 16000;
            console.log(`PLAYBACK ADJUSTMENT:
• WAV Sample Rate: ${storedSampleRate}Hz
• Expected Sample Rate: 16000Hz
• Browser Sample Rate: ${nativeSampleRate}Hz
• Playback Rate Correction: ${playbackRateCorrection.toFixed(4)}`);
            
            // Apply the correction
            player.playbackRate = playbackRateCorrection;
            
            // ADDED: Fallback if playback still sounds wrong
            player.addEventListener('playing', () => {
                console.log(`Audio playing with rate=${player.playbackRate}`);
                // Add a button to toggle between different playback rates for troubleshooting
                if (window.DEBUG_MODE) {
                    const rates = [1, 3, 0.33]; // Common correction factors
                    const debugContainer = document.getElementById('audioRateDebug') || 
                                          document.createElement('div');
                    debugContainer.id = 'audioRateDebug';
                    debugContainer.innerHTML = '<div style="margin:10px 0;"><strong>Playback Rate Debug:</strong></div>';
                    
                    rates.forEach(rate => {
                        const btn = document.createElement('button');
                        btn.innerText = `Rate: ${rate}`;
                        btn.style.margin = '0 5px';
                        btn.onclick = () => {
                            player.playbackRate = rate;
                            console.log(`Manually set playback rate to ${rate}`);
                        };
                        debugContainer.appendChild(btn);
                    });
                    
                    const debugTarget = document.querySelector('#latestPrediction') ||
                                       document.querySelector('.mui-prediction-result');
                    if (debugTarget && !document.getElementById('audioRateDebug')) {
                        debugTarget.appendChild(debugContainer);
                    }
                }
            });
        } else {
            console.warn("Could not determine WAV sample rate for playback correction");
            // ADDED: Fallback to default correction for 16kHz audio
            const fallbackRate = 3.0; // Typically 48000Hz/16000Hz = 3.0
            console.log(`Using fallback playback rate correction: ${fallbackRate}`);
            player.playbackRate = fallbackRate;
        }
        
        player.play();
        console.log(`Playing audio ID: ${audioId} using HTMLAudioElement with playbackRate = ${player.playbackRate}`);

        player.onended = () => {
             console.log(`Playback finished for audio ID: ${audioId}`);
             URL.revokeObjectURL(audioUrl);
             window.lastObjectURL = null;
             if (currentlyPlayingSource === player) {
                 currentlyPlayingSource = null; 
             }
         };
        player.onerror = (e) => {
            console.error(`Error playing audio blob with HTMLAudioElement:`, e);
            alert("Error playing recorded audio.");
            URL.revokeObjectURL(audioUrl); 
            window.lastObjectURL = null;
             if (currentlyPlayingSource === player) {
                 currentlyPlayingSource = null; 
             }
        };

    } catch (error) {
        console.error(`Error playing audio blob ID ${audioId} with HTMLAudioElement:`, error);
        alert(`Could not play audio: ${error.message}`);
        currentlyPlayingSource = null;
        if (window.lastObjectURL) {
             URL.revokeObjectURL(window.lastObjectURL);
             window.lastObjectURL = null;
         }
    }
}

/**
 * Adds a prediction to the history list in the UI
 */
function addToPredictionHistory(data) {
    const historyCard = document.getElementById('predictionHistoryCard');
    const predictionHistoryList = document.getElementById('predictionHistory');

    if (!predictionHistoryList) {
        console.warn("Element 'predictionHistory' not found for history.");
        return;
    }
    if (!data || !data.prediction || !data.audioId) {
        console.error("addToPredictionHistory called with invalid data", data);
        return;
    }
    const prediction = data.prediction;
    const audioId = data.audioId;

    if (historyCard) historyCard.style.display = 'block';

    const placeholder = predictionHistoryList.querySelector('div[style*="text-align: center"]');
    if (placeholder) {
        predictionHistoryList.innerHTML = '';
    }

    const item = document.createElement('div');
    item.className = 'mui-prediction-item d-flex justify-content-between align-items-center'; // Use flexbox
    
    // Store prediction ID in the data attribute for feedback matching
    if (prediction.prediction_id) {
        item.dataset.predictionId = prediction.prediction_id;
    }
    
    // Store the original class ID (needed for feedback matching)
    const originalClassId = prediction.class || 'Unknown';
    item.dataset.originalClassId = originalClassId;

    // Convert class ID to human-readable name using IdMapper
    let displayClassName = originalClassId;
    if (window.IdMapper && typeof window.IdMapper.getClassName === 'function') {
        const mappedName = window.IdMapper.getClassName(originalClassId);
        if (mappedName) {
            displayClassName = mappedName;
            console.log(`Mapped class ID ${originalClassId} to name: ${displayClassName}`);
        }
    }
    
    let confidenceText = 'N/A';
    if (prediction.confidence !== undefined && prediction.confidence !== null) {
        confidenceText = `${(prediction.confidence * 100).toFixed(1)}%`;
    }

    // Use innerHTML for structure, using the human-readable name for display
    item.innerHTML = `
        <div class="prediction-info">
            <span class="sound">${displayClassName}</span>
            <span class="confidence text-muted ms-2">(${confidenceText})</span>
        </div>
        <div class="feedback-display" data-prediction-class="${originalClassId}"></div>
    `;

    if (predictionHistoryList.firstChild) {
        predictionHistoryList.insertBefore(item, predictionHistoryList.firstChild);
    } else {
        predictionHistoryList.appendChild(item);
    }
    
    const maxHistoryItems = 20;
    while (predictionHistoryList.children.length > maxHistoryItems) {
        // Target the last ELEMENT child specifically
        const itemToRemove = predictionHistoryList.lastElementChild;
        if (!itemToRemove) break; // Exit loop if no element child found
        
        predictionHistoryList.removeChild(itemToRemove);
    }
}

/**
 * Updates the prediction UI with new data
 */
function updatePredictionUI(data) {
    // ADDED: Log state at the very beginning
    console.log(`>>> updatePredictionUI START: pause=${window.pauseForFeedback}, waiting=${window.isWaitingForFeedback}`); 
    
    // CORRECTED: Check data.predictions[0] and get prediction from there
    if (!data || !data.predictions || !Array.isArray(data.predictions) || data.predictions.length === 0 || !data.predictions[0] || !data.predictions[0].class_id) {
        console.error('📋 DEBUG [predict_playback.js]: updatePredictionUI called with invalid or incomplete data', data);
        return;
    }
    const prediction = data.predictions[0]; // Get the first prediction object from the array
    const audioId = data.audioId;

    console.log('📋 DEBUG [predict_playback.js]: Updating UI with prediction:', prediction, 'Audio ID:', audioId);
    // Update global state
    window.currentPrediction = prediction;

    const latestPredictionDiv = document.getElementById('latestPrediction');
    const predictedClassSpan = document.getElementById('predictedClass');
    const confidenceValueSpan = document.getElementById('confidenceValue');
    const predictionHistoryList = document.getElementById('predictionHistory');

    // Hide the latest prediction card in continuous mode
    if (latestPredictionDiv) {
        if (window.pauseForFeedback) {
            latestPredictionDiv.style.display = 'block'; // Show only in feedback mode
        } else {
            latestPredictionDiv.style.display = 'none'; // Hide in continuous mode
        }
    }

    // Update predicted class text (using IdMapper)
    if (predictedClassSpan) {
        let displayName = prediction.class_id; // Default to ID
        if (window.IdMapper) {
            displayName = window.IdMapper.getClassName(prediction.class_id) || prediction.class_id; // Fallback to ID if lookup fails
        }
        console.log(`>>> updatePredictionUI: Setting predictedClassSpan text to: ${displayName}`); // ADDED LOG
        predictedClassSpan.textContent = displayName;
        console.log(`>>> updatePredictionUI: Finished setting predictedClassSpan text.`); // ADDED LOG
    } else {
        console.warn("Element 'predictedClass' not found.");
    }

    // Update confidence text
    if (confidenceValueSpan) {
        let confidenceText = 'Confidence unknown';
        if (prediction.confidence !== undefined && prediction.confidence !== null) {
            const confidencePercent = (prediction.confidence * 100).toFixed(1);
            confidenceText = `${confidencePercent}% confidence`;
        }
        console.log(`>>> updatePredictionUI: Setting confidenceValueSpan text to: ${confidenceText}`); // ADDED LOG
        confidenceValueSpan.textContent = confidenceText;
        console.log(`>>> updatePredictionUI: Finished setting confidenceValueSpan text.`); // ADDED LOG
    } else {
        console.warn("Element 'confidenceValue' not found.");
    }

    // --- Conditional Feedback UI --- 
    const feedbackSection = document.getElementById('feedbackSection'); // ADDED: Get element here
    
    // ADDED: Log flags *immediately* before the check
    console.log(`>>> updatePredictionUI: Feedback Check. pauseForFeedback=${window.pauseForFeedback}, isWaitingForFeedback=${window.isWaitingForFeedback}`); // More specific log
    
    console.log(`updatePredictionUI: Checking feedback display. pauseForFeedback=${window.pauseForFeedback}, isWaitingForFeedback=${window.isWaitingForFeedback}`);
    if (window.pauseForFeedback && window.isWaitingForFeedback) {
        console.log('Feedback mode ON: Showing feedback section and updating options.');
        
        // IMPORTANT CHECK: See if we've already shown feedback options and are waiting for SPACE
        const listeningIndicator = document.getElementById('listeningIndicator');
        const feedbackOptionsEl = document.getElementById('feedbackOptions');
        const alreadyGaveFeedback = listeningIndicator && 
                                  listeningIndicator.innerText.includes('Press SPACE') &&
                                  (!feedbackOptionsEl || feedbackOptionsEl.children.length === 0);
        
        // IMPROVED CHECK: Also verify that we don't have a stale currentPrediction
        const hasStalePrediction = window.currentPrediction &&
                                  window.lastFeedbackPredictionId === window.currentPrediction.prediction_id;
                                  
        if (alreadyGaveFeedback || hasStalePrediction) {
            console.log('>>> IMPORTANT: User already gave feedback and is waiting to press SPACE or has stale prediction. Skipping feedback options display.');
            // Show feedback section but don't recreate options
            if (feedbackSection) {
                feedbackSection.style.display = 'block'; 
                feedbackSection.style.visibility = 'visible'; 
            }
            return; // Exit early to avoid showing options again
        }
        
        // Store the current prediction ID to prevent repeated feedback for same prediction
        if (window.currentPrediction && window.currentPrediction.prediction_id) {
            window.lastFeedbackPredictionId = window.currentPrediction.prediction_id;
        }
        
        // Show the feedback section
        if (feedbackSection) {
            feedbackSection.style.display = 'block'; // Make it visible
            feedbackSection.style.visibility = 'visible'; // Ensure visibility
        } else {
            console.warn("Element 'feedbackSection' not found.");
        }
        
        // Reset and populate feedback button options ONLY when showing the section
        // Add a small delay to ensure everything is properly initialized
        console.log('>>> updatePredictionUI: Calling resetFeedbackForm and updateFeedbackOptions with delay...'); // ADDED Log
        
        // Clear any previous timeout to avoid race conditions
        if (window.feedbackOptionsTimeout) {
            clearTimeout(window.feedbackOptionsTimeout);
        }
        
        window.feedbackOptionsTimeout = setTimeout(() => {
            try {
                // Double-check if the user has already provided feedback
                const indicatorCheck = document.getElementById('listeningIndicator');
                if (indicatorCheck && indicatorCheck.innerText.includes('Press SPACE')) {
                    console.log('>>> TIMEOUT CHECK: User already gave feedback during timeout. Skipping options creation.');
                    return;
                }
                
                // Force feedback section visible again (in case it was hidden)
                if (feedbackSection) {
                    feedbackSection.style.display = 'block';
                    feedbackSection.style.visibility = 'visible';
                }
                
                if (typeof window.resetFeedbackForm === 'function') window.resetFeedbackForm();
                if (typeof window.updateFeedbackOptions === 'function') {
                    window.updateFeedbackOptions();
                    console.log('>>> updatePredictionUI: Successfully updated feedback options after delay');
                }
                else console.error('updateFeedbackOptions function not found!');
            } catch (e) {
                console.error("Error updating feedback options:", e);
            }
        }, 100); // Small delay to ensure DOM is ready
    } else {
        console.log('Continuous mode or not waiting for feedback: Ensuring feedback section is hidden and clearing options.');
        // Ensure feedback section is hidden (it should be by default now)
        if (feedbackSection) {
            feedbackSection.style.display = 'none'; 
        }
        // --- Explicitly clear the options container --- 
        const feedbackOptionsEl = document.getElementById('feedbackOptions');
        if (feedbackOptionsEl) {
            console.warn('>>> updatePredictionUI: ELSE block triggered. Clearing #feedbackOptions via innerHTML!'); // ADDED Warning Log
            feedbackOptionsEl.innerHTML = ''; // Clear buttons or loading text
            console.log('Cleared #feedbackOptions content.');
        } else {
             console.warn("Element 'feedbackOptions' not found when trying to clear.");
        }
        // --- End clearing --- 
    }
    // --- End Conditional Feedback UI ---

    // Add to history - different display for continuous vs feedback mode
    if (window.pauseForFeedback) {
        console.log("Feedback mode ON: Adding prediction to history.");
        addToPredictionHistory({
            prediction: {
                class: prediction.class_id, // Map class_id to class for consistency
                confidence: prediction.confidence,
                prediction_id: prediction.prediction_id // Ensure prediction_id is passed
            },
            audioId: audioId
        });
    } else {
        console.log("Continuous mode: Adding simple prediction to list.");
        addSimplePredictionToList(prediction);
    }
}

/**
 * Adds a simple prediction to the continuous mode list
 */
function addSimplePredictionToList(prediction) {
    // DISABLED: We're using the table for predictions now, not this popup
    return;
    
    /* Original code disabled
    // Get or create the simple predictions container
    let container = document.getElementById('simplePredictionsList');
    if (!container) {
        // Create container if it doesn't exist
        container = document.createElement('div');
        container.id = 'simplePredictionsList';
        container.style.cssText = `
            position: fixed;
            top: 100px;
            right: 20px;
            width: 250px;
            max-height: 500px;
            overflow-y: auto;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
            font-family: monospace;
            font-size: 14px;
        `;
        
        // Add title
        const title = document.createElement('div');
        title.style.cssText = 'font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid #ddd; padding-bottom: 5px;';
        title.textContent = 'Predictions:';
        container.appendChild(title);
        
        // Add list container
        const listContainer = document.createElement('div');
        listContainer.id = 'simplePredictionsListItems';
        container.appendChild(listContainer);
        
        document.body.appendChild(container);
    }
    */
    
    // Get the list items container
    const listContainer = document.getElementById('simplePredictionsListItems');
    if (!listContainer) return;
    
    // Remove highlight from previous items
    const previousItems = listContainer.querySelectorAll('div');
    previousItems.forEach(item => {
        item.style.backgroundColor = 'transparent';
        item.style.padding = '3px 5px';
        item.style.borderRadius = '0';
        item.style.fontWeight = 'normal';
    });
    
    // Get display name for the class
    let displayName = prediction.class_id;
    if (window.IdMapper && typeof window.IdMapper.getClassName === 'function') {
        displayName = window.IdMapper.getClassName(prediction.class_id) || prediction.class_id;
    } else if (prediction.class) {
        displayName = prediction.class;
    }
    
    // Create new prediction item
    const item = document.createElement('div');
    item.style.cssText = 'padding: 5px 8px; white-space: nowrap; margin: 2px 0; transition: all 0.3s ease;';
    
    // Format: "Eh 89%"
    const confidence = Math.round(prediction.confidence * 100);
    item.textContent = `${displayName} ${confidence}%`;
    
    // Color code based on confidence
    if (confidence >= 80) {
        item.style.color = '#2e7d32'; // Green for high confidence
    } else if (confidence >= 60) {
        item.style.color = '#f57c00'; // Orange for medium confidence  
    } else {
        item.style.color = '#d32f2f'; // Red for low confidence
    }
    
    // Highlight the latest prediction
    item.style.backgroundColor = '#e3f2fd';
    item.style.borderRadius = '4px';
    item.style.fontWeight = 'bold';
    item.style.boxShadow = '0 1px 3px rgba(0,0,0,0.1)';
    
    // Add to top of list
    listContainer.insertBefore(item, listContainer.firstChild);
    
    // Keep only last 20 predictions
    while (listContainer.children.length > 20) {
        listContainer.removeChild(listContainer.lastChild);
    }
}

/**
 * Draws an audio waveform visualization
 */
function drawWaveform(audioBuffer, sampleRate, containerId, label) {
    // Create or get container
    let container = document.getElementById(containerId);
    if (!container) {
        container = document.createElement('div');
        container.id = containerId;
        container.style.border = '1px solid #ccc';
        container.style.padding = '10px';
        container.style.margin = '10px 0';
        container.style.backgroundColor = '#f8f8f8';
        container.style.zIndex = '1000'; // Ensure it's on top
        container.style.maxHeight = '300px';
        container.style.overflowY = 'auto';
        
        const title = document.createElement('h4');
        title.textContent = 'Audio Debug Visualization';
        title.style.margin = '0 0 10px 0';
        container.appendChild(title);
        
        // Add to DOM in a visible location - try multiple locations
        const debugLocations = [
            document.querySelector('#latestPrediction'),
            document.querySelector('.mui-prediction-result'),
            document.querySelector('.container'),
            document.body
        ];
        
        const targetLocation = debugLocations.find(el => el !== null);
        if (targetLocation) {
            targetLocation.appendChild(container);
            console.log('Debug container added to DOM at:', targetLocation);
        } else {
            document.body.appendChild(container);
            console.log('Debug container added to body as fallback');
        }
    }
    
    // Create canvas for this waveform
    const waveContainer = document.createElement('div');
    waveContainer.style.marginBottom = '15px';
    
    const waveLabel = document.createElement('div');
    waveLabel.textContent = `${label} (${sampleRate}Hz)`;
    waveLabel.style.fontWeight = 'bold';
    waveLabel.style.marginBottom = '5px';
    
    const canvas = document.createElement('canvas');
    canvas.width = 500;
    canvas.height = 100;
    canvas.style.width = '100%';
    canvas.style.height = '100px';
    canvas.style.backgroundColor = '#222';
    
    waveContainer.appendChild(waveLabel);
    waveContainer.appendChild(canvas);
    container.appendChild(waveContainer);
    
    // Draw the waveform
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    const stepSize = Math.ceil(audioBuffer.length / canvas.width);
    const midHeight = canvas.height / 2;
    
    ctx.strokeStyle = '#00ff00';
    ctx.beginPath();
    
    // Draw the actual waveform
    for (let i = 0; i < canvas.width; i++) {
        const index = i * stepSize;
        if (index < audioBuffer.length) {
            const value = audioBuffer[index] * midHeight; // Scale to half canvas height
            ctx.lineTo(i, midHeight - value);
        }
    }
    
    ctx.stroke();
    
    // Add duration and samples info
    const durationSec = audioBuffer.length / sampleRate;
    const infoText = document.createElement('div');
    infoText.textContent = `Duration: ${durationSec.toFixed(4)}s, Samples: ${audioBuffer.length}`;
    infoText.style.fontSize = '12px';
    infoText.style.marginTop = '5px';
    
    waveContainer.appendChild(infoText);
    
    console.log(`Waveform visualization created for ${label}`);
    return container;
}

/**
 * Analyzes a WAV blob and extracts header information
 */
async function analyzeWavBlob(blob, label) {
    console.log(`===== ANALYZING WAV BLOB: ${label} =====`);
    console.log(`- Blob Size: ${blob.size} bytes`);
    console.log(`- Blob Type: ${blob.type}`);
    
    try {
        // Read first 44 bytes (WAV header)
        const headerBuffer = await blob.slice(0, 44).arrayBuffer();
        const headerView = new DataView(headerBuffer);
        
        // Extract key header values
        const chunkID = String.fromCharCode(
            headerView.getUint8(0), headerView.getUint8(1), 
            headerView.getUint8(2), headerView.getUint8(3)
        );
        const fileSize = headerView.getUint32(4, true) + 8;
        const format = String.fromCharCode(
            headerView.getUint8(8), headerView.getUint8(9), 
            headerView.getUint8(10), headerView.getUint8(11)
        );
        const sampleRate = headerView.getUint32(24, true);
        const byteRate = headerView.getUint32(28, true);
        const numChannels = headerView.getUint16(22, true);
        const bitsPerSample = headerView.getUint16(34, true);
        const dataSize = headerView.getUint32(40, true);
        
        console.log(`- WAV Header Info: 
  • ChunkID: ${chunkID}
  • Format: ${format}
  • File Size: ${fileSize} bytes
  • Sample Rate: ${sampleRate} Hz
  • Byte Rate: ${byteRate} bytes/sec
  • Channels: ${numChannels}
  • Bits Per Sample: ${bitsPerSample}
  • Data Size: ${dataSize} bytes
  • Duration: ~${(dataSize / byteRate).toFixed(2)} seconds`);
        
        // Calculate actual vs. expected duration
        const expectedDuration = dataSize / (sampleRate * numChannels * (bitsPerSample/8));
        console.log(`- Expected Duration: ${expectedDuration.toFixed(4)} seconds`);
        
        if (window.audioContext) {
            const ratio = window.audioContext.sampleRate / sampleRate;
            if (ratio !== 1) {
                console.log(`⚠️ SAMPLE RATE MISMATCH:
  • WAV Header Rate: ${sampleRate} Hz
  • Browser Audio Context Rate: ${window.audioContext.sampleRate} Hz
  • Ratio: ${ratio.toFixed(4)} (>1 means playback will be slower/stretched)`);
            }
        }
        
        console.log(`===== END ANALYSIS: ${label} =====`);
        return { sampleRate, duration: expectedDuration };
    } catch (e) {
        console.error(`Error analyzing WAV blob: ${e}`);
    }
}

// Create download function for audio files (debugging)
function offerDownload(blob, filename) {
    if (!blob) return;
    
    // Create UI for the download
    const section = document.createElement('div');
    section.className = 'audio-debug-download';
    section.style.margin = '10px 0';
    section.style.padding = '8px';
    section.style.backgroundColor = '#f0f0f0';
    section.style.borderRadius = '4px';
    
    const label = document.createElement('span');
    label.textContent = `Download ${filename}: `;
    
    const downloadBtn = document.createElement('button');
    downloadBtn.textContent = 'Download';
    downloadBtn.className = 'mui-button mui-button-small';
    downloadBtn.onclick = function() {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    };
    
    section.appendChild(label);
    section.appendChild(downloadBtn);
    
    // Add to DOM - choose a suitable location
    const container = document.querySelector('#latestPrediction') || 
                      document.querySelector('.mui-prediction-result') ||
                      document.body;
    
    if (container) {
        // Limit to 4 download links
        const existingLinks = container.querySelectorAll('.audio-debug-download');
        if (existingLinks.length >= 4) {
            container.removeChild(existingLinks[0]); // Remove oldest
        }
        container.appendChild(section);
        
        console.log(`Download option created for: ${filename}`);
    }
}

// Export functions to global scope
window.playHistoryAudio = playHistoryAudio;
window.addToPredictionHistory = addToPredictionHistory;
window.addSimplePredictionToList = addSimplePredictionToList;
window.updatePredictionUI = updatePredictionUI;
window.drawWaveform = drawWaveform;
window.analyzeWavBlob = analyzeWavBlob;
window.offerDownload = offerDownload;
window.predictionAudioDataMap = predictionAudioDataMap;
window.predictionAudioSampleRates = predictionAudioSampleRates; 