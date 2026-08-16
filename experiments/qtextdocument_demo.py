import sys
import os
import time
import re

# Ensure project src is in path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QTextDocument, QTextBlockFormat
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QComboBox,
)

import chess.pgn

# --- Document Model (IR) Classes ---

class MoveNode:
    def __init__(self, node, move_index, nesting_level):
        self.node = node  # chess.pgn.GameNode
        self.move_index = move_index
        self.nesting_level = nesting_level
        self.comment_text = ""
        self.clk = ""
        self.eval = ""
        self.bestmove = ""
        self.parse_comment(node.comment)
        
    def parse_comment(self, comment):
        if not comment:
            return
        
        # Extract clock [%clk 0:09:54.9]
        clk_match = re.search(r'\[%clk\s+([^\]]+)\]', comment)
        if clk_match:
            self.clk = clk_match.group(1)
            
        # Extract eval [%eval +0.32]
        eval_match = re.search(r'\[%eval\s+([^\]]+)\]', comment)
        if eval_match:
            self.eval = eval_match.group(1)
            
        # Extract best move [%bestmove e4]
        best_match = re.search(r'\[%bestmove\s+([^\]]+)\]', comment)
        if best_match:
            self.bestmove = best_match.group(1)
            
        # Clean comment text by stripping out all tags
        cleaned = re.sub(r'\[%[^\]]+\]', '', comment)
        self.comment_text = cleaned.replace('{', '').replace('}', '').strip()

class VariationNode:
    def __init__(self, children, nesting_level):
        self.children = children  # List of DocNodes
        self.nesting_level = nesting_level


def build_ir_from_node(node, nesting_level, flat_nodes, ir_flat_nodes):
    elements = []
    curr = node
    while curr is not None:
        move_idx = len(flat_nodes)
        flat_nodes.append(curr)
        curr.flat_index = move_idx
        
        move_node = MoveNode(curr, move_idx, nesting_level)
        ir_flat_nodes.append(move_node)
        elements.append(move_node)
        
        # Process siblings (sidelines) branching from the parent of current
        if curr.parent:
            siblings = curr.parent.variations
            if siblings and siblings[0] == curr:
                for sibling in siblings[1:]:
                    sideline_elements = build_ir_from_node(sibling, nesting_level + 1, flat_nodes, ir_flat_nodes)
                    var_node = VariationNode(sideline_elements, nesting_level + 1)
                    elements.append(var_node)
                    
        # Proceed to next main line move
        if curr.variations:
            curr = curr.variations[0]
        else:
            curr = None
            
    return elements


# --- Subclass QTextBrowser to support Arrow Navigation ---

class KeyboardFriendlyBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.demo_window = None

    def keyPressEvent(self, event):
        if self.demo_window:
            if event.key() == Qt.Key_Right:
                self.demo_window.go_next()
                event.accept()
                return
            elif event.key() == Qt.Key_Left:
                self.demo_window.go_prev()
                event.accept()
                return
            elif event.key() == Qt.Key_Home:
                self.demo_window.go_first()
                event.accept()
                return
            elif event.key() == Qt.Key_End:
                self.demo_window.go_last()
                event.accept()
                return
        super().keyPressEvent(event)


# --- Main Application Demo Window ---

