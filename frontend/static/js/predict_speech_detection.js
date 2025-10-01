/**
 * predict_speech_detection.js
 * Handles energy-based speech detection and processing
 */

// Speech detection state variables
let isListening = false;
let isSpeaking = false;
let isEndingSpeech = false;
let silenceFrames = 0;
let postSpeechFrames = 0;
let speechFramesBuffered = 0;
let postSpeechFramesBuffered = 0;
let mainSpeechBuffer = [];
let animationFrameId = null;
let PRE_SPEECH_MS = 30; // How much audio to keep before speech starts

// State for ambient noise detection
let isCapturingNoise = false;
let noiseBuffer = [];
let ambientNoiseProfile = null;
let noiseCaptureTimeoutId = null;
let lastNoiseCaptureTime = null;
let noiseCaptureStartTime = null;

// Global state for pausing
let pauseForFeedback = false;
let isWaitingForFeedback = false;

// Update window property when local state changes
Object.defineProperty(window, 'isWaitingForFeedback', {
    get: () => isWaitingForFeedback,
    set: (value) => {
        isWaitingForFeedback = value;
        console.log(`>>> window.isWaitingForFeedback set to: ${value}`); // Log changes
    },
    configurable: true // Allow redefinition if needed
});

let logCounter = 0; // ADDED counter for logging

/**
 * Start a prediction session with speech detection
 */
