from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, 
    QCheckBox, QSpinBox, QPushButton, QGroupBox, QFormLayout,
    QLineEdit, QFileDialog
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

        self.figurine_font_cb = QCheckBox("Use Chess Figurine Font")
        board_form.addRow(self.figurine_font_cb)
        
        layout.addWidget(board_group)
        
        # --- Opening Explorer Settings ---
        explorer_group = QGroupBox("Opening Explorer")
        explorer_form = QFormLayout(explorer_group)
        
        self.pgn_path_edit = QLineEdit()
        self.pgn_path_edit.setPlaceholderText("Select PGN file...")
        
        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.pgn_path_edit)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_pgn_file)
        browse_layout.addWidget(self.browse_btn)
        
        explorer_form.addRow("Explorer PGN:", browse_layout)
        layout.addWidget(explorer_group)
        
        # --- PGN Browser Settings ---
        browser_group = QGroupBox("PGN Browser Settings")
        browser_form = QFormLayout(browser_group)
        self.show_eval_cb = QCheckBox("Show Engine Evaluations inline")
        browser_form.addRow(self.show_eval_cb)
        self.show_classifications_cb = QCheckBox("Show Move Classification colors")
        browser_form.addRow(self.show_classifications_cb)
        self.show_variations_cb = QCheckBox("Show Variations")
        browser_form.addRow(self.show_variations_cb)
        self.layout_mode_combo = QComboBox()
        self.layout_mode_combo.addItems(["Columns (One Move per Line)", "ChessBase Blocks"])
        browser_form.addRow("Layout Mode:", self.layout_mode_combo)
        layout.addWidget(browser_group)

        # --- Mode Settings ---
        mode_group = QGroupBox("Application Mode")
        mode_form = QFormLayout(mode_group)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Analysis Mode", "Game / Train Mode"])
        mode_form.addRow("Mode:", self.mode_combo)
        layout.addWidget(mode_group)
        
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

    def browse_pgn_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Explorer PGN File", "", "PGN Files (*.pgn);;All Files (*)"
        )
        if file_path:
            self.pgn_path_edit.setText(file_path)

    def load_settings(self):
        theme = self.settings.value("board_theme", "Classic")
        self.theme_combo.setCurrentText(theme)
        
        premoves = self.settings.value("premoves_enabled", True, type=bool)
        self.premoves_cb.setChecked(premoves)
        
        anim_dur = int(self.settings.value("animation_duration", 200))
        self.anim_duration.setValue(anim_dur)
        
        use_figurine = self.settings.value("use_figurine_font", True, type=bool)
        self.figurine_font_cb.setChecked(use_figurine)

        show_eval = self.settings.value("show_eval_annotations", True, type=bool)
        self.show_eval_cb.setChecked(show_eval)

        show_cls = self.settings.value("show_move_classifications", True, type=bool)
        self.show_classifications_cb.setChecked(show_cls)

        show_vars = self.settings.value("show_variations", True, type=bool)
        self.show_variations_cb.setChecked(show_vars)

        layout_val = int(self.settings.value("layout_mode", 1))
        self.layout_mode_combo.setCurrentIndex(layout_val)

        pgn_path = self.settings.value(
            "explorer_pgn_path",
            r"C:\Users\ASUS\programming\qt_programs\chess\downloader\alex.pgn"
        )
        self.pgn_path_edit.setText(pgn_path)

        mode = self.settings.value("app_mode", "Analysis Mode")
        self.mode_combo.setCurrentText(mode)

    def save_settings(self):
        self.settings.setValue("board_theme", self.theme_combo.currentText())
        self.settings.setValue("premoves_enabled", self.premoves_cb.isChecked())
        self.settings.setValue("animation_duration", self.anim_duration.value())
        self.settings.setValue("use_figurine_font", self.figurine_font_cb.isChecked())
        self.settings.setValue("show_eval_annotations", self.show_eval_cb.isChecked())
        self.settings.setValue("show_move_classifications", self.show_classifications_cb.isChecked())
        self.settings.setValue("show_variations", self.show_variations_cb.isChecked())
        self.settings.setValue("layout_mode", self.layout_mode_combo.currentIndex())
        self.settings.setValue("explorer_pgn_path", self.pgn_path_edit.text())
        self.settings.setValue("app_mode", self.mode_combo.currentText())
        self.accept()

    def get_settings(self):
        return {
            "board_theme": self.theme_combo.currentText(),
            "premoves_enabled": self.premoves_cb.isChecked(),
            "animation_duration": self.anim_duration.value(),
            "use_figurine_font": self.figurine_font_cb.isChecked(),
            "show_eval_annotations": self.show_eval_cb.isChecked(),
            "show_move_classifications": self.show_classifications_cb.isChecked(),
            "show_variations": self.show_variations_cb.isChecked(),
            "layout_mode": self.layout_mode_combo.currentIndex(),
            "explorer_pgn_path": self.pgn_path_edit.text(),
            "app_mode": self.mode_combo.currentText()
        }
