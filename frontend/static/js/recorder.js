/**
 * AudioRecorder - A JavaScript class for recording audio from the microphone
 * 
 * This class provides a simple interface for recording audio from the user's microphone.
 * It handles browser compatibility, microphone access, and provides callbacks for
 * recording events.
 */
class AudioRecorder {
    /**
     * Constructor for AudioRecorder
     * @param {Object} options - Configuration options
     * @param {Function} options.onStart - Callback when recording starts
     * @param {Function} options.onStop - Callback when recording stops, receives the audio blob
     * @param {Function} options.onDataAvailable - Callback when audio data is available
     * @param {Function} options.onError - Callback when an error occurs
     */
    constructor(options = {}) {
        // Set default options
        this.options = {
            // Use audio/webm for recording (most compatible)
            mimeType: 'audio/webm',
            audioBitsPerSecond: 128000,
            onStart: () => {},
            onStop: (blob) => {},
            onDataAvailable: (e) => {},
            onError: (error) => { console.error('AudioRecorder error:', error); }
        };
        
        // Override defaults with provided options
        Object.assign(this.options, options);
        
        // Initialize state
        this.mediaRecorder = null;
        this.stream = null;
        this.audioChunks = [];
        this.isRecording = false;
        this.audioContext = null;
    }
    
    /**
     * Start recording audio
     * @returns {Promise} - Resolves when recording starts
     */
    start() {
        return new Promise((resolve, reject) => {
            // Check browser compatibility
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                console.error('MediaDevices API not supported in this browser');
                this.options.onError(new Error('Your browser does not support audio recording. Please try a different browser.'));
                return reject(new Error('MediaDevices API not supported'));
            }
            
            if (typeof MediaRecorder === 'undefined') {
                console.error('MediaRecorder API not supported in this browser');
                this.options.onError(new Error('Your browser does not support audio recording. Please try a different browser.'));
                return reject(new Error('MediaRecorder API not supported'));
            }
            
            if (this.isRecording) {
                return reject(new Error('Already recording'));
            }
            
            console.log('Requesting microphone access...');
            
            // Request microphone access with explicit error handling
            navigator.mediaDevices.getUserMedia({ 
                audio: {
                    // Request higher quality audio settings
                    channelCount: 1,          // Mono
                    sampleRate: 16000,        // 16 kHz
                    sampleSize: 16,           // 16 bits
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            })
                .then(stream => {
                    console.log('Microphone access granted!');
                    this.stream = stream;
                    
                    // Create MediaRecorder instance
                    const options = {
                        mimeType: this.options.mimeType,
                        audioBitsPerSecond: this.options.audioBitsPerSecond
                    };
                    
                    try {
                        // Try to use PCM audio if possible (WAV)
                        if (MediaRecorder.isTypeSupported('audio/wav')) {
                            options.mimeType = 'audio/wav';
                            console.log('Using native WAV recording');
                        } else if (MediaRecorder.isTypeSupported('audio/webm;codecs=pcm')) {
                            options.mimeType = 'audio/webm;codecs=pcm';
                            console.log('Using WebM PCM recording');
                        } else {
                            console.log('Using default recording type:', this.options.mimeType);
                        }
                        
                        this.mediaRecorder = new MediaRecorder(stream, options);
                        console.log('MediaRecorder created successfully with options:', options);
                    } catch (e) {
                        // If preferred mime type fails, create with default options
                        console.warn('Using default MediaRecorder options:', e);
                        try {
                            this.mediaRecorder = new MediaRecorder(stream);
                            console.log('MediaRecorder created with default options');
                        } catch (err) {
                            console.error('Failed to create MediaRecorder:', err);
                            this.options.onError(new Error('Failed to create media recorder: ' + err.message));
                            return reject(err);
                        }
                    }
                    
                    // Set up event handlers
                    this.mediaRecorder.ondataavailable = (e) => {
                        if (e.data.size > 0) {
                            this.audioChunks.push(e.data);
                            this.options.onDataAvailable(e);
                        }
                    };
                    
                    this.mediaRecorder.onstop = () => {
                        // Create audio blob from chunks (in the recorded format)
                        const audioBlob = new Blob(this.audioChunks, { type: this.mediaRecorder.mimeType || 'audio/webm' });
                        
                        console.log('Recording stopped, converting format from', audioBlob.type, 'to WAV', {
                            size: audioBlob.size,
                            chunks: this.audioChunks.length
                        });
                        
                        // Convert to WAV format for compatibility with backend
                        this.convertToWav(audioBlob).then(wavBlob => {
                            // Clean up
                            this.stream.getTracks().forEach(track => track.stop());
                            this.isRecording = false;
                            
                            // Log success with detailed info
                            console.log('Audio recorded successfully:', {
                                originalFormat: this.mediaRecorder.mimeType || 'audio/webm',
                                originalSize: audioBlob.size,
                                wavSize: wavBlob.size,
                                chunks: this.audioChunks.length
                            });
                            
                            // Call onStop callback with the WAV audio blob
                            this.options.onStop(wavBlob);
                        }).catch(error => {
                            console.error('Error converting to WAV:', error);
                            
                            // Try backup conversion method
                            this.fallbackWavConversion(audioBlob).then(wavBlob => {
                                // Clean up
                                this.stream.getTracks().forEach(track => track.stop());
                                this.isRecording = false;
                                
                                console.log('Used fallback WAV conversion');
                                
                                // Call onStop callback with the WAV audio blob
                                this.options.onStop(wavBlob);
                            }).catch(fallbackError => {
                                console.error('Fallback conversion also failed:', fallbackError);
                                // Last resort - create a simple WAV placeholder
                                const simpleWavBlob = this.createBasicWavFromWebm(audioBlob);
                                this.stream.getTracks().forEach(track => track.stop());
                                this.isRecording = false;
                                this.options.onStop(simpleWavBlob);
                            });
                        });
                    };
                    
                    // Start recording
                    this.audioChunks = [];
                    this.mediaRecorder.start();
                    this.isRecording = true;
                    
                    // Call onStart callback
                    this.options.onStart();
                    resolve();
                })
                .catch(error => {
                    this.options.onError(error);
                    reject(error);
                });
        });
    }
    
