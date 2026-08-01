import sys
import os
import time
import re

# Ensure project src is in path for imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PyQt5.QtCore import Qt
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
)

import chess.pgn
from core.pgn_to_html import pgn_to_html, flatten_nodes_pgn_order

# Subclass QTextBrowser to support Arrow Navigation
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

class HtmlRendererDemo(QMainWindow):
    def __init__(self, pgn_path: str):
        super().__init__()
        self.setWindowTitle("HTML-based PGN Renderer Demo (setHtml Re-render)")
        self.resize(1100, 750)
        
        self.pgn_path = pgn_path
        self.flat_nodes = []
        self.active_index = -1
        self.is_dark = True
        
        self.setup_ui()
        self.load_pgn()
        self.options_changed()
        
    def setup_ui(self):
        # Main widget & layout
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
        
        sidebar_layout.addStretch()
        
        # Note describing the limitations
        sb_note = QLabel("Note: HTML rendering requires recreating and parsing the entire HTML document on EVERY move click to update styling.", sidebar)
        sb_note.setWordWrap(True)
        sb_note.setStyleSheet("font-size: 11px; color: #8A8A93; font-style: italic;")
        sidebar_layout.addWidget(sb_note)
        
        main_layout.addWidget(sidebar)
        
        # Content panel
        content_panel = QWidget(self)
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        
        self.status_label = QLabel("Loading...", self)
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        content_layout.addWidget(self.status_label)
        
        self.browser = KeyboardFriendlyBrowser(self)
        self.browser.demo_window = self
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self.on_anchor_clicked)
        content_layout.addWidget(self.browser)
        
        # Nav buttons
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
        
        self.stats_label = QLabel("Timing stats: N/A", self)
        self.stats_label.setStyleSheet("font-family: monospace; font-size: 13px;")
        content_layout.addWidget(self.stats_label)
        
        main_layout.addWidget(content_panel)
        
        self.cb_dark.stateChanged.connect(self.options_changed)
        self.cb_comments.stateChanged.connect(self.options_changed)
        self.cb_variations.stateChanged.connect(self.options_changed)

    def load_pgn(self):
        t0 = time.perf_counter()
        with open(self.pgn_path, "r", encoding="utf-8") as f:
            self.game = chess.pgn.read_game(f)
        self.t_read = time.perf_counter() - t0
        
        # Flatten nodes in PGN order
        self.flat_nodes = flatten_nodes_pgn_order(self.game)
        if self.flat_nodes:
            self.active_index = 0

    def options_changed(self):
        self.is_dark = self.cb_dark.isChecked()
        self.apply_theme()
        self.render_document()

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
            """)
            self.stats_label.setStyleSheet("font-family: monospace; font-size: 13px; color: #2980B9;")

    def render_document(self):
        t0 = time.perf_counter()
        
        highlight_node = self.flat_nodes[self.active_index] if (self.active_index >= 0 and self.active_index < len(self.flat_nodes)) else None
        
        t_gen_0 = time.perf_counter()
        html_code, _ = pgn_to_html(
            self.game,
            highlight_node=highlight_node,
            style=self.is_dark,
            font_family="Segoe UI"
        )
        t_gen = time.perf_counter() - t_gen_0
        
        t_browser_0 = time.perf_counter()
        self.browser.setHtml(html_code)
        t_browser = time.perf_counter() - t_browser_0
        
        t_total = time.perf_counter() - t0
        
        if self.active_index >= 0:
            self.browser.scrollToAnchor(f"m{self.active_index}")
            
        self.status_label.setText(
            f"PGN loaded: {len(self.flat_nodes)} moves. "
            f"Read PGN: {self.t_read*1000.0:.1f}ms | HTML Gen: {t_gen*1000.0:.1f}ms | setHtml Browser: {t_browser*1000.0:.1f}ms"
        )
        
        mem_mb = self.get_memory_usage()
        self.stats_label.setText(
            f"Active Move Highlight Time (setHtml Re-render): {t_total*1000.0:.3f} ms | Process RSS Memory: {mem_mb:.2f} MB"
        )

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

    def jump_to(self, index: int):
        if not self.flat_nodes or index < 0 or index >= len(self.flat_nodes):
            return
        self.active_index = index
        self.render_document()

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
        
    demo = HtmlRendererDemo(pgn_file)
    demo.show()
    sys.exit(app.exec_())
