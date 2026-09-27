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


class ContinuationsWidget(QtWidgets.QWidget):
    """
    ChessBase-style Common Continuations Explorer & Multi-Move Sequence Analyzer.
    - Queries top multi-move continuation paths for any position from scid-mgr.
    - Supports binary graph (.hot.idx) or on-the-fly candidate search.
    - Double-click a continuation line to play it on the board.
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
        self.is_dark = True
        self._lines_data: List[dict] = []

        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 1. Controls / Parameters Bar
        self.controls_frame = QtWidgets.QFrame(self)
        self.controls_frame.setObjectName("ContinuationsControlsFrame")
        c_layout = QtWidgets.QHBoxLayout(self.controls_frame)
        c_layout.setContentsMargins(6, 4, 6, 4)
        c_layout.setSpacing(6)

        # Depth
        lbl_depth = QtWidgets.QLabel("Depth:")
        lbl_depth.setStyleSheet("font-weight: 600; font-size: 11px;")
        c_layout.addWidget(lbl_depth)

        self.spin_depth = QtWidgets.QSpinBox()
        self.spin_depth.setRange(1, 24)
        self.spin_depth.setValue(8)
        self.spin_depth.setSuffix(" plies")
        self.spin_depth.setToolTip("Maximum continuation depth (plies / half-moves)")
        self.spin_depth.valueChanged.connect(self._on_param_changed)
        c_layout.addWidget(self.spin_depth)

        # Max Lines
        lbl_lines = QtWidgets.QLabel("Lines:")
        lbl_lines.setStyleSheet("font-weight: 600; font-size: 11px;")
        c_layout.addWidget(lbl_lines)

        self.spin_max_lines = QtWidgets.QSpinBox()
        self.spin_max_lines.setRange(1, 30)
        self.spin_max_lines.setValue(10)
        self.spin_max_lines.setToolTip("Maximum continuation lines to display")
        self.spin_max_lines.valueChanged.connect(self._on_param_changed)
        c_layout.addWidget(self.spin_max_lines)

        # Min Games
        lbl_min_games = QtWidgets.QLabel("Min Games:")
        lbl_min_games.setStyleSheet("font-weight: 600; font-size: 11px;")
        c_layout.addWidget(lbl_min_games)

        self.spin_min_games = QtWidgets.QSpinBox()
        self.spin_min_games.setRange(1, 10000)
        self.spin_min_games.setValue(1)
        self.spin_min_games.setToolTip("Filter out lines occurring fewer than N times")
        self.spin_min_games.valueChanged.connect(self._on_param_changed)
        c_layout.addWidget(self.spin_min_games)

        # Min %
        lbl_min_pct = QtWidgets.QLabel("Min %:")
        lbl_min_pct.setStyleSheet("font-weight: 600; font-size: 11px;")
        c_layout.addWidget(lbl_min_pct)

        self.spin_min_pct = QtWidgets.QDoubleSpinBox()
        self.spin_min_pct.setRange(0.0, 100.0)
        self.spin_min_pct.setValue(0.0)
        self.spin_min_pct.setSingleStep(1.0)
        self.spin_min_pct.setSuffix("%")
        self.spin_min_pct.setToolTip("Minimum percentage share of position games")
        self.spin_min_pct.valueChanged.connect(self._on_param_changed)
        c_layout.addWidget(self.spin_min_pct)

        c_layout.addStretch()

        # Auto-query
        self.chk_auto = QtWidgets.QCheckBox("Auto")
        self.chk_auto.setChecked(True)
        self.chk_auto.setToolTip("Automatically calculate continuations on position change")
        c_layout.addWidget(self.chk_auto)

        # Manual Query Button
        self.btn_query = QtWidgets.QPushButton("▶ Query")
        self.btn_query.setToolTip("Run common continuations analysis for current position")
        self.btn_query.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_query.clicked.connect(self.trigger_query)
        c_layout.addWidget(self.btn_query)

        layout.addWidget(self.controls_frame)
        self.controls_frame.hide()  # Hidden by default to maximize space

        # 2. Summary Status Frame (Header with Options Toggle)
        self.summary_frame = QtWidgets.QFrame(self)
        self.summary_frame.setObjectName("ContinuationsSummaryFrame")
        s_layout = QtWidgets.QHBoxLayout(self.summary_frame)
        s_layout.setContentsMargins(6, 3, 6, 3)
        s_layout.setSpacing(10)

        # Toggle Controls Button
        self.btn_toggle_controls = QtWidgets.QPushButton("⚙ Options")
        self.btn_toggle_controls.setCheckable(True)
        self.btn_toggle_controls.setChecked(False)
        self.btn_toggle_controls.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_toggle_controls.setToolTip("Show / Hide Continuation Query Parameters (Depth, Lines, Min Games, Min %)")
        self.btn_toggle_controls.toggled.connect(self.controls_frame.setVisible)
        s_layout.addWidget(self.btn_toggle_controls)

        self.lbl_pos_games = QtWidgets.QLabel("Position Games: -")
        self.lbl_pos_games.setStyleSheet("font-weight: bold; font-size: 11px;")
        s_layout.addWidget(self.lbl_pos_games)

        self.lbl_total_db = QtWidgets.QLabel("Total DB Games: -")
        self.lbl_total_db.setStyleSheet("font-size: 11px; color: #888;")
        s_layout.addWidget(self.lbl_total_db)

        s_layout.addStretch()

        self.lbl_source_badge = QtWidgets.QLabel("⚡ Ready")
        self.lbl_source_badge.setStyleSheet("font-weight: 600; font-size: 11px; color: #2e7d32;")
        s_layout.addWidget(self.lbl_source_badge)

        layout.addWidget(self.summary_frame)

        # 3. Main Continuations Table
        self.table = QtWidgets.QTableWidget(self)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Continuation Line", "Games (%)", "Score (W / D / B)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        self.table.horizontalHeader().resizeSection(2, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table, stretch=1)

        # Status / Empty Label overlay
        self.status_label = QtWidgets.QLabel("Open a database and navigate to explore common continuations.", self)
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
        layout.addWidget(self.status_label)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        if is_dark:
            self.controls_frame.setStyleSheet(
                "QFrame#ContinuationsControlsFrame { background-color: #21201d; border-radius: 4px; border: 1px solid #383531; }"
            )
            self.summary_frame.setStyleSheet(
                "QFrame#ContinuationsSummaryFrame { background-color: #262421; border-radius: 4px; border: 1px solid #383531; }"
            )
            self.btn_toggle_controls.setStyleSheet("""
                QPushButton {
                    background-color: #312e2b;
                    color: #e2e8f0;
                    border: 1px solid #403d39;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #3f3c38;
                }
                QPushButton:checked {
                    background-color: #1e3a5f;
                    border: 1px solid #3b82f6;
                    color: #60a5fa;
                }
            """)
            self.lbl_pos_games.setStyleSheet("font-weight: bold; font-size: 11px; color: #e2e8f0;")
            self.lbl_total_db.setStyleSheet("font-size: 11px; color: #94a3b8;")
            self.status_label.setStyleSheet("color: #94a3b8; font-style: italic; padding: 20px;")
        else:
            self.controls_frame.setStyleSheet(
                "QFrame#ContinuationsControlsFrame { background-color: #f1f5f9; border-radius: 4px; border: 1px solid #cbd5e1; }"
            )
            self.summary_frame.setStyleSheet(
                "QFrame#ContinuationsSummaryFrame { background-color: #f8fafc; border-radius: 4px; border: 1px solid #cbd5e1; }"
            )
            self.btn_toggle_controls.setStyleSheet("""
                QPushButton {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 3px;
                    padding: 2px 8px;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #f1f5f9;
                }
                QPushButton:checked {
                    background-color: #dbeafe;
                    border: 1px solid #2563eb;
                    color: #1d4ed8;
                }
            """)
            self.lbl_pos_games.setStyleSheet("font-weight: bold; font-size: 11px; color: #0f172a;")
            self.lbl_total_db.setStyleSheet("font-size: 11px; color: #64748b;")
            self.status_label.setStyleSheet("color: #64748b; font-style: italic; padding: 20px;")

        # Update percentage bars in table
        for r in range(self.table.rowCount()):
            cell_widget = self.table.cellWidget(r, 2)
            if isinstance(cell_widget, ContinuationPercentageBar):
                cell_widget.set_theme(is_dark)

    def set_position(self, fen: str):
        self.current_fen = fen
        if self.chk_auto.isChecked() and self.isVisible():
            self.trigger_query()

    def trigger_query(self):
        if not self.current_fen:
            return

        options = {
            "max_depth": self.spin_depth.value(),
            "max_lines": self.spin_max_lines.value(),
            "min_games": self.spin_min_games.value(),
            "min_percentage": self.spin_min_pct.value(),
        }
        self.lbl_source_badge.setText("⏳ Calculating...")
        self.lbl_source_badge.setStyleSheet("font-weight: 600; font-size: 11px; color: #b86f1b;")
        self.queryRequested.emit(self.current_fen, options)

    def _on_param_changed(self):
        if self.chk_auto.isChecked() and self.current_fen and self.isVisible():
            self.trigger_query()

    def set_report(self, report: dict):
        self.current_report = report
        lines = report.get("lines", [])
        total_db = report.get("total_games_processed", 0)
        pos_games = report.get("games_reaching_position", 0)
        source = report.get("source", "hot_graph" if report.get("from_hot_graph") else "dynamic")

        self.lbl_pos_games.setText(f"Position Games: {pos_games:,}")
        self.lbl_total_db.setText(f"Total DB Games: {total_db:,}")

        if "hot" in str(source).lower():
            self.lbl_source_badge.setText("⚡ Precomputed .hot.idx")
            self.lbl_source_badge.setStyleSheet("font-weight: 600; font-size: 11px; color: #2e7d32;")
        else:
            self.lbl_source_badge.setText("⚡ Dynamic Candidate Search")
            self.lbl_source_badge.setStyleSheet("font-weight: 600; font-size: 11px; color: #0284c7;")

        self._lines_data = lines

        if not lines:
            self.table.setRowCount(0)
            self.table.hide()
            self.status_label.setText(
                f"No continuations found matching criteria ({pos_games:,} games reach this position)."
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

    def show_status(self, text: str):
        self.table.setRowCount(0)
        self.table.hide()
        self.status_label.setText(text)
        self.status_label.show()
        self.lbl_source_badge.setText("Ready")
        self.lbl_source_badge.setStyleSheet("font-weight: 600; font-size: 11px; color: #888;")

    def _on_item_double_clicked(self, item: QtWidgets.QTableWidgetItem):
        row = item.row()
        if 0 <= row < len(self._lines_data):
            moves = self._lines_data[row].get("moves", [])
            if moves:
                self.continuationSelected.emit(moves)

    def _on_selection_changed(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            if 0 <= row < len(self._lines_data):
                moves = self._lines_data[row].get("moves", [])
                # Hover preview or notification can be emitted
                pass
