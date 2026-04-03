from __future__ import annotations
import time
from typing import Optional, Dict, Tuple, List

from chess.board import Board, Move
from chess.evaluator import evaluate, CHECKMATE_SCORE

INFINITY = CHECKMATE_SCORE * 10


class SearchTimeout(Exception):
    pass


class AlphaBetaAI:
    def __init__(self, depth: int = 5, time_limit: Optional[float] = None):
        """
        Params:
            depth: max search depth
            time_limit: seconds (optional)
        """
        self.depth = depth
        self.time_limit = time_limit

        self.nodes = 0
        self.start_time = 0.0

        # Simple Transposition Table
        # key -> {depth, score, move}
        self.tt: Dict[int, dict] = {}

    # ─────────────────────────────────────────
    # PUBLIC
    # ─────────────────────────────────────────
    def choose_move(self, board: Board) -> Optional[Move]:
        self.nodes = 0
        self.start_time = time.perf_counter()

        legal_moves = list(board.legal_moves())
        if not legal_moves:
            return None

        best_move = legal_moves[0]
        best_score = -INFINITY

        limit = self.time_limit if self.time_limit else 5.0

        try:
            # Iterative Deepening
            for d in range(1, self.depth + 1):
                if self._time_up(limit * 0.9):
                    break

                move, score = self._search(board, d, -INFINITY, INFINITY)

                if move is not None:
                    best_move = move
                    best_score = score

                # Stop early if checkmate found
                if abs(score) >= CHECKMATE_SCORE - 100:
                    break

        except SearchTimeout:
            pass

        return best_move

    # ─────────────────────────────────────────
    # CORE SEARCH (Alpha-Beta)
    # ─────────────────────────────────────────
    def _search(
        self,
        board: Board,
        depth: int,
        alpha: float,
        beta: float,
    ) -> Tuple[Optional[Move], float]:

        self.nodes += 1

        # Time check (cheap)
        if self.nodes & 2047 == 0:
            if self._time_up():
                raise SearchTimeout()

        key = board.zobrist_hash()

        # ── TT lookup ─────────────────────────
        entry = self.tt.get(key)
        if entry and entry["depth"] >= depth:
            return entry["move"], entry["score"]

        # ── Terminal ─────────────────────────
        status = board.status()
        if status != "playing":
            if status == "checkmate":
                return None, -CHECKMATE_SCORE
            return None, 0

        # ── Depth cutoff ─────────────────────
        if depth == 0:
            return None, self._quiescence(board, alpha, beta)

        # ── Move ordering ────────────────────
        moves = list(board.legal_moves())

        tt_move = entry["move"] if entry else None

        def move_score(m: Move):
            if m == tt_move:
                return 100000
            if board.is_capture(m):
                # MVV-LVA
                return 10000 + abs(board.squares[m.to_sq]) * 10 - abs(board.squares[m.from_sq])
            return 0

        moves.sort(key=move_score, reverse=True)

        best_move = None
        best_score = -INFINITY

        # ── Search loop ──────────────────────
        for move in moves:
            board.push(move)

            _, score = self._search(board, depth - 1, -beta, -alpha)
            score = -score

            board.pop()

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, score)
            if alpha >= beta:
                break  # Alpha-beta cutoff

        # ── Store TT ─────────────────────────
        self.tt[key] = {
            "depth": depth,
            "score": best_score,
            "move": best_move,
        }

        return best_move, best_score

    # ─────────────────────────────────────────
    # QUIESCENCE SEARCH
    # ─────────────────────────────────────────
    def _quiescence(self, board: Board, alpha: float, beta: float) -> float:
        self.nodes += 1

        stand_pat = evaluate(board)

        if stand_pat >= beta:
            return beta

        alpha = max(alpha, stand_pat)

        # Only captures
        moves = list(board.legal_moves())
        captures = [m for m in moves if board.is_capture(m)]

        # Simple MVV ordering
        captures.sort(key=lambda m: abs(board.squares[m.to_sq]), reverse=True)

        for move in captures:
            board.push(move)

            score = -self._quiescence(board, -beta, -alpha)

            board.pop()

            if score >= beta:
                return beta

            alpha = max(alpha, score)

        return alpha

    # ─────────────────────────────────────────
    # TIME CHECK
    # ─────────────────────────────────────────
    def _time_up(self, limit: Optional[float] = None) -> bool:
        if self.time_limit is None and limit is None:
            return False

        t = time.perf_counter() - self.start_time
        if limit is not None:
            return t >= limit

        return t >= self.time_limit