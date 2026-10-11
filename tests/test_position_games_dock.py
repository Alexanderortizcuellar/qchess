import pytest
from unittest.mock import MagicMock, ANY
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from core.scid_client import ScidClient
from gui.widgets.position_games_widget import PositionGamesWidget, PositionGamesTableModel
from gui.app import ChessApp
from core.reference_filters import get_reference_filter_manager


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_scid_client_reference_and_query_games_owner():
    """Verify ScidClient properly dispatches reference and query_games with owner parameter."""
    client = ScidClient()
    client.send_request = MagicMock(return_value=1)

    # Test reference orchestrator call
    client.reference(
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        include_tree=False,
        include_continuations=False,
        include_endgames=False,
        include_games=True,
        page=0,
        page_size=50,
        sort_by="date",
        sort_asc=False,
        filters={"min_elo": 2400},
    )

    client.send_request.assert_called_with("reference", {
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "include_tree": False,
        "include_continuations": False,
        "include_endgames": False,
        "include_games": True,
        "page": 0,
        "page_size": 50,
        "sort_by": "date",
        "sort_asc": False,
        "filter": {"min_elo": 2400},
    }, None)

    # Test query_games with owner="reference"
    client.query_games(
        page=1,
        page_size=50,
        sort_by="white_elo",
        sort_asc=False,
        search_id="ref_1",
        owner="reference",
    )

    client.send_request.assert_called_with("query_games", {
        "page": 1,
        "page_size": 50,
        "search_id": "ref_1",
        "owner": "reference",
        "sort_by": "white_elo",
        "sort_asc": False,
        "sort_direction": "DESC",
    }, None)


def test_position_games_table_model(qapp):
    """Test PositionGamesTableModel data formatting, lazy chunk retrieval, and column sorting."""
    client = ScidClient()
    client.is_running = MagicMock(return_value=True)
    client.query_games = MagicMock()

    model = PositionGamesTableModel(client=client)
    assert model.columnCount() == 7
    assert model.rowCount() == 0

    mock_games = [
        {
            "id": 100,
            "white": "Kasparov, G.",
            "white_elo": 2812,
            "black": "Karpov, A.",
            "black_elo": 2775,
            "result": "1-0",
            "date": "1990.11.24",
            "year": 1990,
            "eco": "E97",
            "event": "World Championship",
            "site": "Lyon / New York",
            "matching_plies": [24, 38],
            "match_count": 2,
        },
        {
            "id": 101,
            "white": "Fischer, R.",
            "white_elo": 2785,
            "black": "Spassky, B.",
            "black_elo": 2660,
            "result": "1-0",
            "date": "1972.07.23",
            "year": 1972,
            "eco": "E41",
            "event": "World Championship",
            "site": "Reykjavik",
            "matching_plies": [19],
            "match_count": 1,
        },
    ]

    # Initialize session with 2 total games
    model.set_search_session(
        total_count=2,
        search_id="ref_1",
        initial_games=mock_games,
        owner="reference",
    )

    assert model.rowCount() == 2
    assert model.columnCount() == 7
    assert model.data(model.index(0, 0), Qt.DisplayRole) == "Kasparov, G."
    assert model.data(model.index(0, 1), Qt.DisplayRole) == "2812"
    assert model.data(model.index(0, 2), Qt.DisplayRole) == "Karpov, A."
    assert model.data(model.index(0, 3), Qt.DisplayRole) == "2775"
    assert model.data(model.index(0, 4), Qt.DisplayRole) == "1-0"
    assert model.data(model.index(0, 5), Qt.DisplayRole) == "1990.11.24"
    assert model.data(model.index(1, 5), Qt.DisplayRole) == "1972.07.23"
    assert model.data(model.index(0, 6), Qt.DisplayRole) == "E97"

    # Test tooltip
    tip = model.data(model.index(0, 0), Qt.ToolTipRole)
    assert "Kasparov, G. (2812) vs Karpov, A. (2775)" in tip
    assert "Matching Plies: [24, 38]" in tip

    # Test sorting column trigger
    model.toggle_sort_column(1)  # White Elo
    client.query_games.assert_called_with(
        page=0,
        page_size=25,
        sort_by="white_elo",
        sort_asc=False,
        search_id="ref_1",
        owner="reference",
    )


