import os
import qtawesome as qta

from PyQt5.QtCore import Qt, pyqtSignal, QSettings, QSize
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QStackedWidget,
    QStatusBar,
    QProgressBar,
    QAction,
    QToolBar,
    QToolButton,
    QMenu,
    QMessageBox,
    QDialog,
)

from gui.widgets.game_list_table import GameListTableWidget, GameListTableModel
from gui.widgets.repertoire_tree_widget import RepertoireTreeWidget
from gui.dialogs.advanced_search_dialog import AdvancedSearchDialog
from gui.dialogs.add_game_dialog import AddGameDialog
from gui.dialogs.build_pos_index_dialog import BuildPosIndexDialog
from gui.dialogs.database_settings_dialog import DatabaseSettingsDialog
from core.scid_client import ScidClient
from core.repertoire_db import RepertoireRepository


class HomeWindow(QMainWindow):
    """Application home window for browsing PGN and SCID databases with advanced search.

    Signals:
        gameSelected(dict): Emitted when the user double-clicks a game row.
            The dict contains game metadata + raw PGN text.
        openEditorRequested(): Emitted when the user clicks "New Analysis".
        databaseOpened(str, str): Emitted with (db_path, pgn_path) when a database is loaded.
        repertoireOpenRequested(int, str): Emitted when the user opens a repertoire.
            Carries (node_id, pgn_text).
    """

    gameSelected = pyqtSignal(dict)
    openEditorRequested = pyqtSignal()
    databaseOpened = pyqtSignal(str, str)
    repertoireOpenRequested = pyqtSignal(int, str)

    SCID_EXTENSIONS = {".si4", ".si5", ".sg4", ".sg5", ".sn4", ".sn5"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QChess — Home")
        self.resize(1200, 700)
        self.is_dark = True

        self._current_db_path = None
        self._current_search_filter = None

        # -- ScidClient backend process --
        self.scid_client = ScidClient(self)
        self.scid_client.search_progress.connect(self._on_search_progress)
        self.scid_client.import_progress.connect(self._on_import_progress)
        self.scid_client.export_progress.connect(self._on_export_progress)
        self.scid_client.process_error.connect(self._on_scid_error)

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
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMaximumWidth(220)
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)

        # -- Repertoire dock --
        self._init_repertoire_dock()

        # -- Toolbar & Menu --
        self._init_toolbar()

    # ──────────────────────── Repertoire Dock ────────────────────────

    def _init_repertoire_dock(self):
        """Create the Repertoires dock panel and attach it on the left."""
        data_dir = os.path.join(os.path.expanduser("~"), ".qchess")
        db_path = os.path.join(data_dir, "repertoires.db")

        repo = RepertoireRepository(db_path)

        self.repertoire_tree = RepertoireTreeWidget(repo)
        self.repertoire_tree.repertoireOpenRequested.connect(
            self.repertoireOpenRequested.emit
        )

        dock = QDockWidget("Repertoires", self)
        dock.setObjectName("RepertoiresDock")
        dock.setWidget(self.repertoire_tree)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setFeatures(
            QDockWidget.DockWidgetMovable |
            QDockWidget.DockWidgetFloatable |
            QDockWidget.DockWidgetClosable
        )
        dock.setMinimumWidth(200)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self._repertoire_dock = dock

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

        subtitle = QLabel("Chess database browser, analysis & management")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setStyleSheet("color: #888;")
        layout.addWidget(subtitle)

        layout.addSpacing(16)

        # Action buttons
        btn_layout = QVBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.setSpacing(10)

        self.create_db_btn = QPushButton(qta.icon("fa5s.plus-circle"), "  New SCID Database...")
        self.create_db_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.create_db_btn.setMinimumSize(280, 44)
        self.create_db_btn.setCursor(Qt.PointingHandCursor)
        self.create_db_btn.setStyleSheet(self._primary_button_style())
        self.create_db_btn.clicked.connect(self.create_new_database)
        btn_layout.addWidget(self.create_db_btn, alignment=Qt.AlignCenter)

        self.open_db_btn = QPushButton(qta.icon("fa5s.database"), "  Open Chess Database...")
        self.open_db_btn.setFont(QFont("Segoe UI", 11))
        self.open_db_btn.setMinimumSize(280, 44)
        self.open_db_btn.setCursor(Qt.PointingHandCursor)
        self.open_db_btn.setStyleSheet(self._secondary_button_style())
        self.open_db_btn.clicked.connect(self.open_database)
        btn_layout.addWidget(self.open_db_btn, alignment=Qt.AlignCenter)

        self.new_analysis_btn = QPushButton(qta.icon("fa5s.chess-board"), "  New Analysis")
        self.new_analysis_btn.setFont(QFont("Segoe UI", 11))
        self.new_analysis_btn.setMinimumSize(280, 40)
        self.new_analysis_btn.setCursor(Qt.PointingHandCursor)
        self.new_analysis_btn.setStyleSheet(self._secondary_button_style())
        self.new_analysis_btn.clicked.connect(self.openEditorRequested.emit)
        btn_layout.addWidget(self.new_analysis_btn, alignment=Qt.AlignCenter)

        layout.addLayout(btn_layout)
        layout.addSpacing(20)

        # Recent files
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
        layout.addStretch()
        return page

    # ──────────────────────── Browser Page ────────────────────────

    def _build_browser_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Top header row with database info and active search indicator
        header_row = QHBoxLayout()
        self.db_info_label = QLabel()
        self.db_info_label.setFont(QFont("Segoe UI", 10))
        self.db_info_label.setStyleSheet("color: #aaa; padding: 4px;")
        header_row.addWidget(self.db_info_label)
        header_row.addStretch()

        self.btn_clear_search = QPushButton("✕ Clear Search Filter")
        self.btn_clear_search.setStyleSheet(
            "background-color: #c62828; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px;"
        )
        self.btn_clear_search.setCursor(Qt.PointingHandCursor)
        self.btn_clear_search.clicked.connect(self.clear_search_filter)
        self.btn_clear_search.hide()
        header_row.addWidget(self.btn_clear_search)

        layout.addLayout(header_row)

        # Game list table (virtual scrolling backed by scid_client)
        self.game_table = GameListTableWidget(self.scid_client, self)
        self.game_table.gameSelected.connect(self._on_game_selected)
        self.game_table.loadFinished.connect(self._on_load_finished)
        self.game_table.gameDeleted.connect(lambda gid: self.status_bar.showMessage(f"Game #{gid + 1} marked as DELETED and saved.", 5000))
        self.game_table.gameUndeleted.connect(lambda gid: self.status_bar.showMessage(f"Game #{gid + 1} restored and saved.", 5000))
        layout.addWidget(self.game_table, 1)

        return page

    # ──────────────────────── Toolbar & Menu ────────────────────────

    def _init_toolbar(self):
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(self.toolbar)

        new_db_act = QAction(qta.icon("fa5s.plus", color="#a9aea7"), "New Database", self)
        new_db_act.setToolTip("Create a new SCID database [Ctrl+Shift+N]")
        new_db_act.setShortcut("Ctrl+Shift+N")
        new_db_act.triggered.connect(self.create_new_database)
        self.toolbar.addAction(new_db_act)

        open_act = QAction(qta.icon("fa5s.folder-open", color="#a9aea7"), "Open Database", self)
        open_act.setShortcut("Ctrl+O")
        open_act.setToolTip("Open database file [Ctrl+O]")
        open_act.triggered.connect(self.open_database)
        self.toolbar.addAction(open_act)

        self.toolbar.addSeparator()

        import_act = QAction(qta.icon("fa5s.file-import", color="#a9aea7"), "Import PGN", self)
        import_act.setToolTip("Import external PGN file into active database [Ctrl+I]")
        import_act.setShortcut("Ctrl+I")
        import_act.triggered.connect(self.import_pgn_into_database)
        self.toolbar.addAction(import_act)

        add_game_act = QAction(qta.icon("fa5s.plus-square", color="#a9aea7"), "Add Game", self)
        add_game_act.setToolTip("Add a new game to active database [Ctrl+Shift+A]")
        add_game_act.setShortcut("Ctrl+Shift+A")
        add_game_act.triggered.connect(self.add_game_dialog)
        self.toolbar.addAction(add_game_act)

        del_game_act = QAction(qta.icon("fa5s.trash-alt", color="#f87171"), "Delete Game", self)
        del_game_act.setToolTip("Delete / mark selected game as deleted [Delete]")
        del_game_act.triggered.connect(self.game_table.delete_selected_game)
        self.toolbar.addAction(del_game_act)

        self.toolbar.addSeparator()

        # Advanced Search Action
        self.search_act = QAction(qta.icon("fa5s.search", color="#a9aea7"), "Search Games", self)
        self.search_act.setShortcut("Ctrl+F")
        self.search_act.setToolTip("Advanced Search (Game Info, Position / Board, Material) [Ctrl+F]")
        self.search_act.triggered.connect(lambda: self.open_search_dialog())
        self.toolbar.addAction(self.search_act)

        build_idx_act = QAction(qta.icon("fa5s.bolt", color="#f59e0b"), "Build Position Index", self)
        build_idx_act.setToolTip("Build Fast Companion Position Index (.pos.idx) [Ctrl+Shift+B]")
        build_idx_act.setShortcut("Ctrl+Shift+B")
        build_idx_act.triggered.connect(self.build_position_index)
        self.toolbar.addAction(build_idx_act)

        settings_act = QAction(qta.icon("fa5s.cog", color="#a9aea7"), "Search Settings", self)
        settings_act.setToolTip("Configure worker threads and search performance [Ctrl+Alt+S]")
        settings_act.setShortcut("Ctrl+Alt+S")
        settings_act.triggered.connect(self.open_database_settings)
        self.toolbar.addAction(settings_act)

        self.toolbar.addSeparator()

        new_act = QAction(qta.icon("fa5s.chess-board", color="#a9aea7"), "New Analysis", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.openEditorRequested.emit)
        self.toolbar.addAction(new_act)

        self.toolbar.addSeparator()

        home_act = QAction(qta.icon("fa5s.home", color="#a9aea7"), "Home", self)
        home_act.triggered.connect(self._go_home)
        self.toolbar.addAction(home_act)

        self.toolbar.addSeparator()

        # Columns settings button with popup menu
        self.columns_btn = QToolButton(self)
        self.columns_btn.setIcon(qta.icon("fa5s.columns", color="#a9aea7"))
        self.columns_btn.setText("Columns")
        self.columns_btn.setToolTip("Configure visible columns in the game list")
        self.columns_btn.setPopupMode(QToolButton.InstantPopup)
        self.columns_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.columns_menu = QMenu(self.columns_btn)
        self.columns_btn.setMenu(self.columns_menu)
        self.columns_menu.aboutToShow.connect(self._populate_columns_menu)
        self.toolbar.addWidget(self.columns_btn)

        # Menu bar
        self._init_menubar()

    def _init_menubar(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")
        new_db_act = file_menu.addAction(qta.icon("fa5s.plus", color="#a9aea7"), "New SCID Database...")
        new_db_act.setShortcut("Ctrl+Shift+N")
        new_db_act.triggered.connect(self.create_new_database)

        open_act = file_menu.addAction(qta.icon("fa5s.folder-open", color="#a9aea7"), "Open Database...")
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_database)

        new_act = file_menu.addAction(qta.icon("fa5s.chess-board", color="#a9aea7"), "New Analysis")
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.openEditorRequested.emit)

        file_menu.addSeparator()

        import_act = file_menu.addAction(qta.icon("fa5s.file-import", color="#a9aea7"), "Import PGN into Database...")
        import_act.setShortcut("Ctrl+I")
        import_act.triggered.connect(self.import_pgn_into_database)

        export_act = file_menu.addAction(qta.icon("fa5s.file-export", color="#a9aea7"), "Export Database to PGN...")
        export_act.setShortcut("Ctrl+E")
        export_act.triggered.connect(self.export_database_to_pgn)

        file_menu.addSeparator()

        save_db_act = file_menu.addAction(qta.icon("fa5s.save", color="#a9aea7"), "Save Database")
        save_db_act.setShortcut("Ctrl+S")
        save_db_act.triggered.connect(self.save_database)

        compact_db_act = file_menu.addAction(qta.icon("fa5s.compress-arrows-alt", color="#a9aea7"), "Compact Database (Purge Deleted)")
        compact_db_act.triggered.connect(self.compact_database)

        file_menu.addSeparator()

        home_act = file_menu.addAction(qta.icon("fa5s.home", color="#a9aea7"), "Go to Welcome Screen")
        home_act.triggered.connect(self._go_home)

        # Game Menu
        game_menu = menubar.addMenu("&Game")
        add_game_act = game_menu.addAction(qta.icon("fa5s.plus-square", color="#a9aea7"), "Add Game to Database...")
        add_game_act.setShortcut("Ctrl+Shift+A")
        add_game_act.triggered.connect(self.add_game_dialog)

        del_game_act = game_menu.addAction(qta.icon("fa5s.trash-alt", color="#f87171"), "Delete Selected Game")
        del_game_act.setShortcut("Delete")
        del_game_act.triggered.connect(self.game_table.delete_selected_game)

        undel_game_act = game_menu.addAction(qta.icon("fa5s.undo", color="#4ade80"), "Undelete Selected Game")
        undel_game_act.triggered.connect(self.game_table.undelete_selected_game)

        game_menu.addSeparator()

        copy_pgn_act = game_menu.addAction(qta.icon("fa5s.copy", color="#a9aea7"), "Copy Selected Game PGN")
        copy_pgn_act.setShortcut("Ctrl+C")
        copy_pgn_act.triggered.connect(self.game_table.copy_selected_game_pgn)

        # Search Menu
        search_menu = menubar.addMenu("&Search")
        search_act = search_menu.addAction(qta.icon("fa5s.search", color="#a9aea7"), "Advanced Search...")
        search_act.setShortcut("Ctrl+F")
        search_act.triggered.connect(lambda: self.open_search_dialog())

        clear_search_act = search_menu.addAction(qta.icon("fa5s.times", color="#a9aea7"), "Clear Search Filter")
        clear_search_act.triggered.connect(self.clear_search_filter)

        search_menu.addSeparator()

        build_idx_act = search_menu.addAction(qta.icon("fa5s.bolt", color="#f59e0b"), "Build Position Index (.pos.idx)...")
        build_idx_act.setShortcut("Ctrl+Shift+B")
        build_idx_act.triggered.connect(self.build_position_index)

        search_menu.addSeparator()

        settings_act = search_menu.addAction(qta.icon("fa5s.sliders-h", color="#a9aea7"), "Search & Thread Settings...")
        settings_act.setShortcut("Ctrl+Alt+S")
        settings_act.triggered.connect(self.open_database_settings)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")
        t_build_act = tools_menu.addAction(qta.icon("fa5s.bolt", color="#f59e0b"), "Build Fast Position Index (.pos.idx)...")
        t_build_act.setShortcut("Ctrl+Shift+B")
        t_build_act.triggered.connect(self.build_position_index)

        tools_menu.addSeparator()

        t_settings_act = tools_menu.addAction(qta.icon("fa5s.cog", color="#a9aea7"), "Search & Performance Settings...")
        t_settings_act.setShortcut("Ctrl+Alt+S")
        t_settings_act.triggered.connect(self.open_database_settings)

        # View Menu
        view_menu = menubar.addMenu("&View")
        toggle_act = self._repertoire_dock.toggleViewAction()
        toggle_act.setText("Repertoires")
        toggle_act.setShortcut("Ctrl+Shift+E")
        toggle_act.setIcon(qta.icon("fa5s.chess-board", color="#a9aea7"))
        view_menu.addAction(toggle_act)

        view_menu.addSeparator()

        columns_submenu = view_menu.addMenu(qta.icon("fa5s.columns", color="#a9aea7"), "Columns")
        columns_submenu.aboutToShow.connect(lambda: self._populate_menu_columns(columns_submenu))

    def _populate_columns_menu(self):
        self._populate_menu_columns(self.columns_menu)

    def _populate_menu_columns(self, menu: QMenu):
        menu.clear()
        header = self.game_table.table.horizontalHeader()
        for idx in range(len(GameListTableModel.HEADERS)):
            name = GameListTableModel.HEADERS[idx]
            act = menu.addAction(name)
            act.setCheckable(True)
            act.setChecked(not header.isSectionHidden(idx))
            act.triggered.connect(
                lambda checked, col_idx=idx: self.game_table.toggle_column_visibility(col_idx, checked)
            )

        menu.addSeparator()
        config_act = menu.addAction("Configure Columns...")
        config_act.setIcon(qta.icon("fa5s.sliders-h", color="#a9aea7"))
        config_act.triggered.connect(self.game_table.configure_columns)

    # ──────────────────────── Search Dialog API ────────────────────────

    def open_search_dialog(self, initial_filter: dict = None):
        """Open the ChessBase-style Advanced Multi-Tab Search Dialog."""
        if not self._current_db_path:
            QMessageBox.information(
                self,
                "No Database Opened",
                "Please open a PGN or SCID database before searching."
            )
            return

        f = initial_filter if initial_filter is not None else self._current_search_filter
        dlg = AdvancedSearchDialog(current_filter=f, parent=self)
        if dlg.exec_() == AdvancedSearchDialog.Accepted:
            filter_dict = dlg.get_filter_dict()
            self._execute_advanced_search(filter_dict)

    def _execute_advanced_search(self, filter_dict: dict):
        """Execute search using the high-performance scid-mgr backend."""
        self._current_search_filter = filter_dict
        if not self._current_db_path:
            return

        self.status_bar.showMessage("Searching database with scid-mgr...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        if not self.scid_client.is_running():
            ok = self.scid_client.start(self._current_db_path)
            if not ok:
                self.progress_bar.hide()
                return

        def on_query_finished(resp: dict):
            self.progress_bar.hide()
            if resp.get("status") == "ok":
                data = resp.get("data", {})
                total = data.get("total", 0)
                self.game_table.model.filters = dict(filter_dict) if filter_dict else {}
                self.btn_clear_search.show()
                self.status_bar.showMessage(f"Search complete: {total:,} games matched.", 8000)
                self.game_table.set_info_text(f"{total:,} games matched (Filter Active)")
            else:
                err = resp.get("error", "Unknown error")
                self.status_bar.showMessage(f"Search failed: {err}", 8000)

        self.scid_client.query_games(page=0, page_size=100, filter_dict=filter_dict, callback=on_query_finished)

    def clear_search_filter(self):
        """Clears active search filters and resets table to full database."""
        self._current_search_filter = None
        self.btn_clear_search.hide()

        if self.scid_client.is_running():
            self.game_table.model.set_filters({})
            self.status_bar.showMessage("Search filter cleared.", 4000)

    def _on_search_progress(self, progress_data: dict):
        percent = int(progress_data.get("percent", 0))
        scanned = progress_data.get("scanned", 0)
        total = progress_data.get("total", 0)
        matches = progress_data.get("matches", 0)
        self.progress_bar.setValue(percent)
        self.status_bar.showMessage(f"Searching: {scanned:,}/{total:,} scanned ({percent}%) — {matches:,} matches found")

    def _on_scid_error(self, err_msg: str):
        self.status_bar.showMessage(f"[Backend Error] {err_msg}", 8000)

    # ──────────────────────── Public Database Management API ────────────────────────

    def create_new_database(self):
        """Create a new SCID database (.si5) via scid-mgr backend."""
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Create New SCID Database",
            ".",
            "SCID v5 Database (*.si5);;SCID v4 Database (*.si4)"
        )
        if not file_path:
            return

        fmt = "si4" if "si4" in selected_filter.lower() or file_path.endswith(".si4") else "si5"
        base_path = os.path.splitext(file_path)[0]
        full_path = f"{base_path}.{fmt}"

        if not self.scid_client.is_running():
            settings = QSettings("QChessApp", "SearchConfig")
            threads = int(settings.value("worker_threads", 0))
            ok = self.scid_client.start(threads=threads if threads > 0 else None)
            if not ok:
                return

        self.status_bar.showMessage(f"Creating {os.path.basename(full_path)}...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        def on_create_resp(resp: dict):
            self.progress_bar.hide()
            if resp.get("status") == "ok":
                self._current_db_path = full_path
                self._current_db_stats = resp.get("data", {}).get("stats", {})
                self._current_search_filter = None
                self.btn_clear_search.hide()
                basename = os.path.basename(full_path)
                self.game_table.load_database(0, None)
                self.db_info_label.setText(f"📁 [{fmt.upper()}] {basename}")
                self.setWindowTitle(f"QChess — {basename}")
                self.stack.setCurrentIndex(1)
                self.status_bar.showMessage(f"Created new database: {basename}", 6000)
                self._add_to_recent(full_path)
                self.databaseOpened.emit(full_path, full_path)
            else:
                err = resp.get("error", "Failed to create database")
                QMessageBox.critical(self, "Creation Failed", f"Could not create database:\n{err}")
                self.status_bar.showMessage(f"Error: {err}", 8000)

        self.scid_client.create_database(full_path, fmt, callback=on_create_resp)

    def import_pgn_into_database(self):
        """Import an external PGN file into the active SCID database."""
        if not self._current_db_path:
            QMessageBox.information(
                self,
                "No Database Opened",
                "Please open or create a SCID (.si5) database before importing PGN."
            )
            return

        ext = os.path.splitext(self._current_db_path)[1].lower()
        if ext not in self.SCID_EXTENSIONS:
            QMessageBox.warning(
                self,
                "Unsupported Operation",
                "Importing is only supported on SCID (.si5/.si4) databases.\nPlease open or create a SCID database first."
            )
            return

        pgn_path, _ = QFileDialog.getOpenFileName(
            self, "Select PGN to Import", ".", "PGN Files (*.pgn);;All Files (*)"
        )
        if not pgn_path:
            return

        self.status_bar.showMessage(f"Importing {os.path.basename(pgn_path)} into database...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        def on_import_resp(resp: dict):
            self.progress_bar.hide()
            if resp.get("status") == "ok":
                data = resp.get("data", {})
                imported = data.get("imported", 0)
                errors = data.get("errors", 0)
                stats = data.get("stats", {})
                total = stats.get("total_games", 0)

                # Persist imported games and reload table
                self.scid_client.save_database()
                self.game_table.load_database(total, None)
                self.status_bar.showMessage(f"Import complete: {imported:,} games imported ({errors} errors).", 8000)
                QMessageBox.information(
                    self,
                    "Import Complete",
                    f"Successfully imported {imported:,} games into the database.\nErrors encountered: {errors}\nTotal games in database: {total:,}"
                )
            else:
                err = resp.get("error", "Unknown error during import")
                QMessageBox.critical(self, "Import Failed", f"Failed to import PGN:\n{err}")
                self.status_bar.showMessage(f"Import error: {err}", 8000)

        self.scid_client.import_pgn(pgn_path, callback=on_import_resp)

    def export_database_to_pgn(self):
        """Export the active database games to a PGN file."""
        if not self._current_db_path:
            QMessageBox.information(
                self,
                "No Database Opened",
                "Please open a database before exporting."
            )
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self, "Export Database to PGN", ".", "PGN Files (*.pgn);;All Files (*)"
        )
        if not out_path:
            return

        if not out_path.lower().endswith(".pgn"):
            out_path += ".pgn"

        self.status_bar.showMessage(f"Exporting database to {os.path.basename(out_path)}...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        def on_export_resp(resp: dict):
            self.progress_bar.hide()
            if resp.get("status") == "ok":
                self.status_bar.showMessage(f"Export finished: {os.path.basename(out_path)}", 8000)
                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Database games successfully exported to:\n{out_path}"
                )
            else:
                err = resp.get("error", "Unknown export error")
                QMessageBox.critical(self, "Export Failed", f"Failed to export database:\n{err}")
                self.status_bar.showMessage(f"Export error: {err}", 8000)

        self.scid_client.export_pgn(out_path, callback=on_export_resp)

    def add_game_dialog(self):
        """Open dialog to add a new game into the active SCID database."""
        if not self._current_db_path:
            QMessageBox.information(
                self,
                "No Database Opened",
                "Please open or create a SCID database before adding games."
            )
            return

        ext = os.path.splitext(self._current_db_path)[1].lower()
        if ext not in self.SCID_EXTENSIONS:
            QMessageBox.warning(
                self,
                "Unsupported Operation",
                "Adding games directly is only supported on SCID (.si5/.si4) databases."
            )
            return

        dlg = AddGameDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            pgn_text = dlg.get_pgn_text()
            self.add_game_to_active_db(pgn_text)

    def add_game_to_active_db(self, pgn_text: str):
        """Add game PGN string to the active database backend and reload table."""
        if not self.scid_client.is_running() or not self._current_db_path:
            return

        def on_added(resp: dict):
            if resp.get("status") == "ok":
                data = resp.get("data", {})
                new_idx = data.get("index", 0)
                total = data.get("total", 0)
                self.scid_client.save_database()
                self.game_table.load_database(total, None)
                self.status_bar.showMessage(f"Game added as #{new_idx + 1}. Total games: {total:,}", 6000)
            else:
                err = resp.get("error", "Failed to add game")
                QMessageBox.critical(self, "Error Adding Game", f"Could not add game:\n{err}")

        self.scid_client.add_game(pgn_text, callback=on_added)

    def save_database(self):
        """Save pending changes in the database to disk."""
        if not self.scid_client.is_running() or not self._current_db_path:
            return

        def on_saved(resp: dict):
            if resp.get("status") == "ok":
                self.status_bar.showMessage("Database saved to disk.", 4000)
            else:
                err = resp.get("error", "Save failed")
                self.status_bar.showMessage(f"Save error: {err}", 6000)

        self.scid_client.save_database(callback=on_saved)

    def compact_database(self):
        """Permanently purge deleted games and optimize SCID database storage."""
        if not self._current_db_path:
            return
        ext = os.path.splitext(self._current_db_path)[1].lower()
        if ext not in self.SCID_EXTENSIONS:
            QMessageBox.information(self, "Info", "Compacting is only applicable to SCID (.si5) databases.")
            return

        ret = QMessageBox.question(
            self,
            "Compact Database",
            "Compacting will permanently remove all games marked as DELETED and reclaim disk space.\n\nDo you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if ret != QMessageBox.Yes:
            return

        self.status_bar.showMessage("Compacting database...")

        def on_compact(resp: dict):
            if resp.get("status") == "ok":
                reclaimed = resp.get("data", {}).get("reclaimed_bytes", 0)
                self.scid_client.save_database()
                self.game_table.model.invalidate_cache_and_reload()
                self.status_bar.showMessage(f"Database compacted. Reclaimed {reclaimed:,} bytes.", 6000)
                QMessageBox.information(
                    self,
                    "Compaction Complete",
                    f"Compaction finished successfully.\nReclaimed storage: {reclaimed:,} bytes."
                )
            else:
                err = resp.get("error", "Compaction failed")
                QMessageBox.critical(self, "Compaction Failed", f"Could not compact database:\n{err}")

        self.scid_client.compact_database(callback=on_compact)

    def _on_import_progress(self, prog_data: dict):
        scanned = prog_data.get("scanned", 0)
        total = prog_data.get("total", 0)
        percent = int(prog_data.get("percent", 0))
        self.progress_bar.setValue(percent)
        self.status_bar.showMessage(f"Importing PGN: {scanned:,}/{total:,} games processed ({percent}%)")

    def _on_export_progress(self, prog_data: dict):
        scanned = prog_data.get("scanned", 0)
        total = prog_data.get("total", 0)
        percent = int(prog_data.get("percent", 0))
        self.progress_bar.setValue(percent)
    # ──────────────────────── Open / Load / Navigation ────────────────────────

    def open_database(self):
        """Open a file dialog to select a SCID or PGN database."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Chess Database",
            ".",
            "Chess Databases (*.si5 *.si4 *.pgn);;SCID v5 Database (*.si5);;SCID v4 Database (*.si4);;PGN Files (*.pgn);;All Files (*)"
        )
        if file_path:
            self.load_database_path(file_path)

    def open_pgn_database(self):
        """Backward compatibility alias for open_database."""
        self.open_database()

    def load_pgn_path(self, pgn_path: str):
        """Backward compatibility alias for load_database_path."""
        self.load_database_path(pgn_path)

    def load_database_path(self, db_path: str):
        """Open and load any supported database (SCID .si5/.si4 or PGN) using scid-mgr."""
        if not os.path.exists(db_path):
            QMessageBox.warning(self, "File Not Found", f"Database file does not exist:\n{db_path}")
            return

        self._current_db_path = db_path
        self._current_search_filter = None
        if hasattr(self, "btn_clear_search"):
            self.btn_clear_search.hide()

        basename = os.path.basename(db_path)
        self.status_bar.showMessage(f"Opening {basename}...")
        self.progress_bar.setValue(0)
        self.progress_bar.show()

        if not self.scid_client.is_running():
            settings = QSettings("QChessApp", "SearchConfig")
            threads = int(settings.value("worker_threads", 0))
            ok = self.scid_client.start(db_path, threads=threads if threads > 0 else None)
            if not ok:
                self.progress_bar.hide()
                QMessageBox.critical(self, "Backend Error", "Failed to start scid-mgr backend process.")
                return

        def on_opened(resp: dict):
            self.progress_bar.hide()
            if resp.get("status") == "ok":
                stats = resp.get("data", {}).get("stats", {})
                self._current_db_stats = stats
                total_games = stats.get("total_games", 0)
                fmt = resp.get("data", {}).get("format", "si5")
                self.game_table.load_database(total_games, None)
                self.db_info_label.setText(f"📁 [{fmt.upper()}] {basename}")
                self.setWindowTitle(f"QChess — {basename}")
                self.stack.setCurrentIndex(1)
                self.status_bar.showMessage(f"Opened {basename} ({total_games:,} games).", 6000)
                self._add_to_recent(db_path)
                self.databaseOpened.emit(db_path, db_path)
            else:
                err = resp.get("error", "Failed to open database")
                QMessageBox.critical(self, "Open Failed", f"Could not open database:\n{err}")
                self.status_bar.showMessage(f"Error opening database: {err}", 8000)

        self.scid_client.open_database(db_path, callback=on_opened)

    def build_position_index(self):
        """Open dialog to construct or rebuild the fast companion position index (.pos.idx)."""
        if not self._current_db_path:
            QMessageBox.information(
                self,
                "No Database Opened",
                "Please open or create a SCID database before building a position index."
            )
            return

        ext = os.path.splitext(self._current_db_path)[1].lower()
        if ext not in self.SCID_EXTENSIONS:
            QMessageBox.warning(
                self,
                "Unsupported Operation",
                "Position index (.pos.idx) is only applicable to SCID (.si5/.si4) databases."
            )
            return

        settings = QSettings("QChessApp", "SearchConfig")
        saved_depth = int(settings.value("default_pos_index_depth", 24))
        dlg = BuildPosIndexDialog(self.scid_client, default_ply=saved_depth, parent=self)
        dlg.exec_()

    def open_database_settings(self):
        """Open Search & CPU Threading preferences dialog."""
        dlg = DatabaseSettingsDialog(self.scid_client, parent=self)
        dlg.exec_()

    def _on_game_selected(self, game_data: dict):
        self.gameSelected.emit(game_data)

    def _on_load_finished(self, total_rows: int):
        if self._current_search_filter:
            self.game_table.set_info_text(f"{total_rows:,} games matched (Filter Active)")
        else:
            self.game_table.set_info_text(f"{total_rows:,} games")

    def _go_home(self):
        """Return to the welcome screen."""
        self.stack.setCurrentIndex(0)
        self.setWindowTitle("QChess — Home")

    # ──────────────────────── Recent Files ────────────────────────

    def _add_to_recent(self, db_path: str):
        settings = QSettings("QChessApp", "RecentFiles")
        recent = settings.value("recent_pgn_paths", [])
        if not isinstance(recent, list):
            recent = []
        if db_path in recent:
            recent.remove(db_path)
        recent.insert(0, db_path)
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
            btn.clicked.connect(lambda checked, p=path: self.load_database_path(p))
            self.recent_files_layout.addWidget(btn, alignment=Qt.AlignCenter)

    # ──────────────────────── Theming ────────────────────────

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        if hasattr(self, "create_db_btn"):
            self.create_db_btn.setStyleSheet(self._primary_button_style())
        if hasattr(self, "open_db_btn"):
            self.open_db_btn.setStyleSheet(self._secondary_button_style())
        if hasattr(self, "new_analysis_btn"):
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

    @staticmethod
    def _assets_dir() -> str:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(os.path.dirname(os.path.dirname(current_dir)), "assets")
