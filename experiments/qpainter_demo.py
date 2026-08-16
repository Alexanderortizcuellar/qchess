import sys
import os
import time
import re

# Ensure project src is in path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QColor, QFont, QPainter, QFontMetrics, QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QComboBox,
    QShortcut,
)

import chess.pgn

# --- Structured Layout Blocks for QPainter ---

class PaintBlock:
    def __init__(self, level):
        self.level = level
        self.tokens = []

class Token:
    def __init__(self, token_type, text, move_idx=-1, level=0):
        self.token_type = token_type
        self.text = text
        self.move_idx = move_idx
        self.level = level
        self.rect = None


# --- Custom Paint Widget ---

class QPainterBrowser(QWidget):
    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser
        self.blocks = []
        self.line_height = 30
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        
    def set_blocks(self, blocks):
        self.blocks = blocks
        self.update_size()
        self.update()
        
    def update_size(self):
        self.setMinimumHeight(len(self.blocks) * self.line_height * 2 + 100)
        self.setMinimumWidth(800)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        is_dark = self.parent_browser.is_dark
        active_index = self.parent_browser.active_index
        width = self.width() - 30  # Margin bounds
        
        # Theme colors
        if is_dark:
            bg_color = QColor("#121212")
            text_color = QColor("#E0E0E0")
            num_color = QColor("#8A8A93")
            main_move_color = QColor("#BB86FC")
            var_move_color = QColor("#8A8A93")
            comment_color = QColor("#03DAC6")
            highlight_bg = QColor("#004D40")
            highlight_text_col = QColor("#E0F7FA")
            bracket_color = QColor("#7E7E8A")
            header_bg = QColor("#1E1E24")
            header_border = QColor("#2C2C35")
            header_vs = QColor("#BB86FC")
            header_sub = QColor("#8A8A93")
        else:
            bg_color = QColor("#FAF9F6")
            text_color = QColor("#2C3E50")
            num_color = QColor("#7F8C8D")
            main_move_color = QColor("#1A252C")
            var_move_color = QColor("#7F8C8D")
            comment_color = QColor("#16A085")
            highlight_bg = QColor("#B2DFDB")
            highlight_text_col = QColor("#004D40")
            bracket_color = QColor("#BDC3C7")
            header_bg = QColor("#EAEDED")
            header_border = QColor("#BDC3C7")
            header_vs = QColor("#2980B9")
            header_sub = QColor("#7F8C8D")
            
        # Draw background
        painter.fillRect(self.rect(), bg_color)
        
        # Setup fonts
        font_size = 14 if self.parent_browser.cb_compact.isChecked() else 15
        normal_font = QFont("Segoe UI", font_size)
        bold_font = QFont("Segoe UI", font_size, QFont.Bold)
        italic_font = QFont("Segoe UI", font_size, -1, True)
        
        fm = QFontMetrics(normal_font)
        fm_bold = QFontMetrics(bold_font)
        fm_italic = QFontMetrics(italic_font)
        
        # Get game headers
        headers = {}
        if hasattr(self.parent_browser, 'game') and self.parent_browser.game:
            headers = self.parent_browser.game.headers

        # Draw game header card if game is loaded
        header_offset = 20
        if headers:
            card_margin = 15
            card_padding = 15
            card_width = width
            
            # Fonts for header
            header_title_font = QFont("Segoe UI", 16, QFont.Bold)
            header_sub_font = QFont("Segoe UI", 11)
            
            # Setup player names
            white = headers.get("White", "Unknown White")
            black = headers.get("Black", "Unknown Black")
            white_elo = headers.get("WhiteElo", "")
            black_elo = headers.get("BlackElo", "")
            
            white_str = f"{white} ({white_elo})" if white_elo else white
            black_str = f"{black} ({black_elo})" if black_elo else black
            
            # Subtitle information
            event = headers.get("Event", "?")
            site = headers.get("Site", "?")
            date = headers.get("Date", "?")
            result = headers.get("Result", "*")
            eco = headers.get("ECO", "")
            
            sub_parts = [
                f"Event: {event}",
                f"Site: {site}",
                f"Date: {date}",
                f"Result: {result}"
            ]
            if eco:
                sub_parts.append(f"ECO: {eco}")
            sub_text = " | ".join(sub_parts)
            
            fm_title = QFontMetrics(header_title_font)
            fm_sub = QFontMetrics(header_sub_font)
            
            header_height = 90
            card_rect = QRect(card_margin, 20, card_width, header_height)
            
            # Draw card rounded rect
            painter.setPen(header_border)
            painter.setBrush(header_bg)
            painter.drawRoundedRect(card_rect, 6, 6)
            
            # Elide player names if too long
            available_width = card_width - (card_padding * 2)
            vs_w = fm_title.width(" vs ")
            max_name_w = (available_width - vs_w) // 2
            
            white_elided = fm_title.elidedText(white_str, Qt.ElideRight, max_name_w)
            black_elided = fm_title.elidedText(black_str, Qt.ElideRight, max_name_w)
            sub_text_elided = fm_sub.elidedText(sub_text, Qt.ElideRight, available_width)
            
            # Draw Title: White vs Black
            title_y = 20 + card_padding + fm_title.ascent()
            title_x = card_margin + card_padding
            
            painter.setFont(header_title_font)
            
            painter.setPen(text_color)
            painter.drawText(title_x, title_y, white_elided)
            title_x += fm_title.width(white_elided)
            
            painter.setPen(header_vs)
            painter.drawText(title_x, title_y, " vs ")
            title_x += vs_w
            
            painter.setPen(text_color)
            painter.drawText(title_x, title_y, black_elided)
            
            # Draw Subtitle
            sub_y = 20 + card_padding + fm_title.height() + 8 + fm_sub.ascent()
            sub_x = card_margin + card_padding
            painter.setFont(header_sub_font)
            painter.setPen(header_sub)
            painter.drawText(sub_x, sub_y, sub_text_elided)
            
            # Reset brush & pen
            painter.setBrush(Qt.NoBrush)
            
            header_offset = 20 + header_height + 20
            
        self.line_height = fm.height() + 8
        margin_left = 15
        y = header_offset
        
        for block in self.blocks:
            x = margin_left
            # Indent variation blocks slightly
            indent = 20 if block.level > 0 else 0
            x += indent
            
            if not block.tokens:
                continue
                
            for token in block.tokens:
                # Set layout fonts and measure token width
                if token.token_type == "move":
                    if token.level == 0:
                        fm_current = fm_bold
                    else:
                        fm_current = fm
                elif token.token_type == "comment":
                    fm_current = fm_italic
                else:
                    fm_current = fm
                    
                w = fm_current.width(token.text)
                
                # Check for wrap-around condition in flow layout
                if x + w > width + margin_left:
                    y += self.line_height
                    x = margin_left + indent
                    
                token.rect = QRect(x, y, w + 6, self.line_height)
                
                # Draw token text
                if token.token_type == "move":
                    if token.move_idx == active_index:
                        painter.fillRect(token.rect, highlight_bg)
                        painter.setPen(highlight_text_col)
                        painter.setFont(bold_font)
                    else:
                        painter.setFont(bold_font if token.level == 0 else normal_font)
                        painter.setPen(main_move_color if token.level == 0 else var_move_color)
                    painter.drawText(x + 3, y + fm_current.ascent(), token.text)
                    
                elif token.token_type == "comment":
                    painter.setFont(italic_font)
                    painter.setPen(comment_color)
                    painter.drawText(x + 3, y + fm_current.ascent(), token.text)
                    
                else:
                    painter.setFont(normal_font)
                    painter.setPen(bracket_color if token.text in ["[", "]", "(", ")"] else num_color)
                    painter.drawText(x + 3, y + fm_current.ascent(), token.text)
                    
                x += w + 8  # Add space between tokens
                
            # Block spacing
            y += self.line_height + 8
            
        # Update minimum height dynamically based on final computed height
        expected_height = y + 40
        if self.minimumHeight() != expected_height:
            self.setMinimumHeight(expected_height)

    def mousePressEvent(self, event):
        self.setFocus()
        pos = event.pos()
        for block in self.blocks:
            for token in block.tokens:
                if token.token_type == "move" and token.rect and token.rect.contains(pos):
                    self.parent_browser.jump_to(token.move_idx)
                    event.accept()
                    return
        super().mousePressEvent(event)


