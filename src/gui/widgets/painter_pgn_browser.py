import re
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal, QUrl
from PyQt5.QtGui import QColor, QFont, QPainter, QFontMetrics
from PyQt5.QtWidgets import QScrollArea, QWidget, QMenu, QAction
import chess.pgn

from gui.widgets.pgn_browser import CommentDialog


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
        self.setMinimumWidth(300)
        
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
        base_size = self.parent_browser.base_font_size
        font_size = base_size - 2 if self.parent_browser.cb_compact else base_size
        font_family = self.parent_browser.font_family
        normal_font = QFont(font_family, font_size)
        bold_font = QFont(font_family, font_size, QFont.Bold)
        italic_font = QFont(font_family, font_size, -1, True)
        
        fm = QFontMetrics(normal_font)
        fm_bold = QFontMetrics(bold_font)
        fm_italic = QFontMetrics(italic_font)
        
        # Get game headers
        headers = {}
        if hasattr(self.parent_browser.move_manager, 'game') and self.parent_browser.move_manager.game:
            headers = self.parent_browser.move_manager.game.headers

        # Draw game header card if game is loaded
        header_offset = 20
        if headers:
            card_margin = 15
            card_padding = 15
            card_width = width
            
            # Check if this is a default new game (no real game loaded yet)
            white = headers.get("White", "?")
            black = headers.get("Black", "?")
            event = headers.get("Event", "?")
            
            is_new_game = (white == "?" and black == "?" and (event == "?" or event == "Chess Analysis" or not event))
            
            if is_new_game:
                header_height = 50
                card_rect = QRect(card_margin, 20, card_width, header_height)
                
                # Draw card rounded rect
                painter.setPen(header_border)
                painter.setBrush(header_bg)
                painter.drawRoundedRect(card_rect, 6, 6)
                
                # Draw "New Game"
                painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
                painter.setPen(text_color)
                fm_new = QFontMetrics(painter.font())
                new_str = "New Game"
                title_y = 20 + (header_height - fm_new.height()) // 2 + fm_new.ascent()
                painter.drawText(card_margin + card_padding, title_y, new_str)
                
                painter.setBrush(Qt.NoBrush)
                header_offset = 20 + header_height + 20
            else:
                # Fonts for header
                header_title_font = QFont("Segoe UI", 16, QFont.Bold)
                header_sub_font = QFont("Segoe UI", 11)
                
                # Setup player names
                white_elo = headers.get("WhiteElo", "")
                black_elo = headers.get("BlackElo", "")
                
                white_str = f"{white} ({white_elo})" if white_elo else white
                black_str = f"{black} ({black_elo})" if black_elo else black
                
                # Subtitle information
                site = headers.get("Site", "?")
                date = headers.get("Date", "?")
                result = headers.get("Result", "*")
                eco = headers.get("ECO", "")
                
                # Just show values without keys
                sub_parts = [event, site, date, result]
                if eco:
                    sub_parts.append(eco)
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
                        font = bold_font
                        fm_current = fm_bold
                    else:
                        font = normal_font
                        fm_current = fm
                elif token.token_type == "comment":
                    font = italic_font
                    fm_current = fm_italic
                else:
                    font = normal_font
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
                    # Notify parent browser to jump to this move
                    self.parent_browser.jump_to_move(token.move_idx)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Right:
            self.parent_browser.go_next()
            event.accept()
        elif event.key() == Qt.Key_Left:
            self.parent_browser.go_prev()
            event.accept()
        elif event.key() == Qt.Key_Home:
            self.parent_browser.go_first()
            event.accept()
        elif event.key() == Qt.Key_End:
            self.parent_browser.go_last()
            event.accept()
        else:
            super().keyPressEvent(event)


