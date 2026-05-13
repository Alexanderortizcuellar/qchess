import sys
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
                             QTextBrowser, QVBoxLayout, QWidget, QFrame)

class AnalysisWidget(QWidget):
    evaluationToggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(2)
        self.setLayout(self.main_layout)

        # --- Header Bar ---
        self.header_frame = QFrame()
        self.header_frame.setObjectName("AnalysisHeader")
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(8, 4, 8, 4)
        
        self.check_analysis = QCheckBox("Engine")
        self.check_analysis.setCursor(Qt.PointingHandCursor)
        self.check_analysis.toggled.connect(lambda v: self.evaluationToggled.emit(v))
        
        self.score_label = QLabel("0.00")
        self.score_label.setFont(QFont("Arial", 10, QFont.Bold))
        self.score_label.setAlignment(Qt.AlignCenter)
        
        self.depth_label = QLabel("depth 0")
        self.depth_label.setFont(QFont("Arial", 8))
        
        self.header_layout.addWidget(self.check_analysis)
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

    def set_line_text(self, text: str):
        moves = text.split()
        html = ""
        for i, move in enumerate(moves):
            if i % 2 == 0:
                html += f"<b>{move}</b> "
            else:
                html += f"{move} "
        self.lines_display.setHtml(html.strip())

    def clear(self):
        self.score_label.setText("0.00")
        self.depth_label.setText("depth 0")
        self.lines_display.clear()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = AnalysisWidget()
    w.set_theme(False)
    w.resize(350, 200)
    w.show()
    sys.exit(app.exec_())
