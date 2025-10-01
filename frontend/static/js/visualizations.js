/**
 * SoundClassifiers v10 - Visualization Components
 * 
 * This module provides visualization capabilities for audio data, training metrics,
 * and performance analysis. It uses a non-invasive approach to inject visualizations
 * into existing UI elements.
 */

// Main visualization namespace
const SCVisualizations = {
    // Configuration
    config: {
        colors: {
            primary: '#4285F4',
            secondary: '#34A853',
            accent: '#FBBC05',
            error: '#EA4335',
            waveform: '#4285F4',
            spectrogram: ['#000080', '#0000FF', '#00FFFF', '#FFFF00', '#FF0000']
        },
        animation: {
            duration: 300,
            easing: 'ease-in-out'
        },
        responsive: {
            breakpoints: {
                mobile: 576,
                tablet: 768,
                desktop: 992
            }
        }
    },

    // Initialization function
    init: function() {
        console.log('Initializing SoundClassifiers Visualization System');
        // Check for visualization containers and initialize as needed
        this.initializeWaveformVisualizers();
        this.initializeSpectrogramVisualizers();
        this.initializeTrainingVisualizers();
        this.initializeConfusionMatrixVisualizers();
        this.initializeProgressVisualizers();
    },

    // Creates a container for visualizations if it doesn't exist
    createVisualizationContainer: function(parentSelector, containerId, title = null) {
        const parent = document.querySelector(parentSelector);
        if (!parent) return null;
        
        let container = document.getElementById(containerId);
        if (!container) {
            container = document.createElement('div');
            container.id = containerId;
            container.className = 'sc-visualization-container';
            
            if (title) {
                const titleElement = document.createElement('h4');
                titleElement.className = 'sc-visualization-title';
                titleElement.textContent = title;
                container.appendChild(titleElement);
            }
            
            const visualizationElement = document.createElement('div');
            visualizationElement.className = 'sc-visualization';
            container.appendChild(visualizationElement);
            
            parent.appendChild(container);
        }
        
        return container.querySelector('.sc-visualization');
    },

    // Waveform visualization
    initializeWaveformVisualizers: function() {
        // Find all elements marked for waveform visualization
        const containers = document.querySelectorAll('[data-visualization="waveform"]');
        containers.forEach(container => {
            const audioId = container.dataset.audioId;
            if (audioId) {
                this.createWaveformVisualization(container, audioId);
            }
        });

        // Also check for recording page to add live waveform
        if (document.getElementById('recording-page')) {
            this.initializeLiveWaveform();
        }
    },

    createWaveformVisualization: function(container, audioId) {
        // Fetch audio data from API
        fetch(`/api/recordings/${audioId}/waveform`)
            .then(response => response.json())
            .then(data => {
                // Simple implementation - will be expanded
                const canvas = document.createElement('canvas');
                canvas.width = container.clientWidth;
                canvas.height = 150;
                container.appendChild(canvas);
                
                const ctx = canvas.getContext('2d');
                this.drawWaveform(ctx, data.samples, canvas.width, canvas.height);
            })
            .catch(error => {
                console.error('Error loading waveform data:', error);
                container.innerHTML = '<div class="error-message">Failed to load waveform</div>';
            });
    },
    
    drawWaveform: function(ctx, samples, width, height) {
        // Basic waveform drawing function - will be enhanced
        ctx.clearRect(0, 0, width, height);
        ctx.beginPath();
        ctx.strokeStyle = this.config.colors.waveform;
        ctx.lineWidth = 2;
        
        const step = Math.ceil(samples.length / width);
        const amp = height / 2;
        
        for (let i = 0; i < width; i++) {
            const min = Math.min(...samples.slice(i * step, (i + 1) * step));
            const max = Math.max(...samples.slice(i * step, (i + 1) * step));
            
            ctx.moveTo(i, (1 + min) * amp);
            ctx.lineTo(i, (1 + max) * amp);
        }
        
        ctx.stroke();
    },

    initializeLiveWaveform: function() {
        const liveWaveformContainers = document.querySelectorAll('[data-visualization="waveform"][data-live="true"]');
        
        liveWaveformContainers.forEach(container => {
            // Create canvas for waveform
            const canvas = document.createElement('canvas');
            canvas.className = 'sc-waveform-canvas';
            canvas.width = container.clientWidth;
            canvas.height = 150;
            container.appendChild(canvas);
            
            // Store reference to canvas
            container.dataset.canvasInitialized = 'true';
            
            // Setup will be completed when recording starts
            console.log('Live waveform container initialized:', container.id);
        });
    },

    // New method to handle real-time audio data
    updateLiveWaveform: function(containerId, audioData) {
        const container = document.getElementById(containerId);
        if (!container || container.dataset.canvasInitialized !== 'true') return;
        
        const canvas = container.querySelector('canvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw waveform
        ctx.beginPath();
        ctx.strokeStyle = this.config.colors.waveform;
        ctx.lineWidth = 2;
        
        const sliceWidth = canvas.width / audioData.length;
        let x = 0;
        
        for (let i = 0; i < audioData.length; i++) {
            const y = (0.5 + audioData[i] / 2) * canvas.height;
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
            
            x += sliceWidth;
        }
        
        ctx.stroke();
    },

    // Spectrogram visualization - placeholder
    initializeSpectrogramVisualizers: function() {
        // Will implement spectrogram visualization
        console.log('Spectrogram visualizers initialized');
    },

    // Training curves visualization - placeholder
    initializeTrainingVisualizers: function() {
        // Will implement training metrics visualization
        console.log('Training visualizers initialized');
    },

    // Confusion matrix visualization - placeholder
    initializeConfusionMatrixVisualizers: function() {
        // Will implement confusion matrix visualization
        console.log('Confusion matrix visualizers initialized');
    },

    // Progress tracking visualization - placeholder
    initializeProgressVisualizers: function() {
        // Will implement progress tracking visualization
        console.log('Progress visualizers initialized');
    }
};

// Initialize visualizations when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    SCVisualizations.init();
});

