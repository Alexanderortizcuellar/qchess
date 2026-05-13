import re
import sys
from io import StringIO

import chess.pgn
from PyQt5.QtCore import QUrl, Qt
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
)

from gui.widgets.analysis_widget import AnalysisWidget
from gui.widgets.eval_bar import EvalBar
from gui.widgets.chessboard import ChessBoard
from core.engine import ChessEngine
from core.move_manager import MoveManager
from gui.widgets.pgn_browser import PGNBrowser
from gui.dialogs.variations_dlg import VariationsDialog
from utils.helpers import _create_action, _create_iconed_button
from gui.dialogs.board_editor import BoardEditorDlg
from core.opening_explorer import OpeningExplorerLogic

text = """[Event "?"]
[Site "?"]
[Date "????.??.??"]
[Round "?"]
[White "?"]
[Black "?"]
[Result "*"]
[Link "https://www.chess.com/analysis/game/pgn/4HSfSCP8L6/analysis"]

1. e4 { nada to show } e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 (4. Ng5 d5 5. exd5 Nxd5 (5... Na5 6. Bb5+
c6 7. dxc6 bxc6 8. Bd3 (8. Be2 h6 9. Nf3) 8... Nd5) 6. Nxf7 Kxf7 7. Qf3+ Ke6 8.
Nc3 Nb4 9. O-O c6) 4... Bc5 5. O-O *"""


class ChessApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess App")
        self.move_manager = MoveManager()
        self.engine = ChessEngine("stockfish", self)

        # --- Central Widget (Board Area) ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        central_layout = QVBoxLayout(central_widget)
        central_layout.addStretch()

        # Board and FEN group
        board_group = QWidget()
        board_group_layout = QVBoxLayout(board_group)
        board_group_layout.setContentsMargins(0, 0, 0, 0)
        board_group_layout.setSpacing(10)

        board_bar_container = QWidget()
        board_bar_layout = QHBoxLayout(board_bar_container)
        board_bar_layout.setContentsMargins(0, 0, 0, 0)
        board_bar_layout.setSpacing(10)
        
        self.bar = EvalBar()
        self.bar.hide()
        self.chessboard = ChessBoard(self, chess.Board().fen(), size=750)
        
        board_bar_layout.addWidget(self.bar)
        board_bar_layout.addWidget(self.chessboard)
        
        # We don't necessarily need a fixed size if the layout handles it, 
        # but let's keep it consistent with the board row for now if needed.
        # Actually, removing fixed size might help with centering when bar is hidden.
        # board_bar_container.setFixedSize(
        #     self.chessboard.width() + self.bar.width() + 10, self.chessboard.height()
        # )
        self.bar.setFixedHeight(self.chessboard.height() - 20)
        board_group_layout.addWidget(board_bar_container)

        self.fen_row = QHBoxLayout()
        self.fen_row.setContentsMargins(0, 0, 0, 0)
        self.fen_row.setSpacing(10)
        
        self.fen_label = QLabel("FEN:")
        self.fen_label.setFixedWidth(self.bar.width())
        self.fen_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        
        self.fen_edit = QLineEdit()
        self.fen_edit.setReadOnly(True)
        # Ensure FEN edit matches the board width
        self.fen_edit.setFixedWidth(self.chessboard.width())
        
        self.fen_row.addWidget(self.fen_label)
        self.fen_row.addWidget(self.fen_edit)
        board_group_layout.addLayout(self.fen_row)
        
        # Sync visibility with eval bar
        self.fen_label.setVisible(self.bar.isVisible())

        central_layout.addWidget(board_group, alignment=Qt.AlignCenter)
        central_layout.addStretch()

        # --- Docks ---
        self.setDockOptions(QMainWindow.AnimatedDocks | QMainWindow.AllowTabbedDocks)

        # 1. Analysis Dock (Top Right)
        self.analysis_widget = AnalysisWidget(self)
        self.analysis_dock = QDockWidget("Engine Analysis", self)
        self.analysis_dock.setWidget(self.analysis_widget)
        self.analysis_dock.setObjectName("analysis_dock")
        self.addDockWidget(Qt.RightDockWidgetArea, self.analysis_dock)

        # 2. PGN & Navigation Dock (Under Analysis)
        self.browser = PGNBrowser(self, self.move_manager)
        self.navigation_layout = QHBoxLayout()
        self.jump_to_start_button = _create_iconed_button("ph.caret-double-left-fill", "Home")
        self.backward_button = _create_iconed_button("mdi.skip-previous", "Left", "Navigate back")
        self.forward_button = _create_iconed_button("mdi.skip-next", "Right", "Navigate forward")
        self.jump_to_end_button = _create_iconed_button("mdi.skip-next", "End", "Navigate to end")
        flip_button = _create_iconed_button("ei.refresh", "Ctrl+f", "Flip board")
        for btn in [self.jump_to_start_button, self.backward_button, self.forward_button, self.jump_to_end_button, flip_button]:
            self.navigation_layout.addWidget(btn)

        actions_layout = QHBoxLayout()
        load_fen_btn = _create_iconed_button("fa6s.gear", "Ctrl+l", "Load FEN")
        save_pgn_btn = _create_iconed_button("fa5s.save", "Ctrl+s", "Save Pgn")
        copy_pgn_btn = _create_iconed_button("fa5s.copy", "Ctrl+c", "Copy Pgn")
        clear_btn = _create_iconed_button("fa5s.trash", "Ctrl+d", "Clear Pgn")
        for btn in [load_fen_btn, save_pgn_btn, copy_pgn_btn, clear_btn]:
            actions_layout.addWidget(btn)

        pgn_container = QWidget()
        pgn_dock_layout = QVBoxLayout(pgn_container)
        pgn_dock_layout.setContentsMargins(4, 4, 4, 4)
        pgn_dock_layout.setSpacing(4)
        pgn_dock_layout.addWidget(self.browser)
        
        # Navigation buttons container
        nav_widget = QWidget()
        nav_widget_layout = QHBoxLayout(nav_widget)
        nav_widget_layout.setContentsMargins(0, 0, 0, 0)
        nav_widget_layout.setSpacing(2)
        for btn in [self.jump_to_start_button, self.backward_button, self.forward_button, self.jump_to_end_button, flip_button]:
            nav_widget_layout.addWidget(btn)
        pgn_dock_layout.addWidget(nav_widget)

        # Actions buttons container
        actions_widget = QWidget()
        actions_widget_layout = QHBoxLayout(actions_widget)
        actions_widget_layout.setContentsMargins(0, 0, 0, 0)
        actions_widget_layout.setSpacing(2)
        for btn in [load_fen_btn, save_pgn_btn, copy_pgn_btn, clear_btn]:
            actions_widget_layout.addWidget(btn)
        pgn_dock_layout.addWidget(actions_widget)

        self.pgn_dock = QDockWidget("PGN Browser", self)
        self.pgn_dock.setWidget(pgn_container)
        self.pgn_dock.setObjectName("pgn_dock")
        self.addDockWidget(Qt.RightDockWidgetArea, self.pgn_dock)

        # 3. Opening Explorer Dock (Under PGN)
        self.opxl = OpeningExplorerLogic(self)
        self.explorer_dock = QDockWidget("Opening Explorer", self)
        self.explorer_dock.setWidget(self.opxl)
        self.explorer_dock.setObjectName("explorer_dock")
        self.addDockWidget(Qt.RightDockWidgetArea, self.explorer_dock)
        self.explorer_dock.hide()  # Hidden by default

        # Arrange docks vertically on the right
        self.splitDockWidget(self.analysis_dock, self.pgn_dock, Qt.Vertical)
        self.splitDockWidget(self.pgn_dock, self.explorer_dock, Qt.Vertical)

        # --- Toolbar & Menubar ---
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        self.init_menubar()
        self.display_pgn()

        # --- Signals ---
        self.chessboard.moveMade.connect(self.handle_move)
        self.chessboard.fenChanged.connect(self.fen_edit.setText)
        self.analysis_widget.check_analysis.toggled.connect(self.toggle_analysis)
        self.chessboard.GameOver.connect(self.on_game_over)
        self.forward_button.clicked.connect(self.forward)
        self.backward_button.clicked.connect(self.backward)
        self.jump_to_start_button.clicked.connect(self.jump_to_start)
        self.jump_to_end_button.clicked.connect(self.jump_to_end)
        flip_button.clicked.connect(self.flip_board)
        load_fen_btn.clicked.connect(self.load_fen)
        save_pgn_btn.clicked.connect(self.save_pgn)
        clear_btn.clicked.connect(self.clear_pgn)
        copy_pgn_btn.clicked.connect(lambda _: self.copy_text(self.move_manager.get_pgn()))
        self.move_manager.pgnChanged.connect(lambda _: self.display_pgn())
        self.browser.anchorClicked.connect(self.on_anchor_clicked)
        self.chessboard.fenChanged.connect(self.send_position)
        self.chessboard.fenChanged.connect(self.send_fen_to_opxl)
        self.opxl.errorOcurred.connect(self.statusBar().showMessage)
        self.engine.cpScoreFound.connect(self.get_score)
        self.engine.depthChanged.connect(lambda depth: self.analysis_widget.set_depth(f"depth={depth}"))
        self.engine.lineFound.connect(self.on_lines_found)
        self.engine.mateFound.connect(self.get_mate)

    def set_html_style(self, html_style: bool):
        """Set the HTML style to either light or dark. (True for dark, False for light)"""
        self.move_manager.change_html_style(html_style)

    def init_menubar(self):
        file_menu = self.menuBar().addMenu("&File")
        open_action = _create_action(
            self,
            "Open",
            self.open_pgn,
            "Ctrl+O",
            icon_name="fa5s.folder-open",
            status_tip="Open a pgn file",
            tool_tip="Open a pgn file",
        )
        save_action = _create_action(
            self,
            "Save",
            self.save_pgn,
            "Ctrl+S",
            icon_name="fa5s.save",
            status_tip="Save a pgn file",
            tool_tip="Save a pgn file",
        )
        quit_action = _create_action(
            self,
            "Quit",
            self.close,
            "Ctrl+Q",
            icon_name="fa5s.times-circle",
            status_tip="Quit the application",
            tool_tip="Quit the application",
        )
        view_menu = self.menuBar().addMenu("&View")
        dark_action = _create_action(
            self,
            "Dark",
            lambda: self.set_style("dark"),
            "Ctrl+D",
            status_tip="Set HTML style to dark",
            tool_tip="Set HTML style to dark",
        )
        light_action = _create_action(
            self,
            "Light",
            lambda: self.set_style("light"),
            "Ctrl+L",
            status_tip="Set HTML style to light",
            tool_tip="Set HTML style to light",
        )
        
        docks_menu = view_menu.addMenu("&Docks")
        docks_menu.addAction(self.pgn_dock.toggleViewAction())
        docks_menu.addAction(self.analysis_dock.toggleViewAction())
        docks_menu.addAction(self.explorer_dock.toggleViewAction())

        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
        view_menu.addAction(dark_action)
        view_menu.addAction(light_action)
        self.init_toolbar([open_action, save_action])

    def set_style(self, style_name=None):
        print(f"DEBUG: set_style called with style_name={style_name}")
        if style_name is None:
            action = self.sender()
            print(f"DEBUG: sender is {action}")
            if isinstance(action, QAction):
                style_name = action.text().lower()
                print(f"DEBUG: style_name from action text: {style_name}")
            else:
                print("DEBUG: sender is not a QAction, returning")
                return
            
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "assets")
        print(f"DEBUG: assets_dir is {assets_dir}")
        
        if style_name == "dark":
            qss_file = os.path.join(assets_dir, "style.qss")
            print(f"DEBUG: applying dark theme from {qss_file}")
            self.set_html_style(True)
            self.analysis_widget.set_theme(True)
            self.opxl.set_theme(True)
            from utils.helpers import update_widget_icons
            update_widget_icons(self, True)
        else:
            qss_file = os.path.join(assets_dir, "light_style.qss")
            print(f"DEBUG: applying light theme from {qss_file}")
            self.set_html_style(False)
            self.analysis_widget.set_theme(False)
            self.opxl.set_theme(False)
            from utils.helpers import update_widget_icons
            update_widget_icons(self, False)
        
        try:
            with open(qss_file, "r") as f:
                content = f.read()
                print(f"DEBUG: QSS content length: {len(content)}")
                QApplication.instance().setStyleSheet(content)
                print("DEBUG: setStyleSheet called successfully")
        except Exception as e:
            print(f"DEBUG: Error loading theme: {e}")
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
            dlg = BoardEditorDlg(self)
            dlg.exec_()

    def on_anchor_clicked(self, url: QUrl):
        match = re.match(r"move\((\d+)\)", url.toString())
        if match:
            idx = int(match.group(1))
            self.move_manager.jump_to(idx)
            fen = self.move_manager.current_node.board().fen()
            self.chessboard.update_board(fen, self.move_manager.current_node.move)

    def handle_move(self, move_uci):
        """Handle a move made on the chessboard."""
        self.move_manager.make_move(move_uci)
        # self.chessboard.update_board(self.move_manager.get_board())
        self.display_pgn()

    def toggle_analysis(self, toggle: bool):
        if toggle:
            if self.engine.is_running():
                self.bar.show()
                self.fen_label.show()
                self.send_position()
                return
            self.engine.start()
            self.bar.show()
            self.fen_label.show()
            self.send_position()
        else:
            self.engine.send_command("stop")
            self.bar.hide()
            self.fen_label.hide()

    def enable_moves_explorer(self, toggle: bool):
        self.explorer_dock.setVisible(toggle)

    def forward(self):
        """Go forward in the move variations."""
        if self.move_manager.has_variations():
            variations = self.move_manager.get_current_node_variations()
            if len(variations) > 1:
                dialog = VariationsDialog(variations)
                if dialog.exec_() != QDialog.Accepted:
                    return
                if dialog.selected_index is None:
                    return
                self.move_manager.redo(dialog.selected_index)
            else:
                self.move_manager.redo()

            # move_from = self.move_manager.current_node.move
            # self.chessboard.animate_move(move_from, False)
            self.chessboard.update_board(
                self.move_manager.get_board().fen(), self.move_manager.current_node.move
            )
            self.display_pgn()

    def backward(self):
        """Go backward in the move variations."""
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

    def display_pgn(self):
        """Display the current PGN in the text browser."""
        html = self.move_manager.html
        self.browser.setHtml(html)

    def on_game_over(self):
        self.engine.send_command("stop")

    def send_fen_to_opxl(self, fen: str):
        if self.opxl.isVisible():
            self.opxl.send_fen(fen)

    def send_position(self):
        if self.analysis_widget.check_analysis.isChecked():
            self.engine.send_command("stop")
            self.engine.send_position(
                self.chessboard.fen(), "depth", options={"depth": 60}
            )

    def normalize_score(self, score) -> int:
        score = max(-10, min(10, score))
        return int((score + 10) / 20 * 1000)

    def on_lines_found(self, lines: list[str]):
        if self.chessboard.dragging:
            return
        board = chess.Board(self.chessboard.fen())
        if len(lines) >= 1:
            move1_uci = lines[0]
            move1 = chess.Move.from_uci(move1_uci)
            if move1 not in board.legal_moves:
                return
        header = f'[FEN "{board.fen()}"]\n\n'
        pgn = header + " ".join(lines)
        move1_uci = lines[0]
        move1 = chess.Move.from_uci(move1_uci)
        game = chess.pgn.read_game(StringIO(pgn))
        self.analysis_widget.set_line_text(str(game.mainline_moves()))

    def get_score(self, score: int):
        if self.chessboard.turn:
            if score < 0:
                score = score
            else:
                score = score
        else:
            if score > 0:
                score = -score
            else:
                score = abs(score)
        self.bar.setEngineScore({"type": "cp", "value": score})
        self.bar.setToolTip(str(score / 100))
        self.analysis_widget.set_score(str(score / 100))

    def get_mate(self, matein: int):
        if matein == 0:
            return
        if matein > 0:
            if self.chessboard.turn:
                self.bar.setEngineScore({"type": "mate", "value": matein})
            else:
                self.bar.setEngineScore({"type": "mate", "value": -matein})
        else:
            if self.chessboard.turn:
                self.bar.setEngineScore({"type": "mate", "value": matein})
            else:
                self.bar.setEngineScore({"type": "mate", "value": -matein})
        self.analysis_widget.set_score(f"M{matein}")
        self.bar.setToolTip(f"M{matein}")

    def open_pgn(self):
        file, ok = QFileDialog.getOpenFileName(
            self, "Open", ".", "Pgn Files (*.pgn);;All (*)"
        )
        if ok:
            self.move_manager.load_pgn_file(file)

    def save_pgn(self):
        file, ok = QFileDialog.getSaveFileName(
            self, "Save", ".", "Pgn Files (*.pgn);;All (*)"
        )
        if ok:
            with open(file) as f:
                f.write(self.move_manager.get_pgn())

    def copy_text(self, text: str):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def closeEvent(self, a0):
        msg = QMessageBox.question(
            self,
            "Quit",
            "Are you sure you want to quit?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if msg == QMessageBox.Yes:
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
