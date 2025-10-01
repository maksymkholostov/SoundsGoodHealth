/**
 * predict_audio_processing.js
 * Handles audio processing, encoding, and resampling functions
 */

// Target audio parameters
// Remove duplicate declaration and use global variable from predict_audio_core.js
// let TARGET_SAMPLE_RATE = 16000; // Hz
const SAMPLE_WIDTH = 2; // bytes (16-bit PCM)
const MAX_ALLOWED_SAMPLE_RATE = 48000; // Hz - highest rate we'll accept
const WAV_HEADER_SIZE = 44; // bytes - standard WAV header size

// Debug options
let DEBUG_AUDIO = false;
let DEBUG_SPEECH_DETECTION = false;
let ALWAYS_SHOW_DEBUG_WAVEFORMS = false;

/**
 * Process a speech chunk and send it to the server
 * @param {Float32Array} audioData - Float32Array of audio samples
 */
function processAndSendSpeechChunk(audioData) {
    console.log(`Processing speech chunk: ${audioData.length} samples`);
    if (!window.selectedModelId) {
        window.showToast("No model selected!", "error");
        return;
    }
    
    let processingMethod = null;
    try {
        // Clamp audio samples to the [-1, 1] range to prevent clipping
        for (let i = 0; i < audioData.length; i++) {
            audioData[i] = Math.max(-1.0, Math.min(1.0, audioData[i]));
        }
        
        // Get actual audio context sample rate and calculate appropriate resampling
        const actualSampleRate = window.audioContext.sampleRate;
        if (actualSampleRate > MAX_ALLOWED_SAMPLE_RATE) {
            console.warn(`Very high sample rate detected: ${actualSampleRate}Hz. This may cause issues. Maximum recommended: ${MAX_ALLOWED_SAMPLE_RATE}Hz.`);
        }
        
        // Different approaches to resampling based on situation
        if (actualSampleRate === window.TARGET_SAMPLE_RATE) {
            // No resampling needed, use the audio directly
            processingMethod = "direct (no resampling)";
            sendAudioToServer(audioData, window.TARGET_SAMPLE_RATE);
        } else if (actualSampleRate % window.TARGET_SAMPLE_RATE === 0) {
            // Simple decimation resampling (skip samples)
            const factor = actualSampleRate / window.TARGET_SAMPLE_RATE;
            processingMethod = `decimation (factor: ${factor})`;
            const resampled = simpleDecimation(audioData, factor);
            sendAudioToServer(resampled, window.TARGET_SAMPLE_RATE);
        } else {
            // More complex linear interpolation resampling for non-integer factors
            const factor = actualSampleRate / window.TARGET_SAMPLE_RATE;
            processingMethod = `linear interpolation (factor: ${factor})`;
            const resampled = linearResample(audioData, actualSampleRate, window.TARGET_SAMPLE_RATE);
            sendAudioToServer(resampled, window.TARGET_SAMPLE_RATE);
        }
        console.log(`Audio processed using ${processingMethod}`);
        
        // For debugging only - Show waveform visualization if enabled
        if (DEBUG_AUDIO || ALWAYS_SHOW_DEBUG_WAVEFORMS) {
            visualizeWaveformInCanvas(audioData, "originalWaveform");
        }
    } catch (error) {
        window.showToast("Audio processing error: " + error.message, "error");
        console.error("Error processing audio chunk:", error);
    }
}

/**
 * Send audio data to the server for prediction
 * @param {Float32Array} audioData - Float32Array of audio samples
 * @param {number} sampleRate - Sample rate of the audio data
 */
