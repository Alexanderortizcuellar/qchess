import os
import qtawesome as qta

from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QSize
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QStackedWidget,
    QStatusBar,
    QProgressBar,
    QAction,
    QToolBar,
)

from gui.widgets.game_list_table import GameListTableWidget
from core.indexer import PGNIndexerProcess


class HomeWindow(QMainWindow):
    """Application home window for browsing PGN databases.

    Signals:
        gameSelected(dict): Emitted when the user double-clicks a game row.
            The dict contains game metadata + raw PGN text.
        openEditorRequested(): Emitted when the user clicks "New Analysis".
        databaseOpened(str, str): Emitted with (db_path, pgn_path) when a database is loaded.
    """

    gameSelected = pyqtSignal(dict)
    openEditorRequested = pyqtSignal()
    databaseOpened = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QChess — Home")
        self.resize(1100, 700)
        self.is_dark = True

        self._current_pgn_path = None
        self._current_db_path = None

        # -- Indexer process --
        self.indexer = PGNIndexerProcess(self)
        self.indexer.finishedSuccessfully.connect(self._on_indexing_finished)
        self.indexer.indexingError.connect(self._on_indexing_error)
        self.indexer.progressMessage.connect(self._on_indexing_progress)

        # -- Central stacked widget (welcome vs. database browser) --
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Page 0: Welcome screen
        self.welcome_page = self._build_welcome_page()
        self.stack.addWidget(self.welcome_page)

        # Page 1: Database browser
        self.browser_page = self._build_browser_page()
        self.stack.addWidget(self.browser_page)

        self.stack.setCurrentIndex(0)

        # -- Status bar --
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

        # -- Toolbar --
        self._init_toolbar()

    # ──────────────────────── Welcome Page ────────────────────────

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(24)

        # Logo / icon
        icon_label = QLabel()
        assets_dir = self._assets_dir()
        icon_path = os.path.join(assets_dir, "icon.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaledToWidth(128, Qt.SmoothTransformation)
            icon_label.setPixmap(pix)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Title
        title = QLabel("QChess")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Segoe UI", 28, QFont.Bold))
        title.setStyleSheet("color: #e0e0e0;")
        layout.addWidget(title)

        subtitle = QLabel("Chess database browser and game analysis")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setStyleSheet("color: #888;")
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # ── Action buttons ──
        btn_layout = QVBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.setSpacing(12)

        self.open_db_btn = QPushButton(qta.icon("fa5s.database"), "  Open PGN Database...")
        self.open_db_btn.setFont(QFont("Segoe UI", 12))
        self.open_db_btn.setMinimumSize(280, 48)
        self.open_db_btn.setCursor(Qt.PointingHandCursor)
        self.open_db_btn.setStyleSheet(self._primary_button_style())
        self.open_db_btn.clicked.connect(self.open_pgn_database)
        btn_layout.addWidget(self.open_db_btn, alignment=Qt.AlignCenter)

        self.new_analysis_btn = QPushButton(qta.icon("fa5s.chess-board"), "  New Analysis")
        self.new_analysis_btn.setFont(QFont("Segoe UI", 11))
        self.new_analysis_btn.setMinimumSize(280, 42)
        self.new_analysis_btn.setCursor(Qt.PointingHandCursor)
        self.new_analysis_btn.setStyleSheet(self._secondary_button_style())
        self.new_analysis_btn.clicked.connect(self.openEditorRequested.emit)
        btn_layout.addWidget(self.new_analysis_btn, alignment=Qt.AlignCenter)

        layout.addLayout(btn_layout)

        layout.addSpacing(24)

        # ── Recent files ──
        recent_header = QLabel("Recent Databases")
        recent_header.setAlignment(Qt.AlignCenter)
        recent_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        recent_header.setStyleSheet("color: #aaa;")
        layout.addWidget(recent_header)

        self.recent_files_layout = QVBoxLayout()
        self.recent_files_layout.setAlignment(Qt.AlignCenter)
        self.recent_files_layout.setSpacing(4)
        layout.addLayout(self.recent_files_layout)

        self._populate_recent_files()

        # Push content to center vertically
        layout.addStretch()

        return page

    # ──────────────────────── Browser Page ────────────────────────

    def _build_browser_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Database info header
        self.db_info_label = QLabel()
        self.db_info_label.setFont(QFont("Segoe UI", 10))
        self.db_info_label.setStyleSheet("color: #aaa; padding: 4px;")
        layout.addWidget(self.db_info_label)

        # Game list table (virtual scrolling)
        self.game_table = GameListTableWidget(self)
        self.game_table.gameSelected.connect(self._on_game_selected)
        self.game_table.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self.game_table, 1)

        return page

    # ──────────────────────── Toolbar ────────────────────────

    def _init_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(self.toolbar)

        open_act = QAction(qta.icon("fa5s.folder-open", color="#a9aea7"), "Open Database", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_pgn_database)
        self.toolbar.addAction(open_act)

        new_act = QAction(qta.icon("fa5s.chess-board", color="#a9aea7"), "New Analysis", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.openEditorRequested.emit)
        self.toolbar.addAction(new_act)

        self.toolbar.addSeparator()

        home_act = QAction(qta.icon("fa5s.home", color="#a9aea7"), "Home", self)
        home_act.triggered.connect(self._go_home)
        self.toolbar.addAction(home_act)

    # ──────────────────────── Public API ────────────────────────

    def open_pgn_database(self):
        """Open a file dialog to select a PGN file, then index and display it."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open PGN Database", ".", "PGN Files (*.pgn);;All Files (*)"
        )
        if file_path:
            self._load_pgn(file_path)

    def load_pgn_path(self, pgn_path: str):
        """Programmatically open and index a PGN file."""
        self._load_pgn(pgn_path)

    # ──────────────────────── Internal ────────────────────────

    def _load_pgn(self, pgn_path: str):
        """Index (or reuse existing index of) a PGN file and load the game table."""
        self._current_pgn_path = pgn_path
        db_path = pgn_path + ".db"

        # Check if index already exists and is up-to-date
        if os.path.exists(db_path):
            pgn_mtime = os.path.getmtime(pgn_path)
            db_mtime = os.path.getmtime(db_path)
            if db_mtime >= pgn_mtime:
                # Index is fresh — load directly
                self._current_db_path = db_path
                self._show_database(db_path, pgn_path)
                self._add_to_recent(pgn_path)
                return

        # Need to index
        self.game_table.clear()
        self.status_bar.showMessage(f"Indexing {os.path.basename(pgn_path)}...")
        self.progress_bar.show()
        self.indexer.index_pgn(pgn_path)

    def _on_indexing_finished(self, db_path: str):
        self.progress_bar.hide()
        self.status_bar.showMessage("Indexing complete.", 5000)
        self._current_db_path = db_path
        self._show_database(db_path, self._current_pgn_path)
        self._add_to_recent(self._current_pgn_path)

    def _on_indexing_error(self, error_msg: str):
        self.progress_bar.hide()
        self.status_bar.showMessage(f"Indexing error: {error_msg}", 10000)

    def _on_indexing_progress(self, msg: str):
        self.status_bar.showMessage(msg)

    def _show_database(self, db_path: str, pgn_path: str):
        """Switch from welcome screen to database browser view."""
        self.game_table.load_db(db_path, pgn_path)
        basename = os.path.basename(pgn_path)
        self.db_info_label.setText(f"📁 {basename}")
        self.setWindowTitle(f"QChess — {basename}")
        self.stack.setCurrentIndex(1)
        self.databaseOpened.emit(db_path, pgn_path)

    def _on_game_selected(self, game_data: dict):
        self.gameSelected.emit(game_data)

    def _on_load_finished(self, total_rows: int):
        self.game_table.set_info_text(f"{total_rows:,} games")

    def _go_home(self):
        """Return to the welcome screen."""
        self.stack.setCurrentIndex(0)
        self.setWindowTitle("QChess — Home")

    # ──────────────────────── Recent Files ────────────────────────

    def _add_to_recent(self, pgn_path: str):
        settings = QSettings("QChessApp", "RecentFiles")
        recent = settings.value("recent_pgn_paths", [])
        if not isinstance(recent, list):
            recent = []
        # Remove duplicates, add to front
        if pgn_path in recent:
            recent.remove(pgn_path)
        recent.insert(0, pgn_path)
        recent = recent[:8]  # Keep at most 8 recent entries
        settings.setValue("recent_pgn_paths", recent)
        self._populate_recent_files()

    def _populate_recent_files(self):
        # Clear existing
        while self.recent_files_layout.count():
            child = self.recent_files_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        settings = QSettings("QChessApp", "RecentFiles")
        recent = settings.value("recent_pgn_paths", [])
        if not isinstance(recent, list):
            recent = []

        if not recent:
            no_recent = QLabel("No recent databases.")
            no_recent.setAlignment(Qt.AlignCenter)
            no_recent.setStyleSheet("color: #666; font-style: italic;")
            self.recent_files_layout.addWidget(no_recent)
            return

        for path in recent:
            if not os.path.exists(path):
                continue
            basename = os.path.basename(path)
            btn = QPushButton(f"  📄 {basename}")
            btn.setToolTip(path)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 10))
            btn.setMinimumWidth(280)
            btn.setStyleSheet(self._recent_button_style())
            btn.clicked.connect(lambda checked, p=path: self._load_pgn(p))
            self.recent_files_layout.addWidget(btn, alignment=Qt.AlignCenter)

    # ──────────────────────── Theming ────────────────────────

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        # Re-style buttons for the new theme
        self.open_db_btn.setStyleSheet(self._primary_button_style())
        self.new_analysis_btn.setStyleSheet(self._secondary_button_style())

    def _primary_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5aa0e9;
            }
            QPushButton:pressed {
                background-color: #3a80c9;
            }
        """

    def _secondary_button_style(self) -> str:
        return """
            QPushButton {
                background-color: transparent;
                color: #ccc;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #333;
                border-color: #777;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """

    def _recent_button_style(self) -> str:
        return """
            QPushButton {
                background-color: transparent;
                color: #aaa;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                color: #ddd;
            }
        """

    # ──────────────────────── Helpers ────────────────────────

    @staticmethod
    def _assets_dir() -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(os.path.dirname(os.path.dirname(current_dir)), "assets")
