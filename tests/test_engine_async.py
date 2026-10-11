import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QProcess
from core.engine import ChessEngine


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_chess_engine_initial_state(qapp):
    """Verify ChessEngine initializes with clean async state."""
    engine = ChessEngine(engine_path="stockfish")
    assert not engine.is_uci_ready
    assert not engine.is_starting
    assert engine.pending_search is None
    assert not engine.searching


def test_chess_engine_send_position_queues_search_when_not_started(qapp, monkeypatch):
    """Verify send_position queues pending search and initiates non-blocking startup."""
    engine = ChessEngine(engine_path="stockfish")
    
    # Mock engine.start to avoid launching a real external binary during this unit test
    start_called = []
    monkeypatch.setattr(engine, "start", lambda: start_called.append(True))
    
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    engine.send_position(fen, mode="depth", options={"depth": 15})

    assert len(start_called) == 1
    assert engine.is_starting is True
    assert engine.pending_search == (fen, "depth", {"depth": 15})


def test_chess_engine_uci_handshake_triggers_queued_search(qapp, monkeypatch):
    """Verify that when readyok is received, the queued pending search executes immediately."""
    engine = ChessEngine(engine_path="stockfish")
    
    commands_sent = []
    monkeypatch.setattr(engine, "send_command", lambda cmd: commands_sent.append(cmd))

    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    engine.pending_search = (fen, "depth", {"depth": 20})
    engine.is_starting = True

    # Simulate receiving "uciok"
    engine.readAllStandardOutput = lambda: type("DummyQByteArray", (), {"data": lambda self: b"uciok\n"})()
    engine.read_data()
    assert "isready" in commands_sent

    # Simulate receiving "readyok"
    commands_sent.clear()
    engine.readAllStandardOutput = lambda: type("DummyQByteArray", (), {"data": lambda self: b"readyok\n"})()
    engine.read_data()

    assert engine.is_uci_ready is True
    assert engine.is_starting is False
    assert engine.pending_search is None
    assert engine.searching is True
    assert f"position fen {fen}" in commands_sent
    assert "go depth 20" in commands_sent
