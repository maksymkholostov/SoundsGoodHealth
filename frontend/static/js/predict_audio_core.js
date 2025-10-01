/**
 * predict_audio_core.js
 * Core audio state and initialization functions
 */

// Global state variables
let audioContext = null;
let mediaStreamSource = null;
let analyserNode = null;
let audioDataArray = null;
// Define as const to prevent redefinition issues
const TARGET_SAMPLE_RATE = 16000;
const FFT_SIZE = 512;

// Global configuration
const ENERGY_THRESHOLD = 0.02; // Default threshold if no noise profile (Increased to reduce sensitivity)
const NOISE_THRESHOLD_FACTOR = 3.0; // Speech RMS must be N times noise RMS (Increased to reduce false triggers)
const MIN_SILENCE_FRAMES = 8; // Approx 130ms of silence indicates end of speech (8 * ~16.7ms/frame)
const POST_SPEECH_MS = 30; // How much audio to capture *after* energy drops
const NOISE_CAPTURE_DURATION_MS = 3000; 
const NOISE_REMINDER_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

/**
 * Initialize the audio processing components
 */
async function initAudioProcessing() {
    console.log("Attempting to initialize AudioContext and AnalyserNode...");
    try {
        if (audioContext) {
            console.log("AudioContext already exists, resuming if needed");
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }
            return true;
        }
        
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        // Explicitly request TARGET_SAMPLE_RATE for analysis context
        audioContext = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE }); 
        // --- Enhanced logging for sample rate --- 
        const actualSampleRate = audioContext.sampleRate;
        console.log(`
------------------------------------------------------
AUDIO CONTEXT INITIALIZED:
- Requested Sample Rate: ${TARGET_SAMPLE_RATE}Hz
- Actual Sample Rate:    ${actualSampleRate}Hz
- Sample Rate Match:     ${actualSampleRate === TARGET_SAMPLE_RATE ? '✓ YES' : '✗ NO'}
${actualSampleRate !== TARGET_SAMPLE_RATE ? 
  `- IMPORTANT: Audio will be resampled from ${actualSampleRate}Hz to ${TARGET_SAMPLE_RATE}Hz for classification` : 
  ''}
------------------------------------------------------`);
        // --- End enhanced logging ---
        
        analyserNode = audioContext.createAnalyser();
        analyserNode.fftSize = FFT_SIZE;
        audioDataArray = new Float32Array(analyserNode.fftSize); 
        
        // Initialize circular buffer based on PRE_SPEECH_MS
        window.preSpeechSamples = Math.floor(window.PRE_SPEECH_MS / 1000 * TARGET_SAMPLE_RATE);
        const circularBufferFrames = Math.ceil(window.preSpeechSamples / analyserNode.fftSize); // Number of analysis frames needed
        const circularBufferLength = circularBufferFrames * analyserNode.fftSize; // Ensure multiple of fftSize
        window.circularBuffer = new Float32Array(circularBufferLength);
        window.circularBufferIndex = 0;
        window.preSpeechSamples = circularBufferLength; // Store the actual buffer length in samples
        console.log(`AudioContext initialized, AnalyserNode (fftSize: ${analyserNode.fftSize}), CircularBuffer (Length: ${circularBufferLength} samples ≈ ${circularBufferLength/TARGET_SAMPLE_RATE*1000}ms)`);
        
        // Set window globals explicitly
        window.audioContext = audioContext;
        window.analyserNode = analyserNode;
        window.audioDataArray = audioDataArray;
        
        return true;
    } catch (error) {
        console.error("Error initializing audio processing:", error);
        alert(`Audio setup failed: ${error.message}`);
        return false;
    }
}

/**
 * Get microphone access and create media stream
 */