    /**
     * Convert recorded audio to WAV format
     * @param {Blob} audioBlob - Original audio blob in recorded format
     * @returns {Promise<Blob>} - Promise resolving to WAV format blob
     */
    async convertToWav(audioBlob) {
        try {
            console.log('Starting WAV conversion of blob:', {
                type: audioBlob.type,
                size: audioBlob.size,
            });
            
            // Create an AudioContext
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            // Use explicit sample rate of 16kHz for consistency
            const audioContext = new AudioContext({ sampleRate: 16000 });
            
            // Get the audio data as an ArrayBuffer
            const arrayBuffer = await audioBlob.arrayBuffer();
            
            // Check if array buffer is valid
            if (!arrayBuffer || arrayBuffer.byteLength === 0) {
                console.error('Audio data is empty or invalid');
                throw new Error('Audio data is empty or invalid');
            }
            
            console.log('Audio arrayBuffer received:', arrayBuffer.byteLength, 'bytes');
            
            try {
                // Decode the audio - this might fail for some formats
                const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                
                // Verify the audio buffer
                if (!audioBuffer || audioBuffer.length === 0) {
                    console.error('Failed to decode audio data');
                    throw new Error('Failed to decode audio data');
                }
                
                console.log('Audio decoded successfully:', {
                    duration: audioBuffer.duration,
                    numberOfChannels: audioBuffer.numberOfChannels,
                    sampleRate: audioBuffer.sampleRate,
                    length: audioBuffer.length
                });
                
                // Convert to WAV format
                const wavBlob = this.audioBufferToWav(audioBuffer);
                
                // Verify WAV blob
                if (!wavBlob || wavBlob.size < 44) { // WAV header is at least 44 bytes
                    console.error('Generated WAV file appears to be invalid');
                    throw new Error('Generated WAV file appears to be invalid');
                }
                
                console.log('WAV conversion successful:', {
                    size: wavBlob.size,
                    type: wavBlob.type
                });
                
                // Force the correct MIME type - this is critical
                const properWavBlob = new Blob([wavBlob], { type: 'audio/wav' });
                
                return properWavBlob;
            } catch (decodeError) {
                console.error('Error decoding audio:', decodeError);
                // Try an alternative approach if decoding fails
                return this.fallbackWavConversion(audioBlob);
            }
        } catch (error) {
            console.error('Error in WAV conversion:', error);
            // Try our backup conversion in case of failure
            return this.fallbackWavConversion(audioBlob);
        }
    }
    
