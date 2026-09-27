from typing import Optional, Dict, Any, Set
from collections import OrderedDict
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import Qt, QAbstractTableModel, QModelIndex, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from core.scid_client import ScidClient


class GameListTableModel(QAbstractTableModel):
    """
    Pure virtual scrolling table model powered by scid-mgr backend.
    data() only reads from in-memory cache chunks (100 rows each) and NEVER blocks UI.
    """

    HEADERS = [
        "ID",
        "White",
        "EloW",
        "Black",
        "EloB",
        "Result",
        "ECO",
        "Date",
        "Event",
        "Site",
        "Round",
        "Status",
    ]

    COLUMN_SORT_FIELDS = {
        0: "id",
        1: "white",
        2: "white_elo",
        3: "black",
        4: "black_elo",
        5: "result",
        6: "eco",
        7: "date",
        8: "event",
        9: "site",
        10: "round",
        11: "status",
    }

    CHUNK_SIZE = 100
    MAX_CACHED_CHUNKS = 50  # Cap cache at 5,000 rows (~2-3 MB max memory)
    stats_updated = pyqtSignal(int, int)  # total_games, loaded_games
    sort_started = pyqtSignal()
    sort_finished = pyqtSignal()

    def __init__(self, client: Optional[ScidClient] = None, parent=None):
        super().__init__(parent)
        self.client = client
        self.total_count = 0
        self.search_id: Optional[str] = None
        self.filters: Dict[str, Any] = {}
        self.cached_chunks: OrderedDict[int, list] = OrderedDict()
        self.in_flight_pages: Set[int] = set()
        self.sort_col: Optional[int] = None
        self.sort_asc: bool = True
        self.is_sorting: bool = False

        if self.client:
            self.client.response_received.connect(self.on_backend_response)

    def set_client(self, client: ScidClient):
        if self.client and self.client != client:
            try:
                self.client.response_received.disconnect(self.on_backend_response)
            except Exception:
                pass
        self.client = client
        if self.client:
            self.client.response_received.connect(self.on_backend_response)

    def set_db(self, total_count: int, filters: Optional[dict] = None, search_id: Optional[str] = None):
        self.beginResetModel()
        self.total_count = total_count
        self.search_id = search_id
        self.filters = dict(filters) if filters else {}
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.endResetModel()

        if self.client and self.client.is_running() and total_count > 0:
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

    def has_active_filter(self) -> bool:
        if self.search_id:
            return True
        SORT_KEYS = {"sort_by", "sort_asc", "sort_direction", "include_deleted", "only_deleted"}
        return any(
            k not in SORT_KEYS and bool(v)
            for k, v in self.filters.items()
        ) or bool(self.filters.get("only_deleted", False))

    def toggle_sort_column(self, col: int, order: Optional[Qt.SortOrder] = None):
        if col not in self.COLUMN_SORT_FIELDS:
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
                self.sort_asc = True

        self.filters["sort_by"] = self.COLUMN_SORT_FIELDS[col]
        self.filters["sort_asc"] = self.sort_asc
        self.filters["sort_direction"] = "ASC" if self.sort_asc else "DESC"
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

        # Lazy load chunk if missing
        if game_item is None and page not in self.in_flight_pages and self.client and self.client.is_running():
            self._request_chunk(page)

        if role == Qt.DisplayRole:
            if game_item:
                return self._format_cell(game_item, col)
            return ""

        if role == Qt.FontRole:
            col_name = self.HEADERS[col]
            font = QFont("Segoe UI", 9)
            if col_name in ("White", "Black", "Result"):
                font.setBold(True)
            return font

        if role == Qt.TextAlignmentRole:
            col_name = self.HEADERS[col]
            if col_name in ("ID", "EloW", "EloB", "Result", "Date", "Round", "ECO", "Status"):
                return Qt.AlignCenter

        if role == Qt.ForegroundRole and game_item:
            if game_item.get("deleted"):
                return QColor("#d32f2f")  # Red for deleted games

        return None

    def _format_cell(self, g: dict, col: int) -> str:
        if col == 0:
            gid = g.get("id")
            return str(gid + 1) if gid is not None else ""
        elif col == 1:
            return g.get("white", "")
        elif col == 2:
            elo = g.get("white_elo")
            return str(elo) if elo and elo > 0 else ""
        elif col == 3:
            return g.get("black", "")
        elif col == 4:
            elo = g.get("black_elo")
            return str(elo) if elo and elo > 0 else ""
        elif col == 5:
            return g.get("result", "*")
        elif col == 6:
            return g.get("eco", "")
        elif col == 7:
            return g.get("date", "????.??.??")
        elif col == 8:
            return g.get("event", "")
        elif col == 9:
            return g.get("site", "")
        elif col == 10:
            r = g.get("round")
            return str(r) if r is not None else "-"
        elif col == 11:
            status_flags = []
            if g.get("deleted"):
                status_flags.append("DELETED")
            if g.get("non_standard_start"):
                status_flags.append("FEN")
            return " | ".join(status_flags) if status_flags else "OK"
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
        if page in self.in_flight_pages or not self.client or not self.client.is_running():
            return
        self.in_flight_pages.add(page)
        self.client.query_games(
            page=page,
            page_size=self.CHUNK_SIZE,
            filter_dict=self.filters if not self.search_id else None,
            sort_by=self.filters.get("sort_by"),
            sort_direction=self.filters.get("sort_direction"),
            sort_asc=self.sort_asc,
            search_id=self.search_id,
        )

    def set_filters(self, filters: dict):
        self.beginResetModel()
        self.filters = dict(filters)
        self.search_id = None
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.endResetModel()

        if self.client and self.client.is_running():
            self._request_chunk(0)

    def invalidate_cache_and_reload(self):
        self.beginResetModel()
        self.cached_chunks.clear()
        self.in_flight_pages.clear()
        self.endResetModel()

        if self.client and self.client.is_running():
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
        if "games" not in resp_data:
            return

        page = resp_data.get("page", 0)
        total = resp_data.get("total", 0)
        games = resp_data.get("games", [])
        if "search_id" in resp_data:
            self.search_id = resp_data.get("search_id")

        if page in self.in_flight_pages:
            self.in_flight_pages.remove(page)

        if getattr(self, "is_sorting", False):
            self.is_sorting = False
            self.sort_finished.emit()

        self.cached_chunks[page] = games
        self.cached_chunks.move_to_end(page)

        # Evict oldest chunks if exceeding capacity
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
                self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.ForegroundRole])

        loaded_count = sum(len(c) for c in self.cached_chunks.values())
        self.stats_updated.emit(self.total_count, loaded_count)

    def set_game_deleted_status(self, row: int, deleted: bool):
        page = row // self.CHUNK_SIZE
        offset = row % self.CHUNK_SIZE
        chunk = self.cached_chunks.get(page)
        if chunk and offset < len(chunk):
            chunk[offset]["deleted"] = deleted
            top_left = self.index(row, 0)
            bottom_right = self.index(row, len(self.HEADERS) - 1)
            self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.ForegroundRole])