class QTextDocumentDemo(QMainWindow):
    def __init__(self, pgn_path: str):
        super().__init__()
        self.setWindowTitle("Experimental ChessBase-Style PGN Renderer (QTextDocument)")
        self.resize(1100, 750)
        
        self.pgn_path = pgn_path
        self.move_positions = {}
        self.flat_nodes = []      # Flat chess.pgn.GameNode list
        self.ir_flat_nodes = []   # Flat MoveNode (IR) list
        self.ir_elements = []     # Hierarchical DocNodes list
        self.active_index = -1
        self.prev_highlighted_index = None
        self.is_dark = True
        
        self.setup_ui()
        self.load_pgn_and_build_ir()
        self.options_changed()  # First styling and document rendering trigger
        
    def setup_ui(self):
        # Main widget & layout
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        
        # Horizontal layout: Left Sidebar (Controls) | Right Content (Moves & Nav)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        # Sidebar widget
        sidebar = QWidget(self)
        sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(12)
        
        # Sidebar Title
        sb_title = QLabel("Display Options", sidebar)
        sb_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;")
        sidebar_layout.addWidget(sb_title)
        
        # Checkboxes for display options
        self.cb_dark = QCheckBox("Dark Theme", sidebar)
        self.cb_dark.setChecked(True)
        sidebar_layout.addWidget(self.cb_dark)
        
        self.cb_comments = QCheckBox("Show Comments", sidebar)
        self.cb_comments.setChecked(True)
        sidebar_layout.addWidget(self.cb_comments)
        
        self.cb_comment_block = QCheckBox("Comments as Blocks", sidebar)
        self.cb_comment_block.setChecked(True)
        sidebar_layout.addWidget(self.cb_comment_block)
        
        self.cb_clk = QCheckBox("Show Clock [%clk]", sidebar)
        self.cb_clk.setChecked(True)
        sidebar_layout.addWidget(self.cb_clk)
        
        self.cb_eval = QCheckBox("Show Eval [%eval]", sidebar)
        self.cb_eval.setChecked(True)
        sidebar_layout.addWidget(self.cb_eval)
        
        self.cb_compact = QCheckBox("Compact Mode", sidebar)
        self.cb_compact.setChecked(False)
        sidebar_layout.addWidget(self.cb_compact)
        
        # Layout Mode Option
        sidebar_layout.addWidget(QLabel("Layout Mode:", sidebar))
        self.combo_layout = QComboBox(sidebar)
        self.combo_layout.addItem("Layout A: Move per Line")
        self.combo_layout.addItem("Layout B: ChessBase Blocks")
        self.combo_layout.setCurrentIndex(1)  # Default to Layout B
        sidebar_layout.addWidget(self.combo_layout)
        
        sidebar_layout.addStretch()
        
        # Add sidebar to main layout
        main_layout.addWidget(sidebar)
        
        # Content panel (right side)
        content_panel = QWidget(self)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        # Info labels
        self.status_label = QLabel("Loading...", self)
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        content_layout.addWidget(self.status_label)
        
        # QTextBrowser for displaying the moves
        self.browser = KeyboardFriendlyBrowser(self)
        self.browser.demo_window = self
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.on_anchor_clicked)
        content_layout.addWidget(self.browser)
        
        # Navigation bar
        nav_layout = QHBoxLayout()
        content_layout.addLayout(nav_layout)
        
        self.btn_first = QPushButton("|< First", self)
        self.btn_prev = QPushButton("< Prev", self)
        self.btn_next = QPushButton("Next >", self)
        self.btn_last = QPushButton("Last >|", self)
        
        for btn in [self.btn_first, self.btn_prev, self.btn_next, self.btn_last]:
            btn.setMinimumHeight(40)
            btn.setStyleSheet("font-size: 14px; font-weight: bold;")
            nav_layout.addWidget(btn)
            
        self.btn_first.clicked.connect(self.go_first)
        self.btn_prev.clicked.connect(self.go_prev)
        self.btn_next.clicked.connect(self.go_next)
        self.btn_last.clicked.connect(self.go_last)
        
        # Live stats layout
        self.stats_label = QLabel("Timing stats: N/A", self)
        self.stats_label.setStyleSheet("font-family: monospace; font-size: 13px;")
        content_layout.addWidget(self.stats_label)
        
        # Add content panel to main layout
        main_layout.addWidget(content_panel)
        
        # Connect checkbox changes to automatic document rebuild
        self.cb_dark.stateChanged.connect(self.options_changed)
        self.cb_comments.stateChanged.connect(self.options_changed)
        self.cb_comment_block.stateChanged.connect(self.options_changed)
        self.cb_clk.stateChanged.connect(self.options_changed)
        self.cb_eval.stateChanged.connect(self.options_changed)
        self.cb_compact.stateChanged.connect(self.options_changed)
        self.combo_layout.currentIndexChanged.connect(self.options_changed)

    def load_pgn_and_build_ir(self):
        t0 = time.perf_counter()
        
        # Read PGN from file
        with open(self.pgn_path, "r", encoding="utf-8") as f:
            self.game = chess.pgn.read_game(f)
            
        t_read = time.perf_counter() - t0
        
        # Build the Intermediate Representation (IR) tree once
        t1 = time.perf_counter()
        self.flat_nodes = []
        self.ir_flat_nodes = []
        if self.game.variations:
            first_move = self.game.variations[0]
            self.ir_elements = build_ir_from_node(first_move, 0, self.flat_nodes, self.ir_flat_nodes)
        else:
            self.ir_elements = []
            
        self.t_ir_build = time.perf_counter() - t1
        self.t_read = t_read
        
        # Select first move initially if available
        if self.flat_nodes:
            self.active_index = 0

    def options_changed(self):
        # Update styling options
        self.is_dark = self.cb_dark.isChecked()
        
        # Disable/enable sub-checkboxes based on main checkboxes
        compact = self.cb_compact.isChecked()
        self.cb_comments.setEnabled(not compact)
        self.cb_comment_block.setEnabled(not compact and self.cb_comments.isChecked())
        self.cb_clk.setEnabled(not compact)
        self.cb_eval.setEnabled(not compact)
        
        # Apply style sheets dynamically
        self.apply_theme()
        
        # Re-render document content using the current options
        self.render_document()

    def apply_theme(self):
        if self.is_dark:
            # Dark Theme Palette
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #121212;
                }
                QLabel {
                    color: #E2E2E6;
                }
                QCheckBox {
                    color: #E2E2E6;
                    font-size: 13px;
                    spacing: 8px;
                }
                QCheckBox:disabled {
                    color: #55555A;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 1px solid #3E3E4A;
                    border-radius: 3px;
                    background-color: #1E1E24;
                }
                QCheckBox::indicator:checked {
                    background-color: #BB86FC;
                    border-color: #BB86FC;
                }
                QPushButton {
                    background-color: #2C2C35;
                    color: #E0E0E0;
                    border: 1px solid #3E3E4A;
                    border-radius: 6px;
                    padding: 6px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #3E3E4A;
                }
                QPushButton:pressed {
                    background-color: #BB86FC;
                    color: #121212;
                }
                QComboBox {
                    background-color: #2C2C35;
                    color: #E0E0E0;
                    border: 1px solid #3E3E4A;
                    border-radius: 4px;
                    padding: 4px;
                    font-size: 13px;
                }
                QWidget#sidebar {
                    background-color: #18181C;
                    border-right: 1px solid #2C2C35;
                }
            """)
            self.browser.setStyleSheet("""
                QTextBrowser {
                    background-color: #121212;
                    color: #E0E0E0;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 16px;
                    line-height: 1.6;
                    border: none;
                }
            """)
            self.stats_label.setStyleSheet("font-family: monospace; font-size: 13px; color: #BB86FC;")
        else:
            # Light Theme Palette
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #FAF9F6;
                }
                QLabel {
                    color: #2C3E50;
                }
                QCheckBox {
                    color: #2C3E50;
                    font-size: 13px;
                    spacing: 8px;
                }
                QCheckBox:disabled {
                    color: #BDC3C7;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    border: 1px solid #BDC3C7;
                    border-radius: 3px;
                    background-color: #FFFFFF;
                }
                QCheckBox::indicator:checked {
                    background-color: #2980B9;
                    border-color: #2980B9;
                }
                QPushButton {
                    background-color: #EAEDED;
                    color: #2C3E50;
                    border: 1px solid #BDC3C7;
                    border-radius: 6px;
                    padding: 6px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #D5DBDB;
                }
                QPushButton:pressed {
                    background-color: #2980B9;
                    color: white;
                }
                QComboBox {
                    background-color: #FFFFFF;
                    color: #2C3E50;
                    border: 1px solid #BDC3C7;
                    border-radius: 4px;
                    padding: 4px;
                    font-size: 13px;
                }
                QWidget#sidebar {
                    background-color: #EAEDED;
                    border-right: 1px solid #BDC3C7;
                }
            """)
            self.browser.setStyleSheet("""
                QTextBrowser {
                    background-color: #FAF9F6;
                    color: #2C3E50;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 16px;
                    line-height: 1.6;
                    border: none;
                }
            """)
            self.stats_label.setStyleSheet("font-family: monospace; font-size: 13px; color: #2980B9;")

    def render_document(self):
        t0 = time.perf_counter()
        
        # Save active index
        active_idx = self.active_index
        
        # Build document and populate self.move_positions
        doc = QTextDocument(self.browser)
        self.build_document_content(doc)
        self.browser.setDocument(doc)
        
        t_render = time.perf_counter() - t0
        
        # Update loaded status
        total_moves = len(self.flat_nodes)
        self.status_label.setText(
            f"PGN loaded successfully: {total_moves} moves. "
            f"Read PGN: {self.t_read*1000.0:.1f}ms | IR Build: {self.t_ir_build*1000.0:.1f}ms | Render Doc: {t_render*1000.0:.1f}ms"
        )
        
        # Restore active move highlight and scroll
        if active_idx >= 0 and active_idx < len(self.flat_nodes):
            self.prev_highlighted_index = None  # Reset to force active highlight
            self.jump_to(active_idx)

    def generate_header_html(self, headers, is_dark):
        white = headers.get("White", "Unknown White")
        black = headers.get("Black", "Unknown Black")
        white_elo = headers.get("WhiteElo", "")
        black_elo = headers.get("BlackElo", "")
        event = headers.get("Event", "?")
        site = headers.get("Site", "?")
        date = headers.get("Date", "?")
        result = headers.get("Result", "*")
        eco = headers.get("ECO", "")
        
        white_str = f"{white} ({white_elo})" if white_elo else white
        black_str = f"{black} ({black_elo})" if black_elo else black
        
        bg = "#1E1E24" if is_dark else "#EAEDED"
        border_col = "#2C2C35" if is_dark else "#BDC3C7"
        title_col = "#FFFFFF" if is_dark else "#2C3E50"
        subtitle_col = "#9E9E9E" if is_dark else "#7F8C8D"
        result_col = "#BB86FC" if is_dark else "#2980B9"
        
        html = f"""
        <table width="100%" style="background-color: {bg}; border: 1px solid {border_col}; margin-bottom: 10px;">
          <tr>
            <td style="padding: 15px; font-family: 'Segoe UI', Arial;">
              <div style="font-size: 20px; font-weight: bold; color: {title_col};">
                {white_str} <span style="color: {result_col};">vs</span> {black_str}
              </div>
              <div style="font-size: 13px; color: {subtitle_col}; margin-top: 6px;">
                <b>Event:</b> {event} | <b>Site:</b> {site} | <b>Date:</b> {date} | <b>Result:</b> {result} {f'| <b>ECO:</b> {eco}' if eco else ''}
              </div>
            </td>
          </tr>
        </table>
        """
        return html

    def insert_comment_block(self, cursor, text, is_dark, indent=0):
        bg = "#1A1D20" if is_dark else "#F2F4F4"
        border_col = "#03DAC6" if is_dark else "#16A085"
        text_col = "#B0BEC5" if is_dark else "#34495E"
        margin_left = f"margin-left: {indent}px;" if indent > 0 else ""
        
        html = f"""
        <table width="100%" style="background-color: {bg}; border-left: 4px solid {border_col}; margin-top: 5px; margin-bottom: 5px; {margin_left}">
          <tr>
            <td style="padding: 8px; color: {text_col}; font-family: 'Segoe UI', Arial; font-size: 14px; font-style: italic;">
              {text}
            </td>
          </tr>
        </table>
        """
        cursor.insertHtml(html)

    def get_move_format(self, level):
        fmt = QTextCharFormat()
        fmt.setFontFamily("Segoe UI")
        font_size = 14 if self.cb_compact.isChecked() else 15
        fmt.setFontPointSize(font_size)
        
        # Color coding based on hierarchy level (Mainline vs Variation)
        if level == 0:
            fmt.setFontWeight(QFont.Bold)
            fmt.setForeground(QColor("#BB86FC" if self.is_dark else "#1A252C"))
        else:
            # All variations get same gray color
            fmt.setForeground(QColor("#8A8A93" if self.is_dark else "#7F8C8D"))
            
        fmt.setAnchor(True)
        return fmt

    def format_eval(self, eval_str, is_dark):
        if not eval_str:
            return ""
        try:
            if '#' in eval_str:
                val = 99.0 if '-' not in eval_str else -99.0
            else:
                val = float(eval_str)
            if val > 0.1:
                color = "#81C784" if is_dark else "#2E7D32"
            elif val < -0.1:
                color = "#E57373" if is_dark else "#C62828"
            else:
                color = "#B0BEC5" if is_dark else "#78909C"
        except ValueError:
            color = "#B0BEC5" if is_dark else "#78909C"
            
        return f'<span style="color: {color}; font-weight: bold; font-size: 13px;">[{eval_str}]</span>'

    def format_clk(self, clk_str, is_dark):
        if not clk_str:
            return ""
        color = "#FFB74D" if is_dark else "#EF6C00"
        return f'<span style="color: {color}; font-size: 13px;">🕒 {clk_str}</span>'

    def build_document_content(self, doc: QTextDocument):
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        
        self.move_positions = {}
        
        is_dark = self.is_dark
        show_comments = self.cb_comments.isChecked() if self.cb_comments.isEnabled() else False
        comment_as_block = self.cb_comment_block.isChecked() if self.cb_comment_block.isEnabled() else False
        show_clk = self.cb_clk.isChecked() if self.cb_clk.isEnabled() else False
        show_eval = self.cb_eval.isChecked() if self.cb_eval.isEnabled() else False
        compact_mode = self.cb_compact.isChecked()
        layout_mode = self.combo_layout.currentIndex()  # 0 = Layout A, 1 = Layout B
        
        # Define text styles
        normal_format = QTextCharFormat()
        normal_format.setFontFamily("Segoe UI")
        normal_format.setFontPointSize(14 if compact_mode else 15)
        normal_format.setForeground(QColor("#E0E0E0" if is_dark else "#2C3E50"))
        
        num_format = QTextCharFormat(normal_format)
        num_format.setForeground(QColor("#8A8A93" if is_dark else "#7F8C8D"))
        num_format.setFontWeight(QFont.Bold)
        
        p_format = QTextBlockFormat()
        p_format.setTopMargin(4 if compact_mode else 8)
        p_format.setBottomMargin(4 if compact_mode else 8)
        p_format.setLineHeight(130 if compact_mode else 145, QTextBlockFormat.ProportionalHeight)
        
        # 1. Title/Header block
        header_html = self.generate_header_html(self.game.headers, is_dark)
        cursor.insertHtml(header_html)
        
        # Add basic spacing
        cursor.insertBlock(p_format)
        
        # 2. Initial game comments (if any)
        if self.game.comment and show_comments:
            self.insert_comment_block(cursor, self.game.comment, is_dark, indent=0)
            cursor.insertBlock(p_format)
            
        # 3. Moves Rendering
        if layout_mode == 0:
            # --- Layout A: Move per line ---
            state = {
                "active_level": -1,
                "has_white": False,
            }
            
            def render_layout_a(elements, level):
                for element in elements:
                    if isinstance(element, MoveNode):
                        board = element.node.parent.board()
                        move_num = board.fullmove_number
                        san = board.san(element.node.move)
                        
                        # Decide if we need a new line/paragraph
                        if board.turn == chess.WHITE or state["active_level"] != level or not state["has_white"]:
                            p_fmt = QTextBlockFormat(p_format)
                            if level > 0:
                                p_fmt.setLeftMargin(level * 20)
                                if is_dark:
                                    p_fmt.setBackground(QColor("#1A1D20"))
                                else:
                                    p_fmt.setBackground(QColor("#F0F4F4"))
                            cursor.insertBlock(p_fmt)
                            
                            prefix = f"{move_num}. " if board.turn == chess.WHITE else f"{move_num}... "
                            cursor.insertText(prefix, num_format)
                            state["has_white"] = (board.turn == chess.WHITE)
                            state["active_level"] = level
                        else:
                            state["has_white"] = False
                            
                        # Move anchor
                        move_fmt = self.get_move_format(level)
                        move_fmt.setAnchorHref(f"move({element.move_index})")
                        move_fmt.setAnchorNames([f"move({element.move_index})"])
                        
                        start_pos = cursor.position()
                        cursor.insertText(san, move_fmt)
                        end_pos = cursor.position()
                        
                        self.move_positions[element.move_index] = (start_pos, end_pos)
                        cursor.insertText(" ", normal_format)
                        
                        # Clock/Eval badges
                        ann_parts = []
                        if show_eval and element.eval:
                            ann_parts.append(self.format_eval(element.eval, is_dark))
                        if show_clk and element.clk:
                            ann_parts.append(self.format_clk(element.clk, is_dark))
                        if ann_parts:
                            cursor.insertHtml(" ".join(ann_parts) + " ")
                            cursor.setCharFormat(normal_format)
                            
                        # Comment
                        if show_comments and element.comment_text:
                            if comment_as_block:
                                self.insert_comment_block(cursor, element.comment_text, is_dark, indent=level * 20)
                                state["has_white"] = False
                            else:
                                comment_fmt = QTextCharFormat(normal_format)
                                comment_fmt.setForeground(QColor("#03DAC6" if is_dark else "#16A085"))
                                comment_fmt.setFontItalic(True)
                                cursor.insertText(f"{{{element.comment_text}}} ", comment_fmt)
                                state["has_white"] = False
                                
                    elif isinstance(element, VariationNode):
                        state["has_white"] = False
                        render_layout_a(element.children, level + 1)
                        state["has_white"] = False
                        
            render_layout_a(self.ir_elements, 0)
            
        else:
            # --- Layout B: ChessBase Blocks ---
            state = {
                "in_para": False,
                "need_num_prefix": True,
            }
            
            def render_layout_b(elements, level):
                for element in elements:
                    if isinstance(element, MoveNode):
                        board = element.node.parent.board()
                        move_num = board.fullmove_number
                        san = board.san(element.node.move)
                        
                        # 1. Start block if not currently in one
                        if not state["in_para"]:
                            p_fmt = QTextBlockFormat(p_format)
                            if level > 0:
                                p_fmt.setLeftMargin(20)  # Indent variation block
                                if is_dark:
                                    p_fmt.setBackground(QColor("#1A1D20"))
                                else:
                                    p_fmt.setBackground(QColor("#F0F4F4"))
                            cursor.insertBlock(p_fmt)
                            
                            # Prefix with variation opening bracket
                            if level > 0:
                                paren_fmt = QTextCharFormat(normal_format)
                                paren_fmt.setForeground(QColor("#8A8A93" if is_dark else "#7F8C8D"))
                                cursor.insertText("[ ", paren_fmt)
                                
                            state["in_para"] = True
                            state["need_num_prefix"] = True
                            
                        # 2. Append Move Prefix
                        if board.turn == chess.WHITE:
                            if state["need_num_prefix"]:
                                cursor.insertText(f"{move_num}. ", num_format)
                                state["need_num_prefix"] = False
                            elif level == 0:
                                cursor.insertText(f"{move_num}. ", num_format)
                        else:
                            if state["need_num_prefix"]:
                                cursor.insertText(f"{move_num}... ", num_format)
                                state["need_num_prefix"] = False
                                
                        # 3. Write Move Anchor
                        move_fmt = self.get_move_format(level)
                        move_fmt.setAnchorHref(f"move({element.move_index})")
                        move_fmt.setAnchorNames([f"move({element.move_index})"])
                        
                        start_pos = cursor.position()
                        cursor.insertText(san, move_fmt)
                        end_pos = cursor.position()
                        
                        self.move_positions[element.move_index] = (start_pos, end_pos)
                        cursor.insertText(" ", normal_format)
                        
                        # 4. Badges
                        ann_parts = []
                        if show_eval and element.eval:
                            ann_parts.append(self.format_eval(element.eval, is_dark))
                        if show_clk and element.clk:
                            ann_parts.append(self.format_clk(element.clk, is_dark))
                        if ann_parts:
                            cursor.insertHtml(" ".join(ann_parts) + " ")
                            cursor.setCharFormat(normal_format)
                            
                        # 5. Handle Comment
                        if show_comments and element.comment_text:
                            if level == 0:
                                # Close main line block, insert comment block card
                                if state["in_para"]:
                                    state["in_para"] = False
                                self.insert_comment_block(cursor, element.comment_text, is_dark, indent=0)
                                state["need_num_prefix"] = True
                            else:
                                # Variation: inline comment
                                comment_fmt = QTextCharFormat(normal_format)
                                comment_fmt.setForeground(QColor("#03DAC6" if is_dark else "#16A085"))
                                comment_fmt.setFontItalic(True)
                                cursor.insertText(f"{{{element.comment_text}}} ", comment_fmt)
                                state["need_num_prefix"] = True
                                
                    elif isinstance(element, VariationNode):
                        if level == 0:
                            # Close main line block
                            if state["in_para"]:
                                state["in_para"] = False
                                
                            # Recurse variation block level 1
                            render_layout_b(element.children, 1)
                            
                            # Close variation block with bracket
                            if state["in_para"]:
                                paren_fmt = QTextCharFormat(normal_format)
                                paren_fmt.setForeground(QColor("#8A8A93" if is_dark else "#7F8C8D"))
                                cursor.insertText("] ", paren_fmt)
                                state["in_para"] = False
                                
                            state["need_num_prefix"] = True
                        else:
                            # Nested variation inside existing variation block: wrap in parentheses ()
                            paren_fmt = QTextCharFormat(normal_format)
                            paren_fmt.setForeground(QColor("#8A8A93" if is_dark else "#7F8C8D"))
                            cursor.insertText("( ", paren_fmt)
                            
                            render_layout_b(element.children, level + 1)
                            
                            cursor.insertText(") ", paren_fmt)
                            state["need_num_prefix"] = True
                            
            render_layout_b(self.ir_elements, 0)
            
        cursor.endEditBlock()

    def jump_to(self, index: int):
        if not self.flat_nodes or index < 0 or index >= len(self.flat_nodes):
            return
            
        t0 = time.perf_counter()
        
        prev_idx = self.prev_highlighted_index
        new_idx = index
        self.active_index = index
        self.prev_highlighted_index = index
        
        doc = self.browser.document()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        
        # 1. Reset previous active move highlight to its original format
        if prev_idx is not None and prev_idx in self.move_positions:
            start, end = self.move_positions[prev_idx]
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            
            node_level = self.ir_flat_nodes[prev_idx].nesting_level
            orig_fmt = self.get_move_format(node_level)
            cursor.setCharFormat(orig_fmt)
            
        # 2. Apply new active move highlight (Teal color)
        if new_idx in self.move_positions:
            start, end = self.move_positions[new_idx]
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            
            node_level = self.ir_flat_nodes[new_idx].nesting_level
            fmt = self.get_move_format(node_level)
            
            # semi-dark teal background highlight
            highlight_color = QColor("#004D40" if self.is_dark else "#B2DFDB")
            fmt.setBackground(highlight_color)
            
            # contrasting text color
            text_color = QColor("#E0F7FA" if self.is_dark else "#004D40")
            fmt.setForeground(text_color)
            
            cursor.setCharFormat(fmt)
            
        cursor.endEditBlock()
        
        # 3. Scroll to make the active move centered in the viewport
        if new_idx in self.move_positions:
            start, _ = self.move_positions[new_idx]
            cursor.setPosition(start)
            rect = self.browser.cursorRect(cursor)
            scrollbar = self.browser.verticalScrollBar()
            viewport_h = self.browser.viewport().height()
            target_value = scrollbar.value() + rect.top() - viewport_h // 2
            scrollbar.setValue(target_value)
        
        t_high = time.perf_counter() - t0
        
        # Show status and active node metrics
        active_node = self.flat_nodes[new_idx]
        board = active_node.parent.board()
        move_name = f"{board.fullmove_number}.{board.san(active_node.move)}" if board.turn == chess.WHITE else f"{board.fullmove_number}...{board.san(active_node.move)}"
        self.stats_label.setText(
            f"Active Move: {move_name} (Index: {new_idx}) | "
            f"Highlight Action Time: {t_high*1000.0:.3f} ms"
        )

    def on_anchor_clicked(self, url):
        href = url.toString()
        match = re.match(r"move\((\d+)\)", href)
        if match:
            idx = int(match.group(1))
            self.jump_to(idx)

    def go_first(self):
        self.jump_to(0)

    def go_last(self):
        self.jump_to(len(self.flat_nodes) - 1)

    def go_next(self):
        self.jump_to(min(len(self.flat_nodes) - 1, self.active_index + 1))

    def go_prev(self):
        self.jump_to(max(0, self.active_index - 1))


if __name__ == "__main__":
    app = QApplication([])
    
    pgn_file = r"C:\Users\ASUS\programming\qt_programs\chess\pgn_tests\long_game.pgn"
    if not os.path.exists(pgn_file):
        print(f"ERROR: File not found: {pgn_file}")
        sys.exit(1)
        
    demo = QTextDocumentDemo(pgn_file)
    demo.show()
    sys.exit(app.exec_())
