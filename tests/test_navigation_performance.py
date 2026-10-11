import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from core.move_manager import MoveManager
from gui.app import ChessApp
from gui.app_controller import ApplicationController


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_initial_position_backward_no_redundant_query(qapp):
    """Test that trying to go backward at the initial position does not emit activeNodeChanged or trigger backend reference queries."""
    app = ChessApp()
    mock_ref_slot = MagicMock()
    app.referenceRequested.connect(mock_ref_slot)

    # Move manager is at starting position (move 0)
    assert app.move_manager.current_node == app.move_manager.game

    # Press backward multiple times
    app.backward()
    app.backward()
    app.backward()

    # Verify no reference query was scheduled or dispatched
    mock_ref_slot.assert_not_called()
    assert not app.reference_debounce_timer.isActive()


def test_forward_backward_navigation_smoothness(qapp):
    """Test that navigating forward and backward updates moves cleanly and debounces reference queries."""
    app = ChessApp()
    mock_ref_slot = MagicMock()
    app.referenceRequested.connect(mock_ref_slot)

    # Load a short game
    pgn_sample = """[Event "Test"]
1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 *"""
    app.move_manager.update_pgn(pgn_sample)
    app.is_explorer_active = MagicMock(return_value=True)

    # Fast forward 4 moves
    app.forward()
    app.forward()
    app.forward()
    app.forward()

    # The moves happened instantly on board
    assert app.move_manager.get_current_ply() == 4
    assert app.reference_debounce_timer.isActive()
    mock_ref_slot.assert_not_called()

    # Trigger debounce timer timeout
    app.reference_debounce_timer.timeout.emit()

    # Now exactly 1 unified reference query was dispatched for the settled position
    assert mock_ref_slot.call_count == 1
    call_args = mock_ref_slot.call_args[0]
    assert call_args[0] == app.chessboard.fen()

    # Now step backward 2 moves
    app.backward()
    app.backward()
    assert app.move_manager.get_current_ply() == 2

    app.reference_debounce_timer.timeout.emit()
    assert mock_ref_slot.call_count == 2
    assert mock_ref_slot.call_args[0][0] == app.chessboard.fen()


def test_position_games_table_columns_exclude_site_and_event(qapp):
    """Verify that PositionGamesWidget does not display Site, Event, or Matches columns."""
    from gui.widgets.position_games_widget import PositionGamesWidget, PositionGamesTableModel

    model = PositionGamesTableModel()
    assert "Site" not in model.HEADERS
    assert "Event" not in model.HEADERS
    assert "Matches" not in model.HEADERS
    assert model.HEADERS == [
        "White",
        "Elo W",
        "Black",
        "Elo B",
        "Res",
        "Date",
        "ECO",
    ]
    assert model.columnCount() == 7