async function startPredictionSession() {
    console.log("startPredictionSession called.");
    console.log("Current selectedModelId:", window.selectedModelId);
    
    // Check if we're resuming from feedback (special case)
    const isResumingFromFeedback = window.resumingFromFeedback === true;
    
    // If resuming from feedback, allow restart even if already listening
    if (!isResumingFromFeedback) {
        // Standard check for regular starts (not resuming from feedback)
        if (window.isListening === true || window.isCapturingNoise === true) {
            console.log(`Cannot start: Already in active state. isListening=${window.isListening}, isCapturingNoise=${window.isCapturingNoise}`);
            return;
        }
    } else {
        console.log("Resuming from feedback: Allowing restart even if already listening");
        window.resumingFromFeedback = false; // Reset the flag
    }
    
    // Check for multi-model comparison mode or single model
    if (!window.selectedModelId && (!window.selectedModelIds || window.selectedModelIds.length === 0)) {
        console.error("startPredictionSession Error: No model(s) selected!");
        alert('Please select at least one model first!');
        return;
    }
    
    // For multi-model comparison, ensure we have a selectedModelId for compatibility
    if (window.selectedModelIds && window.selectedModelIds.length > 0 && !window.selectedModelId) {
        // Use the first model in the array as the primary for compatibility
        window.selectedModelId = window.selectedModelIds[0];
        console.log(`Using first model from comparison list as primary: ${window.selectedModelId}`);
    }
    
    // Clear the prediction table for a fresh start
    if (typeof window.clearPredictionTable === 'function') {
        window.clearPredictionTable();
    }
    
    // --- Moved Ambient Noise Check Logic Here --- 
    const ambientSwitch = document.getElementById('ambientNoiseSwitch');
    const noiseCheckEnabled = ambientSwitch ? ambientSwitch.checked : false;
    let proceedToListen = false; // Default to false, only proceed after checks
    let captureSuccess = true; // Assume success if not capturing

    if (noiseCheckEnabled) {
        console.log("startPredictionSession: Ambient noise check is ON.");
        const needsCapture = !ambientNoiseProfile || 
                             (lastNoiseCaptureTime && (Date.now() - lastNoiseCaptureTime > window.NOISE_REMINDER_INTERVAL_MS));
        if (needsCapture) {
            if(ambientNoiseProfile) window.showToast("Noise profile is >30 mins old. Re-capturing...", "warning");
            console.log("startPredictionSession: No valid noise profile. Capturing now...");
            // Ensure audio is initialized *before* noise capture
            if (!await window.initAudioProcessing()) { 
                 alert("Audio system failed to initialize before noise capture.");
                 return; // Stop if audio fails
            }
            captureSuccess = await startNoiseCapture(); // Will update indicator during capture
            if (!captureSuccess) {
                 alert("Failed to capture noise profile. Proceeding with default threshold.");
                 window.ambientNoiseProfile = null;
                 proceedToListen = true; // Allow proceeding even if capture failed
            } else {
                 console.log("startPredictionSession: Noise captured successfully.");
                 proceedToListen = true; // Proceed after successful capture
            }
        } else {
             console.log("startPredictionSession: Valid ambient noise profile exists.");
             if (noiseCaptureTimeoutId) { 
                 clearTimeout(noiseCaptureTimeoutId);
                 noiseCaptureTimeoutId = null;
                 console.log("startPredictionSession: Cleared unnecessary noise capture timeout.");
             }
             proceedToListen = true; // Proceed with existing profile
        }
    } else {
        // Noise check is OFF
        console.log("startPredictionSession: Ambient noise check is OFF.");
        if (ambientNoiseProfile) {
             console.log("startPredictionSession: Clearing existing noise profile.");
             ambientNoiseProfile = null;
             lastNoiseCaptureTime = null;
        }
        proceedToListen = true; // Proceed without noise check
    }
    // --- End Moved Ambient Noise Logic --- 

    // --- Start Actual Listening (only if proceedToListen is true) --- 
    if (proceedToListen) {
        try {
            // Get stream if necessary (might already exist from noise capture)
            if (!await window.getAudioInput()) {
                return; // Failed to get audio input
            }
            
            // Reset state for new listening session
            isListening = true;
            window.isListening = true; // Update window property
            isSpeaking = false;
            window.isSpeaking = false; // Update window property
            isEndingSpeech = false;
            
            // Start game loop if game mode is active
            if (window.currentGameModeActive && typeof window.startGameLoop === 'function') {
                console.log("Starting game loop since game mode is active");
                window.startGameLoop();
            }
            postSpeechFrames = 0;
            silenceFrames = 0;
            mainSpeechBuffer = [];
            window.circularBufferIndex = 0;
            window.circularBuffer.fill(0); 
            speechFramesBuffered = 0; // Reset counters
            postSpeechFramesBuffered = 0;

            // --- ADDED: Start Game Loop If Game Mode Active ---
            if (window.currentGameModeActive && typeof window.startGameLoop === 'function') {
                console.log('startPredictionSession: Game mode is active, starting game loop.');
                window.startGameLoop();
            } else {
                console.log('startPredictionSession: Game mode NOT active, clearing game UI just in case.');
                if (typeof window.stopGameLoop === 'function') window.stopGameLoop(); // Clear target/face
            }
            // --- END ADDED ---

            if (animationFrameId) cancelAnimationFrame(animationFrameId);
            monitorAudioEnergy(); // Start the energy monitoring loop
            
            // Update Button to "End Session"
            const predictButton = document.getElementById('predictButton');
            if (predictButton) {
                predictButton.innerHTML = '<span class="material-icons">stop</span> End Session';
                predictButton.classList.add('mui-button-danger');
            }
            // Update Indicator to "Speak Now"
            const listeningIndicator = document.getElementById('listeningIndicator');
            if (listeningIndicator) {
                listeningIndicator.innerHTML = '<span class="material-icons">mic</span> Speak Now...';
                listeningIndicator.style.display = 'block';
            }
            console.log("Energy monitoring loop started for speech detection.");

        } catch (error) {
            window.handleAudioProcessingError(error); 
            isListening = false;
             // Reset button if start failed
             const predictButton = document.getElementById('predictButton');
             if (predictButton) {
                 predictButton.innerHTML = '<span class="material-icons">mic</span> Predict';
                 predictButton.classList.remove('mui-button-danger');
             }
        }
    }
}

/**
 * Monitor audio energy levels to detect speech
 */
