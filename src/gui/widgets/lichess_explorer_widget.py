import os
from typing import Optional, Dict, Any, List
from PyQt5 import QtCore, QtGui, QtWidgets

from core.lichess_client import LichessClient, load_lichess_token, save_lichess_token
from core.opening_explorer import TwoBarWidget, NoFocusDelegate


class LichessTokenDialog(QtWidgets.QDialog):
    """Dialog allowing users to view, enter, or test their Lichess Personal API Access Token."""

    def __init__(self, current_token: str, parent=None, is_dark: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Lichess API Token Configuration")
        self.setMinimumWidth(440)
        self.is_dark = is_dark
        self.client = LichessClient(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(12)

        info_lbl = QtWidgets.QLabel(
            "Enter your Lichess Personal API Access Token to query opening explorer statistics "
            "and fetch master games without strict rate limiting.<br><br>"
            "You can generate a free token at: "
            "<a href='https://lichess.org/account/oauth/token'>https://lichess.org/account/oauth/token</a>"
        )
        info_lbl.setWordWrap(True)
        info_lbl.setOpenExternalLinks(True)
        layout.addWidget(info_lbl)

        token_box = QtWidgets.QHBoxLayout()
        self.txt_token = QtWidgets.QLineEdit(current_token, self)
        self.txt_token.setEchoMode(QtWidgets.QLineEdit.Password)
        self.txt_token.setPlaceholderText("lip_...")
        token_box.addWidget(self.txt_token)

        self.btn_toggle_vis = QtWidgets.QToolButton(self)
        self.btn_toggle_vis.setText("👁")
        self.btn_toggle_vis.setCheckable(True)
        self.btn_toggle_vis.toggled.connect(
            lambda checked: self.txt_token.setEchoMode(
                QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password
            )
        )
        token_box.addWidget(self.btn_toggle_vis)
        layout.addLayout(token_box)

        self.lbl_status = QtWidgets.QLabel("", self)
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_test = QtWidgets.QPushButton("Test Connection", self)
        self.btn_test.clicked.connect(self._test_connection)
        btn_layout.addWidget(self.btn_test)

        btn_layout.addStretch()

        self.btn_save = QtWidgets.QPushButton("Save Token", self)
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(self.btn_save)

        self.btn_cancel = QtWidgets.QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

    def _test_connection(self):
        token = self.txt_token.text().strip()
        self.lbl_status.setText("⏳ Testing connection to Lichess API...")
        self.lbl_status.setStyleSheet("color: #3b82f6;")
        self.btn_test.setEnabled(False)

        self.client.set_token(token, persist=False)

        def on_result(data, err):
            self.btn_test.setEnabled(True)
            if data and not err:
                moves_cnt = len(data.get("moves", []))
                self.lbl_status.setText(f"✓ Connection successful! Received {moves_cnt} moves from Lichess.")
                self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold;")
            else:
                self.lbl_status.setText(f"⚠ Connection failed: {err}")
                self.lbl_status.setStyleSheet("color: #ef4444;")

        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        self.client.query_opening_tree(start_fen, source="masters", moves_count=5, callback=on_result)

    def _on_save(self):
        token = self.txt_token.text().strip()
        save_lichess_token(token)
        self.accept()

    def get_token(self) -> str:
        return self.txt_token.text().strip()


class LichessTreeTable(QtWidgets.QTableWidget):
    """Table widget displaying opening moves and statistics from Lichess."""
    moveSelected = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(5)
        self.setHorizontalHeaderLabels(["Move", "Games", "Score", "Draw %", "Avg Rating"])

        # Column layout matching OpeningTreeTable:
        # Move: Interactive 70px (compact)
        # Games: ResizeToContents
        # Score: Stretch (outcome bars get room)
        # Draw %: ResizeToContents
        # Avg Rating: ResizeToContents
        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(0, 70)
        self.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)

        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setItemDelegate(NoFocusDelegate(self))
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.is_dark = True
        self.positions_data: List[dict] = []

        self.cellClicked.connect(self._on_cell_clicked)
        self.cellDoubleClicked.connect(self._on_cell_clicked)
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        text_color = "#f8fafc" if is_dark else "#0f172a"
        header_bg = "#141312" if is_dark else "#e2e8f0"
        header_text = "#f8fafc" if is_dark else "#0f172a"
        border_r = "#383531" if is_dark else "#cbd5e1"
        sel_bg = "#1e3a5f" if is_dark else "#2563eb"
        sel_color = "#ffffff"

        self.setStyleSheet(f"""
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
            QHeaderView::section {{
                background-color: {header_bg};
                color: {header_text};
                border: none;
                border-right: 1px solid {border_r};
                border-bottom: 1px solid {border_r};
                padding: 3px 4px;
                font-weight: bold;
                font-size: 10px;
            }}
        """)

        for row in range(self.rowCount()):
            bar_w = self.cellWidget(row, 2)
            if isinstance(bar_w, TwoBarWidget):
                bar_w.set_theme(is_dark)

    def update_moves(self, moves: List[Dict[str, Any]]):
        self.positions_data = moves
        self.setRowCount(len(moves))

        font_bold = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
        font_regular = QtGui.QFont("Segoe UI", 9)

        for row, move_data in enumerate(moves):
            san = move_data.get("san") or move_data.get("move") or ""
            uci = move_data.get("uci") or san
            white_wins = move_data.get("white", 0)
            draws = move_data.get("draws", 0)
            black_wins = move_data.get("black", 0)
            total = white_wins + draws + black_wins
            avg_rating = move_data.get("averageRating")

            draw_pct_str = f"{(draws / total) * 100:.1f}%" if total > 0 else "-"
            rating_str = str(avg_rating) if avg_rating else "-"

            # Item 0: Move
            item_move = QtWidgets.QTableWidgetItem(san)
            item_move.setFont(font_bold)
            item_move.setData(QtCore.Qt.UserRole, uci)

            # Item 1: Total games
            item_games = QtWidgets.QTableWidgetItem(f"{total:,}" if total > 0 else "0")
            item_games.setFont(font_regular)
            item_games.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

            # Item 2: Score outcome bar
            bar_widget = TwoBarWidget(white_wins, black_wins, total_games=total, parent=self)
            bar_widget.set_theme(self.is_dark)

            # Item 3: Draw %
            item_draw = QtWidgets.QTableWidgetItem(draw_pct_str)
            item_draw.setFont(font_regular)
            item_draw.setTextAlignment(QtCore.Qt.AlignCenter)

            # Item 4: Avg Rating
            item_rating = QtWidgets.QTableWidgetItem(rating_str)
            item_rating.setFont(font_regular)
            item_rating.setTextAlignment(QtCore.Qt.AlignCenter)

            tooltip = (
                f"Move: {san} ({uci})\n"
                f"Total games: {total:,}\n"
                f"White wins: {white_wins:,} ({(white_wins / total) * 100:.1f}%)\n"
                f"Draws: {draws:,} ({(draws / total) * 100:.1f}%)\n"
                f"Black wins: {black_wins:,} ({(black_wins / total) * 100:.1f}%)\n"
                f"Avg Rating: {rating_str}"
            )
            item_move.setToolTip(tooltip)
            item_games.setToolTip(tooltip)
            item_draw.setToolTip(tooltip)
            item_rating.setToolTip(tooltip)

            self.setItem(row, 0, item_move)
            self.setItem(row, 1, item_games)
            self.setCellWidget(row, 2, bar_widget)
            self.setItem(row, 3, item_draw)
            self.setItem(row, 4, item_rating)
            self.setRowHeight(row, 22)

    def _on_cell_clicked(self, row: int, column: int):
        item = self.item(row, 0)
        if item:
            uci = item.data(QtCore.Qt.UserRole)
            if uci:
                self.moveSelected.emit(str(uci))


class LichessGamesTable(QtWidgets.QTableWidget):
    """Table widget displaying top/recent games in position from Lichess."""
    gameSelected = QtCore.pyqtSignal(str, dict)  # (game_id, game_summary)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels(["White", "Elo W", "Black", "Elo B", "Res", "Date"])

        self.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(1, 50)
        self.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        self.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(3, 50)
        self.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(4, 45)
        self.horizontalHeader().setSectionResizeMode(5, QtWidgets.QHeaderView.Interactive)
        self.horizontalHeader().resizeSection(5, 60)

        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setItemDelegate(NoFocusDelegate(self))
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.is_dark = True
        self.games_data: List[dict] = []

        self.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        text_color = "#f8fafc" if is_dark else "#0f172a"
        header_bg = "#141312" if is_dark else "#e2e8f0"
        header_text = "#f8fafc" if is_dark else "#0f172a"
        border_r = "#383531" if is_dark else "#cbd5e1"
        sel_bg = "#1e3a5f" if is_dark else "#2563eb"
        sel_color = "#ffffff"

        self.setStyleSheet(f"""
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
            QHeaderView::section {{
                background-color: {header_bg};
                color: {header_text};
                border: none;
                border-right: 1px solid {border_r};
                border-bottom: 1px solid {border_r};
                padding: 3px 4px;
                font-weight: bold;
                font-size: 10px;
            }}
        """)

    def update_games(self, games: List[Dict[str, Any]]):
        self.games_data = games
        self.setRowCount(len(games))

        font_demibold = QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold)
        font_regular = QtGui.QFont("Segoe UI", 9)

        for row, g in enumerate(games):
            w_obj = g.get("white") or {}
            b_obj = g.get("black") or {}
            w_name = w_obj.get("name", "?") if isinstance(w_obj, dict) else str(w_obj)
            b_name = b_obj.get("name", "?") if isinstance(b_obj, dict) else str(b_obj)
            w_elo = str(w_obj.get("rating", "")) if isinstance(w_obj, dict) else ""
            b_elo = str(b_obj.get("rating", "")) if isinstance(b_obj, dict) else ""

            winner = g.get("winner")
            if winner == "white":
                res_str = "1-0"
            elif winner == "black":
                res_str = "0-1"
            else:
                res_str = "½-½"

            date_str = str(g.get("year") or g.get("month") or "")
            game_id = g.get("id") or ""

            item_w = QtWidgets.QTableWidgetItem(w_name)
            item_w.setFont(font_demibold)
            item_w.setData(QtCore.Qt.UserRole, game_id)

            item_w_elo = QtWidgets.QTableWidgetItem(w_elo)
            item_w_elo.setFont(font_regular)
            item_w_elo.setTextAlignment(QtCore.Qt.AlignCenter)

            item_b = QtWidgets.QTableWidgetItem(b_name)
            item_b.setFont(font_demibold)

            item_b_elo = QtWidgets.QTableWidgetItem(b_elo)
            item_b_elo.setFont(font_regular)
            item_b_elo.setTextAlignment(QtCore.Qt.AlignCenter)

            item_r = QtWidgets.QTableWidgetItem(res_str)
            item_r.setFont(font_demibold)
            item_r.setTextAlignment(QtCore.Qt.AlignCenter)

            item_d = QtWidgets.QTableWidgetItem(date_str)
            item_d.setFont(font_regular)
            item_d.setTextAlignment(QtCore.Qt.AlignCenter)

            tooltip = (
                f"{w_name} ({w_elo or 'unrated'}) vs {b_name} ({b_elo or 'unrated'})\n"
                f"Result: {res_str} | Date: {date_str or 'Unknown'}\n"
                f"Double-click to load full game PGN from Lichess"
            )
            item_w.setToolTip(tooltip)
            item_w_elo.setToolTip(tooltip)
            item_b.setToolTip(tooltip)
            item_b_elo.setToolTip(tooltip)
            item_r.setToolTip(tooltip)
            item_d.setToolTip(tooltip)

            self.setItem(row, 0, item_w)
            self.setItem(row, 1, item_w_elo)
            self.setItem(row, 2, item_b)
            self.setItem(row, 3, item_b_elo)
            self.setItem(row, 4, item_r)
            self.setItem(row, 5, item_d)
            self.setRowHeight(row, 22)

    def _on_cell_double_clicked(self, row: int, column: int):
        item = self.item(row, 0)
        if item:
            game_id = item.data(QtCore.Qt.UserRole)
            if game_id and 0 <= row < len(self.games_data):
                self.gameSelected.emit(str(game_id), self.games_data[row])


