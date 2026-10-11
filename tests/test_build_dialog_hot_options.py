import pytest
from unittest.mock import MagicMock
from PyQt5.QtWidgets import QApplication
from gui.dialogs.build_pos_index_dialog import BuildPosIndexDialog
from core.scid_client import ScidClient


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_build_dialog_hot_options_toggling(qapp):
    client = MagicMock(spec=ScidClient)
    client.is_running.return_value = True

    dlg = BuildPosIndexDialog(scid_client=client, default_ply=24)
    dlg.show()

    # Initial state: chk_hot is checked, hot_options_frame is visible and enabled
    assert dlg.chk_hot.isChecked()
    assert not dlg.hot_options_frame.isHidden()
    assert dlg.hot_options_frame.isEnabled()
    assert dlg.spin_depth.value() == 24
    assert dlg.spin_min_games.value() == 1

    # Unchecking chk_hot disables and hides options frame
    dlg.chk_hot.setChecked(False)
    assert dlg.hot_options_frame.isHidden()
    assert not dlg.hot_options_frame.isEnabled()

    # Checking chk_hot restores options frame
    dlg.chk_hot.setChecked(True)
    assert not dlg.hot_options_frame.isHidden()
    assert dlg.hot_options_frame.isEnabled()
    dlg.close()


def test_build_dialog_passes_hot_options_to_client(qapp):
    client = MagicMock(spec=ScidClient)
    client.is_running.return_value = True

    dlg = BuildPosIndexDialog(scid_client=client, default_ply=20)
    dlg.chk_booster.setChecked(False)
    dlg.chk_feat.setChecked(False)
    dlg.chk_hot.setChecked(True)

    dlg.spin_depth.setValue(32)
    dlg.spin_min_games.setValue(5)
    dlg.spin_threads.setValue(8)

    # Trigger build
    dlg.start_build()

    # Verify build_continuations was called with the configured options
    client.build_continuations.assert_called_once()
    kwargs = client.build_continuations.call_args.kwargs
    assert kwargs.get("max_ply") == 32
    assert kwargs.get("min_games") == 5
    assert kwargs.get("threads") == 8
    dlg.close()


def test_build_dialog_progress_bar_reset_and_update(qapp):
    client = MagicMock(spec=ScidClient)
    client.is_running.return_value = True

    dlg = BuildPosIndexDialog(scid_client=client, default_ply=24)
    dlg.show()

    # Simulate running task 1 (build_booster)
    dlg.current_task = "build_booster"
    dlg._on_booster_progress({"scanned": 5000, "total": 10000, "plies": 100000, "percent": 50.0})
    assert dlg.progress_bar.value() == 50

    dlg._on_booster_progress({"scanned": 10000, "total": 10000, "plies": 200000, "percent": 100.0})
    assert dlg.progress_bar.value() == 100

    # Start next task: build_continuations
    dlg.current_task = "build_continuations"
    dlg.progress_bar.setValue(0)
    assert dlg.progress_bar.value() == 0

    # Simulate hot progress with partial scan
    dlg._on_hot_progress({"scanned": 2500, "total": 10000, "nodes": 12000, "percent": 25.0})
    assert dlg.progress_bar.value() == 25
    assert "2,500" in dlg.lbl_progress.text()
    assert "10,000" in dlg.lbl_progress.text()

    dlg.close()