function monitorAudioEnergy() {
    try {
        // IMPORTANT: Always schedule the next frame FIRST before any checks
        // This ensures we don't lose the loop even if there's an error or condition check
        animationFrameId = requestAnimationFrame(monitorAudioEnergy);
    
        // Now check if we should skip audio processing for this frame
        if (!isListening || isWaitingForFeedback) { 
            if (logCounter % 60 === 0) { // Log occasionally but not too much
                console.log(`>>> monitorAudioEnergy: Skipping processing this frame but keeping loop alive. isListening=${isListening}, isWaitingForFeedback=${isWaitingForFeedback}`);
            }
            return; // Skip processing audio for this frame but animation frame is already scheduled
        }
        
        // Get audio data for this frame
        if (!window.analyserNode) {
            console.error("analyserNode not available - cannot process audio");
            return; // Skip this frame but keep the loop running
        }
        
        window.analyserNode.getFloatTimeDomainData(window.audioDataArray);
        const currentAudioFrame = new Float32Array(window.audioDataArray); // Get a copy
        
        // --- Update Circular Buffer --- 
        const frameSize = window.analyserNode.fftSize;
        // Copy current frame into circular buffer
        for (let i = 0; i < frameSize; i++) {
            window.circularBuffer[(window.circularBufferIndex + i) % window.circularBuffer.length] = currentAudioFrame[i];
        }
        window.circularBufferIndex = (window.circularBufferIndex + frameSize) % window.circularBuffer.length;
        // --- End Circular Buffer Update --- 

        // Calculate RMS for the current frame
        let sumSquares = 0.0;
        for (const amplitude of currentAudioFrame) {
            sumSquares += amplitude * amplitude;
        }
        const rms = Math.sqrt(sumSquares / currentAudioFrame.length);

        // Determine the dynamic threshold
        const baseThreshold = ambientNoiseProfile ? 
                            (ambientNoiseProfile.rms * window.NOISE_THRESHOLD_FACTOR) : 
                            window.ENERGY_THRESHOLD; 
        const threshold = Math.max(baseThreshold, window.ENERGY_THRESHOLD);

        // --- REDUCED Frequency Logging ---
        logCounter++;
        if (logCounter % 60 === 0) { // Keep at roughly once per second
            const now = performance.now();
            console.log(`>>> monitorAudioEnergy | Time: ${now.toFixed(0)} | RMS: ${rms.toFixed(5)} | Threshold: ${threshold.toFixed(5)} | isSpeaking: ${isSpeaking}`);
        }
        // --- END REDUCED ---

        // Speech Detection State Machine
        if (isSpeaking) {
            if (rms > threshold) {
                // Still speaking 
                mainSpeechBuffer.push(currentAudioFrame); 
                speechFramesBuffered++; // Increment speech frame counter
                silenceFrames = 0; 
                isEndingSpeech = false; 
                postSpeechFrames = 0;
            } else {
                // Was speaking, now below threshold
                silenceFrames++;
                if (!isEndingSpeech) {
                    console.log(`Speech possibly ending... Counting silence/post-frames...`);
                    isEndingSpeech = true;
                    postSpeechFrames = 0; // Reset post-speech counter when ending phase starts
                    postSpeechFramesBuffered = 0; // Reset frame buffer counter too
                }
                
                const postSpeechSamplesTarget = Math.floor(window.POST_SPEECH_MS / 1000 * window.TARGET_SAMPLE_RATE);
                const postSpeechFramesTarget = Math.ceil(postSpeechSamplesTarget / frameSize);

                // Add post-speech padding frame if needed
                if (postSpeechFrames < postSpeechFramesTarget) {
                    mainSpeechBuffer.push(currentAudioFrame); 
                    postSpeechFrames++;
                    postSpeechFramesBuffered++; // Increment post frame counter
                }

                // Check if enough silence OR enough post-padding collected
                if (silenceFrames > window.MIN_SILENCE_FRAMES || postSpeechFrames >= postSpeechFramesTarget) {
                    // Only process if we have minimum speech duration (at least 10 frames, ~160ms)
                    const MIN_SPEECH_FRAMES = 10;
                    if (speechFramesBuffered >= MIN_SPEECH_FRAMES) {
                        console.log(`>>> DEBUG monitorAudioEnergy: Speech END detected. Calling handleSpeechEnd. (${speechFramesBuffered} frames)`);
                        const bufferToProcess = mainSpeechBuffer; 
                        isSpeaking = false;
                        isEndingSpeech = false;
                        mainSpeechBuffer = [];
                        // Pass frame counts to handler for logging
                        handleSpeechEnd(bufferToProcess, speechFramesBuffered, postSpeechFramesBuffered);
                    } else {
                        console.log(`>>> Speech too short (${speechFramesBuffered} frames < ${MIN_SPEECH_FRAMES}). Ignoring as noise.`);
                        isSpeaking = false;
                        isEndingSpeech = false;
                        mainSpeechBuffer = [];
                    } 

                    // Reset counters for next potential utterance
                    speechFramesBuffered = 0;
                    postSpeechFramesBuffered = 0;

                    // Reset UI indicator
                    const listeningIndicator = document.getElementById('listeningIndicator');
                    if(listeningIndicator) listeningIndicator.innerHTML = '<span class="material-icons">hearing</span> Listening...';
                }
            }
        } else { // Not currently speaking
            if (rms > threshold) {
                // --- Speech START --- 
                console.log(`Speech START detected (RMS: ${rms.toFixed(4)} > Threshold: ${threshold.toFixed(4)})`);
                isSpeaking = true;
                isEndingSpeech = false;
                postSpeechFrames = 0;
                silenceFrames = 0;
                speechFramesBuffered = 0; // Reset counters
                postSpeechFramesBuffered = 0;
                mainSpeechBuffer = []; 

                // Retrieve pre-speech padding 
                const startIdx = (window.circularBufferIndex - window.preSpeechSamples + window.circularBuffer.length) % window.circularBuffer.length;
                const preSpeechPadding = new Float32Array(window.preSpeechSamples);
                for (let i = 0; i < window.preSpeechSamples; i++) {
                    preSpeechPadding[i] = window.circularBuffer[(startIdx + i) % window.circularBuffer.length];
                }
                mainSpeechBuffer.push(preSpeechPadding);
                console.log(`Added ${window.preSpeechSamples} samples of pre-speech padding.`);

                // Add the current frame 
                mainSpeechBuffer.push(currentAudioFrame); 
                speechFramesBuffered++; // Count the first frame

                // Update UI indicator
                const listeningIndicator = document.getElementById('listeningIndicator');
                if(listeningIndicator) listeningIndicator.innerHTML = '<span class="material-icons">record_voice_over</span> Speech Detected';
            } else {
                // Still silent 
            }
        }

        // --- REDUCED Frequency Log before requesting next frame ---
        if (logCounter % 60 === 0) { // Log roughly once per second
            console.log(`>>> monitorAudioEnergy: End of frame check. isListening=${isListening}, isWaitingForFeedback=${isWaitingForFeedback}.`);
        }
        // --- END REDUCED ---
    } catch (error) {
        console.error("Error in monitorAudioEnergy:", error);
        // We still continue the loop since animationFrameId was already scheduled
    }
    
    // Note: Next animation frame is already scheduled at the top of this function
}

