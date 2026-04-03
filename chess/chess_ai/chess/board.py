"""
chess/board.py
Core chess board representation.
Uses a flat 64-element list (index = rank*8 + file).
Piece encoding: positive = White, negative = Black.
  1=Pawn  2=Knight  3=Bishop  4=Rook  5=Queen  6=King

"""

from __future__ import annotations
from typing import List, Optional
import random

# ── Zobrist ──────────────────────────────────────────────────────────────────
ZOBRIST_TABLE = [[random.getrandbits(64) for _ in range(13)] for _ in range(64)]
ZOBRIST_TURN  = random.getrandbits(64)

# ── Piece constants ──────────────────────────────────────────────────────────
EMPTY  = 0
PAWN   = 1
KNIGHT = 2
BISHOP = 3
ROOK   = 4
QUEEN  = 5
KING   = 6

WHITE =  1
BLACK = -1

PIECE_SYMBOLS = {
    0: ".",
    PAWN: "P", KNIGHT: "N", BISHOP: "B",
    ROOK: "R", QUEEN: "Q", KING: "K",
    -PAWN: "p", -KNIGHT: "n", -BISHOP: "b",
    -ROOK: "r", -QUEEN: "q", -KING: "k",
}


# ── Move ─────────────────────────────────────────────────────────────────────
class Move:
    """Lightweight move representation."""
    __slots__ = ("from_sq", "to_sq", "promotion", "is_castle", "is_en_passant")

    def __init__(
        self,
        from_sq: int,
        to_sq: int,
        promotion: int = EMPTY,
        is_castle: bool = False,
        is_en_passant: bool = False,
    ):
        self.from_sq       = from_sq
        self.to_sq         = to_sq
        self.promotion     = promotion
        self.is_castle     = is_castle
        self.is_en_passant = is_en_passant

    def to_dict(self) -> dict:
        return {
            "from_sq":   self.from_sq,
            "to_sq":     self.to_sq,
            "promotion": self.promotion,
        }

    def __eq__(self, other):
        return (
            isinstance(other, Move)
            and self.from_sq   == other.from_sq
            and self.to_sq     == other.to_sq
            and self.promotion == other.promotion
        )

    def __repr__(self):
        p = f"={PIECE_SYMBOLS[self.promotion]}" if self.promotion else ""
        return f"{sq_to_an(self.from_sq)}{sq_to_an(self.to_sq)}{p}"


# ── Helpers ──────────────────────────────────────────────────────────────────
def sq(rank: int, file: int) -> int:
    return rank * 8 + file

def rank_of(s: int) -> int: return s >> 3
def file_of(s: int) -> int: return s & 7

def sq_to_an(s: int) -> str:
    return "abcdefgh"[file_of(s)] + str(rank_of(s) + 1)

def an_to_sq(an: str) -> int:
    return sq("12345678".index(an[1]), "abcdefgh".index(an[0]))