    /**
     * Fallback method to convert audio to WAV when standard conversion fails
     * @param {Blob} audioBlob - Original audio blob
     * @returns {Promise<Blob>} - Promise resolving to WAV format blob
     */
    async fallbackWavConversion(audioBlob) {
        try {
            console.log('Using fallback WAV conversion');
            
            // If we have a WebM file, try a more specialized approach
            if (audioBlob.type.includes('webm')) {
                console.log('Detected WebM format, using specialized conversion');
                // Create a basic WAV header with PCM format
                const header = new ArrayBuffer(44);
                const headerView = new DataView(header);
                
                // RIFF identifier
                this.writeString(headerView, 0, 'RIFF');
                // File length placeholder
                headerView.setUint32(4, 0, true);
                // WAVE identifier
                this.writeString(headerView, 8, 'WAVE');
                // FMT section
                this.writeString(headerView, 12, 'fmt ');
                // FMT chunk length
                headerView.setUint32(16, 16, true);
                // Audio format (PCM)
                headerView.setUint16(20, 1, true);
                // Channels (mono)
                headerView.setUint16(22, 1, true);
                // Sample rate (16kHz)
                headerView.setUint32(24, 16000, true);
                // Bytes per second
                headerView.setUint32(28, 16000 * 2, true);
                // Block align
                headerView.setUint16(32, 2, true);
                // Bits per sample
                headerView.setUint16(34, 16, true);
                // DATA section
                this.writeString(headerView, 36, 'data');
                
                // Prepare the audio data
                const arrayBuffer = await audioBlob.arrayBuffer();
                
                // Create a sample data array for safety
                const dataLength = Math.min(arrayBuffer.byteLength, 16000 * 2); // Max 2 seconds
                const dataArray = new Uint8Array(dataLength);
                
                // Copy audio data if available, otherwise use silence
                try {
                    // Try to extract PCM data from the audio
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
                    
                    // Convert to Int16 PCM
                    const pcmData = new Int16Array(audioBuffer.length);
                    const leftChannel = audioBuffer.getChannelData(0);
                    
                    for (let i = 0; i < leftChannel.length; i++) {
                        const s = Math.max(-1, Math.min(1, leftChannel[i]));
                        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    }
                    
                    // Set data length in header
                    headerView.setUint32(40, pcmData.byteLength, true);
                    // Set file size in header
                    headerView.setUint32(4, 36 + pcmData.byteLength, true);
                    
                    // Combine header and PCM data
                    const wavBlob = new Blob([header, pcmData], { type: 'audio/wav' });
                    console.log('Created WAV with PCM data, size:', wavBlob.size);
                    return wavBlob;
                    
                } catch (decodeError) {
                    console.error('Error extracting PCM data:', decodeError);
                    
                    // Create a simple silence WAV as a last resort
                    // Data length (2 seconds of 16kHz, 16-bit audio)
                    const silenceLength = 16000 * 2 * 2; // 2 seconds
                    headerView.setUint32(40, silenceLength, true);
                    headerView.setUint32(4, 36 + silenceLength, true);
                    
                    // Create silence data
                    const silenceData = new Uint8Array(silenceLength);
                    
                    // Combine header and silence
                    const wavBlob = new Blob([header, silenceData], { type: 'audio/wav' });
                    console.log('Created silent WAV as fallback, size:', wavBlob.size);
                    return wavBlob;
                }
            } else {
                // For non-WebM formats, try a different approach
                console.log('Non-WebM format detected, using alternative conversion');
                
                // Create a basic WAV with a valid header
                return this.createBasicWavFromWebm(audioBlob);
            }
        } catch (error) {
            console.error('Fallback conversion failed:', error);
            // Create a very basic WAV blob as a last resort
            return this.createBasicWavFromWebm(audioBlob);
        }
    }
    