/**
 * Handle the end of a speech segment
 */
function handleSpeechEnd(speechBufferChunks, speechFrames, postFrames) { 
    console.log(`>>> DEBUG handleSpeechEnd: Function called.`);
    console.log(`handleSpeechEnd: Triggered. Received ${speechBufferChunks.length} chunks (Frames during speech: ${speechFrames}, Post-speech frames: ${postFrames}).`);
    if (!speechBufferChunks || speechBufferChunks.length === 0) {
        console.warn("handleSpeechEnd: Received empty buffer.");
        return;
    }
    
    // Combine the buffered chunks
    const totalLength = speechBufferChunks.reduce((sum, arr) => sum + arr.length, 0);
    const combinedAudio = new Float32Array(totalLength);
    let offset = 0;
    speechBufferChunks.forEach(chunk => {
        combinedAudio.set(chunk, offset);
        offset += chunk.length;
    });

    // Log stats of combined buffer 
    try {
        let cMin = combinedAudio[0], cMax = combinedAudio[0], cSum = 0;
        for(const amp of combinedAudio) {
            if (amp < cMin) cMin = amp;
            if (amp > cMax) cMax = amp;
            cSum += amp;
        }
        let cMean = totalLength > 0 ? cSum / totalLength : 0;
        console.log(`handleSpeechEnd: Combined audio stats: Actual Length=${totalLength}, Min=${cMin.toFixed(4)}, Max=${cMax.toFixed(4)}, Mean=${cMean.toFixed(4)}`);
        // Log expected length based on frames
        const expectedLength = window.preSpeechSamples + (speechFrames * window.FFT_SIZE) + (postFrames * window.FFT_SIZE);
        console.log(`handleSpeechEnd: Expected length based on frames: ${window.preSpeechSamples}(pre) + (${speechFrames}*${window.FFT_SIZE})(speech) + (${postFrames}*${window.FFT_SIZE})(post) = ${expectedLength}`);
    } catch (statError) {
        console.error("handleSpeechEnd: Error calculating combined audio stats:", statError);
    }
    // --- END Log stats --- 

    console.log(`>>> DEBUG handleSpeechEnd: Combined buffer length: ${combinedAudio.length}. Checking window.processAndSendSpeechChunk...`);
    if (typeof window.processAndSendSpeechChunk === 'function') {
        console.log(`>>> DEBUG handleSpeechEnd: Calling window.processAndSendSpeechChunk.`);
        window.processAndSendSpeechChunk(combinedAudio);
    } else {
        console.error("!!! ERROR handleSpeechEnd: window.processAndSendSpeechChunk is not defined or not a function!");
    }
}

