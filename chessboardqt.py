import sys
from typing import Literal

from PyQt5 import QtCore, QtGui, QtWidgets


class Square(QtWidgets.QWidget):
    def __init__(self, parent, color: str, image: str, text: str):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.image = QtGui.QImage(image)
        self.color = color
        self.box = QtWidgets.QWidget()
        self.box.setStyleSheet("background-color:red;border:1px solid black")
        self.box.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.boxlayout = QtWidgets.QGridLayout()
        self.boxlayout.setContentsMargins(0, 0, 0, 0)
        self.boxlayout.setSpacing(0)
        self.label = QtWidgets.QLabel()
        self.boxlayout.addWidget(self.label)
        self.setStyleSheet(f"background-color:{color};border:1px solid black")
        self.label.setText(text)
        self.label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        # self.label.setPixmap(QtGui.QPixmap(self.image.scaled(10,10)))
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        #self.layout.addWidget(self.label)
        self.layout.addWidget(self.box)
        self.setFixedSize(100, 100)

    def mouseMoveEvent(self, event):

        drag = QtGui.QDrag(self)
        mime_data = QtCore.QMimeData()
        mime_data.setText("")
        drag.setMimeData(mime_data)
        pixmap = QtGui.QPixmap(self.image.scaled(10, 10))
        drag.setPixmap(pixmap)
        drag.exec(QtCore.Qt.MoveAction)

    def dragEnterEvent(self, event):
        event.accept()

    def dropEvent(self, event: QtGui.QDropEvent):
        src = event.source().image
        self.label.setText(event.source().label.text())
        print("dropping")
        event.accept()

    def mousePressEvent(self, a0:QtGui.QMouseEvent) -> None:
        super().mousePressEvent(a0)
        self.box.move(200, 200)

    # def resize(self):
    # self.adjustSize()


class ChessBoard(QtWidgets.QWidget):
    def __init__(self, parent, side: Literal["white", "black"]):
        super().__init__(parent)
        self.boxlayout = QtWidgets.QGridLayout()
        self.boxlayout.setContentsMargins(0, 0, 0, 0)
        # self.layout.setRowStretch(1, 1)
        self.boxlayout.setSpacing(0)
        self.setLayout(self.boxlayout)
        # self.setFixedSize(700, 700)
        self.create_board()

    def create_board(self):
        for square in range(64):
            row = square % 8
            col = square // 8
            color = "#faf0e6" if ((row + col) % 2) == 0 else "#987456"
            sq = Square(self, color, "/storage/emulated/0/pie.png", f"{row}-{col}")
            # sq.setFixedHeight(440/8)
            # sq.setFixedWidth(440/8)
            self.boxlayout.addWidget(sq, row, col)
        for i in range(8):
            self.boxlayout.setRowStretch(i, 1)  # Make rows stretchable
            self.boxlayout.setColumnStretch(i, 1)  #

    # def resize(self):
    # pass


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.container = QtWidgets.QWidget()
        self.container.setContentsMargins(0, 0, 0, 0)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)
        self.board = ChessBoard(self, "white")
        self.layout.addWidget(self.board)


app = QtWidgets.QApplication(sys.argv)
window = Window()
window.show()
app.exec()
