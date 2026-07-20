import sys
from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
                             QTextBrowser, QVBoxLayout, QWidget, QFrame, QPushButton)

class AnalysisWidget(QWidget):
    evaluationToggled = pyqtSignal(bool)
    configClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(2)
        self.setLayout(self.main_layout)

        # Analysis data storage
        self.analysis_lines = {} # multipv index -> info dict
        self.is_dark = True
        self.last_board_fen = None

        # --- Header Bar ---
        self.header_frame = QFrame()
        self.header_frame.setObjectName("AnalysisHeader")
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(8, 4, 8, 4)
        
        self.check_analysis = QCheckBox("Engine")
        self.check_analysis.setCursor(Qt.PointingHandCursor)
        self.check_analysis.toggled.connect(self.on_checkbox_toggled)
        
        from utils.helpers import _qicon
        self.btn_config = QPushButton()
        self.btn_config.setObjectName("SmallIconButton")
        self.btn_config.setProperty("icon_name", "fa6s.gear")
        self.btn_config.setIcon(_qicon("fa6s.gear", is_dark=self.is_dark))
        self.btn_config.setIconSize(QSize(16, 16))
        self.btn_config.setCursor(Qt.PointingHandCursor)
        self.btn_config.setToolTip("Engine Config")
        self.btn_config.clicked.connect(self.configClicked.emit)
        
        self.score_label = QLabel("0.00")
        self.score_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.score_label.setAlignment(Qt.AlignCenter)
        
        self.depth_label = QLabel("depth 0")
        self.depth_label.setFont(QFont("Arial", 8))
        
        self.header_layout.addWidget(self.check_analysis)
        self.header_layout.addWidget(self.btn_config)
        self.header_layout.addSpacing(10)
        self.header_layout.addWidget(self.score_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.depth_label)
        
        self.main_layout.addWidget(self.header_frame)

        # --- Lines Area ---
        self.lines_display = QTextBrowser()
        self.lines_display.setOpenExternalLinks(False)
        self.lines_display.setPlaceholderText("Enable engine for analysis...")
        self.main_layout.addWidget(self.lines_display)
        
        self.set_theme(True) # Default dark

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        if hasattr(self, "btn_config"):
            from utils.helpers import _qicon
            self.btn_config.setIcon(_qicon("fa6s.gear", is_dark=is_dark))
        if is_dark:
            self.header_frame.setStyleSheet("QFrame#AnalysisHeader { background-color: #262421; border-radius: 3px; }")
            self.check_analysis.setStyleSheet("color: #bababa; font-weight: bold;")
            self.score_label.setStyleSheet("color: #ffffff; font-weight: bold; background: #312e2b; padding: 2px 8px; border-radius: 2px;")
            self.depth_label.setStyleSheet("color: #8b8987;")
            self.lines_display.setStyleSheet("""
                QTextBrowser {
                    background-color: #262421;
                    border: none;
                    color: #bababa;
                    font-family: 'Noto Sans', 'Segoe UI', sans-serif;
                    font-size: 14px;
                }
            """)
        else:
            self.header_frame.setStyleSheet("QFrame#AnalysisHeader { background-color: #e1e1e1; border-radius: 3px; border: 1px solid #ccc; }")
            self.check_analysis.setStyleSheet("color: #312e2b; font-weight: bold;")
            self.score_label.setStyleSheet("color: #000000; font-weight: bold; background: #ffffff; padding: 2px 8px; border: 1px solid #ccc; border-radius: 2px;")
            self.depth_label.setStyleSheet("color: #555;")
            self.lines_display.setStyleSheet("""
                QTextBrowser {
                    background-color: #ffffff;
                    border: 1px solid #ccc;
                    color: #312e2b;
                    font-family: 'Noto Sans', 'Segoe UI', sans-serif;
                    font-size: 14px;
                }
            """)
        self.render_html()

    def set_depth(self, depth: str):
        text = depth.replace("=", " ")
        self.depth_label.setText(text)

    def set_score(self, score: str):
        try:
            val = float(score)
            prefix = "+" if val > 0 else ""
            self.score_label.setText(f"{prefix}{val:.2f}")
        except ValueError:
            self.score_label.setText(score)

    def on_checkbox_toggled(self, checked: bool):
        if checked:
            self.lines_display.setPlaceholderText("")
        else:
            self.lines_display.setPlaceholderText("Enable engine for analysis...")
        self.evaluationToggled.emit(checked)

    def render_html(self):
        if not self.analysis_lines:
            return
            
        sorted_indices = sorted(self.analysis_lines.keys())
        
        import chess
        board = chess.Board(self.last_board_fen) if self.last_board_fen else None
        turn = board.turn if board else chess.WHITE

        bg_color = "#312e2b" if self.is_dark else "#f5f5f5"
        text_color = "#bababa" if self.is_dark else "#312e2b"
        border_color = "#3d3a37" if self.is_dark else "#e1e1e1"

        html = f"""
        <style>
            .line-card {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 6px;
                margin-bottom: 6px;
                color: {text_color};
            }}
            .idx {{ font-weight: bold; color: #8b8987; margin-right: 5px; }}
            .score {{ font-weight: bold; color: #4DB6AC; min-width: 50px; display: inline-block; }}
            .moves {{ margin-left: 5px; }}
        </style>
        """

        for idx in sorted_indices:
            data = self.analysis_lines[idx]
            score = self.format_score(data, turn=turn)
            pv_moves = data.get("pv", [])
            
            moves_text = ""
            if board:
                temp_board = board.copy()
                formatted_moves = []
                is_first = True
                for move_uci in pv_moves[:12]:
                    try:
                        move = chess.Move.from_uci(move_uci)
                        if move in temp_board.legal_moves:
                            san = temp_board.san(move)
                            m_num = temp_board.fullmove_number
                            if temp_board.turn == chess.WHITE:
                                formatted_moves.append(f"<b>{m_num}.</b> {san}")
                            else:
                                if is_first:
                                    formatted_moves.append(f"<b>{m_num}...</b> {san}")
                                else:
                                    formatted_moves.append(san)
                            temp_board.push(move)
                            is_first = False
                        else:
                            formatted_moves.append(move_uci)
                    except:
                        formatted_moves.append(move_uci)
                moves_text = " ".join(formatted_moves)
            else:
                moves_text = " ".join(pv_moves[:12])

            html += f"""
            <div class='line-card'>
                <span class='idx'>{idx}.</span>
                <span class='score'>{score}</span>
                <span class='moves'>{moves_text}</span>
            </div>
            """

        self.lines_display.setHtml(html)

    def update_analysis(self, info: dict, board_fen: str = None):
        """Update analysis lines with new info."""
        from PyQt5.QtCore import QSettings
        settings = QSettings("TestChessApp", "Engine")
        multipv_limit = int(settings.value("multipv", 1))

        self.analysis_lines = {k: v for k, v in self.analysis_lines.items() if k <= multipv_limit}

        multipv = info.get("multipv", 1)
        if multipv <= multipv_limit:
            self.analysis_lines[multipv] = info
        if board_fen:
            self.last_board_fen = board_fen
            
        self.render_html()
        
        # Update top score if it's the first PV
        if multipv == 1:
            import chess
            board = chess.Board(self.last_board_fen) if self.last_board_fen else None
            turn = board.turn if board else chess.WHITE
            self.set_score(self.format_score(info, raw=True, turn=turn))

    def update_analysis_batch(self, infos: list, board_fen: str = None):
        """Update multiple analysis lines and render once."""
        if board_fen:
            self.last_board_fen = board_fen
            
        from PyQt5.QtCore import QSettings
        settings = QSettings("TestChessApp", "Engine")
        multipv_limit = int(settings.value("multipv", 1))

        self.analysis_lines = {k: v for k, v in self.analysis_lines.items() if k <= multipv_limit}

        for info in infos:
            multipv = info.get("multipv", 1)
            if multipv <= multipv_limit:
                self.analysis_lines[multipv] = info
            
        self.render_html()
        
        # Update top score if it's the first PV
        multipv_1_info = self.analysis_lines.get(1)
        if multipv_1_info:
            import chess
            board = chess.Board(self.last_board_fen) if self.last_board_fen else None
            turn = board.turn if board else chess.WHITE
            self.set_score(self.format_score(multipv_1_info, raw=True, turn=turn))



    def reset_lines(self):
        """Clear the current analysis lines data."""
        self.analysis_lines.clear()
        self.lines_display.clear()
        self.score_label.setText("")
        self.depth_label.setText("")

    def format_score(self, info: dict, raw=False, turn=None) -> str:
        import chess
        s_type = info.get("score_type")
        s_val = info.get("score_value", 0)
        
        # UCI engines report scores relative to side-to-move.
        # Normalize to White POV (Positive = White better, Negative = Black better)
        if turn == chess.BLACK:
            s_val = -s_val

        if s_type == "mate":
            return f"M{abs(s_val)}" if not raw else f"M{s_val}"
        else:
            score = s_val / 100.0
            if raw:
                return f"{score:.2f}"
            prefix = "+" if score > 0 else ""
            return f"{prefix}{score:.2f}"

    def clear(self):
        self.score_label.setText("0.00")
        self.depth_label.setText("depth 0")
        self.lines_display.clear()
        self.analysis_lines.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AnalysisWidget()
    w.set_theme(False)
    w.resize(350, 200)
    w.show()
    sys.exit(app.exec_())