/**
 * End the prediction session and clean up resources
 */
function endPredictionSession() {
    console.log("endPredictionSession called. Current state: isListening=" + isListening + ", isCapturingNoise=" + isCapturingNoise + ", isSpeaking=" + isSpeaking);
    
    // Force these flags to false first to prevent any race conditions
    const wasListening = isListening;
    const wasCapturingNoise = isCapturingNoise;
    
    // Force state to false immediately
    isListening = false;
    window.isListening = false; // Update window property
    isSpeaking = false;
    window.isSpeaking = false; // Update window property
    isEndingSpeech = false;
    isCapturingNoise = false;
    window.isCapturingNoise = false; // Update window property
    isWaitingForFeedback = false;
    window.isWaitingForFeedback = false; // Update window property
    
    // Stop noise capture if it was happening
    if (wasCapturingNoise) {
        console.log("Calling stopNoiseCapture because wasCapturingNoise=true");
        stopNoiseCapture(false); // Pass false to indicate cancellation
    }
    
    // Cancel any animation frame regardless of previous state
    if (animationFrameId) {
        console.log("Cancelling animationFrameId: " + animationFrameId);
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    } else {
        console.log("No animationFrameId to cancel");
    }

    // Clean up audio resources
    if (typeof window.cleanupAudioResources === 'function') {
        console.log("Calling window.cleanupAudioResources()");
        window.cleanupAudioResources();
    } else {
        console.warn("window.cleanupAudioResources not available");
    }
    
    // Reset current prediction
    window.currentPrediction = null;

    // Reset UI using the standard UI reset function
    if (typeof window.resetListeningUI === 'function') {
        console.log('endPredictionSession: Calling resetListeningUI.'); 
        window.resetListeningUI(); // This should reset button text/state too
    } else {
        console.error('endPredictionSession: resetListeningUI function not found.');
        // Manual fallback reset for button
        const predictButton = document.getElementById('predictButton');
        if (predictButton) {
            predictButton.innerHTML = '<span class="material-icons">mic</span> Predict';
            predictButton.classList.remove('mui-button-danger');
        }
    }
    
    // Force clear the prediction display explicitly
    const latestPrediction = document.getElementById('latestPrediction');
    if (latestPrediction) {
        latestPrediction.style.display = 'none';
        console.log("Explicitly hiding prediction display");
    }
    
    // Force hide feedback section
    const feedbackSection = document.getElementById('feedbackSection');
    if (feedbackSection) {
        feedbackSection.style.display = 'none';
        console.log("Explicitly hiding feedback section");
    }
    
    // --- ADDED: Stop Game Loop --- 
    if (typeof window.stopGameLoop === 'function') {
        console.log("endPredictionSession: Calling stopGameLoop().");
        window.stopGameLoop();
    }
    // --- END ADDED ---
    
    console.log("Prediction session ended. New state: isListening=" + isListening + ", isCapturingNoise=" + isCapturingNoise);
}