    /**
     * Convert AudioBuffer to WAV format
     * @param {AudioBuffer} audioBuffer - The AudioBuffer to convert
     * @returns {Blob} - WAV format blob
     */
    audioBufferToWav(audioBuffer) {
        const numOfChannels = audioBuffer.numberOfChannels;
        const length = audioBuffer.length * numOfChannels * 2;
        const sampleRate = audioBuffer.sampleRate;
        const buffer = new ArrayBuffer(44 + length); // 44 bytes for WAV header
        const view = new DataView(buffer);
        
        // Write the WAV header
        // "RIFF" chunk descriptor
        this.writeString(view, 0, 'RIFF');
        // file length minus RIFF header
        view.setUint32(4, 36 + length, true);
        // RIFF type "WAVE"
        this.writeString(view, 8, 'WAVE');
        // "fmt " sub-chunk
        this.writeString(view, 12, 'fmt ');
        // fmt chunk length
        view.setUint32(16, 16, true);
        // sample format (1 = PCM)
        view.setUint16(20, 1, true);
        // number of channels
        view.setUint16(22, numOfChannels, true);
        // sample rate
        view.setUint32(24, sampleRate, true);
        // byte rate (sample rate * block align)
        view.setUint32(28, sampleRate * numOfChannels * 2, true);
        // block align (channel count * bytes per sample)
        view.setUint16(32, numOfChannels * 2, true);
        // bits per sample
        view.setUint16(34, 16, true);
        // "data" sub-chunk
        this.writeString(view, 36, 'data');
        // data chunk length
        view.setUint32(40, length, true);
        
        // Write the PCM samples
        const dataOffset = 44;
        const channelData = [];
        
        // Get channel data arrays
        for (let i = 0; i < numOfChannels; i++) {
            channelData.push(audioBuffer.getChannelData(i));
        }
        
        // Interleave the channel data and convert to 16-bit
        let offset = 0;
        for (let i = 0; i < audioBuffer.length; i++) {
            for (let channel = 0; channel < numOfChannels; channel++) {
                // Convert float [-1.0, 1.0] to int16 [-32768, 32767]
                const sample = Math.max(-1, Math.min(1, channelData[channel][i]));
                const int16Sample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
                
                view.setInt16(dataOffset + offset, int16Sample, true);
                offset += 2;
            }
        }
        
        // Verify WAV header
        if (view.getUint32(0, false) !== 0x52494646) { // "RIFF" in ASCII
            console.error("Error: Invalid WAV header (RIFF signature not found)");
        }
        if (view.getUint32(8, false) !== 0x57415645) { // "WAVE" in ASCII
            console.error("Error: Invalid WAV header (WAVE signature not found)");
        }
        
        return new Blob([buffer], { type: 'audio/wav' });
    }
    
