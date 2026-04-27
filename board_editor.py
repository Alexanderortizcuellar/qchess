import sys
import chess
import chess.svg
import qtawesome as qta
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGridLayout,
    QButtonGroup,
    QDialog,
    QLineEdit
)
from PyQt5.QtCore import Qt, QSize, QByteArray, QMimeData
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QDrag
from PyQt5.QtSvg import QSvgRenderer


def get_piece_pixmap(piece, size=60):
    """Generates a QPixmap from the python-chess SVG piece."""
    svg_string = chess.svg.piece(piece)
    renderer = QSvgRenderer(QByteArray(svg_string.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap


class SquareWidget(QLabel):
    """A custom label representing a single square on the chessboard."""

    def __init__(self, square_index, is_light, editor_parent):
        super().__init__()
        self.square_index = square_index
        self.editor_parent = editor_parent
        self.base_color = "#F0D9B5" if is_light else "#B58863"
        self.setFixedSize(60, 60)
        self.setAlignment(Qt.AlignCenter)

        self.setAcceptDrops(True)
        self.drag_start_pos = None

        self.update_background()

    def update_background(self, selected=False):
        """Updates the background color, highlighting if selected."""
        color = "#99CC99" if selected else self.base_color
        self.setStyleSheet(f"background-color: {color};")

    def mousePressEvent(self, event):
        """Registers the start of a potential drag and handles normal clicks."""
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
            self.editor_parent.square_clicked(self.square_index)

    def mouseMoveEvent(self, event):
        """Initiates the drag action if the mouse moves far enough."""
        if not self.drag_start_pos:
            return

        if not (event.buttons() & Qt.LeftButton):
            return

        if (
            event.pos() - self.drag_start_pos
        ).manhattanLength() < QApplication.startDragDistance():
            return

        active_button = self.editor_parent.tool_group.checkedButton()
        if (
            not active_button
            or self.editor_parent.tools_map.get(active_button) != "hand"
        ):
            return

        if not self.editor_parent.board.piece_at(self.square_index):
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.square_index))
        drag.setMimeData(mime_data)

        if self.pixmap():
            drag.setPixmap(self.pixmap())
            # Center the piece on the mouse cursor for a better feel
            drag.setHotSpot(self.pixmap().rect().center())

        # --- THE FIX ---
        # Visually clear the square to simulate "picking it up"
        self.clear()

        # Execute the drag (this is a blocking call until the drop happens)
        drag.exec_(Qt.MoveAction)

        # If the drag was cancelled (e.g., dropped outside the board),
        # this forces the UI to refresh and put the piece back.
        self.editor_parent.update_board_ui()

    def dragEnterEvent(self, event):
        """Accepts the drag if it contains our text data."""
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Reads the origin square from the drag data and executes the move."""
        origin_index = int(event.mimeData().text())
        self.editor_parent.handle_drop(origin_index, self.square_index)
        event.acceptProposedAction()


class ChessBoardEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chessboard Editor")
        self.setObjectName("chessboard_editor")
        self.board = chess.Board()
        self.selected_square = None

        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tools_map = {}
        self.square_widgets = {}

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        top_toolbar = self.create_toolbar(color=chess.BLACK)
        main_layout.addLayout(top_toolbar)

        board_layout = QGridLayout()
        board_layout.setSpacing(0)

        for rank in range(7, -1, -1):
            for file in range(8):
                square_index = chess.square(file, rank)
                is_light = (file + rank) % 2 != 0

                square_widget = SquareWidget(square_index, is_light, self)
                self.square_widgets[square_index] = square_widget

                board_layout.addWidget(square_widget, 7 - rank, file)

        board_container = QHBoxLayout()
        board_container.addStretch()
        board_container.addLayout(board_layout)
        board_container.addStretch()
        main_layout.addLayout(board_container)

        bottom_toolbar = self.create_toolbar(color=chess.WHITE)
        main_layout.addLayout(bottom_toolbar)
        self.fen_display = QLineEdit()
        self.fen_display.setObjectName("fen_display")
        self.fen_display.setReadOnly(True)
        main_layout.addWidget(self.fen_display)

        self.update_board_ui()

        first_btn = self.tool_group.buttons()[0]
        first_btn.setChecked(True)

    def create_toolbar(self, color):
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        btn_hand = QPushButton()
        btn_hand.setIcon(qta.icon("fa5s.hand-pointer",))
        btn_hand.setCheckable(True)
        btn_hand.setFixedSize(60, 60)
        self.tool_group.addButton(btn_hand)
        self.tools_map[btn_hand] = "hand"
        layout.addWidget(btn_hand)

        piece_types = [
            chess.KING,
            chess.QUEEN,
            chess.ROOK,
            chess.BISHOP,
            chess.KNIGHT,
            chess.PAWN,
        ]
        for pt in piece_types:
            piece = chess.Piece(pt, color)
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            pixmap = get_piece_pixmap(piece, size=50)
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(50, 50))
            btn.setCheckable(True)
            btn.setFixedSize(60, 60)

            self.tool_group.addButton(btn)
            self.tools_map[btn] = piece
            layout.addWidget(btn)

        btn_trash = QPushButton()
        btn_trash.setIcon(qta.icon("fa5s.trash-alt"))
        btn_trash.setCheckable(True)
        btn_trash.setFixedSize(60, 60)
        self.tool_group.addButton(btn_trash)
        self.tools_map[btn_trash] = "trash"
        layout.addWidget(btn_trash)

        return layout

    def square_clicked(self, square_index):
        """Handles standard click interactions (placement, trashing, click-to-move)."""
        active_button = self.tool_group.checkedButton()
        if not active_button:
            return

        current_tool = self.tools_map.get(active_button)

        if current_tool == "trash":
            self.board.remove_piece_at(square_index)
            self.selected_square = None

        elif isinstance(current_tool, chess.Piece):
            self.board.set_piece_at(square_index, current_tool)
            self.selected_square = None

        elif current_tool == "hand":
            if self.selected_square is None:
                if self.board.piece_at(square_index):
                    self.selected_square = square_index
            else:
                if self.selected_square != square_index:
                    moving_piece = self.board.piece_at(self.selected_square)
                    if moving_piece:
                        self.board.set_piece_at(square_index, moving_piece)
                        self.board.remove_piece_at(self.selected_square)
                self.selected_square = None

        self.update_board_ui()

    def handle_drop(self, origin_index, target_index):
        """Triggered specifically when a piece is dragged and dropped onto a new square."""
        if origin_index != target_index:
            moving_piece = self.board.piece_at(origin_index)
            if moving_piece:
                self.board.set_piece_at(target_index, moving_piece)
                self.board.remove_piece_at(origin_index)

        # Clear the highlighted square state after a successful drop
        self.selected_square = None
        self.update_board_ui()

    def update_board_ui(self):
        for square_index, widget in self.square_widgets.items():
            piece = self.board.piece_at(square_index)
            if piece:
                widget.setPixmap(get_piece_pixmap(piece))
            else:
                widget.clear()

            is_selected = square_index == self.selected_square
            widget.update_background(selected=is_selected)
            self.fen_display.setText(self.board.fen())


class BoardEditorDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.board_editor = ChessBoardEditor()
        self.main_layout = QVBoxLayout(self)
        self.main_layout.addWidget(self.board_editor)
    



if __name__ == "__main__":
    app = QApplication(sys.argv)
    editor = ChessBoardEditor()
    editor.show()
    sys.exit(app.exec_())
