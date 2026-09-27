from typing import Optional, List, Dict, Any
from PyQt5 import QtCore, QtGui, QtWidgets
import qtawesome as qta


class EndgameOutcomeBar(QtWidgets.QWidget):
    """Visual outcome distribution bar (White Win / Draw / Black Win) for endgames."""

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
        self.setFixedHeight(20)
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
                f"Endgame games: {total:,}\n"
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

        # White segment
        if pw > 0:
            painter.setBrush(color_white)
            painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if not self.is_dark:
                painter.setPen(QtGui.QPen(QtGui.QColor("#cbd5e1"), 1))
                painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if pw > 26:
                painter.setPen(QtGui.QColor("#0f172a"))
                pct = (self.white_win / total) * 100
                painter.drawText(QtCore.QRectF(0, 0, pw, h), QtCore.Qt.AlignCenter, f"{pct:.0f}%")

        # Draw segment
        if pd > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_draw)
            painter.drawRect(QtCore.QRectF(pw, 0, pd, h))
            if pd > 26:
                painter.setPen(QtGui.QColor("#ffffff"))
                pct = (self.draw / total) * 100
                painter.drawText(QtCore.QRectF(pw, 0, pd, h), QtCore.Qt.AlignCenter, f"{pct:.0f}%")

        # Black segment
        if pb > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_black)
            painter.drawRect(QtCore.QRectF(pw + pd, 0, pb, h))
            if pb > 26:
                painter.setPen(QtGui.QColor("#ffffff"))
                pct = (self.black_win / total) * 100
                painter.drawText(QtCore.QRectF(pw + pd, 0, pb, h), QtCore.Qt.AlignCenter, f"{pct:.0f}%")


