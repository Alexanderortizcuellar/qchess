# game_analytics.py
import re
import chess
import chess.pgn
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont, QPainterPath, QLinearGradient
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTabWidget


class EvaluationChart(QWidget):
    clickedIndex = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.data = []  # list of floats (evaluations)
        self.labels = [] # list of strings (move labels)
        self.classifications = [] # list of classifications
        self.highlight_index = -1
        self.hover_index = -1
        self.is_dark = True
        self._cp_scale = 300.0
        
    def set_theme(self, is_dark):
        self.is_dark = is_dark
        self.update()
        
    def update_data(self, evals, labels, highlight_index, classifications=None):
        self.data = evals
        self.labels = labels
        self.highlight_index = highlight_index
        self.classifications = classifications if classifications is not None else []
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.handle_mouse_event(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.handle_mouse_event(event)
        else:
            self.handle_hover(event)
            
    def leaveEvent(self, event):
        self.hover_index = -1
        self.update()
        
    def handle_mouse_event(self, event):
        if not self.data:
            return
        
        W = self.width()
        left_pad = 40
        right_pad = 15
        pw = W - left_pad - right_pad
        if pw <= 0:
            return
            
        N = len(self.data)
        max_dx = 50.0
        dx = pw / (N - 1) if N > 1 else pw
        if dx > max_dx:
            dx = max_dx
            pw = dx * (N - 1)
            left_pad = left_pad + (W - left_pad - right_pad - pw) / 2.0
            
        x = event.x() - left_pad
        if N <= 1:
            idx = 0
        else:
            idx = round(x / dx)
            idx = max(0, min(N - 1, idx))
            
        self.clickedIndex.emit(idx)
        
    def handle_hover(self, event):
        if not self.data:
            return
        W = self.width()
        left_pad = 40
        right_pad = 15
        pw = W - left_pad - right_pad
        if pw <= 0:
            return
            
        N = len(self.data)
        max_dx = 50.0
        dx = pw / (N - 1) if N > 1 else pw
        if dx > max_dx:
            dx = max_dx
            pw = dx * (N - 1)
            left_pad = left_pad + (W - left_pad - right_pad - pw) / 2.0
            
        x = event.x() - left_pad
        if N <= 1:
            idx = 0
        else:
            idx = round(x / dx)
            idx = max(0, min(N - 1, idx))
        if idx != self.hover_index:
            self.hover_index = idx
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        W = self.width()
        H = self.height()
        left_pad = 40
        right_pad = 15
        top_pad = 15
        bottom_pad = 20
        
        pw = W - left_pad - right_pad
        ph = H - top_pad - bottom_pad
        
        # Limit vertical height of chart so it doesn't stretch infinitely
        max_chart_height = 320.0
        actual_ph = min(ph, max_chart_height)
        top_pad = top_pad + (ph - actual_ph) / 2.0
        ph = actual_ph
        
        bg_color = QColor("#262421") if self.is_dark else QColor("#ffffff")
        grid_color = QColor("#3a3835") if self.is_dark else QColor("#e0e0e0")
        text_color = QColor("#8b8987") if self.is_dark else QColor("#666666")
        line_color = QColor("#BB86FC") if self.is_dark else QColor("#312e2b")
        cursor_color = QColor("#03DAC6") if self.is_dark else QColor("#2670e8")
        
        painter.fillRect(self.rect(), bg_color)
        
        baseline_y = top_pad + ph / 2.0
        
        if pw <= 0 or ph <= 0:
            return
            
        N = len(self.data)
        if N < 2:
            # Draw a baseline and return if no data
            painter.setPen(QPen(grid_color, 1, Qt.SolidLine))
            painter.drawLine(left_pad, int(baseline_y), W - right_pad, int(baseline_y))
            painter.setPen(text_color)
            painter.drawText(left_pad + 10, int(baseline_y) - 10, "No move evaluations found")
            return
            
        # Limit horizontal spacing if N is small to avoid stretching over huge screen
        max_dx = 50.0
        dx = pw / (N - 1)
        if dx > max_dx:
            dx = max_dx
            pw = dx * (N - 1)
            left_pad = left_pad + (W - left_pad - right_pad - pw) / 2.0
            
        # Draw grid and labels
        # Y range is clamped to [-8.0, 8.0]
        grid_values = [6.0, 3.0, 0.0, -3.0, -6.0]
        painter.setFont(QFont("Arial", 8))
        for gv in grid_values:
            y = top_pad + ph / 2.0 - (gv / 8.0) * (ph / 2.0)
            if gv == 0.0:
                painter.setPen(QPen(grid_color, 1.5, Qt.SolidLine))
            else:
                grid_pen_color = QColor(grid_color)
                grid_pen_color.setAlpha(100)  # faint grid lines
                painter.setPen(QPen(grid_pen_color, 1, Qt.DashLine))
                
            painter.drawLine(int(left_pad), int(y), int(left_pad + pw), int(y))
            
            painter.setPen(text_color)
            sign = "+" if gv > 0 else ""
            label_text = f"{sign}{gv:.1f}" if gv != 0.0 else "0.0"
            painter.drawText(5, int(y) + 4, label_text)
            
        # Calculate coordinates for each point
        points = []
        for i, val in enumerate(self.data):
            clamped = max(-8.0, min(8.0, val))
            x = left_pad + i * dx
            y = top_pad + ph / 2.0 - (clamped / 8.0) * (ph / 2.0)
            points.append(QPointF(x, y))
            
        # Draw soft gradient fills (white over line, black under line)
        # Positive fill (above baseline)
        painter.save()
        painter.setClipRect(QRectF(left_pad, top_pad, pw, baseline_y - top_pad))
        pos_path = QPainterPath()
        pos_path.moveTo(left_pad, baseline_y)
        for pt in points:
            pos_path.lineTo(pt)
        pos_path.lineTo(points[-1].x(), baseline_y)
        pos_path.closeSubpath()
        
        pos_grad = QLinearGradient(0, top_pad, 0, baseline_y)
        pos_grad.setColorAt(0.0, QColor(255, 255, 255, 120) if self.is_dark else QColor(255, 255, 255, 180))
        pos_grad.setColorAt(1.0, QColor(255, 255, 255, 10) if self.is_dark else QColor(255, 255, 255, 20))
        painter.fillPath(pos_path, QBrush(pos_grad))
        painter.restore()
        
        # Negative fill (below baseline)
        painter.save()
        painter.setClipRect(QRectF(left_pad, baseline_y, pw, top_pad + ph - baseline_y))
        neg_path = QPainterPath()
        neg_path.moveTo(left_pad, baseline_y)
        for pt in points:
            neg_path.lineTo(pt)
        neg_path.lineTo(points[-1].x(), baseline_y)
        neg_path.closeSubpath()
        
        neg_grad = QLinearGradient(0, baseline_y, 0, top_pad + ph)
        neg_grad.setColorAt(0.0, QColor(0, 0, 0, 20) if self.is_dark else QColor(0, 0, 0, 10))
        neg_grad.setColorAt(1.0, QColor(0, 0, 0, 160) if self.is_dark else QColor(0, 0, 0, 100))
        painter.fillPath(neg_path, QBrush(neg_grad))
        painter.restore()
        
        # Draw path
        path = QPainterPath()
        path.moveTo(points[0])
        for pt in points[1:]:
            path.lineTo(pt)
        painter.setPen(QPen(line_color, 2, Qt.SolidLine))
        painter.drawPath(path)
        
        # Draw classification markers
        CLASSIFICATION_COLORS = {
            4: QColor("#FFD54F"),  # Inaccuracy
            5: QColor("#FF9800"),  # Mistake
            6: QColor("#E53935"),  # Blunder
            8: QColor("#FF8A80"),  # Miss
        }
        if hasattr(self, "classifications") and self.classifications:
            for i, pt in enumerate(points):
                if i < len(self.classifications):
                    cls = self.classifications[i]
                    if cls in CLASSIFICATION_COLORS:
                        painter.setBrush(CLASSIFICATION_COLORS[cls])
                        pen_col = QColor("#ffffff") if self.is_dark else QColor("#000000")
                        painter.setPen(QPen(pen_col, 1))
                        painter.drawEllipse(pt, 4, 4)
        
        # Draw cursor
        if 0 <= self.highlight_index < N:
            pt = points[self.highlight_index]
            painter.setPen(QPen(cursor_color, 1.5, Qt.SolidLine))
            painter.drawLine(int(pt.x()), int(top_pad), int(pt.x()), int(top_pad + ph))
            
            painter.setBrush(cursor_color)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(pt, 5, 5)
            
        # Draw hover state
        active_hover = self.hover_index if self.hover_index != -1 else (self.highlight_index if self.highlight_index != -1 else -1)
        if 0 <= active_hover < N:
            pt = points[active_hover]
            if self.hover_index != -1 and self.hover_index != self.highlight_index:
                painter.setPen(QPen(text_color, 1, Qt.DashLine))
                painter.drawLine(int(pt.x()), int(top_pad), int(pt.x()), int(top_pad + ph))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(pt, 4, 4)
                
            val = self.data[active_hover]
            lbl = self.labels[active_hover]
            sign = "+" if val > 0 else ""
            txt = f"{lbl} | Eval: {sign}{val:.2f}"
            
            painter.setPen(text_color)
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(int(left_pad) + 10, int(top_pad) + 15, txt)


class ClockChart(QWidget):
    clickedIndex = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.data = []  # list of floats (time spent on each ply)
        self.turns = [] # list of bools (True for White, False for Black)
        self.labels = []
        self.highlight_index = -1
        self.hover_index = -1
        self.is_dark = True
        
    def set_theme(self, is_dark):
        self.is_dark = is_dark
        self.update()
        
    def update_data(self, spent, turns, labels, highlight_index):
        self.data = spent
        self.turns = turns
        self.labels = labels
        self.highlight_index = highlight_index
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.handle_mouse_event(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.handle_mouse_event(event)
        else:
            self.handle_hover(event)
            
    def leaveEvent(self, event):
        self.hover_index = -1
        self.update()
        
    def handle_mouse_event(self, event):
        if not self.data:
            return
        
        W = self.width()
        left_pad = 40
        right_pad = 15
        pw = W - left_pad - right_pad
        if pw <= 0:
            return
            
        N = len(self.data)
        max_dx = 50.0
        dx = pw / (N - 1) if N > 1 else pw
        if dx > max_dx:
            dx = max_dx
            pw = dx * (N - 1)
            left_pad = left_pad + (W - left_pad - right_pad - pw) / 2.0
            
        x = event.x() - left_pad
        if N <= 1:
            idx = 0
        else:
            idx = round(x / dx)
            idx = max(0, min(N - 1, idx))
            
        self.clickedIndex.emit(idx)
        
    def handle_hover(self, event):
        if not self.data:
            return
        W = self.width()
        left_pad = 40
        right_pad = 15
        pw = W - left_pad - right_pad
        if pw <= 0:
            return
            
        N = len(self.data)
        max_dx = 50.0
        dx = pw / (N - 1) if N > 1 else pw
        if dx > max_dx:
            dx = max_dx
            pw = dx * (N - 1)
            left_pad = left_pad + (W - left_pad - right_pad - pw) / 2.0
            
        x = event.x() - left_pad
        if N <= 1:
            idx = 0
        else:
            idx = round(x / dx)
            idx = max(0, min(N - 1, idx))
        if idx != self.hover_index:
            self.hover_index = idx
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        W = self.width()
        H = self.height()
        left_pad = 40
        right_pad = 15
        top_pad = 15
        bottom_pad = 20
        
        pw = W - left_pad - right_pad
        ph = H - top_pad - bottom_pad
        
        # Limit vertical height of chart so it doesn't stretch infinitely
        max_chart_height = 320.0
        actual_ph = min(ph, max_chart_height)
        top_pad = top_pad + (ph - actual_ph) / 2.0
        ph = actual_ph
        
        bg_color = QColor("#262421") if self.is_dark else QColor("#ffffff")
        grid_color = QColor("#3a3835") if self.is_dark else QColor("#e0e0e0")
        text_color = QColor("#8b8987") if self.is_dark else QColor("#666666")
        
        white_bar_color = QColor("#e0e0e0") if self.is_dark else QColor("#424242")
        black_bar_color = QColor("#BB86FC") if self.is_dark else QColor("#2670e8")
        
        highlight_color = QColor("#03DAC6") if self.is_dark else QColor("#d32f2f")
        hover_color = QColor("#00E676") if self.is_dark else QColor("#388E3C")
        
        painter.fillRect(self.rect(), bg_color)
        
        baseline_y = top_pad + ph / 2.0
        
        if pw <= 0 or ph <= 0:
            return
            
        if not self.data:
            # Draw baseline if empty
            painter.setPen(QPen(grid_color, 1, Qt.SolidLine))
            painter.drawLine(left_pad, int(baseline_y), W - right_pad, int(baseline_y))
            painter.setPen(text_color)
            painter.drawText(left_pad + 10, int(baseline_y) - 10, "No move times found")
            return
            
        N = len(self.data)
        if N < 2:
            painter.setPen(QPen(grid_color, 1, Qt.SolidLine))
            painter.drawLine(left_pad, int(baseline_y), W - right_pad, int(baseline_y))
            painter.setPen(text_color)
            painter.drawText(left_pad + 10, int(baseline_y) - 10, "Not enough moves to chart clock")
            return
            
        # Limit horizontal spacing if N is small to avoid stretching over huge screen
        max_dx = 50.0
        dx = pw / (N - 1)
        if dx > max_dx:
            dx = max_dx
            pw = dx * (N - 1)
            left_pad = left_pad + (W - left_pad - right_pad - pw) / 2.0
            
        max_spent = max(max(self.data), 5.0)
        
        # Draw grid lines (2 above baseline, 2 below baseline)
        y_levels = [max_spent, max_spent / 2.0, -max_spent / 2.0, -max_spent]
        painter.setFont(QFont("Arial", 8))
        for gv in y_levels:
            y = baseline_y - (gv / max_spent) * (ph / 2.0)
            painter.setPen(QPen(grid_color, 1, Qt.DashLine))
            painter.drawLine(int(left_pad), int(y), int(left_pad + pw), int(y))
            
            label_text = f"{abs(gv):.1f}s"
            painter.setPen(text_color)
            painter.drawText(5, int(y) + 4, label_text)
            
        # Draw middle baseline (0s)
        painter.setPen(QPen(grid_color, 1.5, Qt.SolidLine))
        painter.drawLine(int(left_pad), int(baseline_y), int(left_pad + pw), int(baseline_y))
        painter.setPen(text_color)
        painter.drawText(5, int(baseline_y) + 4, "0s")
        
        # Determine bar width dynamically to fill the space nicely without gaps
        bar_width = max(3.0, 0.9 * dx)
        
        # Draw bars
        for i in range(N):
            spent = self.data[i]
            is_white = self.turns[i]
            
            h_bar = (spent / max_spent) * (ph / 2.0)
            x = left_pad + i * dx
            
            if is_white:
                rect = QRectF(x - bar_width / 2.0, baseline_y - h_bar, bar_width, h_bar)
            else:
                rect = QRectF(x - bar_width / 2.0, baseline_y, bar_width, h_bar)
                
            if i == self.highlight_index:
                color = highlight_color
            elif i == self.hover_index:
                color = hover_color
            else:
                color = white_bar_color if is_white else black_bar_color
                
            painter.fillRect(rect, color)
            
        # Draw active hover line / tooltip
        active_hover = self.hover_index if self.hover_index != -1 else (self.highlight_index if self.highlight_index != -1 else -1)
        if 0 <= active_hover < N:
            cx = left_pad + active_hover * dx
            if self.hover_index != -1 and self.hover_index != self.highlight_index:
                painter.setPen(QPen(text_color, 1, Qt.DashLine))
                painter.drawLine(int(cx), int(top_pad), int(cx), int(top_pad + ph))
                
            spent = self.data[active_hover]
            lbl = self.labels[active_hover]
            is_white = self.turns[active_hover]
            player = "White" if is_white else "Black"
            
            txt = f"{lbl} | {player} spent {spent:.1f}s"
            painter.setPen(text_color)
            painter.setFont(QFont("Arial", 9, QFont.Bold))
            painter.drawText(int(left_pad) + 10, int(top_pad) + 15, txt)


class GameAnalytics(QWidget):
    moveIndexRequested = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        
        self.eval_chart = EvaluationChart(self)
        self.clock_chart = ClockChart(self)
        
        self.tabs.addTab(self.eval_chart, "Evaluation Curve")
        self.tabs.addTab(self.clock_chart, "Move Times")
        
        self.layout.addWidget(self.tabs)
        
        self.eval_chart.clickedIndex.connect(self.on_chart_clicked)
        self.clock_chart.clickedIndex.connect(self.on_chart_clicked)
        
        self.path_nodes = []
        self.set_theme(True)

    def set_theme(self, is_dark):
        self.eval_chart.set_theme(is_dark)
        self.clock_chart.set_theme(is_dark)
        
        style = f"""
        QTabWidget::pane {{
            border: none;
            background: {"#262421" if is_dark else "#ffffff"};
        }}
        QTabBar::tab {{
            background: {"#1e1e1e" if is_dark else "#f0f0f0"};
            color: {"#8b8987" if is_dark else "#555555"};
            padding: 6px 12px;
            font-weight: bold;
            font-size: 11px;
            border: none;
        }}
        QTabBar::tab:selected {{
            background: {"#262421" if is_dark else "#ffffff"};
            color: {"#ffffff" if is_dark else "#000000"};
            border-bottom: 2px solid {"#BB86FC" if is_dark else "#2670e8"};
        }}
        """
        self.tabs.setStyleSheet(style)

    def on_chart_clicked(self, idx):
        if 0 <= idx < len(self.path_nodes):
            node = self.path_nodes[idx]
            self.moveIndexRequested.emit(node.flat_index)

    def update_data(self, game, current_node):
        if not game:
            self.path_nodes = []
            self.eval_chart.update_data([], [], -1)
            self.clock_chart.update_data([], [], [], -1)
            return

        # Get mainline nodes only (always from game start to end of first variation branch)
        path = []
        curr = game
        while curr.variations:
            curr = curr.variations[0]
            if curr.move is not None:
                path.append(curr)
                
        # Find highlight index (either current_node or its closest mainline ancestor)
        highlight_index = -1
        curr = current_node
        while curr and curr != game:
            if curr in path:
                highlight_index = path.index(curr)
                break
            curr = curr.parent
            
        # Parse TimeControl increment
        time_control = game.headers.get("TimeControl", "")
        increment = 0.0
        tc_match = re.search(r'\+(\d+)', time_control)
        if tc_match:
            increment = float(tc_match.group(1))
            
        # Parse data out of nodes
        evals = []
        time_spent_list = []
        turns = []
        labels = []
        classifications = []
        
        last_eval = 0.0
        
        # Locate first clock time to initialize starting clocks
        first_clk = 600.0
        for node in path:
            comment = node.comment
            clk_match = re.search(r'\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]', comment)
            if clk_match:
                h, m, s = clk_match.group(1), clk_match.group(2), clk_match.group(3)
                first_clk = int(h) * 3600 + int(m) * 60 + float(s)
                break
                
        last_white_clk = first_clk
        last_black_clk = first_clk
        
        # Single board instance to track move validation and labels incrementally
        board = game.board()
        
        for i, node in enumerate(path):
            comment = node.comment
            
            # Form Label
            move_san = board.san(node.move)
            move_num = board.fullmove_number
            turn = board.turn
            turns.append(turn)
            
            if turn == chess.WHITE:
                lbl = f"{move_num}.{move_san}"
            else:
                lbl = f"{move_num}...{move_san}"
            labels.append(lbl)
            
            board.push(node.move)
            
            # Eval
            eval_val = None
            eval_match = re.search(r'\[%eval\s+([+-]?\d+(?:\.\d+)?|#?[+-]?\d+)\]', comment)
            if eval_match:
                eval_str = eval_match.group(1)
                if eval_str.startswith('#'):
                    mate_val = int(eval_str[1:])
                    eval_val = 15.0 if mate_val > 0 else -15.0
                else:
                    eval_val = float(eval_str)
                    
            if eval_val is None:
                eval_val = last_eval
            else:
                last_eval = eval_val
            evals.append(eval_val)
            
            # Classification
            cls_val = None
            if comment:
                alz_match = re.search(r'\[%alz\s+([^\]]+)\]', comment)
                if alz_match:
                    cls_tokens = alz_match.group(1).split()
                    for token in cls_tokens:
                        if token.startswith("cls="):
                            try:
                                cls_val = int(token.split("=")[1])
                            except ValueError:
                                pass
            classifications.append(cls_val)
            
            # Clock / Time spent
            clk_val = None
            clk_match = re.search(r'\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]', comment)
            time_spent = 0.0
            if clk_match:
                h, m, s = clk_match.group(1), clk_match.group(2), clk_match.group(3)
                clk_val = int(h) * 3600 + int(m) * 60 + float(s)
                
                is_first_move = (i < 2)
                inc = 0.0 if is_first_move else increment
                
                if turn == chess.WHITE:
                    time_spent = max(0.0, last_white_clk + inc - clk_val)
                    last_white_clk = clk_val
                else:
                    time_spent = max(0.0, last_black_clk + inc - clk_val)
                    last_black_clk = clk_val
            
            time_spent_list.append(time_spent)
            
        self.path_nodes = path
        self.eval_chart.update_data(evals, labels, highlight_index, classifications)
        self.clock_chart.update_data(time_spent_list, turns, labels, highlight_index)
