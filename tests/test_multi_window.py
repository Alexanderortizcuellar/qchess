import pytest
from PyQt5.QtWidgets import QApplication
from unittest.mock import MagicMock

from gui.app_controller import ApplicationController
from core.opening_explorer import OpeningExplorerLogic, SampleGamesTable


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_multi_window_game_selection(qapp):
    controller = ApplicationController()
    try:
        # Initial state has 0 open editors in _editors list
        assert len(controller._editors) == 0

        # Simulate selecting Game 1
        game1_data = {
            "ID": "1",
            "White": "Player One",
            "Black": "Player Two",
            "PGN": "1. e4 e5 2. Nf3 *",
            "_row_idx": 0,
            "_total_rows": 100,
        }
        controller._on_game_selected(game1_data)
        assert len(controller._editors) == 1
        ed1 = controller._editors[0]
        assert "Player One" in ed1.windowTitle()
        assert "1. e4" in ed1.move_manager.get_pgn()

        # Simulate selecting Game 2
        game2_data = {
            "ID": "2",
            "White": "Kasparov",
            "Black": "Karpov",
            "PGN": "1. d4 Nf6 2. c4 *",
            "_row_idx": 1,
            "_total_rows": 100,
        }
        controller._on_game_selected(game2_data)
        assert len(controller._editors) == 2
        ed2 = controller._editors[1]
        assert "Kasparov" in ed2.windowTitle()
        assert "1. d4" in ed2.move_manager.get_pgn()

        # ed1 should be intact and unchanged
        assert "Player One" in ed1.windowTitle()
        assert "1. e4" in ed1.move_manager.get_pgn()

        # Simulate New Analysis
        controller._on_open_editor_requested()
        assert len(controller._editors) == 3
        ed3 = controller._editors[2]
        assert "New Analysis" in ed3.windowTitle()

    finally:
        controller.shutdown()


def test_multi_window_sample_game_selected(qapp):
    controller = ApplicationController()
    try:
        # Mock SCID client get_pgn
        def fake_get_pgn(gid, callback):
            callback({"status": "ok", "data": {"pgn": "1. c4 c5 2. Nc3 *"}})

        controller.home.scid_client.is_running = MagicMock(return_value=True)
        controller.home.scid_client.get_pgn = MagicMock(side_effect=fake_get_pgn)

        # Open initial game window
        initial_game = {
            "ID": "1",
            "White": "Morphy",
            "Black": "Duke",
            "PGN": "1. e4 e5 2. Nf3 d6 *",
        }
        controller._on_game_selected(initial_game)
        assert len(controller._editors) == 1
        source_ed = controller._editors[0]

        # Trigger sample game selection from source_ed
        summary = {
            "white": "Carlsen",
            "black": "Nakamura",
            "result": "1-0",
            "eco": "A30",
        }
        controller._on_sample_game_selected(42, summary, source_editor=source_ed)

        # A new window should have been created
        assert len(controller._editors) == 2
        new_ed = controller._editors[1]

        # Source editor was not overwritten
        assert "Morphy" in source_ed.windowTitle()
        # New editor has the sample game
        assert "Carlsen" in new_ed.windowTitle()
        assert "1. c4" in new_ed.move_manager.get_pgn()

    finally:
        controller.shutdown()


def test_sample_games_table_sorting_and_double_click(qapp):
    table = SampleGamesTable()
    games = [
        {"id": 10, "white": "Alpha", "black": "Beta", "result": "1-0", "eco": "A00", "date": "2020"},
        {"id": 20, "white": "Zeta", "black": "Omega", "result": "0-1", "eco": "B00", "date": "2021"},
    ]
    table.update_games(games)

    selected = []
    table.gameSelected.connect(lambda gid, g: selected.append((gid, g)))

    # Double click first row
    table._on_cell_double_clicked(0, 0)
    assert len(selected) == 1
    assert selected[0][0] == 10
    assert selected[0][1]["white"] == "Alpha"

    # Sort descending by White column (Alpha, Zeta -> Zeta at row 0)
    table.sortItems(0, 1)  # Descending
    table._on_cell_double_clicked(0, 0)
    assert len(selected) == 2
    # Even after sorting, item at row 0 correctly has Zeta (id 20)
    assert selected[1][0] == 20
    assert selected[1][1]["white"] == "Zeta"


def test_editor_close_discard_unregisters_cleanly(qapp, monkeypatch):
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtGui import QCloseEvent

    controller = ApplicationController()
    try:
        # Open an editor
        game_data = {
            "ID": "1",
            "White": "Fischer",
            "Black": "Spassky",
            "PGN": "1. e4 e5 *",
        }
        controller._on_game_selected(game_data)
        assert len(controller._editors) == 1
        ed = controller._editors[0]

        # Modify game to make it dirty
        ed.move_manager.is_dirty = True
        assert ed.move_manager.is_dirty is True

        # Mock QMessageBox.exec_ to simulate clicking "Discard"
        monkeypatch.setattr(QMessageBox, "exec_", lambda self: QMessageBox.Discard)

        # Trigger closeEvent
        event = QCloseEvent()
        ed.closeEvent(event)
        assert event.isAccepted() is True
        assert ed.move_manager.is_dirty is False
        assert len(controller._editors) == 0

        # Now when home window is closed / shutdown is called, no prompts or closed editors remain
        controller.shutdown()
        assert len(controller._editors) == 0
    finally:
        controller.shutdown()

