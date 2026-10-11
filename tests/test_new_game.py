import pytest
from PyQt5 import QtCore, QtWidgets
from gui.app import ChessApp


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def test_new_game_action_in_menu(qapp):
    editor = ChessApp()
    try:
        assert hasattr(editor, "new_game_action")
        assert editor.new_game_action.text() == "New Game"
        assert editor.new_game_action.shortcut().toString() == "Ctrl+N"

        # Check action is present in Game menu
        menubar = editor.menuBar()
        game_menu = None
        for action in menubar.actions():
            if action.text() == "&Game":
                game_menu = action.menu()
                break
        assert game_menu is not None
        assert editor.new_game_action in game_menu.actions()
    finally:
        editor.close()


def test_new_game_clears_database_state_and_resets_title(qapp):
    editor = ChessApp()
    try:
        # Simulate an opened database game
        editor.move_manager.update_pgn("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *")
        editor.move_manager.game.headers["White"] = "Carlsen, M."
        editor.move_manager.game.headers["Black"] = "Nakamura, H."
        editor.current_pgn_path = "/path/to/database.pgn"
        editor.current_pgn_offset = 1234
        editor.current_pgn_length = 567
        editor._current_table_row = 42
        editor._current_game_id = 99
        editor.set_matching_plies([3, 5])
        editor.setWindowTitle("Chess App - Game 43/100: Carlsen, M. vs Nakamura, H.")

        assert editor.current_pgn_path is not None
        assert editor._current_table_row == 42
        assert len(editor.matching_plies) == 2
        assert "Carlsen" in editor.windowTitle()
        assert len(list(editor.move_manager.game.mainline())) > 0

        # Trigger new_game
        editor.new_game()

        # Check all database linkages are cleared
        assert editor.current_pgn_path is None
        assert editor.current_pgn_offset is None
        assert editor.current_pgn_length is None
        assert editor._current_table_row is None
        assert editor._current_game_id is None
        assert len(editor.matching_plies) == 0

        # Check moves are cleared and board is at starting FEN
        assert len(list(editor.move_manager.game.mainline())) == 0
        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        assert editor.chessboard.fen().split()[0] == start_fen.split()[0]

        # Check window title is reset
        assert editor.windowTitle() == "Chess App - New Game"

        # Check clear_pgn() has identical behavior
        editor.move_manager.update_pgn("1. d4 d5 *")
        editor.setWindowTitle("Chess App — Player A vs Player B")
        editor.clear_pgn()
        assert editor.windowTitle() == "Chess App - New Game"
        assert len(list(editor.move_manager.game.mainline())) == 0

    finally:
        editor.close()
