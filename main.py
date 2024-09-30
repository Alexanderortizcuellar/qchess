from PyQt5 import QtWidgets, QtGui, QtCore
from board import ChessBoard
from app.menubar import ChessMenu
from app.toolbar import ToolBar
import sys
from server.chess.client import ChessClient
from engine import QChessEngine
from app.playerbar import PlayerBar


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 600, 600)
        self.setWindowTitle("Chess Board")
        self.setMenuBar(ChessMenu(self))
        self.addToolBar(ToolBar(self))
        self.setWindowIcon(QtGui.QIcon("images/icons/icon.png"))
        self.boxlayout = QtWidgets.QVBoxLayout()
        self.board_frame = QtWidgets.QFrame()
        self.boardlayout = QtWidgets.QVBoxLayout()
        self.boardlayout.setContentsMargins(0, 5, 0, 0)
        self.boardlayout.setSpacing(0)
        # self.board_frame.setStyleSheet("background-color: indigo;")
        self.boxlayout.setContentsMargins(9, 0, 0, 0)
        self.board_frame.setLayout(self.boardlayout)
        self.box = QtWidgets.QWidget()
        self.box.setLayout(self.boxlayout)
        self.setCentralWidget(self.box)
        self.player_bar1 = PlayerBar(self, "black")
        self.boardlayout.addWidget(self.player_bar1)
        self.board = ChessBoard(self, (700, 700))
        self.board_frame.setMaximumWidth(self.board.size().width())
        self.board.turnChanged.connect(self.statusBar().showMessage)
        self.boardlayout.addWidget(self.board)
        self.player_bar = PlayerBar(self, "white")
        self.boardlayout.addWidget(self.player_bar)
        self.boxlayout.addWidget(self.board_frame)
        self.client = ChessClient(self, "ws://localhost:1234")
        self.client.move_received.connect(self.board.make_move)
 
        """ test with label """


    def reset_board(self):
        self.board.reset()

    def join(self):
        self.client.join()

    def make_castling_move(self):
        self.board.flip()

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
    app.setStyleSheet("QMainWindow {background-color: rgb(65, 65, 65);}")
    window = Window()
    window.show()
    app.exec()

