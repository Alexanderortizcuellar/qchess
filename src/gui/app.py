import re
import sys

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
)

from gui.widgets.analysis_widget import AnalysisWidget
from gui.widgets.chessboard import ChessBoard
from core.engine import ChessEngine
from core.move_manager import MoveManager
from gui.widgets.pgn_browser import PGNBrowser
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
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks)

        # 1. Analysis Dock
        self.analysis_widget = AnalysisWidget(self)
        self.analysis_dock = QDockWidget("Engine Analysis", self)
        self.analysis_dock.setWidget(self.analysis_widget)
        self.analysis_dock.setObjectName("analysis_dock")
        self.addDockWidget(Qt.RightDockWidgetArea, self.analysis_dock)

        # 2. PGN & Navigation Dock
        self.browser = PGNBrowser(self, self.move_manager)
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
        flip_button = _create_iconed_button("ei.refresh", "Ctrl+f", "Flip board")

        pgn_container = QWidget()
        pgn_dock_layout = QVBoxLayout(pgn_container)
        pgn_dock_layout.setContentsMargins(4, 4, 4, 4)
        pgn_dock_layout.setSpacing(4)
        pgn_dock_layout.addWidget(self.browser)

        nav_widget = QWidget()
        nav_widget_layout = QHBoxLayout(nav_widget)
        nav_widget_layout.setContentsMargins(0, 0, 0, 0)
        nav_widget_layout.setSpacing(2)
        for btn in [
            self.jump_to_start_button,
            self.backward_button,
            self.forward_button,
            self.jump_to_end_button,
            flip_button,
        ]:
            nav_widget_layout.addWidget(btn)
        pgn_dock_layout.addWidget(nav_widget)

        actions_widget = QWidget()
        actions_widget_layout = QHBoxLayout(actions_widget)
        actions_widget_layout.setContentsMargins(0, 0, 0, 0)
        actions_widget_layout.setSpacing(2)
        load_fen_btn = _create_iconed_button("fa6s.gear", "Ctrl+l", "Load FEN")
        save_pgn_btn = _create_iconed_button("fa5s.save", "Ctrl+s", "Save Pgn")
        copy_pgn_btn = _create_iconed_button("fa5s.copy", "Ctrl+c", "Copy Pgn")
        clear_btn = _create_iconed_button("fa5s.trash", "Ctrl+d", "Clear Pgn")
        for btn in [load_fen_btn, save_pgn_btn, copy_pgn_btn, clear_btn]:
            actions_widget_layout.addWidget(btn)
        pgn_dock_layout.addWidget(actions_widget)

        self.pgn_dock = QDockWidget("PGN Browser", self)
        self.pgn_dock.setWidget(pgn_container)
        self.pgn_dock.setObjectName("pgn_dock")
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
        self.addDockWidget(Qt.RightDockWidgetArea, self.explorer_dock)
        self.explorer_dock.hide()

        self.splitDockWidget(self.analysis_dock, self.pgn_dock, Qt.Vertical)
        self.splitDockWidget(self.pgn_dock, self.explorer_dock, Qt.Vertical)

        # --- Toolbar & Menubar ---
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        self.init_menubar()
        self.display_pgn()
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
        flip_button.clicked.connect(self.flip_board)
        load_fen_btn.clicked.connect(self.load_fen)
        save_pgn_btn.clicked.connect(self.save_pgn)
        clear_btn.clicked.connect(self.clear_pgn)
        copy_pgn_btn.clicked.connect(lambda _: self.copy_pgn_action())

        self.move_manager.pgnChanged.connect(lambda _: self.display_pgn())
        self.move_manager.activeNodeChanged.connect(self.sync_board_to_pgn)
        self.browser.anchorClicked.connect(self.on_anchor_clicked)
        self.chessboard.fenChanged.connect(self.send_position)
        self.chessboard.fenChanged.connect(self.send_fen_to_opxl)
        self.opxl.errorOcurred.connect(self.statusBar().showMessage)

        self.engine.analysisUpdated.connect(self.on_analysis_updated)
        self.engine.depthChanged.connect(
            lambda depth: self.analysis_widget.set_depth(f"depth={depth}")
        )
        self.engine.moveFound.connect(self.on_best_move_found)

        # Event filter for mouse wheel navigation on chessboard
        self.chessboard.installEventFilter(self)
        self.chessboard.board_view.installEventFilter(self)
        self.chessboard.board_view.viewport().installEventFilter(self)

    def on_analysis_updated(self, info: dict):
        self.analysis_widget.update_analysis(info, self.chessboard.fen())
        if info.get("multipv") == 1:
            s_type = info.get("score_type")
            s_val = info.get("score_value")
            white_pov_score = s_val
            if self.chessboard.turn == chess.BLACK:
                white_pov_score = -s_val
            if s_type == "mate":
                self.bar.setEngineScore({"type": "mate", "value": white_pov_score})
                self.bar.setToolTip(f"Mate in {white_pov_score}")
            else:
                self.bar.setEngineScore({"type": "cp", "value": white_pov_score})
                self.bar.setToolTip(f"{white_pov_score / 100.0:+.2f}")

    def on_best_move_found(self, move_uci: str):
        pass

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

        self.init_toolbar(
            [
                open_action,
                save_action,
                copy_action,
                paste_pgn_action,
                edit_headers_action,
                export_img_action,
                engine_action,
                settings_action,
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
                    variations, font_family=self.current_figurine_font
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

        use_figurine = settings.value("use_figurine_font", True, type=bool)
        if use_figurine:
            self.current_figurine_font = f"'{self.figurine_font_family}'"
        else:
            self.current_figurine_font = "'Segoe UI', Arial, sans-serif"
        
        self.move_manager.font_family = self.current_figurine_font
        self.move_manager.create_mapping()
        self.display_pgn()

        self.browser.setStyleSheet(
            f"QTextBrowser {{font-size:20px; font-family: {self.current_figurine_font};}}"
        )

    def set_style(self, style_name=None):
        if style_name is None:
            action = self.sender()
            if isinstance(action, QAction):
                style_name = action.text().lower()
            else:
                return
        import os

        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(
            os.path.dirname(os.path.dirname(current_dir)), "assets"
        )
        if style_name == "dark":
            qss_file = os.path.join(assets_dir, "style.qss")
            self.move_manager.change_html_style(True)
            self.analysis_widget.set_theme(True)
            self.opxl.set_theme(True)
            from utils.helpers import update_widget_icons

            update_widget_icons(self, True)
        else:
            qss_file = os.path.join(assets_dir, "light_style.qss")
            self.move_manager.change_html_style(False)
            self.analysis_widget.set_theme(False)
            self.opxl.set_theme(False)
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

    def toggle_analysis(self, toggle: bool):
        if toggle:
            self.analysis_widget.reset_lines()
            if not self.engine.is_running():
                self.engine.start()
            self.chessboard.set_eval_bar_visible(True)
            self.fen_label.show()
            self.send_position()
        else:
            self.engine.send_command("stop")
            self.chessboard.set_eval_bar_visible(False)
            self.fen_label.hide()

    def display_pgn(self):
        self.browser.setHtml(self.move_manager.html)

    def on_game_over(self):
        self.engine.send_command("stop")

    def send_fen_to_opxl(self, fen: str):
        if self.opxl.isVisible():
            self.opxl.send_fen(fen)

    def send_position(self):
        if self.analysis_widget.check_analysis.isChecked():
            self.engine.send_command("stop")
            self.analysis_widget.reset_lines()
            from PyQt5.QtCore import QSettings

            settings = QSettings("TestChessApp", "Engine")
            use_time_limit = settings.value("use_time_limit", False, type=bool)
            depth = int(settings.value("depth", 20))
            time_limit = int(settings.value("time_limit", 1000))

            if not use_time_limit:
                self.engine.send_position(
                    self.chessboard.fen(), "depth", options={"depth": depth}
                )
            else:
                self.engine.send_position(
                    self.chessboard.fen(), "time", options={"time": time_limit}
                )

    def open_engine_config(self):
        dlg = EngineConfigDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            self.engine.set_settings(dlg.get_config())
            if self.analysis_widget.check_analysis.isChecked():
                self.send_position()

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
                with open(file, "w") as f:
                    f.write(self.move_manager.get_pgn())
                self.statusBar().showMessage(f"PGN saved to {file}")

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
        if (
            QMessageBox.question(
                self,
                "Quit",
                "Are you sure you want to quit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self.engine.quit()
            a0.accept()
        else:
            a0.ignore()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChessApp()
    window.set_style("dark")
    window.show()
    sys.exit(app.exec_())
