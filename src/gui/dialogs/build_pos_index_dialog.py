import os
import time
from typing import Optional, Dict, Any
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QFormLayout, QSpinBox,
    QProgressBar, QHBoxLayout, QPushButton, QMessageBox, QFrame,
    QCheckBox, QGroupBox
)
import qtawesome as qta


class BuildPosIndexDialog(QDialog):
    """Unified Dialog for creating / rebuilding .tree.idx (Opening Tree Stats) and .pos.idx (Search Booster)."""

    def __init__(self, scid_client, default_ply: int = 24, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Build Fast Database Indexes (.pos.idx & .tree.idx)")
        self.resize(540, 390)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.client = scid_client
        self.queue = []
        self.current_task = None
        self.task_start_time = 0.0
        self.results: Dict[str, Any] = {}

        self._init_ui(default_ply)
        self._apply_theme()

        # Connect streaming progress signals
        if self.client:
            self.client.pos_index_progress.connect(self._on_pos_progress)
            self.client.tree_index_progress.connect(self._on_tree_progress)
            self.client.continuations_progress.connect(self._on_hot_progress)
            self.client.endgame_index_progress.connect(self._on_feat_progress)

    def _init_ui(self, default_ply: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header Info Card
        info_frame = QFrame()
        info_frame.setObjectName("infoFrame")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(4)

        title_lbl = QLabel("⚡ <b>Companion Fast Indexes</b>")
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        info_layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Companion fast binary indexes enable sub-millisecond opening explorer statistics, "
            "endgame taxonomy distributions, and instant candidate game search acceleration."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        info_layout.addWidget(desc_lbl)

        layout.addWidget(info_frame)

        # Index Targets Selection
        grp_targets = QGroupBox("Select Indexes to Build")
        grp_targets.setObjectName("grpTargets")
        box_targets = QVBoxLayout(grp_targets)
        box_targets.setSpacing(6)

        self.chk_tree = QCheckBox(
            "🌲 Opening Tree Stats Index (.tree.idx) — Instant opening repertoire & move statistics"
        )
        self.chk_tree.setChecked(True)
        self.chk_tree.setStyleSheet("font-weight: bold;")
        box_targets.addWidget(self.chk_tree)

        self.chk_pos = QCheckBox(
            "⚡ Position Search Booster (.pos.idx) — Sub-millisecond position candidate searches"
        )
        self.chk_pos.setChecked(True)
        self.chk_pos.setStyleSheet("font-weight: bold;")
        box_targets.addWidget(self.chk_pos)

        self.chk_hot = QCheckBox(
            "📈 Common Continuations Graph (.hot.idx) — Sub-millisecond multi-move sequence analysis"
        )
        self.chk_hot.setChecked(True)
        self.chk_hot.setStyleSheet("font-weight: bold;")
        box_targets.addWidget(self.chk_hot)

        self.chk_feat = QCheckBox(
            "♟ Endgame Feature Index (.feat.idx) — 47-type standardized endgame taxonomy"
        )
        self.chk_feat.setChecked(True)
        self.chk_feat.setStyleSheet("font-weight: bold;")
        box_targets.addWidget(self.chk_feat)

        layout.addWidget(grp_targets)

        # Form options
        form = QFormLayout()
        form.setSpacing(8)

        self.spin_depth = QSpinBox()
        self.spin_depth.setRange(4, 100)
        self.spin_depth.setValue(default_ply)
        self.spin_depth.setSuffix(" plies (half-moves)")
        self.spin_depth.setToolTip("Maximum depth into games to index positions (24 plies = 12 full moves)")
        form.addRow("Indexing Depth:", self.spin_depth)

        self.spin_min_games = QSpinBox()
        self.spin_min_games.setRange(1, 100000)
        self.spin_min_games.setValue(1)
        self.spin_min_games.setSpecialValueText("1 (Include all positions)")
        self.spin_min_games.setSuffix(" occurrences min")
        self.spin_min_games.setToolTip("Filter out positions occurring fewer than this threshold (1 indexes all positions)")
        form.addRow("Min Position Frequency:", self.spin_min_games)

        cpu_count = os.cpu_count() or 4
        self.spin_threads = QSpinBox()
        self.spin_threads.setRange(1, cpu_count)
        self.spin_threads.setValue(max(1, cpu_count))
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
        self.lbl_progress = QLabel("Status: Ready to build indexes.")
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

    def _is_dark(self) -> bool:
        if self.parent() is not None and hasattr(self.parent(), "is_dark"):
            return bool(self.parent().is_dark)
        return QSettings("QChessApp", "Theme").value("theme", "dark") == "dark"

    def _apply_theme(self):
        if self._is_dark():
            self.lbl_progress.setStyleSheet("color: #a0a0a0; font-size: 11px;")
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
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #3c3c3c;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 10px;
                    color: #e0e0e0;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                }
                QCheckBox {
                    color: #e0e0e0;
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
        else:
            self.lbl_progress.setStyleSheet("color: #475569; font-size: 11px;")
            self.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #0f172a;
                }
                QLabel {
                    color: #0f172a;
                }
                #infoFrame {
                    background-color: #eff6ff;
                    border: 1px solid #bfdbfe;
                    border-radius: 6px;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 10px;
                    color: #0f172a;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                }
                QCheckBox {
                    color: #0f172a;
                }
                QSpinBox {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 4px 8px;
                    min-width: 140px;
                }
                QSpinBox:focus {
                    border-color: #2563eb;
                }
                QProgressBar {
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    text-align: center;
                    height: 22px;
                    font-weight: bold;
                    background-color: #f1f5f9;
                    color: #0f172a;
                }
                QProgressBar::chunk {
                    background-color: #16a34a;
                    border-radius: 3px;
                }
                #btnBuild {
                    background-color: #16a34a;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 4px;
                    padding: 7px 18px;
                }
                #btnBuild:hover {
                    background-color: #15803d;
                }
                #btnBuild:disabled {
                    background-color: #e2e8f0;
                    color: #94a3b8;
                }
                #btnClose {
                    background-color: #f1f5f9;
                    color: #334155;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 7px 16px;
                }
                #btnClose:hover {
                    background-color: #e2e8f0;
                }
            """)

    def start_build(self):
        if not self.client or not self.client.is_running():
            QMessageBox.warning(self, "Offline", "scid-mgr backend is not connected.")
            return

        self.queue = []
        if self.chk_tree.isChecked():
            self.queue.append("build_tree")
        if self.chk_pos.isChecked():
            self.queue.append("build_pos_index")
        if self.chk_hot.isChecked():
            self.queue.append("build_continuations")
        if hasattr(self, "chk_feat") and self.chk_feat.isChecked():
            self.queue.append("build_endgames")

        if not self.queue:
            QMessageBox.warning(self, "No Index Selected", "Please select at least one index to build.")
            return

        self.btn_build.setEnabled(False)
        self.chk_tree.setEnabled(False)
        self.chk_pos.setEnabled(False)
        self.chk_hot.setEnabled(False)
        if hasattr(self, "chk_feat"):
            self.chk_feat.setEnabled(False)
        self.spin_depth.setEnabled(False)
        self.spin_min_games.setEnabled(False)
        self.spin_threads.setEnabled(False)
        self.results = {}
        self.progress_bar.setValue(0)
        self._run_next_task()

    def _run_next_task(self):
        if not self.queue:
            self._all_tasks_completed()
            return

        self.current_task = self.queue.pop(0)
        threads = self.spin_threads.value()
        depth = self.spin_depth.value()
        min_g = self.spin_min_games.value()
        self.task_start_time = time.time()

        if self.current_task == "build_tree":
            task_label = "Opening Tree (.tree.idx)"
        elif self.current_task == "build_pos_index":
            task_label = "Position Booster (.pos.idx)"
        elif self.current_task == "build_endgames":
            task_label = "Endgame Feature Index (.feat.idx)"
        else:
            task_label = "Continuations Graph (.hot.idx)"

        self.progress_bar.setValue(0)
        self.lbl_progress.setText(
            f"Starting {task_label} build (depth: {depth} plies, {threads} threads)..."
        )

        def on_complete(resp: dict):
            if resp.get("status") == "ok":
                data = resp.get("data", {})
                self.results[self.current_task] = data
                self._run_next_task()
            else:
                err = resp.get("error", "Unknown error building index")
                self.lbl_progress.setText(f"❌ Failed ({task_label}): {err}")
                self._restore_controls()
                QMessageBox.critical(self, "Index Build Failed", f"Failed to build {task_label}:\n{err}")

        if self.current_task == "build_tree":
            self.client.build_tree(max_ply=depth, min_games=min_g, threads=threads, callback=on_complete)
        elif self.current_task == "build_pos_index":
            self.client.build_pos_index(max_ply=depth, min_games=min_g, threads=threads, callback=on_complete)
        elif self.current_task == "build_endgames":
            self.client.build_endgames(callback=on_complete)
        else:
            self.client.build_continuations(max_ply=depth, min_games=min_g, threads=threads, callback=on_complete)

    def _all_tasks_completed(self):
        self.progress_bar.setValue(100)
        summary_lines = []
        msg_lines = []
        for task, res in self.results.items():
            if task == "build_tree":
                name = "Opening Tree (.tree.idx)"
                items_cnt = res.get("unique_positions", 0)
                item_label = "positions"
            elif task == "build_pos_index":
                name = "Position Booster (.pos.idx)"
                items_cnt = res.get("unique_positions", 0)
                item_label = "positions"
            elif task == "build_endgames":
                name = "Endgame Feature Index (.feat.idx)"
                items_cnt = res.get("total_games", 0)
                item_label = "games"
            else:
                name = "Continuations Graph (.hot.idx)"
                items_cnt = res.get("nodes", res.get("unique_positions", 0))
                edges_cnt = res.get("edges", 0)
                item_label = f"nodes ({edges_cnt:,} edges)" if edges_cnt > 0 else "nodes"

            elapsed_ms = res.get("elapsed_ms", 0.0)
            summary_lines.append(f"✅ {name}: {items_cnt:,} {item_label} in {elapsed_ms:,.0f} ms")
            msg_lines.append(f"• {name}:\n   - Entries: {items_cnt:,} {item_label}\n   - Elapsed Time: {elapsed_ms / 1000.0:.2f} s")

        self.lbl_progress.setText(" | ".join(summary_lines))
        self._restore_controls()

        QMessageBox.information(
            self,
            "Indexes Created Successfully",
            "Fast database companion indexes have been built successfully:\n\n" + "\n\n".join(msg_lines)
        )

    def _restore_controls(self):
        self.btn_build.setEnabled(True)
        self.chk_tree.setEnabled(True)
        self.chk_pos.setEnabled(True)
        self.chk_hot.setEnabled(True)
        if hasattr(self, "chk_feat"):
            self.chk_feat.setEnabled(True)
        self.spin_depth.setEnabled(True)
        self.spin_min_games.setEnabled(True)
        self.spin_threads.setEnabled(True)

    def _on_pos_progress(self, prog_data: dict):
        if self.current_task == "build_pos_index":
            self._handle_progress_data(prog_data, "Position Booster (.pos.idx)")

    def _on_tree_progress(self, prog_data: dict):
        if self.current_task == "build_tree":
            self._handle_progress_data(prog_data, "Opening Tree (.tree.idx)")

    def _on_hot_progress(self, prog_data: dict):
        if self.current_task == "build_continuations":
            scanned = prog_data.get("scanned", 0)
            total = prog_data.get("total", 0)
            nodes = prog_data.get("nodes", 0)
            edges = prog_data.get("edges", 0)
            percent = float(prog_data.get("percent", 0.0))

            self.progress_bar.setValue(min(100, int(percent)))
            elapsed = time.time() - self.task_start_time
            speed_str = f" (~{scanned / elapsed:,.0f} games/s)" if elapsed > 0.3 and scanned > 0 else ""
            self.lbl_progress.setText(
                f"[Continuations Graph (.hot.idx)] Indexed: {scanned:,} / {total:,} games ({percent:.1f}%){speed_str} | Nodes: {nodes:,} | Edges: {edges:,}"
            )

    def _on_feat_progress(self, prog_data: dict):
        if self.current_task == "build_endgames":
            scanned = prog_data.get("scanned", 0)
            total = prog_data.get("total", 0)
            percent = float(prog_data.get("percent", 0.0))

            self.progress_bar.setValue(min(100, int(percent)))
            elapsed = time.time() - self.task_start_time
            speed_str = f" (~{scanned / elapsed:,.0f} games/s)" if elapsed > 0.3 and scanned > 0 else ""
            self.lbl_progress.setText(
                f"[Endgame Feature Index (.feat.idx)] Indexed: {scanned:,} / {total:,} games ({percent:.1f}%){speed_str}"
            )

    def _handle_progress_data(self, prog_data: dict, task_name: str):
        scanned = prog_data.get("scanned", 0)
        total = prog_data.get("total", 0)
        positions = prog_data.get("positions", 0)
        percent = float(prog_data.get("percent", 0.0))

        self.progress_bar.setValue(min(100, int(percent)))
        elapsed = time.time() - self.task_start_time
        speed_str = f" (~{scanned / elapsed:,.0f} games/s)" if elapsed > 0.3 and scanned > 0 else ""
        self.lbl_progress.setText(
            f"[{task_name}] Indexed: {scanned:,} / {total:,} games ({percent:.1f}%){speed_str} | Positions: {positions:,}"
        )

    def closeEvent(self, event):
        if self.client:
            try:
                self.client.pos_index_progress.disconnect(self._on_pos_progress)
            except Exception:
                pass
            try:
                self.client.tree_index_progress.disconnect(self._on_tree_progress)
            except Exception:
                pass
            try:
                self.client.continuations_progress.disconnect(self._on_hot_progress)
            except Exception:
                pass
            try:
                self.client.endgame_index_progress.disconnect(self._on_feat_progress)
            except Exception:
                pass
        super().closeEvent(event)
