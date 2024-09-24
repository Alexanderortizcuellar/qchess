from PyQt5 import QtWidgets, QtGui
from board import ChessBoard
from app.menu import ChessMenu
import sys
from server.chess.client import ChessClient


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
        self.board = ChessBoard(self, (600, 600))
        self.board.moveMade.connect(self.send_move)
        self.boxlayout.addWidget(self.board)
        self.btn = QtWidgets.QPushButton(self)
        self.btn.setText("Click me")
        self.btn.clicked.connect(self.make_castling_move)
        self.boxlayout.addWidget(self.btn)
        self.client = ChessClient(self)
        self.client.move_received.connect(self.board.make_move)
        self.connect_btn = QtWidgets.QPushButton("Connect")
        self.join_btn = QtWidgets.QPushButton("join")
        self.connect_btn.clicked.connect(self.client.start)
        self.join_btn.clicked.connect(self.join)
        self.boxlayout.addWidget(self.connect_btn)
        self.boxlayout.addWidget(self.join_btn)
        """ test with label """
        self.label = QtWidgets.QLabel("", self)
        self.label.setStyleSheet("background-color: green; color: white;border: 1px solid transparent;border-radius: 15px;")
        self.label.setFixedSize(30, 30)
        #self.label.move()

    def join(self):
        self.client.join()

    def make_castling_move(self):
        self.board.set_position("e1")

    def about(self):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.setText("This is an example of a simple message box")
        msg.setWindowTitle("About")
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec()

    def send_move(self, move: str):
        self.client.send_move(move)

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

