import re
from PyQt5.QtCore import Qt, QRect, QSize, pyqtSignal, QUrl
from PyQt5.QtGui import QColor, QFont, QPainter, QFontMetrics
from PyQt5.QtWidgets import QScrollArea, QWidget, QMenu, QAction, QVBoxLayout
import chess.pgn

from gui.widgets.pgn_browser import CommentDialog


def format_compact_eval(eval_str: str) -> str:
    if not eval_str:
        return ""
    try:
        # Check if mate (e.g. #5 or #-3)
        if '#' in eval_str:
            return eval_str
        val = float(eval_str)
        # Round to 1 decimal place
        rounded = round(val, 1)
        # Format with + sign if positive
        if rounded > 0:
            return f"+{rounded:.1f}"
        elif rounded == 0:
            return "0.0"
        else:
            return f"{rounded:.1f}"
    except ValueError:
        return eval_str


class PaintBlock:
    def __init__(self, level):
        self.level = level
        self.tokens = []
        self.rect = None


class Token:
    def __init__(self, token_type, text, move_idx=-1, level=0, classification=None):
        self.token_type = token_type
        self.text = text
        self.move_idx = move_idx
        self.level = level
        self.rect = None
        self.classification = classification


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
        self.compute_layout(self.blocks)
        
    def compute_layout(self, blocks):
        self.blocks = blocks
        
        # Setup fonts
        base_size = self.parent_browser.base_font_size
        font_size = base_size - 2 if self.parent_browser.cb_compact else base_size
        font_family = self.parent_browser.font_family
        
        normal_font = QFont(font_family, font_size)
        bold_font = QFont(font_family, font_size, QFont.Bold)
        italic_font = QFont(font_family, font_size, -1, True)
        ann_font = QFont(font_family, max(8, font_size - 3))
        
        fm = QFontMetrics(normal_font)
        fm_bold = QFontMetrics(bold_font)
        fm_italic = QFontMetrics(italic_font)
        fm_ann = QFontMetrics(ann_font)
        
        self.line_height = fm.height() + 8
        margin_left = 15
        width = self.width() - 30  # Margin bounds
        if width <= 0:
            width = 300
            
        y = 20
        
        for block in self.blocks:
            x = margin_left
            indent = 20 if block.level > 0 else 0
            x += indent
            
            block_top = y
            
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
                elif token.token_type == "eval":
                    fm_current = fm_ann
                else:
                    fm_current = fm
                    
                w = fm_current.width(token.text)
                
                # Check for wrap-around condition in flow layout
                if x + w > width + margin_left:
                    y += self.line_height
                    x = margin_left + indent
                    
                token.rect = QRect(x, y, w + 6, self.line_height)
                x += w + 8  # Add space between tokens
                
            block_bottom = y + self.line_height
            block.rect = QRect(margin_left, block_top, width, block_bottom - block_top)
            
            # Block spacing
            y = block_bottom + 8
            
        # Update height dynamically based on computed layout height
        self.setMinimumHeight(y + 40)
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        is_dark = self.parent_browser.is_dark
        active_index = self.parent_browser.active_index
        
        # Viewport intersection bounds
        scrollbar = self.parent_browser.scroll_area.verticalScrollBar()
        viewport_top = scrollbar.value()
        viewport_bottom = viewport_top + self.parent_browser.scroll_area.viewport().height()
        
        # Theme colors
        if is_dark:
            bg_color = QColor("#262421")
            text_color = QColor("#ffffff")
            num_color = QColor("#8b8987")
            main_move_color = QColor("#ffffff")
            var_move_color = QColor("#8b8987")
            comment_color = QColor("#81c784")
            eval_color = QColor("#4fc3f7")
            highlight_bg = QColor("#1a365d")
            bracket_color = QColor("#8b8987")
        else:
            bg_color = QColor("#f1f1f1")
            text_color = QColor("#312e2b")
            num_color = QColor("#555555")
            main_move_color = QColor("#312e2b")
            var_move_color = QColor("#777777")
            comment_color = QColor("#2e7d32")
            eval_color = QColor("#0288d1")
            highlight_bg = QColor("#dbeafe")
            bracket_color = QColor("#999999")
            
        # Draw background
        painter.fillRect(self.rect(), bg_color)
        
        # Setup fonts
        base_size = self.parent_browser.base_font_size
        font_size = base_size - 2 if self.parent_browser.cb_compact else base_size
        font_family = self.parent_browser.font_family
        
        normal_font = QFont(font_family, font_size)
        bold_font = QFont(font_family, font_size, QFont.Bold)
        italic_font = QFont(font_family, font_size, -1, True)
        ann_font = QFont(font_family, max(8, font_size - 3))
        
        fm_normal = QFontMetrics(normal_font)
        
        # Draw blocks that intersect with viewport
        for block in self.blocks:
            if hasattr(block, 'rect') and block.rect:
                if block.rect.bottom() < viewport_top - 50 or block.rect.top() > viewport_bottom + 50:
                    continue
                    
            if not block.tokens:
                continue
                
            for token in block.tokens:
                if not token.rect:
                    continue
                    
                if token.rect.bottom() < viewport_top or token.rect.top() > viewport_bottom:
                    continue
                    
                # Draw token text
                if token.token_type == "move":
                    if is_dark:
                        cls_colors = {
                            4: QColor("#FFD54F"),  # Inaccuracy
                            5: QColor("#FF9800"),  # Mistake
                            6: QColor("#FF5252"),  # Blunder
                            7: QColor("#28c2a4"),  # Brilliant
                            8: QColor("#FF8A80"),  # Miss
                        }
                    else:
                        cls_colors = {
                            4: QColor("#b58900"),  # Inaccuracy
                            5: QColor("#e65100"),  # Mistake
                            6: QColor("#b71c1c"),  # Blunder
                            7: QColor("#28c2a4"),  # Brilliant
                            8: QColor("#d32f2f"),  # Miss
                        }

                    is_active = (token.move_idx == active_index)
                    if is_active:
                        painter.fillRect(token.rect, highlight_bg)
                        painter.setFont(bold_font)
                    else:
                        painter.setFont(bold_font if token.level == 0 else normal_font)
                        
                    show_classifications = getattr(self.parent_browser, "show_classifications", True)
                    if show_classifications and hasattr(token, 'classification') and token.classification in cls_colors:
                        painter.setPen(cls_colors[token.classification])
                    else:
                        painter.setPen(main_move_color if token.level == 0 else var_move_color)
                            
                    painter.drawText(token.rect.x() + 3, token.rect.y() + fm_normal.ascent(), token.text)
                    
                elif token.token_type == "comment":
                    painter.setFont(italic_font)
                    painter.setPen(comment_color)
                    painter.drawText(token.rect.x() + 3, token.rect.y() + fm_normal.ascent(), token.text)
                    
                elif token.token_type == "eval":
                    painter.setFont(ann_font)
                    painter.setPen(eval_color)
                    painter.drawText(token.rect.x() + 3, token.rect.y() + fm_normal.ascent(), token.text)
                    
                else:
                    painter.setFont(normal_font)
                    painter.setPen(bracket_color if token.text in ["[", "]", "(", ")"] else num_color)
                    painter.drawText(token.rect.x() + 3, token.rect.y() + fm_normal.ascent(), token.text)

    def mousePressEvent(self, event):
        self.setFocus()
        pos = event.pos()
        for block in self.blocks:
            for token in block.tokens:
                if token.token_type == "move" and token.rect and token.rect.contains(pos):
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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.parent_browser.rebuild_layout()


