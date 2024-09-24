from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget
import chess
from rules import Rules


class Classic(QtCore.QObject):
    moveMade = QtCore.pyqtSignal(str)
    checkmated = QtCore.pyqtSignal(bool)
    board_changed = QtCore.pyqtSignal(str)
    checked = QtCore.pyqtSignal(bool)
    drawn = QtCore.pyqtSignal(bool)

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.rules = Rules(self)
        self.board = chess.Board()

    def check_move(self, src: QWidget, dst: QWidget, promotion="q") -> bool:
        """
        checks if a move is legal takes a uci move string
        """
        move_uci = src.objectName() + dst.objectName()
        move = chess.Move.from_uci(move_uci)
        print(list(self.board.generate_legal_moves()))
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

    def check_turn(self):
        if self.board.turn:
            return "w"
        return "b"

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
            print("made move => " + move.uci())
            self.board_changed.emit(self.board.fen())
            self.moveMade.emit(move.uci())
            return True
        except Exception as e:
            print(e)
            return False

    def reset(self):
        self.board.reset()
