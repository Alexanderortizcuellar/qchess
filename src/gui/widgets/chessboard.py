import chess
from PyQt5 import QtCore, QtWidgets
from gchessboard.src.board import BoardView
from gchessboard.src.promotion import PromotionDialog

class ChessBoard(QtWidgets.QWidget):
    """
    Wrapper for GChessBoard to maintain compatibility with the app.
    """
    ReadyForNextMove = QtCore.pyqtSignal(str)
    GameOver = QtCore.pyqtSignal()
    fenChanged = QtCore.pyqtSignal(str)
    moveMade = QtCore.pyqtSignal(str)

    def __init__(self, parent=None, fen=chess.STARTING_FEN, size=500):
        super().__init__(parent)
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.board_view = BoardView(self)
        self.board_view.setStyleSheet("border: none; background: transparent;")
        self.main_layout.addWidget(self.board_view)
        
        self._internal_board = chess.Board(fen)
        self._interactive = True
        self._user_color = None # For online play, set to player's color to enable premoves
        self.dragging = False # Compatibility property
        
        # Connect signals
        self.board_view.moveMade.connect(self._on_move_made)
        
        if size:
            self.setMinimumSize(300, 300)
            self.resize(size, size)
        self.set_fen(fen)

    def _update_view(self, last_move: chess.Move = None):
        """Syncs the BoardView with the internal board state."""
        dests = {}
        for move in self._internal_board.legal_moves:
            if move.from_square not in dests:
                dests[move.from_square] = []
            dests[move.from_square].append(move.to_square)

        # For online play, movable color should be the user's color 
        # to allow BoardView to handle premoves when it's NOT the user's turn.
        movable_color = self._user_color if self._user_color is not None else self._internal_board.turn

        self.board_view.set(
            fen=self._internal_board.fen(),
            lastMove=last_move,
            movable={
                'dests': dests,
                'color': movable_color
            }
        )

    def _on_move_made(self, move: chess.Move):
        # Handle promotion if needed
        piece = self._internal_board.piece_at(move.from_square)
        if piece and piece.piece_type == chess.PAWN:
            if (chess.square_rank(move.to_square) == 7 and piece.color == chess.WHITE) or \
               (chess.square_rank(move.to_square) == 0 and piece.color == chess.BLACK):
                
                # Show dialog to let the user choose.
                dialog = PromotionDialog(piece.color, self)
                self._selected_promo = chess.QUEEN
                def set_promo(t): self._selected_promo = t
                dialog.pieceSelected.connect(set_promo)
                dialog.exec_()
                move.promotion = self._selected_promo

        uci = move.uci()
        if move in self._internal_board.legal_moves:
            self._internal_board.push(move)
            # Critical: Update the view with the new FEN and highlight
            self._update_view(last_move=move)
            
            self.moveMade.emit(uci)
            self.fenChanged.emit(self._internal_board.fen())
            self.ReadyForNextMove.emit(self._internal_board.fen())
            
            if self._internal_board.is_game_over():
                self.GameOver.emit()
        else:
            # Revert board view if illegal
            self._update_view()

    def set_fen(self, fen: str):
        try:
            self._internal_board.set_fen(fen)
            self._update_view()
        except Exception as e:
            print(f"Error setting FEN: {e}")

    def fen(self):
        return self._internal_board.fen()

    @property
    def turn(self):
        return self._internal_board.turn

    @property
    def side(self):
        # Compatibility with old 'side' (orientation)
        return self.board_view._state.orientation

    @side.setter
    def side(self, value):
        self.board_view.set(orientation=value)

    @property
    def user_color(self):
        return self._user_color

    @user_color.setter
    def user_color(self, value):
        self._user_color = value
        self._update_view()

    @property
    def interactive(self):
        return self._interactive

    @interactive.setter
    def interactive(self, value):
        self._interactive = value
        self.board_view.set(viewOnly=not value)

    def set_premoves_enabled(self, enabled: bool):
        self.board_view.set(premovable={'enabled': enabled})

    def set_theme(self, theme_name_or_dict):
        themes = {
            "classic": {"light": "#dee3e6", "dark": "#8ca2ad"},
            "lichess": {"light": "#f0d9b5", "dark": "#b58863"},
            "chess.com": {"light": "#eeeed2", "dark": "#769656"},
            "blue": {"light": "#ebecd0", "dark": "#779bb0"},
            "wood": {"light": "#dec29b", "dark": "#966f33"},
        }
        if isinstance(theme_name_or_dict, str):
            theme = themes.get(theme_name_or_dict.lower(), themes["classic"])
        else:
            theme = theme_name_or_dict
        
        self.board_view.set(theme=theme)

    def flip(self):
        new_orientation = chess.BLACK if self.side == chess.WHITE else chess.WHITE
        self.side = new_orientation

    def update_board(self, fen: str, last_move: chess.Move = None):
        self._internal_board.set_fen(fen)
        self._update_view(last_move=last_move)
        # Match old board behavior: emit fenChanged
        self.fenChanged.emit(fen)

    def restart_board(self):
        self._internal_board.reset()
        self._update_view()
        self.ReadyForNextMove.emit(self.fen())
        self.fenChanged.emit(self.fen())

    def clear_board(self):
        self.set_fen("8/8/8/8/8/8/8/8 w - - 0 1")
        self.ReadyForNextMove.emit(self.fen())
        self.fenChanged.emit(self.fen())

