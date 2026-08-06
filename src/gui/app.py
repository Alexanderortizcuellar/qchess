import re
import sys
import qtawesome as qta

import chess
from PyQt5.QtCore import QUrl, Qt, QTimer, QEvent
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QToolBar,
    QInputDialog,
    QLabel,
    QLineEdit,
    QDockWidget,
    QAction,
    QSizePolicy,
    QPushButton,
    QMenu,
)

from gui.widgets.analysis_widget import AnalysisWidget
from gui.widgets.game_train_widget import GameTrainWidget
from gui.widgets.chessboard import ChessBoard
from core.engine import ChessEngine
from core.move_manager import MoveManager
from gui.widgets.painter_pgn_browser import QPainterPGNBrowser
from gui.widgets.game_analytics import GameAnalytics
from gui.widgets.analysis_summary_widget import AnalysisSummaryWidget
from gui.dialogs.variations_dlg import VariationsDialog
from utils.helpers import _create_action, _create_iconed_button
from gui.dialogs.board_editor import BoardEditorDlg
from gui.dialogs.engine_dlg import EngineConfigDialog
from gui.dialogs.pgn_import_dlg import PGNImportDlg
from gui.dialogs.settings_dlg import SettingsDialog
from gui.dialogs.pgn_headers_dlg import PGNHeadersDialog
from core.opening_explorer import OpeningExplorerLogic


class ChessApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess App")
        self.is_dark = True

        # Load Figurine Font
        from PyQt5.QtGui import QFontDatabase
        import os

        current_dir = os.path.dirname(os.path.abspath(__file__))
        font_path = os.path.join(
            os.path.dirname(os.path.dirname(current_dir)), "assets", "SEMFIGB.TTF"
        )
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                family = QFontDatabase.applicationFontFamilies(font_id)[0]
                self.figurine_font_family = family
            else:
                self.figurine_font_family = "Noto Sans"
        else:
            self.figurine_font_family = "Noto Sans"
        self.current_figurine_font = self.figurine_font_family

        self.move_manager = MoveManager()
        self.engine = ChessEngine("stockfish", self)

        # Game Autoplay timer
        self.autoplay_timer = QTimer(self)
        self.autoplay_timer.timeout.connect(self.forward)

        # Load engine settings on startup
        from PyQt5.QtCore import QSettings

        settings = QSettings("TestChessApp", "Engine")
        if settings.value("path"):
            config = {
                "path": settings.value("path"),
                "threads": int(settings.value("threads", 1)),
                "hash": int(settings.value("hash", 16)),
                "multipv": int(settings.value("multipv", 1)),
                "syzygy": settings.value("syzygy", ""),
            }
            self.engine.set_settings(config)

        # --- Central Widget (Board Area) ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_layout = QVBoxLayout(central_widget)

        # Board and FEN group
        board_group = QWidget()
        board_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        board_group_layout = QVBoxLayout(board_group)
        board_group_layout.setContentsMargins(0, 0, 0, 0)
        board_group_layout.setSpacing(10)

        self.chessboard = ChessBoard(self, chess.Board().fen(), size=750)
        self.chessboard.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.bar = self.chessboard.eval_bar  # Alias for compatibility

        board_group_layout.addWidget(self.chessboard, stretch=1)

        # FEN display area
        self.fen_row = QHBoxLayout()
        self.fen_label = QLabel("FEN:")
        self.fen_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.fen_edit = QLineEdit()
        self.fen_edit.setReadOnly(True)
        self.fen_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.fen_row.addWidget(self.fen_label)
        self.fen_row.addWidget(self.fen_edit, stretch=1)

        board_group_layout.addLayout(self.fen_row)

        self.fen_label.setVisible(self.bar.isVisible())

        central_layout.addWidget(board_group, stretch=1)

        # --- Docks ---
        self.setDockOptions(
            QMainWindow.AnimatedDocks
            | QMainWindow.AllowTabbedDocks
            | QMainWindow.AllowNestedDocks
            | QMainWindow.GroupedDragging
        )

        # 1. Analysis Dock
        self.analysis_widget = AnalysisWidget(self)
        self.analysis_dock = QDockWidget("Engine Analysis", self)
        self.analysis_dock.setWidget(self.analysis_widget)
        self.analysis_dock.setObjectName("analysis_dock")
        self.analysis_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.RightDockWidgetArea, self.analysis_dock)

        # Game / Train Widget (will be swapped into analysis_dock dynamically in Game / Train mode)
        self.gametrain_widget = GameTrainWidget(self)

        # Game/Train play state variables
        self.play_mode = None
        self.play_depth = 8
        self.self_play_delay = 1000
        self.self_play_timer = QTimer(self)
        self.self_play_timer.timeout.connect(self.make_engine_vs_engine_move)

        # Throttler for engine analysis updates to prevent lag/animation freezing
        self.analysis_update_timer = QTimer(self)
        self.analysis_update_timer.setSingleShot(True)
        self.analysis_update_timer.setInterval(100)  # Update UI at most every 100ms
        self.analysis_update_timer.timeout.connect(self.process_pending_analysis)
        self.pending_analysis_info = {}
        self.pending_analysis_fen = None

        # Debounce timer for engine position updates during navigation
        self.engine_debounce_timer = QTimer(self)
        self.engine_debounce_timer.setSingleShot(True)
        self.engine_debounce_timer.setInterval(150)  # 150ms debounce
        self.engine_debounce_timer.timeout.connect(self.run_debounced_send_position)
        
        self.last_move_time = 0
        self.has_received_first_update = False


        # 2. PGN & Navigation Dock
        self.browser = QPainterPGNBrowser(self, self.move_manager)
        self.navigation_layout = QHBoxLayout()
        self.jump_to_start_button = _create_iconed_button(
            "ph.caret-double-left-fill", "Home"
        )
        self.backward_button = _create_iconed_button(
            "mdi.skip-previous", "Left", "Navigate back"
        )
        self.forward_button = _create_iconed_button(
            "mdi.skip-next", "Right", "Navigate forward"
        )
        self.jump_to_end_button = _create_iconed_button(
            "mdi.skip-next", "End", "Navigate to end"
        )

        pgn_container = QWidget()
        pgn_dock_layout = QVBoxLayout(pgn_container)
        pgn_dock_layout.setContentsMargins(4, 4, 4, 4)
        pgn_dock_layout.setSpacing(4)
        pgn_dock_layout.addWidget(self.browser)

        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(2)

        # Add navigation buttons
        controls_layout.addWidget(self.jump_to_start_button)
        controls_layout.addWidget(self.backward_button)
        controls_layout.addWidget(self.forward_button)
        controls_layout.addWidget(self.jump_to_end_button)

        self.options_menu_btn = _create_iconed_button(
            "fa5s.bars", "", "Game Options", self.is_dark
        )
        
        options_menu = QMenu(self.options_menu_btn)
        options_menu.setStyleSheet("""
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
        """)

        # Add actions to dropdown menu
        flip_act = options_menu.addAction(qta.icon("ei.refresh"), "Flip Board")
        flip_act.triggered.connect(self.flip_board)
        
        load_fen_act = options_menu.addAction(qta.icon("fa6s.gear"), "Load FEN...")
        load_fen_act.triggered.connect(self.load_fen)
        
        save_pgn_act = options_menu.addAction(qta.icon("fa5s.save"), "Save PGN...")
        save_pgn_act.triggered.connect(self.save_pgn)
        
        copy_pgn_act = options_menu.addAction(qta.icon("fa5s.copy"), "Copy PGN")
        copy_pgn_act.triggered.connect(lambda _: self.copy_pgn_action())
        
        clear_pgn_act = options_menu.addAction(qta.icon("fa5s.trash"), "Clear PGN")
        clear_pgn_act.triggered.connect(self.clear_pgn)

        self.options_menu_btn.setMenu(options_menu)
        controls_layout.addWidget(self.options_menu_btn)
        pgn_dock_layout.addWidget(controls_widget)

        self.pgn_dock = QDockWidget("PGN Browser", self)
        self.pgn_dock.setWidget(pgn_container)
        self.pgn_dock.setObjectName("pgn_dock")
        self.pgn_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.RightDockWidgetArea, self.pgn_dock)

        # Apply figurine font to PGN browser
        self.browser.setStyleSheet(
            f"QTextBrowser {{font-size:20px; font-family: '{self.current_figurine_font}';}}"
        )

        # 3. Opening Explorer Dock
        self.opxl = OpeningExplorerLogic(self)
        self.explorer_dock = QDockWidget("Opening Explorer", self)
        self.explorer_dock.setWidget(self.opxl)
        self.explorer_dock.setObjectName("explorer_dock")
        self.explorer_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.RightDockWidgetArea, self.explorer_dock)
        self.explorer_dock.hide()

        # 4. Game Analytics Dock
        self.analytics_widget = GameAnalytics(self)
        self.analytics_dock = QDockWidget("Game Analytics", self)
        self.analytics_dock.setWidget(self.analytics_widget)
        self.analytics_dock.setObjectName("analytics_dock")
        self.analytics_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.analytics_dock)
        self.analytics_dock.hide()
        self.analytics_widget.moveIndexRequested.connect(self.move_manager.jump_to)

        # 5. Game Review (Analysis Summary) Dock
        self.summary_widget = AnalysisSummaryWidget(self)
        self.summary_dock = QDockWidget("Game Review", self)
        self.summary_dock.setWidget(self.summary_widget)
        self.summary_dock.setObjectName("summary_dock")
        self.summary_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.RightDockWidgetArea, self.summary_dock)
        self.tabifyDockWidget(self.pgn_dock, self.summary_dock)
        self.summary_dock.hide()

        self.splitDockWidget(self.analysis_dock, self.pgn_dock, Qt.Vertical)
        self.splitDockWidget(self.pgn_dock, self.explorer_dock, Qt.Vertical)

        # Restore saved window state and geometry if available, else apply defaults
        from PyQt5.QtCore import QSettings
        layout_settings = QSettings("TestChessApp", "Layout")
        saved_geometry = layout_settings.value("geometry")
        saved_state = layout_settings.value("windowState")
        if saved_geometry and saved_state:
            QTimer.singleShot(0, lambda: (self.restoreGeometry(saved_geometry), self.restoreState(saved_state)))
        else:
            QTimer.singleShot(100, lambda: self.resizeDocks([self.analysis_dock, self.pgn_dock], [200, 600], Qt.Vertical))

        # --- Toolbar & Menubar ---
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setObjectName("main_toolbar")
        self.addToolBar(self.toolbar)
        self.init_menubar()
        self.display_pgn()
        self.analytics_widget.update_data(self.move_manager.game, self.move_manager.current_node)
        self.summary_widget.update_data(self.move_manager.game)
        self.apply_settings()

        # --- Signals ---
        self.chessboard.moveMade.connect(self.handle_move)
        self.chessboard.fenChanged.connect(self.fen_edit.setText)
        self.analysis_widget.check_analysis.toggled.connect(self.toggle_analysis)
        self.chessboard.GameOver.connect(self.on_game_over)
        self.forward_button.clicked.connect(lambda: self.forward())
        self.backward_button.clicked.connect(self.backward)
        self.jump_to_start_button.clicked.connect(self.jump_to_start)
        self.jump_to_end_button.clicked.connect(self.jump_to_end)

        self.move_manager.pgnChanged.connect(lambda _: self.display_pgn())
        self.move_manager.activeNodeChanged.connect(self.sync_board_to_pgn)
        self.browser.anchorClicked.connect(self.on_anchor_clicked)
        self.chessboard.fenChanged.connect(self.send_position)
        self.chessboard.fenChanged.connect(self.send_fen_to_opxl)
        self.opxl.errorOcurred.connect(self.statusBar().showMessage)

        self.engine.analysisUpdated.connect(self.on_analysis_updated)
        self.analysis_widget.configClicked.connect(self.open_engine_config)
        self.gametrain_widget.gameStartRequested.connect(self.start_engine_game)
        self.gametrain_widget.gameStopRequested.connect(self.stop_engine_game)
        self.gametrain_widget.loadPresetRequested.connect(self.load_preset_position)
        self.engine.depthChanged.connect(
            lambda depth: self.analysis_widget.set_depth(f"depth={depth}")
            if self.analysis_widget.check_analysis.isChecked()
            else None
        )
        self.engine.moveFound.connect(self.on_best_move_found)

        # Event filter for mouse wheel navigation on chessboard
        self.chessboard.installEventFilter(self)
        self.chessboard.board_view.installEventFilter(self)
        self.chessboard.board_view.viewport().installEventFilter(self)

    def on_analysis_updated(self, info: dict):
        from PyQt5.QtCore import QSettings
        settings = QSettings("TestChessApp", "Config")
        if settings.value("app_mode", "Analysis Mode") == "Game / Train Mode":
            return
        if not self.analysis_widget.check_analysis.isChecked():
            return
        if self.move_manager.get_board().is_game_over():
            return
            
        current_fen = self.chessboard.fen()
        if info.get("fen") != current_fen:
            return
            
        multipv = info.get("multipv", 1)
        self.pending_analysis_info[multipv] = info
        self.pending_analysis_fen = current_fen
        
        if not self.has_received_first_update:
            self.has_received_first_update = True
            self.process_pending_analysis()
        else:
            if not self.analysis_update_timer.isActive():
                self.analysis_update_timer.start()

    def process_pending_analysis(self):
        if not self.pending_analysis_info:
            return
            
        infos = list(self.pending_analysis_info.values())
        fen = self.pending_analysis_fen
        self.pending_analysis_info.clear()
        
        infos.sort(key=lambda x: x.get("multipv", 1))
        
        self.analysis_widget.update_analysis_batch(infos, fen)
        
        multipv_1_info = next((info for info in infos if info.get("multipv") == 1), None)
        if multipv_1_info:
            s_type = multipv_1_info.get("score_type")
            s_val = multipv_1_info.get("score_value")
            white_pov_score = s_val
            if self.chessboard.turn == chess.BLACK:
                white_pov_score = -s_val
                
            if s_type == "mate":
                self.bar.setEngineScore({"type": "mate", "value": white_pov_score})
                self.bar.setToolTip(f"Mate in {white_pov_score}")
            else:
                self.bar.setEngineScore({"type": "cp", "value": white_pov_score})
                self.bar.setToolTip(f"{white_pov_score / 100.0:+.2f}")

    def clear_pending_analysis(self):
        self.pending_analysis_info.clear()
        self.pending_analysis_fen = None
        self.analysis_update_timer.stop()
        self.bar.setAnimationDuration(700)

    def run_debounced_send_position(self):
        from PyQt5.QtCore import QSettings
        settings = QSettings("TestChessApp", "Engine")
        current_fen = self.chessboard.fen()
        
        depth = int(settings.value("depth", 20))
        use_time_limit = settings.value("use_time_limit", False, type=bool)
        if use_time_limit:
            time_limit = int(settings.value("time_limit", 1000))
            self.engine.send_position(current_fen, "time", options={"time": time_limit})
        else:
            self.engine.send_position(current_fen, "depth", options={"depth": depth})

    def get_game_over_reason(self, board) -> str:
        if not board.is_game_over(claim_draw=True):
            return ""
        if board.is_checkmate():
            return "Checkmate"
        if board.is_stalemate():
            return "Stalemate"
        if board.is_insufficient_material():
            return "Insufficient Material"
        if board.is_seventyfive_moves() or board.can_claim_fifty_moves():
            return "50-Move Rule"
        if board.is_fivefold_repetition() or board.can_claim_threefold_repetition():
            return "Repetition"
        return "Game Over"

    def on_best_move_found(self, move_uci: str):
        from PyQt5.QtCore import QSettings
        settings = QSettings("TestChessApp", "Config")
        app_mode = settings.value("app_mode", "Analysis Mode")
        
        if app_mode == "Game / Train Mode" and self.gametrain_widget.playing:
            try:
                move = chess.Move.from_uci(move_uci)
            except Exception:
                self.gametrain_widget.update_status("Game Over")
                self.gametrain_widget.stop_play()
                return
                
            board = self.chessboard._internal_board
            if move in board.legal_moves:
                self.chessboard._on_move_made(move, is_user_input=False)
                
                reason = self.get_game_over_reason(board)
                if reason:
                    self.gametrain_widget.update_status(f"Game Over - {reason}")
                    self.gametrain_widget.stop_play()
                    return
                
                if self.play_mode == "Play as White":
                    self.gametrain_widget.update_status("Your turn (White)")
                elif self.play_mode == "Play as Black":
                    self.gametrain_widget.update_status("Your turn (Black)")
                elif self.play_mode == "Engine vs Engine":
                    self.self_play_timer.start(self.self_play_delay)

    def init_menubar(self):
        file_menu = self.menuBar().addMenu("&File")
        board_menu = self.menuBar().addMenu("&Board")
        open_action = _create_action(
            self, "Open", self.open_pgn, "Ctrl+O", icon_name="fa5s.folder-open"
        )
        save_action = _create_action(
            self, "Save", self.save_pgn, "Ctrl+S", icon_name="fa5s.save"
        )
        copy_action = _create_action(
            self, "Copy PGN", self.copy_pgn_action, "Ctrl+C", icon_name="fa5s.copy"
        )
        paste_pgn_action = _create_action(
            self, "Paste PGN", self.paste_pgn, "Ctrl+V", icon_name="fa5s.paste"
        )
        edit_headers_action = _create_action(
            self,
            "Edit PGN Headers...",
            self.edit_pgn_headers_action,
            "Ctrl+H",
            icon_name="fa5s.edit",
        )
        export_img_action = _create_action(
            self,
            "Export Board Image",
            self.export_board_image,
            "Ctrl+I",
            icon_name="fa5s.image",
        )
        settings_action = _create_action(
            self, "Settings", self.open_settings, "Ctrl+P", icon_name="fa5s.sliders-h"
        )
        quit_action = _create_action(
            self, "Quit", self.close, "Ctrl+Q", icon_name="fa5s.times-circle"
        )

        reset_board_action = _create_action(
            self, "Reset Board", self.clear_pgn, "Ctrl+R", icon_name="fa5s.redo-alt"
        )
        setup_board_action = _create_action(
            self, "Set Up Board...", self.setup_board, "Ctrl+Shift+S", icon_name="fa5s.chess-board"
        )
        copy_board_img_action = _create_action(
            self, "Copy Board Image", self.copy_board_image, "Ctrl+Shift+C", icon_name="fa5s.copy"
        )

        engine_menu = self.menuBar().addMenu("&Engine")
        engine_action = _create_action(
            self,
            "Engine Config",
            self.open_engine_config,
            "Ctrl+E",
            icon_name="fa6s.gear",
        )

        view_menu = self.menuBar().addMenu("&View")
        dark_action = _create_action(
            self, "Dark", lambda: self.set_style("dark"), "Ctrl+D"
        )
        light_action = _create_action(
            self, "Light", lambda: self.set_style("light"), "Ctrl+L"
        )

        self.autoplay_action = _create_action(
            self,
            "Autoplay Game",
            self.toggle_autoplay,
            "Ctrl+Space",
            icon_name="fa5s.play",
            checkable=True,
        )

        docks_menu = view_menu.addMenu("&Docks")
        docks_menu.addAction(self.pgn_dock.toggleViewAction())
        docks_menu.addAction(self.analysis_dock.toggleViewAction())
        docks_menu.addAction(self.explorer_dock.toggleViewAction())
        docks_menu.addAction(self.analytics_dock.toggleViewAction())
        docks_menu.addAction(self.summary_dock.toggleViewAction())

        self.analytics_dock.visibilityChanged.connect(
            lambda visible: self.analytics_widget.update_data(self.move_manager.game, self.move_manager.current_node)
            if visible else None
        )
        self.summary_dock.visibilityChanged.connect(
            lambda visible: self.summary_widget.update_data(self.move_manager.game)
            if visible else None
        )

        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addAction(copy_action)
        file_menu.addAction(paste_pgn_action)
        file_menu.addAction(edit_headers_action)
        file_menu.addSeparator()
        file_menu.addAction(export_img_action)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        board_menu.addAction(reset_board_action)
        board_menu.addAction(setup_board_action)
        board_menu.addSeparator()
        board_menu.addAction(export_img_action)
        board_menu.addAction(copy_board_img_action)

        engine_menu.addAction(engine_action)

        view_menu.addAction(dark_action)
        view_menu.addAction(light_action)
        view_menu.addSeparator()
        view_menu.addAction(self.autoplay_action)

        # Quick Access Toolbar Actions
        flip_action = _create_action(
            self, "Flip Board", self.flip_board, "Ctrl+F", icon_name="ei.refresh"
        )
        clear_action = _create_action(
            self, "Clear PGN", self.clear_pgn, "Ctrl+Shift+D", icon_name="fa5s.trash"
        )

        self.init_toolbar(
            [
                open_action,
                save_action,
                copy_action,
                paste_pgn_action,
                edit_headers_action,
                export_img_action,
                settings_action,
                flip_action,
                clear_action,
            ]
        )

    def toggle_autoplay(self, checked: bool):
        if checked:
            self.autoplay_timer.start(1500)
            self.statusBar().showMessage("Autoplay Started")
        else:
            self.autoplay_timer.stop()
            self.statusBar().showMessage("Autoplay Stopped")

    def forward(self, force_dialog=False, follow_mainline=False):
        if self.move_manager.has_variations():
            variations = self.move_manager.get_current_node_variations()
            if (
                len(variations) > 1
                and not follow_mainline
                and (force_dialog or not self.autoplay_timer.isActive())
            ):
                dialog = VariationsDialog(
                    variations, font_family=self.current_figurine_font, parent=self
                )
                if dialog.exec_() != QDialog.Accepted or dialog.selected_index is None:
                    return
                self.move_manager.redo(dialog.selected_index)
            else:
                self.move_manager.redo(0)

            self.chessboard.update_board(
                self.move_manager.get_board().fen(), self.move_manager.current_node.move
            )
            self.display_pgn()
        elif self.autoplay_timer.isActive():
            self.autoplay_timer.stop()
            self.autoplay_action.setChecked(False)
            self.statusBar().showMessage("Autoplay Finished")

    def backward(self):
        self.move_manager.undo()
        self.chessboard.update_board(
            self.move_manager.get_board().fen(), self.move_manager.current_node.move
        )
        self.display_pgn()

    def jump_to_start(self):
        self.move_manager.jump_to_start()
        self.chessboard.update_board(self.move_manager.get_board().fen())
        self.display_pgn()

    def jump_to_end(self):
        self.move_manager.jump_to_end()
        self.chessboard.update_board(
            self.move_manager.get_board().fen(), self.move_manager.current_node.move
        )
        self.display_pgn()

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.apply_settings()

    def apply_settings(self):
        from PyQt5.QtCore import QSettings

        settings = QSettings("TestChessApp", "Config")
        self.chessboard.set_theme(settings.value("board_theme", "Classic"))
        self.chessboard.set_premoves_enabled(
            settings.value("premoves_enabled", True, type=bool)
        )
        anim_dur = int(settings.value("animation_duration", 200))
        self.chessboard.board_view.set(animation={"duration": anim_dur})
        self.bar.setAnimationDuration(anim_dur)

        use_figurine = settings.value("use_figurine_font", True, type=bool)
        if use_figurine:
            self.current_figurine_font = f"'{self.figurine_font_family}'"
        else:
            self.current_figurine_font = "'Segoe UI', Arial, sans-serif"
        
        self.move_manager.font_family = self.current_figurine_font
        self.move_manager.create_mapping()
        
        show_eval = settings.value("show_eval_annotations", True, type=bool)
        show_cls = settings.value("show_move_classifications", True, type=bool)
        self.browser.show_eval = show_eval
        self.browser.show_classifications = show_cls
        self.move_manager.show_classifications = show_cls
        self.move_manager.create_mapping()
        self.browser.rebuild_layout(force=True)
        self.display_pgn()

        self.browser.setStyleSheet(
            f"QTextBrowser {{font-size:20px; font-family: {self.current_figurine_font};}}"
        )

        # Application Mode Toggle
        app_mode = settings.value("app_mode", "Analysis Mode")
        if app_mode == "Game / Train Mode":
            # Stop game mode play if it was running, then swap widget
            self.gametrain_widget.stop_play()
            self.analysis_dock.setWidget(self.gametrain_widget)
            self.analysis_dock.setWindowTitle("Game / Train")
            self.chessboard.set_eval_bar_visible(False)
            self.engine.stop_search()
        else:
            # Stop game mode play if it was running, then swap widget
            self.gametrain_widget.stop_play()
            self.analysis_dock.setWidget(self.analysis_widget)
            self.analysis_dock.setWindowTitle("Engine Analysis")
            self.chessboard.set_eval_bar_visible(
                self.analysis_widget.check_analysis.isChecked()
            )
            if self.analysis_widget.check_analysis.isChecked():
                self.send_position(force=True)
                
        if hasattr(self, "opxl") and self.opxl.isVisible():
            self.send_fen_to_opxl(self.chessboard.fen())

    def set_style(self, style_name=None):
        if style_name is None:
            action = self.sender()
            if isinstance(action, QAction):
                style_name = action.text().lower()
            else:
                return
        self.is_dark = (style_name == "dark")
        import os

        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(current_dir)), "assets"
        )
        if style_name == "dark":
            qss_file = os.path.join(assets_dir, "style.qss")
            self.move_manager.change_html_style(True)
            self.analysis_widget.set_theme(True)
            self.gametrain_widget.set_theme(True)
            self.opxl.set_theme(True)
            self.analytics_widget.set_theme(True)
            self.summary_widget.set_theme(True)
            from utils.helpers import update_widget_icons

            update_widget_icons(self, True)
        else:
            qss_file = os.path.join(assets_dir, "light_style.qss")
            self.move_manager.change_html_style(False)
            self.analysis_widget.set_theme(False)
            self.gametrain_widget.set_theme(False)
            self.opxl.set_theme(False)
            self.analytics_widget.set_theme(False)
            self.summary_widget.set_theme(False)
            from utils.helpers import update_widget_icons

            update_widget_icons(self, False)
        try:
            with open(qss_file, "r") as f:
                QApplication.instance().setStyleSheet(f.read())
        except Exception as e:
            self.statusBar().showMessage(f"Error loading theme: {e}")

    def init_toolbar(self, actions: list):
        for action in actions:
            self.toolbar.addAction(action)

    def flip_board(self):
        self.chessboard.flip()
        self.bar.setFlipped(not self.bar._flipped)

    def clear_pgn(self):
        self.move_manager.clear()
        self.display_pgn()
        self.chessboard.update_board(self.move_manager.get_board().fen())

    def load_fen(self):
        fen, ok = QInputDialog.getText(self, "Load FEN", "Enter FEN:")
        if ok:
            self.move_manager.load_fen(fen)
            self.display_pgn()
            self.chessboard.update_board(fen)
        else:
            dlg = BoardEditorDlg(self, initial_fen=self.chessboard.fen())
            if dlg.exec_() == QDialog.Accepted:
                new_fen = dlg.get_fen()
                self.move_manager.load_fen(new_fen)
                self.display_pgn()
                self.chessboard.update_board(new_fen)

    def setup_board(self):
        dlg = BoardEditorDlg(self, initial_fen=self.chessboard.fen())
        if dlg.exec_() == QDialog.Accepted:
            new_fen = dlg.get_fen()
            self.move_manager.load_fen(new_fen)
            self.display_pgn()
            self.chessboard.update_board(new_fen)

    def copy_board_image(self):
        pixmap = self.chessboard.grab()
        QApplication.clipboard().setPixmap(pixmap)
        self.statusBar().showMessage("Board image copied to clipboard.")

    def sync_board_to_pgn(self):
        node = self.move_manager.current_node
        last_move = node.move if hasattr(node, "move") and node.move else None
        self.chessboard.update_board(
            self.move_manager.get_board().fen(), last_move
        )
        if hasattr(self, "analytics_dock") and self.analytics_dock.isVisible():
            self.analytics_widget.update_data(self.move_manager.game, node)
        if hasattr(self, "summary_dock") and self.summary_dock.isVisible():
            self.summary_widget.update_data(self.move_manager.game)

    def on_anchor_clicked(self, url: QUrl):
        match = re.match(r"move\((\d+)\)", url.toString())
        if match:
            self.move_manager.jump_to(int(match.group(1)))
            self.chessboard.update_board(
                self.move_manager.current_node.board().fen(),
                self.move_manager.current_node.move,
            )

    def handle_move(self, move_uci):
        self.move_manager.make_move(move_uci)
        self.display_pgn()

        from PyQt5.QtCore import QSettings
        settings = QSettings("TestChessApp", "Config")
        app_mode = settings.value("app_mode", "Analysis Mode")
        if app_mode == "Game / Train Mode" and self.gametrain_widget.playing:
            board = self.chessboard._internal_board
            reason = self.get_game_over_reason(board)
            if reason:
                self.gametrain_widget.update_status(f"Game Over - {reason}")
                self.gametrain_widget.stop_play()
                return
            
            is_engine_turn = False
            if self.play_mode == "Play as White" and board.turn == chess.BLACK:
                is_engine_turn = True
            elif self.play_mode == "Play as Black" and board.turn == chess.WHITE:
                is_engine_turn = True
            
            if is_engine_turn:
                # Use a singleShot delay to let the board finish its slide animation smoothly
                QTimer.singleShot(250, self.trigger_engine_play)

    def start_engine_game(self, mode: str, depth: int, delay_ms: int):
        self.play_mode = mode
        self.play_depth = depth
        self.self_play_delay = delay_ms
        
        current_fen = self.chessboard.fen()
        self.move_manager.load_fen(current_fen)
        self.display_pgn()
        
        board = self.chessboard._internal_board
        reason = self.get_game_over_reason(board)
        if reason:
            self.gametrain_widget.update_status(f"Game Over - {reason}")
            self.gametrain_widget.stop_play()
            return
            
        if self.play_mode == "Play as White":
            if board.turn == chess.WHITE:
                self.gametrain_widget.update_status("Your turn (White)")
            else:
                self.gametrain_widget.update_status("Engine thinking...")
                self.trigger_engine_play()
        elif self.play_mode == "Play as Black":
            if board.turn == chess.BLACK:
                self.gametrain_widget.update_status("Your turn (Black)")
            else:
                self.gametrain_widget.update_status("Engine thinking...")
                self.trigger_engine_play()
        elif self.play_mode == "Engine vs Engine":
            self.gametrain_widget.update_status("Engine vs Engine...")
            self.self_play_timer.start(self.self_play_delay)

    def stop_engine_game(self):
        self.self_play_timer.stop()
        self.engine.stop_search()
        self.gametrain_widget.update_status("Stopped")

    def load_preset_position(self, fen: str):
        self.move_manager.load_fen(fen)
        self.display_pgn()
        self.chessboard.update_board(fen)
        if self.gametrain_widget.playing:
            self.gametrain_widget.stop_play()

    def trigger_engine_play(self):
        if not self.gametrain_widget.playing:
            return
        board = self.chessboard._internal_board
        reason = self.get_game_over_reason(board)
        if reason:
            self.gametrain_widget.update_status(f"Game Over - {reason}")
            self.gametrain_widget.stop_play()
            return
            
        self.gametrain_widget.update_status("Engine thinking...")
        if not self.engine.is_running():
            self.engine.start()
        self.engine.send_position(board.fen(), "depth", options={"depth": self.play_depth})

    def make_engine_vs_engine_move(self):
        if not self.gametrain_widget.playing or self.play_mode != "Engine vs Engine":
            self.self_play_timer.stop()
            return
        board = self.chessboard._internal_board
        reason = self.get_game_over_reason(board)
        if reason:
            self.self_play_timer.stop()
            self.gametrain_widget.update_status(f"Game Over - {reason}")
            self.gametrain_widget.stop_play()
            return
            
        self.trigger_engine_play()

    def toggle_analysis(self, toggle: bool):
        if toggle:
            self.analysis_widget.reset_lines()
            self.clear_pending_analysis()
            if not self.engine.is_running():
                self.engine.start()
            self.chessboard.set_eval_bar_visible(True)
            self.fen_label.show()
            self.send_position(force=True)
        else:
            self.engine.stop_search()
            self.analysis_widget.clear()
            self.clear_pending_analysis()
            self.chessboard.set_eval_bar_visible(False)
            self.fen_label.hide()

    def display_pgn(self):
        self.browser.setHtml(self.move_manager.html)

    def on_game_over(self):
        self.engine.stop_search()
        self.clear_pending_analysis()

    def send_fen_to_opxl(self, fen: str):
        if self.opxl.isVisible():
            self.opxl.send_fen(fen)

    def send_position(self, *args, force=False):
        from PyQt5.QtCore import QSettings
        settings = QSettings("TestChessApp", "Config")
        if settings.value("app_mode", "Analysis Mode") == "Game / Train Mode":
            return
            
        if self.analysis_widget.check_analysis.isChecked():
            current_fen = self.chessboard.fen()
            if not force and hasattr(self, "_last_sent_fen") and self._last_sent_fen == current_fen:
                return
            self._last_sent_fen = current_fen

            import time
            now = time.time()
            time_since_last_move = now - getattr(self, "last_move_time", 0)
            self.last_move_time = now
            
            # Fast navigation is defined as moves played less than 250ms apart (> 4 moves per second)
            is_fast_navigation = (time_since_last_move < 0.25)
            
            self.has_received_first_update = False
            
            # Stop the engine immediately if navigating fast. Otherwise, let ChessEngine queue the next search.
            if is_fast_navigation:
                self.engine.stop_search()
            self.clear_pending_analysis()

            # Handle game over status indicator in status bar and eval bar
            board = self.chessboard._internal_board
            reason = self.get_game_over_reason(board)
            if reason:
                self.statusBar().showMessage(f"Position status: {reason}")
                if board.is_checkmate():
                    winner_symbol = "white" if board.turn == chess.BLACK else "black"
                    self.bar.setEngineScore({"type": "checkmate", "winner": winner_symbol})
                    self.bar.setToolTip("Checkmate")
                else:
                    self.bar.setEngineScore({"type": "draw"})
                    self.bar.setToolTip("Draw")
            else:
                self.statusBar().clearMessage()

            # Clear the widget immediately ONLY if navigating fast.
            # If moving slowly, we keep the old lines visible until the first update of the new position arrives.
            if is_fast_navigation:
                self.analysis_widget.reset_lines()

            # For terminal states (checkmate, stalemate), no further analysis is needed 
            # since there are no legal moves. We stop the engine and return immediately.
            if board.is_checkmate() or board.is_stalemate():
                self.engine_debounce_timer.stop()
                if not is_fast_navigation:
                    self.analysis_widget.reset_lines()
                return

            if force or not is_fast_navigation:
                # If forced or slow, run immediately (no debounce delay)
                self.engine_debounce_timer.stop()
                self.run_debounced_send_position()
            else:
                # If navigating fast, debounce the engine start to wait for user to pause
                self.engine_debounce_timer.start()

    def open_engine_config(self):
        dlg = EngineConfigDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.engine.set_settings(dlg.get_config())
            if self.analysis_widget.check_analysis.isChecked():
                self.send_position(force=True)

    def paste_pgn(self):
        pgn_text = QApplication.clipboard().text()
        dlg = PGNImportDlg(self, initial_text=pgn_text)
        if dlg.exec_() == QDialog.Accepted:
            final_pgn = dlg.get_pgn()
            if final_pgn:
                self.move_manager.update_pgn(final_pgn)
                self.display_pgn()
                self.chessboard.update_board(self.move_manager.get_board().fen())

    def open_pgn(self):
        file, ok = QFileDialog.getOpenFileName(
            self, "Open", ".", "Pgn Files (*.pgn);;All (*)"
        )
        if ok:
            self.move_manager.load_pgn_file(file)

    def edit_pgn_headers(self, title="Edit PGN Headers") -> bool:
        dlg = PGNHeadersDialog(self, self.move_manager.game.headers, title=title)
        if dlg.exec_() == QDialog.Accepted:
            new_headers = dlg.get_headers()
            self.move_manager.game.headers.clear()
            for k, v in new_headers.items():
                self.move_manager.game.headers[k] = v
            self.move_manager.create_mapping()
            self.move_manager.is_dirty = True
            return True
        return False

    def edit_pgn_headers_action(self):
        self.edit_pgn_headers(title="Edit PGN Headers")

    def copy_pgn_action(self):
        if self.edit_pgn_headers(title="Edit PGN Headers before Copying"):
            self.copy_text(self.move_manager.get_pgn())
            self.statusBar().showMessage("PGN copied to clipboard.")

    def save_pgn(self):
        if self.edit_pgn_headers(title="Edit PGN Headers before Saving"):
            file, ok = QFileDialog.getSaveFileName(
                self, "Save", ".", "Pgn Files (*.pgn);;All (*)"
            )
            if ok:
                with open(file, "w", encoding="utf-8") as f:
                    f.write(self.move_manager.get_pgn())
                self.statusBar().showMessage(f"PGN saved to {file}")
                self.move_manager.is_dirty = False

    def export_board_image(self):
        file, ok = QFileDialog.getSaveFileName(
            self,
            "Export Board Image",
            ".",
            "PNG Files (*.png);;JPG Files (*.jpg);;All (*)",
        )
        if ok:
            self.chessboard.grab().save(file)
            self.statusBar().showMessage(f"Board image saved to {file}")

    def copy_text(self, text: str):
        QApplication.clipboard().setText(text)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Wheel:
            if watched in (
                self.chessboard,
                self.chessboard.board_view,
                self.chessboard.board_view.viewport(),
            ):
                delta = event.angleDelta().y()
                if delta > 0:
                    self.forward(follow_mainline=True)
                elif delta < 0:
                    self.backward()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def closeEvent(self, a0):
        from PyQt5.QtCore import QSettings
        layout_settings = QSettings("TestChessApp", "Layout")
        layout_settings.setValue("geometry", self.saveGeometry())
        layout_settings.setValue("windowState", self.saveState())

        if self.move_manager.is_dirty:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Unsaved Changes")
            msg_box.setText("The current game has unsaved changes.\nDo you want to save your changes?")
            msg_box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            msg_box.setDefaultButton(QMessageBox.Save)
            
            ret = msg_box.exec_()
            
            if ret == QMessageBox.Save:
                self.save_pgn()
                if not self.move_manager.is_dirty:
                    self.engine.quit()
                    a0.accept()
                else:
                    a0.ignore()
            elif ret == QMessageBox.Discard:
                self.engine.quit()
                a0.accept()
            else:
                a0.ignore()
        else:
            self.engine.quit()
            a0.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChessApp()
    window.set_style("dark")
    window.show()
    sys.exit(app.exec_())
