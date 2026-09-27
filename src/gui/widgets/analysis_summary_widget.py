import re
import chess
import chess.pgn
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
)

# Standard classifications list
STANDARD_CLASSIFICATIONS = [
    {"id": 7, "name": "Brilliant", "color_dark": "#28c2a4", "color_light": "#28c2a4", "text_color": "#ffffff"},
    {"id": 1, "name": "Best Move", "color_dark": "#4caf50", "color_light": "#2e7d32", "text_color": "#ffffff"},
    {"id": 2, "name": "Excellent", "color_dark": "#81c784", "color_light": "#4caf50", "text_color": "#ffffff"},
    {"id": 3, "name": "Good", "color_dark": "#a5d6a7", "color_light": "#81c784", "text_color": "#111111"},
    {"id": 4, "name": "Inaccuracy", "color_dark": "#ffd54f", "color_light": "#ffd54f", "text_color": "#111111"},
    {"id": 5, "name": "Mistake", "color_dark": "#ffa726", "color_light": "#e65100", "text_color": "#ffffff"},
    {"id": 8, "name": "Miss", "color_dark": "#ff8a80", "color_light": "#d32f2f", "text_color": "#ffffff"},
    {"id": 6, "name": "Blunder", "color_dark": "#ff5252", "color_light": "#b71c1c", "text_color": "#ffffff"},
]

class AnalysisSummaryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = True
        self.game = None
        self.stats = None
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)

        # Header card (Players)
        self.header_card = QFrame()
        self.header_card.setFrameShape(QFrame.StyledPanel)
        self.header_card.setObjectName("headerCard")
        
        header_layout = QHBoxLayout(self.header_card)
        header_layout.setContentsMargins(12, 12, 12, 12)
        
        self.white_label = QLabel("White")
        self.white_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.white_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        self.vs_label = QLabel("vs")
        self.vs_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.vs_label.setAlignment(Qt.AlignCenter)
        self.vs_label.setStyleSheet("color: #2563eb;" if not self.is_dark else "color: #3b82f6;")
        
        self.black_label = QLabel("Black")
        self.black_label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.black_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        header_layout.addWidget(self.white_label, 1)
        header_layout.addWidget(self.vs_label, 0)
        header_layout.addWidget(self.black_label, 1)
        
        self.main_layout.addWidget(self.header_card)

        # Scroll area for rows
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(6)
        
        self.scroll_area.setWidget(self.container)
        self.main_layout.addWidget(self.scroll_area, 1)
        
        self.update_theme_styles()

    def set_theme(self, is_dark):
        self.is_dark = is_dark
        self.update_theme_styles()
        if self.game:
            self.update_data(self.game)

    def update_theme_styles(self):
        if self.is_dark:
            bg_color = "#262421"
            card_bg = "#312e2b"
            card_border = "#403d39"
            text_color = "#ffffff"
        else:
            bg_color = "#ffffff"
            card_bg = "#f8fafc"
            card_border = "#e2e8f0"
            text_color = "#0f172a"
            
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                color: {text_color};
            }}
            QFrame#headerCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
            }}
            QScrollArea {{
                background-color: transparent;
            }}
        """)
        
        self.white_label.setStyleSheet(f"color: {text_color};")
        self.black_label.setStyleSheet(f"color: {text_color};")
        self.vs_label.setStyleSheet("color: #3b82f6;" if self.is_dark else "color: #2563eb;")

    def update_data(self, game):
        self.game = game
        if not game:
            self.white_label.setText("White")
            self.black_label.setText("Black")
            self.clear_rows()
            return

        # Set player names
        white_player = game.headers.get("White", "White")
        black_player = game.headers.get("Black", "Black")
        self.white_label.setText(white_player)
        self.black_label.setText(black_player)

        # Count classifications
        stats = {
            "white": {},
            "black": {},
        }
        
        # Initialize stats counts
        for item in STANDARD_CLASSIFICATIONS:
            stats["white"][item["id"]] = 0
            stats["black"][item["id"]] = 0
            
        self.stats = stats
        
        # Traverse mainline
        curr = game
        while curr.variations:
            curr = curr.variations[0]
            if curr.move is None:
                continue
                
            board = curr.parent.board()
            turn = "white" if board.turn == chess.WHITE else "black"
            
            cls_val = None
            if hasattr(curr, "nags") and curr.nags:
                from core.move_manager import NAG_TO_CLS
                for nag in sorted(curr.nags):
                    if nag in NAG_TO_CLS:
                        cls_val = NAG_TO_CLS[nag]
                        break
                        
            if cls_val is None and curr.comment:
                cls_match = re.search(r'\[%cls\s+(\d+)\]', curr.comment)
                if cls_match:
                    cls_val = int(cls_match.group(1))
                                
            if cls_val is not None:
                if cls_val not in stats[turn]:
                    stats[turn][cls_val] = 0
                stats[turn][cls_val] += 1
            
        self.render_rows()

    def clear_rows(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def render_rows(self):
        self.clear_rows()
        if not self.stats:
            return

        # Filter out classifications with 0 occurrences on both sides
        display_list = []
        for item in STANDARD_CLASSIFICATIONS:
            cid = item["id"]
            if self.stats["white"].get(cid, 0) > 0 or self.stats["black"].get(cid, 0) > 0:
                display_list.append(item)
                
        if not display_list:
            lbl = QLabel("No move classifications found.\nRun game review or analysis first.")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #8b8987; font-style: italic; padding: 20px;")
            self.container_layout.addWidget(lbl)
            return

        # Header Row
        header_row = QFrame()
        header_row.setStyleSheet("background: transparent;")
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(8, 4, 8, 4)
        
        lbl_w = QLabel("W")
        lbl_w.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl_w.setAlignment(Qt.AlignCenter)
        lbl_w.setFixedWidth(40)
        
        lbl_cat = QLabel("Category")
        lbl_cat.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl_cat.setAlignment(Qt.AlignCenter)
        
        lbl_b = QLabel("B")
        lbl_b.setFont(QFont("Segoe UI", 9, QFont.Bold))
        lbl_b.setAlignment(Qt.AlignCenter)
        lbl_b.setFixedWidth(40)
        
        header_layout.addWidget(lbl_w)
        header_layout.addWidget(lbl_cat, 1)
        header_layout.addWidget(lbl_b)
        
        self.container_layout.addWidget(header_row)

        # Render rows
        for item in display_list:
            cls_id = item["id"]
            name = item["name"]
            color = item["color_dark"] if self.is_dark else item["color_light"]
            badge_text_col = item["text_color"]
            
            w_count = self.stats["white"].get(cls_id, 0)
            b_count = self.stats["black"].get(cls_id, 0)
            
            # Row frame
            row_frame = QFrame()
            row_frame.setFrameShape(QFrame.StyledPanel)
            row_bg = "#2b2824" if self.is_dark else "#f8fafc"
            row_border = "none" if self.is_dark else "1px solid #e2e8f0"
            row_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {row_bg};
                    border: {row_border};
                    border-radius: 4px;
                }}
            """)
            
            row_layout = QHBoxLayout(row_frame)
            row_layout.setContentsMargins(8, 6, 8, 6)
            row_layout.setSpacing(10)
            
            # White count
            w_label = QLabel(str(w_count))
            w_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
            w_label.setAlignment(Qt.AlignCenter)
            w_label.setFixedWidth(40)
            
            # Category Badge
            cat_badge = QLabel(name)
            cat_badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
            cat_badge.setAlignment(Qt.AlignCenter)
            cat_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    color: {badge_text_col};
                    border-radius: 3px;
                    padding: 2px 6px;
                }}
            """)
            
            # Black count
            b_label = QLabel(str(b_count))
            b_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
            b_label.setAlignment(Qt.AlignCenter)
            b_label.setFixedWidth(40)
            
            row_layout.addWidget(w_label)
            row_layout.addWidget(cat_badge, 1)
            row_layout.addWidget(b_label)
            
            self.container_layout.addWidget(row_frame)
            
        # Add stretch at the end
        self.container_layout.addStretch(1)
