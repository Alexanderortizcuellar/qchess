from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt
from classic import Classic
from pieces import Piece
from dialogs.promotion import PromotionDlg

class Square(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget, color: str, logic: Classic):
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
            f"background-color:{color};color:darkorange;font-weight:bolder;font-size:25px"
        )

        # self.setCursor(QtCore.Qt.OpenHandCursor)
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
            pixmap_icon = QtGui.QImage(self.label.pixmap()).scaled(
                self.width(), self.width(), QtCore.Qt.KeepAspectRatio
            )
            drag.setPixmap(QtGui.QPixmap(pixmap_icon))
            drag.setHotSpot(event.pos())
            drag.exec(QtCore.Qt.MoveAction)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent):
        src_sq = event.source()
        if (
            src_sq == self
            or src_sq.piece.name == ""
            or not self.logic.check_move(src_sq, self)
        ):
            self.remove_hover_border()
            event.ignore()
            return
        # self.parent.move_glide(src_sq.objectName(), self.objectName())
        if self.logic.rules.check_promotion(src_sq, self):
            self.pmdlg = PromotionDlg(self)
            self.pmdlg.exec()
        self.label.setPixmap(QtGui.QPixmap(src_sq.label.pixmap()))
        self.piece = src_sq.piece
        src_sq.label.setPixmap(QtGui.QPixmap())
        src_sq.setPiece(Piece(self, ""))
        self.logic.make_move(src_sq.objectName() + self.objectName())
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