class GameListTableWidget(QtWidgets.QWidget):
    """
    Virtual scrolling games table widget powered by scid-mgr backend.
    """

    gameSelected = QtCore.pyqtSignal(dict)
    loadFinished = QtCore.pyqtSignal(int)
    gameDeleted = QtCore.pyqtSignal(int)
    gameUndeleted = QtCore.pyqtSignal(int)
    filterStateChanged = QtCore.pyqtSignal(bool)

    def __init__(self, client: Optional[ScidClient] = None, parent=None):
        super().__init__(parent)
        self.client = client

        self.filter_edit = QtWidgets.QLineEdit(self)
        self.filter_edit.setPlaceholderText("Quick filter games by player or text (Press Enter)...")

        self.table = QtWidgets.QTableView(self)
        self.table.setFont(QtGui.QFont("Segoe UI", 9))
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.verticalHeader().setMinimumSectionSize(18)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)

        # Table row context menu
        self.table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)

        self.info_label = QtWidgets.QLabel(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.info_label)

        self.model = GameListTableModel(self.client, self)
        self.model.stats_updated.connect(self._on_stats_updated)
        self.model.sort_started.connect(self._on_sort_started)
        self.model.sort_finished.connect(self._on_sort_finished)
        self.table.setModel(self.model)

        # Header configuration
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.sectionMoved.connect(self.save_header_state)
        header.sectionResized.connect(self.save_header_state)
        header.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_context_menu)

        self.restore_header_state()

        self.filter_edit.returnPressed.connect(self._on_quick_filter_applied)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

    def _on_stats_updated(self, total_count: int, loaded_count: int):
        has_filter = self.model.has_active_filter()
        if has_filter:
            self.set_info_text(f"{total_count:,} games matched (Filter Active)")
        else:
            self.set_info_text(f"{total_count:,} games")
        self.filterStateChanged.emit(has_filter)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == QtCore.Qt.Key_Delete:
            self.delete_selected_game()
        else:
            super().keyPressEvent(event)

    def get_selected_row_and_game(self) -> tuple[Optional[int], Optional[dict]]:
        sel = self.table.selectionModel()
        if not sel or not sel.hasSelection():
            return None, None
        indexes = sel.selectedRows()
        if not indexes:
            return None, None
        row = indexes[0].row()
        return row, self.model.get_game_at(row)

    def _on_table_context_menu(self, pos: QtCore.QPoint):
        row, game_item = self.get_selected_row_and_game()
        if row is None or not game_item:
            return

        import qtawesome as qta
        menu = QtWidgets.QMenu(self)

        open_act = menu.addAction(qta.icon("fa5s.chess-board", color="#a9aea7"), "Open Game in Analyzer")
        open_act.triggered.connect(lambda: self._on_double_clicked(self.model.index(row, 0)))

        copy_act = menu.addAction(qta.icon("fa5s.copy", color="#a9aea7"), "Copy PGN")
        copy_act.triggered.connect(self.copy_selected_game_pgn)

        menu.addSeparator()

        is_del = game_item.get("deleted", False)
        if is_del:
            undel_act = menu.addAction(qta.icon("fa5s.undo", color="#4ade80"), "Undelete Game")
            undel_act.triggered.connect(self.undelete_selected_game)
        else:
            del_act = menu.addAction(qta.icon("fa5s.trash-alt", color="#f87171"), "Delete Game")
            del_act.triggered.connect(self.delete_selected_game)

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def copy_selected_game_pgn(self):
        row, game_item = self.get_selected_row_and_game()
        if row is None or not game_item or not self.client or not self.client.is_running():
            return
        game_id = game_item.get("id", row)

        def on_pgn(resp: dict):
            if resp.get("status") == "ok":
                pgn_text = resp.get("data", {}).get("pgn", "")
                QtWidgets.QApplication.clipboard().setText(pgn_text)

        self.client.get_pgn(int(game_id), callback=on_pgn)

    def delete_selected_game(self):
        row, game_item = self.get_selected_row_and_game()
        if row is None or not game_item or not self.client or not self.client.is_running():
            return
        game_id = game_item.get("id", row)

        def on_del(resp: dict):
            if resp.get("status") == "ok":
                self.model.set_game_deleted_status(row, True)
                self.client.save_database()
                self.gameDeleted.emit(int(game_id))

        self.client.delete_game(int(game_id), callback=on_del)

    def undelete_selected_game(self):
        row, game_item = self.get_selected_row_and_game()
        if row is None or not game_item or not self.client or not self.client.is_running():
            return
        game_id = game_item.get("id", row)

        def on_undel(resp: dict):
            if resp.get("status") == "ok":
                self.model.set_game_deleted_status(row, False)
                self.client.save_database()
                self.gameUndeleted.emit(int(game_id))

        self.client.undelete_game(int(game_id), callback=on_undel)

    def set_client(self, client: ScidClient):
        self.client = client
        self.model.set_client(client)

    def load_database(self, total_games: int, filter_dict: Optional[dict] = None):
        """Load games into the virtual table model."""
        self.model.set_db(total_games, filter_dict)
        self.restore_header_state()
        self.loadFinished.emit(total_games)

    def load_search_session(self, search_id: str, total_matches: int, filter_dict: Optional[dict] = None):
        """Load paginated search session results into the virtual table."""
        self.model.set_db(total_matches, filter_dict, search_id=search_id)
        self.restore_header_state()
        self.loadFinished.emit(total_matches)
        if total_matches > 0:
            self.table.selectRow(0)

    def _on_sort_started(self):
        if not getattr(self, "_is_sorting_cursor", False):
            self._is_sorting_cursor = True
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            QtCore.QTimer.singleShot(4000, self._on_sort_finished)

    def _on_sort_finished(self):
        if getattr(self, "_is_sorting_cursor", False):
            self._is_sorting_cursor = False
            QtWidgets.QApplication.restoreOverrideCursor()

    def clear(self):
        self._on_sort_finished()
        self.model.clear()
        self.set_info_text("")

    def closeEvent(self, event):
        self._on_sort_finished()
        super().closeEvent(event)

    def set_info_text(self, text: str):
        self.info_label.setText(str(text))

    def _on_quick_filter_applied(self):
        text = self.filter_edit.text().strip()
        f = dict(self.model.filters)
        if text:
            f["player"] = text
        else:
            f.pop("player", None)
        self.model.set_filters(f)

    def _on_header_clicked(self, logical_index: int):
        order = self.table.horizontalHeader().sortIndicatorOrder()
        self.model.toggle_sort_column(logical_index, order)

    def _on_double_clicked(self, proxy_index: QtCore.QModelIndex):
        if not proxy_index.isValid() or not self.client or not self.client.is_running():
            return

        row_idx = proxy_index.row()
        self.load_game_at_row(row_idx)

    def load_game_at_row(self, row_idx: int):
        """Loads game at specific row index and emits gameSelected signal."""
        if not self.client or not self.client.is_running():
            return
        if row_idx < 0 or row_idx >= self.model.total_count:
            return

        model_index = self.model.index(row_idx, 0)
        if model_index.isValid():
            self.table.selectRow(row_idx)
            self.table.scrollTo(model_index)

        game_item = self.model.get_game_at(row_idx)
        if game_item:
            game_id = game_item.get("id", row_idx)
            self._fetch_and_emit_game(row_idx, game_id, game_item)
        else:
            page = row_idx // self.model.CHUNK_SIZE
            def on_chunk_loaded(resp: dict):
                if resp.get("status") == "ok":
                    self.model.on_backend_response(resp)
                item = self.model.get_game_at(row_idx) or {}
                gid = item.get("id", row_idx)
                self._fetch_and_emit_game(row_idx, gid, item)
            self.client.query_games(
                page=page,
                page_size=self.model.CHUNK_SIZE,
                filter_dict=self.model.filters if not self.model.search_id else None,
                sort_by=self.model.filters.get("sort_by"),
                sort_direction=self.model.filters.get("sort_direction"),
                sort_asc=self.model.sort_asc,
                search_id=self.model.search_id,
                callback=on_chunk_loaded,
            )

    def _fetch_and_emit_game(self, row_idx: int, game_id: int, game_item: dict):
        def on_pgn_received(resp: dict):
            if resp.get("status") == "ok":
                pgn_text = resp.get("data", {}).get("pgn", "")
                display_id = game_item.get("id", game_id)
                if isinstance(display_id, int):
                    display_id = display_id + 1
                matching_plies = game_item.get("matching_plies") or []
                match_count = game_item.get("match_count", len(matching_plies))
                payload = {
                    "ID": str(display_id),
                    "White": game_item.get("white", "?"),
                    "EloW": str(game_item.get("white_elo", "")),
                    "Black": game_item.get("black", "?"),
                    "EloB": str(game_item.get("black_elo", "")),
                    "Result": game_item.get("result", "*"),
                    "ECO": game_item.get("eco", ""),
                    "Date": game_item.get("date", ""),
                    "Event": game_item.get("event", ""),
                    "Site": game_item.get("site", ""),
                    "Round": str(game_item.get("round", "")),
                    "PGN": pgn_text,
                    "matching_plies": matching_plies,
                    "match_count": match_count,
                    "_matching_plies": matching_plies,
                    "_id": game_id,
                    "_row_idx": row_idx,
                    "_total_rows": self.model.total_count,
                }
                self.gameSelected.emit(payload)

        self.client.get_pgn(int(game_id), callback=on_pgn_received)

    def save_header_state(self):
        settings = QtCore.QSettings("QChessApp", "Config")
        settings.setValue("home_table_header_state", self.table.horizontalHeader().saveState())

    def restore_header_state(self):
        settings = QtCore.QSettings("QChessApp", "Config")
        state = settings.value("home_table_header_state")
        if state is not None:
            self.table.horizontalHeader().restoreState(state)
        else:
            self._apply_default_widths()

    def _apply_default_widths(self):
        default_widths = {
            "ID": 55,
            "White": 160,
            "EloW": 65,
            "Black": 160,
            "EloB": 65,
            "Result": 70,
            "ECO": 55,
            "Date": 90,
            "Event": 160,
            "Site": 130,
            "Round": 55,
            "Status": 70,
        }
        for i, h in enumerate(GameListTableModel.HEADERS):
            width = default_widths.get(h, 100)
            self.table.setColumnWidth(i, width)

    def _on_header_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)
        header = self.table.horizontalHeader()
        for idx in range(len(GameListTableModel.HEADERS)):
            name = GameListTableModel.HEADERS[idx]
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(idx))
            action.triggered.connect(
                lambda checked, col_idx=idx: self.toggle_column_visibility(col_idx, checked)
            )

        menu.addSeparator()
        config_action = menu.addAction("Configure Columns...")
        config_action.triggered.connect(self.configure_columns)
        menu.exec_(self.table.horizontalHeader().mapToGlobal(pos))

    def toggle_column_visibility(self, col_idx, visible):
        self.table.horizontalHeader().setSectionHidden(col_idx, not visible)
        self.save_header_state()

    def configure_columns(self):
        dlg = ColumnConfigDialog(
            self.table.horizontalHeader(), GameListTableModel.HEADERS, self
        )
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            settings = dlg.get_column_settings()
            header = self.table.horizontalHeader()
            header.blockSignals(True)

            for visual_idx, s in enumerate(settings):
                logical_idx = s["logical_idx"]
                visible = s["visible"]
                header.setSectionHidden(logical_idx, not visible)
                curr_vis = header.visualIndex(logical_idx)
                if curr_vis != visual_idx:
                    header.moveSection(curr_vis, visual_idx)

            header.blockSignals(False)
            self.save_header_state()


