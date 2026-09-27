import re
import sys
import qtawesome as qta

import chess
from PyQt5.QtCore import QUrl, Qt, QTimer, QEvent, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence
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
    QMenu,
    QTabWidget,
)

from gui.widgets.analysis_widget import AnalysisWidget
from gui.widgets.game_train_widget import GameTrainWidget
from gui.widgets.chessboard import ChessBoard
from core.engine import ChessEngine
from core.move_manager import MoveManager
from gui.widgets.painter_pgn_browser import QPainterPGNBrowser
from gui.widgets.game_analytics import GameAnalytics
from gui.widgets.analysis_summary_widget import AnalysisSummaryWidget
from gui.widgets.continuations_widget import ContinuationsWidget
from gui.widgets.endgames_widget import EndgamesWidget
from gui.dialogs.variations_dlg import VariationsDialog
from utils.helpers import _create_action, _create_iconed_button
from gui.dialogs.board_editor import BoardEditorDlg
from gui.dialogs.engine_dlg import EngineConfigDialog
from gui.dialogs.pgn_import_dlg import PGNImportDlg
from gui.dialogs.settings_dlg import SettingsDialog
from gui.dialogs.pgn_headers_dlg import PGNHeadersDialog
from core.opening_explorer import OpeningExplorerLogic
from core.pgn_editor import save_game_to_pgn


