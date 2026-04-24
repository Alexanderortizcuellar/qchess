import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QVBoxLayout, QWidget)


class LineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(5)

        # Score label
        self.score_label = QLabel("0.20")
        self.score_label.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(self.score_label)

        # Engine line text
        self.line = QTextEdit()
        # self.line.setFont(QFont("Courier New", 10))
        self.line.setStyleSheet("font-size:18px;font-family: Noto Sans;")
        self.line.setFixedHeight(28)  # Single-line height
        self.line.setLineWrapMode(QTextEdit.NoWrap)
        self.line.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.line.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        layout.addWidget(self.line)

        # Expand/Collapse button
        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedWidth(30)
        self.toggle_btn.clicked.connect(self.toggle_expand)
        layout.addWidget(self.toggle_btn)

        self.expanded = False

    def toggle_expand(self):
        if self.expanded:
            self.line.setLineWrapMode(QTextEdit.NoWrap)
            self.line.setFixedHeight(28)
            self.line.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.toggle_btn.setText("▼")
        else:
            self.line.setLineWrapMode(QTextEdit.FixedPixelWidth)
            self.line.setFixedHeight(100)  # Expand height
            self.line.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.toggle_btn.setText("▲")
        self.expanded = not self.expanded


class AnalysisWidget(QWidget):
    evaluationToggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)

        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)
        self.check_analysis = QCheckBox("Analysis")
        self.check_analysis.setFont(QFont("Arial", 11, QFont.Bold))
        self.check_analysis.toggled.connect(
            lambda value: self.evaluationToggled.emit(value)
        )
        self.depth_label = QLabel("depth=0")
        self.depth_label.setFont(QFont("Arial", 10))
        header_layout.addWidget(self.check_analysis)
        header_layout.addWidget(self.depth_label)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Lines container
        self.lines_layout = QVBoxLayout()
        self.lines_layout.setSpacing(8)
        main_layout.addLayout(self.lines_layout)
        self.line_widget = LineWidget(self)
        # Add sample lines
        self.lines_layout.addWidget(self.line_widget)

    def set_depth(self, depth: str):
        self.depth_label.setText(depth)

    def set_score(self, score: str):
        self.line_widget.score_label.setText(score)

    def set_line_text(self, text: str):
        self.line_widget.line.setPlainText(text)

    def togle_analysis(self, value: bool):
        pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Modern look
    widget = AnalysisWidget()
    widget.setWindowTitle("Engine Evaluation")
    widget.resize(400, 250)
    widget.show()
    sys.exit(app.exec_())