/**
 * Start ambient noise capture
 */
async function startNoiseCapture() {
    console.log("Starting ambient noise capture...");
    isCapturingNoise = true;
    window.isCapturingNoise = true; // Update window property
    noiseBuffer = []; 
    ambientNoiseProfile = null; 
    noiseCaptureStartTime = Date.now(); 

    const listeningIndicator = document.getElementById('listeningIndicator');
    if(listeningIndicator) {
         listeningIndicator.innerHTML = '<span class="material-icons">hourglass_top</span> Recording Noise (3s). Please be quiet...';
         listeningIndicator.style.display = 'block';
    }
    
    // Disable only ambient noise switch during capture
    document.getElementById('ambientNoiseSwitch').disabled = true;

    try {
        if (!await window.getAudioInput()) {
            return false; // Failed to get audio input
        }
        
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
        captureNoiseLoop(); // Start noise capture loop
        
        if (noiseCaptureTimeoutId) clearTimeout(noiseCaptureTimeoutId);
        noiseCaptureTimeoutId = setTimeout(() => {
            stopNoiseCapture(true); // Pass flag indicating it finished normally
        }, window.NOISE_CAPTURE_DURATION_MS);
        return true; // Indicate capture started

    } catch (error) {
        console.error("Error starting noise capture:", error);
        alert(`Could not start noise capture: ${error.message}`);
        window.handleAudioProcessingError(error); 
        isCapturingNoise = false;
        window.isCapturingNoise = false; // Update window property
        if(listeningIndicator) listeningIndicator.textContent = 'Noise Capture Error!';
        // Re-enable toggle
        document.getElementById('ambientNoiseSwitch').disabled = false;
        return false; // Indicate failure
    }
}

/**
 * Monitor audio for ambient noise capture
 */
function captureNoiseLoop() {
    if (!isCapturingNoise) return; 

    window.analyserNode.getFloatTimeDomainData(window.audioDataArray);
    noiseBuffer.push(new Float32Array(window.audioDataArray));

    const elapsedMs = Date.now() - noiseCaptureStartTime;
    const remainingSec = Math.max(0, (window.NOISE_CAPTURE_DURATION_MS - elapsedMs) / 1000).toFixed(1);
    const listeningIndicator = document.getElementById('listeningIndicator');
    if (listeningIndicator) listeningIndicator.innerHTML = `<span class="material-icons">hourglass_top</span> Recording Noise (${remainingSec}s)...`;

    animationFrameId = requestAnimationFrame(captureNoiseLoop);
}

/**
 * Stop noise capture and analyze the results
 */
