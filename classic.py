from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget
import chess
import chess.pgn
from rules import Rules


class Classic(QtCore.QObject):
    moveMade = QtCore.pyqtSignal(str)
    checkmated = QtCore.pyqtSignal(bool)
    board_changed = QtCore.pyqtSignal(str)
    checked = QtCore.pyqtSignal(bool)
    drawn = QtCore.pyqtSignal(bool)
    checked = QtCore.pyqtSignal(bool)
    stalemated = QtCore.pyqtSignal(bool)
    drawn = QtCore.pyqtSignal(str, str)
    moveMade = QtCore.pyqtSignal(str)
    turnChanged = QtCore.pyqtSignal(str)

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.rules = Rules(self)
        self.board = chess.Board()
        self.game = chess.pgn.Game()

    def check_move(self, src: QWidget, dst: QWidget, promotion="q") -> bool:
        """
        checks if a move is legal takes a uci move string
        """
        move_uci = src.objectName() + dst.objectName()
        move = chess.Move.from_uci(move_uci)
        print(self.get_pgn())
        if self.rules.check_promotion(src, dst):
            print("promotion in this move", move.uci())
            move = chess.Move.from_uci(move_uci + promotion)
        if self.board.is_legal(move):
            if self.is_checked():
                self.checked.emit(True)
            if self.board.is_checkmate():
                self.checkmated.emit(True)
            print("legal move", move.uci())
            return True
        print("illegal move", move.uci())
        return False

    def find_king(self) -> tuple[int, int]:
        color = 1 if self.board.turn else 0  # 1 white, 0 black
        index = self._find_piece("wK" if color == 1 else "bK")
        return (index[0], index[1])

    def _find_piece(self, piece: str) -> str:
        piece = "k" if piece == "bK" else "K"
        board = self._fen_to_list()
        print(board, "board")
        print(self.board.fen(), "fen")
        for row in range(8):
            for col in range(8):
                if board[row][col] == piece:
                    return (row, col)
        return None

    def _fen_to_list(self):
        board_list = []
        parts = self.board.fen().split(" ")[0]
        rows = parts.split("/")
        for row in rows:
            row_processed = []
            count = 0
            for char in row:
                if char.isdigit():
                    count = int(char)
                    for _ in range(count):
                        row_processed.append("")
                else:
                    row_processed.append(char)
                    count = 0
            board_list.append(row_processed)
        return board_list

    def check_turn(self):
        if self.board.turn:
            return "w"
        return "b"

    def get_legal_moves(self, src_uci: str):
        return [
            move.uci()
            for move in self.board.generate_legal_moves()
            if move.uci().startswith(src_uci)
        ]

    def is_checked(self):
        return self.board.is_check()

    def make_move(self, src: QWidget, dst: QWidget, promotion="q"):
        try:
            move_uci = src.objectName() + dst.objectName()
            move = chess.Move.from_uci(move_uci)
            print(self.rules.check_promotion(src, dst), "verifying promotion")
            if self.rules.check_promotion(src, dst):
                move = chess.Move.from_uci(move_uci + promotion.lower())
            self.board.push_uci(move.uci())
            node = self.game.end()
            node.add_main_variation(move)
            print("made move => " + move.uci())
            self.board_changed.emit(self.board.fen())
            self.moveMade.emit(move.uci())
            self.turnChanged.emit(self.check_turn())
            return True
        except Exception as e:
            print(e)
            return False

    def get_pgn(self) -> str:
        return str(self.game)

    def reset(self):
        self.board.reset()
