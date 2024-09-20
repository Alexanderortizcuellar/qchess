from PyQt5 import QtWidgets, QtGui
from board import ChessBoard
from dialogs.promotion import PromotionDlg
import sys


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setGeometry(100, 100, 600, 600)
        self.setWindowTitle("Chess Board")
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
        self.coords = QtWidgets.QLineEdit(self)
        self.btn.clicked.connect(lambda: self.board.move_glide(*self.coords.text().split(",")))
        self.fwd = QtWidgets.QPushButton("e2e4")
        self.fwd.clicked.connect(lambda: self.board.move_glide("e2", "e4"))
        self.back = QtWidgets.QPushButton("e4e2")
        self.back.clicked.connect(lambda: self.board.move_glide("e4", "e2"))
        self.boxlayout.addWidget(self.fwd)
        self.boxlayout.addWidget(self.back)
        self.boxlayout.addWidget(self.btn)
        self.boxlayout.addWidget(self.coords)
    
        
    def show_promotion_dialog(self):
        dlg = PromotionDlg(self)
        dlg.show()

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
