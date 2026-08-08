from PyQt5 import QtCore, QtGui, QtWidgets
import sys
import json

MOVES = [
    {"black_wins": 1, "draws": 0, "move": "Bd6", "white_wins": 0},
    {"black_wins": 0, "draws": 0, "move": "Nb4", "white_wins": 1},
    {"black_wins": 1, "draws": 0, "move": "Nd4", "white_wins": 0},
    {"black_wins": 3, "draws": 1, "move": "Nf6", "white_wins": 3},
    {"black_wins": 1, "draws": 0, "move": "Qf6", "white_wins": 0},
    {"black_wins": 0, "draws": 0, "move": "a5", "white_wins": 1},
    {"black_wins": 64, "draws": 4, "move": "a6", "white_wins": 95},
    {"black_wins": 1, "draws": 0, "move": "d6", "white_wins": 3},
    {"black_wins": 1, "draws": 0, "move": "f5", "white_wins": 0},
    {"black_wins": 0, "draws": 0, "move": "g6", "white_wins": 1},
]


class OpeningExplorerHeader(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)

        self.move_lbl = QtWidgets.QLabel("Move")
        self.move_lbl.setFixedWidth(50)

        self.stats_lbl = QtWidgets.QLabel("Stats (W / D / B)")
        self.stats_lbl.setAlignment(QtCore.Qt.AlignCenter)

        layout.addWidget(self.move_lbl)
        layout.addWidget(self.stats_lbl)

        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        color = "#8b8987" if is_dark else "#555555"
        style = f"color: {color}; font-weight: bold; font-size: 11px;"
        self.move_lbl.setStyleSheet(style)
        self.stats_lbl.setStyleSheet(style)


class PercentageBar(QtWidgets.QWidget):
    def __init__(self, white_win, draw, black_win, parent=None):
        super().__init__(parent)
        self.white_win = white_win
        self.draw = draw
        self.black_win = black_win
        self.setFixedHeight(24)
        self.is_dark = True

        # Calculate percentages and set tooltip
        total = self.white_win + self.draw + self.black_win
        if total > 0:
            white_pct = (self.white_win / total) * 100
            draw_pct = (self.draw / total) * 100
            black_pct = (self.black_win / total) * 100
            self.setToolTip(
                f"White wins: {self.white_win} ({white_pct:.1f}%)\n"
                f"Draws: {self.draw} ({draw_pct:.1f}%)\n"
                f"Black wins: {self.black_win} ({black_pct:.1f}%)"
            )
        else:
            self.setToolTip("No games played")

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        total_w = self.width()
        h = self.height()

        total = self.white_win + self.draw + self.black_win
        if total == 0:
            return

        pw = (self.white_win / total) * total_w
        pd = (self.draw / total) * total_w
        pb = total_w - pw - pd

        # Colors
        color_white = QtGui.QColor("#ffffff")
        color_draw = QtGui.QColor("#888888")
        color_black = QtGui.QColor("#312e2b")

        painter.setPen(QtCore.Qt.NoPen)

        # White
        if pw > 0:
            painter.setBrush(color_white)
            painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if pw > 25:
                painter.setPen(QtGui.QColor("#000000"))
                painter.drawText(
                    QtCore.QRectF(0, 0, pw, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.white_win}",
                )

        # Draw
        if pd > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_draw)
            painter.drawRect(QtCore.QRectF(pw, 0, pd, h))
            if pd > 25:
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.drawText(
                    QtCore.QRectF(pw, 0, pd, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.draw}",
                )

        # Black
        if pb > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_black)
            painter.drawRect(QtCore.QRectF(pw + pd, 0, pb, h))
            if pb > 25:
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.drawText(
                    QtCore.QRectF(pw + pd, 0, pb, h),
                    QtCore.Qt.AlignCenter,
                    f"{self.black_win}",
                )


class MoveItem(QtWidgets.QWidget):
    def __init__(self, move_data, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        self.move_lbl = QtWidgets.QLabel(move_data["move"])
        self.move_lbl.setFixedWidth(50)

        self.bar = PercentageBar(
            move_data["white_wins"], move_data["draws"], move_data["black_wins"]
        )

        layout.addWidget(self.move_lbl)
        layout.addWidget(self.bar)

        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        color = "#ffffff" if is_dark else "#312e2b"
        self.move_lbl.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 13px;"
        )
        self.bar.set_theme(is_dark)