class QPainterHeaderWidget(QWidget):
    def __init__(self, parent_browser):
        super().__init__()
        self.parent_browser = parent_browser
        self.setFixedHeight(95)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        is_dark = self.parent_browser.is_dark
        bg_color = QColor("#262421") if is_dark else QColor("#f1f1f1")
        painter.fillRect(self.rect(), bg_color)
        
        headers = {}
        if hasattr(self.parent_browser.move_manager, 'game') and self.parent_browser.move_manager.game:
            headers = self.parent_browser.move_manager.game.headers
            
        if not headers:
            return
            
        white = headers.get("White", "?")
        black = headers.get("Black", "?")
        event_name = headers.get("Event", "?")
        
        is_new_game = (white == "?" and black == "?" and (event_name == "?" or event_name == "Chess Analysis" or not event_name))
        
        # Theme colors
        if is_dark:
            text_color = QColor("#ffffff")
            header_bg = QColor("#312e2b")
            header_border = QColor("#403d39")
            header_vs = QColor("#e6912c")
            header_sub = QColor("#8b8987")
        else:
            text_color = QColor("#312e2b")
            header_bg = QColor("#e1e1e1")
            header_border = QColor("#cccccc")
            header_vs = QColor("#e6912c")
            header_sub = QColor("#555555")
            
        card_margin = 15
        card_padding = 10
        card_width = self.width() - 30
        
        if is_new_game:
            header_height = 42
            card_rect = QRect(card_margin, 10, card_width, header_height)
            
            painter.setPen(header_border)
            painter.setBrush(header_bg)
            painter.drawRoundedRect(card_rect, 6, 6)
            
            painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
            painter.setPen(text_color)
            fm_new = QFontMetrics(painter.font())
            title_y = 10 + (header_height - fm_new.height()) // 2 + fm_new.ascent()
            painter.drawText(card_margin + card_padding, title_y, "New Game")
        else:
            header_height = 70
            card_rect = QRect(card_margin, 10, card_width, header_height)
            
            painter.setPen(header_border)
            painter.setBrush(header_bg)
            painter.drawRoundedRect(card_rect, 6, 6)
            
            header_title_font = QFont("Segoe UI", 12, QFont.Bold)
            header_sub_font = QFont("Segoe UI", 9)
            
            # Setup player names
            white_elo = headers.get("WhiteElo", "")
            black_elo = headers.get("BlackElo", "")
            white_str = f"{white} ({white_elo})" if white_elo else white
            black_str = f"{black} ({black_elo})" if black_elo else black
            
            site = headers.get("Site", "?")
            date = headers.get("Date", "?")
            result = headers.get("Result", "*")
            eco = headers.get("ECO", "")
            
            sub_parts = [event_name, site, date, result]
            if eco:
                sub_parts.append(eco)
            sub_text = " | ".join(sub_parts)
            
            fm_title = QFontMetrics(header_title_font)
            fm_sub = QFontMetrics(header_sub_font)
            
            available_width = card_width - (card_padding * 2)
            vs_w = fm_title.width(" vs ")
            max_name_w = (available_width - vs_w) // 2
            
            white_elided = fm_title.elidedText(white_str, Qt.ElideRight, max_name_w)
            black_elided = fm_title.elidedText(black_str, Qt.ElideRight, max_name_w)
            sub_text_elided = fm_sub.elidedText(sub_text, Qt.ElideRight, available_width)
            
            title_y = 10 + card_padding + fm_title.ascent()
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
            
            sub_y = 10 + card_padding + fm_title.height() + 4 + fm_sub.ascent()
            sub_x = card_margin + card_padding
            painter.setFont(header_sub_font)
            painter.setPen(header_sub)
            painter.drawText(sub_x, sub_y, sub_text_elided)
            
        painter.setBrush(Qt.NoBrush)


