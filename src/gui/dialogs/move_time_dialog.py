import re
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QPushButton,
    QDialogButtonBox,
    QGroupBox,
    QLineEdit,
)
from PyQt5.QtCore import Qt
import qtawesome as qta


class MoveTimeDialog(QDialog):
    """Dialog to edit [%clk ...] clock time annotations on moves."""

    def __init__(self, parent=None, current_clk: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Tiempo Jugada")
        self.resize(350, 230)
        self.result_clk = current_clk.strip()

        # Parse initial time
        hours = 0
        minutes = 0
        seconds = 0

        if current_clk:
            # Matches H:MM:SS or MM:SS or H:MM:SS.s
            clean = current_clk.replace("[%clk", "").replace("]", "").strip()
            parts = clean.split(":")
            try:
                if len(parts) == 3:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(float(parts[2]))
                elif len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(float(parts[1]))
                elif len(parts) == 1:
                    seconds = int(float(parts[0]))
            except Exception:
                pass

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Time spinboxes group
        group = QGroupBox("Tiempo Restante (Reloj)")
        group_layout = QHBoxLayout(group)
        group_layout.setSpacing(6)

        self.spin_h = QSpinBox()
        self.spin_h.setRange(0, 99)
        self.spin_h.setValue(hours)
        self.spin_h.setSuffix(" h")

        self.spin_m = QSpinBox()
        self.spin_m.setRange(0, 59)
        self.spin_m.setValue(minutes)
        self.spin_m.setSuffix(" m")

        self.spin_s = QSpinBox()
        self.spin_s.setRange(0, 59)
        self.spin_s.setValue(seconds)
        self.spin_s.setSuffix(" s")

        group_layout.addWidget(self.spin_h)
        group_layout.addWidget(self.spin_m)
        group_layout.addWidget(self.spin_s)
        layout.addWidget(group)

        # Text input / preview
        text_layout = QHBoxLayout()
        text_layout.addWidget(QLabel("Formato PGN:"))
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText("e.g. 1:30:00 o 0:05:00")
        text_layout.addWidget(self.line_edit)
        layout.addLayout(text_layout)

        # Presets layout
        presets_layout = QHBoxLayout()
        presets_layout.setSpacing(4)
        for label, val in [
            ("1:30:00", (1, 30, 0)),
            ("0:15:00", (0, 15, 0)),
            ("0:05:00", (0, 5, 0)),
            ("0:03:00", (0, 3, 0)),
            ("0:01:00", (0, 1, 0)),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked, v=val: self._set_time(*v))
            presets_layout.addWidget(btn)
        layout.addLayout(presets_layout)

        # Sync spinboxes and text line
        self.spin_h.valueChanged.connect(self._sync_from_spins)
        self.spin_m.valueChanged.connect(self._sync_from_spins)
        self.spin_s.valueChanged.connect(self._sync_from_spins)
        self.line_edit.textChanged.connect(self._sync_from_text)

        self._sync_from_spins()

        # Dialog Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_clear = btn_box.addButton("Borrar Tiempo", QDialogButtonBox.ActionRole)
        btn_clear.setIcon(qta.icon("fa5s.trash-alt", color="#f87171"))
        btn_clear.clicked.connect(self._on_clear)

        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _set_time(self, h, m, s):
        self.spin_h.setValue(h)
        self.spin_m.setValue(m)
        self.spin_s.setValue(s)
        self._sync_from_spins()

    def _sync_from_spins(self):
        h = self.spin_h.value()
        m = self.spin_m.value()
        s = self.spin_s.value()
        self.line_edit.blockSignals(True)
        self.line_edit.setText(f"{h}:{m:02d}:{s:02d}")
        self.line_edit.blockSignals(False)

    def _sync_from_text(self, text: str):
        parts = text.strip().split(":")
        try:
            if len(parts) == 3:
                self.spin_h.blockSignals(True)
                self.spin_m.blockSignals(True)
                self.spin_s.blockSignals(True)
                self.spin_h.setValue(int(parts[0]))
                self.spin_m.setValue(int(parts[1]))
                self.spin_s.setValue(int(float(parts[2])))
                self.spin_h.blockSignals(False)
                self.spin_m.blockSignals(False)
                self.spin_s.blockSignals(False)
        except Exception:
            pass

    def _on_clear(self):
        self.result_clk = ""
        self.accept()

    def _on_accept(self):
        self.result_clk = self.line_edit.text().strip()
        self.accept()

    def get_clk(self) -> str:
        return self.result_clk
