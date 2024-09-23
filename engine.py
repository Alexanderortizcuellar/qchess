from PyQt5 import QtCore, QtGui
import chess.engine



class QEngine(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = chess.engine.SimpleEngine.popen_uci("stockfish")
        self.engine.configure({"Threads": 2})

    def get_best_move(self, board):
        return self.engine.play(board, chess.engine.Limit(time=0.1)).move


class Engine(QtCore.QThread):
    moveMade = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.engine = QEngine()

    def run(self):
        self.engine.get_best_move(self.board)