class QPainterPGNBrowser(QWidget):
    anchorClicked = pyqtSignal(QUrl)

    def __init__(self, parent, move_manager):
        super().__init__(parent)
        self.move_manager = move_manager
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.is_dark = True
        self.cb_compact = False
        self.show_comments = True
        self.show_variations = True
        self.show_eval = True
        self.show_classifications = True
        self.layout_mode = 1  # 1 = ChessBase Blocks
        self.font_family = "Segoe UI"
        self.base_font_size = 12
        self.active_index = -1
        self.flat_nodes = []
        self.blocks = []
        
        # Fixed header widget
        self.header_widget = QPainterHeaderWidget(self)
        self.main_layout.addWidget(self.header_widget)
        
        # Scroll area wrapping the custom paint browser
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFocusPolicy(Qt.NoFocus)
        self.scroll_area.setFrameStyle(0)
        
        self.paint_widget = QPainterBrowser(self)
        self.scroll_area.setWidget(self.paint_widget)
        self.scroll_area.verticalScrollBar().valueChanged.connect(lambda _: self.paint_widget.update())
        self.main_layout.addWidget(self.scroll_area)
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_custom_context)
        
    def setHtml(self, html: str):
        self.rebuild_layout()
        
    def setStyleSheet(self, stylesheet: str):
        font_match = re.search(r"font-family:\s*([^;\}]+)", stylesheet)
        if font_match:
            self.font_family = font_match.group(1).replace("'", "").replace("\"", "").strip()
            
        size_match = re.search(r"font-size:\s*(\d+)px", stylesheet)
        if size_match:
            self.base_font_size = max(11, int(size_match.group(1)) - 6)
            
        self.paint_widget.update()
        self.header_widget.update()
        
    def rebuild_layout(self, force=False):
        self.is_dark = self.move_manager.html_style
        
        # Check if PGN nodes structure has changed to determine if we should rebuild the layout cache
        current_nodes = getattr(self.move_manager, 'nodes', [])
        nodes_changed = True
        if hasattr(self, 'cached_nodes') and len(self.cached_nodes) == len(current_nodes):
            nodes_changed = False
            for i in range(len(current_nodes)):
                if self.cached_nodes[i] is not current_nodes[i]:
                    nodes_changed = True
                    break
                    
        layout_width = self.paint_widget.width() - 30
        if layout_width <= 0:
            layout_width = 300
            
        width_changed = (not hasattr(self, 'last_layout_width') or self.last_layout_width != layout_width)
        
        if force or nodes_changed or width_changed or getattr(self, 'layout_invalid', False):
            self.cached_nodes = list(current_nodes)
            self.last_layout_width = layout_width
            self.layout_invalid = False
            
            headers = {}
            if hasattr(self.move_manager, 'game') and self.move_manager.game:
                headers = self.move_manager.game.headers
                
            if headers:
                white = headers.get("White", "?")
                black = headers.get("Black", "?")
                event_name = headers.get("Event", "?")
                is_new_game = (white == "?" and black == "?" and (event_name == "?" or event_name == "Chess Analysis" or not event_name))
                
                if is_new_game:
                    self.header_widget.setFixedHeight(42 + 20)
                else:
                    self.header_widget.setFixedHeight(70 + 20)
            else:
                self.header_widget.setFixedHeight(0)
                
            self.header_widget.update()
            
            self.flat_nodes = []
            self.blocks = []
            
            game = self.move_manager.game
            if game.variations:
                first_move = game.variations[0]
                if self.layout_mode == 0:
                    self.traverse_layout_a(first_move, 0, self.blocks, self.flat_nodes, self.show_comments, self.show_variations)
                else:
                    self.traverse_layout_b(first_move, 0, self.blocks, self.flat_nodes, self.show_comments, self.show_variations)
                    
            self.paint_widget.compute_layout(self.blocks)
            
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
            scrollbar = self.scroll_area.verticalScrollBar()
            viewport_h = self.scroll_area.viewport().height()
            target_y = active_rect.y() - viewport_h // 2
            target_y = max(scrollbar.minimum(), min(scrollbar.maximum(), target_y))
            scrollbar.setValue(target_y)

    def jump_to_move(self, index):
        if 0 <= index < len(self.flat_nodes):
            self.move_manager.jump_to(index)
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

    def traverse_layout_a(self, node, level, blocks, flat_nodes, show_comments, show_variations):
        curr = node
        while curr is not None:
            board = curr.parent.board()
            move_num = board.fullmove_number
            san = board.san(curr.move)
            
            move_idx = len(flat_nodes)
            flat_nodes.append(curr)
            curr.flat_index = move_idx
            
            # Extract compact eval if present
            eval_text = ""
            if self.show_eval and curr.comment:
                eval_match = re.search(r'\[%eval\s+([^\]]+)\]', curr.comment)
                if eval_match:
                    eval_text = format_compact_eval(eval_match.group(1))

            # Extract classification
            cls_val = None
            if curr.comment:
                alz_match = re.search(r'\[%alz\s+([^\]]+)\]', curr.comment)
                if alz_match:
                    cls_tokens = alz_match.group(1).split()
                    for token in cls_tokens:
                        if token.startswith("cls="):
                            try:
                                cls_val = int(token.split("=")[1])
                            except ValueError:
                                pass
            
            if board.turn == chess.WHITE:
                block = PaintBlock(level)
                block.tokens.append(Token("num", f"{move_num}.", level=level))
                block.tokens.append(Token("move", san, move_idx=move_idx, level=level, classification=cls_val))
                if eval_text:
                    block.tokens.append(Token("eval", eval_text, move_idx=move_idx, level=level))
                blocks.append(block)
            else:
                if blocks and blocks[-1].tokens and blocks[-1].tokens[-1].token_type == "move" and blocks[-1].level == level and "..." not in blocks[-1].tokens[0].text:
                    blocks[-1].tokens.append(Token("move", san, move_idx=move_idx, level=level, classification=cls_val))
                    if eval_text:
                        blocks[-1].tokens.append(Token("eval", eval_text, move_idx=move_idx, level=level))
                else:
                    block = PaintBlock(level)
                    block.tokens.append(Token("num", f"{move_num}...", level=level))
                    block.tokens.append(Token("move", san, move_idx=move_idx, level=level, classification=cls_val))
                    if eval_text:
                        block.tokens.append(Token("eval", eval_text, move_idx=move_idx, level=level))
                    blocks.append(block)
                    
            if show_comments and curr.comment:
                cleaned = re.sub(r'\[%[^\]]+\]', '', curr.comment).replace('{', '').replace('}', '')
                cleaned = cleaned.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
                words = cleaned.split()
                if blocks:
                    for word in words:
                        blocks[-1].tokens.append(Token("comment", word, level=level))
                    
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

            # Extract classification
            cls_val = None
            if curr.comment:
                alz_match = re.search(r'\[%alz\s+([^\]]+)\]', curr.comment)
                if alz_match:
                    cls_tokens = alz_match.group(1).split()
                    for token in cls_tokens:
                        if token.startswith("cls="):
                            try:
                                cls_val = int(token.split("=")[1])
                            except ValueError:
                                pass
                    
            current_block.tokens.append(Token("move", san, move_idx=move_idx, level=level, classification=cls_val))
            
            # Extract and add compact eval if present
            if self.show_eval and curr.comment:
                eval_match = re.search(r'\[%eval\s+([^\]]+)\]', curr.comment)
                if eval_match:
                    eval_text = format_compact_eval(eval_match.group(1))
                    if eval_text:
                        current_block.tokens.append(Token("eval", eval_text, move_idx=move_idx, level=level))
            
            if show_comments and curr.comment:
                cleaned = re.sub(r'\[%[^\]]+\]', '', curr.comment).replace('{', '').replace('}', '')
                cleaned = cleaned.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
                words = cleaned.split()
                for word in words:
                    current_block.tokens.append(Token("comment", word, level=level))
                        
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
