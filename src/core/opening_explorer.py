import os
import sys
from typing import Optional, List, Dict, Any
from PyQt5 import QtCore, QtGui, QtWidgets


class OpeningExplorerHeader(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)

        self.move_lbl = QtWidgets.QLabel("Move")
        self.move_lbl.setFixedWidth(60)

        self.stats_lbl = QtWidgets.QLabel("Stats (W / D / B)")
        self.stats_lbl.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(self.move_lbl)
        layout.addWidget(self.stats_lbl)

        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        bg = "#141312" if is_dark else "#e2e8f0"
        color = "#f8fafc" if is_dark else "#0f172a"
        border_c = "#383531" if is_dark else "#cbd5e1"
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg};
                border-bottom: 1px solid {border_c};
                border-top: 1px solid {border_c};
            }}
        """)
        style = f"color: {color}; font-weight: bold; font-size: 11px; background: transparent; border: none;"
        self.move_lbl.setStyleSheet(style)
        self.stats_lbl.setStyleSheet(style)


class PercentageBar(QtWidgets.QWidget):
    def __init__(self, white_win: int, draw: int, black_win: int, avg_white_elo=None, avg_black_elo=None, parent=None):
        super().__init__(parent)
        self.white_win = int(white_win)
        self.draw = int(draw)
        self.black_win = int(black_win)
        self.avg_white_elo = avg_white_elo
        self.avg_black_elo = avg_black_elo
        self.setFixedHeight(24)
        self.is_dark = True

        # Calculate percentages and set tooltip
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
            if self.avg_white_elo or self.avg_black_elo:
                w_elo = self.avg_white_elo or "?"
                b_elo = self.avg_black_elo or "?"
                tooltip += f"\nAvg Elo: ♔ {w_elo} / ♚ {b_elo}"
            self.setToolTip(tooltip)
        else:
            self.setToolTip("No games played")

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

        # Colors
        color_white = QtGui.QColor("#ffffff")
        color_draw = QtGui.QColor("#94a3b8")
        color_black = QtGui.QColor("#1e293b" if not self.is_dark else "#312e2b")

        painter.setPen(QtCore.Qt.NoPen)

        # White
        if pw > 0:
            painter.setBrush(color_white)
            painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if not self.is_dark:
                # Add subtle border around white bar in light mode
                painter.setPen(QtGui.QPen(QtGui.QColor("#cbd5e1"), 1))
                painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if pw > 25:
                painter.setPen(QtGui.QColor("#0f172a"))
                painter.drawText(
                    QtCore.QRectF(0, 0, pw, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.white_win}",
                )

        # Draw
        if pd > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_draw)
            painter.drawRect(QtCore.QRectF(pw, 0, pd, h))
            if pd > 25:
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.drawText(
                    QtCore.QRectF(pw, 0, pd, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.draw}",
                )

        # Black
        if pb > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_black)
            painter.drawRect(QtCore.QRectF(pw + pd, 0, pb, h))
            if pb > 25:
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.drawText(
                    QtCore.QRectF(pw + pd, 0, pb, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.black_win}",
                )


class MoveItem(QtWidgets.QWidget):
    moveClicked = QtCore.pyqtSignal(str)

    def __init__(self, move_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.move_data = move_data
        self.move_text = move_data.get("san") or move_data.get("move") or move_data.get("uci") or ""
        self.move_uci = move_data.get("uci") or self.move_text

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        self.move_lbl = QtWidgets.QLabel(self.move_text)
        self.move_lbl.setFixedWidth(60)

        white_wins = move_data.get("white_wins", 0)
        draws = move_data.get("draws", 0)
        black_wins = move_data.get("black_wins", 0)
        avg_w = move_data.get("avg_white_elo")
        avg_b = move_data.get("avg_black_elo")

        self.bar = PercentageBar(
            white_wins, draws, black_wins, avg_white_elo=avg_w, avg_black_elo=avg_b, parent=self
        )

        layout.addWidget(self.move_lbl)
        layout.addWidget(self.bar)

        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        color = "#f8fafc" if is_dark else "#0f172a"
        self.move_lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 13px;"
        )
        self.bar.set_theme(is_dark)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.moveClicked.emit(self.move_uci)
        super().mousePressEvent(event)


class SampleGamesTable(QtWidgets.QTableWidget):
    gameSelected = QtCore.pyqtSignal(int, dict)  # (game_id, game_summary)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["White", "Res", "Black", "Date", "ECO"])
        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setShowGrid(True)  # show grid lines for clearer table look
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)  # enable column sorting
        self.is_dark = True
        self.games_data = []

        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        alt_bg = "#2b2926" if is_dark else "#f8fafc"
        text_color = "#bababa" if is_dark else "#0f172a"
        header_bg = "#141312" if is_dark else "#e2e8f0"
        header_text = "#f8fafc" if is_dark else "#0f172a"
        border_r = "#383531" if is_dark else "#cbd5e1"
        sel_bg = "#44413c" if is_dark else "#dbeafe"
        sel_color = "#f8fafc" if is_dark else "#1e3a8a"

        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg};
                alternate-background-color: {alt_bg};
                color: {text_color};
                border: none;
                font-size: 11px;
                selection-background-color: {sel_bg};
                selection-color: {sel_color};
            }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {header_text};
                border: none;
                border-right: 1px solid {border_r};
                border-bottom: 1px solid {border_r};
                padding: 4px 6px;
                font-weight: bold;
                font-size: 10px;
            }}
        """)

    def update_games(self, games: List[Dict[str, Any]]):
        self.setSortingEnabled(False)
        self.games_data = games
        self.setRowCount(len(games))

        for row, g in enumerate(games):
            w_name = g.get("white", "?")
            w_elo = g.get("white_elo", 0)
            white_str = f"{w_name} ({w_elo})" if w_elo else w_name

            b_name = g.get("black", "?")
            b_elo = g.get("black_elo", 0)
            black_str = f"{b_name} ({b_elo})" if b_elo else b_name

            res_str = g.get("result", "*")
            date_str = str(g.get("date", "")).replace(".??", "").replace(".?", "")
            eco_str = g.get("eco", "")

            item_w = QtWidgets.QTableWidgetItem(white_str)
            item_w.setData(QtCore.Qt.UserRole, g)
            item_r = QtWidgets.QTableWidgetItem(res_str)
            item_b = QtWidgets.QTableWidgetItem(black_str)
            item_d = QtWidgets.QTableWidgetItem(date_str)
            item_e = QtWidgets.QTableWidgetItem(eco_str)

            item_r.setTextAlignment(QtCore.Qt.AlignCenter)
            item_d.setTextAlignment(QtCore.Qt.AlignCenter)
            item_e.setTextAlignment(QtCore.Qt.AlignCenter)

            item_w.setToolTip(f"{w_name} vs {b_name}\nEvent: {g.get('event', '')}\nSite: {g.get('site', '')}")
            item_b.setToolTip(f"{w_name} vs {b_name}\nEvent: {g.get('event', '')}\nSite: {g.get('site', '')}")

            self.setItem(row, 0, item_w)
            self.setItem(row, 1, item_r)
            self.setItem(row, 2, item_b)
            self.setItem(row, 3, item_d)
            self.setItem(row, 4, item_e)
            self.setRowHeight(row, 24)

        self.setSortingEnabled(True)

    def _on_cell_double_clicked(self, row: int, column: int):
        item = self.item(row, 0)
        if item:
            g = item.data(QtCore.Qt.UserRole)
            if isinstance(g, dict):
                game_id = g.get("id")
                if game_id is not None:
                    self.gameSelected.emit(int(game_id), g)
                    return
        if 0 <= row < len(self.games_data):
            g = self.games_data[row]
            game_id = g.get("id")
            if game_id is not None:
                self.gameSelected.emit(int(game_id), g)


