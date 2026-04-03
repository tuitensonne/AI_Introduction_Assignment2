"""
api/server.py
Flask REST API + WebSocket server for the Chess AI web GUI.

Endpoints
─────────
POST /api/new_game          → start a new game
GET  /api/board/<game_id>   → current board state
POST /api/move/<game_id>    → human move
POST /api/ai_move/<game_id> → request AI move
"""

import uuid
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from chess.board import Board, Move, WHITE, BLACK, sq_to_an, an_to_sq, PIECE_SYMBOLS
from ai.alphabeta import AlphaBetaAI
from ai.mcts import MCTSAI

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)
CORS(app)

# ── In-memory game store ──────────────────────────────────────────────────────
_games: dict[str, dict] = {}

# --- api/server.py ---

def _make_ai(algorithm: str, difficulty: str):
    if algorithm == "alphabeta":
        depth_map = {"easy": 2, "medium": 3, "hard": 4}
        return AlphaBetaAI(depth=depth_map.get(difficulty, 3))
    elif algorithm == "mcts":
        iter_map = {"easy": 200, "medium": 600, "hard": 1200}
        return MCTSAI(iterations=iter_map.get(difficulty, 600))
    return None


def _board_to_json(board: Board) -> dict:
    """Serialise board for the frontend."""
    squares = []
    for i, p in enumerate(board.squares):
        squares.append({
            "index":  i,
            "piece":  p,
            "symbol": PIECE_SYMBOLS[p],
        })
    legal_moves = []
    for m in board.legal_moves():
        legal_moves.append({"from": m.from_sq, "to": m.to_sq, "promotion": m.promotion})

    return {
        "squares":    squares,
        "turn":       board.turn,
        "turn_name":  "white" if board.turn == WHITE else "black",
        "status":     board.status(),
        "in_check":   board.in_check(),
        "legal_moves": legal_moves,
    }


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/new_game", methods=["POST"])
def new_game():
    data = request.json or {}
    game_id    = str(uuid.uuid4())[:8]
    white_algo = data.get("white_algo", "human")    # "human"|"alphabeta"|"mcts"
    black_algo = data.get("black_algo", "alphabeta")
    difficulty = data.get("difficulty", "medium")

    board = Board()
    _games[game_id] = {
        "board":       board,
        "white_algo":  white_algo,
        "black_algo":  black_algo,
        "difficulty":  difficulty,
        "move_count":  0,
        "white_ai":    _make_ai(white_algo, difficulty),
        "black_ai":    _make_ai(black_algo, difficulty),
    }
    return jsonify({"game_id": game_id, "board": _board_to_json(board)})


@app.route("/api/board/<game_id>")
def get_board(game_id: str):
    game = _games.get(game_id)
    if not game:
        return jsonify({"error": "game not found"}), 404
    return jsonify(_board_to_json(game["board"]))


@app.route("/api/move/<game_id>", methods=["POST"])
def human_move(game_id: str):
    game = _games.get(game_id)
    if not game:
        return jsonify({"error": "game not found"}), 404

    data    = request.json or {}
    from_sq = data.get("from_sq")
    to_sq   = data.get("to_sq")
    promo   = data.get("promotion", 0)

    board = game["board"]
    legal = board.legal_moves()

    # Find matching legal move
    matched = None
    for m in legal:
        if m.from_sq == from_sq and m.to_sq == to_sq:
            if promo and m.promotion != promo:
                continue
            matched = m
            break

    if not matched:
        return jsonify({"error": "illegal move"}), 400

    # push() now mutates the board instead of returning a new one
    board.push(matched)
    game["move_count"] += 1

    status = board.status()
    if status != "playing":
        _finish_game(game_id, game)

    return jsonify({
        "board": _board_to_json(board),
        "move":  str(matched),
    })


@app.route("/api/ai_move/<game_id>", methods=["POST"])
def ai_move(game_id: str):
    game = _games.get(game_id)
    if not game:
        return jsonify({"error": "game not found"}), 404

    board = game["board"]
    color = board.turn
    ai    = game["white_ai"] if color == WHITE else game["black_ai"]
    algo  = game["white_algo"] if color == WHITE else game["black_algo"]

    if ai is None:
        return jsonify({"error": "no AI for this side"}), 400
    if board.status() != "playing":
        return jsonify({"error": "game over"}), 400

    move = ai.choose_move(board)
    if not move:
        return jsonify({"error": "AI found no move"}), 500

    # push() now mutates the board instead of returning a new one
    board.push(move)
    game["move_count"] += 1

    status = board.status()
    if status != "playing":
        _finish_game(game_id, game)

    return jsonify({
        "board":   _board_to_json(board),
        "move":    str(move),
    })

@app.route("/api/legal_moves/<game_id>/<int:square>")
def legal_moves_for_square(game_id: str, square: int):
    game = _games.get(game_id)
    if not game:
        return jsonify({"error": "game not found"}), 404
    board  = game["board"]
    result = [m.to_sq for m in board.legal_moves() if m.from_sq == square]
    return jsonify({"targets": result})


# ── Helpers ───────────────────────────────────────────────────────────────────
def _finish_game(game_id: str, game: dict):
    board  = game["board"]
    status = board.status()
    winner = board.winner()
    if winner == WHITE:      result = "white"
    elif winner == BLACK:    result = "black"
    else:                    result = "draw"


if __name__ == "__main__":
    app.run(debug=True, port=5000)