# --- Main QPainter Window ---

class QPainterDemo(QMainWindow):
    def __init__(self, pgn_path: str):
        super().__init__()
        self.setWindowTitle("QPainter-based PGN Renderer Demo (Manual Layout)")
        self.resize(1100, 750)
        
        self.pgn_path = pgn_path
        self.flat_nodes = []
        self.blocks = []
        self.active_index = -1
        self.is_dark = True
        
        self.setup_ui()
        self.load_pgn()
        self.options_changed()
        
    def setup_ui(self):
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)
        
        # Sidebar
        sidebar = QWidget(self)
        sidebar.setFixedWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 15, 15, 15)
        sidebar_layout.setSpacing(12)
        
        sb_title = QLabel("Display Options", sidebar)
        sb_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;")
        sidebar_layout.addWidget(sb_title)
        
        self.cb_dark = QCheckBox("Dark Theme", sidebar)
        self.cb_dark.setChecked(True)
        sidebar_layout.addWidget(self.cb_dark)
        
        self.cb_comments = QCheckBox("Show Comments", sidebar)
        self.cb_comments.setChecked(True)
        sidebar_layout.addWidget(self.cb_comments)
        
        self.cb_variations = QCheckBox("Show Variations", sidebar)
        self.cb_variations.setChecked(True)
        sidebar_layout.addWidget(self.cb_variations)
        
        self.cb_compact = QCheckBox("Compact Mode", sidebar)
        self.cb_compact.setChecked(False)
        sidebar_layout.addWidget(self.cb_compact)
        
        # Layout Mode dropdown
        sidebar_layout.addWidget(QLabel("Layout Mode:", sidebar))
        self.combo_layout = QComboBox(sidebar)
        self.combo_layout.addItem("Layout A: Move per Line")
        self.combo_layout.addItem("Layout B: ChessBase Blocks")
        self.combo_layout.setCurrentIndex(1)  # Default to Layout B
        sidebar_layout.addWidget(self.combo_layout)
        
        sidebar_layout.addStretch()
        
        # Note
        sb_note = QLabel("Note: QPainter demo draws text elements directly in paintEvent and does mouse-collision click detection manually.", sidebar)
        sb_note.setWordWrap(True)
        sb_note.setStyleSheet("font-size: 11px; color: #8A8A93; font-style: italic;")
        sidebar_layout.addWidget(sb_note)
        
        main_layout.addWidget(sidebar)
        
        # Content
        content_panel = QWidget(self)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        self.status_label = QLabel("Loading...", self)
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        content_layout.addWidget(self.status_label)
        
        # QScrollArea to hold QPainterBrowser
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.paint_widget = QPainterBrowser(self)
        self.scroll_area.setWidget(self.paint_widget)
        content_layout.addWidget(self.scroll_area)
        
        # Navigation
        nav_layout = QHBoxLayout()
        content_layout.addLayout(nav_layout)
        
        self.btn_first = QPushButton("|< First", self)
        self.btn_prev = QPushButton("< Prev", self)
        self.btn_next = QPushButton("Next >", self)
        self.btn_last = QPushButton("Last >|", self)
        
        for btn in [self.btn_first, self.btn_prev, self.btn_next, self.btn_last]:
            btn.setMinimumHeight(40)
            btn.setStyleSheet("font-size: 14px; font-weight: bold;")
            btn.setFocusPolicy(Qt.NoFocus)
            nav_layout.addWidget(btn)
            
        self.btn_first.clicked.connect(self.go_first)
        self.btn_prev.clicked.connect(self.go_prev)
        self.btn_next.clicked.connect(self.go_next)
        self.btn_last.clicked.connect(self.go_last)

        # Keyboard shortcuts for arrow and navigation keys
        self.shortcut_left = QShortcut(QKeySequence(Qt.Key_Left), self)
        self.shortcut_left.activated.connect(self.go_prev)
        
        self.shortcut_right = QShortcut(QKeySequence(Qt.Key_Right), self)
        self.shortcut_right.activated.connect(self.go_next)
        
        self.shortcut_home = QShortcut(QKeySequence(Qt.Key_Home), self)
        self.shortcut_home.activated.connect(self.go_first)
        
        self.shortcut_end = QShortcut(QKeySequence(Qt.Key_End), self)
        self.shortcut_end.activated.connect(self.go_last)
        
        self.stats_label = QLabel("Timing stats: N/A", self)
        self.stats_label.setStyleSheet("font-family: monospace; font-size: 13px;")
        content_layout.addWidget(self.stats_label)
        
        main_layout.addWidget(content_panel)
        
        self.cb_dark.stateChanged.connect(self.options_changed)
        self.cb_comments.stateChanged.connect(self.options_changed)
        self.cb_variations.stateChanged.connect(self.options_changed)
        self.cb_compact.stateChanged.connect(self.options_changed)
        self.combo_layout.currentIndexChanged.connect(self.options_changed)

    def load_pgn(self):
        t0 = time.perf_counter()
        with open(self.pgn_path, "r", encoding="utf-8") as f:
            self.game = chess.pgn.read_game(f)
        self.t_read = time.perf_counter() - t0

    def traverse_layout_a(self, node, level, blocks, flat_nodes, show_comments, show_variations):
        curr = node
        while curr is not None:
            board = curr.parent.board()
            move_num = board.fullmove_number
            san = board.san(curr.move)
            
            move_idx = len(flat_nodes)
            flat_nodes.append(curr)
            curr.flat_index = move_idx
            
            # Start a new block for White move
            if board.turn == chess.WHITE:
                block = PaintBlock(level)
                block.tokens.append(Token("num", f"{move_num}.", level=level))
                block.tokens.append(Token("move", san, move_idx=move_idx, level=level))
                blocks.append(block)
            else:
                # Append to existing row if it's White only and on same level
                if blocks and blocks[-1].tokens and blocks[-1].tokens[-1].token_type == "move" and blocks[-1].level == level and "..." not in blocks[-1].tokens[0].text:
                    blocks[-1].tokens.append(Token("move", san, move_idx=move_idx, level=level))
                else:
                    block = PaintBlock(level)
                    block.tokens.append(Token("num", f"{move_num}...", level=level))
                    block.tokens.append(Token("move", san, move_idx=move_idx, level=level))
                    blocks.append(block)
                    
            # Handle comment on this move
            if show_comments and curr.comment:
                cleaned = re.sub(r'\[%[^\]]+\]', '', curr.comment).replace('{', '').replace('}', '').strip()
                if cleaned:
                    comment_block = PaintBlock(level)
                    comment_block.tokens.append(Token("comment", f"{{{cleaned}}}", level=level))
                    blocks.append(comment_block)
                    
            # Handle variations
            if show_variations and curr.parent:
                siblings = curr.parent.variations
                if siblings and siblings[0] == curr:
                    for sibling in siblings[1:]:
                        self.traverse_layout_a(sibling, level + 1, blocks, flat_nodes, show_comments, show_variations)
                        
            # Proceed
            if curr.variations:
                curr = curr.variations[0]
            else:
                curr = None

    def traverse_layout_b(self, node, level, blocks, flat_nodes, show_comments, show_variations, current_block=None):
        curr = node
        need_prefix = True
        
        while curr is not None:
            board = curr.parent.board()
            move_num = board.fullmove_number
            san = board.san(curr.move)
            
            move_idx = len(flat_nodes)
            flat_nodes.append(curr)
            curr.flat_index = move_idx
            
            # Start/retrieve block
            if level == 0:
                if current_block is None:
                    current_block = PaintBlock(level=0)
                    blocks.append(current_block)
                    need_prefix = True
            else:
                if current_block is None:
                    current_block = PaintBlock(level=level)
                    blocks.append(current_block)
                    need_prefix = True
                    
            # Prefix Move Number
            if board.turn == chess.WHITE:
                if need_prefix:
                    current_block.tokens.append(Token("num", f"{move_num}.", level=level))
                    need_prefix = False
                elif level == 0 and len(current_block.tokens) > 0:
                    current_block.tokens.append(Token("num", f"{move_num}.", level=level))
            else:
                if need_prefix:
                    current_block.tokens.append(Token("num", f"{move_num}...", level=level))
                    need_prefix = False
                    
            # Add Move
            current_block.tokens.append(Token("move", san, move_idx=move_idx, level=level))
            
            # Handle Comment
            if show_comments and curr.comment:
                cleaned = re.sub(r'\[%[^\]]+\]', '', curr.comment).replace('{', '').replace('}', '').strip()
                if cleaned:
                    if level == 0:
                        # Comments at level 0 break main line block
                        current_block = None
                        comment_block = PaintBlock(level=0)
                        comment_block.tokens.append(Token("comment", f"{{{cleaned}}}", level=0))
                        blocks.append(comment_block)
                        need_prefix = True
                    else:
                        # Comments in variation stay inline
                        current_block.tokens.append(Token("comment", f"{{{cleaned}}}", level=level))
                        need_prefix = True
                        
            # Handle sidelines
            if show_variations and curr.parent:
                siblings = curr.parent.variations
                if siblings and siblings[0] == curr:
                    for sibling in siblings[1:]:
                        if level == 0:
                            # Close mainline, recurse variation block wrapped in square brackets
                            current_block = None
                            var_block = PaintBlock(level=1)
                            blocks.append(var_block)
                            var_block.tokens.append(Token("text", "[", level=1))
                            
                            self.traverse_layout_b(sibling, 1, blocks, flat_nodes, show_comments, show_variations, var_block)
                            
                            var_block.tokens.append(Token("text", "]", level=1))
                            need_prefix = True
                        else:
                            # Nested variations inside variation blocks are wrapped in parentheses () inline
                            current_block.tokens.append(Token("text", "(", level=level))
                            
                            self.traverse_layout_b(sibling, level + 1, blocks, flat_nodes, show_comments, show_variations, current_block)
                            
                            current_block.tokens.append(Token("text", ")", level=level))
                            need_prefix = True
                            
            # Proceed
            if curr.variations:
                curr = curr.variations[0]
            else:
                curr = None

    def options_changed(self):
        self.is_dark = self.cb_dark.isChecked()
        self.apply_theme()
        
        # Regenerate blocks dynamically
        t0 = time.perf_counter()
        self.flat_nodes = []
        self.blocks = []
        
        layout_mode = self.combo_layout.currentIndex()  # 0 = Layout A, 1 = Layout B
        show_comments = self.cb_comments.isChecked()
        show_variations = self.cb_variations.isChecked()
        
        if self.game.variations:
            first_move = self.game.variations[0]
            if layout_mode == 0:
                self.traverse_layout_a(first_move, 0, self.blocks, self.flat_nodes, show_comments, show_variations)
            else:
                self.traverse_layout_b(first_move, 0, self.blocks, self.flat_nodes, show_comments, show_variations)
                
        self.t_build_blocks = time.perf_counter() - t0
        
        # Tell the widget to paint
        self.paint_widget.set_blocks(self.blocks)
        
        total_moves = len(self.flat_nodes)
        self.status_label.setText(
            f"PGN loaded successfully: {total_moves} moves. "
            f"Read PGN: {self.t_read*1000.0:.1f}ms | Layout Gen: {self.t_build_blocks*1000.0:.1f}ms"
        )
        
        # Trigger active index update
        if self.active_index >= 0 and self.active_index < len(self.flat_nodes):
            self.jump_to(self.active_index)
        elif self.flat_nodes:
            self.jump_to(0)

    def apply_theme(self):
        if self.is_dark:
            self.setStyleSheet("""
                QMainWindow { background-color: #121212; }
                QLabel { color: #E2E2E6; }
                QCheckBox { color: #E2E2E6; font-size: 13px; spacing: 8px; }
                QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #3E3E4A; border-radius: 3px; background-color: #1E1E24; }
                QCheckBox::indicator:checked { background-color: #BB86FC; border-color: #BB86FC; }
                QPushButton { background-color: #2C2C35; color: #E0E0E0; border: 1px solid #3E3E4A; border-radius: 6px; padding: 6px; font-size: 13px; }
                QPushButton:hover { background-color: #3E3E4A; }
                QPushButton:pressed { background-color: #BB86FC; color: #121212; }
                QComboBox { background-color: #2C2C35; color: #E0E0E0; border: 1px solid #3E3E4A; border-radius: 4px; padding: 4px; font-size: 13px; }
            """)
            self.stats_label.setStyleSheet("font-family: monospace; font-size: 13px; color: #BB86FC;")
        else:
            self.setStyleSheet("""
                QMainWindow { background-color: #FAF9F6; }
                QLabel { color: #2C3E50; }
                QCheckBox { color: #2C3E50; font-size: 13px; spacing: 8px; }
                QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #BDC3C7; border-radius: 3px; background-color: #FFFFFF; }
                QCheckBox::indicator:checked { background-color: #2980B9; border-color: #2980B9; }
                QPushButton { background-color: #EAEDED; color: #2C3E50; border: 1px solid #BDC3C7; border-radius: 6px; padding: 6px; font-size: 13px; }
                QPushButton:hover { background-color: #D5DBDB; }
                QPushButton:pressed { background-color: #2980B9; color: white; }
                QComboBox { background-color: #FFFFFF; color: #2C3E50; border: 1px solid #BDC3C7; border-radius: 4px; padding: 4px; font-size: 13px; }
            """)
            self.stats_label.setStyleSheet("font-family: monospace; font-size: 13px; color: #2980B9;")

    def jump_to(self, index: int):
        if not self.flat_nodes or index < 0 or index >= len(self.flat_nodes):
            return
            
        t0 = time.perf_counter()
        self.active_index = index
        
        # Trigger repaint of widget
        self.paint_widget.update()
        
        t_total = time.perf_counter() - t0
        
        # Center active move
        self.scroll_to_move(index)
        
        active_node = self.flat_nodes[index]
        board = active_node.parent.board()
        move_name = f"{board.fullmove_number}.{board.san(active_node.move)}" if board.turn == chess.WHITE else f"{board.fullmove_number}...{board.san(active_node.move)}"
        
        mem_mb = self.get_memory_usage()
        self.stats_label.setText(
            f"Active Move: {move_name} (Index: {index}) | "
            f"Highlight Action Time: {t_total*1000.0:.3f} ms | "
            f"Process RSS Memory: {mem_mb:.2f} MB"
        )

    def scroll_to_move(self, index):
        active_rect = None
        for block in self.blocks:
            for token in block.tokens:
                if token.token_type == "move" and token.move_idx == index:
                    active_rect = token.rect
                    break
            if active_rect:
                break
                
        if active_rect:
            scrollbar = self.scroll_area.verticalScrollBar()
            viewport_h = self.scroll_area.viewport().height()
            target_y = active_rect.y() - viewport_h // 2
            target_y = max(scrollbar.minimum(), min(scrollbar.maximum(), target_y))
            scrollbar.setValue(target_y)

    def get_memory_usage(self):
        try:
            import ctypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
            GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if GetProcessMemoryInfo(GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize / 1024 / 1024
        except Exception:
            pass
        return 0.0

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.go_next()
            event.accept()
        elif event.key() == Qt.Key_Left:
            self.go_prev()
            event.accept()
        elif event.key() == Qt.Key_Home:
            self.go_first()
            event.accept()
        elif event.key() == Qt.Key_End:
            self.go_last()
            event.accept()
        else:
            super().keyPressEvent(event)

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
        
    demo = QPainterDemo(pgn_file)
    demo.show()
    sys.exit(app.exec_())
