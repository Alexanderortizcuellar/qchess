from PyQt5 import QtGui, QtWidgets, QtCore
from square import Square
from pieces import Piece, pieces


class ChessBoard(QtWidgets.QWidget):
    boardChanged = QtCore.pyqtSignal(str)  # fen string
    onDrop = QtCore.pyqtSignal(str, str)
    onDrag = QtCore.pyqtSignal(str, str)
    onPromotion = QtCore.pyqtSignal(str, str)
    onCastling = QtCore.pyqtSignal(str, str)
    onEnPassant = QtCore.pyqtSignal(str, str)
    onCheck = QtCore.pyqtSignal(str, str)
    onCheckMate = QtCore.pyqtSignal(str, str)
    onStaleMate = QtCore.pyqtSignal(str, str)
    onDraw = QtCore.pyqtSignal(str, str)

    def __init__(self, parent, size=(800, 800)):
        super().__init__(parent)
        self.setObjectName("chessboard")
        self.boxlayout = QtWidgets.QGridLayout()
        self.setLayout(self.boxlayout)
        self.boxlayout.setContentsMargins(0, 0, 0, 0)
        self.boxlayout.setSpacing(0)
        size = size
        self.resize(*size)
        self.setMaximumSize(*size)
        self.init_pieces()
        self.create_board()

    def init_pieces(self):
        self.pieces = {key: Piece(self, value) for key, value in pieces.items()}

    def create_board(self):
        letters = "abcdefgh"
        for square in range(64):
            row = square % 8
            col = square // 8
            color = "beige" if ((row + col) % 2 == 0) else "brown"
            text = f"{letters[col]}{8 - row}"
            sq = Square(self, color)
            sq.setObjectName(text)
            if pieces.get(text) is not None:
                piece = self.pieces.get(text)
                sq.setPixmap(piece.pixmap)
                sq.setPiece(piece)
            else:
                sq.piece = Piece(self, "")
            self.boxlayout.addWidget(sq, row, col)

    def set_position(self, position):
        self.boardChanged.emit(position)
    
    def check_move(self, src, dst):
        # check if is a valid move
        pass

    def handle_castle(self, src, dst):
        pass

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:

        super().paintEvent(a0)
        painter = QtGui.QPainter(self)
        pen = QtGui.QPen()
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawRect(0, 0, self.width(), self.height())
        painter.end()
