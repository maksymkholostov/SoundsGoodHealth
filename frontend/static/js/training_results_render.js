// --- UI Rendering for Training Results, Summaries, and Details ---

function displayModelResults(results) {
    // Assumes clearLoadingSpinners is available (defined in training_init_ui.js)
    clearLoadingSpinners(); // Clear any placeholder spinners

    const resultsContainer = document.getElementById('modelResultsContainer');
    const resultsEl = document.getElementById('modelResults');
    if (!resultsContainer || !resultsEl) return;

    resultsContainer.style.display = 'block'; // Show the container
    resultsEl.innerHTML = ''; // Clear previous content

    // --- Calculate Display Values ---
    let displayAccuracy = null; // Initialize as null
    // Use 'accuracy' key from backend metrics, ensure it's a number
    if (typeof results.accuracy === 'number') { 
        displayAccuracy = results.accuracy;
    } 

    // Prepare the string for display
    const accuracyString = displayAccuracy !== null 
        ? `${(displayAccuracy * 100).toFixed(1)}%` 
        : '<span class="text-danger small">N/A</span>'; // Display N/A or Error if null

    // Get sample counts from metrics
    const trainSamples = results.num_train_samples !== undefined ? results.num_train_samples : 'N/A';
    const valSamples = results.num_val_samples !== undefined ? results.num_val_samples : 'N/A';

    // const displayTrainingTime = (results.training_time > 0) ? results.training_time.toFixed(1) : 'N/A'; // REMOVED - Time not in metrics

    // --- Generate HTML ---
    let html = '<div class="row">'; // Use Bootstrap row

    // Accuracy Card (Takes up half width now)
    html += `
        <div class="col-lg-6 mb-3">
            <div class="mui-card h-100">
                <div class="mui-card-header mui-card-header-primary"><span class="material-icons me-1">emoji_events</span>Accuracy</div>
                <div class="mui-card-content text-center">
                    <h1 class="display-4">${accuracyString}</h1> {# Use the prepared string #}
                    <p class="text-muted mb-0 small">Final Validation Accuracy</p>
                </div>
            </div>
        </div>`;

    // Train Samples Card (Takes up quarter width)
    html += `
        <div class="col-lg-3 col-md-6 mb-3">
            <div class="mui-card h-100">
                <div class="mui-card-header mui-card-header-secondary"><span class="material-icons me-1">data_usage</span>Train Samples</div>
                <div class="mui-card-content text-center">
                    <h1 class="display-5">${trainSamples}</h1>
                    <p class="text-muted mb-0 small">Used for Training</p>
                </div>
            </div>
        </div>`;

    // Validation Samples Card (Takes up quarter width)
    html += `
        <div class="col-lg-3 col-md-6 mb-3">
            <div class="mui-card h-100">
                <div class="mui-card-header mui-card-header-secondary"><span class="material-icons me-1">science</span>Validation Samples</div>
                <div class="mui-card-content text-center">
                    <h1 class="display-5">${valSamples}</h1>
                    <p class="text-muted mb-0 small">Used for Validation</p>
                </div>
            </div>
        </div>`;

    // Training Time Card - COMMENTED OUT
    /*
    html += `
        <div class="col-md-6 mb-3">
            <div class="mui-card h-100">
                <div class="mui-card-header mui-card-header-primary"><span class="material-icons me-1">timer</span>Time</div>
                <div class="mui-card-content text-center">
                    <h1 class="display-4">${displayTrainingTime}s</h1>
                    <p class="text-muted mb-0 small">Total Training Duration</p>
                </div>
            </div>
        </div>`;
    */

    // Class Accuracy Card (if available) - COMMENTED OUT
    /*
    if (results.class_accuracy && Object.keys(results.class_accuracy).length > 0) {
        html += `
            <div class="col-12 mb-3">
                <div class="mui-card">
                    <div class="mui-card-header mui-card-header-secondary"><span class="material-icons me-1">bar_chart</span>Class Accuracy</div>
                    <div class="mui-card-content">
                        <div class="row">`;

        const sortedClasses = Object.entries(results.class_accuracy).sort((a, b) => a[0].localeCompare(b[0]));
        for (const [className, accuracy] of sortedClasses) {
            const classAccValue = accuracy > 0 ? accuracy : 0.01; // Min 1% for visibility
            const classAccPercent = (classAccValue * 100);
            let barColor = 'bg-success';
            if (classAccPercent < 70) barColor = 'bg-warning';
            if (classAccPercent < 40) barColor = 'bg-danger';

            html += `
                <div class="col-md-6 col-lg-4 mb-3"> {# Adjust columns for responsiveness #}
                    <div class="d-flex justify-content-between align-items-center mb-1 small">
                        <span class="fw-bold text-truncate" title="${className}">${className}</span>
                        <span>${classAccPercent.toFixed(1)}%</span>
                    </div>
                    <div class="progress" style="height: 8px;"> {# Thinner progress bar #}
                        <div class="progress-bar ${barColor}" role="progressbar" style="width: ${classAccPercent}%"
                             aria-valuenow="${classAccPercent}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                </div>`;
        }
        html += `</div></div></div></div>`; // Close row, card-content, card, col
    }
    */

    html += '</div>'; // Close main row
    resultsEl.innerHTML = html;
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
          // Also reset summary counts above the table
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

     // Add/Update footer total row
     let tfoot = classTableBody.tFoot;
     if(!tfoot) tfoot = classTableBody.createTFoot();
     tfoot.innerHTML = ''; // Clear previous footer if any
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
     document.getElementById('totalCount').textContent = totalTraining; // Total used for training
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
    // Updates the text display showing the *structure* of the feature vector
    const featureVectorElement = document.getElementById('complete-feature-vector');
    const featureCountElement = document.getElementById('feature-vector-count');
    if (!featureVectorElement || !featureCountElement) return;

    // Example structure - this should ideally align with backend logic, but serves as an example
    // It does not display actual values, just the names/types of features used.
    const featureVectorParts = [
        'mfcc_mean_1...14', 'mfcc_std_1...14', // Assuming 14 MFCCs
        'mfcc_delta_mean_2...14', 'mfcc_delta_std_2...14', // Assuming delta excludes 1st coeff
        'mfcc_delta2_mean_2...14', 'mfcc_delta2_std_2...14', // Assuming delta-delta excludes 1st
        'pitch_mean', 'pitch_std', 'pitch_min', 'pitch_max',
        'rms_mean', 'rms_std',
        'zcr_mean', 'zcr_std',
        'spectral_centroid_mean', 'spectral_centroid_std',
        'spectral_rolloff_mean', 'spectral_rolloff_std',
        // Add other features if used, e.g., formants:
        // 'formant1_mean', 'formant2_mean', 'formant3_mean',
        // 'formant1_std', 'formant2_std', 'formant3_std'
    ];
     // Placeholder count. Backend *could* provide this in stats if needed for accuracy.
     // Calculation: 14*2 (mfcc) + 13*2 (delta) + 13*2 (delta2) + 4 (pitch) + 2 (rms) + 2 (zcr) + 2 (centroid) + 2 (rolloff) = 28+26+26+4+2+2+2+2 = 92 (adjust if features differ)
     const estimatedFeatureCount = 92;

    featureVectorElement.textContent = featureVectorParts.join(', ');
    featureCountElement.textContent = estimatedFeatureCount; // Update count display
}


