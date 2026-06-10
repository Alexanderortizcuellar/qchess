from PyQt5.QtWidgets import QDialog, QPushButton, QVBoxLayout
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt, QEvent


class VariationsDialog(QDialog):
    def __init__(self, variations: dict, font_family: str = "Noto Sans"):
        super().__init__()
        self.setWindowTitle("Variations")
        self.setMinimumWidth(200)

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.selected_index = None
        self.buttons = []

        for index, item in variations.items():
            button = QPushButton(f"{item['san']}")
            button.setFont(QFont(font_family, 16))
            button.clicked.connect(
                lambda _, i=index, m=item["san"]: self.select_variation(m, i)
            )
            # Install event filter to capture keys before the button handles them
            button.installEventFilter(self)
            layout.addWidget(button)
            self.buttons.append(button)

        if self.buttons:
            self.buttons[0].setDefault(True)
            self.buttons[0].setFocus()

    def select_variation(self, _, index):
        # Handle the selection of a variation
        self.selected_index = index
        self.accept()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Right:
                # If a button has focus, select its specific variation
                for i, btn in enumerate(self.buttons):
                    if btn.hasFocus():
                        self.select_variation(None, i)
                        return True
                # Fallback to main line if no button has focus (shouldn't happen)
                if self.buttons:
                    self.select_variation(None, 0)
                    return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            # Check which button has focus and select it
            for i, btn in enumerate(self.buttons):
                if btn.hasFocus():
                    self.select_variation(None, i)
                    return
            # Default to main line
            if self.buttons:
                self.select_variation(None, 0)
                return
        super().keyPressEvent(event)
