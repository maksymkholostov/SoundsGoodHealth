# Predict Page – Minimal, Fast, and Stable Implementation (No Predict Button Relocation)

Author’s intent: Restore the original UX (Predict button stays where it always was), add the Game modes cleanly, and align the left column cards with the right card using CSS only. No auto-start, no relocators, no height-sync JS.

## Non‑Negotiable “Don’ts”
- Do not move, clone, or reparent the existing Predict button. Leave it exactly where it is (below the cards).
- Do not auto‑start continuous mode on load or on mode switch.
- Do not alter Dictionary/Model cards beyond the CSS layout rules here.
- Do not include heavy third‑party scripts at page load; lazy‑load Phaser only for Game 2.

---

## 1) CSS: Equalize Heights (Left 1+2 equals Right 3) – CSS only

Assumptions:
- You can add stable IDs to the three cards’ outer wrappers:
  - Step 1 (left): `#leftStep1`
  - Step 2 (left): `#leftStep2`
  - Step 3 (right): `#rightStep3`
- Wrap both left cards in a “virtual” wrapper `#leftColumn` (we’ll use `display: contents` so the HTML structure doesn’t have to change deeply).

Add (or append) to your predict page stylesheet:

```css
/* Two-column, two-row grid. Right card spans both rows. */
.mui-steps-grid {
  display: grid;
  grid-template-columns: 420px 1fr;     /* left fixed, right fluid */
  grid-template-rows: auto auto;
  gap: 16px;
  align-items: stretch;                 /* columns stretch vertically */
}

/* Left “wrapper” participates without extra box */
#leftColumn { display: contents; }

/* Position the three cards into the grid */
#leftStep1   { grid-column: 1; grid-row: 1; }
#leftStep2   { grid-column: 1; grid-row: 2; }
#rightStep3  { grid-column: 2; grid-row: 1 / span 2; }

/* Ensure cards can stretch naturally without forced minimums */
.mui-model-card,
.mui-card-content {
  height: 100%;
  min-height: 0;
}

/* Optional: remove any decorative ::after overlays that might catch clicks */
.mui-card-content::after { pointer-events: none; }
```

HTML structural notes (only if you can add shallow wrappers/IDs, no relocation):

```html
<div class="mui-steps-grid">
  <div id="leftColumn">
    <div id="leftStep1" class="mui-model-card"> ... Step 1 (Dictionary) ... </div>
    <div id="leftStep2" class="mui-model-card"> ... Step 2 (Real-time Predictor) ... </div>
  </div>

  <div id="rightStep3" class="mui-model-card"> ... Step 3 (Model Select) ... </div>
</div>
```

No JS is needed for equal height. The grid ensures the right card equals the combined height of the two left cards.

---

## 2) Game Mode – Add as a separate, independent card (Predict button stays put)

### 2.1 HTML (new “Game Mode” card below the main section)
```html
<div id="gameModeCard" class="mui-model-card">
  <div class="mui-card-header">
    <h2><span class="material-icons">videogame_asset</span> Game Mode</h2>
  </div>

  <div class="mui-card-content">
    <!-- Game variant radios -->
    <div id="gameVariantSelector" style="margin: 0 0 1rem 0;">
      <label><input type="radio" name="gameVariant" value="game1" checked> Game 1</label>
      <label style="margin-left: 1rem;"><input type="radio" name="gameVariant" value="game2"> Game 2</label>
      <label style="margin-left: 1rem;"><input type="radio" name="gameVariant" value="puzzle"> Puzzle</label>
      <span id="gameVariantStatus" style="margin-left: 1rem;">Active: Game 1</span>
    </div>

    <!-- Target & feedback row -->
    <div style="display: flex; align-items: center; gap: 2rem; min-height: 160px;">
      <div style="flex: 1;">
        <div id="classToSay" style="font-size: 2rem; font-weight: 600; color: var(--primary-color);">
          Say: …
        </div>
      </div>

      <div style="flex: 1; text-align: right;">
        <div style="font-size: 1.25rem; font-weight: 700; color: var(--primary-color);">Latest Prediction:</div>
        <!-- Centered thumbs here -->
        <div id="gameFeedbackIcon"
             style="display: flex; justify-content: center; align-items: center; height: 160px; font-size: 128px;">
          <!-- material icon thumbs up/down inserted by JS -->
        </div>
      </div>
    </div>

    <!-- Game action bar -->
    <div id="gameActionBar" style="display: flex; align-items: center; gap: .75rem; margin-top: .5rem;">
      <button id="gameStartBtn" type="button" class="mui-button">
        <span class="material-icons">mic</span> Start
      </button>
      <span id="gameCountdownLabel" style="display:none; font-weight: 600;">30s</span>
      <span id="gameScoreLabel" style="display:none; font-weight: 600;">Score: 0</span>
    </div>

    <!-- Game 2 (Tower) canvas container, lazy loaded -->
    <div id="towerGameContainer" style="display:none;"></div>

    <!-- Puzzle container -->
    <div id="puzzleGameContainer" style="display:none;"></div>
  </div>
</div>
```