function updateMfccStats(stats) {
    const mfccDetailsContainer = document.getElementById('mfccNormalizationDetails');
    if (!mfccDetailsContainer) return;
    if (!stats?.mfcc_stats) {
        // If stats are missing, ensure the section is hidden or shows a message
        // mfccDetailsContainer.style.display = 'none'; // Option: hide it completely
        // Option: Or ensure content indicates missing data if already visible
        const tableBody = document.getElementById('mfccStatsTableBody');
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="3" class="text-muted text-center small">MFCC Stats not available.</td></tr>';
         const coeffChartContainer = document.getElementById('mfccCoefficientsChart');
         if(coeffChartContainer) coeffChartContainer.innerHTML = '<p class="text-muted small p-3">Coefficient chart data unavailable.</p>';
         const deltaChartContainer = document.getElementById('mfccDeltasChart');
          if(deltaChartContainer) deltaChartContainer.innerHTML = '<p class="text-muted small p-3">Delta chart data unavailable.</p>';

        return;
    }

    mfccDetailsContainer.style.display = 'block'; // Ensure visible if we have stats

    const tableBody = document.getElementById('mfccStatsTableBody');
    const coeffChartContainer = document.getElementById('mfccCoefficientsChart');
    const deltaChartContainer = document.getElementById('mfccDeltasChart');
    if (!tableBody) return; // Need table body at minimum

    tableBody.innerHTML = ''; // Clear previous stats
    const formatStat = (val) => (val !== null && val !== undefined) ? val.toFixed(4) : '-';
    const addRow = (name, before, after) => {
        tableBody.insertRow().innerHTML = `<td><strong>${name}</strong></td><td>${formatStat(before)}</td><td>${formatStat(after)}</td>`;
    };

    // Safely access nested stats properties
    const beforeNorm = stats.mfcc_stats.before_normalization || {};
    const afterNorm = stats.mfcc_stats.after_normalization || {};
    const coeffs = stats.mfcc_stats.coefficients || []; // Raw coefficients before norm
    const deltasBefore = stats.mfcc_stats.delta_stats?.before_normalization;
    const deltasAfter = stats.mfcc_stats.delta_stats?.after_normalization;
    const delta2Before = stats.mfcc_stats.delta2_stats?.before_normalization;
    const delta2After = stats.mfcc_stats.delta2_stats?.after_normalization;


    // Add overall MFCC stats (calculated by backend, potentially excluding coeff 0)
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


    // --- Update Charts ---
    // Chart raw coefficients (usually before normalization)
    if (coeffs.length > 0 && coeffChartContainer) {
        updateMfccChart(coeffChartContainer, 'mfccCoeffChart', coeffs, 'MFCC Coeffs (Raw)', true);
    } else if (coeffChartContainer) {
        coeffChartContainer.innerHTML = '<p class="text-muted small p-3">Coefficient chart data unavailable.</p>';
    }

     // Chart raw delta values if backend provides them (e.g., stats.mfcc_stats.deltas_raw_values)
     // This requires the backend to compute and send these individual values.
     const deltasRaw = stats.mfcc_stats.deltas_raw_values || []; // Check if this field exists in stats
     if (deltasRaw.length > 0 && deltaChartContainer) {
         updateMfccChart(deltaChartContainer, 'mfccDeltaChart', deltasRaw, 'Delta Features (Raw)', false); // No highlight for first delta
     } else if (deltaChartContainer) {
          deltaChartContainer.innerHTML = '<p class="text-muted small p-3">Delta chart data unavailable.</p>';
     }
      // Similarly for delta-delta chart if data is available
}


