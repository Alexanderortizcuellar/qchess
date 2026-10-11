from typing import Optional, Dict, Any, Set, List
from collections import OrderedDict
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from core.scid_client import ScidClient


class PositionGamesTableModel(QAbstractTableModel):
    """
    Pure virtual scrolling table model for reference / position search results.
    Loads 50-game slices on demand from the scid-mgr search session without blocking UI.
    """

    HEADERS = [
        "White",
        "Elo W",
        "Black",
        "Elo B",
        "Res",
        "Date",
        "ECO",
    ]

    COLUMN_SORT_FIELDS = {
        0: "white",
        1: "white_elo",
        2: "black",
        3: "black_elo",
        4: "result",
        5: "date",
        6: "eco",
    }

    CHUNK_SIZE = 25
    MAX_CACHED_CHUNKS = 50  # Up to 1,250 games cached in memory
    stats_updated = pyqtSignal(int, int)  # total_count, loaded_count
    sort_started = pyqtSignal()
    sort_finished = pyqtSignal()

    def __init__(self, client: Optional[ScidClient] = None, parent=None):
        super().__init__(parent)
        self.client = client if (client is not None and hasattr(client, "response_received")) else None
        self.total_count = 0
        self.search_id: Optional[str] = None
        self.owner: str = "reference"
        self.filters: Dict[str, Any] = {}
        self.cached_chunks: OrderedDict[int, list] = OrderedDict()
        self.in_flight_pages: Set[int] = set()
        self.sort_col: Optional[int] = None
        self.sort_asc: bool = False  # Default to newest games first
        self.is_sorting: bool = False

        if self.client and hasattr(self.client, "response_received"):
            try:
                self.client.response_received.connect(self.on_backend_response)
            except Exception:
                pass

    def set_client(self, client: ScidClient):
        if self.client and self.client != client:
            try:
                self.client.response_received.disconnect(self.on_backend_response)
            except Exception:
                pass
        self.client = client if (client is not None and hasattr(client, "response_received")) else None
        if self.client and hasattr(self.client, "response_received"):
            try:
                self.client.response_received.connect(self.on_backend_response)
            except Exception:
                pass

    def set_search_session(
        self,
        total_count: int,
        search_id: Optional[str] = None,
        filters: Optional[dict] = None,
        initial_games: Optional[List[dict]] = None,
        owner: str = "reference",
    ):
        self.beginResetModel()
        self.total_count = total_count
        self.search_id = search_id
        self.owner = owner
        self.filters = dict(filters) if filters else {}
        self.cached_chunks.clear()
        self.in_flight_pages.clear()

        if initial_games:
            self.cached_chunks[0] = initial_games
            self.cached_chunks.move_to_end(0)

        self.endResetModel()

        loaded_count = sum(len(c) for c in self.cached_chunks.values())
        self.stats_updated.emit(self.total_count, loaded_count)

        if not initial_games and self.client and self.client.is_running() and total_count > 0 and search_id:
            self._request_chunk(0)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else self.total_count

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            title = self.HEADERS[section]
            if self.sort_col == section:
                title += " ▲" if self.sort_asc else " ▼"
            return title
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return str(section + 1)
        return None

    def toggle_sort_column(self, col: int, order: Optional[Qt.SortOrder] = None):
        if col not in self.COLUMN_SORT_FIELDS or not self.search_id:
            return

        self.is_sorting = True
        self.sort_started.emit()

        if order is not None:
            self.sort_col = col
            self.sort_asc = (order == Qt.AscendingOrder)
        else:
            if self.sort_col == col:
                self.sort_asc = not self.sort_asc
            else:
                self.sort_col = col
                self.sort_asc = False if self.COLUMN_SORT_FIELDS[col] in ("date", "white_elo", "black_elo") else True

        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self.HEADERS) - 1)
        self.invalidate_cache_and_reload()

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()
        page = row // self.CHUNK_SIZE
        offset_in_page = row % self.CHUNK_SIZE

        chunk = self.cached_chunks.get(page)
        if chunk is not None:
            self.cached_chunks.move_to_end(page)
        game_item = chunk[offset_in_page] if (chunk and offset_in_page < len(chunk)) else None

        # Lazy load chunk on demand
        if game_item is None and page not in self.in_flight_pages and self.client and self.client.is_running() and self.search_id:
            self._request_chunk(page)

        if role == Qt.DisplayRole:
            if game_item:
                return self._format_cell(game_item, col)
            return ""

        if role == Qt.FontRole:
            col_name = self.HEADERS[col]
            font = QFont("Segoe UI", 9)
            if col_name in ("White", "Black", "Res"):
                font.setBold(True)
            return font

        if role == Qt.TextAlignmentRole:
            col_name = self.HEADERS[col]
            if col_name in ("Elo W", "Elo B", "Res", "Date", "ECO"):
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.ToolTipRole and game_item:
            w_name = game_item.get("white", "?")
            w_elo = game_item.get("white_elo", "")
            b_name = game_item.get("black", "?")
            b_elo = game_item.get("black_elo", "")
            res_str = game_item.get("result", "*")
            date_str = game_item.get("date", "")
            eco_str = game_item.get("eco", "")
            event_str = game_item.get("event", "")
            site_str = game_item.get("site", "")
            matching_plies = game_item.get("matching_plies") or []
            plies_str = f"Matching Plies: {matching_plies}" if matching_plies else ""

            return (
                f"{w_name} ({w_elo or 'unrated'}) vs {b_name} ({b_elo or 'unrated'})\n"
                f"Result: {res_str} | Date: {date_str} | ECO: {eco_str}\n"
                f"Event: {event_str}\nSite: {site_str}"
                + (f"\n{plies_str}" if plies_str else "")
            )

        return None

    def _format_cell(self, g: dict, col: int) -> str:
        if col == 0:
            return g.get("white", "?")
        elif col == 1:
            elo = g.get("white_elo")
            return str(elo) if elo and int(elo) > 0 else ""
        elif col == 2:
            return g.get("black", "?")
        elif col == 3:
            elo = g.get("black_elo")
            return str(elo) if elo and int(elo) > 0 else ""
        elif col == 4:
            return g.get("result", "*")
        elif col == 5:
            # Whole date (e.g. "1990.11.24", "1972.??.??", "2024")
            date_str = str(g.get("date") or "").strip()
            if date_str and date_str != "?":
                return date_str
            year_val = g.get("year")
            if year_val:
                return str(year_val)
            return ""
        elif col == 6:
            return g.get("eco", "")
        return ""

    def get_game_at(self, row: int) -> Optional[dict]:
        page = row // self.CHUNK_SIZE
        offset = row % self.CHUNK_SIZE
        chunk = self.cached_chunks.get(page)
        if chunk is not None:
            self.cached_chunks.move_to_end(page)
        if chunk and offset < len(chunk):
            return chunk[offset]
        return None

    def _request_chunk(self, page: int):
        if page in self.in_flight_pages or not self.client or not self.client.is_running() or not self.search_id:
            return
        self.in_flight_pages.add(page)
        sort_field = self.COLUMN_SORT_FIELDS.get(self.sort_col) if self.sort_col is not None else None
        self.client.query_games(
            page=page,
            page_size=self.CHUNK_SIZE,
            sort_by=sort_field,
            sort_asc=self.sort_asc,
            search_id=self.search_id,
            owner=self.owner,
        )

    def invalidate_cache_and_reload(self):
        self.beginResetModel()
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.endResetModel()

        if self.client and self.client.is_running() and self.search_id:
            self._request_chunk(0)

    def clear(self):
        self.beginResetModel()
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.total_count = 0
        self.search_id = None
        self.endResetModel()
        self.stats_updated.emit(0, 0)

    def on_backend_response(self, data: dict):
        if data.get("status") != "ok":
            return
        resp_data = data.get("data", {})
        if not isinstance(resp_data, dict):
            return

        games = resp_data.get("games")
        if games is None or not isinstance(games, list):
            return

        resp_search_id = resp_data.get("search_id")
        if self.search_id and resp_search_id and self.search_id != resp_search_id:
            return

        page = resp_data.get("page", 0)
        total = resp_data.get("total", self.total_count)

        if page in self.in_flight_pages:
            self.in_flight_pages.remove(page)

        if self.is_sorting:
            self.is_sorting = False
            self.sort_finished.emit()

        self.cached_chunks[page] = games
        self.cached_chunks.move_to_end(page)

        while len(self.cached_chunks) > self.MAX_CACHED_CHUNKS:
            self.cached_chunks.popitem(last=False)

        if total != self.total_count:
            self.beginResetModel()
            self.total_count = total
            self.endResetModel()
        else:
            start_row = page * self.CHUNK_SIZE
            end_row = min(self.total_count - 1, start_row + len(games) - 1)
            if start_row <= end_row:
                top_left = self.index(start_row, 0)
                bottom_right = self.index(end_row, len(self.HEADERS) - 1)
                self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.ToolTipRole])

        loaded_count = sum(len(c) for c in self.cached_chunks.values() if isinstance(c, list))
        self.stats_updated.emit(self.total_count, loaded_count)


class NoFocusDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that suppresses the dotted cell focus rectangle on selection."""
    def paint(self, painter, option, index):
        opt = QtWidgets.QStyleOptionViewItem(option)
        opt.state &= ~QtWidgets.QStyle.State_HasFocus
        super().paint(painter, opt, index)


class PositionGamesWidget(QtWidgets.QWidget):
    """
    Dedicated dock widget displaying all games matching the current board position or search.
    Provides on-demand virtual scrolling, multi-column sorting, and double-click game opening.
    """

    queryRequested = QtCore.pyqtSignal(str, dict)  # (fen, filters)
    gameSelected = QtCore.pyqtSignal(int, dict)    # (game_id, game_summary)
    def __init__(self, parent=None, client: Optional[ScidClient] = None):
        super().__init__(parent)
        if isinstance(parent, ScidClient) and client is None:
            self.client = parent
        else:
            self.client = client
        self.last_fen: Optional[str] = None
        self.is_dark = QtCore.QSettings("QChessApp", "Theme").value("theme", "dark") == "dark"

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header Info Bar
        self.header_bar = QtWidgets.QWidget(self)
        self.header_bar.setFixedHeight(28)
        header_layout = QtWidgets.QHBoxLayout(self.header_bar)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(6)

        self.lbl_count = QtWidgets.QLabel("0 games", self.header_bar)
        self.lbl_count.setFont(QFont("Segoe UI", 9, QFont.Bold))

        self.lbl_status = QtWidgets.QLabel("", self.header_bar)
        self.lbl_status.setFont(QFont("Segoe UI", 9, QFont.Normal))
        self.lbl_status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(self.lbl_count)
        header_layout.addStretch()
        header_layout.addWidget(self.lbl_status)

        # Header Bar (hidden in favor of unified Reference tab header)
        self.header_bar.hide()

        # Table View
        self.table = QtWidgets.QTableView(self)
        self.table.setFont(QFont("Segoe UI", 9))
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.verticalHeader().setMinimumSectionSize(18)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.setItemDelegate(NoFocusDelegate(self.table))

        # Column configuration (7 columns)
        self.model = PositionGamesTableModel(self.client, self)
        self.model.stats_updated.connect(self._on_stats_updated)
        self.table.setModel(self.model)

        # Horizontal Header
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)          # White
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Interactive)      # Elo W
        header.resizeSection(1, 55)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)          # Black
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Interactive)      # Elo B
        header.resizeSection(3, 55)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Interactive)      # Res
        header.resizeSection(4, 50)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.Interactive)      # Year
        header.resizeSection(5, 48)
        header.setSectionResizeMode(6, QtWidgets.QHeaderView.Interactive)      # ECO
        header.resizeSection(6, 45)
        header.sectionClicked.connect(self._on_header_clicked)

        # Context menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.doubleClicked.connect(self._on_row_double_clicked)

        layout.addWidget(self.table, 1)

        # Empty State / Status Overlay
        self.overlay_lbl = QtWidgets.QLabel(self)
        self.overlay_lbl.setAlignment(Qt.AlignCenter)
        self.overlay_lbl.setText("Open a database to explore matching games.")
        self.overlay_lbl.setStyleSheet("color: #8b8987; font-style: italic; font-size: 11px; padding: 16px;")
        layout.addWidget(self.overlay_lbl)
        self.overlay_lbl.hide()

        # Wire global reference filter manager
        from core.reference_filters import get_reference_filter_manager
        self.ref_filter_mgr = get_reference_filter_manager()
        self.ref_filter_mgr.filtersChanged.connect(self._on_global_filters_changed)

        self.set_theme(self.is_dark)

    def set_client(self, client: ScidClient):
        self.client = client
        self.model.set_client(client)

    def _on_global_filters_changed(self, _=None):
        if self.last_fen:
            self.send_fen(self.last_fen, force=True)

    def get_filters(self) -> Dict[str, Any]:
        return self.ref_filter_mgr.get_filter_dict()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        alt_bg = "#2b2926" if is_dark else "#f8fafc"
        text_color = "#bababa" if is_dark else "#0f172a"
        header_bg = "#141312" if is_dark else "#e2e8f0"
        header_text = "#f8fafc" if is_dark else "#0f172a"
        border_r = "#383531" if is_dark else "#cbd5e1"
        sel_bg = "#1e3a5f" if is_dark else "#2563eb"
        sel_color = "#ffffff"

        self.setStyleSheet(f"background-color: {bg};")
        self.header_bar.setStyleSheet(f"""
            QWidget {{
                background-color: {header_bg};
                border-bottom: 1px solid {border_r};
            }}
            QLabel {{
                color: {header_text};
                background: transparent;
                border: none;
            }}
        """)
        self.table.setStyleSheet(f"""
            QTableView {{
                background-color: {bg};
                color: {text_color};
                border: none;
                font-size: 11px;
                selection-background-color: {sel_bg};
                selection-color: {sel_color};
                outline: none;
            }}
            QTableView::item {{
                outline: none;
                border: none;
            }}
            QTableView::item:selected {{
                background-color: {sel_bg};
                color: {sel_color};
                outline: none;
                border: none;
            }}
            QTableView::item:focus {{
                outline: none;
                border: none;
            }}
            QTableView::item:selected:focus {{
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
                padding: 3px 6px;
                font-weight: bold;
                font-size: 10px;
            }}
        """)
        self.overlay_lbl.setStyleSheet(f"color: {'#94a3b8' if is_dark else '#64748b'}; font-style: italic; font-size: 11px; padding: 16px; background: transparent;")

    def _on_stats_updated(self, total: int, loaded: int):
        has_filter = bool(self.ref_filter_mgr.get_filter_dict())
        filter_badge = " (Filter Active)" if has_filter else ""
        if total > 0:
            self.lbl_count.setText(f"{total:,} games match{filter_badge}")
            self.overlay_lbl.hide()
            self.table.show()
        else:
            self.lbl_count.setText("0 games")
            if self.last_fen:
                self.overlay_lbl.setText(f"No games found matching position{filter_badge}.")
                self.overlay_lbl.show()

    def _on_header_clicked(self, logical_index: int):
        self.model.toggle_sort_column(logical_index)

    def _on_row_double_clicked(self, index: QModelIndex):
        if not index.isValid():
            return
        row = index.row()
        game_item = self.model.get_game_at(row)
        if game_item:
            gid = game_item.get("id", row)
            self.gameSelected.emit(int(gid), game_item)

    def _on_context_menu(self, pos: QtCore.QPoint):
        sel = self.table.selectionModel()
        if not sel or not sel.hasSelection():
            return
        indexes = sel.selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        game_item = self.model.get_game_at(row)
        if not game_item:
            return

        import qtawesome as qta
        menu = QtWidgets.QMenu(self)
        open_act = menu.addAction(qta.icon("fa5s.chess-board", color="#a9aea7"), "Open Game in Analyzer")
        open_act.triggered.connect(lambda: self._on_row_double_clicked(self.model.index(row, 0)))

        copy_act = menu.addAction(qta.icon("fa5s.copy", color="#a9aea7"), "Copy PGN")
        copy_act.triggered.connect(lambda: self.copy_game_pgn(game_item))

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def copy_game_pgn(self, game_item: dict):
        if not self.client or not self.client.is_running():
            return
        gid = game_item.get("id")
        if gid is None:
            return

        def on_pgn(resp: dict):
            if resp.get("status") == "ok":
                pgn_text = resp.get("data", {}).get("pgn", "")
                QtWidgets.QApplication.clipboard().setText(pgn_text)

        self.client.get_pgn(int(gid), callback=on_pgn)

    def set_search_session(
        self,
        search_id: Optional[str],
        total_count: int,
        filters: Optional[dict] = None,
        initial_games: Optional[List[dict]] = None,
        owner: str = "reference",
    ):
        self.lbl_status.setText("")
        self.model.set_search_session(
            total_count=total_count,
            search_id=search_id,
            filters=filters,
            initial_games=initial_games,
            owner=owner,
        )

    def show_loading(self, message: str = "Querying matching games..."):
        self.lbl_status.setText("⏳ Querying...")
        self.overlay_lbl.setText(message)
        self.overlay_lbl.show()

    def show_status(self, message: str):
        self.lbl_status.setText("")
        self.model.clear()
        self.overlay_lbl.setText(message)
        self.overlay_lbl.show()

    def send_fen(self, fen: str, force: bool = False):
        current_filters = self.get_filters()
        if not force and self.last_fen == fen and getattr(self, "last_filters", None) == current_filters:
            return

        self.last_fen = fen
        self.last_filters = current_filters
        self.show_loading("Querying matching games...")
        self.queryRequested.emit(fen, current_filters)

    def showEvent(self, event):
        super().showEvent(event)
        if self.last_fen:
            self.send_fen(self.last_fen, force=False)
