from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QDialogButtonBox,
    QLabel,
    QApplication
)
from PyQt5.QtCore import Qt

class PGNImportDlg(QDialog):
    def __init__(self, parent=None, initial_text=""):
        super().__init__(parent)
        self.setWindowTitle("Import PGN")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Paste or edit your PGN here:"))
        
        self.text_edit = QTextEdit()
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("1. e4 e5 ...")
        self.text_edit.setPlainText(initial_text)
        layout.addWidget(self.text_edit)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Ok).setText("Import")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_pgn(self):
        return self.text_edit.toPlainText().strip()