function stopNoiseCapture(captureFinished = false) {
    // --- ADDED: Log the call source --- 
    console.log("--- stopNoiseCapture called --- ");
    console.trace("Call stack for stopNoiseCapture:"); // Print stack trace
    // --- END LOG ---
    
    let success = false;
    isCapturingNoise = false;
    window.isCapturingNoise = false; // Update window property
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
     if (noiseCaptureTimeoutId) {
        clearTimeout(noiseCaptureTimeoutId);
        noiseCaptureTimeoutId = null;
    }
    
    const listeningIndicator = document.getElementById('listeningIndicator'); 

    if (noiseBuffer.length > 0 && captureFinished) {
        // Calculate average RMS of all captured frames
        let totalSumSquares = 0;
        let totalSamples = 0;
        noiseBuffer.forEach(chunk => {
            for (const amp of chunk) { totalSumSquares += amp * amp; }
            totalSamples += chunk.length;
        });
        const avgRms = totalSamples > 0 ? Math.sqrt(totalSumSquares / totalSamples) : 0;
        ambientNoiseProfile = { rms: avgRms }; 
        lastNoiseCaptureTime = Date.now(); 
        console.log(`Ambient noise profile calculated: Average RMS=${avgRms.toFixed(5)}`);
        if (listeningIndicator) listeningIndicator.textContent = 'Noise Profile Captured!';
        success = true;
    } else {
        console.warn(captureFinished ? "No noise data captured." : "Noise capture cancelled.");
        ambientNoiseProfile = null;
        lastNoiseCaptureTime = null; 
        if (listeningIndicator) listeningIndicator.textContent = captureFinished ? 'Noise Capture Failed!' : 'Noise Capture Cancelled.';
        success = false;
    }
    noiseBuffer = []; // Clear buffer regardless
    
    // Re-enable ambient noise switch
    document.getElementById('ambientNoiseSwitch').disabled = false;
    return success; // Return whether profile was calculated
}

/**
 * Audio system function to resume listening after feedback is provided
 * This is the implementation that handles the actual audio restart
 */
