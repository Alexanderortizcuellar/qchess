from PyQt5 import QtWidgets
from board import ChessBoard
import sys


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 600, 600)
        self.setWindowTitle("Chess Board")
        self.boxlayout = QtWidgets.QGridLayout()
        self.box = QtWidgets.QWidget()
        self.box.setLayout(self.boxlayout)
        self.box.setLayout(self.boxlayout)
        self.setCentralWidget(self.box)
        self.board = ChessBoard(self, (700, 700))
        self.boxlayout.addWidget(self.board)
        self.btn = QtWidgets.QPushButton(self)
        self.btn.setText("Click me")
        self.btn.clicked.connect(self.board.create_board)
        self.boxlayout.addWidget(self.btn)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = Window()
    window.show()
    app.exec()
