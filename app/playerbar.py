from PyQt5 import QtWidgets, QtCore, QtGui
from app.clock.clock import Clock



class PlayerBar(QtWidgets.QWidget):
    def __init__(self, parent=None, color="white"):
        super().__init__(parent)
        self.setMaximumHeight(66)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.profile = QtWidgets.QLabel()
        img = QtGui.QPixmap("images/profile.png").scaled(50, 50, QtCore.Qt.KeepAspectRatio)
        self.profile.setPixmap(img)
        self.info_frame = QtWidgets.QFrame()
        self.info_layout = QtWidgets.QVBoxLayout()
        self.info_frame.setLayout(self.info_layout)
        self.name = QtWidgets.QLabel("Player 1")
        self.name.setFont(QtGui.QFont("Times", 10, weight=QtGui.QFont.Bold))
        self.score = QtWidgets.QLabel("+2")
        spacer = QtWidgets.QSpacerItem(40, 40, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.clock = Clock(self, color)
        self.info_layout.addWidget(self.name)
        self.info_layout.addWidget(self.score)
        self.layout.addWidget(self.profile)
        self.layout.addWidget(self.info_frame)
        self.layout.addSpacerItem(spacer)
        self.layout.addWidget(self.clock)