async function audioResumeListeningAfterFeedback() {
    console.log("=== AUDIO SYSTEM: STARTING COMPLETE AUDIO RESET AND RESTART ===");
    
    try {
        // 1. First, completely clean everything up (like end session does)
        console.log("Step 1: Cleanup - cancelling frames, resetting states");
        if (animationFrameId) {
            cancelAnimationFrame(animationFrameId);
            animationFrameId = null;
            console.log("- Cancelled animation frame");
        }
        
        // Reset all state variables
        isListening = false;
        window.isListening = false;
        isSpeaking = false;
        window.isSpeaking = false;
        isEndingSpeech = false;
        isWaitingForFeedback = false;
        window.isWaitingForFeedback = false;
        console.log("- Reset all state variables to false");
        
        // 2. Clean up audio resources completely
        console.log("Step 2: Audio cleanup");
        if (typeof window.cleanupAudioResources === 'function') {
            window.cleanupAudioResources();
            console.log("- Cleaned up audio resources");
        }
        
        // 3. Clear UI display elements but keep history/stats
        console.log("Step 3: UI cleanup");
        const listeningIndicator = document.getElementById('listeningIndicator');
        if (listeningIndicator) {
            listeningIndicator.innerHTML = '<span class="material-icons">refresh</span> Restarting audio...';
            listeningIndicator.style.display = 'block';
            console.log("- Updated indicator to 'Restarting audio'");
        }
        
        const latestPrediction = document.getElementById('latestPrediction');
        if (latestPrediction) {
            latestPrediction.style.display = 'none';
            console.log("- Hidden latest prediction display");
        }
        
        const feedbackSection = document.getElementById('feedbackSection');
        if (feedbackSection) {
            feedbackSection.innerHTML = '';
            feedbackSection.style.display = 'none';
            console.log("- Cleared feedback section");
        }
        
        // Keep history/stats visible
        const predictionHistoryCard = document.getElementById('predictionHistoryCard');
        if (predictionHistoryCard) {
            predictionHistoryCard.style.display = 'block';
        }
        
        const confusionMatrixContainer = document.getElementById('confusionMatrixContainer');
        if (confusionMatrixContainer) {
            confusionMatrixContainer.style.display = 'block';
        }
        
        // 4. Reinitialize audio system from scratch
        console.log("Step 4: Reinitializing audio processing system");
        if (typeof window.initAudioProcessing === 'function') {
            const initSuccess = await window.initAudioProcessing();
            if (!initSuccess) {
                throw new Error("Failed to initialize audio system");
            }
            console.log("- Successfully initialized audio processing");
        } else {
            throw new Error("initAudioProcessing function not available");
        }
        
        // 5. Get fresh audio input (microphone access)
        console.log("Step 5: Getting audio input (mic access)");
        if (typeof window.getAudioInput === 'function') {
            const inputSuccess = await window.getAudioInput();
            if (!inputSuccess) {
                throw new Error("Failed to get audio input");
            }
            console.log("- Successfully got audio input");
        } else {
            throw new Error("getAudioInput function not available");
        }
        
        // 6. Set up system for new monitoring
        console.log("Step 6: Setting up for new monitoring session");
        // Reset variables for clean start
        silenceFrames = 0;
        postSpeechFrames = 0;
        mainSpeechBuffer = [];
        window.circularBufferIndex = 0;
        if (window.circularBuffer) {
            window.circularBuffer.fill(0);
            console.log("- Reset circular buffer");
        }
        
        // 7. Set state to listening and start monitoring
        console.log("Step 7: Starting monitoring");
        isListening = true;
        window.isListening = true;
        
        if (listeningIndicator) {
            listeningIndicator.innerHTML = '<span class="material-icons">hearing</span> Listening...';
            console.log("- Updated indicator to 'Listening'");
        }
        
        // Start the monitoring loop
        console.log("- Starting monitorAudioEnergy");
        monitorAudioEnergy();
        
        console.log("=== AUDIO RESTART COMPLETE ===");
        
    } catch (error) {
        console.error("ERROR DURING AUDIO RESTART:", error);
        alert("Error restarting audio system. Please refresh the page and try again.");
        
        // Try to update the UI to reflect the error
        const listeningIndicator = document.getElementById('listeningIndicator');
        if (listeningIndicator) {
            listeningIndicator.innerHTML = '<span class="material-icons">error</span> Audio Error! Refresh the page.';
            listeningIndicator.style.color = 'red';
        }
    }
}

// Alias for compatibility - old name points to new function
const resumeListeningAfterFeedback = audioResumeListeningAfterFeedback;

// --- ADDED: Function to explicitly stop the animation loop --- 
function stopMonitorLoop() {
    if (animationFrameId) {
        console.log(`>>> stopMonitorLoop: Cancelling animation frame ID: ${animationFrameId}`);
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    } else {
        console.log(">>> stopMonitorLoop: No animation frame ID to cancel.");
    }
}
// --- END ADDED --- 

// Export to global scope (Initial values are set here, subsequent updates happen in functions)
window.isListening = isListening;
window.isSpeaking = isSpeaking;
window.isCapturingNoise = isCapturingNoise; // Define it here initially
window.silenceFrames = silenceFrames;
window.postSpeechFrames = postSpeechFrames;
window.mainSpeechBuffer = mainSpeechBuffer;
window.PRE_SPEECH_MS = PRE_SPEECH_MS;
window.pauseForFeedback = pauseForFeedback;
window.ambientNoiseProfile = ambientNoiseProfile;

window.startPredictionSession = startPredictionSession;
window.monitorAudioEnergy = monitorAudioEnergy;
window.handleSpeechEnd = handleSpeechEnd;
window.endPredictionSession = endPredictionSession;
window.startNoiseCapture = startNoiseCapture;
window.stopNoiseCapture = stopNoiseCapture;
window.resumeListeningAfterFeedback = resumeListeningAfterFeedback; // Keep old name for compatibility
window.audioResumeListeningAfterFeedback = audioResumeListeningAfterFeedback; // Export with new distinct name
window.stopMonitorLoop = stopMonitorLoop; // Export new function 