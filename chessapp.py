import re
import sys
from io import StringIO

import chess.pgn
from PyQt5.QtCore import QUrl
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
)

from analysis_widget import AnalysisWidget
from bar import EvalBar
from chessboard import ChessBoard
from engine import ChessEngine
from movemanager import MoveManager
from pgn_browser import PGNBrowser
from variations_dlg import VariationsDialog
from useful_methods import _create_action, _create_iconed_button, _slot_or_noop
from board_editor import BoardEditorDlg
from opening_explorer import OpeningExplorerLogic

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
        # Create a central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        # Create a vertical layout
        layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        central_widget.setLayout(layout)
        self.move_manager = MoveManager()
        # Create a horizontal layout
        board_bar_container = QWidget()
        board_bar_layout = QHBoxLayout()
        board_bar_container.setLayout(board_bar_layout)
        board_bar_layout.setContentsMargins(0, 0, 0, 0)
        self.bar = EvalBar()
        self.bar.hide()
        self.chessboard = ChessBoard(self, chess.Board().fen(), size=750)
        board_bar_layout.addWidget(self.bar)
        board_bar_layout.addWidget(self.chessboard)
        board_bar_container.setFixedSize(
            self.chessboard.width() + self.bar.width(), self.chessboard.height()
        )
        self.bar.setFixedHeight(self.chessboard.height() - 20)
        left_layout.addWidget(board_bar_container)
        layout.addLayout(left_layout)
        fen_row = QHBoxLayout()
        fen_label = QLabel("FEN:")
        self.fen_edit = QLineEdit()
        self.fen_edit.setReadOnly(True)
        fen_row.addWidget(fen_label)
        fen_row.addWidget(self.fen_edit)
        left_layout.addLayout(fen_row)
        pgn_area_layout = QVBoxLayout()
        layout.addLayout(pgn_area_layout)
        self.analysis_widget = AnalysisWidget(self)
        self.analysis_widget.setFixedHeight(100)
        self.browser = PGNBrowser(self, self.move_manager)
        self.opxl = OpeningExplorerLogic(self)
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
        self.navigation_layout.addWidget(self.jump_to_start_button)
        self.navigation_layout.addWidget(self.backward_button)
        self.navigation_layout.addWidget(self.forward_button)
        self.navigation_layout.addWidget(self.jump_to_end_button)
        self.navigation_layout.addWidget(flip_button)
        actions_layout = QHBoxLayout()
        load_fen_btn = _create_iconed_button("fa6s.gear", "Ctrl+l", "Load FEN")
        save_pgn_btn = _create_iconed_button("fa5s.save", "Ctrl+s", "Save Pgn")
        copy_pgn_btn = _create_iconed_button("fa5s.copy", "Ctrl+c", "Copy Pgn")
        clear_btn = _create_iconed_button("fa5s.trash", "Ctrl+d", "Clear Pgn")
        actions_layout.addWidget(load_fen_btn)
        actions_layout.addWidget(save_pgn_btn)
        actions_layout.addWidget(copy_pgn_btn)
        actions_layout.addWidget(clear_btn)
        pgn_area_layout.addWidget(self.analysis_widget)
        pgn_area_layout.addWidget(self.browser)
        pgn_area_layout.addWidget(self.opxl)
        pgn_area_layout.addLayout(self.navigation_layout)
        pgn_area_layout.addLayout(actions_layout)

        self.engine = ChessEngine("stockfish", self)
        self.init_menubar()
        self.display_pgn()
        # Connect signals
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
        copy_pgn_btn.clicked.connect(
            lambda _: self.copy_text(self.move_manager.get_pgn())
        )
        self.move_manager.pgnChanged.connect(lambda _: self.display_pgn())
        self.browser.anchorClicked.connect(self.on_anchor_clicked)
        self.chessboard.fenChanged.connect(self.send_position)
        self.chessboard.fenChanged.connect(self.send_fen_to_opxl)
        self.opxl.errorOcurred.connect(self.statusBar().showMessage)
        self.engine.cpScoreFound.connect(self.get_score)
        self.engine.depthChanged.connect(
            lambda depth: self.analysis_widget.set_depth(f"depth={depth}")
        )
        self.engine.lineFound.connect(self.on_lines_found)
        self.engine.mateFound.connect(self.get_mate)
        # self.engine.start()
        # self.engine.set_threads(5)

    def set_html_style(self, html_style: bool):
        """Set the HTML style to either light or dark. (True for dark, False for light)"""
        self.move_manager.change_html_style(html_style)

    def init_menubar(self):
        file_menu = self.menuBar().addMenu("&File")
        open_action = _create_action(
            self,
            "Open",
            _slot_or_noop(self, "open_pgn"),
            "Ctrl+O",
            icon_name="fa5s.folder-open",
            status_tip="Open a pgn file",
            tool_tip="Open a pgn file",
        )
        save_action = _create_action(
            self,
            "Save",
            _slot_or_noop(self, "save_pgn"),
            "Ctrl+S",
            icon_name="fa5s.save",
            status_tip="Save a pgn file",
            tool_tip="Save a pgn file",
        )
        quit_action = _create_action(
            self,
            "Quit",
            _slot_or_noop(self, "close"),
            "Ctrl+Q",
            icon_name="fa5s.times-circle",
            status_tip="Quit the application",
            tool_tip="Quit the application",
        )
        view_menu = self.menuBar().addMenu("&View")
        dark_action = _create_action(
            self,
            "Dark",
            _slot_or_noop(self, "set_style"),
            "Ctrl+D",
            status_tip="Set HTML style to dark",
            tool_tip="Set HTML style to dark",
        )
        light_action = _create_action(
            self,
            "Light",
            _slot_or_noop(self, "set_style"),
            "Ctrl+L",
            status_tip="Set HTML style to light",
            tool_tip="Set HTML style to light",
        )
        moves_explorer_action = _create_action(
            self,
            "Moves Explorer",
            _slot_or_noop(self, "enable_moves_explorer"),
            "Ctrl+M",
            status_tip="Open moves explorer",
            tool_tip="Open moves explorer",
            checkable=True,
            checked=True,
        )
        file_menu.addAction(open_action)
        file_menu.addAction(save_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)
        view_menu.addAction(dark_action)
        view_menu.addAction(light_action)
        view_menu.addSeparator()
        view_menu.addAction(moves_explorer_action)
        self.init_toolbar([open_action, save_action])

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
                self.send_position()
                return
            self.engine.start()
            self.bar.show()
            self.send_position()
        else:
            self.engine.send_command("stop")
            self.bar.hide()

    def enable_moves_explorer(self, toggle: bool):
        if toggle:
            self.opxl.setVisible(True)
        else:
            self.opxl.setVisible(False)

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
    window.set_html_style(True)
    window.show()
    sys.exit(app.exec_())
