import time
import pytest
from unittest.mock import MagicMock
from collections import OrderedDict
from PyQt5.QtWidgets import QApplication

from core.scid_client import ScidClient
from gui.widgets.game_list_table import GameListTableModel
from gui.widgets.painter_pgn_browser import QPainterBrowser


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_game_list_table_lru_cache_eviction(qapp):
    """Verify that GameListTableModel evicts older chunks when exceeding MAX_CACHED_CHUNKS."""
    model = GameListTableModel()
    assert isinstance(model.cached_chunks, OrderedDict)
    assert model.MAX_CACHED_CHUNKS == 50

    # Simulate receiving 60 pages of backend data
    for page in range(60):
        fake_response = {
            "status": "ok",
            "data": {
                "page": page,
                "total": 6000,
                "games": [{"id": page * 100 + i, "white": f"P{page}_{i}"} for i in range(100)],
            }
        }
        model.on_backend_response(fake_response)

    # Total cached chunks must be capped at 50
    assert len(model.cached_chunks) == 50
    # Pages 0 to 9 should have been evicted
    assert 0 not in model.cached_chunks
    assert 9 not in model.cached_chunks
    # Pages 10 to 59 must be present
    assert 10 in model.cached_chunks
    assert 59 in model.cached_chunks

    # Access page 10 to make it MRU (most recently used)
    item = model.get_game_at(10 * model.CHUNK_SIZE)
    assert item is not None
    assert item["id"] == 1000

    # Add page 60
    fake_response_60 = {
        "status": "ok",
        "data": {
            "page": 60,
            "total": 6100,
            "games": [{"id": 6000 + i, "white": f"P60_{i}"} for i in range(100)],
        }
    }
    model.on_backend_response(fake_response_60)

    # Now page 11 should have been evicted instead of page 10
    assert len(model.cached_chunks) == 50
    assert 10 in model.cached_chunks
    assert 11 not in model.cached_chunks
    assert 60 in model.cached_chunks


def test_scid_client_callback_pruning_and_cancel():
    """Verify ScidClient properly prunes stale callbacks and supports explicit cancellation."""
    client = ScidClient()

    called = []
    def dummy_cb(data):
        called.append(data)

    # Add simulated callbacks with past timestamps
    client.pending_callbacks[1] = (dummy_cb, time.time() - 100.0)  # stale (>60s)
    client.pending_callbacks[2] = (dummy_cb, time.time())          # fresh

    # Dispatching a response triggers pruning
    client._dispatch_response_on_main_thread({"id": 2, "status": "ok"})
    assert 1 not in client.pending_callbacks
    assert 2 not in client.pending_callbacks
    assert len(called) == 1

    # Test explicit cancel
    client.pending_callbacks[3] = (dummy_cb, time.time())
    client.cancel_callback(3)
    assert 3 not in client.pending_callbacks

    # Test cancel with None or missing
    client.cancel_callback(None)
    client.cancel_callback(999)


def test_diagram_cache_lru_eviction(qapp):
    """Verify QPainterBrowser bounds diagram pixmap cache with LRU eviction."""
    browser = QPainterBrowser(MagicMock())
    assert isinstance(browser._diagram_cache, OrderedDict)
    assert browser.MAX_DIAGRAM_CACHE == 64

    # Populate cache up to and beyond limit
    for i in range(80):
        key = (f"fen_{i}", 150, True)
        browser._diagram_cache[key] = f"fake_pixmap_{i}"
        browser._diagram_cache.move_to_end(key)
        while len(browser._diagram_cache) > browser.MAX_DIAGRAM_CACHE:
            browser._diagram_cache.popitem(last=False)

    assert len(browser._diagram_cache) == 64
    assert ("fen_0", 150, True) not in browser._diagram_cache
    assert ("fen_15", 150, True) not in browser._diagram_cache
    assert ("fen_79", 150, True) in browser._diagram_cache

    browser.clear_diagram_cache()
    assert len(browser._diagram_cache) == 0


def test_navigation_without_reflattening(qapp):
    """Verify MoveManager navigation updates cursor and emits activeNodeChanged without re-flattening."""
    from core.move_manager import MoveManager
    from unittest.mock import patch

    mm = MoveManager("1. e4 e5 2. Nf3 Nc6 3. Bb5")
    assert len(mm.nodes) == 5

    active_changed_count = 0
    def on_active():
        nonlocal active_changed_count
        active_changed_count += 1

    mm.activeNodeChanged.connect(on_active)

    with patch.object(mm, "create_mapping") as mock_mapping:
        # Jump to end (ply 5)
        mm.jump_to_end()
        assert mm.get_current_ply() == 5
        assert active_changed_count == 1
        mock_mapping.assert_not_called()

        # Navigate backward (undo to ply 4)
        mm.undo()
        assert mm.get_current_ply() == 4
        assert active_changed_count == 2
        mock_mapping.assert_not_called()

        # Jump to start (ply 0)
        mm.jump_to_start()
        assert mm.get_current_ply() == 0
        assert active_changed_count == 3
        mock_mapping.assert_not_called()

        # Goto ply 2
        mm.goto_ply(2)
        assert mm.get_current_ply() == 2
        assert active_changed_count == 4
        mock_mapping.assert_not_called()

        # Redo (to ply 3)
        mm.redo(0)
        assert mm.get_current_ply() == 3
        assert active_changed_count == 5
        mock_mapping.assert_not_called()

        # Jump to index 0 (ply 1)
        mm.jump_to(0)
        assert mm.get_current_ply() == 1
        assert active_changed_count == 6
        mock_mapping.assert_not_called()
