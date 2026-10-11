import chess
from typing import Optional, List, Dict, Any
from PyQt5 import QtCore, QtGui, QtWidgets


class ContinuationPercentageBar(QtWidgets.QWidget):
    """Visual outcome distribution bar (White Win / Draw / Black Win)."""

    def __init__(
        self,
        white_win: int,
        draw: int,
        black_win: int,
        parent=None,
    ):
        super().__init__(parent)
        self.white_win = int(white_win)
        self.draw = int(draw)
        self.black_win = int(black_win)
        self.setFixedHeight(22)
        self.is_dark = True
        self._update_tooltip()

    def set_data(self, white_win: int, draw: int, black_win: int):
        self.white_win = int(white_win)
        self.draw = int(draw)
        self.black_win = int(black_win)
        self._update_tooltip()
        self.update()

    def _update_tooltip(self):
        total = self.white_win + self.draw + self.black_win
        if total > 0:
            white_pct = (self.white_win / total) * 100
            draw_pct = (self.draw / total) * 100
            black_pct = (self.black_win / total) * 100
            tooltip = (
                f"Total games: {total:,}\n"
                f"White wins: {self.white_win:,} ({white_pct:.1f}%)\n"
                f"Draws: {self.draw:,} ({draw_pct:.1f}%)\n"
                f"Black wins: {self.black_win:,} ({black_pct:.1f}%)"
            )
            self.setToolTip(tooltip)
        else:
            self.setToolTip("No games")

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        total_w = self.width()
        h = self.height()
        total = self.white_win + self.draw + self.black_win
        if total == 0:
            return

        pw = (self.white_win / total) * total_w
        pd = (self.draw / total) * total_w
        pb = total_w - pw - pd

        color_white = QtGui.QColor("#ffffff")
        color_draw = QtGui.QColor("#94a3b8")
        color_black = QtGui.QColor("#1e293b" if not self.is_dark else "#312e2b")

        painter.setPen(QtCore.Qt.NoPen)

        # White
        if pw > 0:
            painter.setBrush(color_white)
            painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if not self.is_dark:
                painter.setPen(QtGui.QPen(QtGui.QColor("#cbd5e1"), 1))
                painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if pw > 28:
                painter.setPen(QtGui.QColor("#0f172a"))
                pct = (self.white_win / total) * 100
                painter.drawText(QtCore.QRectF(0, 0, pw, h), QtCore.Qt.AlignCenter, f"{pct:.0f}%")

        # Draw
        if pd > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_draw)
            painter.drawRect(QtCore.QRectF(pw, 0, pd, h))
            if pd > 28:
                painter.setPen(QtGui.QColor("#ffffff"))
                pct = (self.draw / total) * 100
                painter.drawText(QtCore.QRectF(pw, 0, pd, h), QtCore.Qt.AlignCenter, f"{pct:.0f}%")

        # Black
        if pb > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_black)
            painter.drawRect(QtCore.QRectF(pw + pd, 0, pb, h))
            if pb > 28:
                painter.setPen(QtGui.QColor("#ffffff"))
                pct = (self.black_win / total) * 100
                painter.drawText(QtCore.QRectF(pw + pd, 0, pb, h), QtCore.Qt.AlignCenter, f"{pct:.0f}%")


class NoFocusDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that suppresses the dotted cell focus rectangle on selection."""
    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        opt.state &= ~QtWidgets.QStyle.State_HasFocus
        super().paint(painter, opt, index)


class ContinuationsWidget(QtWidgets.QWidget):
    """
    ChessBase-style Common Continuations Explorer & Multi-Move Sequence Analyzer.
    - Queries top multi-move continuation paths for any position from scid-mgr.
    - Features a compact right-side line counter widget (+ / N / -) similar to engine PV controls.
    - Headerless table for a clean, minimal, uncluttered view.
    """

    queryRequested = QtCore.pyqtSignal(str, dict)  # (fen, options)
    continuationSelected = QtCore.pyqtSignal(list)  # list of moves (SAN or UCI)
    moveHovered = QtCore.pyqtSignal(object, object)  # (fen | None, uci | None)
    buildHotIndexRequested = QtCore.pyqtSignal()
    statusMessage = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_fen: Optional[str] = None
        self.current_report: Optional[dict] = None
        self.is_dark = QtCore.QSettings("QChessApp", "Theme").value("theme", "dark") == "dark"
        self._lines_data: List[dict] = []

        settings = QtCore.QSettings("TestChessApp", "Config")
        self.max_lines = int(settings.value("continuations_max_lines", 6))
        if self.max_lines < 1:
            self.max_lines = 1
        elif self.max_lines > 20:
            self.max_lines = 20

        self.depth = 8
        self.min_games = 1
        self.min_pct = 0.0

        self.init_ui()
        self.set_theme(self.is_dark)

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(2)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        # 1. Main Continuations Table (Headerless)
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.horizontalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Interactive)
        self.table.horizontalHeader().resizeSection(2, 120)
        self.table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setItemDelegate(NoFocusDelegate(self.table))
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        content_layout.addWidget(self.table, stretch=1)

        # 2. Right-side Line Control Widget (+ / N / -)
        self.lines_ctrl_widget = QtWidgets.QWidget(self)
        self.lines_ctrl_widget.setFixedWidth(24)
        v_layout = QtWidgets.QVBoxLayout(self.lines_ctrl_widget)
        v_layout.setContentsMargins(0, 2, 0, 2)
        v_layout.setSpacing(2)

        from utils.helpers import _qicon

        self.btn_plus_lines = QtWidgets.QToolButton(self.lines_ctrl_widget)
        self.btn_plus_lines.setIcon(_qicon("fa6s.plus", is_dark=self.is_dark))
        self.btn_plus_lines.setIconSize(QtCore.QSize(10, 10))
        self.btn_plus_lines.setFixedSize(22, 22)
        self.btn_plus_lines.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_plus_lines.setToolTip("More continuation lines")
        self.btn_plus_lines.clicked.connect(self.increment_lines)

        self.lbl_lines = QtWidgets.QLabel(f"{self.max_lines}", self.lines_ctrl_widget)
        self.lbl_lines.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))
        self.lbl_lines.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_lines.setToolTip(f"Show top {self.max_lines} continuation lines")

        self.btn_minus_lines = QtWidgets.QToolButton(self.lines_ctrl_widget)
        self.btn_minus_lines.setIcon(_qicon("fa6s.minus", is_dark=self.is_dark))
        self.btn_minus_lines.setIconSize(QtCore.QSize(10, 10))
        self.btn_minus_lines.setFixedSize(22, 22)
        self.btn_minus_lines.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_minus_lines.setToolTip("Fewer continuation lines")
        self.btn_minus_lines.clicked.connect(self.decrement_lines)

        v_layout.addWidget(self.btn_plus_lines)
        v_layout.addWidget(self.lbl_lines)
        v_layout.addWidget(self.btn_minus_lines)
        v_layout.addStretch()

        content_layout.addWidget(self.lines_ctrl_widget)
        main_layout.addLayout(content_layout)

        # Status / Empty Label overlay
        self.status_label = QtWidgets.QLabel("Open a database and navigate to explore common continuations.", self)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
        main_layout.addWidget(self.status_label)

    def increment_lines(self):
        if self.max_lines < 20:
            self.max_lines += 1
            self._update_lines_state()

    def decrement_lines(self):
        if self.max_lines > 1:
            self.max_lines -= 1
            self._update_lines_state()

    def _update_lines_state(self):
        self.lbl_lines.setText(str(self.max_lines))
        self.lbl_lines.setToolTip(f"Show top {self.max_lines} continuation lines")
        self.btn_minus_lines.setEnabled(self.max_lines > 1)
        self.btn_plus_lines.setEnabled(self.max_lines < 20)
        QtCore.QSettings("TestChessApp", "Config").setValue("continuations_max_lines", self.max_lines)
        if self.current_fen and self.isVisible():
            self.trigger_query()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        from utils.helpers import _qicon
        self.btn_plus_lines.setIcon(_qicon("fa6s.plus", is_dark=is_dark))
        self.btn_minus_lines.setIcon(_qicon("fa6s.minus", is_dark=is_dark))

        bg = "#262421" if is_dark else "#ffffff"
        text_color = "#bababa" if is_dark else "#0f172a"
        sel_bg = "#1e3a5f" if is_dark else "#2563eb"
        sel_color = "#ffffff"
        btn_bg = "#312e2b" if is_dark else "#f1f5f9"
        btn_border = "#403d39" if is_dark else "#cbd5e1"
        btn_hover = "#3f3c38" if is_dark else "#e2e8f0"
        lbl_color = "#f8fafc" if is_dark else "#0f172a"

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg};
                color: {text_color};
                border: none;
                font-size: 11px;
                selection-background-color: {sel_bg};
                selection-color: {sel_color};
                outline: none;
            }}
            QTableWidget::item {{
                outline: none;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {sel_bg};
                color: {sel_color};
                outline: none;
                border: none;
            }}
            QTableWidget::item:focus {{
                outline: none;
                border: none;
            }}
            QTableWidget::item:selected:focus {{
                background-color: {sel_bg};
                color: {sel_color};
                outline: none;
                border: none;
            }}
        """)

        btn_style = f"""
            QToolButton {{
                background-color: {btn_bg};
                color: {lbl_color};
                border: 1px solid {btn_border};
                border-radius: 3px;
                padding: 1px;
            }}
            QToolButton:hover {{
                background-color: {btn_hover};
            }}
            QToolButton:disabled {{
                opacity: 0.4;
            }}
        """
        self.btn_plus_lines.setStyleSheet(btn_style)
        self.btn_minus_lines.setStyleSheet(btn_style)
        self.lbl_lines.setStyleSheet(f"color: {lbl_color}; font-weight: bold; font-size: 10px;")
        self.status_label.setStyleSheet("color: #94a3b8; font-style: italic; padding: 20px;" if is_dark else "color: #64748b; font-style: italic; padding: 20px;")

        for row in range(self.table.rowCount()):
            w = self.table.cellWidget(row, 2)
            if isinstance(w, ContinuationPercentageBar):
                w.set_theme(is_dark)

    def set_position(self, fen: str):
        self.current_fen = fen

    def trigger_query(self):
        if not self.current_fen:
            return

        options = {
            "max_depth": 8,
            "max_lines": self.max_lines,
            "min_games": 1,
            "min_percentage": 0.0,
        }
        self.queryRequested.emit(self.current_fen, options)

    def set_report(self, report: dict):
        self.current_report = report
        lines = report.get("lines", [])
        pos_games = report.get("games_reaching_position", 0)
        self._lines_data = lines

        if not lines:
            self.table.setRowCount(0)
            self.table.hide()
            self.status_label.setText(
                f"No continuations found ({pos_games:,} games reach this position)."
            )
            self.status_label.show()
            return

        self.status_label.hide()
        self.table.show()
        self.table.setRowCount(len(lines))

        for row, line_info in enumerate(lines):
            formatted_moves = line_info.get("formatted", " ".join(line_info.get("moves", [])))
            games = line_info.get("games", 0)
            pct = line_info.get("percentage", 0.0)
            w_win = line_info.get("white_wins", 0)
            draws = line_info.get("draws", 0)
            b_win = line_info.get("black_wins", 0)

            # Col 0: Formatted Line
            item_line = QtWidgets.QTableWidgetItem(formatted_moves)
            item_line.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.DemiBold))
            item_line.setData(QtCore.Qt.UserRole, line_info)
            self.table.setItem(row, 0, item_line)

            # Col 1: Games & Percentage
            item_games = QtWidgets.QTableWidgetItem(f"{games:,} ({pct:.1f}%)")
            item_games.setTextAlignment(QtCore.Qt.AlignCenter)
            item_games.setFont(QtGui.QFont("Segoe UI", 9))
            self.table.setItem(row, 1, item_games)

            # Col 2: Score Bar
            bar = ContinuationPercentageBar(w_win, draws, b_win, self)
            bar.set_theme(self.is_dark)
            self.table.setCellWidget(row, 2, bar)

            # Col 3: Last Date / Year
            last_year = line_info.get("last_year") or line_info.get("last_played") or line_info.get("year")
            year_str = str(last_year) if last_year else "-"
            item_year = QtWidgets.QTableWidgetItem(year_str)
            item_year.setFont(QtGui.QFont("Segoe UI", 9))
            item_year.setTextAlignment(QtCore.Qt.AlignCenter)
            item_year.setToolTip(f"Last played: {year_str}")
            self.table.setItem(row, 3, item_year)

            self.table.setRowHeight(row, 24)

    def show_status(self, text: str):
        self.table.setRowCount(0)
        self.table.hide()
        self.status_label.setText(text)
        self.status_label.show()

    def set_progress(self, scanned: int, total: int, percent: float):
        self.table.hide()
        self.status_label.setText(f"Scanning database... {scanned:,} / {total:,} games ({percent:.1f}%)")
        self.status_label.show()

    def _on_item_double_clicked(self, item: QtWidgets.QTableWidgetItem):
        row = item.row()
        if 0 <= row < len(self._lines_data):
            moves = self._lines_data[row].get("moves", [])
            if moves:
                self.continuationSelected.emit(moves)

    def _on_selection_changed(self):
        pass