# ── Board ────────────────────────────────────────────────────────────────────
class Board:
    # Declare all instance attributes up front to reduce memory overhead and
    # prevent accidental dynamic attribute creation.
    __slots__ = (
        "squares", 
        "turn", 
        "castling", 
        "en_passant_sq", 
        "halfmove_clock", 
        "fullmove", 
        "_history"
    )

    def __init__(self):
        # Initialize all board state fields.
        self.squares:       List[int]       = [EMPTY] * 64
        self.turn:          int             = WHITE
        self.castling:      dict            = {"K": True, "Q": True, "k": True, "q": True}
        self.en_passant_sq: Optional[int]   = None
        self.halfmove_clock: int             = 0
        self.fullmove:      int             = 1
        self._history:      List[dict]      = []

        # Important: any new `self.<field>` introduced in this class must also
        # be added to `__slots__`.
        self._setup_start()

    # ── Setup ────────────────────────────────────────────────────────────────
    def _setup_start(self):
        back = [ROOK, KNIGHT, BISHOP, QUEEN, KING, BISHOP, KNIGHT, ROOK]
        for f, p in enumerate(back):
            self.squares[sq(0, f)] =  p
            self.squares[sq(7, f)] = -p
            self.squares[sq(1, f)] =  PAWN
            self.squares[sq(6, f)] = -PAWN

    @classmethod
    def from_dict(cls, d: dict) -> "Board":
        b = cls.__new__(cls)
        b.squares        = list(d["squares"])
        b.turn           = d["turn"]
        b.castling       = dict(d["castling"])
        b.en_passant_sq  = d["en_passant_sq"]
        b.halfmove_clock = d["halfmove_clock"]
        b.fullmove       = d["fullmove"]
        b._history       = []
        return b

    def to_dict(self) -> dict:
        return {
            "squares":        list(self.squares),
            "turn":           self.turn,
            "castling":       dict(self.castling),
            "en_passant_sq":  self.en_passant_sq,
            "halfmove_clock": self.halfmove_clock,
            "fullmove":       self.fullmove,
        }

    def copy(self) -> "Board":
        return Board.from_dict(self.to_dict())

    # ── Move generation ──────────────────────────────────────────────────────
    def pseudo_legal_moves(self, color: int) -> List[Move]:
        moves = []
        for s in range(64):
            p = self.squares[s]
            if p == EMPTY or (p > 0) != (color > 0):
                continue
            pt = abs(p)
            if   pt == PAWN:   moves += self._pawn_moves(s, color)
            elif pt == KNIGHT: moves += self._knight_moves(s, color)
            elif pt == BISHOP: moves += self._slider_moves(s, color, [(1,1),(1,-1),(-1,1),(-1,-1)])
            elif pt == ROOK:   moves += self._slider_moves(s, color, [(1,0),(-1,0),(0,1),(0,-1)])
            elif pt == QUEEN:  moves += self._slider_moves(s, color, [(1,1),(1,-1),(-1,1),(-1,-1),(1,0),(-1,0),(0,1),(0,-1)])
            elif pt == KING:   moves += self._king_moves(s, color)
        return moves

    def legal_moves(self) -> List[Move]:
        """
        Returns legal moves for the side to move.

        A move is legal only if it does not leave that side's king in check.
        Castling is filtered here (instead of in pseudo-legal generation) to
        avoid nested `is_in_check` calls during move generation.

        Castling validation is intentionally split as follows:
        1) `_king_moves` checks rights + empty path squares.
        2) `legal_moves` checks current check state and attacked transit squares.
        3) Destination safety is validated by push/pop with `is_in_check`.
        """
        result = []
        current_turn = self.turn

        # Compute once for castling validation: king cannot castle out of check.
        in_check_now = self.is_in_check(current_turn)

        for m in self.pseudo_legal_moves(current_turn):

            # Castling-specific legality filters.
            if m.is_castle:
                # Condition 1: king is not currently in check.
                if in_check_now:
                    continue
                # Condition 2: king does not pass through an attacked square.
                back_rank = 0 if current_turn == WHITE else 7
                f_to = file_of(m.to_sq)
                # Kingside crosses file 5; queenside crosses file 3.
                mid_file  = 5 if f_to == 6 else 3
                mid_sq    = sq(back_rank, mid_file)
                if self._sq_attacked(mid_sq, -current_turn):
                    continue
                # Condition 3 (destination not attacked) is validated by push/pop.

            # Keep only moves that do not leave king in check.
            self.push(m)
            if not self.is_in_check(current_turn):
                result.append(m)
            self.pop()

        return result

    # ── Pawn ─────────────────────────────────────────────────────────────────
    def _pawn_moves(self, s: int, color: int) -> List[Move]:
        moves = []
        r, f        = rank_of(s), file_of(s)
        direction   = 1 if color == WHITE else -1
        start_rank  = 1 if color == WHITE else 6
        promo_rank  = 6 if color == WHITE else 1

        # Single push.
        nr = r + direction
        if 0 <= nr <= 7 and self.squares[sq(nr, f)] == EMPTY:
            if r == promo_rank:
                for promo in [QUEEN, ROOK, BISHOP, KNIGHT]:
                    moves.append(Move(s, sq(nr, f), promotion=promo))
            else:
                moves.append(Move(s, sq(nr, f)))
                # Double push from the starting rank if path is clear.
                if r == start_rank and self.squares[sq(nr + direction, f)] == EMPTY:
                    moves.append(Move(s, sq(nr + direction, f)))

        # Diagonal captures and en passant captures.
        for df in (-1, 1):
            nf = f + df
            if 0 <= nf <= 7 and 0 <= nr <= 7:
                target = self.squares[sq(nr, nf)]
                if target != EMPTY and (target > 0) != (color > 0):
                    dest = sq(nr, nf)
                    if r == promo_rank:
                        for promo in [QUEEN, ROOK, BISHOP, KNIGHT]:
                            moves.append(Move(s, dest, promotion=promo))
                    else:
                        moves.append(Move(s, dest))
                # En passant capture target.
                if self.en_passant_sq == sq(nr, nf):
                    moves.append(Move(s, sq(nr, nf), is_en_passant=True))
        return moves

    # ── Knight ───────────────────────────────────────────────────────────────
    def _knight_moves(self, s: int, color: int) -> List[Move]:
        moves = []
        r, f = rank_of(s), file_of(s)
        for dr, df in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            nr, nf = r + dr, f + df
            if 0 <= nr <= 7 and 0 <= nf <= 7:
                t = self.squares[sq(nr, nf)]
                if t == EMPTY or (t > 0) != (color > 0):
                    moves.append(Move(s, sq(nr, nf)))
        return moves

    # ── Sliders (bishop / rook / queen) ──────────────────────────────────────
    def _slider_moves(self, s: int, color: int, directions) -> List[Move]:
        moves = []
        r, f = rank_of(s), file_of(s)
        for dr, df in directions:
            nr, nf = r + dr, f + df
            while 0 <= nr <= 7 and 0 <= nf <= 7:
                t = self.squares[sq(nr, nf)]
                if t == EMPTY:
                    moves.append(Move(s, sq(nr, nf)))
                elif (t > 0) != (color > 0):
                    moves.append(Move(s, sq(nr, nf)))
                    break
                else:
                    break
                nr += dr; nf += df
        return moves

    # ── King ─────────────────────────────────────────────────────────────────
    def _king_moves(self, s: int, color: int) -> List[Move]:
        """
        Generate pseudo-legal king moves.

        Castling checks here are intentionally minimal: rights + empty squares.
        Attack-related castling checks (in-check and transit attack) are handled
        in `legal_moves()`.
        """
        moves = []
        r, f = rank_of(s), file_of(s)

        # Normal king moves (8 directions).
        for dr, df in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            nr, nf = r + dr, f + df
            if 0 <= nr <= 7 and 0 <= nf <= 7:
                t = self.squares[sq(nr, nf)]
                if t == EMPTY or (t > 0) != (color > 0):
                    moves.append(Move(s, sq(nr, nf)))

        # Pseudo-legal castling: check rights and empty path squares only.
        back_rank = 0 if color == WHITE else 7
        king_sq   = sq(back_rank, 4)
        if s == king_sq:
            ks = "K" if color == WHITE else "k"
            qs = "Q" if color == WHITE else "q"
            # Kingside castling.
            if (self.castling.get(ks)
                    and self.squares[sq(back_rank, 5)] == EMPTY
                    and self.squares[sq(back_rank, 6)] == EMPTY):
                moves.append(Move(s, sq(back_rank, 6), is_castle=True))
            # Queenside castling.
            if (self.castling.get(qs)
                    and self.squares[sq(back_rank, 3)] == EMPTY
                    and self.squares[sq(back_rank, 2)] == EMPTY
                    and self.squares[sq(back_rank, 1)] == EMPTY):
                moves.append(Move(s, sq(back_rank, 2), is_castle=True))
        return moves

    # ── Apply / Undo move ────────────────────────────────────────────────────
    def _apply(self, move: Move):
        """Apply a move in place without cloning the full board."""
        from_sq, to_sq = move.from_sq, move.to_sq
        piece = self.squares[from_sq]
        captured = self.squares[to_sq]
        
        # 1) Save minimal state required to undo the move.
        state = {
            "captured": captured,
            "castling": dict(self.castling),
            "en_passant_sq": self.en_passant_sq,
            "halfmove_clock": self.halfmove_clock,
            "fullmove": self.fullmove,
            "move": move
        }
        self._history.append(state)

        # 2) Handle en passant capture bookkeeping.
        if move.is_en_passant:
            # Captured pawn is behind destination square, not on `to_sq`.
            r_from, f_to = move.from_sq >> 3, move.to_sq & 7
            ep_cap_idx = (r_from << 3) | f_to
            state["captured"] = self.squares[ep_cap_idx] # Store actual captured pawn.
            self.squares[ep_cap_idx] = EMPTY

        # 3) Update en passant square for the next ply.
        if abs(piece) == PAWN and abs((to_sq >> 3) - (from_sq >> 3)) == 2:
            self.en_passant_sq = (from_sq + to_sq) // 2
        else:
            self.en_passant_sq = None

        # 4) Move rook when castling.
        if move.is_castle:
            back_rank = 0 if piece > 0 else 7
            if (to_sq & 7) == 6: # Kingside
                self.squares[(back_rank << 3) | 5] = self.squares[(back_rank << 3) | 7]
                self.squares[(back_rank << 3) | 7] = EMPTY
            else: # Queenside
                self.squares[(back_rank << 3) | 3] = self.squares[(back_rank << 3) | 0]
                self.squares[(back_rank << 3) | 0] = EMPTY

        # 5) Update castling rights after king/rook movement.
        pt = abs(piece)
        if pt == KING:
            if piece > 0: self.castling["K"] = self.castling["Q"] = False
            else:          self.castling["k"] = self.castling["q"] = False
        elif pt == ROOK:
            if from_sq == 0: self.castling["Q"] = False
            elif from_sq == 7: self.castling["K"] = False
            elif from_sq == 56: self.castling["q"] = False
            elif from_sq == 63: self.castling["k"] = False

        # 6) Move the piece.
        self.squares[to_sq] = piece
        self.squares[from_sq] = EMPTY

        # 7) Apply promotion.
        if move.promotion != EMPTY:
            self.squares[to_sq] = move.promotion * (1 if piece > 0 else -1)

        # 8) Update halfmove/fullmove counters and side to move.
        if pt == PAWN or captured != EMPTY or move.is_en_passant:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        if self.turn == BLACK: self.fullmove += 1
        self.turn = -self.turn

    def pop(self):
        """Undo the most recent move (supports both normal and null moves)."""
        if not self._history:
            return
        
        state = self._history.pop()
        move = state["move"] # May be `None` for a null move entry.
        
        # 1) Restore always-present state fields.
        self.turn = -self.turn
        if self.turn == BLACK:
            self.fullmove -= 1
        
        self.castling = state["castling"]
        self.en_passant_sq = state["en_passant_sq"]
        self.halfmove_clock = state["halfmove_clock"]
        
        # 2) Null move: stop here because no pieces were moved.
        if move is None:
            return

        # 3) Normal move: revert piece positions.
        piece = self.squares[move.to_sq]
        
        # If the move was a promotion, revert promoted piece back to pawn.
        if move.promotion != EMPTY:
            piece = (1 if piece > 0 else -1) * PAWN
            
        self.squares[move.from_sq] = piece
        self.squares[move.to_sq] = state["captured"]
        
        # Revert en passant capture.
        if move.is_en_passant:
            self.squares[move.to_sq] = EMPTY
            r_from, f_to = move.from_sq >> 3, move.to_sq & 7
            self.squares[(r_from << 3) | f_to] = state["captured"]

        # Revert castling rook movement.
        if move.is_castle:
            back_rank = 0 if piece > 0 else 7
            if (move.to_sq & 7) == 6: # Kingside
                self.squares[(back_rank << 3) | 7] = self.squares[(back_rank << 3) | 5]
                self.squares[(back_rank << 3) | 5] = EMPTY
            else: # Queenside
                self.squares[(back_rank << 3) | 0] = self.squares[(back_rank << 3) | 3]
                self.squares[(back_rank << 3) | 3] = EMPTY
    def push(self, move: Move):
        """Apply a move in place; call `pop()` to undo it."""
        self._apply(move)

    def push_null(self):
        """
        Apply a null move (pass turn without moving a piece), typically used in
        null-move pruning.

        `fullmove` is incremented before turn flip when Black is to move, which
        keeps behavior consistent with `_apply`.
        """
        state = {
            "squares":        list(self.squares),
            "turn":           self.turn,
            "castling":       dict(self.castling),
            "en_passant_sq":  self.en_passant_sq,
            "halfmove_clock": self.halfmove_clock,
            "fullmove":       self.fullmove,
            "move":           None,
        }
        self._history.append(state)

        # Keep fullmove update order consistent with regular move application.
        if self.turn == BLACK:
            self.fullmove += 1
        self.turn          = -self.turn
        self.en_passant_sq = None

    def is_tactical(self, move: Move) -> bool:
        """
        Params:
            move: Move
        Returns:
            bool
        Use case:
            Used in rollout policy to prioritize strong moves
        """
        return (
            move.is_en_passant or
            self.squares[move.to_sq] != EMPTY or
            move.promotion != EMPTY
        )
    
    # ── Attack / Check detection ─────────────────────────────────────────────
    def _sq_attacked(self, target: int, by_color: int) -> bool:
        """
        Return whether `target` is attacked by any piece of `by_color`.

        Pawn attack lookup is done from the target square backward to potential
        pawn origins:
        - White pawns attack from one rank above target: `(r + 1, f±1)`.
        - Black pawns attack from one rank below target: `(r - 1, f±1)`.
        """
        r, f = rank_of(target), file_of(target)

        # White pawn sources are above target; Black pawn sources are below.
        direction = 1 if by_color == WHITE else -1

        # Pawns
        nr = r + direction
        for df in (-1, 1):
            nf = f + df
            if 0 <= nr <= 7 and 0 <= nf <= 7:
                if self.squares[sq(nr, nf)] == by_color * PAWN:
                    return True

        # Knights
        for dr, df in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            nr, nf = r + dr, f + df
            if 0 <= nr <= 7 and 0 <= nf <= 7:
                if self.squares[sq(nr, nf)] == by_color * KNIGHT:
                    return True

        # Bishops / queens on diagonals.
        for dr, df in [(1,1),(1,-1),(-1,1),(-1,-1)]:
            nr, nf = r + dr, f + df
            while 0 <= nr <= 7 and 0 <= nf <= 7:
                p = self.squares[sq(nr, nf)]
                if p != EMPTY:
                    if p == by_color * BISHOP or p == by_color * QUEEN:
                        return True
                    break
                nr += dr; nf += df

        # Rooks / queens on ranks and files.
        for dr, df in [(1,0),(-1,0),(0,1),(0,-1)]:
            nr, nf = r + dr, f + df
            while 0 <= nr <= 7 and 0 <= nf <= 7:
                p = self.squares[sq(nr, nf)]
                if p != EMPTY:
                    if p == by_color * ROOK or p == by_color * QUEEN:
                        return True
                    break
                nr += dr; nf += df

        # King (adjacent squares).
        for dr, df in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
            nr, nf = r + dr, f + df
            if 0 <= nr <= 7 and 0 <= nf <= 7:
                if self.squares[sq(nr, nf)] == by_color * KING:
                    return True

        return False

    def king_square(self, color: int) -> Optional[int]:
        target = color * KING
        for i, p in enumerate(self.squares):
            if p == target:
                return i
        return None

    def is_in_check(self, color: int) -> bool:
        ks = self.king_square(color)
        return ks is not None and self._sq_attacked(ks, -color)

    def in_check(self) -> bool:
        """Return whether the side to move is currently in check."""
        return self.is_in_check(self.turn)

    def is_capture(self, move: Move) -> bool:
        """Return whether a move is a capture (including en passant)."""
        return move.is_en_passant or self.squares[move.to_sq] != EMPTY

    # ── Game status ──────────────────────────────────────────────────────────
    def status(self) -> str:
        """Return one of: 'playing' | 'checkmate' | 'stalemate' | 'draw'."""
        # Fifty-move rule (100 half-moves).
        if self.halfmove_clock >= 100:
            return "draw"

        # Materialize generator-like output once to check emptiness reliably.
        moves = list(self.legal_moves()) 
        
        if len(moves) == 0:
            if self.in_check():
                return "checkmate"
            else:
                return "stalemate"
        
        return "playing"
    def winner(self) -> Optional[int]:
        """Return winning side (WHITE/BLACK), or None if game not finished."""
        if self.status() == "checkmate":
            return -self.turn   # The side that just moved delivered checkmate.
        return None

    # ── Zobrist hash ─────────────────────────────────────────────────────────
    def zobrist_hash(self) -> int:
        h = 0
        for i, piece in enumerate(self.squares):
            if piece != EMPTY:
                piece_idx = piece + 6   # Maps -6..6 to index range 0..12.
                h ^= ZOBRIST_TABLE[i][piece_idx]
        if self.turn == BLACK:
            h ^= ZOBRIST_TURN
        return h

    # ── Debug ────────────────────────────────────────────────────────────────
    def __str__(self) -> str:
        rows = []
        for r in range(7, -1, -1):
            row = f"{r+1} "
            for f in range(8):
                row += PIECE_SYMBOLS[self.squares[sq(r, f)]] + " "
            rows.append(row)
        rows.append("  a b c d e f g h")
        turn_str = "White" if self.turn == WHITE else "Black"
        rows.append(f"Turn: {turn_str}")
        return "\n".join(rows)