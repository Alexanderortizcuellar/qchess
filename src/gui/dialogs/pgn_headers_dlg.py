from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QDialogButtonBox, QLabel,
    QDateEdit, QComboBox, QMenu
)
from PyQt5.QtCore import QDate
import qtawesome as qta


class PGNHeadersWidget(QWidget):
    def __init__(self, parent=None, headers=None):
        super().__init__(parent)
        self.headers = headers or {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Helper info label
        info_label = QLabel("Double-click cells to edit Tag Name or Value.")
        info_label.setStyleSheet("color: #8b8987; font-style: italic;")
        layout.addWidget(info_label)

        # Table setup
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Tag Name", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(False)
        layout.addWidget(self.table)

        # Action Buttons for adding/removing tags
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add Tag")
        self.add_btn.setIcon(qta.icon("fa5s.plus", color="#ffffff"))
        self.add_btn.clicked.connect(self.add_tag)

        self.remove_btn = QPushButton("Remove Tag")
        self.remove_btn.setIcon(qta.icon("fa5s.minus", color="#ffffff"))
        self.remove_btn.clicked.connect(self.remove_tag)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Connect itemChanged to handle dynamic swap of cell widgets on tag name change
        self.table.itemChanged.connect(self.on_item_changed)

        self.populate_table()

    def parse_pgn_date(self, date_str):
        if date_str:
            parts = date_str.split('.')
            if len(parts) == 3:
                try:
                    y = int(parts[0])
                    m = int(parts[1])
                    d = int(parts[2])
                    qdate = QDate(y, m, d)
                    if qdate.isValid():
                        return qdate
                except ValueError:
                    pass
        return QDate.currentDate()

    def update_row_widget(self, row, tag, value=None):
        if value is None:
            cell_widget = self.table.cellWidget(row, 1)
            if isinstance(cell_widget, QDateEdit):
                value = cell_widget.date().toString("yyyy.MM.dd")
            elif isinstance(cell_widget, QComboBox):
                value = cell_widget.currentText()
            else:
                val_item = self.table.item(row, 1)
                value = val_item.text().strip() if val_item else ""

        cell_widget = self.table.cellWidget(row, 1)
        if tag == "Date":
            if not isinstance(cell_widget, QDateEdit):
                self.table.removeCellWidget(row, 1)
                date_edit = QDateEdit()
                date_edit.setDisplayFormat("yyyy.MM.dd")
                date_edit.setCalendarPopup(True)
                date_edit.setDate(self.parse_pgn_date(value))
                self.table.setCellWidget(row, 1, date_edit)
        elif tag == "Result":
            if not isinstance(cell_widget, QComboBox):
                self.table.removeCellWidget(row, 1)
                combo = QComboBox()
                combo.addItems(["*", "1-0", "0-1", "1/2-1/2"])
                idx = combo.findText(value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                self.table.setCellWidget(row, 1, combo)
        else:
            if cell_widget is not None:
                self.table.removeCellWidget(row, 1)
            val_item = self.table.item(row, 1)
            if not val_item:
                val_item = QTableWidgetItem(value)
                self.table.setItem(row, 1, val_item)
            else:
                val_item.setText(value)

    def on_item_changed(self, item):
        if item.column() == 0:
            row = item.row()
            tag = item.text().strip()
            self.table.blockSignals(True)
            self.update_row_widget(row, tag)
            self.table.blockSignals(False)

    def populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        str_tags = ["Event", "Site", "Date", "Round", "White", "Black", "Result"]
        
        all_tags = list(self.headers.keys())
        
        def tag_sort_key(tag):
            try:
                return (0, str_tags.index(tag))
            except ValueError:
                return (1, tag.lower())
                
        sorted_tags = sorted(all_tags, key=tag_sort_key)
        
        for tag in sorted_tags:
            value = self.headers[tag]
            self.add_table_row(tag, value)
        self.table.blockSignals(False)

    def add_table_row(self, tag="", value=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        tag_item = QTableWidgetItem(tag)
        self.table.setItem(row, 0, tag_item)
        
        self.update_row_widget(row, tag, value)
        return row

    def add_tag(self):
        # Determine which standard tags are not already in the table
        existing_tags = set()
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item:
                existing_tags.add(item.text().strip())

        all_potential_tags = [
            "WhiteElo",
            "BlackElo",
            "Annotator",
            "Termination",
            "TimeControl",
            "ECO",
            "Opening",
            "Variation",
            "PlyCount",
            "EventDate",
            "SetUp",
            "FEN"
        ]
        available_tags = [t for t in all_potential_tags if t not in existing_tags]

        # Show context menu to select a tag or add a custom one
        menu = QMenu(self)
        for tag in available_tags:
            action = menu.addAction(tag)
            action.triggered.connect(lambda checked, t=tag: self.perform_add_tag(t))

        if available_tags:
            menu.addSeparator()

        custom_action = menu.addAction("Custom...")
        custom_action.triggered.connect(lambda: self.perform_add_tag(None))

        menu.exec_(self.add_btn.mapToGlobal(self.add_btn.rect().bottomLeft()))

    def perform_add_tag(self, tag):
        self.table.blockSignals(True)
        if tag is None:
            # Custom tag
            row = self.add_table_row("NewTag", "")
            self.table.setCurrentCell(row, 0)
            self.table.blockSignals(False)
            self.table.editItem(self.table.item(row, 0))
        else:
            # Predefined tag
            row = self.add_table_row(tag, "")
            self.table.blockSignals(False)
            self.table.setCurrentCell(row, 1)
            cell_widget = self.table.cellWidget(row, 1)
            if cell_widget:
                cell_widget.setFocus()
            else:
                self.table.editItem(self.table.item(row, 1))

    def remove_tag(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def get_headers(self):
        headers = {}
        for row in range(self.table.rowCount()):
            tag_item = self.table.item(row, 0)
            if tag_item:
                tag = tag_item.text().strip()
                if not tag:
                    continue
                cell_widget = self.table.cellWidget(row, 1)
                if isinstance(cell_widget, QDateEdit):
                    val = cell_widget.date().toString("yyyy.MM.dd")
                elif isinstance(cell_widget, QComboBox):
                    val = cell_widget.currentText()
                else:
                    val_item = self.table.item(row, 1)
                    val = val_item.text().strip() if val_item else ""
                headers[tag] = val
        return headers


class PGNHeadersDialog(QDialog):
    def __init__(self, parent=None, headers=None, title="Edit PGN Headers"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(550, 450)
        
        layout = QVBoxLayout(self)
        
        self.headers_widget = PGNHeadersWidget(self, headers)
        layout.addWidget(self.headers_widget)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
    def get_headers(self):
        return self.headers_widget.get_headers()
