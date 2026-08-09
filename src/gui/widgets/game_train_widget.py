from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QSpinBox, QGroupBox, QFormLayout
)
from utils.helpers import _qicon

class GameTrainWidget(QWidget):
    gameStartRequested = pyqtSignal(str, int, int) # mode, depth, delay_ms
    gameStopRequested = pyqtSignal()
    loadPresetRequested = pyqtSignal(str)

    PRESETS = {
        "Current Position": None,
        "King & Queen vs King": "k7/8/8/8/8/8/8/Q3K3 w - - 0 1",
        "King & Rook vs King": "k7/8/8/8/8/8/8/R3K3 w - - 0 1",
        "King & Two Bishops vs King": "k7/8/8/8/8/8/8/2BBK3 w - - 0 1",
        "King & Pawn vs King (winning)": "8/8/8/8/4k3/8/4P3/4K3 w - - 0 1",
        "King & Pawn vs King (drawn)": "8/8/8/8/4k3/4K3/4P3/8 w - - 0 1",
        "Mate in 1": "k7/8/1Q6/8/8/8/8/1R2K3 w - - 0 1",
        "Mate in 2": "k7/8/1K6/8/8/8/1R6/8 w - - 0 1"
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = True
        self.playing = False
        
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(10)
        self.setLayout(self.main_layout)

        # --- Play Options Group ---
        self.play_group = QGroupBox("Game Settings")
        self.play_form = QFormLayout(self.play_group)
        
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Play as White", "Play as Black", "Engine vs Engine"])
        self.play_form.addRow("Mode:", self.color_combo)

        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 20)
        self.depth_spin.setValue(8)
        self.play_form.addRow("Engine Depth:", self.depth_spin)

        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(100, 5000)
        self.delay_spin.setValue(1000)
        self.delay_spin.setSuffix(" ms")
        self.delay_spin.setSingleStep(100)
        self.play_form.addRow("Self-Play Delay:", self.delay_spin)
        
        self.main_layout.addWidget(self.play_group)

        # --- Presets Group ---
        self.presets_group = QGroupBox("Training Presets")
        self.presets_form = QFormLayout(self.presets_group)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(list(self.PRESETS.keys()))
        self.presets_form.addRow("Position:", self.preset_combo)

        self.btn_load = QPushButton("Load Position")
        self.btn_load.setIcon(_qicon("fa5s.folder-open", is_dark=self.is_dark))
        self.btn_load.setCursor(Qt.PointingHandCursor)
        self.btn_load.clicked.connect(self.on_load_clicked)
        self.presets_form.addRow(self.btn_load)

        self.main_layout.addWidget(self.presets_group)

        # --- Control & Status ---
        self.ctrl_layout = QHBoxLayout()
        self.btn_play = QPushButton("Start Play")
        self.btn_play.setIcon(_qicon("fa5s.play", is_dark=self.is_dark))
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self.toggle_play)
        
        self.status_label = QLabel("Stopped")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 4px; border-radius: 3px;")
        
        self.ctrl_layout.addWidget(self.btn_play)
        self.main_layout.addLayout(self.ctrl_layout)
        self.main_layout.addWidget(self.status_label)
        self.main_layout.addStretch()

        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        
        # Update Icons
        self.btn_load.setIcon(_qicon("fa5s.folder-open", is_dark=is_dark))
        if self.playing:
            self.btn_play.setIcon(_qicon("fa5s.stop", is_dark=is_dark))
        else:
            self.btn_play.setIcon(_qicon("fa5s.play", is_dark=is_dark))

        # Update styling
        if is_dark:
            self.presets_group.setStyleSheet("QGroupBox { color: #ffffff; font-weight: bold; }")
            self.play_group.setStyleSheet("QGroupBox { color: #ffffff; font-weight: bold; }")
            self.status_label.setStyleSheet("color: #bababa; font-weight: bold; background-color: #312e2b; padding: 6px; border-radius: 3px;")
        else:
            self.presets_group.setStyleSheet("QGroupBox { color: #000000; font-weight: bold; }")
            self.play_group.setStyleSheet("QGroupBox { color: #000000; font-weight: bold; }")
            self.status_label.setStyleSheet("color: #312e2b; font-weight: bold; background-color: #e1e1e1; padding: 6px; border: 1px solid #ccc; border-radius: 3px;")

    def toggle_play(self):
        if self.playing:
            self.stop_play()
        else:
            self.start_play()

    def start_play(self):
        self.playing = True
        self.btn_play.setText("Stop Play")
        self.btn_play.setIcon(_qicon("fa5s.stop", is_dark=self.is_dark))
        self.color_combo.setEnabled(False)
        self.preset_combo.setEnabled(False)
        self.btn_load.setEnabled(False)
        
        mode = self.color_combo.currentText()
        depth = self.depth_spin.value()
        delay = self.delay_spin.value()
        
        self.status_label.setText("Playing...")
        self.gameStartRequested.emit(mode, depth, delay)

    def stop_play(self):
        self.playing = False
        self.btn_play.setText("Start Play")
        self.btn_play.setIcon(_qicon("fa5s.play", is_dark=self.is_dark))
        self.color_combo.setEnabled(True)
        self.preset_combo.setEnabled(True)
        self.btn_load.setEnabled(True)
        
        self.status_label.setText("Stopped")
        self.gameStopRequested.emit()

    def on_load_clicked(self):
        preset_name = self.preset_combo.currentText()
        fen = self.PRESETS.get(preset_name)
        if fen:
            self.loadPresetRequested.emit(fen)

    def update_status(self, text: str):
        self.status_label.setText(text)
