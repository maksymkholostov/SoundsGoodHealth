/**
 * game2.js - UI Logic for Sound Classification Game (Originally Game 3)
 * Relies on predict_*.js scripts for core audio/API handling.
 */

// Access game namespace
const Game = window.SoundsGoodGame;

// --- Game-specific Speech Detection Settings ---
// Define game thresholds here
Game.GAME_ENERGY_THRESHOLD = 0.02;
Game.GAME_NOISE_THRESHOLD_FACTOR = 2.0; // Keep lowered value for now

// Store original default thresholds from predict_audio_core.js
const originalEnergyThreshold = window.ENERGY_THRESHOLD;
const originalNoiseThresholdFactor = window.NOISE_THRESHOLD_FACTOR;

// Function to apply game-specific thresholds when needed
function applyGameSpeechThresholds(enable) {
    if (enable) {
        console.log(`Game2: Applying game-specific speech thresholds (Energy: ${Game.GAME_ENERGY_THRESHOLD}, Factor: ${Game.GAME_NOISE_THRESHOLD_FACTOR})`);
        // Override the global thresholds used by predict_speech_detection.js
        window.ENERGY_THRESHOLD = Game.GAME_ENERGY_THRESHOLD;
        window.NOISE_THRESHOLD_FACTOR = Game.GAME_NOISE_THRESHOLD_FACTOR;
    } else {
        console.log(`Game2: Restoring original speech thresholds (Energy: ${originalEnergyThreshold}, Factor: ${originalNoiseThresholdFactor})`);
        // Restore the original defaults
        window.ENERGY_THRESHOLD = originalEnergyThreshold;
        window.NOISE_THRESHOLD_FACTOR = originalNoiseThresholdFactor;
    }
}

// --- DOM Elements --- 
// ... (rest of the file - content is the same as game3.js) ... 