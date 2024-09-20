from PyQt5 import QtGui, QtCore
from pathlib import Path


path = "images/pieces/2048/"

pieces = {
    "a8": f"{path}bR.png",
    "b8": f"{path}bN.png",
    "c8": f"{path}bB.png",
    "d8": f"{path}bQ.png",
    "e8": f"{path}bK.png",
    "f8": f"{path}bB.png",
    "g8": f"{path}bN.png",
    "h8": f"{path}bR.png",
    "a7": f"{path}bP.png",
    "b7": f"{path}bP.png",
    "c7": f"{path}bP.png",
    "d7": f"{path}bP.png",
    "e7": f"{path}bP.png",
    "f7": f"{path}bP.png",
    "g7": f"{path}bP.png",
    "h7": f"{path}bP.png",
    "a1": f"{path}wR.png",
    "b1": f"{path}wN.png",
    "c1": f"{path}wB.png",
    "d1": f"{path}wQ.png",
    "e1": f"{path}wK.png",
    "f1": f"{path}wB.png",
    "g1": f"{path}wN.png",
    "h1": f"{path}wR.png",
    "a2": f"{path}wP.png",
    "b2": f"{path}wP.png",
    "c2": f"{path}wP.png",
    "d2": f"{path}wP.png",
    "e2": f"{path}wP.png",
    "f2": f"{path}wP.png",
    "g2": f"{path}wP.png",
    "h2": f"{path}wP.png",
    "empty": "",
}


pieces_info = {
    "P": f"{path}wP.png",
    "Q": f"{path}wQ.png",
    "K": f"{path}wK.png",
    "N": f"{path}wN.png",
    "R": f"{path}wR.png",
    "B": f"{path}wB.png",
    "p": f"{path}bP.png",
    "q": f"{path}bQ.png",
    "k": f"{path}bK.png",
    "n": f"{path}bN.png",
    "r": f"{path}bR.png",
    "b": f"{path}bB.png",
}


class Piece(QtCore.QObject):
    def __init__(self, parent, filename):
        super().__init__(parent)
        self.filename = filename
        self.parent = parent
        self.color = ""
        self.pixmap = QtGui.QPixmap(filename)
        self.name = self.parse_name(filename)

    def parse_name(self, filename: str):
        if filename == "":
            return ""
        name = Path(filename).stem
        if name.startswith("w"):
            self.color = "white"
            return name[1:].upper()
        self.color = "black"
        return name[1:].lower()


class Knight(Piece):
    def __init__(self, parent, filename):
        super().__init__(parent, filename)


class Pawn(Piece):
    def __init__(self, parent, filename):
        super().__init__(parent, filename)


class Queen(Piece):
    def __init__(self, parent, filename):
        super().__init__(parent, filename)


class Bishop(Piece):
    def __init__(self, parent, filename):
        super().__init__(parent, filename)


class Rook(Piece):
    def __init__(self, parent, filename):
        super().__init__(parent, filename)


class King(Piece):
    def __init__(self, parent, filename):
        super().__init__(parent, filename)
