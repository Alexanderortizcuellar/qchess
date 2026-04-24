from PyQt5.QtWidgets import QDialog, QPushButton, QVBoxLayout
from PyQt5.QtGui import QFont


class VariationsDialog(QDialog):
    def __init__(self, variations: dict):
        super().__init__()
        self.setWindowTitle("Variations")
        self.setGeometry(100, 100, 300, 200)

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.selected_index = None

        for index, item in variations.items():
            button = QPushButton(f"{item['san']}")
            button.setFont(QFont("Noto Sans", 16))
            button.clicked.connect(
                lambda _, i=index, m=item["san"]: self.select_variation(m, i)
            )
            layout.addWidget(button)

    def select_variation(self, _, index):
        # Handle the selection of a variation
        self.selected_index = index
        self.accept()