def test_position_games_widget_signals_and_theme(qapp):
    """Verify PositionGamesWidget properly emits queryRequested, handles selection, and themes."""
    widget = PositionGamesWidget()

    # Verify initial theme
    widget.set_theme(True)
    assert widget.is_dark is True

    widget.set_theme(False)
    assert widget.is_dark is False

    # Test FEN query emission
    queries = []
    widget.queryRequested.connect(lambda fen, flt: queries.append((fen, flt)))

    start_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    widget.send_fen(start_fen)
    assert len(queries) == 1
    assert queries[0][0] == start_fen

    # Test double click selection emission
    selected_games = []
    widget.gameSelected.connect(lambda gid, summ: selected_games.append((gid, summ)))

    mock_game = {
        "id": 42,
        "white": "Tal, M.",
        "black": "Botvinnik, M.",
        "result": "1-0",
        "date": "1960",
        "matching_plies": [21],
    }
    widget.set_search_session("ref_tal", 1, initial_games=[mock_game])

    widget._on_row_double_clicked(widget.model.index(0, 0))
    assert len(selected_games) == 1
    assert selected_games[0][0] == 42
    assert selected_games[0][1]["white"] == "Tal, M."


def test_chess_app_games_dock_integration(qapp):
    """Test ChessApp instantiates sidebar_tab_widget and position_games_widget, connects signals, and toggles visibility."""
    app = ChessApp()
    try:
        assert hasattr(app, "sidebar_tab_widget")
        assert hasattr(app, "position_games_widget")
        assert hasattr(app, "pgn_dock")
        assert app.pgn_dock.objectName() == "pgn_dock"
        assert app.sidebar_tab_widget.currentIndex() == 0  # Notation tab by default

        # Initial state is not active because Notation tab (index 0) is active
        assert not app.is_games_active()

        # Mock referenceRequested signal
        mock_slot = MagicMock()
        app.referenceRequested.connect(mock_slot)

        # When Reference tab is not active, send_fen_to_games(force=False) does not trigger query
        app.send_fen_to_games("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", force=False)
        mock_slot.assert_not_called()

        # With force=True, send_fen_to_games queries regardless of tab
        app.send_fen_to_games("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", force=True)
        mock_slot.assert_called_once_with("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", True)
    finally:
        app.close()


def test_application_controller_position_games_query(qapp):
    """Verify ApplicationController routes unified reference call and populates PositionGamesWidget session."""
    from gui.app_controller import ApplicationController

    ctrl = ApplicationController()
    try:
        ctrl.ref_filter_mgr.clear_filters()
        ctrl.home.scid_client.is_running = MagicMock(return_value=True)
        ctrl.home._current_db_path = "tests/fixtures/sample.si5"

        editor = ctrl._create_editor()
        editor.continuations_widget.max_lines = 6
        editor.position_games_widget.set_search_session = MagicMock()
        editor.is_games_active = MagicMock(return_value=True)
        editor.is_explorer_active = MagicMock(return_value=True)
        editor.is_continuations_active = MagicMock(return_value=False)
        editor.is_endgames_active = MagicMock(return_value=False)

        # Mock unified reference response
        ctrl.home.scid_client.reference = MagicMock(side_effect=lambda **kwargs: kwargs["callback"]({
            "status": "ok",
            "data": {
                "search_id": "ref_1",
                "total_games": 85,
                "tree": {"moves": [], "total_games": 85},
                "games": [{"id": 1, "white": "Player A", "black": "Player B"}],
            }
        }))

        fen_test = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
        ctrl._on_position_games_query_requested(fen_test, {}, editor)

        ctrl.home.scid_client.reference.assert_called_with(
            fen=fen_test,
            include_tree=True,
            include_continuations=False,
            include_endgames=False,
            include_games=True,
            page=0,
            page_size=25,
            filters=None,
            continuation_depth=8,
            max_lines=6,
            min_games=1,
            min_percentage=0.0,
            callback=ANY,
        )
        editor.position_games_widget.set_search_session.assert_called_with(
            search_id="ref_1",
            total_count=85,
            filters=None,
            initial_games=[{"id": 1, "white": "Player A", "black": "Player B"}],
            owner="reference",
        )
    finally:
        ctrl.shutdown()
