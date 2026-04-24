import sys
import xml.etree.ElementTree as ET
from typing import Literal

import chess
import chess.svg
from PyQt5 import QtCore, QtGui, QtSvg, QtWidgets
from PyQt5.QtCore import Qt


class PieceCache:
    _cache = {}

    @classmethod
    def piece_to_pixmap(cls, piece: chess.Piece, size: int) -> QtGui.QPixmap:
        """Convert a chess piece to a cached QPixmap."""
        key = (piece.symbol(), size)
        if key in cls._cache:
            return cls._cache[key]

        # Generate SVG only once per piece type/size
        svg_data = chess.svg.piece(piece, size=size)
        renderer = QtSvg.QSvgRenderer(QtCore.QByteArray(svg_data.encode("utf-8")))

        pixmap = QtGui.QPixmap(size, size)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        cls._cache[key] = pixmap
        return pixmap


## support responsiveness
class ChessBoard(QtWidgets.QWidget, chess.Board):
    """
    An interactive chessboard that only allows legal moves.
    """

    ReadyForNextMove = QtCore.pyqtSignal(str)
    GameOver = QtCore.pyqtSignal()
    fenChanged = QtCore.pyqtSignal(str)
    moveMade = QtCore.pyqtSignal(str)

    def __init__(
        self,
        parent=None,
        fen=chess.Board().fen(),
        size=500,
    ):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.installEventFilter(self)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_fen(fen)
        self.side = chess.WHITE
        self.svg_xy = 10  # top left x, y-pos of chessboard
        self.board_size = size  # size of chessboard
        self.margin = (
            0.0 * self.board_size
        )  # should be 0.04 * self.board_size to work when drawing board with coords
        self.square_size = (self.board_size - 2 * self.margin) / 8.0
        wnd_wh = self.board_size + 2 * self.svg_xy

        self.setMinimumSize(wnd_wh, wnd_wh)
        self.svg_widget = QtSvg.QSvgWidget(parent=self)
        self.svg_widget.setGeometry(
            self.svg_xy, self.svg_xy, self.board_size, self.board_size
        )
        self.side = chess.WHITE
        self.last_click = None
        self.last_move = None
        self.animated_piece = QtSvg.QSvgWidget(self)
        self.animated_piece.setGeometry(
            0, 0, int(self.square_size), int(self.square_size)
        )
        self.animated_piece.setStyleSheet("background-color:transparent")
        self.animated_piece.hide()
        self._current_anim = None
        self.set_fen(fen)
        self.draw_board()

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        if self.check_area_clicked(event):
            this_click = self.get_clicked(event)
            self.draw_board(legal_moves=self.get_legal_moves(this_click))
            self._drag_start_pos = event.pos()
            if self.last_click:
                if self.last_click != this_click:
                    uci = self.last_click + this_click
                    self.apply_move(uci + self.get_promotion(uci))
            self.last_click = this_click

    def mouseMoveEvent(self, a0):
        try:
            current_square = chess.parse_square(self.get_clicked(a0.pos()))
            # piece_at_current_square = self.piece_at(current_square)
            if a0.buttons() & Qt.MouseButton.RightButton:
                print(current_square)

            # allow only to drag pieces included in legal moves
            if (
                current_square not in [move.from_square for move in self.legal_moves]
                or self.get_clicked(a0.pos()) != self.last_click
            ):
                a0.ignore()
            # start drag only if left button is pressed and drag start pos is set
            if a0.buttons() & Qt.MouseButton.LeftButton and self._drag_start_pos:
                dist = (a0.pos() - self._drag_start_pos).manhattanLength()
                if dist >= QtWidgets.QApplication.startDragDistance():
                    drag = QtGui.QDrag(self)
                    mime_data = QtCore.QMimeData()
                    mime_data.setText(
                        f"{self.get_clicked(a0.pos())},{self.piece_at(current_square).symbol()},{self.fen()}"
                    )
                    drag.setMimeData(mime_data)
                    current_piece = self.piece_at(current_square)
                    pixmap_icon = self.piece_to_pixmap(
                        current_piece, int(self.square_size)
                    )
                    drag.setPixmap(pixmap_icon)
                    drag.setHotSpot(pixmap_icon.rect().center())
                    # drag.setDragCursor(self.create_transparent_cursor(), Qt.MoveAction)
                    legal_moves = self.get_legal_moves(current_square)
                    self.set_piece_at(current_square, None)
                    self.draw_board(legal_moves=legal_moves)
                    drag.exec(Qt.MoveAction)
        except Exception:
            a0.ignore()

    def dragMoveEvent(self, a0):
        if not self.check_area_clicked(a0.pos()):
            QtGui.QCursor.setPos(self.mapToGlobal(self._drag_start_pos))
            print("not in a square when dragging")
            a0.ignore()
        else:
            a0.accept()

    def dragEnterEvent(self, a0):
        a0.accept()

    def dragLeaveEvent(self, a0):
        # QtGui.QCursor.setPos(self.mapToGlobal(self._drag_start_pos))
        print("drag leave event")
        a0.ignore()

    def dropEvent(self, a0):
        current = self.get_clicked(a0.pos())
        # piece = a0.mimeData().text().split(",")[1]
        fen = a0.mimeData().text().split(",")[-1]
        if not self.check_area_clicked(a0.pos()):
            print("not in a square when dropping")
            a0.ignore()
            return
        try:
            self.set_fen(fen)
            self.draw_board()
            uci = self.last_click + current
            self.apply_move(uci + self.get_promotion(uci), animate=False)
            a0.accept()
        except Exception:
            a0.ignore()

    def eventFilter(self, a0, a1):
        if a0 == self:
            if a1.type() == QtCore.QEvent.Type.HoverMove:
                if not self.check_area_clicked(a1.pos()):
                    if self.cursor().shape() != Qt.CursorShape.ArrowCursor:
                        self.setCursor(Qt.CursorShape.ArrowCursor)
                else:
                    if self.cursor().shape() != Qt.CursorShape.PointingHandCursor:
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
        return super().eventFilter(a0, a1)

    def contextMenuEvent(self, a0):
        super().contextMenuEvent(a0)
        menu = QtWidgets.QMenu(self)
        menu.addAction("Flip board")
        menu.addSeparator()

        action = menu.exec_(a0.globalPos())
        if action is None:
            return
        if action.text() == "Flip board":
            self.flip()

    def paintEvent(self, a0):
        super().paintEvent(a0)
        painter = QtGui.QPainter(self)
        painter.setPen(QtGui.QPen(Qt.GlobalColor.black, 3))
        # painter.drawEllipse(self.svg_xy, self.svg_xy, 5, 5)  # Draw a red circle
        # rect x="150" y="15" width="45" height="45"
        painter.end()

    def create_transparent_cursor(self) -> QtGui.QPixmap:
        pixmap = QtGui.QPixmap(1, 1)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        return pixmap

    def get_promotion(self, uci: str) -> Literal["q", "r", "b", "n", ""]:
        if chess.Move.from_uci(uci + "q") in self.legal_moves:
            dialog = PromotionDialog(self.turn, self)
            if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                return dialog.SelectedPiece()
        return ""

    def animate_move(self, move: chess.Move, emit=True):
        previous_fen = self.fen()
        piece = self.piece_at(move.from_square)
        self.set_piece_at(move.from_square, None)
        self.draw_board()
        svg_piece = chess.svg.piece(piece, size=int(self.square_size))
        self.animated_piece.load(QtCore.QByteArray(svg_piece.encode("utf-8")))
        self.animated_piece.raise_()

        # 2) compute start/end pixel coords
        x0, y0 = self.square_to_xy(move.from_square)
        x1, y1 = self.square_to_xy(move.to_square)
        self.animated_piece.setGeometry(
            x0, y0, int(self.square_size), int(self.square_size)
        )
        self.animated_piece.show()

        # 3) QPropertyAnimation on widget position
        anim = QtCore.QPropertyAnimation(self.animated_piece, b"pos", self)
        anim.setDuration(160)
        anim.setStartValue(QtCore.QPoint(x0, y0))
        anim.setEndValue(QtCore.QPoint(x1, y1))
        anim.finished.connect(
            lambda: self._finish_animated_move(move, previous_fen, emit)
        )
        anim.start()
        self._current_anim = anim  # keep alive

    @QtCore.pyqtSlot(chess.Move, chess.Piece)
    def _finish_animated_move(self, move: chess.Move, previous_fen, emit=True):
        self.set_fen(previous_fen)
        self.draw_board()
        if not self.is_game_over():
            self.animated_piece.hide()
            self.push(move)
            # self.set_piece_at(move.to_square, piece)
            self.draw_board()
            self.ReadyForNextMove.emit(self.fen())
            self.fenChanged.emit(self.fen())
            if emit:
                self.moveMade.emit(move.uci())
        else:
            self.GameOver.emit()

    def finish_move(self, move: chess.Move):
        if not self.is_game_over():
            self.push(move)
            self.draw_board()
            self.ReadyForNextMove.emit(self.fen())
            self.fenChanged.emit(self.fen())
            self.moveMade.emit(move.uci())
        else:
            self.GameOver.emit()

    def apply_move(self, uci: str, animate: bool = True):
        move = chess.Move.from_uci(uci)
        if move in self.legal_moves:
            self.last_move = move
            if animate:
                self.animate_move(move)
            else:
                self.finish_move(move)
            sys.stdout.flush()

    def add_legal_moves(self, svg_data: str, legal_moves: list[chess.Move]) -> str:
        root = ET.fromstring(svg_data)
        for rect in root.findall(".//{http://www.w3.org/2000/svg}rect"):
            class_attr = rect.attrib.get("class", "")
            for move in legal_moves:
                square_name = chess.square_name(move.to_square)
                if square_name in class_attr:  # manual "contains"
                    x = float(rect.attrib["x"])
                    y = float(rect.attrib["y"])
                    w = float(rect.attrib["width"])
                    h = float(rect.attrib["height"])
                    if self.is_capture(move):
                        circle = ET.Element(
                            "circle",
                            {
                                "cx": str(x + w / 2),
                                "cy": str(y + h / 2),
                                "r": str(w / 2.25),
                                "fill": "none",
                                "stroke": "rgb(20 85 30 / 50%)",
                                "stroke-width": "4",
                                "stroke-opacity": "0.3",
                            },
                        )
                    else:
                        circle = ET.Element(
                            "circle",
                            {
                                "cx": str(x + w / 2),
                                "cy": str(y + h / 2),
                                "r": str(w / 6),
                                "fill": "rgb(20 85 30 / 50%)",
                                "fill-opacity": "0.5",
                            },
                        )
                    root.append(circle)

        return ET.tostring(root, encoding="unicode")

    def get_legal_moves(self, src: str | chess.Square) -> list[chess.Move]:
        if isinstance(src, str):
            src = chess.parse_square(src)
        if isinstance(src, chess.Square):
            square_src = src
        if square_src not in [move.from_square for move in self.legal_moves]:
            return []
        targets = [move for move in self.legal_moves if move.from_square == square_src]

        return targets

    def restart_board(self):
        self.last_move = None
        self.reset()
        self.draw_board()
        self.ReadyForNextMove.emit(self.fen())
        self.fenChanged.emit(self.fen())

    def update_board(self, fen: str, last_move: chess.Move = None):
        self.last_move = last_move
        self.set_fen(fen)
        self.draw_board()
        self.fenChanged.emit(self.fen())

    def draw_board(self, legal_moves: list[chess.Move] = [], arrows: list[dict] = []):
        """Draws the board.

        Args:
            legal_moves (list[chess.Move]): A dict of legal moves. Defaults to .
            arrows (list[dict], optional): A list of arrows. Defaults to [].
        """
        from_square = None
        try:
            arrows = [
                chess.svg.Arrow(
                    arrow.get("from"),
                    arrow.get("to"),
                )
                for arrow in arrows
            ]
        except Exception:
            arrows = []
        if len(legal_moves) > 0:
            from_square = legal_moves[0].from_square
        squares_to_highlight = {from_square: "#699B71AA"} if from_square else {}
        svg = chess.svg.board(
            self,
            orientation=self.side,
            lastmove=self.last_move,
            check=self.king(self.turn) if self.is_check() else None,
            fill=squares_to_highlight,
            arrows=arrows,
            coordinates=False,
            borders=False,
            colors={"square light": "#eed8b3", "square dark": "#b68564"},
        )
        # legal = [chess.square_name(move.to_square) for move in legal_moves]
        svg = self.add_legal_moves(svg, legal_moves)
        # print(svg)
        self.svg_widget.load(svg.encode("utf-8"))

    def clear_board(self):
        self.reset()
        self.set_fen("8/8/8/8/8/8/8/8 w - - 0 1")
        self.draw_board()
        self.ReadyForNextMove.emit(self.fen())
        self.fenChanged.emit(self.fen())

    def flip(self):
        self.side = chess.BLACK if self.side == chess.WHITE else chess.WHITE
        self.draw_board()

    def get_clicked(self, event) -> str:
        top_left = self.svg_xy + self.margin
        file_i = int((event.x() - top_left) / self.square_size)
        rank_i = 7 - int((event.y() - top_left) / self.square_size)
        if self.side == chess.BLACK:
            rank_i = 7 - rank_i
            file_i = 7 - file_i
        return chr(file_i + 97) + str(rank_i + 1)

    def check_area_clicked(self, event: QtGui.QMouseEvent) -> bool:
        topleft = self.svg_xy + self.margin
        bottomright = self.board_size + self.svg_xy - self.margin
        return all(
            [
                # event.buttons() == Qt.MouseButton.LeftButton,
                topleft < event.x() < bottomright,
                topleft < event.y() < bottomright,
            ]
        )

    def square_to_xy(self, square: chess.Square) -> tuple[int, int]:
        f = chess.square_file(square)
        r = chess.square_rank(square)
        if self.side == chess.BLACK:
            f, r = 7 - f, 7 - r
        x = int(self.svg_xy + self.margin + f * self.square_size)
        y = int(self.svg_xy + self.margin + (7 - r) * self.square_size)
        return x, y - 5

    def piece_to_pixmap(self, piece: chess.Piece, size: int) -> QtGui.QPixmap:
        return PieceCache.piece_to_pixmap(piece, size)


