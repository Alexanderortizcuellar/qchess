from PyQt5.QtWidgets import QDialog, QPushButton, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QEvent
from utils.helpers import _qicon


class VariationsDialog(QDialog):
    def __init__(self, variations: dict, font_family: str = "Noto Sans", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Variations")
        self.setMinimumWidth(200)

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.selected_index = None
        self.row_to_index = {}

        is_dark = True
        if parent and hasattr(parent, "is_dark"):
            is_dark = parent.is_dark

        self.list_widget = QListWidget()
        # QFont expects a single raw font family name, not a CSS string with quotes/fallbacks.
        # Clean up the font_family to prevent slow system-wide font resolution freezes.
        clean_font = font_family.split(",")[0].strip("'\" ")
        self.list_widget.setFont(QFont(clean_font, 16))
        self.list_widget.installEventFilter(self)
        self.list_widget.itemActivated.connect(self.on_item_activated)

        for index, item in variations.items():
            list_item = QListWidgetItem(item.get("line", item["san"]))
            self.list_widget.addItem(list_item)
            row = self.list_widget.count() - 1
            self.row_to_index[row] = index

        layout.addWidget(self.list_widget)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self.list_widget.setFocus()

        # Add "Move Up" and "Move Down" buttons horizontally at the bottom
        nav_layout = QHBoxLayout()
        
        self.btn_up = QPushButton("Move Up")
        self.btn_up.setIcon(_qicon("fa5s.arrow-up", is_dark=is_dark))
        self.btn_up.setCursor(Qt.PointingHandCursor)
        self.btn_up.clicked.connect(self.move_up)

        self.btn_down = QPushButton("Move Down")
        self.btn_down.setIcon(_qicon("fa5s.arrow-down", is_dark=is_dark))
        self.btn_down.setCursor(Qt.PointingHandCursor)
        self.btn_down.clicked.connect(self.move_down)

        nav_layout.addWidget(self.btn_up)
        nav_layout.addWidget(self.btn_down)
        layout.addLayout(nav_layout)

    def move_up(self):
        count = self.list_widget.count()
        if count == 0:
            return
        current = self.list_widget.currentRow()
        new_row = (current - 1) % count
        self.list_widget.setCurrentRow(new_row)

    def move_down(self):
        count = self.list_widget.count()
        if count == 0:
            return
        current = self.list_widget.currentRow()
        new_row = (current + 1) % count
        self.list_widget.setCurrentRow(new_row)

    def on_item_activated(self, item):
        row = self.list_widget.row(item)
        var_idx = self.row_to_index.get(row)
        if var_idx is not None:
            self.selected_index = var_idx
            self.accept()

    def eventFilter(self, obj, event):
        if obj == self.list_widget and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Right:
                row = self.list_widget.currentRow()
                if row != -1:
                    var_idx = self.row_to_index.get(row)
                    if var_idx is not None:
                        self.selected_index = var_idx
                        self.accept()
                        return True
            elif event.key() == Qt.Key_Left:
                self.reject()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            row = self.list_widget.currentRow()
            if row != -1:
                var_idx = self.row_to_index.get(row)
                if var_idx is not None:
                    self.selected_index = var_idx
                    self.accept()
                    return
        super().keyPressEvent(event)
