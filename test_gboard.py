import sys
import os

from PyQt5.QtWidgets import QApplication, QMainWindow
from gchessboard.src.board import BoardView
import chess

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.board_view = BoardView()
        self.setCentralWidget(self.board_view)
        
        # Test basic config
        self.board_view.set(fen=chess.STARTING_FEN)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = TestWindow()
    w.show()
    print("GChessBoard initialized successfully")