class EndgamesWidget(QtWidgets.QWidget):
    """Endgame Taxonomy & Statistical Feature Explorer.

    - Classifies database games into 47 standardized endgame types from scid-mgr.
    - Shows occurrence frequency, percentage distribution, and win/draw/loss rates.
    - Supports category filtering (Pawn, Rook, Bishop, Knight, Minor Mixed, Queen, etc.).
    - Queries endgames reaching the current board position or whole database.
    """

    queryRequested = QtCore.pyqtSignal(str, dict)  # (fen, options)
    featureSelected = QtCore.pyqtSignal(str)       # (feature_id)
    buildEndgamesIndexRequested = QtCore.pyqtSignal()
    statusMessage = QtCore.pyqtSignal(str)

    CATEGORY_LABELS = {
        "ALL": "All Categories",
        "PAWN": "♙ Pawn Endgames",
        "ROOK": "♖ Rook Endgames",
        "BISHOP": "♗ Bishop Endgames",
        "KNIGHT": "♘ Knight Endgames",
        "MINOR_MIXED": "♗♘ Mixed Minor Endgames",
        "QUEEN": "♕ Queen Endgames",
        "ROOK_VS_MINOR": "♖ vs ♗/♘ Rook vs Minor",
        "QUEEN_VS_PIECES": "♕ vs Pieces Queen Endgames",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_fen: Optional[str] = None
        self.last_queried_fen: Optional[str] = None
        self.current_report: Optional[dict] = None
        self.is_dark = True
        self._features_data: List[dict] = []

        self.init_ui()

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 1. Controls Bar
        self.controls_frame = QtWidgets.QFrame(self)
        self.controls_frame.setObjectName("EndgamesControlsFrame")
        c_layout = QtWidgets.QHBoxLayout(self.controls_frame)
        c_layout.setContentsMargins(4, 3, 4, 3)
        c_layout.setSpacing(6)

        # Category Filter Combo
        self.combo_category = QtWidgets.QComboBox(self)
        for cat_id, cat_name in self.CATEGORY_LABELS.items():
            self.combo_category.addItem(cat_name, cat_id)
        self.combo_category.currentIndexChanged.connect(self._on_filter_changed)
        c_layout.addWidget(self.combo_category, stretch=2)

        # Search / Filter Box
        self.txt_filter = QtWidgets.QLineEdit(self)
        self.txt_filter.setPlaceholderText("Filter endgames...")
        self.txt_filter.textChanged.connect(self._on_search_text_changed)
        c_layout.addWidget(self.txt_filter, stretch=2)

        # Auto-query
        self.chk_auto = QtWidgets.QCheckBox("Auto", self)
        self.chk_auto.setChecked(True)
        self.chk_auto.setToolTip("Automatically compute endgame distribution on position change")
        c_layout.addWidget(self.chk_auto)

        # Query Button
        self.btn_query = QtWidgets.QPushButton("▶ Query", self)
        self.btn_query.setToolTip("Query endgame statistics for current position")
        self.btn_query.setCursor(QtCore.Qt.PointingHandCursor)
        self.btn_query.clicked.connect(self.trigger_query)
        c_layout.addWidget(self.btn_query)

        layout.addWidget(self.controls_frame)

        # 2. Summary Status Frame
        self.summary_frame = QtWidgets.QFrame(self)
        self.summary_frame.setObjectName("EndgamesSummaryFrame")
        s_layout = QtWidgets.QHBoxLayout(self.summary_frame)
        s_layout.setContentsMargins(6, 3, 6, 3)
        s_layout.setSpacing(10)

        self.lbl_pos_games = QtWidgets.QLabel("Position Games: -", self)
        self.lbl_pos_games.setStyleSheet("font-weight: bold; font-size: 11px;")
        s_layout.addWidget(self.lbl_pos_games)

        self.lbl_total_db = QtWidgets.QLabel("Total DB: -", self)
        self.lbl_total_db.setStyleSheet("font-size: 11px; color: #888;")
        s_layout.addWidget(self.lbl_total_db)

        s_layout.addStretch()

        self.lbl_status = QtWidgets.QLabel("⚡ Ready", self)
        self.lbl_status.setStyleSheet("font-weight: 600; font-size: 11px; color: #2e7d32;")
        s_layout.addWidget(self.lbl_status)

        layout.addWidget(self.summary_frame)

        # 3. Main Endgames Tree / Table (Optimized space without GBR column)
        self.table = QtWidgets.QTreeWidget(self)
        self.table.setColumnCount(3)
        self.table.setHeaderLabels(["Endgame Classification", "Games (%)", "Score (W / D / B)"])
        self.table.header().setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
        self.table.header().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
        self.table.header().setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        self.table.header().resizeSection(2, 140)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setRootIsDecorated(True)
        self.table.setAnimated(True)

        layout.addWidget(self.table)

        # 4. Status overlay label for placeholder/loading
        self.status_lbl = QtWidgets.QLabel(self.table)
        self.status_lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.status_lbl.setStyleSheet("color: #8b8987; font-style: italic; font-size: 11px; padding: 16px;")
        self.status_lbl.setText("Open a database in QChess to explore endgame classifications.")
        self.status_lbl.show()

        self.set_theme(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.status_lbl.setGeometry(self.table.rect())

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#1e1e1e" if is_dark else "#ffffff"
        alt_bg = "#252526" if is_dark else "#f8fafc"
        text_color = "#d4d4d4" if is_dark else "#0f172a"
        panel_bg = "#2d2d2d" if is_dark else "#f1f5f9"
        header_bg = "#141312" if is_dark else "#e2e8f0"
        header_text = "#f8fafc" if is_dark else "#0f172a"
        border_color = "#3e3e42" if is_dark else "#cbd5e1"
        sel_bg = "#094771" if is_dark else "#dbeafe"
        sel_color = "#ffffff" if is_dark else "#1e3a8a"

        self.setStyleSheet(f"""
            QFrame#EndgamesControlsFrame, QFrame#EndgamesSummaryFrame {{
                background-color: {panel_bg};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QTreeWidget {{
                background-color: {bg};
                alternate-background-color: {alt_bg};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                font-size: 11px;
            }}
            QTreeWidget::item:selected {{
                background-color: {sel_bg};
                color: {sel_color};
            }}
            QHeaderView::section {{
                background-color: {header_bg};
                color: {header_text};
                border: none;
                border-right: 1px solid {border_color};
                border-bottom: 1px solid {border_color};
                padding: 5px 6px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)

        # Update any custom outcome bars in tree
        root = self.table.invisibleRootItem()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            w = self.table.itemWidget(cat_item, 2)
            if isinstance(w, EndgameOutcomeBar):
                w.set_theme(is_dark)
            for j in range(cat_item.childCount()):
                feat_item = cat_item.child(j)
                fw = self.table.itemWidget(feat_item, 2)
                if isinstance(fw, EndgameOutcomeBar):
                    fw.set_theme(is_dark)

    def show_status(self, message: str):
        self.lbl_status.setText("ℹ Info")
        self.lbl_status.setStyleSheet("font-weight: 600; font-size: 11px; color: #888;")
        self.status_lbl.setText(message)
        self.status_lbl.show()

    def show_loading(self, message: str = "Querying endgame statistics..."):
        self.lbl_status.setText("⏳ Querying...")
        self.lbl_status.setStyleSheet("font-weight: 600; font-size: 11px; color: #e65100;")
        self.status_lbl.setText(message)
        self.status_lbl.show()

    def trigger_query(self, force: bool = True):
        if not self.current_fen:
            return
        cat_data = self.combo_category.currentData()
        options = {
            "category": cat_data if cat_data != "ALL" else None,
            "max_samples": 20,
        }
        self.show_loading()
        self.last_queried_fen = self.current_fen
        self.queryRequested.emit(self.current_fen, options)

    def send_fen(self, fen: str, force: bool = False):
        self.current_fen = fen
        if not self.chk_auto.isChecked() and not force:
            return
        if not force and self.last_queried_fen == fen:
            return
        self.trigger_query(force=force)

    def _on_filter_changed(self, index: int):
        self._apply_client_filter()

    def _on_search_text_changed(self, text: str):
        self._apply_client_filter()

    def _apply_client_filter(self):
        cat_filter = self.combo_category.currentData()
        search_query = self.txt_filter.text().strip().lower()

        root = self.table.invisibleRootItem()
        for i in range(root.childCount()):
            cat_item = root.child(i)
            cat_id = cat_item.data(0, QtCore.Qt.UserRole)
            cat_visible = False

            if cat_filter in ("ALL", None, cat_id):
                for j in range(cat_item.childCount()):
                    feat_item = cat_item.child(j)
                    feat_name = feat_item.text(0).lower()

                    matches_search = (
                        not search_query
                        or search_query in feat_name
                    )
                    feat_item.setHidden(not matches_search)
                    if matches_search:
                        cat_visible = True

            cat_item.setHidden(not cat_visible)

    def set_report(self, data: dict):
        """Populate the widget with EndgamePopularityReport from scid-mgr."""
        self.current_report = data
        self.status_lbl.hide()
        self.lbl_status.setText("⚡ Ready")
        self.lbl_status.setStyleSheet("font-weight: 600; font-size: 11px; color: #2e7d32;")

        total_db = data.get("total_db_games", 0)
        pos_games = data.get("games_reaching_position", total_db)
        is_pos_filtered = data.get("position_filtered", False)

        if is_pos_filtered:
            self.lbl_pos_games.setText(f"Position Games: {pos_games:,}")
        else:
            self.lbl_pos_games.setText(f"Total Games: {pos_games:,}")
        self.lbl_total_db.setText(f"Database: {total_db:,}")

        categories = data.get("categories", [])
        features = data.get("features", [])

        self.table.clear()
        if not categories and not features:
            self.show_status("No endgame occurrences found for this position/database.")
            return

        has_any_data = False
        for cat in categories:
            cat_games = cat.get("total_games", 0)
            if cat_games <= 0:
                continue

            cat_features = [f for f in cat.get("features", []) if f.get("game_count", 0) > 0]
            if not cat_features:
                continue

            has_any_data = True
            cat_id = cat.get("category_id", "")
            cat_name = cat.get("name", cat_id)
            cat_pct = cat.get("percentage", 0.0)

            display_name = self.CATEGORY_LABELS.get(cat_id, cat_name)
            cat_item = QtWidgets.QTreeWidgetItem(self.table)
            cat_item.setText(0, display_name)
            cat_item.setText(1, f"{cat_games:,} ({cat_pct:.1f}%)")
            cat_item.setFont(0, QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))
            cat_item.setFont(1, QtGui.QFont("Segoe UI", 9, QtGui.QFont.Bold))
            cat_item.setData(0, QtCore.Qt.UserRole, cat_id)

            cat_w = sum(f.get("white_wins", 0) for f in cat_features)
            cat_d = sum(f.get("draws", 0) for f in cat_features)
            cat_b = sum(f.get("black_wins", 0) for f in cat_features)

            if (cat_w + cat_d + cat_b) > 0:
                bar = EndgameOutcomeBar(cat_w, cat_d, cat_b, parent=self.table)
                bar.set_theme(self.is_dark)
                self.table.setItemWidget(cat_item, 2, bar)

            for feat in cat_features:
                f_name = feat.get("name", "")
                f_short = feat.get("short_name", "")
                f_games = feat.get("game_count", 0)
                f_pct = feat.get("percentage", 0.0)
                f_w = feat.get("white_wins", 0)
                f_d = feat.get("draws", 0)
                f_b = feat.get("black_wins", 0)

                feat_item = QtWidgets.QTreeWidgetItem(cat_item)
                label_text = f"{f_short} — {f_name}" if f_short else f_name
                feat_item.setText(0, label_text)
                feat_item.setText(1, f"{f_games:,} ({f_pct:.1f}%)")
                feat_item.setData(0, QtCore.Qt.UserRole, feat.get("id"))

                feat_bar = EndgameOutcomeBar(f_w, f_d, f_b, parent=self.table)
                feat_bar.set_theme(self.is_dark)
                self.table.setItemWidget(feat_item, 2, feat_bar)

        if not has_any_data:
            self.show_status("No endgame occurrences found for this position/database.")
            return

        self.table.expandAll()
        self._apply_client_filter()
