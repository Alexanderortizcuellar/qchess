import re
import chess
import qtawesome as qta
from PyQt5.QtCore import Qt, pyqtSignal, QUrl, QSize
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QSplitter,
    QFrame,
    QSizePolicy,
)

from core.move_manager import MoveManager
from gui.widgets.chessboard import ChessBoard
from gui.widgets.painter_pgn_browser import QPainterPGNBrowser


class GamePreviewWidget(QWidget):
    """
    Game preview widget embedding a ChessBoard, MoveManager, and QPainterPGNBrowser.
    Allows fast move-by-move navigation and opening the game in the full analyzer.
    """

    openGameRequested = pyqtSignal(dict)

    def __init__(self, parent=None, is_dark: bool = True):
        super().__init__(parent)
        self.is_dark = is_dark
        self._current_game_data = {}

        self.move_manager = MoveManager()
        self.move_manager.change_html_style(self.is_dark)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Header card (Players, Elo, Result, ECO, Event)
        self.header_card = QFrame(self)
        self.header_card.setFrameShape(QFrame.StyledPanel)
        header_layout = QVBoxLayout(self.header_card)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(2)

        self.players_label = QLabel("No game selected", self.header_card)
        self.players_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.players_label.setWordWrap(True)

        self.meta_label = QLabel("", self.header_card)
        self.meta_label.setFont(QFont("Segoe UI", 8))
        self.meta_label.setWordWrap(True)

        header_layout.addWidget(self.players_label)
        header_layout.addWidget(self.meta_label)
        main_layout.addWidget(self.header_card)

        # Splitter dividing Board+Controls and PGN Browser
        self.splitter = QSplitter(Qt.Vertical, self)
        self.splitter.setChildrenCollapsible(False)

        # Top section: Board + Controls
        top_container = QWidget(self.splitter)
        top_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)

        # Board container
        self.board_container = QWidget(top_container)
        self.board_container.setObjectName("previewBoardContainer")
        self.board_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        board_layout = QVBoxLayout(self.board_container)
        board_layout.setContentsMargins(0, 0, 0, 0)

        self.chessboard = ChessBoard(self.board_container, fen=chess.STARTING_FEN, size=0)
        self.chessboard.interactive = False
        self.chessboard.setMinimumSize(120, 120)
        self.chessboard.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        board_layout.addWidget(self.chessboard)

        top_layout.addWidget(self.board_container, 1)

        # Mini Navigation Controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)
        controls_layout.setAlignment(Qt.AlignCenter)

        self.btn_first = self._create_btn("ph.caret-double-left-fill", "First Move (Home)", self.go_first)
        self.btn_prev = self._create_btn("ph.caret-left-fill", "Previous Move (Left)", self.go_prev)
        self.btn_next = self._create_btn("ph.caret-right-fill", "Next Move (Right)", self.go_next)
        self.btn_last = self._create_btn("ph.caret-double-right-fill", "Last Move (End)", self.go_last)
        self.btn_flip = self._create_btn("fa5s.sync-alt", "Flip Board", self.flip_board)

        # Match Stepping Buttons (shown when game has search matching plies)
        self.btn_prev_match = self._create_btn("fa5s.step-backward", "Previous Match Position", self.go_prev_match)
        self.btn_prev_match.setToolTip("Jump to previous query match position")
        self.btn_prev_match.hide()

        self.lbl_match_badge = QLabel("", self)
        self.lbl_match_badge.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self.lbl_match_badge.setStyleSheet("color: #3b82f6; padding: 2px 4px;")
        self.lbl_match_badge.hide()

        self.btn_next_match = self._create_btn("fa5s.step-forward", "Next Match Position", self.go_next_match)
        self.btn_next_match.setToolTip("Jump to next query match position")
        self.btn_next_match.hide()

        self.btn_open = QToolButton(top_container)
        self.btn_open.setIcon(qta.icon("fa5s.external-link-alt", color="#3b82f6" if self.is_dark else "#2563eb"))
        self.btn_open.setText(" Open")
        self.btn_open.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_open.setToolTip("Open Game in Full Analyzer")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self._on_open_clicked)

        controls_layout.addWidget(self.btn_first)
        controls_layout.addWidget(self.btn_prev)
        controls_layout.addWidget(self.btn_next)
        controls_layout.addWidget(self.btn_last)
        controls_layout.addWidget(self.btn_flip)
        controls_layout.addWidget(self.btn_prev_match)
        controls_layout.addWidget(self.lbl_match_badge)
        controls_layout.addWidget(self.btn_next_match)
        controls_layout.addWidget(self.btn_open)

        top_layout.addLayout(controls_layout)
        self.splitter.addWidget(top_container)

        # Bottom section: PGN Browser
        self.browser = QPainterPGNBrowser(self.splitter, self.move_manager)
        self.browser.anchorClicked.connect(self._on_anchor_clicked)
        self.browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.splitter.addWidget(self.browser)

        # Proportions and stretch factors
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([280, 220])

        main_layout.addWidget(self.splitter, 1)

        self.apply_theme_styles()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "chessboard") and hasattr(self.chessboard, "_update_layout"):
            self.chessboard._update_layout()

    def _create_btn(self, icon_name: str, tooltip: str, callback) -> QToolButton:
        btn = QToolButton(self)
        color = "#a9aea7" if self.is_dark else "#475569"
        btn.setIcon(qta.icon(icon_name, color=color))
        btn.setIconSize(QSize(16, 16))
        btn.setToolTip(tooltip)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)
        btn.setFixedSize(28, 28)
        return btn

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.move_manager.change_html_style(is_dark)
        self.apply_theme_styles()
        if hasattr(self.browser, "rebuild_layout"):
            self.browser.rebuild_layout(force=True)
            self.browser.paint_widget.update()
            self.browser.header_widget.update()

    def apply_theme_styles(self):
        icon_color = "#a9aea7" if self.is_dark else "#475569"
        self.btn_first.setIcon(qta.icon("ph.caret-double-left-fill", color=icon_color))
        self.btn_prev.setIcon(qta.icon("ph.caret-left-fill", color=icon_color))
        self.btn_next.setIcon(qta.icon("ph.caret-right-fill", color=icon_color))
        self.btn_last.setIcon(qta.icon("ph.caret-double-right-fill", color=icon_color))
        self.btn_flip.setIcon(qta.icon("fa5s.sync-alt", color=icon_color))
        self.btn_open.setIcon(qta.icon("fa5s.external-link-alt", color="#3b82f6" if self.is_dark else "#2563eb"))

        if self.is_dark:
            self.header_card.setStyleSheet("""
                QFrame {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 6px;
                }
            """)
            self.players_label.setStyleSheet("color: #f8fafc;")
            self.meta_label.setStyleSheet("color: #94a3b8;")
            self.board_container.setStyleSheet("#previewBoardContainer { background: transparent; }")
            self.btn_open.setStyleSheet("""
                QToolButton {
                    background-color: #1e293b;
                    color: #93c5fd;
                    border: 1px solid #3b82f6;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: bold;
                }
                QToolButton:hover {
                    background-color: #2563eb;
                    color: #ffffff;
                }
            """)
        else:
            self.header_card.setStyleSheet("""
                QFrame {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                }
            """)
            self.players_label.setStyleSheet("color: #0f172a;")
            self.meta_label.setStyleSheet("color: #64748b;")
            self.board_container.setStyleSheet("""
                #previewBoardContainer {
                    background-color: #e2e8f0;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                }
            """)
            self.btn_open.setStyleSheet("""
                QToolButton {
                    background-color: #eff6ff;
                    color: #1d4ed8;
                    border: 1px solid #3b82f6;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-weight: bold;
                }
                QToolButton:hover {
                    background-color: #2563eb;
                    color: #ffffff;
                }
            """)

    def load_game(self, game_dict: dict, pgn_text: str):
        self._current_game_data = dict(game_dict) if game_dict else {}
        self._current_game_data["PGN"] = pgn_text

        # Update labels
        w = game_dict.get("White", "?") or "?"
        w_elo = game_dict.get("EloW") or ""
        b = game_dict.get("Black", "?") or "?"
        b_elo = game_dict.get("EloB") or ""

        w_str = f"{w} ({w_elo})" if w_elo and w_elo != "-" else w
        b_str = f"{b} ({b_elo})" if b_elo and b_elo != "-" else b
        self.players_label.setText(f"{w_str} vs {b_str}")

        res = game_dict.get("Result", "*") or "*"
        eco = game_dict.get("ECO", "") or ""
        date = game_dict.get("Date", "") or ""
        event = game_dict.get("Event", "") or ""

        meta_parts = []
        if res and res != "*":
            meta_parts.append(f"Result: {res}")
        if eco and eco != "?":
            meta_parts.append(f"[{eco}]")
        if date and date != "????.??.??":
            meta_parts.append(date)
        if event and event != "?":
            meta_parts.append(event)

        self.meta_label.setText(" • ".join(meta_parts))

        # Update PGN and board
        self.matching_plies = game_dict.get("matching_plies") or game_dict.get("_matching_plies") or []
        self.current_match_idx = 0

        if pgn_text:
            self.move_manager.update_pgn(pgn_text)
            if self.matching_plies:
                target_ply = self.matching_plies[0]
                self.move_manager.goto_ply(target_ply)
            else:
                self.move_manager.jump_to_start()
        else:
            self.move_manager.update_pgn("")

        self._update_match_controls()
        self.browser.setHtml(self.move_manager.html)
        self.sync_board_to_pgn()

    def _update_match_controls(self):
        if self.matching_plies and len(self.matching_plies) > 0:
            total_m = len(self.matching_plies)
            curr_m = self.current_match_idx + 1
            curr_ply = self.matching_plies[self.current_match_idx]
            self.lbl_match_badge.setText(f"Match {curr_m}/{total_m} (p{curr_ply})")
            self.lbl_match_badge.show()
            if total_m > 1:
                self.btn_prev_match.show()
                self.btn_next_match.show()
            else:
                self.btn_prev_match.hide()
                self.btn_next_match.hide()
        else:
            self.lbl_match_badge.hide()
            self.btn_prev_match.hide()
            self.btn_next_match.hide()

    def go_prev_match(self):
        if not self.matching_plies:
            return
        self.current_match_idx = (self.current_match_idx - 1) % len(self.matching_plies)
        target_ply = self.matching_plies[self.current_match_idx]
        self.move_manager.goto_ply(target_ply)
        self._update_match_controls()
        self.sync_board_to_pgn()
        self.browser.update_active_index()

    def go_next_match(self):
        if not self.matching_plies:
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matching_plies)
        target_ply = self.matching_plies[self.current_match_idx]
        self.move_manager.goto_ply(target_ply)
        self._update_match_controls()
        self.sync_board_to_pgn()
        self.browser.update_active_index()

    def clear(self):
        self._current_game_data = {}
        self.matching_plies = []
        self.current_match_idx = 0
        self._update_match_controls()
        self.players_label.setText("No game selected")
        self.meta_label.setText("")
        self.move_manager.update_pgn("")
        self.browser.setHtml("")
        self.chessboard.set_fen(chess.STARTING_FEN)

    def sync_board_to_pgn(self):
        node = self.move_manager.current_node
        last_move = node.move if hasattr(node, "move") and node.move else None
        shapes, highlights = self.move_manager.get_current_shapes_and_highlights()
        self.chessboard.update_board(
            self.move_manager.get_board().fen(),
            last_move,
            shapes=shapes,
            custom_highlights=highlights,
        )

    def _on_anchor_clicked(self, url: QUrl):
        match = re.match(r"move\((\d+)\)", url.toString())
        if match:
            idx = int(match.group(1))
            self.move_manager.jump_to(idx)
            self.sync_board_to_pgn()
            self.browser.update_active_index()

    def go_first(self):
        self.move_manager.jump_to_start()
        self.sync_board_to_pgn()
        self.browser.update_active_index()

    def go_prev(self):
        self.move_manager.undo()
        self.sync_board_to_pgn()
        self.browser.update_active_index()

    def go_next(self):
        if self.move_manager.current_node.variations:
            self.move_manager.redo(0)
            self.sync_board_to_pgn()
            self.browser.update_active_index()

    def go_last(self):
        self.move_manager.jump_to_end()
        self.sync_board_to_pgn()
        self.browser.update_active_index()

    def flip_board(self):
        self.chessboard.flip()

    def _on_open_clicked(self):
        if self._current_game_data:
            self.openGameRequested.emit(self._current_game_data)
