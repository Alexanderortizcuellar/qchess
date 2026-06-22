from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView, QDialogButtonBox, QLabel
)
from PyQt5.QtCore import Qt
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

        self.populate_table()

    def populate_table(self):
        self.table.setRowCount(0)
        # Seven Tag Roster (STR) order
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

    def add_table_row(self, tag="", value=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        tag_item = QTableWidgetItem(tag)
        val_item = QTableWidgetItem(value)
        
        self.table.setItem(row, 0, tag_item)
        self.table.setItem(row, 1, val_item)
        return row

    def add_tag(self):
        row = self.add_table_row("NewTag", "")
        self.table.setCurrentCell(row, 0)
        self.table.editItem(self.table.item(row, 0))

    def remove_tag(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def get_headers(self):
        headers = {}
        for row in range(self.table.rowCount()):
            tag_item = self.table.item(row, 0)
            val_item = self.table.item(row, 1)
            if tag_item:
                tag = tag_item.text().strip()
                val = val_item.text().strip() if val_item else ""
                if tag:
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
