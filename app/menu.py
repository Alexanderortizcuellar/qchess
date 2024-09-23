from PyQt5 import QtWidgets

class ChessMenu(QtWidgets.QMenuBar):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        # Menu file
        self.file = QtWidgets.QMenu("&File", self)
        self.exit = QtWidgets.QAction("Exit", self)
        self.exit.setShortcut("Ctrl+Q")
        self.exit.triggered.connect(self.parent.close)
        self.file.addAction(self.exit)
        # Menu board
        self.board = QtWidgets.QMenu("&Board")
        self.addMenu(self.file)
        self.addMenu(self.board)
        # Menu Game
        self.game = QtWidgets.QMenu("&Game")
        self.addMenu(self.game)
        
        # Menu help
        self.help = QtWidgets.QMenu("&Help")
        self.about = QtWidgets.QAction("About", self)
        self.about.triggered.connect(self.parent.about)
        self.help.addAction(self.about)
        self.addMenu(self.help)