function updateMfccChart(container, chartVar, data, title, highlightFirst) {
    if (!container || !data || data.length === 0 || typeof Chart === 'undefined') {
        if (container) container.innerHTML = `<p class="text-muted small p-3">Chart data unavailable.</p>`;
        return;
    }

    // Destroy previous chart instance if exists
    if (window[chartVar] && typeof window[chartVar].destroy === 'function') {
        window[chartVar].destroy();
    }

    const labels = data.map((_, i) => `${title.split(' ')[0]} ${i + 1}`); // e.g., "MFCC 1", "Delta 1"
    const bgColors = data.map((_, i) => (highlightFirst && i === 0) ? 'rgba(255, 193, 7, 0.7)' : 'rgba(63, 81, 181, 0.7)');
    const borderColors = data.map((_, i) => (highlightFirst && i === 0) ? 'rgba(255, 193, 7, 1)' : 'rgba(63, 81, 181, 1)');

    container.innerHTML = ''; // Clear container before adding canvas
    const canvas = document.createElement('canvas');
    container.appendChild(canvas);
    const ctx = canvas.getContext('2d');


    window[chartVar] = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: title, // Use specific title for dataset label
                data: data,
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // Important for fixed height container
            scales: {
                y: {
                    beginAtZero: false, // Allow negative values if present
                    ticks: { font: { size: 10 } }
                },
                x: {
                    ticks: { font: { size: 10 } }
                }
            },
            plugins: {
                title: { display: true, text: title, font: { size: 14 } },
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (ctx) => {
                            // Tooltip title: e.g., "MFCC 1 (Energy)" or "Delta 5"
                            const index = ctx[0].dataIndex;
                            let suffix = '';
                            if (highlightFirst && index === 0 && title.includes('MFCC')) {
                                suffix = ' (Energy)';
                            }
                            return `${labels[index]}${suffix}`;
                        },
                        label: (ctx) => `Value: ${ctx.raw.toFixed(4)}`, // Display value
                        afterLabel: (ctx) => {
                             // Optional note for the first MFCC coefficient
                             if (highlightFirst && ctx.dataIndex === 0 && title.includes('MFCC')) {
                                 return 'Note: Handled separately';
                             }
                             return null;
                        }
                    }
                }
            }
        }
    });
}
