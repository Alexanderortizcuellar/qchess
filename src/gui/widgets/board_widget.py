import chess
import chess.svg
import qtawesome as qta
from PyQt5.QtCore import Qt, pyqtSignal, QByteArray, QSize, QMimeData, QSettings
from PyQt5.QtGui import QPixmap, QPainter, QIcon, QDrag
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QButtonGroup, QApplication
)


def get_piece_pixmap(piece, size=40):
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
        self.setFixedSize(42, 42)
        self.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)
        self.drag_start_pos = None
        self.update_background()

    def update_background(self, selected=False):
        color = "#99CC99" if selected else self.base_color
        self.setStyleSheet(f"background-color: {color}; border: 1px solid rgba(0,0,0,0.05);")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
            self.editor_parent.square_clicked(self.square_index)

    def mouseMoveEvent(self, event):
        if not self.drag_start_pos or not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return

        active_btn = self.editor_parent.tool_group.checkedButton()
        if not active_btn or self.editor_parent.tools_map.get(active_btn) != "hand":
            return
        if not self.editor_parent.board.piece_at(self.square_index):
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(str(self.square_index))
        drag.setMimeData(mime_data)
        if self.pixmap():
            drag.setPixmap(self.pixmap())
            drag.setHotSpot(self.pixmap().rect().center())
        self.clear()
        drag.exec_(Qt.MoveAction)
        self.editor_parent.update_board_ui()

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        origin_idx = int(event.mimeData().text())
        self.editor_parent.handle_drop(origin_idx, self.square_index)
        event.acceptProposedAction()