class LichessExplorerWidget(QtWidgets.QWidget):
    """
    Full-featured Lichess Opening Explorer Widget.
    Queries Lichess Opening Explorer via Qt Network (QNetworkAccessManager).
    Features:
    - Mode selector: Masters (2M+ FIDE masters) vs Lichess (Online rated database)
    - Rating & Speed filters for online database
    - Opening Tree Table with move win outcome bars
    - Master / Top Games Table with instant PGN loading
    - Token management (loads from .env / QSettings, modal dialog to configure)
    """
    moveSelected = QtCore.pyqtSignal(str)              # (move_uci)
    gameSelected = QtCore.pyqtSignal(str, dict)        # (pgn_text, game_summary)
    statusMessage = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = True
        self.client = LichessClient(self)
        self.current_fen: Optional[str] = None
        self.last_queried_fen: Optional[str] = None

        self.init_ui()
        self.set_theme(True)

        # Wire client signals
        self.client.treeReady.connect(self._on_tree_ready)
        self.client.errorOccurred.connect(self._on_error_occurred)

    def init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Top Controls Bar
        self.controls_bar = QtWidgets.QWidget(self)
        self.controls_bar.setObjectName("LichessControlsBar")
        self.controls_bar.setFixedHeight(30)
        cb_layout = QtWidgets.QHBoxLayout(self.controls_bar)
        cb_layout.setContentsMargins(6, 2, 6, 2)
        cb_layout.setSpacing(6)

        # Source selector (Masters vs Lichess)
        self.combo_source = QtWidgets.QComboBox(self.controls_bar)
        self.combo_source.addItem("👑 Masters", "masters")
        self.combo_source.addItem("🌐 Lichess DB", "lichess")
        self.combo_source.setToolTip("Select opening database source")
        self.combo_source.currentIndexChanged.connect(self._on_source_changed)
        cb_layout.addWidget(self.combo_source)

        # Speeds filter (visible in Lichess mode)
        self.combo_speed = QtWidgets.QComboBox(self.controls_bar)
        self.combo_speed.addItem("Blitz, Rapid, Classic", ["blitz", "rapid", "classical"])
        self.combo_speed.addItem("Bullet, Blitz", ["bullet", "blitz"])
        self.combo_speed.addItem("Rapid, Classical", ["rapid", "classical"])
        self.combo_speed.addItem("All Speeds", ["bullet", "blitz", "rapid", "classical"])
        self.combo_speed.setToolTip("Filter by time controls")
        self.combo_speed.setVisible(False)
        self.combo_speed.currentIndexChanged.connect(lambda: self.refresh())
        cb_layout.addWidget(self.combo_speed)

        # Ratings filter (visible in Lichess mode)
        self.combo_rating = QtWidgets.QComboBox(self.controls_bar)
        self.combo_rating.addItem("2000+", [2000, 2200, 2500])
        self.combo_rating.addItem("2200+", [2200, 2500])
        self.combo_rating.addItem("1800+", [1800, 2000, 2200, 2500])
        self.combo_rating.addItem("1600+", [1600, 1800, 2000, 2200, 2500])
        self.combo_rating.setToolTip("Filter by player rating bracket")
        self.combo_rating.setVisible(False)
        self.combo_rating.currentIndexChanged.connect(lambda: self.refresh())
        cb_layout.addWidget(self.combo_rating)

        cb_layout.addStretch()

        # Auto checkbox
        self.chk_auto = QtWidgets.QCheckBox("Auto", self.controls_bar)
        self.chk_auto.setChecked(True)
        self.chk_auto.setToolTip("Automatically query Lichess when navigating the board")
        cb_layout.addWidget(self.chk_auto)

        # Refresh button
        self.btn_refresh = QtWidgets.QToolButton(self.controls_bar)
        self.btn_refresh.setText("🔄")
        self.btn_refresh.setToolTip("Refresh statistics for current position")
        self.btn_refresh.clicked.connect(self.refresh)
        cb_layout.addWidget(self.btn_refresh)

        # Token config button
        self.btn_token = QtWidgets.QToolButton(self.controls_bar)
        self.btn_token.setText("🔑 Token")
        self._update_token_button_state()
        self.btn_token.clicked.connect(self._open_token_dialog)
        cb_layout.addWidget(self.btn_token)

        main_layout.addWidget(self.controls_bar)

        # 2. Position Summary Bar (Opening Name & Total Games)
        self.summary_bar = QtWidgets.QWidget(self)
        self.summary_bar.setObjectName("LichessSummaryBar")
        self.summary_bar.setFixedHeight(24)
        sb_layout = QtWidgets.QHBoxLayout(self.summary_bar)
        sb_layout.setContentsMargins(8, 2, 8, 2)
        sb_layout.setSpacing(6)

        self.lbl_opening = QtWidgets.QLabel("Starting Position", self.summary_bar)
        self.lbl_opening.setFont(QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))
        self.lbl_opening.setStyleSheet("color: #3b82f6;")
        sb_layout.addWidget(self.lbl_opening)

        sb_layout.addStretch()

        self.lbl_total_games = QtWidgets.QLabel("", self.summary_bar)
        self.lbl_total_games.setFont(QtGui.QFont("Segoe UI", 9))
        self.lbl_total_games.setStyleSheet("color: #94a3b8;")
        sb_layout.addWidget(self.lbl_total_games)

        main_layout.addWidget(self.summary_bar)

        # 3. Main Content Splitter (Moves Tree & Games Table)
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)
        self.splitter.setChildrenCollapsible(False)

        # Top section: Tree Table
        self.tree_table = LichessTreeTable(self)
        self.tree_table.moveSelected.connect(self.moveSelected.emit)
        self.splitter.addWidget(self.tree_table)

        # Bottom section: Games container
        self.games_container = QtWidgets.QWidget(self)
        gc_layout = QtWidgets.QVBoxLayout(self.games_container)
        gc_layout.setContentsMargins(0, 0, 0, 0)
        gc_layout.setSpacing(0)

        self.lbl_games_header = QtWidgets.QLabel("  Top Games in Position", self.games_container)
        self.lbl_games_header.setFixedHeight(20)
        self.lbl_games_header.setFont(QtGui.QFont("Segoe UI", 8, QtGui.QFont.Bold))
        gc_layout.addWidget(self.lbl_games_header)

        self.games_table = LichessGamesTable(self.games_container)
        self.games_table.gameSelected.connect(self._on_game_double_clicked)
        gc_layout.addWidget(self.games_table)

        self.splitter.addWidget(self.games_container)
        self.splitter.setSizes([220, 160])

        main_layout.addWidget(self.splitter, 1)

        # 4. Status / Empty Overlay Label
        self.lbl_status = QtWidgets.QLabel(self)
        self.lbl_status.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_status.setStyleSheet("color: #94a3b8; font-style: italic; padding: 16px; font-size: 11px;")
        self.lbl_status.setText("Navigate on board to query Lichess opening tree.")
        self.lbl_status.hide()
        main_layout.addWidget(self.lbl_status)

    def _update_token_button_state(self):
        has_tok = self.client.has_token()
        if has_tok:
            self.btn_token.setText("🔑 Token ✓")
            self.btn_token.setToolTip("Lichess API Token is configured. Click to view/modify.")
        else:
            self.btn_token.setText("🔑 Token ⚠")
            self.btn_token.setToolTip("No Lichess API Token found! Click to configure token.")

    def _open_token_dialog(self):
        dlg = LichessTokenDialog(self.client.get_token(), self, is_dark=self.is_dark)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            new_token = dlg.get_token()
            self.client.set_token(new_token, persist=True)
            self._update_token_button_state()
            self.refresh()

    def _on_source_changed(self):
        is_lichess = self.combo_source.currentData() == "lichess"
        self.combo_speed.setVisible(is_lichess)
        self.combo_rating.setVisible(is_lichess)
        self.lbl_games_header.setText("  Recent & Top Games" if is_lichess else "  Top Master Games")
        self.refresh()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        text_color = "#f8fafc" if is_dark else "#0f172a"
        bar_bg = "#1f1d1a" if is_dark else "#f1f5f9"
        border_c = "#383531" if is_dark else "#cbd5e1"
        header_color = "#94a3b8" if is_dark else "#475569"

        self.setStyleSheet(f"""
            QWidget#LichessControlsBar, QWidget#LichessSummaryBar {{
                background-color: {bar_bg};
                border-bottom: 1px solid {border_c};
            }}
            QComboBox, QToolButton, QCheckBox {{
                background-color: {'#312e2b' if is_dark else '#ffffff'};
                color: {text_color};
                border: 1px solid {border_c};
                border-radius: 3px;
                padding: 2px 5px;
                font-size: 11px;
            }}
            QToolButton:hover, QComboBox:hover {{
                background-color: {'#3d3935' if is_dark else '#e2e8f0'};
            }}
        """)

        self.lbl_games_header.setStyleSheet(
            f"background-color: {bar_bg}; color: {header_color}; border-top: 1px solid {border_c}; border-bottom: 1px solid {border_c};"
        )
        self.tree_table.set_theme(is_dark)
        self.games_table.set_theme(is_dark)

    def query_fen(self, fen: str, force: bool = False):
        """Query Lichess for the given board FEN."""
        if not force and not self.chk_auto.isChecked():
            return

        self.current_fen = fen
        if not force and self.last_queried_fen == fen:
            return

        self.last_queried_fen = fen
        self.lbl_status.setText("⏳ Querying Lichess opening tree...")
        self.lbl_status.show()

        source = self.combo_source.currentData() or "masters"
        speeds = self.combo_speed.currentData() if source == "lichess" else None
        ratings = self.combo_rating.currentData() if source == "lichess" else None

        self.client.query_opening_tree(
            fen=fen,
            source=source,
            speeds=speeds,
            ratings=ratings,
            moves_count=15,
            top_games_count=10,
        )

    def refresh(self):
        """Force re-query for current position."""
        if self.current_fen:
            self.query_fen(self.current_fen, force=True)

    def _on_tree_ready(self, data: dict, fen: str):
        if fen != self.current_fen:
            return

        self.lbl_status.hide()

        # Update opening summary
        op_info = data.get("opening")
        if op_info and isinstance(op_info, dict):
            eco = op_info.get("eco", "")
            name = op_info.get("name", "")
            self.lbl_opening.setText(f"{eco} {name}".strip() or "Standard Position")
        else:
            self.lbl_opening.setText("Position Statistics")

        w_cnt = data.get("white", 0)
        d_cnt = data.get("draws", 0)
        b_cnt = data.get("black", 0)
        total = w_cnt + d_cnt + b_cnt

        if total > 0:
            self.lbl_total_games.setText(f"{total:,} games (♔ {int(round(w_cnt/total*100))}% · {int(round(d_cnt/total*100))}% · ♚ {int(round(b_cnt/total*100))}%)")
        else:
            self.lbl_total_games.setText("0 games")

        # Update Moves Tree
        moves = data.get("moves", [])
        self.tree_table.update_moves(moves)

        # Update Top/Recent Games
        top_games = data.get("topGames") or []
        recent_games = data.get("recentGames") or []
        all_games = top_games + [g for g in recent_games if g not in top_games]
        self.games_table.update_games(all_games)

    def _on_error_occurred(self, err_msg: str):
        self.lbl_status.setText(f"⚠ {err_msg}")
        self.lbl_status.show()
        self.statusMessage.emit(err_msg)

    def _on_game_double_clicked(self, game_id: str, summary: dict):
        self.lbl_status.setText(f"⏳ Downloading PGN for game {game_id} from Lichess...")
        self.lbl_status.show()

        def on_pgn_ready(pgn_text, err):
            self.lbl_status.hide()
            if pgn_text and not err:
                self.gameSelected.emit(pgn_text, summary)
            else:
                self.lbl_status.setText(f"⚠ {err or 'Failed to download game'}")
                self.lbl_status.show()

        self.client.fetch_game_pgn(game_id, callback=on_pgn_ready)