### 2.2 CSS for centered thumbs
```css
#gameFeedbackIcon {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 160px;
  font-size: 128px;  /* thumbs size */
}
#gameFeedbackIcon .material-icons {
  font-size: inherit;
}
```

### 2.3 JS Wiring (minimal, no Predict button changes)

Attach the following to your existing page scripts (after your predict_* core files). This is a minimal, additive layer:

```javascript
// ======= Game Mode Wiring (no changes to Predict button) =======

(function(){
  let gameVariant = 'game1';
  let gameScore = 0;
  let countdownId = null;
  let countdownRemaining = 30;

  // Set target “Say: …”
  function displayTargetSound(classId) {
    const el = document.getElementById('classToSay');
    if (!el) return;
    // Map ID to display name if mapper exists
    let displayName = classId || '…';
    if (window.IdMapper && classId) displayName = window.IdMapper.getClassName(classId) || classId;
    el.innerHTML = 'Say: <span style="color: var(--primary-color);">' + displayName + '</span>';
  }

  // Thumbs up/down/neutral
  function showFace(type) {
    const host = document.getElementById('gameFeedbackIcon');
    if (!host) return;
    let icon = 'horizontal_rule', color = '#9E9E9E';
    if (type === 'happy') { icon = 'thumb_up_alt'; color = '#43A047'; }
    if (type === 'grimace') { icon = 'thumb_down_alt'; color = '#E53935'; }
    host.innerHTML = '<span class="material-icons" style="color:'+color+';">'+icon+'</span>';
  }

  // Pick next target randomly from loaded classes
  function selectNextTargetSound() {
    if (!window.soundClasses || !window.soundClasses.length) return;
    const pool = window.soundClasses;
    const next = pool[Math.floor(Math.random() * pool.length)];
    window.currentGameTargetClassId = next;
    displayTargetSound(next);
    if (gameVariant !== 'puzzle') showFace('neutral');
  }

  // Start/Stop game listening (uses existing audio start/stop)
  function startGame() {
    window.currentGameModeActive = true;
    gameScore = 0;
    updateScoreLabel();
    startCountdown();

    // Ensure classes are ready; then pick target
    if (!window.soundClasses || window.soundClasses.length === 0) {
      // If you have a helper to fetch classes for selected model, call it here before selecting a target
      // await window.fetchClassesForModel(window.selectedModelId);
    }
    selectNextTargetSound();

    if (typeof window.startPredictionSession === 'function' && !window.isListening) {
      window.startPredictionSession();
    }
    updateStartStopLabel();
  }

  function stopGame() {
    window.currentGameModeActive = false;
    stopCountdown();
    if (typeof window.endPredictionSession === 'function' && window.isListening) {
      window.endPredictionSession();
    }
    updateStartStopLabel();
  }

  function updateStartStopLabel() {
    const btn = document.getElementById('gameStartBtn');
    if (!btn) return;
    btn.innerHTML = window.isListening ? '<span class="material-icons">stop</span> Stop'
                                       : '<span class="material-icons">mic</span> Start';
  }

  function updateScoreLabel() {
    const lbl = document.getElementById('gameScoreLabel');
    if (lbl) { lbl.style.display = 'inline'; lbl.textContent = 'Score: ' + gameScore; }
  }

  function startCountdown() {
    const lbl = document.getElementById('gameCountdownLabel');
    countdownRemaining = 30;
    if (lbl) { lbl.style.display = 'inline'; lbl.textContent = countdownRemaining + 's'; }
    if (countdownId) clearInterval(countdownId);
    countdownId = setInterval(() => {
      countdownRemaining = Math.max(0, countdownRemaining - 1);
      if (lbl) lbl.textContent = countdownRemaining + 's';
      if (countdownRemaining <= 0) {
        clearInterval(countdownId); countdownId = null;
        stopGame();
      }
    }, 1000);
  }

  function stopCountdown() {
    if (countdownId) clearInterval(countdownId);
    countdownId = null;
    const lbl = document.getElementById('gameCountdownLabel');
    if (lbl) lbl.style.display = 'none';
  }

  // Hook into your existing processPredictionResponse without changing it:
  const origPPR = window.processPredictionResponse;
  window.processPredictionResponse = function(result, audioId, skipTableUpdate) {
    if (typeof origPPR === 'function') origPPR(result, audioId, skipTableUpdate);

    if (window.currentGameModeActive && result && result.predictions && result.predictions[0]) {
      const pred = result.predictions[0];
      const correct = (pred.class_id && window.currentGameTargetClassId && pred.class_id === window.currentGameTargetClassId);

      if (gameVariant === 'game1') {
        showFace(correct ? 'happy' : 'grimace');
        if (correct) { gameScore += 1; updateScoreLabel(); }
        setTimeout(selectNextTargetSound, 700); // keep flow; no pausing
      }
      // Game 2/3 handled separately below (Tower/Puzzle)
    }
    updateStartStopLabel();
  };

  // Variant radios
  document.querySelectorAll('input[name="gameVariant"]').forEach(r => {
    r.addEventListener('change', () => {
      gameVariant = r.value;
      const status = document.getElementById('gameVariantStatus');
      if (status) status.textContent = 'Active: ' + (gameVariant === 'game2' ? 'Game 2' : (gameVariant === 'puzzle' ? 'Puzzle' : 'Game 1'));

      // Show/hide containers
      document.getElementById('towerGameContainer')?.style && (document.getElementById('towerGameContainer').style.display = (gameVariant === 'game2') ? 'block' : 'none');
      document.getElementById('puzzleGameContainer')?.style && (document.getElementById('puzzleGameContainer').style.display = (gameVariant === 'puzzle') ? 'block' : 'none');

      // Lazy-load Phaser when first entering Game 2
      if (gameVariant === 'game2') {
        if (!window.__phaserLoaded) {
          const s = document.createElement('script');
          s.src = 'https://cdn.jsdelivr.net/npm/phaser@3/dist/phaser.min.js';
          s.onload = function(){ window.__phaserLoaded = true; if (window.initTowerGame) window.initTowerGame('towerGameContainer'); };
          s.onerror = function(){ console.error('Failed to load Phaser'); };
          document.head.appendChild(s);
        } else if (window.initTowerGame) {
          window.initTowerGame('towerGameContainer');
        }
      }
    });
  });

  // Start/Stop button (game-only; Predict button remains untouched)
  document.getElementById('gameStartBtn')?.addEventListener('click', () => {
    if (window.isListening) stopGame(); else startGame();
  });

  // Continuous mode radio: show Analysis card “off” (no auto-start)
  document.getElementById('continuousModeRadio')?.addEventListener('change', function(){
    if (!this.checked) return;
    // Show Analysis controls as OFF; hide Game UI
    document.getElementById('gameModeCard')?.style && (document.getElementById('gameModeCard').style.display = 'block');
    document.getElementById('gameActionBar')?.style && (document.getElementById('gameActionBar').style.display = 'none');
    const analysisCard = document.getElementById('predictionHistoryCard');
    if (analysisCard) analysisCard.style.display = 'block';  // visible OFF state
    const tableContainer = document.getElementById('predictionTableContainer');
    if (tableContainer) tableContainer.style.display = 'none'; // hidden table until Predict
  });

})();
```

