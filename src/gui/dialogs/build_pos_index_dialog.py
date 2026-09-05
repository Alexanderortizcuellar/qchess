import os
import time
from typing import Optional
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QFormLayout, QSpinBox,
    QProgressBar, QHBoxLayout, QPushButton, QMessageBox, QFrame
)
import qtawesome as qta


class BuildPosIndexDialog(QDialog):
    """Dialog for creating / rebuilding .pos.idx companion position index with streaming progress."""

    def __init__(self, scid_client, default_ply: int = 24, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Build Fast Position Index (.pos.idx)")
        self.resize(520, 310)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.client = scid_client
        self.start_time = 0.0

        self._init_ui(default_ply)
        self._apply_dark_theme()

        # Connect streaming progress signal
        if self.client:
            self.client.pos_index_progress.connect(self._on_progress_event)

    def _init_ui(self, default_ply: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header Info Card
        info_frame = QFrame()
        info_frame.setObjectName("infoFrame")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(4)

        title_lbl = QLabel("⚡ <b>High-Performance Position Index (.pos.idx)</b>")
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        info_layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Constructs a binary Zobrist position hash index enabling instant (< 0.1 ms) "
            "board position searches, transpose matching, and instant opening tree statistics."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        info_layout.addWidget(desc_lbl)

        layout.addWidget(info_frame)

        # Form options
        form = QFormLayout()
        form.setSpacing(8)

        self.spin_depth = QSpinBox()
        self.spin_depth.setRange(4, 100)
        self.spin_depth.setValue(default_ply)
        self.spin_depth.setSuffix(" plies (half-moves)")
        self.spin_depth.setToolTip("Maximum depth into games to index positions (24 plies = 12 full moves)")
        form.addRow("Indexing Depth:", self.spin_depth)

        cpu_count = os.cpu_count() or 4
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, cpu_count)
        self.spin_threads.setValue(max(1, cpu_count - 1 if cpu_count > 2 else cpu_count))
        self.spin_threads.setSuffix(f" threads (of {cpu_count} CPU cores)")
        form.addRow("Worker Threads:", self.spin_threads)

        layout.addLayout(form)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Status Label
        self.lbl_progress = QLabel("Status: Ready to build index.")
        self.lbl_progress.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        layout.addWidget(self.lbl_progress)

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_build = QPushButton(qta.icon("fa5s.bolt", color="white"), "  Start Indexing")
        self.btn_build.setObjectName("btnBuild")
        self.btn_build.setCursor(Qt.PointingHandCursor)
        self.btn_build.clicked.connect(self.start_build)
        btn_box.addWidget(self.btn_build)

        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("btnClose")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        btn_box.addWidget(self.btn_close)

        layout.addLayout(btn_box)

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
            }
            #infoFrame {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }
            QSpinBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 140px;
            }
            QSpinBox:focus {
                border-color: #4a90d9;
            }
            QProgressBar {
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                text-align: center;
                height: 22px;
                font-weight: bold;
                background-color: #252526;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #2e7d32;
                border-radius: 3px;
            }
            #btnBuild {
                background-color: #2e7d32;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
                padding: 7px 18px;
            }
            #btnBuild:hover {
                background-color: #388e3c;
            }
            #btnBuild:disabled {
                background-color: #444444;
                color: #888888;
            }
            #btnClose {
                background-color: #333333;
                color: #cccccc;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 7px 16px;
            }
            #btnClose:hover {
                background-color: #3d3d3d;
            }
        """)

    def start_build(self):
        if not self.client or not self.client.is_running():
            QMessageBox.warning(self, "Offline", "scid-mgr backend is not connected.")
            return

        self.btn_build.setEnabled(False)
        self.spin_depth.setEnabled(False)
        self.spin_threads.setEnabled(False)
        self.progress_bar.setValue(0)
        self.start_time = time.time()

        threads = self.spin_threads.value()
        depth = self.spin_depth.value()
        self.lbl_progress.setText(f"Building position index (depth: {depth} plies, {threads} threads)...")

        def on_complete(resp: dict):
            self.btn_build.setEnabled(True)
            self.spin_depth.setEnabled(True)
            self.spin_threads.setEnabled(True)

            if resp.get("status") == "ok":
                data = resp.get("data", {})
                unique_pos = data.get("unique_positions", 0)
                elapsed_ms = data.get("elapsed_ms", (time.time() - self.start_time) * 1000.0)
                self.progress_bar.setValue(100)
                self.lbl_progress.setText(
                    f"✅ Finished in {elapsed_ms:,.0f} ms! Indexed {unique_pos:,} unique positions."
                )
                QMessageBox.information(
                    self,
                    "Position Index Created",
                    f"Position index (.pos.idx) successfully constructed!\n\n"
                    f"• Unique Positions: {unique_pos:,}\n"
                    f"• Indexing Depth: {depth} plies\n"
                    f"• Elapsed Time: {elapsed_ms / 1000.0:.2f} s"
                )
            else:
                err = resp.get("error", "Unknown error building index")
                self.lbl_progress.setText(f"❌ Failed: {err}")
                QMessageBox.critical(self, "Index Build Failed", f"Failed to build position index:\n{err}")

        self.client.build_pos_index(max_ply=depth, threads=threads, callback=on_complete)

    def _on_progress_event(self, prog_data: dict):
        scanned = prog_data.get("scanned", 0)
        total = prog_data.get("total", 0)
        positions = prog_data.get("positions", 0)
        percent = float(prog_data.get("percent", 0.0))

        self.progress_bar.setValue(min(100, int(percent)))
        elapsed = time.time() - self.start_time
        speed_str = f" (~{scanned / elapsed:,.0f} games/s)" if elapsed > 0.3 and scanned > 0 else ""
        self.lbl_progress.setText(
            f"Indexed: {scanned:,} / {total:,} games ({percent:.1f}%){speed_str} | Positions: {positions:,}"
        )

    def closeEvent(self, event):
        if self.client:
            try:
                self.client.pos_index_progress.disconnect(self._on_progress_event)
            except Exception:
                pass
        super().closeEvent(event)