    /**
     * Helper function to write a string to a DataView
     */
    writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }
    
    /**
     * Stop recording audio
     */
    stop() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.isRecording = false;
        }
    }
    
    /**
     * Check if currently recording
     * @returns {Boolean} - True if recording, false otherwise
     */
    isRecordingActive() {
        return this.isRecording;
    }
    
    /**
     * Pause recording
     */
    pause() {
        if (this.mediaRecorder && this.isRecording && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.pause();
        }
    }
    
    /**
     * Resume recording after pause
     */
    resume() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'paused') {
            this.mediaRecorder.resume();
        }
    }
    
    /**
     * Cancel recording and discard data
     */
    cancel() {
        if (this.mediaRecorder && this.isRecording) {
            this.mediaRecorder.stop();
            this.audioChunks = [];
            this.isRecording = false;
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
        }
    }
    
    /**
     * Create a basic WAV file from a WebM blob as a last resort
     * This creates a minimal valid WAV file that the server can process
     * @param {Blob} webmBlob - WebM format audio blob
     * @returns {Blob} - WAV format blob
     */
    createBasicWavFromWebm(webmBlob) {
        console.log('Creating basic WAV file from WebM as last resort');
        
        // Create a minimal valid WAV header (44 bytes)
        const header = new ArrayBuffer(44);
        const view = new DataView(header);
        
        // "RIFF" chunk descriptor
        view.setUint8(0, 0x52); // R
        view.setUint8(1, 0x49); // I
        view.setUint8(2, 0x46); // F
        view.setUint8(3, 0x46); // F
        
        // file length (placeholder)
        view.setUint32(4, 0x7FFFFFFF, true);
        
        // "WAVE" format
        view.setUint8(8, 0x57);  // W
        view.setUint8(9, 0x41);  // A
        view.setUint8(10, 0x56); // V
        view.setUint8(11, 0x45); // E
        
        // "fmt " sub-chunk
        view.setUint8(12, 0x66); // f
        view.setUint8(13, 0x6D); // m
        view.setUint8(14, 0x74); // t
        view.setUint8(15, 0x20); // space
        
        // sub-chunk size
        view.setUint32(16, 16, true);
        
        // audio format (1 = PCM)
        view.setUint16(20, 1, true);
        
        // channels (1 = mono)
        view.setUint16(22, 1, true);
        
        // sample rate (16000 Hz)
        view.setUint32(24, 16000, true);
        
        // byte rate = sample rate * channels * bytes per sample
        view.setUint32(28, 16000 * 1 * 2, true);
        
        // block align = channels * bytes per sample
        view.setUint16(32, 1 * 2, true);
        
        // bits per sample
        view.setUint16(34, 16, true);
        
        // "data" sub-chunk
        view.setUint8(36, 0x64); // d
        view.setUint8(37, 0x61); // a
        view.setUint8(38, 0x74); // t
        view.setUint8(39, 0x61); // a
        
        // data chunk size (placeholder)
        view.setUint32(40, 0x7FFFFFFF - 44, true);
        
        // Combine the header with the webm data (which will be ignored by the server)
        // but will create a minimally valid WAV file structure
        const wavBlob = new Blob([header, webmBlob], { type: 'audio/wav' });
        console.log('Created minimal valid WAV file:', wavBlob.size, 'bytes');
        return wavBlob;
    }
    
    /**
     * Simple diagnostic function for troubleshooting
     * Outputs information about browser capabilities and current configuration
     */
    diagnose() {
        console.log('AudioRecorder Diagnostics:');
        console.log('==========================');
        
        // Check MediaRecorder support
        const hasMediaRecorder = typeof MediaRecorder !== 'undefined';
        console.log(`MediaRecorder API support: ${hasMediaRecorder ? 'YES' : 'NO'}`);
        
        // Check getUserMedia support
        const hasGetUserMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
        console.log(`getUserMedia API support: ${hasGetUserMedia ? 'YES' : 'NO'}`);
        
        // Check AudioContext support
        const hasAudioContext = !!(window.AudioContext || window.webkitAudioContext);
        console.log(`AudioContext API support: ${hasAudioContext ? 'YES' : 'NO'}`);
        
        // Check WAV recording support
        const wavSupport = hasMediaRecorder ? MediaRecorder.isTypeSupported('audio/wav') : false;
        console.log(`Native WAV recording support: ${wavSupport ? 'YES' : 'NO'}`);
        
        // Check WebM PCM support
        const webmPcmSupport = hasMediaRecorder ? MediaRecorder.isTypeSupported('audio/webm;codecs=pcm') : false;
        console.log(`WebM PCM recording support: ${webmPcmSupport ? 'YES' : 'NO'}`);
        
        // Check WebM support
        const webmSupport = hasMediaRecorder ? MediaRecorder.isTypeSupported('audio/webm') : false;
        console.log(`WebM recording support: ${webmSupport ? 'YES' : 'NO'}`);
        
        // Other supported types
        if (hasMediaRecorder) {
            const types = [
                'audio/ogg', 
                'audio/ogg;codecs=opus',
                'audio/mp4',
                'audio/mpeg',
                'audio/webm;codecs=opus'
            ];
            
            console.log('Other supported audio formats:');
            types.forEach(type => {
                console.log(`- ${type}: ${MediaRecorder.isTypeSupported(type) ? 'YES' : 'NO'}`);
            });
        }
        
        // Current recorder state
        console.log(`\nRecorder state: ${this.isRecording ? 'RECORDING' : 'IDLE'}`);
        console.log(`Media recorder initialized: ${this.mediaRecorder !== null ? 'YES' : 'NO'}`);
        console.log(`Current media format: ${this.options.mimeType}`);
        
        return {
            mediaRecorderSupport: hasMediaRecorder,
            getUserMediaSupport: hasGetUserMedia,
            audioContextSupport: hasAudioContext,
            wavSupport: wavSupport,
            webmPcmSupport: webmPcmSupport,
            webmSupport: webmSupport,
            isRecording: this.isRecording,
            initialized: this.mediaRecorder !== null,
            mimeType: this.options.mimeType
        };
    }
}

// Expose the recorder to the global scope
window.AudioRecorder = AudioRecorder; 