class ChessBoardEditorWidget(QWidget):
    """
    Embedded Chess Board Editor with piece palette, click-to-place, drag-and-drop,
    and partial position support (e.g. single Queen on d4).
    """
    fen_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.selected_square = None
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        self.tools_map = {}
        self.square_widgets = {}
        self.palette_buttons = []
        self.is_dark = self._is_dark()

        self.init_ui()

    def _is_dark(self) -> bool:
        if self.parent() is not None and hasattr(self.parent(), "is_dark"):
            return bool(self.parent().is_dark)
        return QSettings("QChessApp", "Theme").value("theme", "dark") == "dark"

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # Black piece toolbar
        top_tb = self.create_toolbar(color=chess.BLACK)
        main_layout.addLayout(top_tb)

        # 8x8 Board grid
        board_layout = QGridLayout()
        board_layout.setSpacing(0)

        for rank in range(7, -1, -1):
            for file in range(8):
                sq_idx = chess.square(file, rank)
                is_light = (file + rank) % 2 != 0
                sq_w = SquareWidget(sq_idx, is_light, self)
                self.square_widgets[sq_idx] = sq_w
                board_layout.addWidget(sq_w, 7 - rank, file)

        b_container = QHBoxLayout()
        b_container.addStretch()
        b_container.addLayout(board_layout)
        b_container.addStretch()
        main_layout.addLayout(b_container)

        # White piece toolbar
        bot_tb = self.create_toolbar(color=chess.WHITE)
        main_layout.addLayout(bot_tb)

        self.set_theme(self.is_dark)
        self.update_board_ui()
        if self.tool_group.buttons():
            self.tool_group.buttons()[0].setChecked(True)

    def create_toolbar(self, color):
        layout = QHBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        # Hand / Move tool
        btn_hand = QPushButton()
        btn_hand.setCheckable(True)
        btn_hand.setFixedSize(38, 38)
        btn_hand.setCursor(Qt.PointingHandCursor)
        btn_hand.setToolTip("Hand: Click or Drag to move pieces on the board")
        self.tool_group.addButton(btn_hand)
        self.tools_map[btn_hand] = "hand"
        btn_hand.setProperty("tool_type", "hand")
        btn_hand.setProperty("tool_color", "black" if color == chess.BLACK else "white")
        self.palette_buttons.append(btn_hand)
        layout.addWidget(btn_hand)

        # Piece buttons
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
            pixmap = get_piece_pixmap(piece, size=32)
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(32, 32))
            btn.setCheckable(True)
            btn.setFixedSize(38, 38)
            btn.setToolTip(f"Place {piece.symbol()} on square")
            self.tool_group.addButton(btn)
            self.tools_map[btn] = piece
            btn.setProperty("tool_type", "piece")
            self.palette_buttons.append(btn)
            layout.addWidget(btn)

        # Trash tool
        btn_trash = QPushButton()
        btn_trash.setCheckable(True)
        btn_trash.setFixedSize(38, 38)
        btn_trash.setCursor(Qt.PointingHandCursor)
        btn_trash.setToolTip("Trash: Click squares to remove pieces")
        self.tool_group.addButton(btn_trash)
        self.tools_map[btn_trash] = "trash"
        btn_trash.setProperty("tool_type", "trash")
        self.palette_buttons.append(btn_trash)
        layout.addWidget(btn_trash)

        return layout

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        if is_dark:
            btn_style = """
                QPushButton {
                    background-color: #262421;
                    border: 1px solid #383531;
                    border-radius: 4px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: #35322e;
                    border: 1px solid #504d48;
                }
                QPushButton:checked {
                    background-color: #1e3a5f;
                    border: 2px solid #3b82f6;
                }
            """
        else:
            btn_style = """
                QPushButton {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                    border: 1px solid #94a3b8;
                }
                QPushButton:checked {
                    background-color: #dbeafe;
                    border: 2px solid #2563eb;
                }
            """

        for btn in self.palette_buttons:
            btn.setStyleSheet(btn_style)
            t_type = btn.property("tool_type")
            if t_type == "hand":
                t_col = btn.property("tool_color")
                if is_dark:
                    icon_color = "#cbd5e1" if t_col == "black" else "#60a5fa"
                else:
                    icon_color = "#334155" if t_col == "black" else "#2563eb"
                btn.setIcon(qta.icon("fa5s.hand-pointer", color=icon_color))
            elif t_type == "trash":
                btn.setIcon(qta.icon("fa5s.trash-alt", color="#ef4444" if is_dark else "#dc2626"))

    def square_clicked(self, square_index):
        active_btn = self.tool_group.checkedButton()
        if not active_btn:
            return
        tool = self.tools_map.get(active_btn)

        if tool == "trash":
            self.board.remove_piece_at(square_index)
            self.selected_square = None
        elif isinstance(tool, chess.Piece):
            self.board.set_piece_at(square_index, tool)
            self.selected_square = None
        elif tool == "hand":
            if self.selected_square is None:
                if self.board.piece_at(square_index):
                    self.selected_square = square_index
            else:
                if self.selected_square != square_index:
                    p = self.board.piece_at(self.selected_square)
                    if p:
                        self.board.set_piece_at(square_index, p)
                        self.board.remove_piece_at(self.selected_square)
                self.selected_square = None

        self.update_board_ui()

    def handle_drop(self, origin_idx, target_idx):
        if origin_idx != target_idx:
            p = self.board.piece_at(origin_idx)
            if p:
                self.board.set_piece_at(target_idx, p)
                self.board.remove_piece_at(origin_idx)
        self.selected_square = None
        self.update_board_ui()

    def update_board_ui(self):
        for sq_idx, w in self.square_widgets.items():
            p = self.board.piece_at(sq_idx)
            if p:
                w.setPixmap(get_piece_pixmap(p, size=36))
            else:
                w.clear()
            w.update_background(selected=(sq_idx == self.selected_square))

        fen_str = self.board.fen()
        self.fen_changed.emit(fen_str)

    def clear_board(self):
        self.board.clear()
        self.selected_square = None
        self.update_board_ui()

    def reset_to_initial(self):
        self.board.reset()
        self.selected_square = None
        self.update_board_ui()

    def set_fen(self, fen: str):
        try:
            t = fen.strip()
            if not t:
                return
            parts = t.split()
            if len(parts) >= 6:
                self.board.set_fen(t)
            else:
                self.board.set_board_fen(parts[0])
            self.selected_square = None
            self.update_board_ui()
        except Exception:
            pass

    def get_board_fen(self) -> str:
        return self.board.fen()