/**
 * Visualization components for SoundClassifiers v10
 *
 * This script adds visualization support to the existing pages by
 * injecting visualization elements at appropriate points.
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize visualization elements based on current page
    const currentPage = window.location.pathname;
    
    if (currentPage.includes('/recordings')) {
        initRecordingVisualizations();
    } else if (currentPage.includes('/training')) {
        initTrainingVisualizations();
    } else if (currentPage.includes('/inference')) {
        initInferenceVisualizations();
    } else if (currentPage.includes('/analysis')) {
        initAnalysisDashboard();
    }
});

/**
 * Initialize visualizations for the recordings page
 */
function initRecordingVisualizations() {
    // Find the container where recordings are displayed
    const container = document.querySelector('#recording-container') || 
                     document.querySelector('.recording-section');
    
    if (!container) return;
    
    // Create visualization container
    const vizContainer = document.createElement('div');
    vizContainer.className = 'visualization-container';
    
    // Add it to the page
    container.appendChild(vizContainer);
    
    // Set up event listeners to detect when a recording is completed
    // This depends on how the frontend triggers recording completion
    document.addEventListener('recordingComplete', function(event) {
        const recordingId = event.detail.recordingId;
        const dictionaryId = event.detail.dictionaryId;
        
        // Fetch analysis data
        fetch(`/api/analysis/recording/${dictionaryId}/${recordingId}`)
            .then(response => response.json())
            .then(data => {
                // Clear previous visualizations
                vizContainer.innerHTML = '';
                
                // Add waveform
                if (data.waveform_image) {
                    addVisualization(vizContainer, 'Waveform', data.waveform_image);
                }
                
                // Add spectrogram
                if (data.spectrogram_image) {
                    addVisualization(vizContainer, 'Spectrogram', data.spectrogram_image);
                }
                
                // Add quality metrics
                addQualityMetrics(vizContainer, data);
            })
            .catch(error => console.error('Error fetching analysis:', error));
    });
    
    // Also check for existing recordings that might need visualization
    // This depends on how recordings are stored/displayed in the frontend
}

/**
 * Initialize visualizations for the training page
 */
function initTrainingVisualizations() {
    // Find the container where training results are displayed
    const container = document.querySelector('#training-results') || 
                     document.querySelector('.training-section');
    
    if (!container) return;
    
    // Create visualization container
    const vizContainer = document.createElement('div');
    vizContainer.className = 'visualization-container';
    
    // Add it to the page
    container.appendChild(vizContainer);
    
    // Set up event listeners for when training is completed
    document.addEventListener('trainingComplete', function(event) {
        const modelId = event.detail.modelId;
        const dictionaryId = event.detail.dictionaryId;
        
        // Fetch training history
        fetch(`/api/analysis/training/${dictionaryId}/${modelId}/history`)
            .then(response => response.json())
            .then(data => {
                // Clear previous visualizations
                vizContainer.innerHTML = '';
                
                // Add training curves
                if (data.training_curve_image) {
                    addVisualization(vizContainer, 'Training Curves', data.training_curve_image);
                }
                
                // Add confusion matrix if available
                if (data.confusion_matrix_image) {
                    addVisualization(vizContainer, 'Confusion Matrix', data.confusion_matrix_image);
                }
            })
            .catch(error => console.error('Error fetching training analysis:', error));
    });
}

// Helper functions for visualization

/**
 * Add a visualization to a container
 */
function addVisualization(container, title, base64Image) {
    const div = document.createElement('div');
    div.className = 'visualization-item';
    
    const titleElem = document.createElement('h3');
    titleElem.textContent = title;
    
    const img = document.createElement('img');
    img.src = `data:image/png;base64,${base64Image}`;
    img.alt = title;
    
    div.appendChild(titleElem);
    div.appendChild(img);
    container.appendChild(div);
}

/**
 * Add quality metrics display
 */
function addQualityMetrics(container, data) {
    const div = document.createElement('div');
    div.className = 'quality-metrics';
    
    const title = document.createElement('h3');
    title.textContent = 'Audio Quality Metrics';
    div.appendChild(title);
    
    const metrics = [
        { name: 'Quality Score', value: data.quality_score, unit: '/100' },
        { name: 'Signal-to-Noise Ratio', value: data.signal_to_noise_ratio_db, unit: 'dB' },
        { name: 'Duration', value: data.duration_seconds, unit: 's' }
    ];
    
    const table = document.createElement('table');
    table.className = 'metrics-table';
    
    // Add table header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    ['Metric', 'Value'].forEach(text => {
        const th = document.createElement('th');
        th.textContent = text;
        headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // Add table body
    const tbody = document.createElement('tbody');
    metrics.forEach(metric => {
        const row = document.createElement('tr');
        
        const nameTd = document.createElement('td');
        nameTd.textContent = metric.name;
        
        const valueTd = document.createElement('td');
        valueTd.textContent = `${metric.value.toFixed(2)} ${metric.unit}`;
        
        row.appendChild(nameTd);
        row.appendChild(valueTd);
        tbody.appendChild(row);
    });
    table.appendChild(tbody);
    
    div.appendChild(table);
    container.appendChild(div);
}

// Add additional visualization functions as needed for inference and analysis
