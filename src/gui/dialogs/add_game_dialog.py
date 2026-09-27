import io
import chess.pgn
import qtawesome as qta
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QFormLayout,
)


class AddGameDialog(QDialog):
    """
    Dialog for adding a new game to the active SCID database by pasting or typing PGN.
    Includes instant PGN header validation and preview.
    """

    def _is_dark(self) -> bool:
        if self.parent() is not None and hasattr(self.parent(), "is_dark"):
            return bool(self.parent().is_dark)
        from PyQt5.QtCore import QSettings
        return QSettings("QChessApp", "Theme").value("theme", "dark") == "dark"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Game to Database")
        self.resize(600, 500)
        is_dark = self._is_dark()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        info_lbl = QLabel(
            "Paste or write a complete PGN game below. Headers and moves will be validated."
        )
        info_lbl.setStyleSheet(f"color: {'#9ca3af' if is_dark else '#475569'}; font-size: 11px;")
        main_layout.addWidget(info_lbl)

        # PGN Text Editor
        self.pgn_edit = QTextEdit(self)
        self.pgn_edit.setFont(QFont("Consolas", 10))
        self.pgn_edit.setPlaceholderText(
            '[Event "Casual Game"]\n'
            '[Site "City"]\n'
            '[Date "2026.01.01"]\n'
            '[Round "1"]\n'
            '[White "Player 1"]\n'
            '[Black "Player 2"]\n'
            '[Result "1-0"]\n\n'
            '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 1-0'
        )
        self.pgn_edit.textChanged.connect(self._validate_pgn)
        main_layout.addWidget(self.pgn_edit, 1)

        # Quick Headers Preview
        self.preview_box = QGroupBox("Detected Game Info")
        if is_dark:
            self.preview_box.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #403d39;
                    border-radius: 6px;
                    margin-top: 6px;
                    padding: 8px;
                    background-color: #21201d;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color: #a9aea7;
                }
            """)
        else:
            self.preview_box.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    margin-top: 6px;
                    padding: 8px;
                    background-color: #f8fafc;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color: #2563eb;
                }
            """)
        prev_layout = QFormLayout(self.preview_box)
        prev_layout.setContentsMargins(8, 8, 8, 8)
        prev_layout.setSpacing(6)

        self.lbl_players = QLabel("—")
        self.lbl_result = QLabel("—")
        self.lbl_moves = QLabel("—")
        prev_layout.addRow("Players:", self.lbl_players)
        prev_layout.addRow("Result:", self.lbl_result)
        prev_layout.addRow("Moves count:", self.lbl_moves)
        main_layout.addWidget(self.preview_box)

        # Buttons
        btn_box = QHBoxLayout()
        btn_paste = QPushButton(qta.icon("fa5s.paste", color="#a9aea7" if is_dark else "#475569"), "Paste from Clipboard")
        btn_paste.clicked.connect(self._paste_clipboard)
        btn_box.addWidget(btn_paste)

        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        self.btn_add = QPushButton(qta.icon("fa5s.plus", color="#ffffff"), "Add Game")
        disabled_bg = "#374151" if is_dark else "#e2e8f0"
        disabled_fg = "#6b7280" if is_dark else "#94a3b8"
        disabled_border = "#4b5563" if is_dark else "#cbd5e1"
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                font-weight: bold;
                background-color: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
                border-radius: 4px;
                padding: 6px 18px;
            }}
            QPushButton:hover {{
                background-color: #3b82f6;
            }}
            QPushButton:pressed {{
                background-color: #1d4ed8;
            }}
            QPushButton:disabled {{
                background-color: {disabled_bg};
                color: {disabled_fg};
                border: 1px solid {disabled_border};
            }}
        """)
        self.btn_add.clicked.connect(self._on_accept)
        self.btn_add.setEnabled(False)
        btn_box.addWidget(self.btn_add)

        main_layout.addLayout(btn_box)

    def _paste_clipboard(self):
        from PyQt5.QtWidgets import QApplication
        text = QApplication.clipboard().text()
        if text.strip():
            self.pgn_edit.setPlainText(text)

    def _validate_pgn(self):
        text = self.pgn_edit.toPlainText().strip()
        if not text:
            self.lbl_players.setText("—")
            self.lbl_result.setText("—")
            self.lbl_moves.setText("—")
            self.btn_add.setEnabled(False)
            return

        try:
            game = chess.pgn.read_game(io.StringIO(text))
            if game:
                w = game.headers.get("White", "?")
                b = game.headers.get("Black", "?")
                res = game.headers.get("Result", "*")
                moves_count = sum(1 for _ in game.mainline_moves())

                self.lbl_players.setText(f"<b>{w}</b> vs <b>{b}</b>")
                self.lbl_result.setText(res)
                self.lbl_moves.setText(f"{moves_count} moves")
                self.btn_add.setEnabled(True)
                return
        except Exception:
            pass

        self.lbl_players.setText("<i>Parsing incomplete...</i>")
        self.lbl_result.setText("—")
        self.lbl_moves.setText("—")
        self.btn_add.setEnabled(bool(text))

    def _on_accept(self):
        text = self.pgn_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Empty PGN", "Please paste or write a PGN before adding.")
            return
        self.accept()

    def get_pgn_text(self) -> str:
        return self.pgn_edit.toPlainText().strip()
