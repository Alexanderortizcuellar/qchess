from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt



class ToolBar(QtWidgets.QToolBar):
    def __init__(self, parent):
        super().__init__(parent)
        #self.setFloatable(False)
        self.setMovable(False)
        play_button = QtWidgets.QToolButton()
        play_button.setToolTip("Play a game")
        pixmap = QtGui.QPixmap(80, 80)
        pixmap.fill(QtGui.QColorConstants.DarkGray)
        icon = QtGui.QIcon(pixmap)
        play_button.setIcon(icon)
        self.addWidget(play_button)
        

        
