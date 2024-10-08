from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from classic import Classic
from pieces import Piece
from dialogs.promotion import PromotionDlg
from pieces import pieces_info


class Square(QtWidgets.QWidget):
    pieceMovedAttempted = QtCore.pyqtSignal(str)
    pieceDropped = QtCore.pyqtSignal(str, str)
    mouseReleased = QtCore.pyqtSignal(str)
    mousePressed = QtCore.pyqtSignal(str)
    pieceEnter = QtCore.pyqtSignal(str)
    pieceLeave = QtCore.pyqtSignal(str)
    mouseEnter = QtCore.pyqtSignal(str)
    mouseLeave = QtCore.pyqtSignal(str)
    mouseDoubleClicked = QtCore.pyqtSignal(str)
    kingMoved = QtCore.pyqtSignal(str, str)

    def __init__(self, parent: QtWidgets.QWidget, color: str, logic: Classic):
        """
        Args:
            parent: parent widget
            size: size of the board
            settings: settings dict

        Signals:
            pieceMovedAttempted: (position) returns the piece coordinate that was moved
            pieceDropped: (src, dst) returns the pieces coordinates that were dropped
            mouseReleased: (position) returns the piece coordinate that was released
            mousePressed: (position) returns the piece coordinate that was pressed
            pieceEnter: (position) returns the piece coordinate that entered
            pieceLeave: (position) returns the piece coordinate that left
            mouseEnter: (position) returns the piece coordinate that entered
            mouseLeave: (position) returns the piece coordinate that left
            mouseDoubleClicked: (position) returns the piece coordinate that was double clicked

        """
        super().__init__(parent)
        self.parent = parent
        self.setAcceptDrops(True)
        self.label = QtWidgets.QLabel(self)
        self.label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self.label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.label.setScaledContents(True)
        self.logic = logic
        self.setStyleSheet(
            f"background-color:{color};color:darkorange;font-weight:bolder;font-size:25px;"
        )
        self.clicked = False
        # self.setCursor(QtCore.Qt.OpenHandCursor)
        self.get_size()

    def setPiece(self, piece: Piece):
        self.piece = piece

    def change_promotion(self, promotion):
        self.promotion = promotion

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.mouseLeave.emit(self.objectName())
        self.setCursor(QtCore.Qt.ArrowCursor)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.mouseEnter.emit(self.objectName())
        if self.piece.name != "":
            self.setCursor(QtCore.Qt.OpenHandCursor)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if (event.buttons() & QtCore.Qt.LeftButton) and (self.piece.name != ""):
            self.pieceMovedAttempted.emit(self.objectName())
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            mime_data.setText("Dragging data")
            # Set mime data to drag object
            drag.setMimeData(mime_data)

            pixmap_icon = QtGui.QImage(self.label.pixmap()).scaled(
                self.width(), self.width(), QtCore.Qt.KeepAspectRatio
            )
            drag.setPixmap(QtGui.QPixmap(pixmap_icon))
            drag.setHotSpot(event.pos())
            drag.exec(QtCore.Qt.MoveAction)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.mousePressed.emit(self.objectName())
            if self.piece.name != "" and self.clicked is None:
                self.clicked = self
            if self.piece.name != "" and self.clicked is not None:
                pass
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        self.mouseReleased.emit(self.objectName())
        super().mouseReleaseEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent):
        self.promotion = "q"
        src_sq = event.source()
        self.pieceDropped.emit(self.objectName(), src_sq.objectName())
        if (
            src_sq == self
            or src_sq.piece.name == ""
            or not self.logic.check_move(src_sq, self)
        ):
            self.remove_hover_border()
            event.ignore()
            return
        if src_sq.piece.name.lower() == "k":
            self.kingMoved.emit(src_sq.objectName(), self.objectName())
            
        if self.logic.rules.check_promotion(src_sq, self):
            self.pmdlg = PromotionDlg(self)
            self.pmdlg.pieceSelected.connect(self.change_promotion)
            self.pmdlg.exec()

        if self.logic.rules.check_castle(src_sq, self):
            squares = self.logic.rules.get_castle_moves(src_sq, self)[1]
            src_rook = squares[0]
            dst_rook = squares[1]
            self.parent._move_glide(src_rook, dst_rook, promotion="q", make_move=False)

        if self.logic.rules.check_en_passant(src_sq, self):
            moves = self.logic.rules.get_en_passant_moves(src_sq, self)
            enpassant = self.parent.findChild(QtWidgets.QWidget, moves[1])
            enpassant.setPiece(Piece(self, ""))
            enpassant.label.setPixmap(QtGui.QPixmap())

        self.logic.make_move(src_sq, self, promotion=self.promotion)
        if self.logic.rules.check_promotion(src_sq, self):
            src_sq.label.setPixmap(QtGui.QPixmap(pieces_info[self.promotion]))
            src_sq.setPiece(Piece(self, pieces_info[self.promotion]))
        self.label.setPixmap(QtGui.QPixmap(src_sq.label.pixmap()))
        self.piece = src_sq.piece
        src_sq.label.setPixmap(QtGui.QPixmap())
        src_sq.setPiece(Piece(self, ""))
        self.remove_hover_border()
        event.accept()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.source() == self:
            event.ignore()
            return
        self.create_hover_border()
        event.accept()

    def dragLeaveEvent(self, event):
        self.remove_hover_border()
        event.accept()

    def dragMoveEvent(self, event):
        event.accept()

    def paintEvent(self, event):
        super().paintEvent(event)

    def resizeEvent(self, a0: QtGui.QResizeEvent) -> None:
        super().resizeEvent(a0)
        self.get_size()

    def get_size(self):
        width, height = self.parent.size().width(), self.parent.size().height()
        self.resize(int(width / 8), int(height / 8))
        self.setMaximumSize(int(width / 8), int(height / 8))
        self.setMinimumSize(int(width / 8), int(height / 8))
        self.label.resize(int(width / 8), int(height / 8))

    def create_hover_border(self):
        border = ";border:7px solid darkorange;"
        self.setStyleSheet(self.styleSheet() + border)

    def remove_hover_border(self):
        self.setStyleSheet(
            self.styleSheet().replace(";border:7px solid darkorange;", "")
        )
