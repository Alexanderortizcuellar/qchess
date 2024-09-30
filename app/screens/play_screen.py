from PyQt5 import QtWidgets, QtCore, QtGui


class PlayScreen(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget):
        super().__init__(parent)
        self.parent = parent
        self.setMouseTracking(True)
    