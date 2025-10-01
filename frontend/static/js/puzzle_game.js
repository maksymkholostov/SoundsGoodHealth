// Simple Puzzle Game (Game 3) - external file to avoid inline script stripping
(function(){
  let container, imgUrl, tiles = [], size = 5, tileSize = 64, hidden = new Set();

  function drawGrid(){
    if (!container) return;
    container.innerHTML = '';
    // Box frame only; no shaded image underneath
    container.style.background = 'transparent';
    container.style.border = '2px solid rgba(0,0,0,0.12)';
    for (let r=0; r<size; r++){
      for (let c=0; c<size; c++){
        const idx = r*size+c;
        const tile = document.createElement('div');
        tile.className = 'pz-tile';
        tile.style.cssText = `position:absolute; width:${tileSize}px; height:${tileSize}px; left:${c*tileSize}px; top:${r*tileSize}px; background:url('${imgUrl}') ${-c*tileSize}px ${-r*tileSize}px / ${size*tileSize}px ${size*tileSize}px no-repeat; border:1px solid rgba(255,255,255,0.6); box-sizing:border-box; border-radius:6px; transform: rotateY(90deg); opacity:0; transition: transform 200ms ease, opacity 200ms ease;`;
        if (!hidden.has(idx)) tile.style.visibility = 'hidden';
        container.appendChild(tile);
        tiles[idx] = tile;
      }
    }
  }

  function showCompletion(){
    if (!container) return;
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:absolute; inset:0; display:flex; align-items:center; justify-content:center; background: rgba(0,0,0,0.35); color:#fff; font-size:22px; font-weight:700; text-shadow: 0 2px 4px rgba(0,0,0,0.4); border-radius:8px;';
    overlay.textContent = 'Hooray! You finished the puzzle!';
    container.appendChild(overlay);
    // Optional toast if available
    if (typeof window.showToast === 'function') {
      try { window.showToast('Hooray! You finished the puzzle!', 'success'); } catch(e) {}
    }
    // End the game loop/session on completion
    try { if (typeof window.stopGameLoop === 'function') window.stopGameLoop(); } catch(e) {}
    try { if (window.isListening && typeof window.endPredictionSession === 'function') window.endPredictionSession(); } catch(e) {}
  }

  function revealRandom(){
    const remaining = Array.from(hidden);
    if (remaining.length === 0) return;
    const idx = remaining[Math.floor(Math.random()*remaining.length)];
    hidden.delete(idx);
    const t = tiles[idx];
    if (t){
      t.style.visibility = 'visible';
      requestAnimationFrame(()=>{
        t.style.transform = 'rotateY(0deg)';
        t.style.opacity = '1';
      });
    }
    // Completion check
    if (hidden.size === 0) {
      showCompletion();
    }
  }

  window.initPuzzleGame = function(){
    container = document.getElementById('puzzleGameContainer');
    if (!container) return;
    imgUrl = container.getAttribute('data-img-url');
    // compute tile size based on container width
    const w = container.clientWidth || 480;
    size = 5; tileSize = Math.floor(w/size);
    hidden = new Set(Array.from({length:size*size}, (_,i)=>i));
    drawGrid();
  };

  window.destroyPuzzleGame = function(){ tiles=[]; if (hidden) hidden.clear(); if (container) container.innerHTML=''; };

  window.puzzleOnAnswer = function(isCorrect){
    const shown = document.getElementById('puzzleGameContainer');
    if (!shown || shown.style.display === 'none') return;
    if (isCorrect) revealRandom();
  };
})();


