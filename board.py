from PyQt5 import QtGui, QtWidgets, QtCore
from classic import Classic
from square import Square
from pieces import Piece, pieces, pieces_info
from consts import settings


class ChessBoard(QtWidgets.QWidget):
    boardChanged = QtCore.pyqtSignal(str)  # position fen
    dropped = QtCore.pyqtSignal(str, str)
    dragged = QtCore.pyqtSignal(str, str)
    promoted = QtCore.pyqtSignal(str, str)
    castled = QtCore.pyqtSignal(str, str)
    enpassant_ocurred = QtCore.pyqtSignal(str, str)
    checked = QtCore.pyqtSignal(bool)
    checkmated = QtCore.pyqtSignal(bool)
    stalemated = QtCore.pyqtSignal(bool)
    drawn = QtCore.pyqtSignal(str, str)
    moveMade = QtCore.pyqtSignal(str)

    def __init__(self, parent, size=(800, 800), settings=settings):
        super().__init__(parent)
        self.setObjectName("chessboard")
        self.boxlayout = QtWidgets.QGridLayout()
        self.setLayout(self.boxlayout)
        self.boxlayout.setContentsMargins(0, 0, 0, 0)
        self.boxlayout.setSpacing(0)
        self.resize(*size)
        self.setMaximumSize(*size)
        self.logic = Classic(self)
        self.logic.moveMade.connect(self.emit_move)
        self.logic.checked.connect(self.checked.emit)
        self.logic.checkmated.connect(self.checkmated.emit)
        self.logic.drawn.connect(self.drawn.emit)
        self.init_pieces()
        self.create_board()
        self.label = QtWidgets.QLabel("", self)
        self.label.setStyleSheet("background-color: green; color: white;border: 1px solid transparent;border-radius: 15px;")
        self.label.setFixedSize(30, 30)

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
        print(src.pos(), dst.pos())
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

    def handle_en_passant(self, src_pawn: str, dst_pawn: str):
        src_pawn = self.findChild(QtWidgets.QWidget, src_pawn)
        dst_pawn = self.findChild(QtWidgets.QWidget, dst_pawn)
        moves = self.logic.rules.get_en_passant_moves(src_pawn, dst_pawn)
        self.move_glide(src_pawn.objectName(), dst_pawn.objectName(), make_move=True)
        enpassant = self.findChild(QtWidgets.QWidget, moves[1])
        enpassant.setPiece(Piece(self, ""))
        enpassant.label.setPixmap(QtGui.QPixmap())

    def handle_promotion(self, src_piece: str, dst_piece: str, promotion: str):
        src_sq = self.findChild(QtWidgets.QWidget, src_piece)
        dst_sq = self.findChild(QtWidgets.QWidget, dst_piece)
        src_sq.label.setPixmap(QtGui.QPixmap())
        src_sq.setPiece(Piece(self, ""))
        dst_sq.label.setPixmap(QtGui.QPixmap(pieces_info[promotion]))
        dst_sq.setPiece(Piece(self, promotion))
        self.move_glide(
            src_sq.objectName(),
            dst_sq.objectName(),
            promotion=promotion,
            make_move=True,
        )

    def set_position(self, position: str):
        e4 = self.findChild(QtWidgets.QWidget, "e4")
        print(e4.rect(), e4.pos())
        self.label.move(QtCore.QPoint(e4.pos().x() + int(e4.width() / 2) - 15 , e4.pos().y() + int(e4.height() / 2) - 15))

    def make_move(self, uci: str):
        promotion = "q"
        src = uci[0:2]
        target = uci[2:4]
        if len(uci) > 4:
            promotion = uci[4]
        src_sq = self.findChild(QtWidgets.QWidget, src)
        target_sq = self.findChild(QtWidgets.QWidget, target)
        if self.logic.check_move(src_sq, target_sq):
            if self.logic.rules.check_en_passant(src_sq, target_sq):
                self.handle_en_passant(src, target)
                return
            if self.logic.rules.check_castle(src_sq, target_sq):
                self.handle_castle(src, target)
                return
            if self.logic.rules.check_promotion(src_sq, target_sq):
                self.handle_promotion(src, target, promotion)
            self.move_glide(src, target, promotion=promotion) 

    def flip(self, white: bool = True) -> None:
        pass

    def to_fen(self):
        squares = []
        for row in range(8):
            count = 0
            for col in range(8):
                piece = self.boxlayout.itemAtPosition(row, col).widget()
                if piece.piece.name == "":
                    count += 1
                else:
                    if count > 0:
                        squares.append(str(count))
                    squares.append(piece.piece.name)
                    count = 0
            if count > 0:
                squares.append(str(count))
            squares.append("/")
        return "".join(squares)

    def fen_to_board(self, fen: str):
        board = []
        parts = fen.split(" ")
        board_rows = parts[0].split("/")
        for row in board_rows:
            row_processed = []
            count = 0
            for char in row:
                if char.isdigit():
                    count += int(char)
                else:
                    row_processed.append(char)
                    count = 0
            if count > 0:
                for _ in range(count):
                    row_processed.append("")
            board.append(row_processed)
        return board

    def emit_move(self, move: str):
        self.moveMade.emit(move)

    def reset(self):
        self.create_board()
        self.logic.reset()

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        super().paintEvent(a0)