function sendAudioToServer(audioData, sampleRate) {
    console.log(`Sending audio to server: ${audioData.length} samples at ${sampleRate}Hz`);
    
    try {
        // Convert to WAV
        const wavBytes = encodeWAV(audioData, sampleRate);
        
        // Update status UI
        const statusElement = document.getElementById('statusMessage');
        if (statusElement) statusElement.textContent = 'Processing...';
        
        // Update listening indicator if exists
        const listeningIndicator = document.getElementById('listeningIndicator');
        if (listeningIndicator && window.isListening) {
            listeningIndicator.innerHTML = '<span class="material-icons">cloud_upload</span> Sending to server...';
        }
        
        // Debug stats
        if (DEBUG_AUDIO) {
            console.log(`WAV encoded data: ${wavBytes.byteLength} bytes`);
            console.log(`Audio duration: ~${(audioData.length / sampleRate).toFixed(2)}s`);
        }
        
        // Send data to server
        window.submitPrediction(wavBytes, audioData.length, sampleRate);
    } catch (error) {
        window.showToast("Error sending audio: " + error.message, "error");
        console.error("Error sending audio to server:", error);
        
        // Update status UI on failure
        const statusElement = document.getElementById('statusMessage');
        if (statusElement) statusElement.textContent = 'Error: ' + error.message;
        
        // Reset listening indicator
        const listeningIndicator = document.getElementById('listeningIndicator');
        if (listeningIndicator && window.isListening) {
            listeningIndicator.innerHTML = '<span class="material-icons">hearing</span> Listening...';
        }
    }
}

/**
 * Simple decimation resampling - only works well for integer factors
 * @param {Float32Array} audioData - Input audio data
 * @param {number} factor - Downsampling factor (must be >= 1)
 * @returns {Float32Array} - Resampled audio data
 */
function simpleDecimation(audioData, factor) {
    if (factor === 1) return audioData; // No change needed
    if (factor < 1) throw new Error("Decimation factor must be >= 1");
    
    const outputLength = Math.floor(audioData.length / factor);
    const result = new Float32Array(outputLength);
    
    for (let i = 0; i < outputLength; i++) {
        result[i] = audioData[Math.floor(i * factor)];
    }
    
    return result;
}

/**
 * Linear interpolation resampling - works for any resampling factor
 * @param {Float32Array} audioData - Input audio data
 * @param {number} inputRate - Input sample rate
 * @param {number} outputRate - Desired output sample rate
 * @returns {Float32Array} - Resampled audio data
 */
function linearResample(audioData, inputRate, outputRate) {
    const factor = inputRate / outputRate;
    const outputLength = Math.floor(audioData.length / factor);
    const result = new Float32Array(outputLength);
    
    for (let i = 0; i < outputLength; i++) {
        const exactIdx = i * factor;
        const lowIdx = Math.floor(exactIdx);
        const highIdx = Math.min(lowIdx + 1, audioData.length - 1);
        const fraction = exactIdx - lowIdx;
        
        // Linear interpolation between adjacent samples
        result[i] = audioData[lowIdx] * (1 - fraction) + audioData[highIdx] * fraction;
    }
    
    return result;
}

/**
 * Encode a Float32Array of audio samples to a WAV file
 * @param {Float32Array} samples - Audio samples in the range [-1.0, 1.0]
 * @param {number} sampleRate - Sample rate of the audio
 * @returns {ArrayBuffer} - WAV file as an ArrayBuffer
 */
function encodeWAV(samples, sampleRate) {
    // Calculate sizes
    const numSamples = samples.length;
    const dataSize = numSamples * SAMPLE_WIDTH;
    const fileSize = WAV_HEADER_SIZE + dataSize;
    
    // Create buffer and view
    const buffer = new ArrayBuffer(fileSize);
    const view = new DataView(buffer);
    
    // Write WAV header
    // "RIFF" chunk descriptor
    writeString(view, 0, 'RIFF');
    view.setUint32(4, fileSize - 8, true);
    writeString(view, 8, 'WAVE');
    
    // "fmt " sub-chunk
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // fmt chunk size
    view.setUint16(20, 1, true); // format code: 1 for PCM
    view.setUint16(22, 1, true); // number of channels
    view.setUint32(24, sampleRate, true); // sample rate
    view.setUint32(28, sampleRate * SAMPLE_WIDTH, true); // byte rate
    view.setUint16(32, SAMPLE_WIDTH, true); // block align
    view.setUint16(34, SAMPLE_WIDTH * 8, true); // bits per sample
    
    // "data" sub-chunk
    writeString(view, 36, 'data');
    view.setUint32(40, dataSize, true); // data chunk size
    
    // Write audio data (convert float to 16-bit PCM)
    let offset = 44; // Start of data
    for (let i = 0; i < numSamples; i++, offset += 2) {
        const sample = Math.max(-1, Math.min(1, samples[i]));
        const s16 = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(offset, s16, true);
    }
    
    return buffer;
}

