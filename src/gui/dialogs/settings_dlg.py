import chess
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QCheckBox, QSpinBox, QPushButton, QGroupBox, QFormLayout
)
from PyQt5.QtCore import QSettings

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.settings = QSettings("TestChessApp", "Config")
        
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Board Settings ---
        board_group = QGroupBox("Board Settings")
        board_form = QFormLayout(board_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Classic", "Lichess", "Chess.com", "Blue", "Wood"])
        board_form.addRow("Theme:", self.theme_combo)
        
        self.premoves_cb = QCheckBox("Enable Premoves")
        board_form.addRow(self.premoves_cb)
        
        self.anim_duration = QSpinBox()
        self.anim_duration.setRange(0, 1000)
        self.anim_duration.setSuffix(" ms")
        self.anim_duration.setSingleStep(50)
        board_form.addRow("Animation Duration:", self.anim_duration)
        
        layout.addWidget(board_group)
        
        # --- Engine Settings ---
        engine_group = QGroupBox("Engine Settings")
        engine_form = QFormLayout(engine_group)
        
        self.engine_depth = QSpinBox()
        self.engine_depth.setRange(1, 40)
        engine_form.addRow("Default Analysis Depth:", self.engine_depth)
        
        layout.addWidget(engine_group)
        
        # --- Buttons ---
        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addStretch()
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def load_settings(self):
        theme = self.settings.value("board_theme", "Classic")
        self.theme_combo.setCurrentText(theme)
        
        premoves = self.settings.value("premoves_enabled", True, type=bool)
        self.premoves_cb.setChecked(premoves)
        
        anim_dur = int(self.settings.value("animation_duration", 200))
        self.anim_duration.setValue(anim_dur)
        
        depth = int(self.settings.value("analysis_depth", 20))
        self.engine_depth.setValue(depth)

    def save_settings(self):
        self.settings.setValue("board_theme", self.theme_combo.currentText())
        self.settings.setValue("premoves_enabled", self.premoves_cb.isChecked())
        self.settings.setValue("animation_duration", self.anim_duration.value())
        self.settings.setValue("analysis_depth", self.engine_depth.value())
        self.accept()

    def get_settings(self):
        return {
            "board_theme": self.theme_combo.currentText(),
            "premoves_enabled": self.premoves_cb.isChecked(),
            "animation_duration": self.anim_duration.value(),
            "analysis_depth": self.engine_depth.value()
        }