Notes:
- The above does not move the Predict button, does not auto-start continuous mode, and gives Game Mode its own Start/Stop.
- Game 2 logic calls `initTowerGame('towerGameContainer')` after Phaser loads. Implement `initTowerGame`/`destroyTowerGame` in your game2 module.
- Puzzle initialization/destroy happens on variant change (stubbed; hook your existing functions there if you have them).

---

## 3) Spacebar toggle (Continuous mode only)
To make Space a true toggle:
- Keep a `window.pausedByUser` flag. In your keydown handler:
  - If listening: `endPredictionSession(); pausedByUser = true`
  - Else if `pausedByUser === true`: `startPredictionSession(); pausedByUser = false`
- In your “auto-restart after prediction” path in `processPredictionResponse`, guard with:
  - `if (window.isListening && !window.pausedByUser && !window.currentGameModeActive) monitorAudioEnergy();`

This prevents unexpected restarts while the user has explicitly paused.

---

## 4) Performance
- Do not load heavy scripts at page load; lazy-load Phaser on first entry to Game 2.
- Keep detection thresholds permissive for responsiveness:
  - ENERGY_THRESHOLD ≈ 0.005–0.008
  - NOISE_THRESHOLD_FACTOR ≈ 1.2–1.8
  - MIN_SILENCE_FRAMES ≈ 3–4
  - POST_SPEECH_MS ≈ 10–20
- Optional: hard cap a single utterance to ~600–800 ms to reduce tail latency if silence isn’t detected promptly.

---

## 5) Test Checklist
1. Load /predict: fast load, Predict button visible below cards. Continuous mode selected, Analysis card visible but table hidden (OFF).
2. Click Predict: mic prompt appears, predictions add to the table quickly. Space toggles pause/resume.
3. Switch to Game Mode:
   - Analysis card remains (but is not used); Game Mode card shows Start button.
   - Start → Stop toggles; countdown 30→0; thumbs show correctly and are centered and large; score increments on corrects; no pause between utterances.
   - Game 2 lazy-loads Phaser the first time only; Puzzle initializes/destroys properly.
4. Leave Game Mode → Continuous: Analysis card visible; table still hidden until Predict is clicked; no auto-start.

This document contains exactly the CSS and JS you need to restore the original UX (Predict stays put) plus the games, with no other side effects.