class OpeningExplorer(QtWidgets.QWidget):
    moveSelected = QtCore.pyqtSignal(str)
    sampleGameSelected = QtCore.pyqtSignal(int, dict)

    def __init__(self, parent=None, positions=None):
        super().__init__(parent)
        self.is_dark = True
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Main vertical splitter
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.splitter.setChildrenCollapsible(False)

        # --- Top Section: Moves ---
        self.moves_container = QtWidgets.QWidget(self.splitter)
        moves_layout = QtWidgets.QVBoxLayout(self.moves_container)
        moves_layout.setContentsMargins(0, 0, 0, 0)
        moves_layout.setSpacing(0)

        self.header = OpeningExplorerHeader(self.moves_container)
        moves_layout.addWidget(self.header)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(1)
        self.container_layout.addStretch()

        self.scroll.setWidget(self.container)
        moves_layout.addWidget(self.scroll)

        self.status_lbl = QtWidgets.QLabel(self.container)
        self.status_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.status_lbl.setStyleSheet("color: #8b8987; font-style: italic; font-size: 11px; padding: 12px;")
        self.status_lbl.setText("Open a database to explore positions.")
        self.status_lbl.show()
        self.container_layout.insertWidget(0, self.status_lbl)

        # --- Bottom Section: Sample Games ---
        self.games_container = QtWidgets.QWidget(self.splitter)
        games_layout = QtWidgets.QVBoxLayout(self.games_container)
        games_layout.setContentsMargins(0, 0, 0, 0)
        games_layout.setSpacing(0)

        self.games_table = SampleGamesTable(self.games_container)
        self.games_table.gameSelected.connect(self.sampleGameSelected.emit)
        games_layout.addWidget(self.games_table)

        self.games_status_lbl = QtWidgets.QLabel(self.games_container)
        self.games_status_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.games_status_lbl.setStyleSheet("color: #8b8987; font-style: italic; font-size: 11px; padding: 12px;")
        self.games_status_lbl.setText("No sample games available.")
        self.games_status_lbl.hide()
        games_layout.addWidget(self.games_status_lbl)

        self.splitter.addWidget(self.moves_container)
        self.splitter.addWidget(self.games_container)
        self.splitter.setSizes([260, 180])

        self.main_layout.addWidget(self.splitter)

        self.set_theme(True)

        if positions:
            self.update_positions(positions)

    def show_loading(self, message: str = "Querying opening tree..."):
        self._clear_move_items()
        self.status_lbl.setText(message)
        self.status_lbl.show()
        self.games_table.setRowCount(0)
        self.games_status_lbl.setText(message)
        self.games_status_lbl.show()

    def show_status(self, message: str):
        self._clear_move_items()
        self.status_lbl.setText(message)
        self.status_lbl.show()
        self.games_table.setRowCount(0)
        self.games_status_lbl.setText(message)
        self.games_status_lbl.show()

    def _clear_move_items(self):
        while self.container_layout.count() > 2:
            item = self.container_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        color = "#94a3b8" if is_dark else "#64748b"
        splitter_handle = "#3a3734" if is_dark else "#cbd5e1"

        self.setStyleSheet(f"background-color: {bg};")
        self.splitter.setStyleSheet(f"""
            QSplitter::handle:vertical {{
                background-color: {splitter_handle};
                height: 2px;
            }}
        """)
        self.status_lbl.setStyleSheet(f"color: {color}; font-style: italic; font-size: 11px; padding: 12px;")
        self.games_status_lbl.setStyleSheet(f"color: {color}; font-style: italic; font-size: 11px; padding: 12px;")
        self.header.set_theme(is_dark)
        self.games_table.set_theme(is_dark)

        for i in range(self.container_layout.count()):
            w = self.container_layout.itemAt(i).widget()
            if isinstance(w, MoveItem):
                w.set_theme(is_dark)

    def update_positions(self, positions: List[Dict[str, Any]]):
        self._clear_move_items()

        if not positions:
            self.status_lbl.setText("No games found in this position.")
            self.status_lbl.show()
            return

        self.status_lbl.hide()
        for move_data in positions:
            item = MoveItem(move_data, self)
            item.set_theme(self.is_dark)
            item.moveClicked.connect(self.moveSelected.emit)
            self.container_layout.insertWidget(self.container_layout.count() - 1, item)

    def update_sample_games(self, sample_games: List[Dict[str, Any]]):
        if not sample_games:
            self.games_table.setRowCount(0)
            self.games_status_lbl.setText("No sample games found.")
            self.games_status_lbl.show()
            return

        self.games_status_lbl.hide()
        self.games_table.update_games(sample_games)


