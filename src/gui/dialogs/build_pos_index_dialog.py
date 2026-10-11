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
    """Unified Dialog for creating / rebuilding .boost.idx (Search Booster) and .feat.idx (Endgame Taxonomy)."""

    def __init__(self, scid_client, default_ply: int = 24, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Build Fast Database Indexes")
        self.resize(560, 390)
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
            self.client.booster_progress.connect(self._on_booster_progress)
            self.client.pos_index_progress.connect(self._on_booster_progress)
            if hasattr(self.client, "build_continuations_progress"):
                self.client.build_continuations_progress.connect(self._on_hot_progress)
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

        title_lbl = QLabel("⚡ <b>Companion Fast Database Indexes</b>")
        title_lbl.setFont(QFont("Segoe UI", 10, QFont.Bold))
        info_layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Companion binary indexes enable instant opening explorer statistics, "
            "deep variation graphs, sub-second position searching, and 47-feature endgame classification."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #a0a0a0; font-size: 11px;")
        info_layout.addWidget(desc_lbl)

        layout.addWidget(info_frame)

        # Index Targets Selection
        grp_targets = QGroupBox("Select Indexes to Build")
        grp_targets.setObjectName("grpTargets")
        box_targets = QVBoxLayout(grp_targets)
        box_targets.setSpacing(8)

        self.chk_booster = QCheckBox(
            "⚡ Search Booster (.boost.idx) — Fast position matching, opening explorer & dynamic search"
        )
        self.chk_booster.setChecked(True)
        self.chk_booster.setStyleSheet("font-weight: bold;")
        box_targets.addWidget(self.chk_booster)

        self.chk_hot = QCheckBox(
            "📈 Common Continuations Graph (.hot.idx) — Precomputed instant tree & variation graph"
        )
        self.chk_hot.setChecked(True)
        self.chk_hot.setStyleSheet("font-weight: bold;")
        self.chk_hot.toggled.connect(self._on_hot_toggled)
        box_targets.addWidget(self.chk_hot)

        # Options specific to .hot.idx build
        self.hot_options_frame = QFrame()
        self.hot_options_frame.setObjectName("hotOptionsFrame")
        hot_layout = QFormLayout(self.hot_options_frame)
        hot_layout.setContentsMargins(24, 2, 8, 6)
        hot_layout.setSpacing(6)

        self.spin_depth = QSpinBox()
        self.spin_depth.setRange(4, 60)
        self.spin_depth.setValue(default_ply if default_ply else 24)
        self.spin_depth.setSuffix(" plies")
        self.spin_depth.setToolTip("Maximum search depth in half-moves (plies) to index (e.g. 24 plies = 12 full moves)")
        hot_layout.addRow("Max Depth / Ply:", self.spin_depth)

        self.spin_min_games = QSpinBox()
        self.spin_min_games.setRange(1, 1000)
        self.spin_min_games.setValue(1)
        self.spin_min_games.setSuffix(" games")
        self.spin_min_games.setToolTip("Minimum number of games reaching a position to be included in the graph")
        hot_layout.addRow("Min Games Threshold:", self.spin_min_games)

        box_targets.addWidget(self.hot_options_frame)

        self.chk_feat = QCheckBox(
            "♟ Endgame Feature Index (.feat.idx) — 47-type standardized endgame taxonomy"
        )
        self.chk_feat.setChecked(True)
        self.chk_feat.setStyleSheet("font-weight: bold;")
        box_targets.addWidget(self.chk_feat)

        # Backwards compatibility aliases for callers referencing chk_tree, chk_pos
        self.chk_tree = self.chk_booster
        self.chk_pos = self.chk_booster

        layout.addWidget(grp_targets)

        # Form options
        form = QFormLayout()
        form.setSpacing(8)

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
                }
                QProgressBar {
                    background-color: #2d2d2d;
                    color: white;
                    border: 1px solid #444;
                    border-radius: 4px;
                    text-align: center;
                    height: 18px;
                }
                QProgressBar::chunk {
                    background-color: #3b82f6;
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
                    background-color: #333333;
                    color: #666666;
                }
                #btnClose {
                    background-color: #333333;
                    color: #cccccc;
                    border: 1px solid #444;
                    border-radius: 4px;
                    padding: 7px 16px;
                }
                #btnClose:hover {
                    background-color: #444444;
                }
            """)
        else:
            self.lbl_progress.setStyleSheet("color: #64748b; font-size: 11px;")
            self.setStyleSheet("""
                QDialog {
                    background-color: #ffffff;
                    color: #1e293b;
                }
                QLabel {
                    color: #1e293b;
                }
                #infoFrame {
                    background-color: #f8fafc;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                }
                QGroupBox {
                    font-weight: bold;
                    border: 1px solid #e2e8f0;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 10px;
                    color: #1e293b;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                }
                QCheckBox {
                    color: #1e293b;
                }
                QSpinBox {
                    background-color: #ffffff;
                    color: #1e293b;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 4px 8px;
                }
                QProgressBar {
                    background-color: #f1f5f9;
                    color: #1e293b;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    text-align: center;
                    height: 18px;
                }
                QProgressBar::chunk {
                    background-color: #2563eb;
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

    def _on_hot_toggled(self, checked: bool):
        self.hot_options_frame.setEnabled(checked)
        self.hot_options_frame.setVisible(checked)

    def start_build(self):
        if not self.client or not self.client.is_running():
            QMessageBox.warning(self, "Offline", "scid-mgr backend is not connected.")
            return

        self.queue = []
        if self.chk_booster.isChecked():
            self.queue.append("build_booster")
        if self.chk_hot.isChecked():
            self.queue.append("build_continuations")
        if self.chk_feat.isChecked():
            self.queue.append("build_endgames")

        if not self.queue:
            QMessageBox.warning(self, "No Index Selected", "Please select at least one index to build.")
            return

        self.btn_build.setEnabled(False)
        self.chk_booster.setEnabled(False)
        self.chk_hot.setEnabled(False)
        self.chk_feat.setEnabled(False)
        self.spin_threads.setEnabled(False)
        self.hot_options_frame.setEnabled(False)
        self.results = {}
        self.progress_bar.setValue(0)
        self._run_next_task()

    def _run_next_task(self):
        if not self.queue:
            self._all_tasks_completed()
            return

        self.current_task = self.queue.pop(0)
        threads = self.spin_threads.value()
        self.task_start_time = time.time()

        if self.current_task == "build_booster":
            task_label = "Search Booster (.boost.idx)"
        elif self.current_task == "build_continuations":
            max_ply = self.spin_depth.value()
            min_games = self.spin_min_games.value()
            task_label = f"Continuations Graph (.hot.idx, max_ply={max_ply}, min_games={min_games})"
        else:
            task_label = "Endgame Feature Index (.feat.idx)"

        self.progress_bar.setValue(0)
        self.lbl_progress.setText(
            f"Starting {task_label} build ({threads} worker threads)..."
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

        if self.current_task == "build_booster":
            self.client.build_booster(callback=on_complete)
        elif self.current_task == "build_continuations":
            max_ply = self.spin_depth.value()
            min_games = self.spin_min_games.value()
            self.client.build_continuations(
                max_ply=max_ply,
                min_games=min_games,
                threads=threads,
                callback=on_complete,
            )
        elif self.current_task == "build_endgames":
            self.client.build_endgames(callback=on_complete)

    def _all_tasks_completed(self):
        self.progress_bar.setValue(100)
        summary_lines = []
        msg_lines = []
        for task, res in self.results.items():
            if task == "build_booster":
                name = "Search Booster (.boost.idx)"
                items_cnt = res.get("total_plies", 0)
                item_label = "plies"
                games_cnt = res.get("games_indexed", 0)
                extra = f" across {games_cnt:,} games"
            elif task == "build_continuations":
                name = "Continuations Graph (.hot.idx)"
                items_cnt = res.get("total_nodes", res.get("node_count", res.get("nodes_indexed", 0)))
                item_label = "nodes"
                games_cnt = res.get("games_processed", res.get("db_game_count", res.get("total_games", 0)))
                extra = f" across {games_cnt:,} games"
            else:
                name = "Endgame Feature Index (.feat.idx)"
                items_cnt = res.get("total_games", 0)
                item_label = "games"
                extra = ""

            elapsed_ms = res.get("elapsed_ms", res.get("total_duration_ms", 0.0))
            summary_lines.append(f"✅ {name}: {items_cnt:,} {item_label}{extra} in {elapsed_ms:,.0f} ms")
            msg_lines.append(f"• {name}:\n   - Entries: {items_cnt:,} {item_label}{extra}\n   - Elapsed Time: {elapsed_ms / 1000.0:.2f} s")

        self.lbl_progress.setText(" | ".join(summary_lines))
        self._restore_controls()

        QMessageBox.information(
            self,
            "Indexes Created Successfully",
            "Fast database companion indexes have been built successfully:\n\n" + "\n\n".join(msg_lines)
        )

    def _restore_controls(self):
        self.btn_build.setEnabled(True)
        self.chk_booster.setEnabled(True)
        self.chk_hot.setEnabled(True)
        self.chk_feat.setEnabled(True)
        self.spin_threads.setEnabled(True)
        self.hot_options_frame.setEnabled(self.chk_hot.isChecked())

    def _on_booster_progress(self, prog_data: dict):
        if self.current_task == "build_booster":
            scanned = prog_data.get("scanned", 0)
            total = prog_data.get("total", 0)
            plies = prog_data.get("plies", 0)

            if total > 0:
                percent = (scanned / total) * 100.0
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(min(100, int(percent)))
                total_str = f"{total:,}"
            else:
                raw_pct = float(prog_data.get("percent", 0.0))
                percent = raw_pct if 0 <= raw_pct <= 100 else 0.0
                self.progress_bar.setValue(min(100, int(percent)))
                total_str = "..."

            elapsed = time.time() - self.task_start_time
            speed_str = f" (~{scanned / elapsed:,.0f} games/s)" if elapsed > 0.3 and scanned > 0 else ""
            self.lbl_progress.setText(
                f"[Search Booster (.boost.idx)] Indexed: {scanned:,} / {total_str} games ({percent:.1f}%){speed_str} | Plies: {plies:,}"
            )

    def _on_hot_progress(self, prog_data: dict):
        if self.current_task == "build_continuations":
            scanned = prog_data.get("scanned", 0)
            total = prog_data.get("total", 0)
            nodes = prog_data.get("nodes", 0)

            if total > 0:
                percent = (scanned / total) * 100.0
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(min(100, int(percent)))
                total_str = f"{total:,}"
            else:
                raw_pct = float(prog_data.get("percent", 0.0))
                percent = raw_pct if 0 <= raw_pct <= 100 else 0.0
                self.progress_bar.setValue(min(100, int(percent)))
                total_str = "..."

            elapsed = time.time() - self.task_start_time
            speed_str = f" (~{scanned / elapsed:,.0f} games/s)" if elapsed > 0.3 and scanned > 0 else ""
            self.lbl_progress.setText(
                f"[Continuations Graph (.hot.idx)] Indexed: {scanned:,} / {total_str} games ({percent:.1f}%){speed_str}" +
                (f" | Nodes: {nodes:,}" if nodes > 0 else "")
            )

    def _on_feat_progress(self, prog_data: dict):
        if self.current_task == "build_endgames":
            scanned = prog_data.get("scanned", 0)
            total = prog_data.get("total", 0)

            if total > 0:
                percent = (scanned / total) * 100.0
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(min(100, int(percent)))
                total_str = f"{total:,}"
            else:
                raw_pct = float(prog_data.get("percent", 0.0))
                percent = raw_pct if 0 <= raw_pct <= 100 else 0.0
                self.progress_bar.setValue(min(100, int(percent)))
                total_str = "..."

            elapsed = time.time() - self.task_start_time
            speed_str = f" (~{scanned / elapsed:,.0f} games/s)" if elapsed > 0.3 and scanned > 0 else ""
            self.lbl_progress.setText(
                f"[Endgame Feature Index (.feat.idx)] Indexed: {scanned:,} / {total_str} games ({percent:.1f}%){speed_str}"
            )

    def closeEvent(self, event):
        if self.client:
            try:
                self.client.booster_progress.disconnect(self._on_booster_progress)
            except Exception:
                pass
            try:
                self.client.pos_index_progress.disconnect(self._on_booster_progress)
            except Exception:
                pass
            try:
                if hasattr(self.client, "build_continuations_progress"):
                    self.client.build_continuations_progress.disconnect(self._on_hot_progress)
            except Exception:
                pass
            try:
                self.client.endgame_index_progress.disconnect(self._on_feat_progress)
            except Exception:
                pass
        super().closeEvent(event)
