# Chess AI Lab

A complete web-based Chess AI project built for an AI course assignment.
Implements Minimax with Alpha-Beta Pruning and Monte Carlo Tree Search (MCTS).

---

## Quick Start

```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

---

## Project Structure

```
chess_ai/
├── app.py                   ← Entry point (Flask server)
├── requirements.txt
│
├── chess/
│   ├── board.py             ← Board, move generation, game rules
│   └── evaluator.py         ← Static position evaluation (material + PST)
│
├── ai/
│   ├── alphabeta.py         ← Minimax + Alpha-Beta pruning
│   └── mcts.py              ← Monte Carlo Tree Search (UCT)
│
├── api/
│   └── server.py            ← REST API (Flask)
│
├── templates/
│   └── index.html           ← Single-page web UI
│
├── static/
    └── js/chess.js          ← Frontend game controller

```

---

## Features

| Feature          | Details                                                                    |
| ---------------- | -------------------------------------------------------------------------- |
| Human vs Human   | Click to move on the web board                                             |
| Human vs AI      | Choose Alpha-Beta or MCTS for Black/White                                  |
| AI vs AI         | Watch algorithms battle with live metrics                                  |
| Difficulty       | Easy / Medium / Hard (controls depth / iterations)                         |
| Full chess rules | En passant, castling, promotion, check, checkmate, stalemate, 50-move draw |
| Metrics panel    | Nodes explored, time per move, algorithm                                   |

---

## Algorithms

### Alpha-Beta (Minimax)

Recursive adversarial search to depth D. The evaluation function scores
positions using material values (pawn=100cp, knight=320cp, …) and
piece-square tables.

Alpha-Beta pruning cuts branches where α ≥ β, reducing effective
branching factor from ~35 to ~6 with good move ordering.

**Difficulty settings:**

- Easy → depth 2
- Medium → depth 3
- Hard → depth 4

### MCTS (UCT)

Four-phase loop: Select → Expand → Simulate → Backpropagate.

UCT selection: `Q/N + C·√(ln(N_parent)/N)` with C=√2.

Terminal detection uses the static evaluator when rollout depth is exceeded.

**Difficulty settings:**

- Easy → 200 iterations
- Medium → 600 iterations
- Hard → 1200 iterations

---

## API Endpoints

| Method | URL                 | Description             |
| ------ | ------------------- | ----------------------- |
| POST   | `/api/new_game`     | Start a new game        |
| GET    | `/api/board/<id>`   | Get current board state |
| POST   | `/api/move/<id>`    | Submit a human move     |
| POST   | `/api/ai_move/<id>` | Request an AI move      |
