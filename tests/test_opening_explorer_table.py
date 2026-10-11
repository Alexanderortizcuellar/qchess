import pytest
from PyQt5 import QtCore, QtWidgets
from core.opening_explorer import OpeningExplorer, OpeningTreeTable, TwoBarWidget, OpeningExplorerHeader, OpeningExplorerLogic


def test_two_bar_widget(qtbot):
    w = TwoBarWidget(white_wins=50, black_wins=30, total_games=100)
    qtbot.addWidget(w)
    assert w.white_wins == 50
    assert w.black_wins == 30
    assert w.total_games == 100
    assert "White wins: 50" in w.toolTip()
    assert "Black wins: 30" in w.toolTip()


def test_opening_tree_table(qtbot):
    table = OpeningTreeTable()
    qtbot.addWidget(table)

    positions = [
        {"san": "e4", "uci": "e2e4", "white_wins": 50, "draws": 25, "black_wins": 25, "total_games": 100, "first_year": 1851, "last_year": 2024},
        {"san": "d4", "uci": "d2d4", "white_wins": 40, "draws": 35, "black_wins": 25, "total_games": 100, "first_year": 1900, "last_year": 1900},
    ]
    table.update_positions(positions)

    assert table.rowCount() == 2
    assert table.columnCount() == 5
    assert table.horizontalHeader().sectionResizeMode(0) == QtWidgets.QHeaderView.Interactive
    assert table.horizontalHeader().sectionResizeMode(2) == QtWidgets.QHeaderView.Stretch

    # Move column
    assert table.item(0, 0).text() == "e4"
    assert table.item(1, 0).text() == "d4"

    # Games column
    assert table.item(0, 1).text() == "100"

    # Score column has TwoBarWidget
    score_widget = table.cellWidget(0, 2)
    assert isinstance(score_widget, TwoBarWidget)
    assert score_widget.white_wins == 50
    assert score_widget.black_wins == 25

    # Draw % column
    assert table.item(0, 3).text() == "25.0%"
    assert table.item(1, 3).text() == "35.0%"

    # Years column
    assert table.item(0, 4).text() == "1851-2024"
    assert table.item(1, 4).text() == "1900"

    # Click emits moveSelected
    with qtbot.waitSignal(table.moveSelected, timeout=1000) as blocker:
        table.cellClicked.emit(0, 0)
    assert blocker.args[0] == "e2e4"


def test_opening_explorer_dual_mode(qtbot):
    explorer = OpeningExplorer()
    qtbot.addWidget(explorer)

    # Initial mode toggling
    explorer.set_mode("table")
    assert explorer.mode == "table"
    assert explorer.stack.currentWidget() == explorer.table_view

    explorer.set_mode("bars")
    assert explorer.mode == "bars"
    assert explorer.stack.currentWidget() == explorer.scroll

    # Toggle mode button
    explorer.toggle_view_mode()
    assert explorer.mode == "table"

    # Positions update
    positions = [
        {"san": "Nf3", "uci": "g1f3", "white_wins": 10, "draws": 5, "black_wins": 5, "total_games": 20},
    ]
    explorer.update_positions(positions)
    assert explorer.table_view.rowCount() == 1
    assert explorer.table_view.item(0, 0).text() == "Nf3"