/**
 * Helper to write a string to a DataView
 * @param {DataView} view - Target DataView
 * @param {number} offset - Byte offset
 * @param {string} str - String to write
 */
function writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}

/**
 * Visualize audio waveform in a canvas for debugging
 * @param {Float32Array} audioData - Audio data to visualize
 * @param {string} canvasId - ID of the canvas element
 */
function visualizeWaveformInCanvas(audioData, canvasId = "waveformCanvas") {
    try {
        // Find or create the canvas
        let canvas = document.getElementById(canvasId);
        if (!canvas) {
            const debugContainer = document.getElementById('debugContainer') || document.body;
            canvas = document.createElement('canvas');
            canvas.id = canvasId;
            canvas.width = 600;
            canvas.height = 150;
            canvas.style.border = '1px solid #ccc';
            canvas.style.marginTop = '10px';
            canvas.style.display = 'block';
            
            // Add a label before the canvas
            const label = document.createElement('div');
            label.textContent = 'Debug Audio Waveform:';
            label.style.marginTop = '10px';
            label.style.fontWeight = 'bold';
            
            debugContainer.appendChild(label);
            debugContainer.appendChild(canvas);
        }
        
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        
        // Clear canvas
        ctx.fillStyle = '#f8f8f8';
        ctx.fillRect(0, 0, width, height);
        
        // Draw audio waveform
        ctx.beginPath();
        ctx.strokeStyle = '#3498db';
        ctx.lineWidth = 1;
        
        const sliceWidth = width / audioData.length;
        let x = 0;
        
        for (let i = 0; i < audioData.length; i++) {
            const y = (audioData[i] * 0.5 + 0.5) * height;
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
            x += sliceWidth;
        }
        
        ctx.stroke();
        
        // Draw threshold lines if applicable
        if (window.ENERGY_THRESHOLD) {
            // Convert energy threshold to amplitude for visualization
            const thresholdAmplitude = Math.sqrt(window.ENERGY_THRESHOLD);
            const thresholdY = (1 - thresholdAmplitude) * height / 2;
            
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(255, 0, 0, 0.5)';
            ctx.setLineDash([5, 5]);
            ctx.moveTo(0, thresholdY);
            ctx.lineTo(width, thresholdY);
            
            // Mirror for negative threshold
            ctx.moveTo(0, height - thresholdY);
            ctx.lineTo(width, height - thresholdY);
            
            ctx.stroke();
            ctx.setLineDash([]);
        }
    } catch (error) {
        console.error("Error visualizing waveform:", error);
    }
}

// Export to global scope
window.SAMPLE_WIDTH = SAMPLE_WIDTH;
window.MAX_ALLOWED_SAMPLE_RATE = MAX_ALLOWED_SAMPLE_RATE;
window.WAV_HEADER_SIZE = WAV_HEADER_SIZE;
window.DEBUG_AUDIO = DEBUG_AUDIO;
window.DEBUG_SPEECH_DETECTION = DEBUG_SPEECH_DETECTION;
window.ALWAYS_SHOW_DEBUG_WAVEFORMS = ALWAYS_SHOW_DEBUG_WAVEFORMS;

window.processAndSendSpeechChunk = processAndSendSpeechChunk;
window.sendAudioToServer = sendAudioToServer;
window.simpleDecimation = simpleDecimation;
window.linearResample = linearResample;
window.encodeWAV = encodeWAV;
window.visualizeWaveformInCanvas = visualizeWaveformInCanvas; 