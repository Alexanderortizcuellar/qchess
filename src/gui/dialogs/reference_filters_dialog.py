from typing import Optional
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QSettings
from core.reference_filters import get_reference_filter_manager


class ReferenceFiltersDialog(QtWidgets.QDialog):
    """
    Global Reference Database Filters Dialog.
    Allows users to configure persistent metadata filters applied consistently across:
      1. Opening Explorer (Tree widget)
      2. Common Continuations
      3. Endgame Statistics
    """
    filtersApplied = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None, is_dark: Optional[bool] = None):
        super().__init__(parent)
        self.setWindowTitle("Database Reference Filters")
        self.setMinimumWidth(440)
        self.mgr = get_reference_filter_manager()
        
        self.is_dark = self._resolve_is_dark(parent, is_dark)

        self._init_ui()
        self._load_current_values()
        self.set_theme(self.is_dark)

    def _resolve_is_dark(self, parent, is_dark_param: Optional[bool]) -> bool:
        if is_dark_param is not None:
            return bool(is_dark_param)
        if parent is not None and hasattr(parent, "is_dark"):
            return bool(parent.is_dark)
        return QSettings("QChessApp", "Theme").value("theme", "dark") == "dark"

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Header Banner
        self.header_frame = QtWidgets.QFrame(self)
        self.header_frame.setObjectName("HeaderFrame")
        h_layout = QtWidgets.QVBoxLayout(self.header_frame)
        h_layout.setContentsMargins(12, 10, 12, 10)
        h_layout.setSpacing(4)

        self.title_lbl = QtWidgets.QLabel("🔍 Global Reference Filters", self)
        self.title_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.desc_lbl = QtWidgets.QLabel(
            "These filters are applied consistently across Opening Explorer, Continuations, and Endgame Statistics.",
            self
        )
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("font-size: 11px;")

        h_layout.addWidget(self.title_lbl)
        h_layout.addWidget(self.desc_lbl)
        main_layout.addWidget(self.header_frame)

        # 2. Main Filter Form
        self.form_group = QtWidgets.QGroupBox("Filter Criteria", self)
        form_layout = QtWidgets.QFormLayout(self.form_group)
        form_layout.setContentsMargins(12, 12, 12, 12)
        form_layout.setSpacing(10)

        # --- Player Row ---
        self.player_edit = QtWidgets.QLineEdit(self)
        self.player_edit.setPlaceholderText("e.g. Carlsen, Magnus")
        self.color_combo = QtWidgets.QComboBox(self)
        self.color_combo.addItems(["Either Color", "As White", "As Black"])

        player_row = QtWidgets.QHBoxLayout()
        player_row.addWidget(self.player_edit, stretch=2)
        player_row.addWidget(self.color_combo, stretch=1)
        player_row.setContentsMargins(0, 0, 0, 0)
        form_layout.addRow("Player:", player_row)

        # --- Elo / Rating Row ---
        self.min_rating_spin = QtWidgets.QSpinBox(self)
        self.min_rating_spin.setRange(0, 3500)
        self.min_rating_spin.setSingleStep(25)
        self.min_rating_spin.setSpecialValueText("Any")

        self.max_rating_spin = QtWidgets.QSpinBox(self)
        self.max_rating_spin.setRange(0, 3500)
        self.max_rating_spin.setSingleStep(25)
        self.max_rating_spin.setSpecialValueText("Any")

        rating_row = QtWidgets.QHBoxLayout()
        rating_row.addWidget(QtWidgets.QLabel("Min:"))
        rating_row.addWidget(self.min_rating_spin)
        rating_row.addSpacing(10)
        rating_row.addWidget(QtWidgets.QLabel("Max:"))
        rating_row.addWidget(self.max_rating_spin)
        rating_row.setContentsMargins(0, 0, 0, 0)
        form_layout.addRow("Elo Rating:", rating_row)

        # --- ECO & Result Row ---
        self.eco_edit = QtWidgets.QLineEdit(self)
        self.eco_edit.setPlaceholderText("e.g. B01, E")
        self.eco_edit.setMaxLength(3)

        self.result_combo = QtWidgets.QComboBox(self)
        self.result_combo.addItems(["Any", "1-0", "0-1", "1/2-1/2"])

        eco_result_row = QtWidgets.QHBoxLayout()
        eco_result_row.addWidget(self.eco_edit, stretch=1)
        eco_result_row.addSpacing(10)
        eco_result_row.addWidget(QtWidgets.QLabel("Result:"))
        eco_result_row.addWidget(self.result_combo, stretch=1)
        eco_result_row.setContentsMargins(0, 0, 0, 0)
        form_layout.addRow("ECO / Result:", eco_result_row)

        # --- Event & Site Row ---
        self.event_edit = QtWidgets.QLineEdit(self)
        self.event_edit.setPlaceholderText("e.g. World Championship")
        form_layout.addRow("Event:", self.event_edit)

        self.site_edit = QtWidgets.QLineEdit(self)
        self.site_edit.setPlaceholderText("e.g. London")
        form_layout.addRow("Site:", self.site_edit)

        # --- Year Range Row ---
        self.min_year_spin = QtWidgets.QSpinBox(self)
        self.min_year_spin.setRange(0, 2100)
        self.min_year_spin.setSpecialValueText("Any")

        self.max_year_spin = QtWidgets.QSpinBox(self)
        self.max_year_spin.setRange(0, 2100)
        self.max_year_spin.setSpecialValueText("Any")

        year_row = QtWidgets.QHBoxLayout()
        year_row.addWidget(QtWidgets.QLabel("From:"))
        year_row.addWidget(self.min_year_spin)
        year_row.addSpacing(10)
        year_row.addWidget(QtWidgets.QLabel("To:"))
        year_row.addWidget(self.max_year_spin)
        year_row.setContentsMargins(0, 0, 0, 0)
        form_layout.addRow("Year Range:", year_row)

        main_layout.addWidget(self.form_group)

        # 3. Active Status Preview Bar
        self.status_preview_lbl = QtWidgets.QLabel(self)
        self.status_preview_lbl.setWordWrap(True)
        main_layout.addWidget(self.status_preview_lbl)

        # 4. Buttons Row
        btn_layout = QtWidgets.QHBoxLayout()
        self.clear_btn = QtWidgets.QPushButton("Reset / Clear All", self)
        self.clear_btn.clicked.connect(self._on_clear_clicked)

        self.apply_btn = QtWidgets.QPushButton("Apply Filters", self)
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self._on_apply_clicked)

        self.cancel_btn = QtWidgets.QPushButton("Cancel", self)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.apply_btn)
        main_layout.addLayout(btn_layout)

        # Connect live updates to status preview
        self.player_edit.textChanged.connect(self._update_preview)
        self.color_combo.currentIndexChanged.connect(self._update_preview)
        self.min_rating_spin.valueChanged.connect(self._update_preview)
        self.max_rating_spin.valueChanged.connect(self._update_preview)
        self.eco_edit.textChanged.connect(self._update_preview)
        self.result_combo.currentIndexChanged.connect(self._update_preview)
        self.event_edit.textChanged.connect(self._update_preview)
        self.site_edit.textChanged.connect(self._update_preview)
        self.min_year_spin.valueChanged.connect(self._update_preview)
        self.max_year_spin.valueChanged.connect(self._update_preview)

    def _load_current_values(self):
        raw = self.mgr.get_raw_settings()
        self.player_edit.setText(raw.get("player", ""))
        
        color = raw.get("color", "Either Color")
        color_idx = 0
        if color in ("As White", "White"):
            color_idx = 1
        elif color in ("As Black", "Black"):
            color_idx = 2
        self.color_combo.setCurrentIndex(color_idx)

        self.min_rating_spin.setValue(int(raw.get("min_rating", 0)))
        self.max_rating_spin.setValue(int(raw.get("max_rating", 0)))
        self.eco_edit.setText(raw.get("eco", ""))
        
        res = raw.get("result", "Any")
        res_idx = self.result_combo.findText(res)
        self.result_combo.setCurrentIndex(max(0, res_idx))

        self.event_edit.setText(raw.get("event", ""))
        self.site_edit.setText(raw.get("site", ""))
        self.min_year_spin.setValue(int(raw.get("min_year", 0)))
        self.max_year_spin.setValue(int(raw.get("max_year", 0)))

        self._update_preview()

    def _update_preview(self):
        parts = []
        player = self.player_edit.text().strip()
        color = self.color_combo.currentText()
        if player:
            if color == "As White":
                parts.append(f"White: {player}")
            elif color == "As Black":
                parts.append(f"Black: {player}")
            else:
                parts.append(f"Player: {player}")

        min_r = self.min_rating_spin.value()
        max_r = self.max_rating_spin.value()
        if min_r > 0 and max_r > 0:
            parts.append(f"Elo: {min_r}-{max_r}")
        elif min_r > 0:
            parts.append(f"Elo ≥ {min_r}")
        elif max_r > 0:
            parts.append(f"Elo ≤ {max_r}")

        eco = self.eco_edit.text().strip()
        if eco:
            parts.append(f"ECO: {eco.upper()}")

        res = self.result_combo.currentText()
        if res != "Any":
            parts.append(f"Result: {res}")

        event = self.event_edit.text().strip()
        if event:
            parts.append(f"Event: {event}")

        if not parts:
            self.status_preview_lbl.setText("Status: No filters active (Full Database)")
        else:
            self.status_preview_lbl.setText(f"Active Filter: {' | '.join(parts)}")

    def _on_clear_clicked(self):
        self.player_edit.clear()
        self.color_combo.setCurrentIndex(0)
        self.min_rating_spin.setValue(0)
        self.max_rating_spin.setValue(0)
        self.eco_edit.clear()
        self.result_combo.setCurrentIndex(0)
        self.event_edit.clear()
        self.site_edit.clear()
        self.min_year_spin.setValue(0)
        self.max_year_spin.setValue(0)
        self._update_preview()

    def _on_apply_clicked(self):
        color_val = self.color_combo.currentText()
        self.mgr.set_filters(
            player=self.player_edit.text(),
            color=color_val,
            min_rating=self.min_rating_spin.value(),
            max_rating=self.max_rating_spin.value(),
            eco=self.eco_edit.text(),
            result=self.result_combo.currentText(),
            event=self.event_edit.text(),
            site=self.site_edit.text(),
            min_year=self.min_year_spin.value(),
            max_year=self.max_year_spin.value(),
        )
        self.filtersApplied.emit(self.mgr.get_filter_dict())
        self.accept()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        if is_dark:
            self.desc_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
            self.status_preview_lbl.setStyleSheet("font-size: 11px; font-style: italic; color: #94a3b8;")
            self.setStyleSheet("""
                QDialog {
                    background-color: #201e1b;
                    color: #f8fafc;
                }
                QFrame#HeaderFrame {
                    background-color: #262421;
                    border: 1px solid #383531;
                    border-radius: 6px;
                }
                QGroupBox {
                    background-color: #262421;
                    border: 1px solid #383531;
                    border-radius: 6px;
                    margin-top: 12px;
                    font-weight: bold;
                    color: #f8fafc;
                    padding-top: 12px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 6px;
                    left: 10px;
                    color: #94a3b8;
                }
                QLabel {
                    color: #f8fafc;
                }
                QLineEdit, QComboBox, QSpinBox {
                    background-color: #2c2a26;
                    color: #f8fafc;
                    border: 1px solid #44413c;
                    border-radius: 4px;
                    padding: 5px 8px;
                    font-size: 11px;
                }
                QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                    border: 1px solid #3b82f6;
                }
                QPushButton {
                    background-color: #3c3934;
                    color: #f8fafc;
                    border: 1px solid #44413c;
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-weight: 600;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #4a4741;
                }
                QPushButton:default {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                }
                QPushButton:default:hover {
                    background-color: #1d4ed8;
                }
            """)
        else:
            self.desc_lbl.setStyleSheet("font-size: 11px; color: #475569;")
            self.status_preview_lbl.setStyleSheet("font-size: 11px; font-style: italic; color: #64748b;")
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                    color: #0f172a;
                }
                QFrame#HeaderFrame {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                }
                QGroupBox {
                    background-color: #ffffff;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    margin-top: 12px;
                    font-weight: bold;
                    color: #0f172a;
                    padding-top: 12px;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 6px;
                    left: 10px;
                    color: #475569;
                }
                QLabel {
                    color: #0f172a;
                }
                QLineEdit, QComboBox, QSpinBox {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 5px 8px;
                    font-size: 11px;
                }
                QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                    border: 1px solid #2563eb;
                }
                QPushButton {
                    background-color: #f1f5f9;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 6px 14px;
                    font-weight: 600;
                    font-size: 11px;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                }
                QPushButton:default {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                }
                QPushButton:default:hover {
                    background-color: #1d4ed8;
                }
            """)
