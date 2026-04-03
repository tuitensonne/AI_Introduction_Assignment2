from __future__ import annotations
import math
import random
from typing import Optional, Dict, List

from chess.board import Board, Move, WHITE, BLACK
from chess.evaluator import evaluate


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
UCT_C = 1.2
SIGMOID_K = 500.0


# ─────────────────────────────────────────────
# TRANSPOSITION TABLE ENTRY
# ─────────────────────────────────────────────
class TTEntry:
    __slots__ = ("wins", "visits")

    def __init__(self):
        self.wins = 0.0
        self.visits = 0


# ─────────────────────────────────────────────
# NODE
# ─────────────────────────────────────────────
class MCTSNode:
    __slots__ = (
        "move",
        "parent",
        "children",
        "wins",
        "visits",
        "moves",
        "next_idx",
        "player_just_moved",
    )

    def __init__(self, board: Board, parent=None, move=None):
        self.move = move
        self.parent = parent
        self.children: List[MCTSNode] = []
        self.wins = 0.0
        self.visits = 0

        moves = board.legal_moves()
        random.shuffle(moves)
        self.moves = moves
        self.next_idx = 0

        self.player_just_moved = -board.turn

    def is_fully_expanded(self) -> bool:
        return self.next_idx >= len(self.moves)

    def expand(self, board: Board) -> "MCTSNode":
        move = self.moves[self.next_idx]
        self.next_idx += 1

        board.push(move)
        child = MCTSNode(board, parent=self, move=move)
        self.children.append(child)
        return child

    def uct(self, log_parent_visits: float) -> float:
        if self.visits == 0:
            return float("inf")
        return (
            self.wins / self.visits
            + UCT_C * math.sqrt(log_parent_visits / self.visits)
        )

    def best_child(self) -> "MCTSNode":
        log_n = math.log(self.visits)
        return max(self.children, key=lambda c: c.uct(log_n))


# ─────────────────────────────────────────────
# MCTS
# ─────────────────────────────────────────────
class MCTSAI:
    def __init__(self, iterations: int = 1000, rollout_depth: int = 40):
        self.iterations = iterations
        self.rollout_depth = rollout_depth
        self.tt: Dict[int, TTEntry] = {}

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────
    def choose_move(self, board: Board) -> Optional[Move]:
        root = MCTSNode(board)

        for _ in range(self.iterations):
            self._run_iteration(board, root)

        if not root.children:
            return None

        return max(root.children, key=lambda c: c.visits).move

    # ─────────────────────────────────────────
    # CORE LOOP
    # ─────────────────────────────────────────
    def _run_iteration(self, board: Board, root: MCTSNode):
        node = root
        pushed = 0

        # ── SELECTION ─────────────────────────
        while node.is_fully_expanded() and node.children:
            node = node.best_child()
            board.push(node.move)
            pushed += 1

            # TT read (lightweight)
            h = board.zobrist_hash()
            entry = self.tt.get(h)
            if entry and entry.visits < 1000:
                node.visits += entry.visits
                node.wins += entry.wins

        # ── EXPANSION ─────────────────────────
        if not node.is_fully_expanded():
            node = node.expand(board)
            pushed += 1

        # ── SIMULATION ────────────────────────
        result, sim_pushed = self._simulate(board)
        pushed += sim_pushed

        # ── BACKPROP ─────────────────────────
        self._backprop(node, result, board, pushed)

    # ─────────────────────────────────────────
    # SIMULATION
    # ─────────────────────────────────────────
    def _simulate(self, board: Board) -> (float, int):
        pushed = 0

        for _ in range(self.rollout_depth):
            status = board.status()
            if status != "playing":
                break

            moves = board.legal_moves()
            if not moves:
                break

            move = self._select_rollout_move(board, moves)
            board.push(move)
            pushed += 1

        result = self._evaluate(board)
        return result, pushed

    def _select_rollout_move(self, board: Board, moves: List[Move]) -> Move:
        # sample few moves instead of scanning all
        for _ in range(3):
            m = random.choice(moves)
            if board.is_tactical(m):
                return m
        return random.choice(moves)

    # ─────────────────────────────────────────
    # EVALUATION
    # ─────────────────────────────────────────
    def _evaluate(self, board: Board) -> float:
        status = board.status()

        if status == "checkmate":
            winner = board.winner()
            if winner == WHITE:
                return 1.0
            elif winner == BLACK:
                return 0.0
            return 0.5

        if status in ("draw", "stalemate"):
            return 0.5

        score = evaluate(board)
        score = max(min(score, 2000), -2000)

        return 1 / (1 + math.exp(-score / SIGMOID_K))

    # ─────────────────────────────────────────
    # BACKPROP
    # ─────────────────────────────────────────
    def _backprop(self, node: MCTSNode, result: float, board: Board, pushed: int):
        for _ in range(pushed):
            h = board.zobrist_hash()

            entry = self.tt.get(h)
            if entry is None:
                entry = self.tt[h] = TTEntry()

            entry.visits += 1
            entry.wins += result

            board.pop()

        while node:
            node.visits += 1

            if node.player_just_moved == WHITE:
                node.wins += result
            else:
                node.wins += (1 - result)

            node = node.parent