class ColumnConfigDialog(QtWidgets.QDialog):
    def __init__(self, header_view, headers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Columns")
        self.resize(320, 400)
        self.header_view = header_view
        self.headers = headers

        layout = QtWidgets.QVBoxLayout(self)

        info_lbl = QtWidgets.QLabel(
            "Drag items or use buttons to reorder.\nCheck/uncheck to show/hide columns."
        )
        info_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px;")
        layout.addWidget(info_lbl)

        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        layout.addWidget(self.list_widget)

        btn_layout = QtWidgets.QHBoxLayout()
        self.up_btn = QtWidgets.QPushButton("Move Up")
        self.down_btn = QtWidgets.QPushButton("Move Down")
        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)
        layout.addLayout(btn_layout)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load_columns()

        self.up_btn.clicked.connect(self.move_up)
        self.down_btn.clicked.connect(self.move_down)

    def load_columns(self):
        visual_map = {}
        for logical_idx in range(len(self.headers)):
            vis_idx = self.header_view.visualIndex(logical_idx)
            visual_map[vis_idx] = logical_idx

        for vis_idx in sorted(visual_map.keys()):
            logical_idx = visual_map[vis_idx]
            name = self.headers[logical_idx]
            is_hidden = self.header_view.isSectionHidden(logical_idx)

            item = QtWidgets.QListWidgetItem(name, self.list_widget)
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemIsUserCheckable
                | QtCore.Qt.ItemIsSelectable
                | QtCore.Qt.ItemIsDragEnabled
            )
            item.setCheckState(QtCore.Qt.Unchecked if is_hidden else QtCore.Qt.Checked)
            item.setData(QtCore.Qt.UserRole, logical_idx)

    def move_up(self):
        row = self.list_widget.currentRow()
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            self.list_widget.setCurrentRow(row - 1)

    def move_down(self):
        row = self.list_widget.currentRow()
        if row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            self.list_widget.setCurrentRow(row + 1)

    def get_column_settings(self):
        settings = []
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            logical_idx = item.data(QtCore.Qt.UserRole)
            visible = item.checkState() == QtCore.Qt.Checked
            settings.append({"logical_idx": logical_idx, "visible": visible})
        return settings
