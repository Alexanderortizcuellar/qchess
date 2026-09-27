import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from core.move_manager import MoveManager
from core.scid_client import ScidClient
from gui.widgets.game_list_table import GameListTableModel
from gui.widgets.game_preview_widget import GamePreviewWidget

# Ensure QApplication exists for Qt widget tests
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_move_manager_goto_ply():
    """Test jumping to specific plies along the mainline."""
    mm = MoveManager()
    # 1. e4 e5 2. Nf3 Nc6 3. Bb5
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]
    for uci_str in moves:
        mm.make_move(uci_str)

    assert mm.get_current_ply() == 5

    # Jump to start position (ply 0)
    mm.goto_ply(0)
    assert mm.get_current_ply() == 0
    assert mm.current_node == mm.game

    # Jump to ply 1 (1. e4)
    mm.goto_ply(1)
    assert mm.get_current_ply() == 1
    assert mm.current_node.move.uci() == "e2e4"

    # Jump to ply 4 (2... Nc6)
    mm.goto_ply(4)
    assert mm.get_current_ply() == 4
    assert mm.current_node.move.uci() == "b8c6"

    # Jump beyond available mainline ply
    mm.goto_ply(100)
    assert mm.get_current_ply() == 5
    assert mm.current_node.move.uci() == "f1b5"


def test_scid_client_search_methods():
    """Verify ScidClient properly dispatches search session RPCs."""
    client = ScidClient()
    client.send_request = MagicMock(return_value=1)

    # Test query_games with search_id and sort_asc
    client.query_games(page=0, page_size=20, sort_by="year", sort_asc=False, search_id="s_123")
    client.send_request.assert_called_with("query_games", {
        "page": 0,
        "page_size": 20,
        "sort_by": "year",
        "sort_asc": False,
        "sort_direction": "DESC",
        "search_id": "s_123"
    }, None)

    # Test unified search
    search_filter = {"white": "Kasparov", "result": "1-0", "eco": "B90"}
    client.search(search_filter)
    client.send_request.assert_called_with("search", search_filter, None)

    # Test search_cql
    client.search_cql("(match (position :piece count K == 1))")
    client.send_request.assert_called_with("search", {
        "query": "(match (position :piece count K == 1))"
    }, None)

    # Test search_position
    client.search_position("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1", turn="both", match_mode="exact", max_ply=10)
    client.send_request.assert_called_with("search_position", {
        "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        "turn": "both",
        "match_mode": "exact",
        "max_ply": 10
    }, None)

    # Test search_material
    mat_filter = {"white_pawns": 8, "white_queens": 1, "black_queens": 0, "strict": True}
    client.search_material(mat_filter)
    client.send_request.assert_called_with("search_material", mat_filter, None)


def test_advanced_search_dialog_category_isolation(qapp):
    """Verify AdvancedSearchDialog isolates tabs without contaminating FEN into header searches."""
    from gui.dialogs.advanced_search_dialog import AdvancedSearchDialog

    dlg = AdvancedSearchDialog()

    # Case 1: Only Game Info (Result: 1-0)
    dlg.in_result.setCurrentText("1-0")
    assert dlg.chk_enable_info.isChecked()
    assert not dlg.chk_enable_pos.isChecked()
    assert not dlg.chk_enable_mat.isChecked()
    assert not dlg.chk_enable_query.isChecked()

    f1 = dlg.get_filter_dict()
    assert f1.get("result") == "1-0"
    assert "fen" not in f1
    assert "material" not in f1
    assert "query" not in f1

    # Case 2: Enable Position tab criteria as well
    dlg.chk_enable_pos.setChecked(True)
    dlg.in_fen.setText("8/8/8/8/3Q4/8/8/8")
    f2 = dlg.get_filter_dict()
    assert f2.get("result") == "1-0"
    assert f2.get("fen") == "8/8/8/8/3Q4/8/8/8"
    assert f2.get("match_mode") == "board_only"

    # Case 3: Reset
    dlg.reset_all()
    f3 = dlg.get_filter_dict()
    assert "result" not in f3
    assert "fen" not in f3
    assert not dlg.chk_enable_info.isChecked()
    assert not dlg.chk_enable_pos.isChecked()


def test_game_list_table_columns_and_match_metadata(qapp):
    """Test GameListTableModel column count and match metadata caching."""
    model = GameListTableModel()
    
    # 12 columns (Matches column was removed from table display)
    assert model.columnCount() == 12
    headers = [model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) for col in range(12)]
    assert "Matches" not in headers
    assert headers == ["ID", "White", "EloW", "Black", "EloB", "Result", "ECO", "Date", "Event", "Site", "Round", "Status"]

    # Mock chunk data with match_count and matching_plies
    mock_game = {
        "id": 1,
        "white": "Carlsen, M.",
        "black": "Nakamura, H.",
        "result": "1-0",
        "date": "2024.01.01",
        "event": "Titled Tuesday",
        "site": "chess.com",
        "round": "1",
        "white_elo": 2880,
        "black_elo": 2875,
        "eco": "B01",
        "ply_count": 60,
        "match_count": 3,
        "matching_plies": [11, 23, 45]
    }
    
    model.set_db(1, search_id="search_123")
    model.cached_chunks[0] = [mock_game]

    # Check cached metadata is preserved for preview/viewer navigation
    game_item = model.get_game_at(0)
    assert game_item is not None
    assert game_item.get("matching_plies") == [11, 23, 45]
    assert game_item.get("match_count") == 3


def test_game_preview_widget_stepping(qapp):
    """Test GamePreviewWidget auto-jump and stepping through matching plies."""
    widget = GamePreviewWidget()
    
    pgn_text = """[Event "Test"]
[Site "Online"]
[Date "2024.01.01"]
[Round "1"]
[White "Player1"]
[Black "Player2"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 *
"""
    game_dict = {
        "White": "Player1",
        "Black": "Player2",
        "match_count": 2,
        "matching_plies": [5, 8]
    }
    
    widget.load_game(game_dict, pgn_text)

    # Verify initial position jumped to target_ply 5
    assert widget.move_manager.get_current_ply() == 5
    assert not widget.lbl_match_badge.isHidden()
    assert widget.lbl_match_badge.text() == "Match 1/2 (p5)"

    # Step to next match (ply 8 -> 4... Nf6)
    widget.go_next_match()
    assert widget.current_match_idx == 1
    assert widget.move_manager.get_current_ply() == 8
    assert widget.lbl_match_badge.text() == "Match 2/2 (p8)"

    # Step prev match back to ply 5
    widget.go_prev_match()
    assert widget.current_match_idx == 0
    assert widget.move_manager.get_current_ply() == 5
