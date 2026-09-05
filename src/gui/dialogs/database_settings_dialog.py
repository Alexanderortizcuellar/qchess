import os
from typing import Optional
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QSlider, QSpinBox, QPushButton, QGroupBox, QMessageBox, QFrame
)
import qtawesome as qta


class DatabaseSettingsDialog(QDialog):
    """
    Settings / Preferences Dialog allowing users to configure CPU thread limits,
    indexing parameters, and backend performance profiles for search & position indexing.
    """

    def __init__(self, scid_client=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Search & Performance Settings")
        self.resize(500, 300)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.client = scid_client
        self.settings = QSettings("QChessApp", "SearchConfig")
        self.max_system_cpus = os.cpu_count() or 4

        self._init_ui()
        self._apply_dark_theme()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Performance & CPU Threading Group
        cpu_group = QGroupBox("⚡ Parallel Processing & CPU Resource Limit")
        cpu_layout = QGridLayout(cpu_group)
        cpu_layout.setContentsMargins(14, 14, 14, 14)
        cpu_layout.setSpacing(10)

        cpu_layout.addWidget(QLabel("<b>Worker Threads for Searches & Indexing:</b>"), 0, 0, 1, 2)

        slider_row = QHBoxLayout()
        self.slider_threads = QSlider(Qt.Horizontal)
        self.slider_threads.setRange(1, self.max_system_cpus)
        self.slider_threads.setTickPosition(QSlider.TicksBelow)
        self.slider_threads.setTickInterval(1)
        slider_row.addWidget(self.slider_threads)

        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, self.max_system_cpus)
        slider_row.addWidget(self.spin_threads)
        cpu_layout.addLayout(slider_row, 1, 0, 1, 2)

        self.slider_threads.valueChanged.connect(self.spin_threads.setValue)
        self.spin_threads.valueChanged.connect(self.slider_threads.setValue)
        self.spin_threads.valueChanged.connect(self._update_cpu_hint)

        self.lbl_cpu_info = QLabel()
        self.lbl_cpu_info.setWordWrap(True)
        self.lbl_cpu_info.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        cpu_layout.addWidget(self.lbl_cpu_info, 2, 0, 1, 2)

        layout.addWidget(cpu_group)

        # Additional Search Options Group
        opts_group = QGroupBox("🔍 Search & Indexing Defaults")
        opts_layout = QGridLayout(opts_group)
        opts_layout.setContentsMargins(14, 14, 14, 14)
        opts_layout.setSpacing(10)

        opts_layout.addWidget(QLabel("Default Position Index Depth:"), 0, 0)
        self.spin_default_depth = QSpinBox()
        self.spin_default_depth.setRange(4, 100)
        self.spin_default_depth.setValue(24)
        self.spin_default_depth.setSuffix(" plies")
        opts_layout.addWidget(self.spin_default_depth, 0, 1)

        layout.addWidget(opts_group)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(qta.icon("fa5s.save", color="white"), "  Save & Apply")
        self.btn_save.setObjectName("btnSave")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(self.btn_save)

        layout.addLayout(btn_box)

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: #4a90d9;
            }
            QLabel {
                color: #e0e0e0;
            }
            QSpinBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 90px;
            }
            QSpinBox:focus {
                border-color: #4a90d9;
            }
            QSlider::groove:horizontal {
                border: 1px solid #3c3c3c;
                height: 6px;
                background: #2d2d2d;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #4a90d9;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #e0e0e0;
                border: 1px solid #777;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            #btnSave {
                background-color: #1976d2;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 7px 18px;
            }
            #btnSave:hover {
                background-color: #1e88e5;
            }
            #btnCancel {
                background-color: #333333;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 7px 16px;
            }
            #btnCancel:hover {
                background-color: #3d3d3d;
            }
        """)

    def _update_cpu_hint(self, threads: int):
        pct = (threads / self.max_system_cpus) * 100.0
        if threads == self.max_system_cpus:
            rec = "🔥 <b>Maximum Speed</b> — Utilizes 100% of CPU cores during searches & indexing."
        elif threads >= max(1, self.max_system_cpus // 2):
            rec = "⚡ <b>Balanced (Recommended)</b> — Fast searches while leaving headroom for smooth GUI responsiveness."
        else:
            rec = "🍃 <b>Low CPU Usage</b> — Minimizes system temperature and resource usage."

        self.lbl_cpu_info.setText(
            f"Configured: <b>{threads} / {self.max_system_cpus} threads</b> (~{pct:.0f}% CPU capacity)<br>{rec}"
        )

    def _load_settings(self):
        recommended = max(1, self.max_system_cpus - 1) if self.max_system_cpus > 2 else self.max_system_cpus
        saved_threads = int(self.settings.value("worker_threads", recommended))
        saved_threads = max(1, min(self.max_system_cpus, saved_threads))
        self.spin_threads.setValue(saved_threads)
        self.slider_threads.setValue(saved_threads)
        self._update_cpu_hint(saved_threads)

        saved_depth = int(self.settings.value("default_pos_index_depth", 24))
        self.spin_default_depth.setValue(saved_depth)

    def _save_settings(self):
        threads = self.spin_threads.value()
        depth = self.spin_default_depth.value()

        self.settings.setValue("worker_threads", threads)
        self.settings.setValue("default_pos_index_depth", depth)

        if self.client and self.client.is_running():
            self.client.set_threads(threads)

        self.accept()
