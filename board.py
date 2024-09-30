from PyQt5 import QtGui, QtWidgets, QtCore
from classic import Classic
from square import Square
from engine import QChessEngine
from pieces import Piece, pieces, pieces_info
from consts import settings, check_style
import chess


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
    turnChanged = QtCore.pyqtSignal(str)
    kingMoved = QtCore.pyqtSignal(str, str)

    def __init__(self, parent, size=(800, 800), settings=settings):
        """
        Args:
            parent: parent widget
            size: size of the board
            settings: settings dict
        Signals:
            boardChanged: (fen)
            dropped: (piece, position)
            dragged: (piece, position)
            promoted: (piece, position)
            castled: (piece, position)
            enpassant_ocurred: (piece, position)
            checked: (bool)
            checkmated: (bool)
            stalemated: (bool)
            drawn: (bool)
            moveMade: (uci: str)
            turnChanged: (bool)
            kingMoved: (src: str, dst: str)
        """
        super().__init__(parent)
        self.highlightCheck = True
        self.highlightLegalMoves = True
        self.positions_to_clear = []
        self.setObjectName("chessboard")
        self.boxlayout = QtWidgets.QVBoxLayout()
        self.setLayout(self.boxlayout)
        self.boxlayout.setContentsMargins(0, 0, 0, 0)
        self.boxlayout.setSpacing(0)
        self.resize(*size)
        self.setMaximumSize(*size)
        self.grid = QtWidgets.QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(0)
        self.box = QtWidgets.QWidget()
        self.box.setLayout(self.grid)
        self.boxlayout.addWidget(self.box)
        # logic and piece set up
        self.logic = Classic(self)
        self.logic.moveMade.connect(self._on_move_made)
        self.logic.checked.connect(self.checked.emit)
        self.logic.checkmated.connect(self.checkmated.emit)
        self.logic.drawn.connect(self.drawn.emit)
        self.logic.turnChanged.connect(self.turnChanged.emit)
        # engine
        self.engine = QChessEngine(self, "")
        self._init_pieces()
        self._create_board()

    def setEngine(self, engine: QChessEngine):
        self.engine = engine

    def setHighlightLegalMoves(self, state: bool = True):
        self.highlightLegalMoves = state

    def setHighlightCheck(self, state: bool = True):
        self.highlightCheck = state

    def _init_pieces(self):
        self.pieces = {key: Piece(self, value) for key, value in pieces.items()}

    def _on_drag_attempted(self, src: str):
        self._clear_higlight()
        if self.highlightLegalMoves:
            self._higlight_moves(src)

    def _on_dropped(self, src: str, dst: str):
        self._clear_higlight()

    def _on_clicked(self, src: str):
        self._clear_higlight()

    def _on_king_moved(self, src: str, dst: str):
        self.kingMoved.emit(src, dst)

    def _on_move_made(self, move: str):
        self._clear_check()
        self._highlight_check()
        self.moveMade.emit(move)

    def _create_board(self):
        letters = "abcdefgh"
        for square in range(64):
            row = square % 8
            col = square // 8
            color = "beige" if ((row + col) % 2 == 0) else "brown"
            text = f"{letters[col]}{8 - row}"
            sq = Square(self, color, self.logic)
            sq.pieceMovedAttempted.connect(self._on_drag_attempted)
            sq.pieceDropped.connect(self._on_dropped)
            sq.mousePressed.connect(self._on_clicked)
            sq.setObjectName(text)
            if pieces.get(text) is not None:
                piece = self.pieces.get(text)
                sq.label.setPixmap(piece.pixmap)
                sq.setPiece(piece)
            else:
                sq.piece = Piece(self, "")
            self.grid.addWidget(sq, row, col)

    def _move_glide(
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
        self.glide.setDuration(150)
        self.glide.setEndValue(dst.pos())
        self.glide.finished.connect(
            lambda: self._animation_end(dst, src_style, src_pos, src, loop)
        )
        self.glide.start()
        loop = QtCore.QEventLoop()
        loop.exec_()

    def _animation_end(
        self,
        dst: QtWidgets.QWidget,
        src_style: str,
        src_pos: QtCore.QPoint,
        src: QtWidgets.QWidget,
        loop: QtCore.QEventLoop,
    ):
        dst.move(src_pos)
        dst.label.setPixmap(QtGui.QPixmap())
        src.setStyleSheet(dst.styleSheet())
        src.label.setStyleSheet(dst.styleSheet())
        dst.setStyleSheet(src_style)
        dst.label.setStyleSheet(src_style)
        loop.quit()

    def _handle_castle(self, src_king: str, dst_king: str):
        src_king = self.findChild(QtWidgets.QWidget, src_king)
        dst_king = self.findChild(QtWidgets.QWidget, dst_king)
        moves = self.logic.rules.get_castle_moves(src_king, dst_king)[1]
        self._move_glide(src_king.objectName(), dst_king.objectName(), make_move=True)
        self._move_glide(moves[0], moves[1], make_move=False)

    def _handle_en_passant(self, src_pawn: str, dst_pawn: str):
        src_pawn = self.findChild(QtWidgets.QWidget, src_pawn)
        dst_pawn = self.findChild(QtWidgets.QWidget, dst_pawn)
        moves = self.logic.rules.get_en_passant_moves(src_pawn, dst_pawn)
        self._move_glide(src_pawn.objectName(), dst_pawn.objectName(), make_move=True)
        enpassant = self.findChild(QtWidgets.QWidget, moves[1])
        enpassant.setPiece(Piece(self, ""))
        enpassant.label.setPixmap(QtGui.QPixmap())

    def _handle_promotion(self, src_piece: str, dst_piece: str, promotion: str):
        src_sq: Square = self.findChild(QtWidgets.QWidget, src_piece)
        dst_sq: Square = self.findChild(QtWidgets.QWidget, dst_piece)
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

    def _set_position(self, position: str):
        e4 = self.findChild(QtWidgets.QWidget, "e4")
        print(e4.rect(), e4.pos())
        # self.label.move(QtCore.QPoint(e4.pos().x() + int(e4.width() / 2) - 15 , e4.pos().y() + int(e4.height() / 2) - 15))

    def make_move(self, uci: str):
        promotion = "q"
        src = uci[0:2]
        target = uci[2:4]
        if len(uci) > 4:
            promotion = uci[4]
        src_sq: Square = self.findChild(QtWidgets.QWidget, src)
        target_sq: Square = self.findChild(QtWidgets.QWidget, target)
        if self.logic.check_move(src_sq, target_sq):
            if self.logic.rules.check_en_passant(src_sq, target_sq):
                self._handle_en_passant(src, target)
                return
            if self.logic.rules.check_castle(src_sq, target_sq):
                self._handle_castle(src, target)
                return
            if self.logic.rules.check_promotion(src_sq, target_sq):
                self._handle_promotion(src, target, promotion)
            self._move_glide(src, target, promotion=promotion)

    def flip(self, white: bool = True) -> None:
        for row in range(8):
            for col in range(8):
                widget = self.grid.itemAtPosition(row, col).widget().deleteLater()
                self.grid

    def to_fen(self):
        squares = []
        for row in range(8):
            count = 0
            for col in range(8):
                piece: Square = self.grid.itemAtPosition(row, col).widget()
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
                    count = int(char)
                    if count > 0:
                        for _ in range(count):
                            row_processed.append("")
                else:
                    row_processed.append(char)
                    count = 0
            
            board.append(row_processed)
        return board

    def _higlight_moves(self, src):
        legal_moves = self.logic.get_legal_moves(src)
        print(legal_moves)
        for move in legal_moves:
            widget = self.findChild(QtWidgets.QWidget, move[2:4])
            label = QtWidgets.QLabel("", self)
            label.setObjectName("marker")
            label.raise_()
            label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            label.setStyleSheet(
                "background-color: rgba(160, 160, 160,0.7   ); color: white;border: 1px solid transparent;border-radius: 15px;"
            )
            label.setFixedSize(30, 30)
            label.show()
            position = QtCore.QPoint(
                widget.pos().x() + int(widget.width() / 2) - 15,
                widget.pos().y() + int(widget.height() / 2) - 15,
            )
            label.move(position)

    def _highlight_check(self):
        if self.highlightCheck:
            if self.logic.is_checked():
                king_index = self.logic.find_king()
                print(king_index)
                king = self.grid.itemAtPosition(king_index[0], king_index[1]).widget()
                print(king_index, king.objectName(), "check stuff", self.logic.find_king())
                self.positions_to_clear.append(king)
                king.label.setStyleSheet(king.label.styleSheet() + ";" + check_style)

    def _clear_higlight(self):
        labels = self.findChildren(QtWidgets.QLabel, "marker")
        for label in labels:
            label.destroy()
            label.deleteLater()

    def _clear_check(self):
        for position in self.positions_to_clear:
            print(position.label.styleSheet())
            position.label.setStyleSheet(
                position.label.styleSheet().replace(check_style, "")
            )

        self.positions_to_clear = []


    def reset(self):
        self._create_board()
        self.logic.reset()

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:
        super().paintEvent(a0)