class ChessApp(QMainWindow):
    gameSaved = pyqtSignal(str, object, object)
    # Emitted when the user saves a repertoire from the File menu.
    # Carries the current PGN text; the controller decides where to store it.
    repertoireSaveRequested = pyqtSignal(str)
    searchPositionRequested = pyqtSignal(str)
    previousGameRequested = pyqtSignal()
    nextGameRequested = pyqtSignal()
    themeChanged = pyqtSignal(str)
    closed = pyqtSignal(object)

    _cached_figurine_font_family = None

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess App")
        self.resize(1360, 820)
        self.is_dark = True

        # Load Figurine Font (cached once across instances)
        if ChessApp._cached_figurine_font_family is None:
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
                    ChessApp._cached_figurine_font_family = family
                else:
                    ChessApp._cached_figurine_font_family = "Noto Sans"
            else:
                ChessApp._cached_figurine_font_family = "Noto Sans"

        self.figurine_font_family = ChessApp._cached_figurine_font_family
        self.current_figurine_font = self.figurine_font_family

        self.move_manager = MoveManager()
        self.current_pgn_path = None
        self.current_pgn_offset = None
        self.current_pgn_length = None
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
        central_widget.setObjectName("boardCentralWidget")
        self.setCentralWidget(central_widget)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(8, 8, 8, 8)

        # Board and FEN group
        board_group = QWidget()
        board_group.setObjectName("boardGroup")
        board_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        board_group_layout = QVBoxLayout(board_group)
        board_group_layout.setContentsMargins(0, 0, 0, 0)
        board_group_layout.setSpacing(10)

        self.chessboard = ChessBoard(self, chess.Board().fen(), size=750)
        self.chessboard.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.bar = self.chessboard.eval_bar  # Alias for compatibility

        board_group_layout.addWidget(self.chessboard, stretch=1)

        # FEN display area
        self.fen_container = QWidget()
        self.fen_container.setObjectName("fenContainer")
        self.fen_row = QHBoxLayout(self.fen_container)
        self.fen_row.setContentsMargins(0, 0, 0, 0)
        self.fen_label = QLabel("FEN:")
        self.fen_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.fen_edit = QLineEdit()
        self.fen_edit.setReadOnly(True)
        self.fen_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.fen_row.addWidget(self.fen_label)
        self.fen_row.addWidget(self.fen_edit, stretch=1)

        board_group_layout.addWidget(self.fen_container)

        from PyQt5.QtCore import QSettings
        layout_settings = QSettings("TestChessApp", "Layout")
        show_fen = layout_settings.value("show_fen", "true") == "true"
        self.fen_container.setVisible(show_fen)

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
        self.analysis_widget.set_engine_name(self.engine.engine_name)
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
        
        # Delay timer for engine move hover preview to avoid rapid flashing
        self.engine_hover_preview_timer = QTimer(self)
        self.engine_hover_preview_timer.setSingleShot(True)
        self.engine_hover_preview_timer.setInterval(250)
        self.engine_hover_preview_timer.timeout.connect(self._apply_engine_hover_preview)
        self._pending_engine_hover = (None, None)
        
        self.last_move_time = 0
        self.has_received_first_update = False


        # 2. PGN & Navigation Dock
        self.browser = QPainterPGNBrowser(self, self.move_manager)
        self.navigation_layout = QHBoxLayout()
        self.jump_to_start_button = _create_iconed_button(
            "ph.caret-double-left-fill", "", "Start of game (Home)", is_dark=self.is_dark
        )
        self.backward_button = _create_iconed_button(
            "mdi.skip-previous", "", "Previous move (Left)", is_dark=self.is_dark
        )
        self.forward_button = _create_iconed_button(
            "mdi.skip-next", "", "Next move (Right)", is_dark=self.is_dark
        )
        self.jump_to_end_button = _create_iconed_button(
            "mdi.skip-next", "", "End of game (End)", is_dark=self.is_dark
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

        # Match Stepping Buttons (active when game has matching plies from database search)
        self.matching_plies = []
        self.current_match_idx = 0

        self.btn_prev_match = _create_iconed_button(
            "fa5s.step-backward", "", "Previous Query Match (Alt+[)", is_dark=self.is_dark
        )
        self.btn_prev_match.setToolTip("Jump to previous query match position in this game [Alt+[]")
        self.btn_prev_match.clicked.connect(self.go_prev_match)
        self.btn_prev_match.hide()

        self.lbl_match_badge = QLabel("", self)
        self.lbl_match_badge.setFont(QFont("Segoe UI", 9, QFont.Bold))
        self.lbl_match_badge.setStyleSheet("color: #3b82f6; padding: 0 4px;")
        self.lbl_match_badge.hide()

        self.btn_next_match = _create_iconed_button(
            "fa5s.step-forward", "", "Next Query Match (Alt+])", is_dark=self.is_dark
        )
        self.btn_next_match.setToolTip("Jump to next query match position in this game [Alt+]]")
        self.btn_next_match.clicked.connect(self.go_next_match)
        self.btn_next_match.hide()

        controls_layout.addWidget(self.btn_prev_match)
        controls_layout.addWidget(self.lbl_match_badge)
        controls_layout.addWidget(self.btn_next_match)

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
        self.opt_prev_game_act = options_menu.addAction(qta.icon("fa5s.arrow-left"), "Previous Game (Alt+Left)")
        self.opt_prev_game_act.triggered.connect(self.previous_game)

        self.opt_next_game_act = options_menu.addAction(qta.icon("fa5s.arrow-right"), "Next Game (Alt+Right)")
        self.opt_next_game_act.triggered.connect(self.next_game)

        options_menu.addSeparator()

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
        self.analysis_dock.setMinimumWidth(380)
        self.pgn_dock.setMinimumWidth(380)
        self.explorer_dock.setMinimumWidth(380)
        self.explorer_dock.hide()

        # 4. Common Continuations & Reference Dock (Tabbed container)
        self.continuations_widget = ContinuationsWidget(self)
        self.endgames_widget = EndgamesWidget(self)

        self.ref_tab_widget = QTabWidget(self)
        self.ref_tab_widget.addTab(self.continuations_widget, "📈 Continuations")
        self.ref_tab_widget.addTab(self.endgames_widget, "♟ Endgames")

        self.continuations_dock = QDockWidget("Continuations", self)
        self.continuations_dock.setWidget(self.ref_tab_widget)
        self.continuations_dock.setObjectName("continuations_dock")
        self.continuations_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.RightDockWidgetArea, self.continuations_dock)
        self.continuations_dock.setMinimumWidth(380)
        self.tabifyDockWidget(self.explorer_dock, self.continuations_dock)
        self.continuations_dock.hide()

        # 5. Game Analytics Dock
        self.analytics_widget = GameAnalytics(self)
        self.analytics_dock = QDockWidget("Game Analytics", self)
        self.analytics_dock.setWidget(self.analytics_widget)
        self.analytics_dock.setObjectName("analytics_dock")
        self.analytics_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.analytics_dock)
        self.analytics_dock.hide()
        self.analytics_widget.moveIndexRequested.connect(self.move_manager.jump_to)

        # 6. Game Review (Analysis Summary) Dock
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

        # Restore saved dock window state if available, else apply defaults
        from PyQt5.QtCore import QSettings
        layout_settings = QSettings("TestChessApp", "Layout")
        saved_state = layout_settings.value("windowState")
        if saved_state:
            def _restore_and_focus_pgn():
                self.restoreState(saved_state)
                self.pgn_dock.show()
                self.pgn_dock.raise_()
            QTimer.singleShot(0, _restore_and_focus_pgn)
        else:
            def _apply_default_dock_layout():
                dock_w = int(self.width() * 0.48)
                self.resizeDocks([self.analysis_dock, self.pgn_dock], [dock_w, dock_w], Qt.Horizontal)
                self.resizeDocks([self.analysis_dock, self.pgn_dock], [200, 600], Qt.Vertical)
                self.pgn_dock.show()
                self.pgn_dock.raise_()
            QTimer.singleShot(100, _apply_default_dock_layout)

        # --- Toolbar & Menubar ---
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setObjectName("main_toolbar")
        self.addToolBar(self.toolbar)
        self.init_menubar()
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

        # Keyboard Navigation Shortcuts (clean, no visual button depressing)
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        QShortcut(QKeySequence(Qt.Key_Right), self, lambda: self.forward())
        QShortcut(QKeySequence(Qt.Key_Left), self, self.backward)
        QShortcut(QKeySequence(Qt.Key_Home), self, self.jump_to_start)
        QShortcut(QKeySequence(Qt.Key_End), self, self.jump_to_end)
        QShortcut(QKeySequence("Alt+["), self, self.go_prev_match)
        QShortcut(QKeySequence("Alt+]"), self, self.go_next_match)

        self.move_manager.pgnChanged.connect(lambda _: self.display_pgn())
        self.move_manager.activeNodeChanged.connect(self.sync_board_to_pgn)
        self.browser.anchorClicked.connect(self.on_anchor_clicked)
        self.chessboard.fenChanged.connect(self.send_position)
        self.chessboard.fenChanged.connect(self.send_fen_to_opxl)
        self.chessboard.fenChanged.connect(self.send_fen_to_continuations)
        self.chessboard.fenChanged.connect(self.send_fen_to_endgames)
        self.ref_tab_widget.currentChanged.connect(self._on_ref_tab_changed)
        self.opxl.moveSelected.connect(self._on_explorer_move_selected)
        self.opxl.errorOcurred.connect(self.statusBar().showMessage)
        self.explorer_dock.visibilityChanged.connect(
            lambda visible: QTimer.singleShot(0, lambda: self.send_fen_to_opxl(self.chessboard.fen())) if visible else None
        )
        self.continuations_widget.continuationSelected.connect(self.on_continuation_selected)
        self.continuations_dock.visibilityChanged.connect(
            lambda visible: QTimer.singleShot(0, lambda: self.send_fen_to_continuations(self.chessboard.fen())) if visible else None
        )

        self.engine.analysisUpdated.connect(self.on_analysis_updated)
        self.engine.engineNameChanged.connect(self.analysis_widget.set_engine_name)
        self.analysis_widget.configClicked.connect(self.open_engine_config)
        self.analysis_widget.multipvChanged.connect(self.on_multipv_changed)
        self.analysis_widget.moveHovered.connect(self.on_engine_move_hovered)
        self.analysis_widget.moveClicked.connect(self.on_engine_move_clicked)
        self.gametrain_widget.gameStartRequested.connect(self.start_engine_game)
        self.gametrain_widget.gameStopRequested.connect(self.stop_engine_game)
        self.gametrain_widget.loadPresetRequested.connect(self.load_preset_position)
        self.engine.depthChanged.connect(
            lambda depth: self.analysis_widget.set_depth(f"depth={depth}")
            if self.analysis_widget.check_analysis.isChecked()
            else None
        )
        self.engine.moveFound.connect(self.on_best_move_found)
        self.analysis_dock.visibilityChanged.connect(self._on_analysis_dock_visibility_changed)

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
        try:
            if hasattr(self, "bar") and self.bar is not None:
                self.bar.setAnimationDuration(700)
        except Exception:
            pass

    def get_current_engine_eval(self) -> str | None:
        """Return formatted engine evaluation string (e.g. '+0.35', '#-2') if engine is active."""
        if not hasattr(self, "analysis_widget") or not self.analysis_widget.check_analysis.isChecked():
            return None
        
        # 1. Try first multipv line from analysis widget
        line_1 = self.analysis_widget.analysis_lines.get(1)
        if line_1:
            s_type = line_1.get("score_type")
            s_val = line_1.get("score_value")
            if s_type and s_val is not None:
                fen = line_1.get("fen", self.chessboard.fen())
                board = chess.Board(fen) if fen else self.chessboard._internal_board
                white_pov = s_val if board.turn == chess.WHITE else -s_val
                if s_type == "mate":
                    return f"#{white_pov}"
                else:
                    prefix = "+" if (white_pov / 100.0) > 0 else ""
                    return f"{prefix}{white_pov / 100.0:.2f}"
                    
        # 2. Fallback to score label
        score_text = self.analysis_widget.score_label.text().strip()
        if score_text and score_text not in ("0.00", "--", "Starting...", "...", ""):
            if score_text.startswith("M"):
                return score_text.replace("M", "#")
            return score_text
            
        return None

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
        game_menu = self.menuBar().addMenu("&Game")
        board_menu = self.menuBar().addMenu("&Board")
        open_action = _create_action(
            self, "Open", self.open_pgn, "Ctrl+O", icon_name="fa5s.folder-open"
        )
        save_action = _create_action(
            self, "Save", self.save_pgn, "Ctrl+S", icon_name="fa5s.save"
        )
        save_as_action = _create_action(
            self, "Save As...", self.save_pgn_as, "Ctrl+Shift+S", icon_name="fa5s.save"
        )
        self.prev_game_action = _create_action(
            self, "Previous Game", self.previous_game, "Alt+Left", icon_name="fa5s.arrow-left"
        )
        self.prev_game_action.setToolTip("Load Previous Game in Database [Alt+Left]")
        self.next_game_action = _create_action(
            self, "Next Game", self.next_game, "Alt+Right", icon_name="fa5s.arrow-right"
        )
        self.next_game_action.setToolTip("Load Next Game in Database [Alt+Right]")
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
        flip_action = _create_action(
            self, "Flip Board", self.flip_board, "Ctrl+F", icon_name="ei.refresh"
        )
        setup_board_action = _create_action(
            self, "Set Up Board...", self.setup_board, "Ctrl+Shift+T", icon_name="fa5s.chess-board"
        )
        search_position_action = _create_action(
            self, "Search Position in Database...", self.search_current_position, "Ctrl+Alt+F", icon_name="fa5s.search"
        )
        copy_board_img_action = _create_action(
            self, "Copy Board Image", self.copy_board_image, "Ctrl+Shift+C", icon_name="fa5s.copy"
        )
        copy_fen_action = _create_action(
            self, "Copy FEN", self.copy_current_fen, "Ctrl+Shift+F", icon_name="fa5s.copy"
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

        self.show_fen_action = _create_action(
            self,
            "Show FEN under Chessboard",
            self.toggle_fen_visibility,
            shortcut=None,
            checkable=True,
        )
        from PyQt5.QtCore import QSettings
        layout_settings = QSettings("TestChessApp", "Layout")
        show_fen = layout_settings.value("show_fen", "true") == "true"
        self.show_fen_action.setChecked(show_fen)

        docks_menu = view_menu.addMenu("&Docks")
        docks_menu.addAction(self.pgn_dock.toggleViewAction())
        docks_menu.addAction(self.analysis_dock.toggleViewAction())
        docks_menu.addAction(self.explorer_dock.toggleViewAction())
        docks_menu.addAction(self.continuations_dock.toggleViewAction())
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
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.prev_game_action)
        file_menu.addAction(self.next_game_action)
        file_menu.addSeparator()
        # Repertoire save — visible only when editing a repertoire (controller manages this)
        self.save_repertoire_action = _create_action(
            self,
            "Save Repertoire",
            self._save_repertoire,
            "Ctrl+Shift+R",
            icon_name="fa5s.chess-board",
        )
        self.save_repertoire_action.setVisible(False)
        file_menu.addAction(self.save_repertoire_action)
        file_menu.addSeparator()
        file_menu.addAction(copy_action)
        file_menu.addAction(paste_pgn_action)
        file_menu.addAction(edit_headers_action)
        file_menu.addSeparator()
        file_menu.addAction(export_img_action)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        game_menu.addAction(self.prev_game_action)
        game_menu.addAction(self.next_game_action)
        game_menu.addSeparator()
        game_menu.addAction(reset_board_action)
        game_menu.addAction(flip_action)
        game_menu.addAction(edit_headers_action)
        game_menu.addAction(copy_action)
        game_menu.addAction(paste_pgn_action)
        game_menu.addSeparator()
        game_menu.addAction(self.autoplay_action)

        board_menu.addAction(reset_board_action)
        board_menu.addAction(flip_action)
        board_menu.addAction(setup_board_action)
        board_menu.addAction(search_position_action)
        board_menu.addSeparator()
        board_menu.addAction(export_img_action)
        board_menu.addAction(copy_board_img_action)
        board_menu.addAction(copy_fen_action)

        engine_menu.addAction(engine_action)

        view_menu.addAction(dark_action)
        view_menu.addAction(light_action)
        view_menu.addSeparator()
        view_menu.addAction(self.show_fen_action)
        view_menu.addAction(self.autoplay_action)

        # Quick Access Toolbar Actions
        clear_action = _create_action(
            self, "Clear PGN", self.clear_pgn, "Ctrl+Shift+D", icon_name="fa5s.trash"
        )

        self.init_toolbar(
            [
                open_action,
                save_action,
                self.prev_game_action,
                self.next_game_action,
                search_position_action,
                copy_action,
                paste_pgn_action,
                edit_headers_action,
                export_img_action,
                settings_action,
                flip_action,
                clear_action,
            ]
        )

    def previous_game(self):
        """Emit request to load the previous game in the active database."""
        self.previousGameRequested.emit()

    def next_game(self):
        """Emit request to load the next game in the active database."""
        self.nextGameRequested.emit()

    def search_current_position(self):
        """Emit signal to search the current board position in the database."""
        fen = self.move_manager.get_board().fen()
        self.searchPositionRequested.emit(fen)

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
            show_vars = getattr(self.browser, "show_variations", True)
            if (
                len(variations) > 1
                and not follow_mainline
                and show_vars
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

            shapes, highlights = self.move_manager.get_current_shapes_and_highlights()
            self.chessboard.update_board(
                self.move_manager.get_board().fen(),
                self.move_manager.current_node.move,
                shapes=shapes,
                custom_highlights=highlights,
            )
            self.display_pgn()
        elif self.autoplay_timer.isActive():
            self.autoplay_timer.stop()
            self.autoplay_action.setChecked(False)
            self.statusBar().showMessage("Autoplay Finished")

    def backward(self):
        self.move_manager.undo()
        shapes, highlights = self.move_manager.get_current_shapes_and_highlights()
        self.chessboard.update_board(
            self.move_manager.get_board().fen(),
            self.move_manager.current_node.move,
            shapes=shapes,
            custom_highlights=highlights,
        )
        self.display_pgn()

    def jump_to_start(self):
        self.move_manager.jump_to_start()
        shapes, highlights = self.move_manager.get_current_shapes_and_highlights()
        self.chessboard.update_board(
            self.move_manager.get_board().fen(),
            shapes=shapes,
            custom_highlights=highlights,
        )
        self.display_pgn()

    def jump_to_end(self):
        self.move_manager.jump_to_end()
        shapes, highlights = self.move_manager.get_current_shapes_and_highlights()
        self.chessboard.update_board(
            self.move_manager.get_board().fen(),
            self.move_manager.current_node.move,
            shapes=shapes,
            custom_highlights=highlights,
        )
        self.display_pgn()

    def goto_ply(self, target_ply: int):
        """Jump chessboard and move cursor directly to target_ply."""
        self.move_manager.goto_ply(target_ply)
        node = self.move_manager.current_node
        last_move = node.move if hasattr(node, "move") and node.move else None
        shapes, highlights = self.move_manager.get_current_shapes_and_highlights()
        self.chessboard.update_board(
            self.move_manager.get_board().fen(),
            last_move,
            shapes=shapes,
            custom_highlights=highlights,
        )
        self.display_pgn()
        if hasattr(self.browser, "update_active_index"):
            self.browser.update_active_index()

    def set_matching_plies(self, plies: list):
        """Configure match stepping for database query search results."""
        self.matching_plies = list(plies) if plies else []
        self.current_match_idx = 0
        self._update_match_controls()

    def _update_match_controls(self):
        if self.matching_plies and len(self.matching_plies) > 0:
            total_m = len(self.matching_plies)
            curr_m = self.current_match_idx + 1
            curr_ply = self.matching_plies[self.current_match_idx]
            self.lbl_match_badge.setText(f"Match {curr_m}/{total_m} (p{curr_ply})")
            self.lbl_match_badge.show()
            if total_m > 1:
                self.btn_prev_match.show()
                self.btn_next_match.show()
            else:
                self.btn_prev_match.hide()
                self.btn_next_match.hide()
        else:
            self.lbl_match_badge.hide()
            self.btn_prev_match.hide()
            self.btn_next_match.hide()

    def go_prev_match(self):
        """Cycle to the previous matching ply from the database search."""
        if not self.matching_plies:
            return
        self.current_match_idx = (self.current_match_idx - 1) % len(self.matching_plies)
        target_ply = self.matching_plies[self.current_match_idx]
        self.goto_ply(target_ply)
        self._update_match_controls()
        self.statusBar().showMessage(
            f"Jumped to search match {self.current_match_idx + 1}/{len(self.matching_plies)} at ply {target_ply}.",
            4000
        )

    def go_next_match(self):
        """Cycle to the next matching ply from the database search."""
        if not self.matching_plies:
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matching_plies)
        target_ply = self.matching_plies[self.current_match_idx]
        self.goto_ply(target_ply)
        self._update_match_controls()
        self.statusBar().showMessage(
            f"Jumped to search match {self.current_match_idx + 1}/{len(self.matching_plies)} at ply {target_ply}.",
            4000
        )

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
        
        show_nags = settings.value("show_nags", True, type=bool)
        show_eval = settings.value("show_eval_annotations", True, type=bool)
        show_cls = settings.value("show_move_classifications", True, type=bool)
        show_vars = settings.value("show_variations", True, type=bool)
        layout_val = int(settings.value("layout_mode", 1))

        self.browser.show_nags = show_nags
        self.browser.show_eval = show_eval
        self.browser.show_classifications = show_cls
        self.browser.show_variations = show_vars
        self.browser.layout_mode = layout_val

        self.move_manager.show_nags = show_nags
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
        from PyQt5.QtCore import QSettings
        QSettings("QChessApp", "Theme").setValue("theme", style_name)
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
            self.continuations_widget.set_theme(True)
            self.endgames_widget.set_theme(True)
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
            self.continuations_widget.set_theme(False)
            self.endgames_widget.set_theme(False)
            self.analytics_widget.set_theme(False)
            self.summary_widget.set_theme(False)
            from utils.helpers import update_widget_icons

            update_widget_icons(self, False)
        if hasattr(self, "browser") and hasattr(self.browser, "rebuild_layout"):
            self.browser.rebuild_layout(force=True)
            self.browser.paint_widget.update()
            self.browser.header_widget.update()
        try:
            with open(qss_file, "r") as f:
                QApplication.instance().setStyleSheet(f.read())
        except Exception as e:
            self.statusBar().showMessage(f"Error loading theme: {e}")
        self.themeChanged.emit(style_name)

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
        shapes, highlights = self.move_manager.get_current_shapes_and_highlights()
        self.chessboard.update_board(
            self.move_manager.get_board().fen(),
            last_move,
            shapes=shapes,
            custom_highlights=highlights,
        )
        if hasattr(self, "analytics_dock") and self.analytics_dock.isVisible():
            self.analytics_widget.update_data(self.move_manager.game, node)
        if hasattr(self, "summary_dock") and self.summary_dock.isVisible():
            self.summary_widget.update_data(self.move_manager.game)

    def on_anchor_clicked(self, url: QUrl):
        match = re.match(r"move\((\d+)\)", url.toString())
        if match:
            self.move_manager.jump_to(int(match.group(1)))
            shapes, highlights = self.move_manager.get_current_shapes_and_highlights()
            self.chessboard.update_board(
                self.move_manager.current_node.board().fen(),
                self.move_manager.current_node.move,
                shapes=shapes,
                custom_highlights=highlights,
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
            self.engine.ensure_started()
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

    def _on_analysis_dock_visibility_changed(self, visible: bool):
        """Handle Engine Dock open/close lifecycle.

        Closing the dock stops analysis, cleans up timers, and terminates the engine
        process to release all system resources.
        Reopening the dock starts a new process only if analysis is enabled.
        """
        if not visible:
            # Dock closed: Stop analysis and terminate the engine process
            self.engine_debounce_timer.stop()
            self.analysis_update_timer.stop()
            self.self_play_timer.stop()
            self.clear_pending_analysis()
            self.engine.quit()
            self.chessboard.set_eval_bar_visible(False)
            if hasattr(self, "gametrain_widget") and self.gametrain_widget.playing:
                self.gametrain_widget.stop_play()
        else:
            # Dock opened: Start engine only if analysis is enabled
            from PyQt5.QtCore import QSettings

            settings = QSettings("TestChessApp", "Config")
            app_mode = settings.value("app_mode", "Analysis Mode")
            if app_mode != "Game / Train Mode":
                if self.analysis_widget.check_analysis.isChecked():
                    self.engine.ensure_started()
                    self.chessboard.set_eval_bar_visible(True)
                    self.send_position(force=True)

    def toggle_analysis(self, toggle: bool):
        """Handle the Engine Checkbox toggled state.

        Checkbox controls whether analysis is ACTIVE.
        Disabling the checkbox pauses analysis but keeps the engine process alive
        in the background for quick reuse.
        """
        if toggle:
            self.analysis_widget.show_starting_status()
            self.clear_pending_analysis()
            if not self.engine.is_running():
                self.engine.ensure_started()
            self.chessboard.set_eval_bar_visible(True)
            self.send_position(force=True)
        else:
            self.engine.stop_search()
            self.analysis_widget.clear()
            self.clear_pending_analysis()
            self.chessboard.set_eval_bar_visible(False)
            # Process is deliberately NOT terminated here (kept alive for quick resumption)

    def display_pgn(self):
        self.browser.setHtml(self.move_manager.html)

    def on_game_over(self):
        self.engine.stop_search()
        self.clear_pending_analysis()

    def _on_explorer_move_selected(self, move_str: str):
        try:
            board = self.move_manager.get_board()
            move = None
            try:
                m = chess.Move.from_uci(move_str)
                if m in board.legal_moves:
                    move = m
            except Exception:
                pass
            if not move:
                try:
                    m = board.parse_san(move_str)
                    if m in board.legal_moves:
                        move = m
                except Exception:
                    pass
            if move:
                self.chessboard._on_move_made(move, is_user_input=True)
        except Exception as e:
            print(f"[ChessApp] Error executing explorer move '{move_str}': {e}")

    def is_explorer_active(self) -> bool:
        """Return True only if the Opening Explorer dock and widget are visible and active on screen."""
        if not hasattr(self, "explorer_dock") or not hasattr(self, "opxl"):
            return False
        if not self.explorer_dock.isVisible() or self.explorer_dock.isMinimized():
            return False
        # If tabbed behind another dock widget, its visibleRegion is empty
        if self.explorer_dock.visibleRegion().isEmpty():
            return False
        return True

    def send_fen_to_opxl(self, fen: str, force: bool = False):
        if getattr(self, "suppress_explorer_update", False):
            return
        if self.is_explorer_active():
            self.opxl.send_fen(fen, force=force)

    def is_continuations_active(self) -> bool:
        """Return True only if the Continuations dock and widget are visible and active on screen."""
        if not hasattr(self, "continuations_dock") or not hasattr(self, "continuations_widget"):
            return False
        if not self.continuations_dock.isVisible() or self.continuations_dock.isMinimized():
            return False
        if hasattr(self, "ref_tab_widget") and self.ref_tab_widget.currentWidget() != self.continuations_widget:
            return False
        if self.continuations_dock.visibleRegion().isEmpty():
            return False
        return True

    def send_fen_to_continuations(self, fen: str, force: bool = False):
        if getattr(self, "suppress_explorer_update", False):
            return
        if self.is_continuations_active() or force:
            self.continuations_widget.set_position(fen)

    def is_endgames_active(self) -> bool:
        """Return True only if the Continuations dock and Endgames tab are visible and active on screen."""
        if not hasattr(self, "continuations_dock") or not hasattr(self, "endgames_widget"):
            return False
        if not self.continuations_dock.isVisible() or self.continuations_dock.isMinimized():
            return False
        if hasattr(self, "ref_tab_widget") and self.ref_tab_widget.currentWidget() != self.endgames_widget:
            return False
        if self.continuations_dock.visibleRegion().isEmpty():
            return False
        return True

    def send_fen_to_endgames(self, fen: str, force: bool = False):
        if getattr(self, "suppress_explorer_update", False):
            return
        if self.is_endgames_active() or force:
            self.endgames_widget.send_fen(fen, force=force)

    def _on_ref_tab_changed(self, index: int):
        if not hasattr(self, "ref_tab_widget"):
            return
        current = self.ref_tab_widget.widget(index)
        fen = self.chessboard.fen()
        if hasattr(self, "endgames_widget") and current == self.endgames_widget:
            self.send_fen_to_endgames(fen, force=True)
        elif hasattr(self, "continuations_widget") and current == self.continuations_widget:
            self.send_fen_to_continuations(fen, force=True)

    def on_continuation_selected(self, moves: list):
        """Play a sequence of moves (e.g. from common continuations) on the board."""
        if not moves:
            return
        for move_str in moves:
            board = self.move_manager.get_board()
            move = None
            try:
                m = chess.Move.from_uci(move_str)
                if m in board.legal_moves:
                    move = m
            except Exception:
                pass
            if not move:
                try:
                    m = board.parse_san(move_str)
                    if m in board.legal_moves:
                        move = m
                except Exception:
                    pass
            if move:
                self.chessboard._on_move_made(move, is_user_input=True)
            else:
                break

    def send_position(self, *args, force=False):
        from PyQt5.QtCore import QSettings
        settings = QSettings("TestChessApp", "Config")
        if settings.value("app_mode", "Analysis Mode") == "Game / Train Mode":
            return

        if self.analysis_dock.isVisible() and self.analysis_widget.check_analysis.isChecked():
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

    def on_multipv_changed(self, multipv: int):
        self.engine.set_multipv(multipv)
        if self.analysis_dock.isVisible() and self.analysis_widget.check_analysis.isChecked():
            self.send_position(force=True)

    def on_engine_move_hovered(self, fen: str | None, uci: str | None):
        if not hasattr(self, "chessboard"):
            return
        if fen:
            self._pending_engine_hover = (fen, uci)
            # If already displaying a ghost position, update immediately for seamless scrubbing
            if self.chessboard.is_previewing:
                self.engine_hover_preview_timer.stop()
                self._apply_engine_hover_preview()
            else:
                self.engine_hover_preview_timer.start(180)
        else:
            self.engine_hover_preview_timer.stop()
            self._pending_engine_hover = (None, None)
            self.chessboard.clear_preview()

    def _apply_engine_hover_preview(self):
        fen, uci = self._pending_engine_hover
        if not fen or not hasattr(self, "chessboard"):
            return
        try:
            last_move = chess.Move.from_uci(uci) if uci else None
            self.chessboard.set_preview(fen, last_move=last_move, opacity=0.85)
        except Exception:
            self.chessboard.set_preview(fen, opacity=0.85)

    def on_engine_move_clicked(self, move_uci: str, fen: str):
        if not move_uci:
            return
        try:
            move = chess.Move.from_uci(move_uci)
            board = self.chessboard._internal_board
            if move in board.legal_moves:
                self.handle_move(move_uci)
        except Exception:
            pass

    def open_engine_config(self):
        dlg = EngineConfigDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            config = dlg.get_config()
            self.engine.set_settings(config)
            if "multipv" in config:
                mp = int(config["multipv"])
                self.analysis_widget.multipv_limit = mp
                self.analysis_widget.lbl_lines.setText(str(mp))
                self.analysis_widget.update_buttons_state()
            if self.analysis_dock.isVisible() and self.analysis_widget.check_analysis.isChecked():
                self.engine.ensure_started()
                self.send_position(force=True)
            else:
                self.engine.quit()
        else:
            if not (self.analysis_dock.isVisible() and self.analysis_widget.check_analysis.isChecked()):
                self.engine.quit()

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
            self.current_pgn_path = file
            self.current_pgn_offset = None
            self.current_pgn_length = None

    def edit_pgn_headers(self, title="Edit PGN Headers") -> bool:
        dlg = PGNHeadersDialog(self, self.move_manager.game.headers, title=title)
        if dlg.exec_() == QDialog.Accepted:
            new_headers = dlg.get_headers()
            self.move_manager.game.headers.clear()
            for k, v in new_headers.items():
                self.move_manager.game.headers[k] = v
            self.move_manager.create_mapping()
            self.move_manager.is_dirty = True
            self.browser.rebuild_layout(force=True)
            self.display_pgn()
            
            # Immediately update the window title
            white = self.move_manager.game.headers.get("White", "?")
            black = self.move_manager.game.headers.get("Black", "?")
            self.setWindowTitle(f"Chess App — {white} vs {black}")
            
            return True
        return False

    def edit_pgn_headers_action(self):
        self.edit_pgn_headers(title="Edit PGN Headers")

    def copy_pgn_action(self):
        if self.edit_pgn_headers(title="Edit PGN Headers before Copying"):
            self.copy_text(self.move_manager.get_pgn())
            self.statusBar().showMessage("PGN copied to clipboard.")

    def save_pgn(self):
        # Save to currently opened file, or fall back to Save As if none is open
        if self.current_pgn_path:
            if self.edit_pgn_headers(title="Edit PGN Headers before Saving"):
                try:
                    save_game_to_pgn(
                        self.move_manager.game,
                        self.current_pgn_path,
                        offset=self.current_pgn_offset,
                        length=self.current_pgn_length
                    )
                    self.statusBar().showMessage(f"PGN saved to {self.current_pgn_path}")
                    self.move_manager.is_dirty = False
                    self.gameSaved.emit(self.current_pgn_path, self.current_pgn_offset, self.current_pgn_length)
                except Exception as e:
                    QMessageBox.critical(self, "Save Error", f"Could not save PGN: {str(e)}")
        else:
            self.save_pgn_as()

    def save_pgn_as(self):
        if self.edit_pgn_headers(title="Edit PGN Headers before Saving"):
            file, ok = QFileDialog.getSaveFileName(
                self, "Save As", ".", "Pgn Files (*.pgn);;All (*)"
            )
            if ok:
                try:
                    save_game_to_pgn(self.move_manager.game, file)
                    self.current_pgn_path = file
                    self.statusBar().showMessage(f"PGN saved to {file}")
                    self.move_manager.is_dirty = False
                    self.gameSaved.emit(self.current_pgn_path, self.current_pgn_offset, self.current_pgn_length)
                except Exception as e:
                    QMessageBox.critical(self, "Save Error", f"Could not save PGN: {str(e)}")

    def _save_repertoire(self):
        """Save the current PGN back to the active repertoire in the database.

        The editor knows nothing about storage — it simply emits the signal
        with the current PGN and lets the ApplicationController route it to
        the RepertoireRepository via the HomeWindow's tree widget.
        """
        pgn_text = self.move_manager.get_pgn()
        self.repertoireSaveRequested.emit(pgn_text)
        self.move_manager.is_dirty = False
        self.statusBar().showMessage("Repertoire saved.")

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

    def copy_current_fen(self):
        fen = self.chessboard.fen()
        self.copy_text(fen)
        self.statusBar().showMessage("FEN copied to clipboard.")

    def toggle_fen_visibility(self, visible: bool):
        self.fen_container.setVisible(visible)

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

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._ensure_dock_proportions)

    def _ensure_dock_proportions(self):
        """Ensure right dock widgets have adequate width (approx 50/50 split with board)."""
        target_w = max(460, int(self.width() * 0.46))
        docks_to_resize = [d for d in [self.analysis_dock, self.pgn_dock, self.explorer_dock, self.continuations_dock] if d.isVisible()]
        if docks_to_resize:
            if any(d.width() < 380 for d in docks_to_resize) or not hasattr(self, '_dock_proportions_set'):
                self._dock_proportions_set = True
                self.resizeDocks(docks_to_resize, [target_w] * len(docks_to_resize), Qt.Horizontal)

    def _cleanup_resources(self):
        """Stop all background timers and cleanly terminate the engine process."""
        if hasattr(self, "autoplay_timer") and self.autoplay_timer.isActive():
            self.autoplay_timer.stop()
        if hasattr(self, "self_play_timer") and self.self_play_timer.isActive():
            self.self_play_timer.stop()
        if hasattr(self, "analysis_update_timer") and self.analysis_update_timer.isActive():
            self.analysis_update_timer.stop()
        if hasattr(self, "engine_debounce_timer") and self.engine_debounce_timer.isActive():
            self.engine_debounce_timer.stop()
        if hasattr(self, "engine_hover_preview_timer") and self.engine_hover_preview_timer.isActive():
            self.engine_hover_preview_timer.stop()
        if hasattr(self, "engine") and self.engine:
            self.engine.quit()
        self.clear_pending_analysis()

    def closeEvent(self, a0):
        from PyQt5.QtCore import QSettings
        layout_settings = QSettings("TestChessApp", "Layout")
        layout_settings.setValue("windowState", self.saveState())
        layout_settings.setValue("show_fen", "true" if self.show_fen_action.isChecked() else "false")

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
                    self._cleanup_resources()
                    a0.accept()
                else:
                    a0.ignore()
            elif ret == QMessageBox.Discard:
                self.move_manager.is_dirty = False
                self._cleanup_resources()
                a0.accept()
            else:
                a0.ignore()
        else:
            self._cleanup_resources()
            a0.accept()

        if a0.isAccepted():
            self.closed.emit(self)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChessApp()
    window.set_style("dark")
    window.showMaximized()
    sys.exit(app.exec_())
