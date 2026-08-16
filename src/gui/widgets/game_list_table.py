import sqlite3
import re
from typing import Dict

from PyQt5 import QtCore, QtWidgets, QtGui


def format_int_eco(eco_val) -> str:
    if eco_val is None:
        return "??"
    try:
        code = int(eco_val)
        if code < 0 or code >= 500:
            return "??"
        letter = chr(ord('A') + (code // 100))
        num = code % 100
        return f"{letter}{num:02d}"
    except Exception:
        return "??"


def get_eco_filter_sql(filter_text: str):
    """
    Returns (sql_condition_str, params_list) or None if it doesn't match an ECO pattern.
    """
    text = filter_text.strip().upper()
    # Match full ECO code: e.g. "B12"
    if re.match(r"^[A-E]\d{2}$", text):
        letter = text[0]
        num = int(text[1:3])
        code = (ord(letter) - ord('A')) * 100 + num
        return "g.eco = ?", [code]
    # Match partial ECO prefix: e.g. "B1" (matches B10-B19)
    elif re.match(r"^[A-E]\d$", text):
        letter = text[0]
        digit = int(text[1])
        start_code = (ord(letter) - ord('A')) * 100 + digit * 10
        end_code = start_code + 9
        return "g.eco BETWEEN ? AND ?", [start_code, end_code]
    # Match single letter ECO prefix: e.g. "B" (matches B00-B99)
    elif re.match(r"^[A-E]$", text):
        letter = text[0]
        start_code = (ord(letter) - ord('A')) * 100
        end_code = start_code + 99
        return "g.eco BETWEEN ? AND ?", [start_code, end_code]

    return None


RESULT_MAP = {
    0: "*",
    1: "0-1",
    2: "1/2-1/2",
    3: "1-0",
}


def format_int_result(res_val) -> str:
    if res_val is None:
        return "*"
    try:
        return RESULT_MAP.get(int(res_val), "*")
    except Exception:
        return "*"


def format_int_date(date_val) -> str:
    if date_val is None:
        return "????.??.??"
    try:
        date_int = int(date_val)
        if date_int <= 0:
            return "????.??.??"

        # Extract components
        year = date_int // 10000
        month = (date_int % 10000) // 100
        day = date_int % 100

        year_str = f"{year:04d}" if year > 0 else "????"
        month_str = f"{month:02d}" if month > 0 else "??"
        day_str = f"{day:02d}" if day > 0 else "??"

        return f"{year_str}.{month_str}.{day_str}"
    except Exception:
        return "????.??.??"


class GameListTableModel(QtCore.QAbstractTableModel):
    """
    Read-only table model that fetches rows on-demand from a SQLite PGN index.
    Includes a sliding-window cache for seamless virtualized scrolling.
    """

    HEADERS = [
        "Event",
        "Site",
        "Date",
        "Round",
        "White",
        "Black",
        "EloW",
        "EloB",
        "Result",
        "ECO",
        "Move Count",
        "Moves",
    ]

    COLUMNS_MAP = {
        "Event": "e.name",
        "Site": "s.name",
        "Date": "g.date",
        "Round": "g.round",
        "White": "pw.name",
        "Black": "pb.name",
        "EloW": "g.white_elo",
        "EloB": "g.black_elo",
        "Result": "g.result",
        "ECO": "g.eco",
        "Move Count": "g.num_moves",
        "Moves": "g.id",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conn = None
        self.total_rows = 0
        self.pgn_path = None

        self.filter_text = ""
        self.sort_column = "g.id"
        self.sort_order = "ASC"

        self._cache = {}
        self._cache_start = -1
        self._cache_size = 200

        self._lazy_load_timer = QtCore.QTimer()
        self._lazy_load_timer.setSingleShot(True)
        self._lazy_load_timer.timeout.connect(self._on_lazy_load_timeout)
        self._pending_load_row = -1

    def set_db(self, conn, total_rows, pgn_path):
        self.beginResetModel()
        self.conn = conn
        self.total_rows = total_rows
        self.pgn_path = pgn_path

        self.filter_text = ""
        self.sort_column = "g.id"
        self.sort_order = "ASC"

        self._cache.clear()
        self._cache_start = -1
        self.endResetModel()

    def set_filter(self, filter_text: str):
        self.beginResetModel()
        self.filter_text = filter_text.strip()
        self._cache.clear()
        self._cache_start = -1

        if not self.conn:
            self.total_rows = 0
            self.endResetModel()
            return

        cursor = self.conn.cursor()
        if self.filter_text:
            like_pat = f"%{self.filter_text}%"
            eco_res = get_eco_filter_sql(self.filter_text)
            if eco_res:
                eco_cond, eco_params = eco_res
            else:
                eco_cond, eco_params = "g.eco = -2", []

            cursor.execute(
                f"""
                SELECT COUNT(*) FROM games g
                LEFT JOIN players pw ON g.white_id = pw.id
                LEFT JOIN players pb ON g.black_id = pb.id
                LEFT JOIN events e ON g.event_id = e.id
                LEFT JOIN sites s ON g.site_id = s.id
                WHERE pw.name LIKE ? OR pb.name LIKE ? OR e.name LIKE ? OR s.name LIKE ? OR {eco_cond}
                """,
                [like_pat, like_pat, like_pat, like_pat] + eco_params,
            )
            self.total_rows = cursor.fetchone()[0]
        else:
            cursor.execute("SELECT COUNT(*) FROM games")
            self.total_rows = cursor.fetchone()[0]

        self.endResetModel()

    def sort(self, col: int, order: QtCore.Qt.SortOrder):
        self.beginResetModel()
        col_name = self.HEADERS[col]
        self.sort_column = self.COLUMNS_MAP.get(col_name, "g.id")
        self.sort_order = "DESC" if order == QtCore.Qt.DescendingOrder else "ASC"

        self._cache.clear()
        self._cache_start = -1
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else self.total_rows

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.DisplayRole):
        if not index.isValid() or not self.conn:
            return None

        row = index.row()
        col = index.column()

        if role == QtCore.Qt.FontRole:
            col_name = self.HEADERS[col]
            font = QtGui.QFont("Segoe UI", 10)
            if col_name in ("White", "Black", "Result"):
                font.setBold(True)
            return font

        if role == QtCore.Qt.TextAlignmentRole:
            col_name = self.HEADERS[col]
            if col_name in ("EloW", "EloB", "Result", "Date", "Round", "ECO", "Move Count"):
                return QtCore.Qt.AlignCenter

        if role in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            # Fetch cache block if requested index is outside the sliding window
            if not (self._cache_start <= row < self._cache_start + len(self._cache)):
                self._pending_load_row = row
                self._lazy_load_timer.start(80)  # 80ms debounce
                return None

            row_data = self._cache.get(row)
            if not row_data:
                return None

            col_name = self.HEADERS[col]
            if col_name == "Event":
                return row_data[8]
            elif col_name == "Site":
                return row_data[9]
            elif col_name == "Date":
                return format_int_date(row_data[7])
            elif col_name == "Round":
                return row_data[10] if row_data[10] is not None else "-"
            elif col_name == "White":
                return row_data[1]
            elif col_name == "Black":
                return row_data[2]
            elif col_name == "EloW":
                return str(row_data[4]) if row_data[4] is not None else ""
            elif col_name == "EloB":
                return str(row_data[5]) if row_data[5] is not None else ""
            elif col_name == "Result":
                return format_int_result(row_data[3])
            elif col_name == "ECO":
                return format_int_eco(row_data[6])
            elif col_name == "Move Count":
                return str(row_data[13]) if row_data[13] is not None else "0"
            elif col_name == "Moves":
                return ""

        return None

    def _load_cache_slice(self, center_row):
        if not self.conn:
            return

        start = max(0, center_row - self._cache_size // 2)
        cursor = self.conn.cursor()

        query_base = (
            "SELECT g.id, pw.name AS white, pb.name AS black, g.result, g.white_elo, g.black_elo, g.eco, g.date, e.name AS event, s.name AS site, g.round, g.offset, g.length, g.num_moves "
            "FROM games g "
            "LEFT JOIN players pw ON g.white_id = pw.id "
            "LEFT JOIN players pb ON g.black_id = pb.id "
            "LEFT JOIN events e ON g.event_id = e.id "
            "LEFT JOIN sites s ON g.site_id = s.id "
        )

        if self.filter_text:
            like_pat = f"%{self.filter_text}%"
            eco_res = get_eco_filter_sql(self.filter_text)
            if eco_res:
                eco_cond, eco_params = eco_res
            else:
                eco_cond, eco_params = "g.eco = -2", []

            query = (
                f"{query_base} WHERE pw.name LIKE ? OR pb.name LIKE ? OR e.name LIKE ? OR s.name LIKE ? OR {eco_cond} "
                f"ORDER BY {self.sort_column} {self.sort_order} LIMIT ? OFFSET ?"
            )
            cursor.execute(
                query,
                [like_pat, like_pat, like_pat, like_pat] + eco_params + [self._cache_size, start],
            )
        else:
            query = f"{query_base} ORDER BY {self.sort_column} {self.sort_order} LIMIT ? OFFSET ?"
            cursor.execute(query, (self._cache_size, start))

        rows = cursor.fetchall()
        self._cache.clear()
        for idx, r in enumerate(rows):
            self._cache[start + idx] = r
        self._cache_start = start

    def _on_lazy_load_timeout(self):
        if self._pending_load_row != -1:
            row = self._pending_load_row
            self._pending_load_row = -1
            self._load_cache_slice(row)
            self.layoutChanged.emit()

    def headerData(
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role=QtCore.Qt.DisplayRole,
    ):
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return self.HEADERS[section]
        return section + 1

    def flags(self, index: QtCore.QModelIndex):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def row_dict(self, row_idx: int) -> Dict[str, str]:
        if not (self._cache_start <= row_idx < self._cache_start + len(self._cache)):
            self._load_cache_slice(row_idx)

        row_data = self._cache.get(row_idx)
        if not row_data:
            return {}

        return {
            "Event": row_data[8],
            "Site": row_data[9],
            "Date": format_int_date(row_data[7]),
            "Round": row_data[10] if row_data[10] is not None else "-",
            "White": row_data[1],
            "Black": row_data[2],
            "EloW": str(row_data[4]) if row_data[4] is not None else "",
            "EloB": str(row_data[5]) if row_data[5] is not None else "",
            "Result": format_int_result(row_data[3]),
            "ECO": format_int_eco(row_data[6]),
            "Move Count": str(row_data[13]) if row_data[13] is not None else "0",
            "_offset": row_data[11],
            "_length": row_data[12],
            "_pgn_path": self.pgn_path,
        }


class GameListTableWidget(QtWidgets.QWidget):
    """
    Results table widget utilizing SQLite lazy-loading.
    Double-clicking a game offsets/reads from the PGN file on-demand.
    """

    gameSelected = QtCore.pyqtSignal(dict)
    loadFinished = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.conn = None

        self.filter_edit = QtWidgets.QLineEdit(self)
        self.filter_edit.setPlaceholderText("Filter games instantly...")

        self.table = QtWidgets.QTableView(self)
        self.table.setFont(QtGui.QFont("Segoe UI", 10))
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)

        self.info_label = QtWidgets.QLabel(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.info_label)

        self.model = GameListTableModel(self)
        self.table.setModel(self.model)

        self._hide_moves_column()

        # Reordering and layout persistence setup
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.sectionMoved.connect(self.save_header_state)
        header.sectionResized.connect(self.save_header_state)
        header.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_context_menu)

        self.filter_edit.textChanged.connect(self._on_filter_text_changed)
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

    def load_db(self, db_path: str, pgn_path: str):
        """Connect to indexed SQLite database and load model."""
        if self.conn:
            self.conn.close()

        self.conn = sqlite3.connect(db_path)

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM games")
        total_rows = cursor.fetchone()[0]

        self.model.set_db(self.conn, total_rows, pgn_path)

        # Restore header state (widths, reordering, hidden state)
        self.restore_header_state()

        self.loadFinished.emit(total_rows)

    def clear(self):
        """Clears connection and table rows."""
        if self.conn:
            self.conn.close()
            self.conn = None
        self.model.set_db(None, 0, None)
        self.set_info_text("")

    def set_info_text(self, text: str):
        self.info_label.setText(str(text))

    def _hide_moves_column(self):
        try:
            moves_col = GameListTableModel.HEADERS.index("Moves")
            self.table.setColumnHidden(moves_col, True)
        except ValueError:
            pass

    def _on_filter_text_changed(self, text: str):
        self.model.set_filter(text)
        self.set_info_text(f"Filtered: {self.model.total_rows} matches")

    def _on_header_clicked(self, logical_index: int):
        order = self.table.horizontalHeader().sortIndicatorOrder()
        self.model.sort(logical_index, order)

    def _on_double_clicked(self, proxy_index: QtCore.QModelIndex):
        if not proxy_index.isValid():
            return

        row_idx = proxy_index.row()
        row_data = self.model.row_dict(row_idx)
        if not row_data:
            return

        offset = row_data.get("_offset")
        length = row_data.get("_length")
        pgn_path = row_data.get("_pgn_path")

        pgn_text = ""
        if pgn_path and offset is not None and length is not None:
            try:
                with open(pgn_path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(offset)
                    pgn_text = f.read(length)
            except Exception as e:
                print(f"Error lazy-loading PGN: {e}")

        payload = {h: row_data.get(h, "") for h in GameListTableModel.HEADERS}
        payload["PGN"] = pgn_text
        payload["_pgn_path"] = pgn_path
        payload["_offset"] = offset
        payload["_length"] = length
        self.gameSelected.emit(payload)

    def save_header_state(self):
        from PyQt5.QtCore import QSettings

        settings = QSettings("QChessApp", "Config")
        settings.setValue(
            "home_table_header_state", self.table.horizontalHeader().saveState()
        )

    def restore_header_state(self):
        from PyQt5.QtCore import QSettings

        settings = QSettings("QChessApp", "Config")
        state = settings.value("home_table_header_state")
        if state is not None:
            self.table.horizontalHeader().restoreState(state)
            self._hide_moves_column()
        else:
            self._apply_default_widths()

    def _apply_default_widths(self):
        default_widths = {
            "Event": 180,
            "Site": 150,
            "Date": 95,
            "Round": 60,
            "White": 160,
            "Black": 160,
            "EloW": 75,
            "EloB": 75,
            "Result": 75,
            "ECO": 60,
            "Move Count": 85,
        }
        for i, h in enumerate(GameListTableModel.HEADERS):
            width = default_widths.get(h, 100)
            self.table.setColumnWidth(i, width)
        self._hide_moves_column()

    def _on_header_context_menu(self, pos):
        menu = QtWidgets.QMenu(self)

        # Add checkable items for each column (except "Moves")
        header = self.table.horizontalHeader()
        for idx in range(len(GameListTableModel.HEADERS)):
            name = GameListTableModel.HEADERS[idx]
            if name == "Moves":
                continue

            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(not header.isSectionHidden(idx))
            action.triggered.connect(
                lambda checked, col_idx=idx: self.toggle_column_visibility(
                    col_idx, checked
                )
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
            self._hide_moves_column()
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

        # List Widget
        self.list_widget = QtWidgets.QListWidget(self)
        self.list_widget.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        layout.addWidget(self.list_widget)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.up_btn = QtWidgets.QPushButton("Move Up")
        self.down_btn = QtWidgets.QPushButton("Move Down")
        btn_layout.addWidget(self.up_btn)
        btn_layout.addWidget(self.down_btn)
        layout.addLayout(btn_layout)

        # Buttons box
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load columns
        self.load_columns()

        # Connections
        self.up_btn.clicked.connect(self.move_up)
        self.down_btn.clicked.connect(self.move_down)

    def load_columns(self):
        visual_map = {}
        for logical_idx in range(len(self.headers)):
            if self.headers[logical_idx] == "Moves":
                continue
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
