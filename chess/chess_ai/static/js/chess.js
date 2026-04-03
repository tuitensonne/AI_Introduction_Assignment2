/**
 * static/js/chess.js
 * Frontend game controller — communicates with Flask API.
 */

"use strict";

// Maps backend piece codes to Unicode symbols for board rendering.
const PIECE_UNICODE = {
   6:"♔",  5:"♕",  4:"♖",  3:"♗",  2:"♘",  1:"♙",
  "-6":"♚","-5":"♛","-4":"♜","-3":"♝","-2":"♞","-1":"♟",
};

// Central UI/game state used by the frontend controller.
// - `selected` tracks the currently selected source square.
// - `legalTargets` stores destination squares for the selected piece.
// - `pendingPromo` stores a move while waiting for promotion choice.
let state = {
  gameId:       null,
  boardData:    null,
  selected:     null,       // Index of the currently selected board square.
  legalTargets: [],         // Legal destination square indices for the selected piece.
  pendingPromo: null,       // Promotion move payload `{ from, to }` while modal is open.
  moveLog:      [],         // Chronological list of move strings returned by the API.
  moveCount:    0,
  gamesPlayed:  0,
  whiteAlgo:    "human",
  blackAlgo:    "alphabeta",
  gameOver:     false,
};

// Handles top-level tab visibility and active button styling.
function showTab(name) {
  ["game"].forEach(t => {
    document.getElementById(`tab-${t}`).style.display = "none";
  });
  document.getElementById(`tab-${name}`).style.display = name === "game" ? "grid" : "block";
  document.querySelectorAll(".nav-btn").forEach((b,i) => {
    b.classList.toggle("active", ["game"][i] === name);
  });
}

// Starts a new game by sending selected algorithms and difficulty to the API,
// then resets UI state and optionally triggers White's AI move.
async function startGame() {
  state.whiteAlgo = document.getElementById("white-algo").value;
  state.blackAlgo = document.getElementById("black-algo").value;
  const difficulty = document.getElementById("difficulty").value;

  const res = await fetch("/api/new_game", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({
      white_algo: state.whiteAlgo,
      black_algo: state.blackAlgo,
      difficulty,
    }),
  });
  const data = await res.json();
  state.gameId    = data.game_id;
  state.boardData = data.board;
  state.selected  = null;
  state.legalTargets = [];
  state.moveLog   = [];
  state.moveCount = 0;
  state.gameOver  = false;
  state.gamesPlayed++;

  renderBoard();
  updateStatus();
  updateMoveLog();
  updateSessionStats();
  toast("New game started!");

  // If White is controlled by AI, request its opening move immediately.
  if (state.whiteAlgo !== "human") {
    setTimeout(requestAIMove, 300);
  }
}

// Rebuilds the full board grid (rank labels, 64 squares, and file labels).
function renderBoard() {
  const container = document.getElementById("board");
  container.innerHTML = "";

  // Render rank labels (8..1) down the left side of the board.
  for (let r = 7; r >= 0; r--) {
    const lbl = document.createElement("div");
    lbl.className = "rank-label";
    lbl.textContent = r + 1;
    container.appendChild(lbl);
    for (let f = 0; f < 8; f++) {
      container.appendChild(makeSquare(r * 8 + f));
    }
  }
  // Render file labels (a..h) along the bottom row.
  const blank = document.createElement("div");
  container.appendChild(blank);
  for (const c of "abcdefgh") {
    const lbl = document.createElement("div");
    lbl.className = "file-label";
    lbl.textContent = c;
    container.appendChild(lbl);
  }
}

