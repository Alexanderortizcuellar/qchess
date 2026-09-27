import sys
import chess
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QRect, QSettings
from PyQt5.QtGui import QFont, QPainter, QColor, QFontMetrics, QBrush, QPen
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    QFrame,
    QPushButton,
    QScrollArea,
)


class EngineMoveToken:
    """Represents an individual move in an engine PV line with hit-testing geometry."""
    def __init__(self, san: str, uci: str, fen: str, move_num: int, is_white: bool, line_idx: int, move_idx: int):
        self.san = san
        self.uci = uci
        self.fen = fen
        self.move_num = move_num
        self.is_white = is_white
        self.line_idx = line_idx
        self.move_idx = move_idx
        self.rect = QRect()


class EngineLineData:
    """Structured data container for a single MultiPV analysis line."""
    def __init__(self, multipv: int, score_str: str, depth_str: str, tokens: list, raw_score: float = 0.0, is_mate: bool = False):
        self.multipv = multipv
        self.score_str = score_str
        self.depth_str = depth_str
        self.tokens = tokens
        self.raw_score = raw_score
        self.is_mate = is_mate
        self.row_rect = QRect()
        self.idx_rect = QRect()
        self.score_rect = QRect()


class QPainterEngineView(QWidget):
    """
    Lightweight, custom-painted engine analysis lines view with multi-line move wrapping.
    Provides precise per-move hit testing, hover highlights, and board preview signal hooks.
    """
    moveHovered = pyqtSignal(object, object)  # (fen: str | None, uci: str | None)
    moveClicked = pyqtSignal(str, str)        # (uci: str, fen: str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.lines = []
        self.placeholder_text = "Enable engine for analysis..."
        self.is_dark = True
        self.hovered_token = None
        self._preview_active = False
        self.token_line_h = 24
        self.row_spacing = 6
        self.calculated_height = 80
        self.setMinimumHeight(80)

    def set_placeholder(self, text: str):
        self.placeholder_text = text
        self.lines = []
        if self.hovered_token is not None or self._preview_active:
            self.hovered_token = None
            self._preview_active = False
            self.moveHovered.emit(None, None)
        self.calculated_height = 80
        self.setMinimumHeight(80)
        self.updateGeometry()
        self.update()

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.update()

    def set_lines(self, lines: list):
        self.lines = lines
        self.compute_layout()
        self.update()

    def sizeHint(self):
        return QSize(200, self.calculated_height)

    def compute_layout(self):
        if not self.lines:
            self.calculated_height = 80
            self.setMinimumHeight(80)
            self.updateGeometry()
            return

        font_family = "Segoe UI"
        font_regular = QFont(font_family, 9)
        font_bold = QFont(font_family, 9, QFont.Bold)
        fm_regular = QFontMetrics(font_regular)
        fm_bold = QFontMetrics(font_bold)

        self.token_line_h = max(22, fm_regular.height() + 4)
        margin_x = 4
        margin_y = 4
        avail_width = max(80, self.width() - margin_x * 2)

        cur_y = margin_y
        for line in self.lines:
            card_top = cur_y
            card_left = margin_x

            # 1. Line Index (e.g. "1.")
            idx_str = f"{line.multipv}."
            idx_w = fm_bold.width(idx_str) + 6

            # 2. Score Badge (e.g. "+0.45", "M3")
            score_text = line.score_str
            score_w = fm_bold.width(score_text) + 12
            score_h = self.token_line_h

            prefix_w = idx_w + score_w + 8
            
            line.idx_rect = QRect(card_left + 6, card_top + 4, idx_w, score_h)
            line.score_rect = QRect(card_left + 6 + idx_w, card_top + 4, score_w, score_h)

            # Move Tokens Layout (Wrapping flow)
            start_x = card_left + 6 + prefix_w
            wrap_x = card_left + 6 + prefix_w  # Hanging indent aligned with first move
            token_x = start_x
            token_y = card_top + 4

            # If card is very narrow, wrap to a standard left indent
            if wrap_x > card_left + avail_width - 80:
                wrap_x = card_left + 8

            for token in line.tokens:
                token_w = fm_regular.width(token.san) + 8

                # Check if we need to wrap to the next line
                if token_x + token_w > card_left + avail_width - 6 and token_x > wrap_x:
                    token_y += self.token_line_h + 3
                    token_x = wrap_x

                token.rect = QRect(token_x, token_y, token_w, self.token_line_h)
                token_x += token_w + 3

            card_bottom = token_y + self.token_line_h + 4
            card_height = max(score_h + 8, card_bottom - card_top)
            line.row_rect = QRect(card_left, card_top, avail_width, card_height)

            cur_y += card_height + self.row_spacing

        self.calculated_height = max(80, cur_y + margin_y)
        self.setMinimumHeight(self.calculated_height)
        self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.compute_layout()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        found_token = None
        inside_lines_area = False

        if self.lines:
            top_y = self.lines[0].row_rect.top()
            bottom_y = self.lines[-1].row_rect.bottom()
            # Check if mouse is within the active engine lines vertical boundaries
            if top_y <= pos.y() <= bottom_y:
                inside_lines_area = True
                for line in self.lines:
                    if line.row_rect.contains(pos):
                        for token in line.tokens:
                            if token.rect.isValid() and token.rect.contains(pos):
                                found_token = token
                                break
                        break

        if inside_lines_area:
            if found_token != self.hovered_token:
                self.hovered_token = found_token
                if self.hovered_token:
                    self.setCursor(Qt.PointingHandCursor)
                    self._preview_active = True
                    self.moveHovered.emit(self.hovered_token.fen, self.hovered_token.uci)
                else:
                    self.setCursor(Qt.ArrowCursor)
                    # Inside line card bounds: hold the active ghost preview across token gaps
                self.update()
        else:
            # Outside active engine lines (e.g. empty canvas space below) -> restore real board
            if self.hovered_token is not None or self._preview_active:
                self.hovered_token = None
                self._preview_active = False
                self.setCursor(Qt.ArrowCursor)
                self.moveHovered.emit(None, None)
                self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hovered_token = None
        self._preview_active = False
        self.setCursor(Qt.ArrowCursor)
        self.moveHovered.emit(None, None)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            for line in self.lines:
                if line.row_rect.contains(pos):
                    for token in line.tokens:
                        if token.rect.isValid() and token.rect.contains(pos):
                            self.moveClicked.emit(token.uci, token.fen)
                            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        font_family = "Segoe UI"
        font_regular = QFont(font_family, 9)
        font_bold = QFont(font_family, 9, QFont.Bold)
        fm_regular = QFontMetrics(font_regular)
        fm_bold = QFontMetrics(font_bold)

        if not self.lines:
            painter.setFont(font_regular)
            color_text = QColor("#8b8987") if self.is_dark else QColor("#94a3b8")
            painter.setPen(color_text)
            painter.drawText(self.rect(), Qt.AlignCenter, self.placeholder_text)
            return

        # Palette definition
        if self.is_dark:
            card_bg = QColor("#312e2b")
            card_border = QColor("#3d3a37")
            idx_color = QColor("#8b8987")
            score_bg = QColor("#21201d")
            score_border = QColor("#403d39")
            score_pos = QColor("#4DB6AC")
            score_neg = QColor("#ef5350")
            score_mate = QColor("#ffd54f")
            move_text_color = QColor("#d4d4d4")
            hover_bg = QColor("#4a4641")
            hover_border = QColor("#5e5852")
        else:
            card_bg = QColor("#f8fafc")
            card_border = QColor("#e2e8f0")
            idx_color = QColor("#64748b")
            score_bg = QColor("#ffffff")
            score_border = QColor("#cbd5e1")
            score_pos = QColor("#2563eb")
            score_neg = QColor("#dc2626")
            score_mate = QColor("#d97706")
            move_text_color = QColor("#0f172a")
            hover_bg = QColor("#e2e8f0")
            hover_border = QColor("#cbd5e1")

        for line in self.lines:
            row_r = line.row_rect
            if not row_r.isValid():
                continue

            # 1. Draw Row Background Card
            painter.setPen(QPen(card_border, 1))
            painter.setBrush(QBrush(card_bg))
            painter.drawRoundedRect(row_r, 4, 4)

            # 2. Draw Line Index
            if line.idx_rect.isValid():
                painter.setFont(font_bold)
                painter.setPen(idx_color)
                painter.drawText(line.idx_rect, Qt.AlignVCenter | Qt.AlignLeft, f"{line.multipv}.")

            # 3. Draw Score Badge
            if line.score_rect.isValid():
                painter.setPen(QPen(score_border, 1))
                painter.setBrush(QBrush(score_bg))
                painter.drawRoundedRect(line.score_rect, 3, 3)

                if line.is_mate:
                    sc_color = score_mate
                elif line.raw_score < 0:
                    sc_color = score_neg
                else:
                    sc_color = score_pos

                painter.setPen(sc_color)
                painter.setFont(font_bold)
                painter.drawText(line.score_rect, Qt.AlignCenter, line.score_str)

            # 4. Draw Move Tokens
            for token in line.tokens:
                if not token.rect.isValid():
                    continue

                if token == self.hovered_token:
                    painter.setPen(QPen(hover_border, 1))
                    painter.setBrush(QBrush(hover_bg))
                    painter.drawRoundedRect(token.rect, 3, 3)

                painter.setFont(font_regular)
                painter.setPen(move_text_color)
                painter.drawText(token.rect, Qt.AlignCenter, token.san)


