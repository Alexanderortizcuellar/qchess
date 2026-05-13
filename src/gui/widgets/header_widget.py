from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class PGNHeaderWidget(QWidget):
    def __init__(self, header_dict: dict):
        super().__init__()
        self.setWindowTitle("PGN Header Viewer")
        self.setStyleSheet(
            """
            QLabel { font-family: Segoe UI, sans-serif; font-size: 14px; }
            .header-box { border: 1px solid #ccc; border-radius: 6px; padding: 8px; background: #f9f9f9; }
            .title { font-weight: bold; }
        """
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        # Extract values safely
        white = header_dict.get("White", "Unknown")
        black = header_dict.get("Black", "Unknown")
        white_elo = header_dict.get("WhiteElo", "")
        black_elo = header_dict.get("BlackElo", "")
        result = header_dict.get("Result", "")
        event = header_dict.get("Event", "Unknown Event")
        date = header_dict.get("Date", "")

        # Format names with Elo if available
        white_display = f"{white} ({white_elo})" if white_elo else white
        black_display = f"{black} ({black_elo})" if black_elo else black

        # First row: [ White (Elo) | Result | Black (Elo) ]
        row1 = QHBoxLayout()
        row1.setSpacing(20)
        row1.addWidget(QLabel(white_display))
        lbl_result = QLabel(result)
        lbl_result.setAlignment(Qt.AlignCenter)
        lbl_result.setObjectName("title")
        row1.addWidget(lbl_result)
        black_display_lbl = QLabel(black_display)
        black_display_lbl.setAlignment(Qt.AlignRight)
        row1.addWidget(black_display_lbl)

        # Second row: [ Event | Date ]
        label = QLabel(f"{event} {date}")
        label.setAlignment(Qt.AlignCenter)
        # Wrap in frame for styling
        frame = QFrame()
        frame.setObjectName("header-box")
        frame_layout = QVBoxLayout(frame)
        frame_layout.addLayout(row1)
        frame_layout.addWidget(label)

        layout.addWidget(frame)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    pgn_header_widget = PGNHeaderWidget({"White": "White", "Black": "Black", "Result": "1-0", "Event": "Event", "Date": "Date"})
    pgn_header_widget.show()
    sys.exit(app.exec_())