class OpeningExplorerLogic(QtWidgets.QWidget):
    """
    Pure UI Widget for Opening Explorer with filters.
    Completely decoupled from databases, SQLite, or backend processes.
    Emits queryRequested(fen, filters) to let the controller fetch statistics.
    """
    queryRequested = QtCore.pyqtSignal(str, dict)  # (fen, filters)
    moveSelected = QtCore.pyqtSignal(str)          # (move_uci)
    sampleGameSelected = QtCore.pyqtSignal(int, dict)  # (game_id, game_summary)
    errorOcurred = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.explorer = OpeningExplorer(self)
        self.explorer.moveSelected.connect(self.moveSelected.emit)
        self.explorer.sampleGameSelected.connect(self.sampleGameSelected.emit)
        self.last_fen = None
        self.is_dark = True

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header / toggle button
        self.toggle_filters_btn = QtWidgets.QPushButton("🔍 Filters", self)
        self.toggle_filters_btn.setCheckable(True)
        self.toggle_filters_btn.setChecked(False)
        self.toggle_filters_btn.clicked.connect(self.toggle_filter_panel)
        layout.addWidget(self.toggle_filters_btn)

        # Build Filter Frame
        self.filter_frame = QtWidgets.QFrame(self)
        self.filter_frame.setVisible(False)
        self.filter_frame.setObjectName("FilterFrame")

        filter_layout = QtWidgets.QFormLayout(self.filter_frame)
        filter_layout.setContentsMargins(8, 8, 8, 8)
        filter_layout.setSpacing(6)

        # Player Row
        self.player_input = QtWidgets.QLineEdit()
        self.player_input.setPlaceholderText("Player name...")
        self.player_color_combo = QtWidgets.QComboBox()
        self.player_color_combo.addItems(["Either Color", "As White", "As Black"])

        player_layout = QtWidgets.QHBoxLayout()
        player_layout.addWidget(self.player_input, 2)
        player_layout.addWidget(self.player_color_combo, 1)
        player_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addRow("Player:", player_layout)

        # Rating Row
        self.min_rating_spin = QtWidgets.QSpinBox()
        self.min_rating_spin.setRange(0, 3500)
        self.min_rating_spin.setValue(0)
        self.min_rating_spin.setSpecialValueText("Any")

        self.max_rating_spin = QtWidgets.QSpinBox()
        self.max_rating_spin.setRange(0, 3500)
        self.max_rating_spin.setValue(0)
        self.max_rating_spin.setSpecialValueText("Any")

        rating_layout = QtWidgets.QHBoxLayout()
        rating_layout.addWidget(QtWidgets.QLabel("Min:"))
        rating_layout.addWidget(self.min_rating_spin)
        rating_layout.addWidget(QtWidgets.QLabel("Max:"))
        rating_layout.addWidget(self.max_rating_spin)
        rating_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addRow("Rating:", rating_layout)

        # ECO / Result Row
        self.eco_input = QtWidgets.QLineEdit()
        self.eco_input.setPlaceholderText("e.g. B01")
        self.eco_input.setMaxLength(3)

        self.result_combo = QtWidgets.QComboBox()
        self.result_combo.addItems(["Any", "1-0", "0-1", "1/2-1/2"])

        eco_result_layout = QtWidgets.QHBoxLayout()
        eco_result_layout.addWidget(self.eco_input, 1)
        eco_result_layout.addWidget(QtWidgets.QLabel("Result:"), 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        eco_result_layout.addWidget(self.result_combo, 2)
        eco_result_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addRow("ECO:", eco_result_layout)

        # Action Buttons
        self.apply_btn = QtWidgets.QPushButton("Apply Filters")
        self.apply_btn.clicked.connect(self.apply_filters)
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_filters)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addRow("", btn_layout)

        layout.addWidget(self.filter_frame)
        layout.addWidget(self.explorer)

        # Connect inputs to apply automatically where appropriate
        self.player_input.returnPressed.connect(self.apply_filters)
        self.eco_input.returnPressed.connect(self.apply_filters)
        self.player_color_combo.currentIndexChanged.connect(self.apply_filters)
        self.result_combo.currentIndexChanged.connect(self.apply_filters)

    def toggle_filter_panel(self, checked):
        self.filter_frame.setVisible(checked)

    def get_filters(self) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        player = self.player_input.text().strip()
        if player:
            color_idx = self.player_color_combo.currentIndex()
            if color_idx == 1:
                filters["white"] = player
            elif color_idx == 2:
                filters["black"] = player
            else:
                filters["player"] = player

        min_r = self.min_rating_spin.value()
        if min_r > 0:
            filters["min_rating"] = min_r

        max_r = self.max_rating_spin.value()
        if max_r > 0:
            filters["max_rating"] = max_r

        eco = self.eco_input.text().strip()
        if eco:
            filters["eco"] = eco

        result = self.result_combo.currentText()
        if result != "Any":
            filters["result"] = result

        return filters

    def apply_filters(self):
        if self.last_fen:
            self.send_fen(self.last_fen, force=True)

    def clear_filters(self):
        self.player_input.clear()
        self.player_color_combo.setCurrentIndex(0)
        self.min_rating_spin.setValue(0)
        self.max_rating_spin.setValue(0)
        self.eco_input.clear()
        self.result_combo.setCurrentIndex(0)
        self.apply_filters()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.explorer.set_theme(is_dark)

        # Style filter panel
        if is_dark:
            bg_color = "#262421"
            text_color = "#ffffff"
            input_bg = "#312e2b"
            input_border = "#44413c"
            btn_bg = "#3c3934"
            btn_hover_bg = "#4c4943"
            label_color = "#94a3b8"
            toggle_bg = "#312e2b"
            toggle_color = "#bababa"
            toggle_hover = "#3c3934"
            toggle_checked = "#211f1d"
        else:
            bg_color = "#ffffff"
            text_color = "#0f172a"
            input_bg = "#ffffff"
            input_border = "#cbd5e1"
            btn_bg = "#f1f5f9"
            btn_hover_bg = "#e2e8f0"
            label_color = "#475569"
            toggle_bg = "#f1f5f9"
            toggle_color = "#334155"
            toggle_hover = "#e2e8f0"
            toggle_checked = "#dbeafe"

        frame_style = f"background-color: {bg_color}; border-bottom: 1px solid {input_border};"
        self.filter_frame.setStyleSheet(f"QFrame#FilterFrame {{ {frame_style} }}")

        label_style = f"color: {label_color}; font-weight: bold;"
        for lbl in self.filter_frame.findChildren(QtWidgets.QLabel):
            lbl.setStyleSheet(label_style)

        input_style = f"""
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 4px 6px;
            }}
        """
        for widget in self.filter_frame.findChildren((QtWidgets.QLineEdit, QtWidgets.QComboBox, QtWidgets.QSpinBox)):
            widget.setStyleSheet(input_style)

        btn_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_color};
                border: 1px solid {input_border};
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {btn_hover_bg};
            }}
        """
        self.apply_btn.setStyleSheet(btn_style)
        self.clear_btn.setStyleSheet(btn_style)

        self.toggle_filters_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {toggle_bg};
                color: {toggle_color};
                border: none;
                padding: 6px 10px;
                font-weight: bold;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {toggle_hover};
                color: {text_color};
            }}
            QPushButton:checked {{
                background-color: {toggle_checked};
                color: {'#ffffff' if is_dark else '#1e3a8a'};
            }}
        """)

    def set_tree_data(self, data: Any):
        """
        Accepts OpeningTreeReport dictionary returned by scid-mgr or list of moves.
        """
        if isinstance(data, dict):
            moves = data.get("moves", [])
            sample_games = data.get("sample_games", [])
        elif isinstance(data, list):
            moves = data
            sample_games = []
        else:
            moves = []
            sample_games = []

        if moves:
            # Sort by total games played descending
            moves = sorted(
                moves,
                key=lambda x: x.get("total_games", x.get("white_wins", 0) + x.get("draws", 0) + x.get("black_wins", 0)),
                reverse=True,
            )
            self.explorer.update_positions(moves[:20])
        else:
            self.explorer.update_positions([])

        self.explorer.update_sample_games(sample_games)

    def show_loading(self, message: str = "Querying opening tree..."):
        self.explorer.show_loading(message)

    def show_status(self, message: str):
        self.explorer.show_status(message)

    def send_fen(self, fen: str, force: bool = False):
        current_filters = self.get_filters()
        if not force and self.last_fen == fen and getattr(self, "last_filters", None) == current_filters:
            return

        self.last_fen = fen
        self.last_filters = current_filters
        self.show_loading("Querying opening tree...")
        self.queryRequested.emit(fen, current_filters)

    def showEvent(self, event):
        super().showEvent(event)
        if self.last_fen:
            self.send_fen(self.last_fen, force=False)


