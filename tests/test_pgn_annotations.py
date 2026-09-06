import io
import chess
import chess.pgn
import pytest
from core.pgn_annotations import (
    parse_pgn_shapes,
    extract_node_shapes,
    export_pgn_shapes,
    COLOR_MAP,
)
from core.move_manager import MoveManager
from gui.widgets.chessboard import ChessBoard


def test_parse_cal_arrows():
    comment = "[%cal Ge2e4,Rg1f3,Ye7e5,Bc1f4]"
    shapes, highlights = parse_pgn_shapes(comment)

    assert len(shapes) == 4
    assert shapes[0] == {
        "type": "arrow",
        "orig": chess.E2,
        "dest": chess.E4,
        "color": COLOR_MAP["G"],
        "width": 4.0,
    }
    assert shapes[1] == {
        "type": "arrow",
        "orig": chess.G1,
        "dest": chess.F3,
        "color": COLOR_MAP["R"],
        "width": 4.0,
    }
    assert shapes[2] == {
        "type": "arrow",
        "orig": chess.E7,
        "dest": chess.E5,
        "color": COLOR_MAP["Y"],
        "width": 4.0,
    }
    assert shapes[3] == {
        "type": "arrow",
        "orig": chess.C1,
        "dest": chess.F4,
        "color": COLOR_MAP["B"],
        "width": 4.0,
    }
    assert len(highlights) == 0


def test_parse_csl_squares():
    comment = "[%csl Ge4,Rd4,Yc3,Bb2]"
    shapes, highlights = parse_pgn_shapes(comment)

    assert len(shapes) == 4
    assert shapes[0] == {
        "type": "circle",
        "orig": chess.E4,
        "color": COLOR_MAP["G"],
        "width": 4.0,
    }
    assert highlights[chess.E4] == COLOR_MAP["G"]
    assert highlights[chess.D4] == COLOR_MAP["R"]
    assert highlights[chess.C3] == COLOR_MAP["Y"]
    assert highlights[chess.B2] == COLOR_MAP["B"]


def test_parse_case_insensitive_and_extended_colors():
    comment = "[%cal ge2e4,oe7e5,cd2d4,mf8c5] [%csl re4,yc3,kb1,wa1]"
    shapes, highlights = parse_pgn_shapes(comment)

    assert len(shapes) == 8
    # Lowercase green arrow
    assert shapes[0]["orig"] == chess.E2
    assert shapes[0]["dest"] == chess.E4
    assert shapes[0]["color"] == COLOR_MAP["G"]
    # Orange arrow
    assert shapes[1]["orig"] == chess.E7
    assert shapes[1]["dest"] == chess.E5
    assert shapes[1]["color"] == COLOR_MAP["O"]
    # Cyan arrow
    assert shapes[2]["orig"] == chess.D2
    assert shapes[2]["dest"] == chess.D4
    assert shapes[2]["color"] == COLOR_MAP["C"]
    # Magenta arrow
    assert shapes[3]["orig"] == chess.F8
    assert shapes[3]["dest"] == chess.C5
    assert shapes[3]["color"] == COLOR_MAP["M"]

    # Lowercase red square
    assert highlights[chess.E4] == COLOR_MAP["R"]
    assert highlights[chess.C3] == COLOR_MAP["Y"]
    assert highlights[chess.B1] == COLOR_MAP["K"]
    assert highlights[chess.A1] == COLOR_MAP["W"]


def test_mixed_comment_with_eval_and_text():
    comment = "[%eval +0.45] [%cal Ge2e4,Rg1f3] [%csl Ge4] Excellent opening move"
    shapes, highlights = parse_pgn_shapes(comment)

    assert len(shapes) == 3
    assert shapes[0]["type"] == "arrow"
    assert shapes[0]["orig"] == chess.E2
    assert shapes[0]["dest"] == chess.E4
    assert shapes[1]["type"] == "arrow"
    assert shapes[1]["orig"] == chess.G1
    assert shapes[1]["dest"] == chess.F3
    assert shapes[2]["type"] == "circle"
    assert shapes[2]["orig"] == chess.E4
    assert highlights[chess.E4] == COLOR_MAP["G"]


def test_export_pgn_shapes():
    shapes = [
        {"type": "arrow", "orig": chess.E2, "dest": chess.E4, "color": COLOR_MAP["G"]},
        {"type": "circle", "orig": chess.D4, "color": COLOR_MAP["R"]},
    ]
    exported = export_pgn_shapes(shapes)
    assert "[%cal Ge2e4]" in exported
    assert "[%csl Rd4]" in exported


def test_move_manager_extracts_shapes_per_node():
    pgn = """[Event "Test PGN with Arrows"]
[Site "Everywhere"]
[Date "2026.09.06"]
[Round "1"]
[White "Player1"]
[Black "Player2"]
[Result "*"]

1. e4 { [%cal Ge2e4] [%csl Ge4] } 1... c5 { [%cal c7c5,Rd8a5] } 2. Nf3 { [%cal Gf1c4] } *
"""
    mm = MoveManager(pgn)

    # Initial position (root game node)
    shapes0, hl0 = mm.get_current_shapes_and_highlights()
    assert len(shapes0) == 0

    # Move 1: 1. e4
    mm.redo(0)
    shapes1, hl1 = mm.get_current_shapes_and_highlights()
    assert len(shapes1) == 2
    assert shapes1[0]["type"] == "arrow"
    assert shapes1[0]["orig"] == chess.E2
    assert shapes1[0]["dest"] == chess.E4
    assert shapes1[1]["type"] == "circle"
    assert shapes1[1]["orig"] == chess.E4
    assert hl1[chess.E4] == COLOR_MAP["G"]

    # Move 2: 1... c5
    mm.redo(0)
    shapes2, hl2 = mm.get_current_shapes_and_highlights()
    assert len(shapes2) == 2
    assert shapes2[0]["type"] == "arrow"
    assert shapes2[0]["orig"] == chess.C7
    assert shapes2[0]["dest"] == chess.C5
    assert shapes2[1]["type"] == "arrow"
    assert shapes2[1]["orig"] == chess.D8
    assert shapes2[1]["dest"] == chess.A5
    assert shapes2[1]["color"] == COLOR_MAP["R"]

    # Move 3: 2. Nf3
    mm.redo(0)
    shapes3, hl3 = mm.get_current_shapes_and_highlights()
    assert len(shapes3) == 1
    assert shapes3[0]["orig"] == chess.F1
    assert shapes3[0]["dest"] == chess.C4

    # Undo back to 1... c5
    mm.undo()
    shapes_back, hl_back = mm.get_current_shapes_and_highlights()
    assert len(shapes_back) == 2
    assert shapes_back[0]["orig"] == chess.C7
    assert shapes_back[0]["dest"] == chess.C5


def test_chessboard_update_with_shapes(qapp):
    cb = ChessBoard(fen=chess.STARTING_FEN, size=400)
    shapes = [
        {"type": "arrow", "orig": chess.E2, "dest": chess.E4, "color": "rgba(21, 128, 61, 0.7)"}
    ]
    highlights = {chess.E4: "rgba(21, 128, 61, 0.7)"}

    cb.update_board(
        fen=chess.STARTING_FEN,
        shapes=shapes,
        custom_highlights=highlights,
    )

    # Verify shapes and highlights reached the board view
    assert len(cb.board_view._state.shapes) == 1
    assert cb.board_view._state.shapes[0].type == "arrow"
    assert cb.board_view._state.shapes[0].orig == chess.E2
    assert cb.board_view._state.shapes[0].dest == chess.E4
    assert chess.E4 in cb.board_view._state.custom_highlights
