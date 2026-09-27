import pytest
from PyQt5.QtWidgets import QApplication
from unittest.mock import MagicMock

from gui.widgets.endgames_widget import EndgamesWidget, EndgameOutcomeBar
from core.scid_client import ScidClient


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_endgame_outcome_bar(qapp):
    bar = EndgameOutcomeBar(50, 30, 20)
    assert bar.white_win == 50
    assert bar.draw == 30
    assert bar.black_win == 20
    assert "White wins: 50" in bar.toolTip()
    assert "Draws: 30" in bar.toolTip()
    assert "Black wins: 20" in bar.toolTip()


def test_endgames_widget_populate_and_filter(qapp):
    widget = EndgamesWidget()
    sample_report = {
        "db_path": "test.si5",
        "total_db_games": 1000,
        "games_reaching_position": 500,
        "position_filtered": True,
        "categories": [
            {
                "category_id": "ROOK",
                "name": "Rook Endgames",
                "total_games": 200,
                "percentage": 40.0,
                "features": [
                    {
                        "id": "END_ROOK_RP_R",
                        "bit": 6,
                        "name": "Rook and Pawn vs Rook",
                        "short_name": "R+P vs R",
                        "gbr_code": "0400.10",
                        "category_id": "ROOK",
                        "game_count": 80,
                        "percentage": 16.0,
                        "white_wins": 40,
                        "draws": 30,
                        "black_wins": 10,
                    }
                ],
            },
            {
                "category_id": "PAWN",
                "name": "Pawn Endgames",
                "total_games": 100,
                "percentage": 20.0,
                "features": [
                    {
                        "id": "END_PAWN_KP_K",
                        "bit": 0,
                        "name": "King and Pawn vs King",
                        "short_name": "K+P vs K",
                        "gbr_code": "0000.10",
                        "category_id": "PAWN",
                        "game_count": 50,
                        "percentage": 10.0,
                        "white_wins": 35,
                        "draws": 5,
                        "black_wins": 10,
                    }
                ],
            },
        ],
        "features": [],
    }

    widget.set_report(sample_report)
    assert "500" in widget.lbl_pos_games.text()
    assert widget.table.topLevelItemCount() == 2

    # Filter to ROOK only
    idx = widget.combo_category.findData("ROOK")
    assert idx >= 0
    widget.combo_category.setCurrentIndex(idx)
    # Check item visibility
    root = widget.table.invisibleRootItem()
    rook_item = root.child(0)
    pawn_item = root.child(1)
    assert not rook_item.isHidden()
    assert pawn_item.isHidden()

    # Search filter
    widget.combo_category.setCurrentIndex(0)  # ALL
    widget.txt_filter.setText("Nonexistent")  # doesn't match
    assert rook_item.isHidden()
    assert pawn_item.isHidden()

    widget.txt_filter.setText("Rook")  # matches ROOK
    assert not rook_item.isHidden()
    assert pawn_item.isHidden()


def test_endgames_widget_zero_count_filtering(qapp):
    widget = EndgamesWidget()
    report_with_zeros = {
        "db_path": "test.si5",
        "total_db_games": 1000,
        "games_reaching_position": 100,
        "position_filtered": True,
        "categories": [
            {
                "category_id": "ROOK",
                "name": "Rook Endgames",
                "total_games": 10,
                "percentage": 10.0,
                "features": [
                    {
                        "id": "END_ROOK_RP_R",
                        "name": "Rook and Pawn vs Rook",
                        "game_count": 10,
                        "percentage": 10.0,
                        "white_wins": 5,
                        "draws": 3,
                        "black_wins": 2,
                    },
                    {
                        "id": "END_ROOK_2R_2R",
                        "name": "Double Rook Endgame",
                        "game_count": 0,
                        "percentage": 0.0,
                        "white_wins": 0,
                        "draws": 0,
                        "black_wins": 0,
                    },
                ],
            },
            {
                "category_id": "QUEEN",
                "name": "Queen Endgames",
                "total_games": 0,
                "percentage": 0.0,
                "features": [
                    {
                        "id": "END_QUEEN_Q_Q",
                        "name": "Bare Queens",
                        "game_count": 0,
                        "percentage": 0.0,
                        "white_wins": 0,
                        "draws": 0,
                        "black_wins": 0,
                    }
                ],
            },
        ],
    }

    widget.set_report(report_with_zeros)
    # Only ROOK category should be in table (QUEEN has 0 games)
    assert widget.table.topLevelItemCount() == 1
    root = widget.table.invisibleRootItem()
    rook_cat = root.child(0)
    # Only END_ROOK_RP_R feature should be in ROOK category (END_ROOK_2R_2R has 0 games)
    assert rook_cat.childCount() == 1
    assert "Rook and Pawn vs Rook" in rook_cat.child(0).text(0)


def test_scid_client_endgame_methods(qapp):
    client = ScidClient()
    client.send_request = MagicMock(return_value=123)

    req_id = client.endgames(fen="8/8/8/8/8/8/8/8 w - - 0 1", category="ROOK")
    assert req_id == 123
    client.send_request.assert_called_with(
        "endgames",
        {"max_samples": 20, "fen": "8/8/8/8/8/8/8/8 w - - 0 1", "category": "ROOK"},
        None,
    )

    build_id = client.build_endgames()
    assert build_id == 123
    client.send_request.assert_called_with("build_endgames", {}, None)