function makeSquare(idx) {
  const rank = idx >> 3, file = idx & 7;
  const isLight = (rank + file) % 2 === 1;

  const sq = document.createElement("div");
  sq.className = `sq ${isLight ? "light" : "dark"}`;
  sq.dataset.idx = idx;
  sq.addEventListener("click", () => onSquareClick(idx));

  // Place piece glyph if this square is occupied.
  if (state.boardData) {
    const piece = state.boardData.squares[idx]?.piece;
    if (piece !== 0) {
      const span = document.createElement("span");
      span.className = "piece";
      span.textContent = PIECE_UNICODE[String(piece)] || "";
      sq.appendChild(span);
    }
  }

  // Mark the currently selected source square.
  if (state.selected === idx) sq.classList.add("selected");

  // Highlight legal destination squares (separate style for captures).
  if (state.legalTargets.includes(idx)) {
    const piece = state.boardData?.squares[idx]?.piece;
    sq.classList.add(piece !== 0 ? "legal-capture" : "legal-target");
  }

  // Highlight king square when the side to move is currently in check.
  if (state.boardData?.in_check) {
    const kingSq = findKing(state.boardData.turn);
    if (kingSq === idx) sq.classList.add("in-check");
  }

  return sq;
}

function findKing(color) {
  if (!state.boardData) return -1;
  const kingPiece = color * 6; // King is encoded as +/-6 depending on color.
  for (const s of state.boardData.squares) {
    if (s.piece === kingPiece) return s.index;
  }
  return -1;
}

// Handles user interaction with board squares:
// - select own piece
// - execute legal move
// - open promotion modal when needed
// - reselect or clear selection
function onSquareClick(idx) {
  if (!state.gameId || state.gameOver) return;

  const board = state.boardData;
  const humanTurn = (board.turn === 1 && state.whiteAlgo === "human") ||
                    (board.turn === -1 && state.blackAlgo === "human");
  if (!humanTurn) return;

  const piece = board.squares[idx]?.piece;
  const ownPiece = (board.turn === 1 && piece > 0) || (board.turn === -1 && piece < 0);

  if (state.selected === null) {
    if (ownPiece) {
      state.selected = idx;
      state.legalTargets = board.legal_moves
        .filter(m => m.from === idx)
        .map(m => m.to);
      renderBoard();
    }
  } else {
    if (state.legalTargets.includes(idx)) {
      const moves = board.legal_moves.filter(m => m.from === state.selected && m.to === idx);
      if (moves.some(m => m.promotion !== 0)) {
        // Pause move submission until the player chooses a promotion piece.
        state.pendingPromo = { from: state.selected, to: idx };
        document.getElementById("promo-modal").classList.add("open");
      } else {
        submitMove(state.selected, idx, 0);
      }
    } else if (ownPiece) {
      // Allow fast re-selection when another own piece is clicked.
      state.selected = idx;
      state.legalTargets = board.legal_moves
        .filter(m => m.from === idx)
        .map(m => m.to);
      renderBoard();
    } else {
      state.selected = null;
      state.legalTargets = [];
      renderBoard();
    }
  }
}

// Finalizes a pending promotion move after the player selects a piece type.
function choosePromotion(piece) {
  document.getElementById("promo-modal").classList.remove("open");
  if (state.pendingPromo) {
    submitMove(state.pendingPromo.from, state.pendingPromo.to, piece);
    state.pendingPromo = null;
  }
}

// Submits a human move to the backend and refreshes all UI panels.
// If the game continues and next side is AI, schedules the AI response.
async function submitMove(from, to, promotion) {
  state.selected = null;
  state.legalTargets = [];

  const res = await fetch(`/api/move/${state.gameId}`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ from_sq: from, to_sq: to, promotion }),
  });

  if (!res.ok) {
    toast("Illegal move!", true);
    renderBoard();
    return;
  }

  const data = await res.json();
  state.boardData = data.board;
  state.moveCount++;
  state.moveLog.push(data.move);

  renderBoard();
  updateStatus();
  updateMoveLog();
  updateSessionStats();

  if (state.boardData.status !== "playing") {
    handleGameOver();
    return;
  }

  // If the next side is AI-controlled, request its move.
  const nextAlgo = state.boardData.turn === 1 ? state.whiteAlgo : state.blackAlgo;
  if (nextAlgo !== "human") {
    setTimeout(requestAIMove, 200);
  }
}

