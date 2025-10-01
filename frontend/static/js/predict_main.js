/**
 * predict_main.js
 * Entry point for SoundsGood prediction UI
 * Loads all required modules and initializes the application
 */

// Module loading order matters due to dependencies
document.addEventListener('DOMContentLoaded', function() {
    console.log('📋 DEBUG [predict_main.js]: Application initializing...');
    
    // Load modules dynamically in the correct order
    const modules = [
        'predict_api.js',          // API communication (FIRST - needed by others)
        'predict_ui_core.js',      // Core UI functionality
        'predict_playback.js',     // Audio playback & visualization 
        'predict_feedback.js',     // Feedback and confusion matrix
        'predict_audio_core.js',   // Audio core functionality
        'predict_audio_processing.js', // Audio processing and WAV encoding
        'predict_speech_detection.js', // Speech detection
        'predict_events.js'        // Event listeners and UI interactions (LAST - depends on everything else)
    ];
    
    // Load each module and track when they're all loaded
    let loadedModules = 0;
    
    modules.forEach(modulePath => {
        const script = document.createElement('script');
        script.src = `/static/js/${modulePath}`;
        script.async = false; // Maintain load order
        
        script.onload = function() {
            console.log(`📋 DEBUG [predict_main.js]: Module loaded: ${modulePath}`);
            loadedModules++;
            
            // When all modules are loaded, run initialization code
            if (loadedModules === modules.length) {
                console.log('📋 DEBUG [predict_main.js]: All modules loaded, initializing app...');
                initializeApplication();
            }
        };
        
        script.onerror = function() {
            console.error(`Failed to load module: ${modulePath}`);
            alert(`Error loading module: ${modulePath}. Please reload the page.`);
        };
        
        document.head.appendChild(script);
    });
});

/**
 * Initialize the application once all modules are loaded
 */
function initializeApplication() {
    // Set up any global event listeners
    console.log('📋 DEBUG [predict_main.js]: Running application initialization...');
    
    // --- ADDED: Call setupEventListeners --- 
    if (typeof window.setupEventListeners === 'function') {
        console.log('📋 DEBUG [predict_main.js]: Calling window.setupEventListeners()...');
        window.setupEventListeners();
    } else {
        console.error('CRITICAL: setupEventListeners function not found after loading predict_events.js!');
    }
    // --- END ADDED ---
    
    // Apply UI styles
    if (typeof window.applyMuiStyles === 'function') {
        window.applyMuiStyles();
    }
    
    // Initialize audio processing ahead of time
    setTimeout(function() {
        console.log('📋 DEBUG [predict_main.js]: Pre-initializing audio processing...');
        // Initializing audio ahead of time helps prevent delays later
        if (typeof window.initAudioProcessing === 'function') {
            window.initAudioProcessing().then(result => {
                console.log('📋 DEBUG [predict_main.js]: Audio pre-initialization result:', result);
            }).catch(error => {
                console.error('📋 DEBUG [predict_main.js]: Audio pre-initialization error:', error);
            });
        }
    }, 2000);
    
    // --- REMOVED: Direct .onclick handler (conflicted with addEventListener in predict_events.js) ---
    // const predictButton = document.getElementById('predictButton');
    // if (predictButton) {
    //     predictButton.onclick = function() { ... };
    // }
    // --- END REMOVED ---
    
    // Log successful initialization
    console.log('📋 DEBUG [predict_main.js]: Application initialized successfully');
} 