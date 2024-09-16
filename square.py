from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

from pieces import Piece
from rules import Rules


class Square(QtWidgets.QLabel):
    def __init__(self, parent: QtWidgets.QWidget, color: str):
        super().__init__(parent)
        self.parent = parent
        self.piece_text = ""
        self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.setAcceptDrops(True)
        self.setScaledContents(True)
        self.setStyleSheet(
            f"background-color:{color};color:darkorange;font-weight:bolder;font-size:25px"
        )
        self.setCursor(QtCore.Qt.OpenHandCursor)
        self.get_size()

    def setPiece(self, piece: Piece):
        self.piece = piece

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        if (event.buttons() & QtCore.Qt.LeftButton) and (self.piece.name != ""):
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            mime_data.setText("Dragging data")
            # Set mime data to drag object
            drag.setMimeData(mime_data)
            pixmap_icon = QtGui.QImage(self.pixmap()).scaled(
                self.width(), self.width(), QtCore.Qt.KeepAspectRatio
            )
            drag.setPixmap(QtGui.QPixmap(pixmap_icon))
            drag.setHotSpot(event.pos())
            drag.exec(QtCore.Qt.MoveAction)

    def mousePressEvent(self, event):
        # self.move(400, 400)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent):
        src_sq = event.source()
        if src_sq == self or src_sq.piece.name == "":
            self.remove_hover_border()
            event.ignore()
            return
        self.setPixmap(QtGui.QPixmap(src_sq.pixmap()))
        self.piece = src_sq.piece
        src_sq.setPixmap(QtGui.QPixmap())
        print(Rules().check_en_passant(src_sq, self))
        self.remove_hover_border()
        event.accept()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.source() == self:
            event.ignore()
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

    def create_hover_border(self):
        border = ";border:8px solid darkorange;"
        self.setStyleSheet(self.styleSheet() + border)

    def remove_hover_border(self):
        self.setStyleSheet(
            self.styleSheet().replace(";border:8px solid darkorange;", "")
        )