async function getAudioInput() {
    try {
        // First ensure audio processing is initialized
        if (!audioContext || !analyserNode) {
            console.log("Audio context or analyser not initialized, initializing now");
            if (!await initAudioProcessing()) {
                console.error("Failed to initialize audio processing");
                return null;
            }
        }
        
        // Resume context if suspended
        if (audioContext.state === 'suspended') {
            console.log("AudioContext suspended, resuming...");
            await audioContext.resume();
        }
        
        if (!mediaStreamSource) {
            console.log("Requesting microphone access...");
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: { 
                    sampleRate: TARGET_SAMPLE_RATE, 
                    channelCount: 1, 
                    echoCancellation: true, 
                    noiseSuppression: true 
                } 
            });
            
            console.log("Microphone access granted, creating media stream source");
            mediaStreamSource = audioContext.createMediaStreamSource(stream);
            mediaStreamSource.connect(analyserNode);
            
            // Set window global
            window.mediaStreamSource = mediaStreamSource;
            
            console.log("Created and connected new media stream source");
        } else {
            console.log("Using existing media stream source");
        }
        
        // Verify analyzer node is properly setup
        if (!analyserNode) {
            throw new Error("AnalyserNode is null after setup. This should not happen.");
        }
        
        // Do a test read to ensure the analyzer is working
        const testArray = new Float32Array(analyserNode.fftSize);
        try {
            analyserNode.getFloatTimeDomainData(testArray);
            console.log("Successfully tested analyzer node data reading");
        } catch (err) {
            console.error("Error testing analyzer node:", err);
            throw new Error("Audio analyzer failed to initialize properly");
        }
        
        return mediaStreamSource;
    } catch (error) {
        console.error("Error accessing microphone:", error);
        handleAudioProcessingError(error);
        return null;
    }
}

/**
 * Handle errors from audio processing
 */
function handleAudioProcessingError(error) {
    console.error('Audio Processing Error:', error);
    let userMessage = `Audio error: ${error.message || error.name || 'Unknown error'}`;
    
    if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        userMessage = 'Microphone access denied. Please allow microphone access in your browser settings.';
    } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        userMessage = 'No microphone found. Please ensure a microphone is connected and enabled.';
    } else if (error.name === 'NotReadableError') {
        userMessage = 'Microphone is already in use by another application or tab.';
    }
    
    alert(userMessage);
    
    if (window.isListening) {
        window.endPredictionSession(); // Ensure cleanup happens on error
    }
}

/**
 * Clean up audio resources
 */
function cleanupAudioResources() {
    if (mediaStreamSource) {
        const stream = mediaStreamSource.mediaStream;
        if (stream) {
            console.log("Stopping media stream tracks...");
            try { 
                stream.getTracks().forEach(track => track.stop());
                console.log("Media stream tracks stopped.");
            } catch (e) { console.error('Error stopping media stream tracks:', e); }
        }
        
        try {
            mediaStreamSource.disconnect();
            console.log("Disconnected media stream source.");
        } catch(e) { console.warn('Error disconnecting media stream source:', e); }
        
        mediaStreamSource = null;
    }
    
    // We don't close the audioContext as it could be reused
}

/**
 * Simple utility to show toast notifications
 */
function showToast(message, type = 'info') {
    console.log(`[Toast-${type}] ${message}`);
}

// Export to global scope
window.audioContext = audioContext;
window.mediaStreamSource = mediaStreamSource;
window.analyserNode = analyserNode;
window.audioDataArray = audioDataArray;
window.TARGET_SAMPLE_RATE = TARGET_SAMPLE_RATE;
window.FFT_SIZE = FFT_SIZE;
window.ENERGY_THRESHOLD = ENERGY_THRESHOLD;
window.NOISE_THRESHOLD_FACTOR = NOISE_THRESHOLD_FACTOR;
window.MIN_SILENCE_FRAMES = MIN_SILENCE_FRAMES;
window.POST_SPEECH_MS = POST_SPEECH_MS;
window.NOISE_CAPTURE_DURATION_MS = NOISE_CAPTURE_DURATION_MS;
window.NOISE_REMINDER_INTERVAL_MS = NOISE_REMINDER_INTERVAL_MS;

window.initAudioProcessing = initAudioProcessing;
window.getAudioInput = getAudioInput;
window.handleAudioProcessingError = handleAudioProcessingError;
window.cleanupAudioResources = cleanupAudioResources;
window.showToast = showToast; 