/**
 * play.js - Sound-reactive face animation logic
 * Part of SoundsGood SoundClassifiers
 */

document.addEventListener('DOMContentLoaded', function() {
    let audioContext;
    let analyser;
    let microphone;
    let javascriptNode;
    let listening = false;
    let sensitivity = 80; // Higher default sensitivity (was 50)
    
    const faceContainer = document.getElementById('faceContainer');
    const neutralFace = document.getElementById('neutralFace');
    const happyFace = document.getElementById('happyFace');
    const soundLevelIndicator = document.getElementById('soundLevelIndicator');
    const startAudioBtn = document.getElementById('startAudioBtn');
    const sensitivitySlider = document.getElementById('sensitivitySlider');
    
    // Update sensitivity when slider changes
    sensitivitySlider.addEventListener('input', function() {
        sensitivity = parseInt(this.value);
    });
    
    // Start audio processing
    startAudioBtn.addEventListener('click', function() {
        if (!listening) {
            initAudio();
            startAudioBtn.innerHTML = '<span class="material-icons">mic_off</span> Stop Listening';
            listening = true;
        } else {
            stopAudio();
            startAudioBtn.innerHTML = '<span class="material-icons">mic</span> Start Listening';
            listening = false;
            resetFace();
        }
    });
    
    function initAudio() {
        try {
            // Create audio context
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Create analyser node
            analyser = audioContext.createAnalyser();
            analyser.minDecibels = -90;
            analyser.maxDecibels = -10;
            analyser.smoothingTimeConstant = 0.85;
            analyser.fftSize = 256;
            
            // Setup audio processing callback
            javascriptNode = audioContext.createScriptProcessor(2048, 1, 1);
            javascriptNode.connect(audioContext.destination);
            
            // Get microphone input
            navigator.mediaDevices.getUserMedia({ audio: true, video: false })
                .then(function(stream) {
                    microphone = audioContext.createMediaStreamSource(stream);
                    microphone.connect(analyser);
                    analyser.connect(javascriptNode);
                    
                    // Process audio data
                    javascriptNode.onaudioprocess = processAudio;
                })
                .catch(function(err) {
                    console.error('Error accessing microphone:', err);
                    alert('Error accessing microphone. Please make sure your browser has permission to use the microphone.');
                    listening = false;
                    startAudioBtn.innerHTML = '<span class="material-icons">mic</span> Start Listening';
                });
        } catch (e) {
            console.error('Audio context error:', e);
            alert('Your browser does not support the Web Audio API. Please try a different browser.');
        }
    }
    
    function stopAudio() {
        if (javascriptNode) {
            javascriptNode.onaudioprocess = null;
            javascriptNode.disconnect();
        }
        
        if (analyser) {
            analyser.disconnect();
        }
        
        if (microphone) {
            microphone.disconnect();
        }
        
        if (audioContext) {
            audioContext.close();
        }
    }
    
    function processAudio(e) {
        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);
        analyser.getByteFrequencyData(dataArray);
        
        // Calculate average volume
        let sum = 0;
        for(let i = 0; i < bufferLength; i++) {
            sum += dataArray[i];
        }
        
        const average = sum / bufferLength;
        const normalizedSensitivity = sensitivity / 100 * 50; // Adjust sensitivity range
        const threshold = 5 + 30 - normalizedSensitivity; // Lower the base threshold (was 15 + 50)
        
        // Update sound level indicator
        const soundLevel = Math.min(100, (average / 128) * 100);
        soundLevelIndicator.style.width = soundLevel + '%';
        
        // React face to sound level
        if (average > threshold) {
            showHappyFace(soundLevel);
        } else {
            resetFace();
        }
    }
    
    function showHappyFace(intensity) {
        // Map intensity to opacity (max 1)
        const opacity = Math.min(1, intensity / 50);
        happyFace.style.opacity = opacity;
        neutralFace.style.opacity = 1 - opacity;
        
        // Scale face based on intensity
        const scale = 1 + (intensity / 200);
        faceContainer.style.transform = `scale(${scale})`;
    }
    
    function resetFace() {
        happyFace.style.opacity = 0;
        neutralFace.style.opacity = 1;
        faceContainer.style.transform = 'scale(1)';
        soundLevelIndicator.style.width = '0%';
    }
}); 