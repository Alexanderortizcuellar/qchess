from PyQt5 import QtCore
from PyQt5.QtWidgets import QWidget
import chess
from rules import Rules


class Classic(QtCore.QObject):
    moveMade = QtCore.pyqtSignal(str)

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
        print(self.board)
        print(list(self.board.generate_legal_moves()))
        if self.rules.check_promotion(src, dst):
            print("promotion in this move", move.uci())
            move = chess.Move.from_uci(move_uci + promotion)
        if self.board.is_legal(move):
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

    def make_move(self, src, dst, promotion="q"):
        try:
            move_uci = src.objectName() + dst.objectName()
            move = chess.Move.from_uci(move_uci)
            if self.rules.check_promotion(src, dst):
                move = chess.Move.from_uci(move_uci + promotion)
            self.board.push_uci(move.uci())
            print("made move => " + move_uci)
            self.moveMade.emit(self.board.fen())
            return True
        except Exception:
            return False

    def reset(self):
        self.board.reset()