// Requests one AI move from the backend, updates metrics, and continues
// automatically in AI-vs-AI mode until the game ends.
async function requestAIMove() {
  if (!state.gameId || state.gameOver) return;

  const board = state.boardData;
  if (!board || board.status !== "playing") return;

  const algo = board.turn === 1 ? state.whiteAlgo : state.blackAlgo;
  if (algo === "human") return;

  showThinking(true, algo);

  const res = await fetch(`/api/ai_move/${state.gameId}`, { method: "POST" });

  if (!res.ok) {
    showThinking(false);
    toast("AI error!", true);
    return;
  }

  const data = await res.json();
  state.boardData = data.board;
  state.moveCount++;
  state.moveLog.push(data.move);

  if (data.metrics) updateMetrics(data.metrics, data.move);

  renderBoard();
  updateStatus();
  updateMoveLog();
  updateSessionStats();
  showThinking(false);

  if (state.boardData.status !== "playing") {
    handleGameOver();
    return;
  }

  // Continue automatic play when both sides are AI-controlled.
  const nextAlgo = state.boardData.turn === 1 ? state.whiteAlgo : state.blackAlgo;
  if (nextAlgo !== "human") {
    setTimeout(requestAIMove, 150);
  }
}

// Handles final game state messaging for checkmate/stalemate/draw.
function handleGameOver() {
  state.gameOver = true;
  const status = state.boardData.status;
  let msg;
  if (status === "checkmate") {
    const winner = state.boardData.turn === 1 ? "Black" : "White";
    msg = `♛ ${winner} wins by checkmate!`;
  } else if (status === "stalemate") {
    msg = "½ Draw by stalemate";
  } else {
    msg = "½ Draw";
  }
  document.getElementById("status-turn").textContent = msg;
  document.getElementById("status-info").textContent = `Game ${state.gameId} ended`;
  toast(msg);
}

// UI helper functions for status text, move history, metrics, and overlays.
function updateStatus() {
  if (!state.boardData) return;
  const b = state.boardData;
  const turnName = b.turn === 1 ? "White" : "Black";
  const algo = b.turn === 1 ? state.whiteAlgo : state.blackAlgo;
  const who = algo === "human" ? "Your move" : `${algo.toUpperCase()} thinking`;

  document.getElementById("status-turn").innerHTML =
    `${turnName} to move` +
    (b.in_check ? `<span class="check-badge">CHECK</span>` : "");
  document.getElementById("status-info").textContent = who;
}

function updateMoveLog() {
  const log = document.getElementById("move-log");
  if (!state.moveLog.length) {
    log.innerHTML = `<span style="color:var(--text-dim);font-size:.75rem">No moves yet.</span>`;
    return;
  }
  let html = "";
  for (let i = 0; i < state.moveLog.length; i += 2) {
    const num  = Math.floor(i/2) + 1;
    const wm   = state.moveLog[i] || "";
    const bm   = state.moveLog[i+1] || "";
    html += `<div class="move-pair">
      <span class="move-num">${num}.</span>
      <span class="move-w">${wm}</span>
      <span class="move-b">${bm}</span>
    </div>`;
  }
  log.innerHTML = html;
  log.scrollTop = log.scrollHeight;
}

function updateMetrics(m, move) {
  document.getElementById("m-algo").textContent   = m.algorithm || "—";
  document.getElementById("m-nodes").textContent  = (m.nodes_explored||0).toLocaleString();
  document.getElementById("m-time").textContent   = `${(m.time_taken_s||0).toFixed(3)}s`;
  document.getElementById("m-depth").textContent  = m.depth || m.iterations || "—";
  document.getElementById("m-move").textContent   = move || "—";
}

function updateSessionStats() {
  document.getElementById("s-games").textContent = state.gamesPlayed;
  document.getElementById("s-move").textContent  = state.moveCount;
  document.getElementById("s-id").textContent    = state.gameId || "—";
}

function showThinking(show, algo) {
  const el = document.getElementById("thinking-overlay");
  el.classList.toggle("active", show);
  if (algo) {
    document.getElementById("thinking-label").textContent =
      `${algo.toUpperCase()} thinking…`;
  }
}
// Displays a temporary toast notification for success/error feedback.
function toast(msg, isError) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.style.borderColor = isError ? "#c04040" : "var(--accent)";
  el.style.color = isError ? "#e06060" : "var(--accent)";
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2800);
}

// Initial page setup after DOM is ready.
document.addEventListener("DOMContentLoaded", () => {
  showTab("game");
  renderBoard();
});