class AnalysisWidget(QWidget):
    evaluationToggled = pyqtSignal(bool)
    configClicked = pyqtSignal()
    multipvChanged = pyqtSignal(int)
    moveHovered = pyqtSignal(object, object)
    moveClicked = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(3)
        self.setLayout(self.main_layout)

        # MultiPV & theme state
        settings = QSettings("TestChessApp", "Engine")
        self.multipv_limit = int(settings.value("multipv", 1))
        if self.multipv_limit < 1:
            self.multipv_limit = 1
        elif self.multipv_limit > 5:
            self.multipv_limit = 5

        self.analysis_lines = {}  # multipv index -> raw info dict
        self.is_dark = True
        self.last_board_fen = None

        # --- Header Bar ---
        self.header_frame = QFrame()
        self.header_frame.setObjectName("AnalysisHeader")
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(6, 3, 6, 3)
        self.header_layout.setSpacing(4)
        
        self.engine_name = "Stockfish"
        self.check_analysis = QCheckBox(self.engine_name)
        self.check_analysis.setCursor(Qt.PointingHandCursor)
        self.check_analysis.toggled.connect(self.on_checkbox_toggled)
        
        from utils.helpers import _qicon

        # MultiPV Quick Line Controls (- [N] +)
        self.btn_minus_lines = QPushButton()
        self.btn_minus_lines.setObjectName("SmallIconButton")
        self.btn_minus_lines.setProperty("icon_name", "fa6s.minus")
        self.btn_minus_lines.setIcon(_qicon("fa6s.minus", is_dark=self.is_dark))
        self.btn_minus_lines.setIconSize(QSize(11, 11))
        self.btn_minus_lines.setCursor(Qt.PointingHandCursor)
        self.btn_minus_lines.setToolTip("Fewer engine lines")
        self.btn_minus_lines.clicked.connect(self.decrement_lines)

        self.lbl_lines = QLabel(f"{self.multipv_limit}")
        self.lbl_lines.setFont(QFont("Arial", 9, QFont.Bold))
        self.lbl_lines.setAlignment(Qt.AlignCenter)
        self.lbl_lines.setToolTip("Number of engine lines (MultiPV)")

        self.btn_plus_lines = QPushButton()
        self.btn_plus_lines.setObjectName("SmallIconButton")
        self.btn_plus_lines.setProperty("icon_name", "fa6s.plus")
        self.btn_plus_lines.setIcon(_qicon("fa6s.plus", is_dark=self.is_dark))
        self.btn_plus_lines.setIconSize(QSize(11, 11))
        self.btn_plus_lines.setCursor(Qt.PointingHandCursor)
        self.btn_plus_lines.setToolTip("More engine lines")
        self.btn_plus_lines.clicked.connect(self.increment_lines)

        # Engine Config Gear Button
        self.btn_config = QPushButton()
        self.btn_config.setObjectName("SmallIconButton")
        self.btn_config.setProperty("icon_name", "fa6s.gear")
        self.btn_config.setIcon(_qicon("fa6s.gear", is_dark=self.is_dark))
        self.btn_config.setIconSize(QSize(15, 15))
        self.btn_config.setCursor(Qt.PointingHandCursor)
        self.btn_config.setToolTip("Engine Config")
        self.btn_config.clicked.connect(self.configClicked.emit)
        
        self.score_label = QLabel("0.00")
        self.score_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.score_label.setAlignment(Qt.AlignCenter)
        
        self.depth_label = QLabel("depth 0")
        self.depth_label.setFont(QFont("Arial", 8))
        
        self.header_layout.addWidget(self.check_analysis)
        self.header_layout.addSpacing(2)
        self.header_layout.addWidget(self.btn_minus_lines)
        self.header_layout.addWidget(self.lbl_lines)
        self.header_layout.addWidget(self.btn_plus_lines)
        self.header_layout.addSpacing(2)
        self.header_layout.addWidget(self.btn_config)
        self.header_layout.addSpacing(8)
        self.header_layout.addWidget(self.score_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.depth_label)
        
        self.main_layout.addWidget(self.header_frame)

        # --- Custom QPainter Lines Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.lines_view = QPainterEngineView()
        self.lines_view.moveHovered.connect(self.moveHovered.emit)
        self.lines_view.moveClicked.connect(self.moveClicked.emit)
        self.scroll_area.setWidget(self.lines_view)

        self.main_layout.addWidget(self.scroll_area)
        
        self.update_buttons_state()
        self.set_theme(True)

    def increment_lines(self):
        if self.multipv_limit < 5:
            self.set_multipv(self.multipv_limit + 1)

    def decrement_lines(self):
        if self.multipv_limit > 1:
            self.set_multipv(self.multipv_limit - 1)

    def set_multipv(self, count: int):
        count = max(1, min(5, count))
        if count == self.multipv_limit:
            return

        self.multipv_limit = count
        self.lbl_lines.setText(str(count))
        self.update_buttons_state()

        settings = QSettings("TestChessApp", "Engine")
        settings.setValue("multipv", count)

        # Prune existing lines exceeding the new limit
        self.analysis_lines = {k: v for k, v in self.analysis_lines.items() if k <= self.multipv_limit}
        self.render_lines()
        self.multipvChanged.emit(count)

    def update_buttons_state(self):
        self.btn_minus_lines.setEnabled(self.multipv_limit > 1)
        self.btn_plus_lines.setEnabled(self.multipv_limit < 5)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        from utils.helpers import _qicon
        self.btn_minus_lines.setIcon(_qicon("fa6s.minus", is_dark=is_dark))
        self.btn_plus_lines.setIcon(_qicon("fa6s.plus", is_dark=is_dark))
        self.btn_config.setIcon(_qicon("fa6s.gear", is_dark=is_dark))
        self.lines_view.set_theme(is_dark)

        if is_dark:
            self.header_frame.setStyleSheet("QFrame#AnalysisHeader { background-color: #262421; border-radius: 4px; }")
            self.check_analysis.setStyleSheet("color: #bababa; font-weight: bold;")
            self.lbl_lines.setStyleSheet("color: #bababa; font-weight: bold; min-width: 14px;")
            self.score_label.setStyleSheet("color: #ffffff; font-weight: bold; background: #312e2b; padding: 2px 8px; border-radius: 4px;")
            self.depth_label.setStyleSheet("color: #8b8987;")
            self.scroll_area.setStyleSheet("QScrollArea { background-color: #262421; border: none; }")
        else:
            self.header_frame.setStyleSheet("QFrame#AnalysisHeader { background-color: #f1f5f9; border-radius: 4px; border: 1px solid #cbd5e1; }")
            self.check_analysis.setStyleSheet("color: #0f172a; font-weight: bold;")
            self.lbl_lines.setStyleSheet("color: #334155; font-weight: bold; min-width: 14px;")
            self.score_label.setStyleSheet("color: #2563eb; font-weight: bold; background: #ffffff; padding: 2px 8px; border: 1px solid #cbd5e1; border-radius: 4px;")
            self.depth_label.setStyleSheet("color: #64748b;")
            self.scroll_area.setStyleSheet("QScrollArea { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 4px; }")

        self.render_lines()

    def set_engine_name(self, name: str):
        self.engine_name = name if name else "Engine"
        self.check_analysis.setText(self.engine_name)

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
            self.show_starting_status()
        else:
            self.clear()
        self.evaluationToggled.emit(checked)

    def show_starting_status(self):
        """Show 'Starting engine analysis...' status while waiting for the engine."""
        self.analysis_lines.clear()
        self.lines_view.set_placeholder("Starting engine analysis...")
        self.score_label.setText("...")
        self.depth_label.setText("starting...")

    def render_lines(self):
        # Filter out lines from stale FENs or exceeding multipv limit
        valid_lines = {}
        for k, v in self.analysis_lines.items():
            if k <= self.multipv_limit:
                line_fen = v.get("fen")
                if not line_fen or not self.last_board_fen or line_fen == self.last_board_fen:
                    valid_lines[k] = v

        if not valid_lines:
            if not self.check_analysis.isChecked():
                self.lines_view.set_placeholder("Enable engine for analysis...")
            else:
                self.lines_view.set_placeholder("Analyzing position...")
            self.lines_view.set_lines([])
            return

        sorted_indices = sorted(valid_lines.keys())
        board = chess.Board(self.last_board_fen) if self.last_board_fen else None
        turn = board.turn if board else chess.WHITE

        rendered_lines = []
        for idx in sorted_indices:
            data = valid_lines[idx]
            score_str, raw_val, is_mate = self.format_score_meta(data, turn=turn)
            pv_moves = data.get("pv", [])

            tokens = []
            if board:
                temp_board = board.copy()
                is_first = True
                for m_idx, move_uci in enumerate(pv_moves[:24]):
                    try:
                        move = chess.Move.from_uci(move_uci)
                        if move in temp_board.legal_moves:
                            san = temp_board.san(move)
                            m_num = temp_board.fullmove_number
                            is_white_move = (temp_board.turn == chess.WHITE)

                            if is_white_move:
                                display_san = f"{m_num}. {san}"
                            else:
                                if is_first:
                                    display_san = f"{m_num}... {san}"
                                else:
                                    display_san = san

                            temp_board.push(move)
                            ply_fen = temp_board.fen()
                            token = EngineMoveToken(
                                san=display_san,
                                uci=move_uci,
                                fen=ply_fen,
                                move_num=m_num,
                                is_white=is_white_move,
                                line_idx=idx,
                                move_idx=m_idx
                            )
                            tokens.append(token)
                            is_first = False
                        else:
                            tokens.append(EngineMoveToken(move_uci, move_uci, "", 0, True, idx, m_idx))
                    except Exception:
                        tokens.append(EngineMoveToken(move_uci, move_uci, "", 0, True, idx, m_idx))
            else:
                for m_idx, move_uci in enumerate(pv_moves[:24]):
                    tokens.append(EngineMoveToken(move_uci, move_uci, "", 0, True, idx, m_idx))

            depth_str = f"d{data.get('depth', '')}" if data.get("depth") else ""
            line_data = EngineLineData(
                multipv=idx,
                score_str=score_str,
                depth_str=depth_str,
                tokens=tokens,
                raw_score=raw_val,
                is_mate=is_mate
            )
            rendered_lines.append(line_data)

        self.lines_view.set_lines(rendered_lines)

    def update_analysis(self, info: dict, board_fen: str = None):
        """Update analysis lines with new info."""
        if board_fen:
            if self.last_board_fen != board_fen:
                self.analysis_lines.clear()
            self.last_board_fen = board_fen

        self.analysis_lines = {k: v for k, v in self.analysis_lines.items() if k <= self.multipv_limit}

        multipv = info.get("multipv", 1)
        if multipv <= self.multipv_limit:
            self.analysis_lines[multipv] = info
            
        self.render_lines()
        
        # Update top score if it's the first PV
        if multipv == 1:
            board = chess.Board(self.last_board_fen) if self.last_board_fen else None
            turn = board.turn if board else chess.WHITE
            self.set_score(self.format_score(info, raw=True, turn=turn))

    def update_analysis_batch(self, infos: list, board_fen: str = None):
        """Update multiple analysis lines and render once."""
        if board_fen:
            if self.last_board_fen != board_fen:
                self.analysis_lines.clear()
            self.last_board_fen = board_fen

        self.analysis_lines = {k: v for k, v in self.analysis_lines.items() if k <= self.multipv_limit}

        for info in infos:
            multipv = info.get("multipv", 1)
            if multipv <= self.multipv_limit:
                self.analysis_lines[multipv] = info
            
        self.render_lines()
        
        # Update top score if it's the first PV
        multipv_1_info = self.analysis_lines.get(1)
        if multipv_1_info:
            board = chess.Board(self.last_board_fen) if self.last_board_fen else None
            turn = board.turn if board else chess.WHITE
            self.set_score(self.format_score(multipv_1_info, raw=True, turn=turn))

    def reset_lines(self):
        """Clear the current analysis lines data."""
        self.analysis_lines.clear()
        if self.check_analysis.isChecked():
            self.lines_view.set_placeholder("Starting engine analysis...")
            self.score_label.setText("...")
            self.depth_label.setText("")
        else:
            self.lines_view.set_placeholder("Enable engine for analysis...")
            self.score_label.setText("")
            self.depth_label.setText("")

    def format_score_meta(self, info: dict, turn=None) -> tuple:
        """Returns (score_str, raw_numeric_value, is_mate)."""
        s_type = info.get("score_type")
        s_val = info.get("score_value", 0)
        
        if turn == chess.BLACK:
            s_val = -s_val

        if s_type == "mate":
            return (f"M{abs(s_val)}" if s_val >= 0 else f"-M{abs(s_val)}", float(s_val), True)
        else:
            score = s_val / 100.0
            prefix = "+" if score > 0 else ""
            return (f"{prefix}{score:.2f}", score, False)

    def format_score(self, info: dict, raw=False, turn=None) -> str:
        s_type = info.get("score_type")
        s_val = info.get("score_value", 0)
        
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
        self.analysis_lines.clear()
        self.lines_view.set_placeholder("Enable engine for analysis...")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AnalysisWidget()
    w.set_theme(True)
    w.resize(400, 200)
    w.show()
    sys.exit(app.exec_())
