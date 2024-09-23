from PyQt5 import QtGui, QtWidgets, QtCore
from classic import Classic
from square import Square
from pieces import Piece, pieces
from consts import settings


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

    def __init__(self, parent, size=(800, 800), settings=settings):
        super().__init__(parent)
        self.setObjectName("chessboard")
        self.boxlayout = QtWidgets.QGridLayout()
        self.setLayout(self.boxlayout)
        self.boxlayout.setContentsMargins(0, 0, 0, 0)
        self.boxlayout.setSpacing(0)
        size = size
        self.resize(*size)
        self.setMaximumSize(*size)
        self.logic = Classic(self)
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
            sq = Square(self, color, self.logic)
            sq.setObjectName(text)
            if pieces.get(text) is not None:
                piece = self.pieces.get(text)
                sq.label.setPixmap(piece.pixmap)
                sq.setPiece(piece)
            else:
                sq.piece = Piece(self, "")
            self.boxlayout.addWidget(sq, row, col)

    def move_glide(
        self, src_uci: str, dst_uci: str, promotion: str = "q", make_move: bool = True
    ):
        src = self.findChild(QtWidgets.QWidget, src_uci)
        dst = self.findChild(QtWidgets.QWidget, dst_uci)
        if make_move:
            if not self.logic.check_move(src, dst):
                return
            self.logic.make_move(src, dst, promotion)
        src.raise_()
        src_style = src.styleSheet()
        src_pos = src.pos()
        dst.setObjectName(src_uci)
        src.setObjectName(dst_uci)
        src.setStyleSheet("background-color:transparent")
        src.label.setStyleSheet("background-color:transparent")
        self.glide = QtCore.QPropertyAnimation(src, b"pos")
        src.setStyleSheet(dst.styleSheet())
        self.glide.setDuration(200)
        self.glide.setEndValue(dst.pos())
        self.glide.finished.connect(
            lambda: self.animation_end(dst, src_style, src_pos, src, loop)
        )
        self.glide.start()
        loop = QtCore.QEventLoop()
        loop.exec_()

    def animation_end(self, dst, src_style, src_pos, src, loop):
        dst.move(src_pos)
        dst.label.setPixmap(QtGui.QPixmap())
        src.setStyleSheet(dst.styleSheet())
        src.label.setStyleSheet(dst.styleSheet())
        dst.setStyleSheet(src_style)
        dst.label.setStyleSheet(src_style)
        loop.quit()

    def handle_castle(self, src_king, dst_king):
        src_king = self.findChild(QtWidgets.QWidget, src_king)
        dst_king = self.findChild(QtWidgets.QWidget, dst_king)
        moves = self.logic.rules.get_castle_moves(src_king, dst_king)[1]
        self.move_glide(src_king.objectName(), dst_king.objectName(), make_move=True)
        self.move_glide(moves[0], moves[1], make_move=False)

    def handle_en_passant(self, src_pawn, dst_pawn):
        src_pawn = self.findChild(QtWidgets.QWidget, src_pawn)
        dst_pawn = self.findChild(QtWidgets.QWidget, dst_pawn)
        moves = self.logic.rules.get_en_passant_moves(src_pawn, dst_pawn)
        self.move_glide(src_pawn.objectName(), dst_pawn.objectName(), make_move=True)
        enpassant = self.findChild(QtWidgets.QWidget, moves[1])
        enpassant.setPiece(Piece(self, ""))
        enpassant.label.setPixmap(QtGui.QPixmap())

    def set_position(self, position):
        self.boardChanged.emit(position)

    def check_move(self, src, dst):
        # check if is a valid move
        pass

    def make_enpassant(self):
        self.handle_en_passant("a5", "b6")

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        super().paintEvent(a0)