class OpeningExplorer(QtWidgets.QWidget):
    def __init__(self, parent=None, positions=[]):
        super().__init__(parent)
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.header = OpeningExplorerHeader(self)
        self.main_layout.addWidget(self.header)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(1)
        self.container_layout.addStretch()

        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)

        self.set_theme(True)

        if positions:
            self.update_positions(positions)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        self.setStyleSheet(f"background-color: {bg};")
        self.header.set_theme(is_dark)
        for i in range(self.container_layout.count()):
            w = self.container_layout.itemAt(i).widget()
            if isinstance(w, MoveItem):
                w.set_theme(is_dark)

    def update_positions(self, positions):
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for move in positions:
            item = MoveItem(move, self)
            item.set_theme(self.is_dark)
            self.container_layout.insertWidget(self.container_layout.count() - 1, item)


import os

class OpeningProcess(QtCore.QObject):
    dataReady = QtCore.pyqtSignal(list)
    errorOcurred = QtCore.pyqtSignal(str)

    STATE_IDLE = 0
    STATE_INDEXING = 1
    STATE_INTERACTIVE = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QtCore.QProcess(self)
        self.exe_path = r"C:\Users\ASUS\programming\qt_programs\chess\opening-explorer\target\release\opening-explorer.exe"
        self.process.readyReadStandardOutput.connect(self.process_output)
        self.process.readyReadStandardError.connect(self.process_error)
        self.process.finished.connect(self.process_finished)
        self.process.errorOccurred.connect(self.on_process_error)
        
        self.indexer = None
        self.state = self.STATE_IDLE
        self.buffer = ""
        self.response_lines = []
        self.current_db_path = None
        self.is_ready = False
        self.pending_query = None  # Tuple: (fen, filters)

        app = QtWidgets.QApplication.instance()
        if app:
            app.aboutToQuit.connect(self.stop_process)

    def start_query(self, fen, filters=None):
        # 1. Resolve PGN and DB path from settings
        settings = QtCore.QSettings("TestChessApp", "Config")
        pgn_path = settings.value(
            "explorer_pgn_path",
            r"C:\Users\ASUS\programming\qt_programs\chess\downloader\alex.pgn"
        )
        if not pgn_path:
            self.errorOcurred.emit("No PGN path configured in settings")
            return
            
        # 2. Determine DB path (must include 'positions' in filename)
        if pgn_path.lower().endswith(".pgn"):
            db_path = pgn_path + ".positions.db"
        elif pgn_path.lower().endswith(".db") and "positions" not in pgn_path.lower():
            # If a custom .db path is supplied without 'positions' in name
            base, ext = os.path.splitext(pgn_path)
            db_path = f"{base}_positions{ext}"
        else:
            db_path = pgn_path

        # 3. Check if PGN needs to be indexed
        needs_index = False
        if pgn_path.lower().endswith(".pgn") and os.path.exists(pgn_path):
            if not os.path.exists(db_path):
                needs_index = True
            else:
                try:
                    pgn_time = os.path.getmtime(pgn_path)
                    db_time = os.path.getmtime(db_path)
                    if pgn_time > db_time:
                        needs_index = True
                except Exception as e:
                    print(f"Error checking timestamps: {e}")

        # 4. Handle states
        if needs_index:
            self.pending_query = (fen, filters)
            if self.state == self.STATE_INDEXING:
                # Already indexing, just update pending query
                return
            
            # Stop interactive process if running
            self.stop_process()
            
            # Start indexing process using a separate QProcess
            self.state = self.STATE_INDEXING
            self.current_db_path = db_path
            self.errorOcurred.emit("Indexing database, please wait...")
            
            self.indexer = QtCore.QProcess(self)
            self.indexer.setProgram(self.exe_path)
            self.indexer.setArguments(["index", "--pgn", pgn_path, "--db", db_path])
            self.indexer.readyReadStandardOutput.connect(self.indexer_output)
            self.indexer.readyReadStandardError.connect(self.indexer_error)
            self.indexer.finished.connect(self.indexing_finished)
            self.indexer.errorOccurred.connect(self.on_indexer_error)
            self.indexer.start()
            return

        # No indexing needed. Check if we need to start or restart interactive mode.
        if self.state != self.STATE_INTERACTIVE or self.current_db_path != db_path or self.process.state() != QtCore.QProcess.Running:
            self.pending_query = (fen, filters)
            
            # Stop existing process
            self.stop_process()
            
            # Start interactive process
            self.state = self.STATE_INTERACTIVE
            self.current_db_path = db_path
            self.is_ready = False
            self.buffer = ""
            self.response_lines = []
            
            self.process.setProgram(self.exe_path)
            self.process.setArguments(["interactive", "--db", db_path])
            self.process.start()
            return

        # If already interactive and ready, write query directly
        if self.is_ready:
            self.write_query(fen, filters)
        else:
            # Not ready yet, queue this query
            self.pending_query = (fen, filters)

    def write_query(self, fen, filters):
        # Normalize FEN: first 4 fields
        parts = fen.split()
        if len(parts) > 4:
            fen = " ".join(parts[:4])
            
        cmd = f'query "{fen}"'
        if filters:
            if filters.get("player"):
                player = filters["player"].replace('"', '\\"')
                cmd += f' --player "{player}"'
                if filters.get("player_color") in ["white", "black"]:
                    cmd += f' --color {filters["player_color"]}'
            else:
                if filters.get("white"):
                    white = filters["white"].replace('"', '\\"')
                    cmd += f' --white "{white}"'
                if filters.get("black"):
                    black = filters["black"].replace('"', '\\"')
                    cmd += f' --black "{black}"'
            
            if filters.get("min_rating"):
                cmd += f' --min-rating {filters["min_rating"]}'
            if filters.get("max_rating"):
                cmd += f' --max-rating {filters["max_rating"]}'
            if filters.get("eco"):
                eco = filters["eco"].replace('"', '\\"').strip()
                if eco:
                    cmd += f' --eco "{eco}"'
            if filters.get("result"):
                res = filters["result"]
                cmd += f' --result "{res}"'
                
        cmd_str = cmd + "\n"
        self.process.write(cmd_str.encode("utf-8"))

    def process_output(self):
        raw = self.process.readAllStandardOutput().data().decode("utf-8")
        self.buffer += raw
        
        lines = self.buffer.split("\n")
        self.buffer = lines[-1]
        
        for line in lines[:-1]:
            line = line.replace("\r", "")
            line_str = line.strip()
            if line_str == "ready":
                content = "\n".join(self.response_lines).strip()
                self.response_lines = []
                self.handle_response(content)
            else:
                self.response_lines.append(line)

    def handle_response(self, content):
        if not self.is_ready:
            # Startup "ready" signal
            self.is_ready = True
            self.errorOcurred.emit("Explorer connection ready")
        else:
            # Response to a query command
            if content:
                try:
                    if content.startswith("error:"):
                        self.errorOcurred.emit(content)
                    else:
                        data = json.loads(content)
                        self.dataReady.emit(data)
                except Exception as e:
                    self.errorOcurred.emit(f"Explorer JSON Parse Error: {str(e)}")
            else:
                self.dataReady.emit([])
        
        # If we have a pending query, run it now!
        if self.pending_query:
            fen, filters = self.pending_query
            self.pending_query = None
            self.write_query(fen, filters)

    def process_error(self):
        raw = self.process.readAllStandardError().data().decode("utf-8").strip()
        if raw:
            print(f"Explorer stderr: {raw}")
            if "error" in raw.lower() or "failed" in raw.lower():
                self.errorOcurred.emit(raw)

    def process_finished(self, exit_code, exit_status):
        self.is_ready = False
        self.buffer = ""
        self.response_lines = []
        print(f"Interactive process exited with code {exit_code}")

    def on_process_error(self, error):
        print(f"QProcess error: {error}")
        self.errorOcurred.emit(f"Explorer process error: {error}")

    def indexer_output(self):
        raw = self.indexer.readAllStandardOutput().data().decode("utf-8").strip()
        if raw:
            print(f"Indexer stdout: {raw}")
            self.errorOcurred.emit(raw)

    def indexer_error(self):
        raw = self.indexer.readAllStandardError().data().decode("utf-8").strip()
        if raw:
            print(f"Indexer stderr: {raw}")
            if "error" in raw.lower() or "failed" in raw.lower():
                self.errorOcurred.emit(raw)

    def on_indexer_error(self, error):
        print(f"Indexer QProcess error: {error}")
        self.errorOcurred.emit(f"Indexer process error: {error}")

    def indexing_finished(self, exit_code, exit_status):
        self.indexer = None
        if exit_code == 0:
            self.errorOcurred.emit("Indexing complete. Starting explorer...")
            self.state = self.STATE_IDLE
            # Start interactive mode using start_query
            if self.pending_query:
                fen, filters = self.pending_query
                self.pending_query = None
                self.start_query(fen, filters)
        else:
            self.state = self.STATE_IDLE
            self.errorOcurred.emit(f"Indexing failed with exit code {exit_code}")
            self.pending_query = None

    def stop_process(self):
        # Stop indexer if running
        if self.indexer and self.indexer.state() == QtCore.QProcess.Running:
            self.indexer.kill()
            self.indexer.waitForFinished(1000)
        self.indexer = None

        if self.process.state() == QtCore.QProcess.Running:
            self.process.write(b"quit\n")
            if not self.process.waitForFinished(1000):
                self.process.kill()
                
        self.state = self.STATE_IDLE
        self.is_ready = False
        self.buffer = ""
        self.response_lines = []


