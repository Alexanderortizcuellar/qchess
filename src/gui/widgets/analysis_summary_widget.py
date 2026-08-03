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
        self.vs_label.setStyleSheet("color: #e6912c;")
        
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
            bg_color = "#f1f1f1"
            card_bg = "#e1e1e1"
            card_border = "#cccccc"
            text_color = "#312e2b"
            
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

        # Traverse mainline
        curr = game
        while curr.variations:
            curr = curr.variations[0]
            if curr.move is None:
                continue
                
            board = curr.parent.board()
            turn = board.turn
            
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
                                
            if cls_val is not None:
                player_key = "white" if turn == chess.WHITE else "black"
                if cls_val not in stats[player_key]:
                    stats[player_key][cls_val] = 0
                stats[player_key][cls_val] += 1

        self.stats = stats
        self.render_stats()

    def clear_rows(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def render_stats(self):
        self.clear_rows()
        
        # Build the dynamic list of classifications to display.
        # This handles extensibility: if there are classifications in the stats that are not standard,
        # we can append them to the end of standard list.
        display_list = list(STANDARD_CLASSIFICATIONS)
        standard_ids = {item["id"] for item in display_list}
        
        all_ids = set(self.stats["white"].keys()).union(self.stats["black"].keys())
        for extra_id in all_ids:
            if extra_id not in standard_ids:
                # Add unknown classifications dynamically
                display_list.append({
                    "id": extra_id,
                    "name": f"Class {extra_id}",
                    "color_dark": "#90a4ae",
                    "color_light": "#78909c",
                    "text_color": "#ffffff"
                })

        # Add a header row
        header_row = QFrame()
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
            row_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {"#2b2824" if self.is_dark else "#e8e8e8"};
                    border: none;
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