class PromotionDialog(QtWidgets.QDialog):
    """
    A dialog to choose a piece for pawn promotion using graphical icons.
    """

    def __init__(self, color=chess.WHITE, parent=None):
        super().__init__(
            parent,
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("Choose Promotion Piece")

        # rounded dialog with shadow and gradient
        self.setStyleSheet(
            """
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f7fafc, stop:1 #dbeafe);
                border-radius: 30px;
                border: 2px solid #60a5fa;
            }
        """
        )

        self.color = color

        self.button_group = QtWidgets.QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.pieces = [
            (chess.QUEEN, "q"),
            (chess.ROOK, "r"),
            (chess.BISHOP, "b"),
            (chess.KNIGHT, "n"),
        ]

        layout = QtWidgets.QVBoxLayout()
        piece_layout = QtWidgets.QHBoxLayout()

        icon_size = 64
        for piece_type, piece_code in self.pieces:
            piece = chess.Piece(piece_type, self.color)
            pixmap = self.piece_to_pixmap(piece, icon_size)

            button = QtWidgets.QToolButton()
            button.setIcon(QtGui.QIcon(pixmap))
            button.setIconSize(QtCore.QSize(icon_size, icon_size))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setCheckable(True)
            button.setToolTip(piece_code)
            button.setProperty("piece_code", piece_code)

            # Modern button style
            button.setStyleSheet(
                """
                QToolButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #f5f3e7, stop:1 #bfa77a); /* Cream to muted brown */
                    border-radius: 20px;
                    border: 2px solid #a67c52;           /* Soft brown border */
                    padding: 8px;
                    margin: 8px;
                }
                QToolButton:pressed {
                    background: #a67c52;                 /* Rich brown for selected */
                    border: 2px solid #7c5c36;           /* Darker brown border */
                }

                QToolButton:hover {
                    background: #e6d3b3;                 /* Light brown highlight */
                }
            """
            )

            button.clicked.connect(self.accept)
            piece_layout.addWidget(button)
            self.button_group.addButton(button)

        first_button = self.button_group.buttons()[0]
        first_button.setChecked(True)

        layout.addLayout(piece_layout)
        self.setLayout(layout)

    def SelectedPiece(self) -> Literal["q", "r", "b", "n"]:
        """
        Returns the selected piece code: 'q', 'r', 'b', or 'n'
        """
        for button in self.button_group.buttons():
            if button.isChecked():
                return button.property("piece_code")
        return "q"  # fallback

    def piece_to_pixmap(self, piece: chess.Piece, size: int) -> QtGui.QPixmap:
        """
        Converts a chess piece to a QPixmap using chess.svg.piece().
        """
        return PieceCache.piece_to_pixmap(piece, size)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    board = ChessBoard(size=500)
    board.show()
    sys.exit(app.exec_())
