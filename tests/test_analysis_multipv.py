import pytest
from PyQt5.QtWidgets import QApplication
from gui.widgets.analysis_widget import AnalysisWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_analysis_widget_clears_stale_multipv_on_fen_change(qapp):
    """Verify AnalysisWidget isolates MultiPV lines per FEN and drops stale lines from prior positions."""
    w = AnalysisWidget()
    w.set_multipv(3)
    w.check_analysis.setChecked(True)

    fen_pos_1 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    fen_pos_2 = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"

    # 1. Update Position 1 with 3 MultiPV lines
    info_p1_line1 = {
        "fen": fen_pos_1,
        "multipv": 1,
        "score_type": "cp",
        "score_value": 35,
        "pv": ["e7e5", "g1f3"],
        "depth": 15,
    }
    info_p1_line2 = {
        "fen": fen_pos_1,
        "multipv": 2,
        "score_type": "cp",
        "score_value": 20,
        "pv": ["c7c5", "g1f3"],
        "depth": 15,
    }
    info_p1_line3 = {
        "fen": fen_pos_1,
        "multipv": 3,
        "score_type": "cp",
        "score_value": 10,
        "pv": ["e7e6", "d2d4"],
        "depth": 15,
    }

    w.update_analysis_batch([info_p1_line1, info_p1_line2, info_p1_line3], board_fen=fen_pos_1)
    assert len(w.lines_view.lines) == 3
    assert w.lines_view.lines[0].tokens[0].san == "1... e5"
    assert w.lines_view.lines[1].tokens[0].san == "1... c5"

    # 2. Position changes to Position 2 (White moves), but initially only PV 1 arrives (e.g. mate found)
    info_p2_line1 = {
        "fen": fen_pos_2,
        "multipv": 1,
        "score_type": "mate",
        "score_value": 4,
        "pv": ["g1f3", "b8c6", "f1b5"],
        "depth": 12,
    }

    w.update_analysis(info_p2_line1, board_fen=fen_pos_2)

    # PV 2 & PV 3 from Position 1 MUST be discarded, not displayed as invalid UCI moves on Position 2
    assert len(w.lines_view.lines) == 1
    assert w.lines_view.lines[0].multipv == 1
    assert w.lines_view.lines[0].score_str == "M4"
    assert w.lines_view.lines[0].tokens[0].san == "2. Nf3"

    # 3. When Position 2 PV 2 arrives, it renders cleanly
    info_p2_line2 = {
        "fen": fen_pos_2,
        "multipv": 2,
        "score_type": "cp",
        "score_value": 40,
        "pv": ["d2d4", "e5d4"],
        "depth": 14,
    }
    w.update_analysis(info_p2_line2, board_fen=fen_pos_2)
    assert len(w.lines_view.lines) == 2
    assert w.lines_view.lines[1].tokens[0].san == "2. d4"