class QPainterPGNBrowser(QScrollArea):
    anchorClicked = pyqtSignal(QUrl)

    def __init__(self, parent, move_manager):
        super().__init__(parent)
        self.move_manager = move_manager
        
        self.setWidgetResizable(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFrameStyle(0)  # No frame border
        
        # Setup inner paint widget
        self.paint_widget = QPainterBrowser(self)
        self.setWidget(self.paint_widget)
        
        # Default options matching setup
        self.is_dark = True
        self.cb_compact = False
        self.show_comments = True
        self.show_variations = True
        self.layout_mode = 1  # 1 = ChessBase Blocks
        self.font_family = "Segoe UI"
        self.base_font_size = 14
        self.active_index = -1
        self.flat_nodes = []
        self.blocks = []
        
        # Context Menu Setup
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_custom_context)
        
    def setHtml(self, html: str):
        # We ignore the HTML argument and render using the PGN tree in self.move_manager.game
        self.rebuild_layout()
        
    def setStyleSheet(self, stylesheet: str):
        # Parse font-family from the stylesheet to keep dynamic figurine fonts synchronized
        font_match = re.search(r"font-family:\s*([^;\}]+)", stylesheet)
        if font_match:
            self.font_family = font_match.group(1).replace("'", "").replace("\"", "").strip()
            
        # Parse font-size from stylesheet
        size_match = re.search(r"font-size:\s*(\d+)px", stylesheet)
        if size_match:
            self.base_font_size = max(10, int(size_match.group(1)) - 4)
            
        self.paint_widget.update()
        
    def rebuild_layout(self):
        self.is_dark = self.move_manager.html_style
        
        self.flat_nodes = []
        self.blocks = []
        
        show_comments = self.show_comments
        show_variations = self.show_variations
        layout_mode = self.layout_mode
        
        game = self.move_manager.game
        if game.variations:
            first_move = game.variations[0]
            if layout_mode == 0:
                self.traverse_layout_a(first_move, 0, self.blocks, self.flat_nodes, show_comments, show_variations)
            else:
                self.traverse_layout_b(first_move, 0, self.blocks, self.flat_nodes, show_comments, show_variations)
                
        self.paint_widget.set_blocks(self.blocks)
        self.update_active_index()
        
    def update_active_index(self):
        node = self.move_manager.current_node
        if node and hasattr(node, "flat_index"):
            self.active_index = node.flat_index
        else:
            self.active_index = -1
            
        self.paint_widget.update()
        self.scroll_to_move(self.active_index)
        
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
            scrollbar = self.verticalScrollBar()
            viewport_h = self.viewport().height()
            target_y = active_rect.y() - viewport_h // 2
            target_y = max(scrollbar.minimum(), min(scrollbar.maximum(), target_y))
            scrollbar.setValue(target_y)

    def jump_to_move(self, index):
        if 0 <= index < len(self.flat_nodes):
            self.move_manager.jump_to(index)
            # Emit anchorClicked signal with QUrl for standard application logic
            self.anchorClicked.emit(QUrl(f"move({index})"))

    def go_next(self):
        if self.move_manager.current_node.variations:
            self.move_manager.redo(0)
            
    def go_prev(self):
        self.move_manager.undo()
        
    def go_first(self):
        self.move_manager.jump_to_start()
        
    def go_last(self):
        self.move_manager.jump_to_end()

    # --- Traversals copied from qpainter_demo.py ---
    def traverse_layout_a(self, node, level, blocks, flat_nodes, show_comments, show_variations):
        curr = node
        while curr is not None:
            board = curr.parent.board()
            move_num = board.fullmove_number
            san = board.san(curr.move)
            
            move_idx = len(flat_nodes)
            flat_nodes.append(curr)
            curr.flat_index = move_idx
            
            if board.turn == chess.WHITE:
                block = PaintBlock(level)
                block.tokens.append(Token("num", f"{move_num}.", level=level))
                block.tokens.append(Token("move", san, move_idx=move_idx, level=level))
                blocks.append(block)
            else:
                if blocks and blocks[-1].tokens and blocks[-1].tokens[-1].token_type == "move" and blocks[-1].level == level and "..." not in blocks[-1].tokens[0].text:
                    blocks[-1].tokens.append(Token("move", san, move_idx=move_idx, level=level))
                else:
                    block = PaintBlock(level)
                    block.tokens.append(Token("num", f"{move_num}...", level=level))
                    block.tokens.append(Token("move", san, move_idx=move_idx, level=level))
                    blocks.append(block)
                    
            if show_comments and curr.comment:
                cleaned = re.sub(r'\[%[^\]]+\]', '', curr.comment).replace('{', '').replace('}', '').strip()
                if cleaned:
                    if blocks:
                        blocks[-1].tokens.append(Token("comment", cleaned, level=level))
                    
            if show_variations and curr.parent:
                siblings = curr.parent.variations
                if siblings and siblings[0] == curr:
                    for sibling in siblings[1:]:
                        self.traverse_layout_a(sibling, level + 1, blocks, flat_nodes, show_comments, show_variations)
                        
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
                    
            current_block.tokens.append(Token("move", san, move_idx=move_idx, level=level))
            
            if show_comments and curr.comment:
                cleaned = re.sub(r'\[%[^\]]+\]', '', curr.comment).replace('{', '').replace('}', '').strip()
                if cleaned:
                    current_block.tokens.append(Token("comment", cleaned, level=level))
                        
            if show_variations and curr.parent:
                siblings = curr.parent.variations
                if siblings and siblings[0] == curr:
                    for sibling in siblings[1:]:
                        if level == 0:
                            current_block = None
                            var_block = PaintBlock(level=1)
                            blocks.append(var_block)
                            var_block.tokens.append(Token("text", "[", level=1))
                            self.traverse_layout_b(sibling, 1, blocks, flat_nodes, show_comments, show_variations, var_block)
                            var_block.tokens.append(Token("text", "]", level=1))
                            need_prefix = True
                        else:
                            current_block.tokens.append(Token("text", "(", level=level))
                            self.traverse_layout_b(sibling, level + 1, blocks, flat_nodes, show_comments, show_variations, current_block)
                            current_block.tokens.append(Token("text", ")", level=level))
                            need_prefix = True
                            
            if curr.variations:
                curr = curr.variations[0]
            else:
                curr = None

    # --- Context Menu Actions ---
    def on_custom_context(self, point):
        paint_point = self.paint_widget.mapFrom(self, point)
        
        move_idx = None
        for block in self.blocks:
            for token in block.tokens:
                if token.token_type == "move" and token.rect and token.rect.contains(paint_point):
                    move_idx = token.move_idx
                    break
            if move_idx is not None:
                break
                
        if move_idx is None:
            return
            
        anchor = f"move({move_idx})"
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: palette(window);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 12px;
                margin: 2px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QMenu::separator {
                height: 1px;
                background-color: palette(mid);
                margin: 4px 8px;
            }
        """)

        import qtawesome as qta
        actions = [
            ("Promote to Main Line", self.on_promote_to_main, "fa5s.arrow-up"),
            ("Promote Move", self.on_promote, "fa5s.chevron-up"),
            ("Demote Move", self.on_demote, "fa5s.chevron-down"),
            ("Delete from Here", self.on_delete, "fa5s.trash-alt"),
            (None, None, None),  # Separator
            ("Edit Comment...", self.on_add_comment, "fa5s.comment-alt"),
        ]

        for name, func, icon_name in actions:
            if name is None:
                menu.addSeparator()
            else:
                icon = qta.icon(icon_name)
                act = QAction(icon, name, self)
                act.triggered.connect(lambda checked, f=func: f(anchor))
                menu.addAction(act)

        menu.exec_(self.mapToGlobal(point))

    def on_add_comment(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            node = self.move_manager.get_node_by_index(node_index)
            dlg = CommentDialog(self, node.comment)
            if dlg.exec_() != CommentDialog.Accepted:
                return
            self.move_manager.add_comment(node_index, dlg.comment)

    def on_promote_to_main(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            self.move_manager.promote_to_main(node_index)

    def on_promote(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            self.move_manager.promote(node_index)

    def on_demote(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            self.move_manager.demote(node_index)

    def on_delete(self, anchor):
        node_index = self.match_node(anchor)
        if node_index is not None:
            self.move_manager.delete_from_here(node_index)

    def match_node(self, anchor: str) -> int | None:
        match = re.match(r"move\((\d+)\)", anchor)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return None
