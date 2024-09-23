from PyQt5 import QtWidgets, QtGui
from board import ChessBoard
from app.menu import ChessMenu
import sys


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 600, 600)
        self.setWindowTitle("Chess Board")
        self.setMenuBar(ChessMenu(self))
        self.setWindowIcon(QtGui.QIcon("images/icons/icon.png"))
        self.boxlayout = QtWidgets.QGridLayout()
        self.box = QtWidgets.QWidget()
        self.box.setLayout(self.boxlayout)
        self.box.setLayout(self.boxlayout)
        self.setCentralWidget(self.box)
        self.board = ChessBoard(self, (700, 700))
        self.boxlayout.addWidget(self.board)
        self.btn = QtWidgets.QPushButton(self)
        self.btn.setText("Click me")
        self.btn.clicked.connect(self.make_castling_move)
        self.boxlayout.addWidget(self.btn)

    def make_castling_move(self):
        self.board.make_enpassant()

    def about(self):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setText("This is an example of a simple message box")
        msg.setWindowTitle("About")
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec()

    def closeEvent(self, event):
        msg = QtWidgets.QMessageBox.question(
            self,
            "Close Window",
            "Are you sure?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )

        if msg == QtWidgets.QMessageBox.Yes:
            event.accept()
            self.deleteLater()
        event.ignore()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = Window()
    window.show()
    app.exec()
