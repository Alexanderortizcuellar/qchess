import pytest
from PyQt5 import QtCore, QtWidgets, QtNetwork
from core.lichess_client import LichessClient, load_lichess_token, save_lichess_token
from gui.widgets.lichess_explorer_widget import (
    LichessTreeTable,
    LichessGamesTable,
    LichessExplorerWidget,
    LichessTokenDialog,
)
from core.opening_explorer import TwoBarWidget


def test_lichess_token_loading(monkeypatch):
    # Test loading token
    token = load_lichess_token()
    assert isinstance(token, str)
    assert len(token) > 0  # Should find token from .env

    # Test QSettings override
    settings = QtCore.QSettings("QChessApp", "Lichess")
    orig = settings.value("api_token", "")
    try:
        settings.setValue("api_token", "lip_test123456789")
        assert load_lichess_token() == "lip_test123456789"
    finally:
        if orig:
            settings.setValue("api_token", orig)
        else:
            settings.remove("api_token")


def test_lichess_client_request_construction(qtbot):
    client = LichessClient()
    client.set_token("lip_custom_token_xyz", persist=False)
    assert client.get_token() == "lip_custom_token_xyz"
    assert client.has_token() is True

    req = client._create_request(QtCore.QUrl("https://explorer.lichess.ovh/masters"))
    assert req.rawHeader(b"Authorization") == b"Bearer lip_custom_token_xyz"
    assert b"QChess" in req.rawHeader(b"User-Agent")


def test_lichess_tree_table(qtbot):
    table = LichessTreeTable()
    qtbot.addWidget(table)

    sample_moves = [
        {
            "uci": "e2e4",
            "san": "e4",
            "averageRating": 2450,
            "white": 1000,
            "draws": 1500,
            "black": 800,
        },
        {
            "uci": "d2d4",
            "san": "d4",
            "averageRating": 2465,
            "white": 900,
            "draws": 1600,
            "black": 700,
        },
    ]

    table.update_moves(sample_moves)
    assert table.rowCount() == 2
    assert table.columnCount() == 5

    # Check Move column
    assert table.item(0, 0).text() == "e4"
    assert table.item(0, 0).data(QtCore.Qt.UserRole) == "e2e4"
    assert table.item(1, 0).text() == "d4"

    # Check Games column
    total_e4 = 1000 + 1500 + 800
    assert table.item(0, 1).text() == f"{total_e4:,}"

    # Check Score column has TwoBarWidget
    bar = table.cellWidget(0, 2)
    assert isinstance(bar, TwoBarWidget)
    assert bar.white_wins == 1000
    assert bar.black_wins == 800

    # Check Draw % and Rating
    assert "%" in table.item(0, 3).text()
    assert table.item(0, 4).text() == "2450"

    # Check moveSelected signal on click
    with qtbot.waitSignal(table.moveSelected, timeout=1000) as blocker:
        table.cellClicked.emit(0, 0)
    assert blocker.args[0] == "e2e4"


def test_lichess_games_table(qtbot):
    table = LichessGamesTable()
    qtbot.addWidget(table)

    sample_games = [
        {
            "id": "game123",
            "uci": "e2e4",
            "winner": "white",
            "white": {"name": "Carlsen, M.", "rating": 2882},
            "black": {"name": "Caruana, F.", "rating": 2818},
            "year": 2021,
        },
        {
            "id": "game456",
            "uci": "d2d4",
            "winner": None,
            "white": {"name": "Ding, L.", "rating": 2800},
            "black": {"name": "Nepomniachtchi, I.", "rating": 2795},
            "year": 2023,
        },
    ]

    table.update_games(sample_games)
    assert table.rowCount() == 2

    assert table.item(0, 0).text() == "Carlsen, M."
    assert table.item(0, 1).text() == "2882"
    assert table.item(0, 2).text() == "Caruana, F."
    assert table.item(0, 3).text() == "2818"
    assert table.item(0, 4).text() == "1-0"
    assert table.item(0, 5).text() == "2021"

    assert table.item(1, 4).text() == "½-½"

    # Test double click emits gameSelected
    with qtbot.waitSignal(table.gameSelected, timeout=1000) as blocker:
        table.cellDoubleClicked.emit(0, 0)
    assert blocker.args[0] == "game123"
    assert blocker.args[1]["white"]["name"] == "Carlsen, M."


def test_lichess_explorer_widget(qtbot):
    widget = LichessExplorerWidget()
    qtbot.addWidget(widget)

    assert widget.combo_source.count() >= 2
    assert widget.chk_auto.isChecked() is True
    assert widget.client.has_token() is True

    widget.show()

    # Test switching source
    widget.combo_source.setCurrentIndex(1)  # Lichess DB
    assert not widget.combo_speed.isHidden()
    assert not widget.combo_rating.isHidden()

    widget.combo_source.setCurrentIndex(0)  # Masters
    assert widget.combo_speed.isHidden()
    assert widget.combo_rating.isHidden()

    # Test theme switching
    widget.set_theme(False)
    assert widget.is_dark is False
    widget.set_theme(True)
    assert widget.is_dark is True


def test_lichess_token_dialog(qtbot):
    dlg = LichessTokenDialog("lip_initial_token", is_dark=True)
    qtbot.addWidget(dlg)

    assert dlg.txt_token.text() == "lip_initial_token"
    dlg.txt_token.setText("lip_new_token")
    assert dlg.get_token() == "lip_new_token"
