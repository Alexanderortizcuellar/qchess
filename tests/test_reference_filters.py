import pytest
from PyQt5 import QtCore, QtWidgets
from core.reference_filters import get_reference_filter_manager, ReferenceFilterManager
from gui.dialogs.reference_filters_dialog import ReferenceFiltersDialog
from core.scid_client import ScidClient


@pytest.fixture(autouse=True)
def clean_filter_settings():
    mgr = get_reference_filter_manager()
    mgr.clear_filters()
    yield
    mgr.clear_filters()


def test_reference_filter_manager_defaults():
    mgr = get_reference_filter_manager()
    mgr.clear_filters()
    assert mgr.has_active_filter() is False
    assert mgr.get_filter_dict() == {}
    assert "No reference filters active" in mgr.get_summary_text()


def test_reference_filter_manager_set_filters(qtbot):
    mgr = get_reference_filter_manager()
    
    with qtbot.waitSignal(mgr.filtersChanged, timeout=1000) as blocker:
        mgr.set_filters(
            player="Carlsen",
            color="As White",
            min_rating=2700,
            max_rating=2900,
            eco="B01",
            result="1-0",
            event="WCh",
            min_year=2015,
            max_year=2023,
        )

    filt = mgr.get_filter_dict()
    assert filt.get("white") == "Carlsen"
    assert "player" not in filt
    assert filt.get("min_rating") == 2700
    assert filt.get("max_rating") == 2900
    assert filt.get("eco") == "B01"
    assert filt.get("result") == "1-0"
    assert filt.get("event") == "WCh"
    assert filt.get("date_from") == "2015.01.01"
    assert filt.get("date_to") == "2023.12.31"
    assert mgr.has_active_filter() is True
    assert "White: Carlsen" in mgr.get_summary_text()


def test_reference_filters_dialog_ui(qtbot):
    mgr = get_reference_filter_manager()
    mgr.clear_filters()

    dlg = ReferenceFiltersDialog(is_dark=True)
    qtbot.addWidget(dlg)

    dlg.player_edit.setText("Kasparov")
    dlg.color_combo.setCurrentIndex(2)  # As Black
    dlg.min_rating_spin.setValue(2600)
    dlg.eco_edit.setText("E90")
    dlg.result_combo.setCurrentIndex(1)  # 1-0

    dlg._on_apply_clicked()

    filt = mgr.get_filter_dict()
    assert filt.get("black") == "Kasparov"
    assert filt.get("min_rating") == 2600
    assert filt.get("eco") == "E90"
    assert filt.get("result") == "1-0"


def test_reference_filters_dialog_theme_matching(qtbot):
    # Test Dark theme
    dlg_dark = ReferenceFiltersDialog(is_dark=True)
    qtbot.addWidget(dlg_dark)
    assert dlg_dark.is_dark is True
    assert "#201e1b" in dlg_dark.styleSheet()

    # Test Light theme
    dlg_light = ReferenceFiltersDialog(is_dark=False)
    qtbot.addWidget(dlg_light)
    assert dlg_light.is_dark is False
    assert "#f8fafc" in dlg_light.styleSheet()


def test_scid_client_filter_params_passed():
    client = ScidClient()
    
    recorded_requests = []
    def mock_send(method, params=None, callback=None):
        recorded_requests.append((method, params))
        return 1
        
    client.send_request = mock_send

    sample_filter = {"white": "Carlsen", "min_rating": 2700}

    # 1. Opening Tree
    client.opening_tree(fen="test_fen", filters=sample_filter)
    assert recorded_requests[-1][0] == "opening_tree"
    assert recorded_requests[-1][1]["filter"] == sample_filter

    # 2. Continuations
    client.continuations(fen="test_fen", filters=sample_filter)
    assert recorded_requests[-1][0] == "continuations"
    assert recorded_requests[-1][1]["filter"] == sample_filter

    # 3. Endgames
    client.endgames(fen="test_fen", filters=sample_filter)
    assert recorded_requests[-1][0] == "endgames"
    assert recorded_requests[-1][1]["filter"] == sample_filter