class OpeningExplorerLogic(QtWidgets.QWidget):
    errorOcurred = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.explorer = OpeningExplorer(self)
        self.last_fen = None
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header / toggle button
        self.toggle_filters_btn = QtWidgets.QPushButton("🔍 Filters", self)
        self.toggle_filters_btn.setCheckable(True)
        self.toggle_filters_btn.setChecked(False)
        self.toggle_filters_btn.clicked.connect(self.toggle_filter_panel)
        layout.addWidget(self.toggle_filters_btn)
        
        # Build Filter Frame
        self.filter_frame = QtWidgets.QFrame(self)
        self.filter_frame.setVisible(False)
        self.filter_frame.setObjectName("FilterFrame")
        
        filter_layout = QtWidgets.QFormLayout(self.filter_frame)
        filter_layout.setContentsMargins(8, 8, 8, 8)
        filter_layout.setSpacing(6)
        
        # Player Row
        self.player_input = QtWidgets.QLineEdit()
        self.player_input.setPlaceholderText("Player name...")
        self.player_color_combo = QtWidgets.QComboBox()
        self.player_color_combo.addItems(["Either Color", "As White", "As Black"])
        
        player_layout = QtWidgets.QHBoxLayout()
        player_layout.addWidget(self.player_input, 2)
        player_layout.addWidget(self.player_color_combo, 1)
        player_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addRow("Player:", player_layout)
        
        # Rating Row
        self.min_rating_spin = QtWidgets.QSpinBox()
        self.min_rating_spin.setRange(0, 3500)
        self.min_rating_spin.setValue(0)
        self.min_rating_spin.setSpecialValueText("Any")
        
        self.max_rating_spin = QtWidgets.QSpinBox()
        self.max_rating_spin.setRange(0, 3500)
        self.max_rating_spin.setValue(0)
        self.max_rating_spin.setSpecialValueText("Any")
        
        rating_layout = QtWidgets.QHBoxLayout()
        rating_layout.addWidget(QtWidgets.QLabel("Min:"))
        rating_layout.addWidget(self.min_rating_spin)
        rating_layout.addWidget(QtWidgets.QLabel("Max:"))
        rating_layout.addWidget(self.max_rating_spin)
        rating_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addRow("Rating:", rating_layout)
        
        # ECO / Result Row
        self.eco_input = QtWidgets.QLineEdit()
        self.eco_input.setPlaceholderText("e.g. B01")
        self.eco_input.setMaxLength(3)
        
        self.result_combo = QtWidgets.QComboBox()
        self.result_combo.addItems(["Any", "1-0", "0-1", "1/2-1/2"])
        
        eco_result_layout = QtWidgets.QHBoxLayout()
        eco_result_layout.addWidget(self.eco_input, 1)
        eco_result_layout.addWidget(QtWidgets.QLabel("Result:"), 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        eco_result_layout.addWidget(self.result_combo, 2)
        eco_result_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addRow("ECO:", eco_result_layout)
        
        # Action Buttons
        self.apply_btn = QtWidgets.QPushButton("Apply Filters")
        self.apply_btn.clicked.connect(self.apply_filters)
        self.clear_btn = QtWidgets.QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_filters)
        
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addRow("", btn_layout)
        
        layout.addWidget(self.filter_frame)
        layout.addWidget(self.explorer)

        self.opening_process = OpeningProcess(self)
        self.opening_process.dataReady.connect(self.on_data_ready)
        self.opening_process.errorOcurred.connect(self.errorOcurred.emit)

        # Connect inputs to apply automatically where appropriate
        self.player_input.returnPressed.connect(self.apply_filters)
        self.eco_input.returnPressed.connect(self.apply_filters)
        self.player_color_combo.currentIndexChanged.connect(self.apply_filters)
        self.result_combo.currentIndexChanged.connect(self.apply_filters)

    def toggle_filter_panel(self, checked):
        self.filter_frame.setVisible(checked)

    def get_filters(self):
        filters = {}
        player = self.player_input.text().strip()
        if player:
            filters["player"] = player
            color_idx = self.player_color_combo.currentIndex()
            if color_idx == 1:
                filters["player_color"] = "white"
            elif color_idx == 2:
                filters["player_color"] = "black"
            else:
                filters["player_color"] = "both"
        
        min_r = self.min_rating_spin.value()
        if min_r > 0:
            filters["min_rating"] = min_r
            
        max_r = self.max_rating_spin.value()
        if max_r > 0:
            filters["max_rating"] = max_r
            
        eco = self.eco_input.text().strip()
        if eco:
            filters["eco"] = eco
            
        result = self.result_combo.currentText()
        if result != "Any":
            filters["result"] = result
            
        return filters

    def apply_filters(self):
        if self.last_fen:
            self.send_fen(self.last_fen)

    def clear_filters(self):
        self.player_input.clear()
        self.player_color_combo.setCurrentIndex(0)
        self.min_rating_spin.setValue(0)
        self.max_rating_spin.setValue(0)
        self.eco_input.clear()
        self.result_combo.setCurrentIndex(0)
        self.apply_filters()

    def set_theme(self, is_dark: bool):
        self.explorer.set_theme(is_dark)
        
        # Style filter panel
        if is_dark:
            bg_color = "#262421"
            text_color = "#ffffff"
            input_bg = "#312e2b"
            input_border = "#44413c"
            btn_bg = "#3c3934"
            btn_hover_bg = "#4c4943"
            label_color = "#8b8987"
        else:
            bg_color = "#ffffff"
            text_color = "#312e2b"
            input_bg = "#f5f5f5"
            input_border = "#cccccc"
            btn_bg = "#e1e1e1"
            btn_hover_bg = "#d1d1d1"
            label_color = "#555555"

        frame_style = f"background-color: {bg_color}; border-bottom: 1px solid {input_border};"
        self.filter_frame.setStyleSheet(f"QFrame#FilterFrame {{ {frame_style} }}")
        
        label_style = f"color: {label_color}; font-weight: bold;"
        for lbl in self.filter_frame.findChildren(QtWidgets.QLabel):
            lbl.setStyleSheet(label_style)
            
        input_style = f"""
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {input_bg};
                color: {text_color};
                border: 1px solid {input_border};
                border-radius: 3px;
                padding: 3px 5px;
            }}
        """
        for widget in self.filter_frame.findChildren((QtWidgets.QLineEdit, QtWidgets.QComboBox, QtWidgets.QSpinBox)):
            widget.setStyleSheet(input_style)
            
        btn_style = f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {text_color};
                border: 1px solid {input_border};
                border-radius: 3px;
                padding: 4px 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {btn_hover_bg};
            }}
        """
        self.apply_btn.setStyleSheet(btn_style)
        self.clear_btn.setStyleSheet(btn_style)
        
        toggle_bg = "#312e2b" if is_dark else "#e1e1e1"
        toggle_color = "#bababa" if is_dark else "#312e2b"
        toggle_hover = "#3c3934" if is_dark else "#d1d1d1"
        toggle_checked = "#211f1d" if is_dark else "#c5c5c5"
        self.toggle_filters_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {toggle_bg};
                color: {toggle_color};
                border: none;
                padding: 6px;
                font-weight: bold;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {toggle_hover};
                color: {text_color};
            }}
            QPushButton:checked {{
                background-color: {toggle_checked};
                color: {text_color};
            }}
        """)

    def on_data_ready(self, data):
        if data:
            data = sorted(
                data,
                key=lambda x: x["white_wins"] + x["draws"] + x["black_wins"],
                reverse=True,
            )
            self.explorer.update_positions(data[:12])
        else:
            self.explorer.update_positions([])

    def send_fen(self, fen):
        self.last_fen = fen
        self.opening_process.start_query(fen, self.get_filters())


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = OpeningExplorer(positions=MOVES)
    w.resize(300, 400)
    w.show()
    sys.exit(app.exec_())
