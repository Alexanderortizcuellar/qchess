import re
from typing import Literal, Any

from PyQt5 import QtCore


class ChessEngine(QtCore.QProcess):
    moveFound = QtCore.pyqtSignal(str)
    depthChanged = QtCore.pyqtSignal(int)
    analysisUpdated = QtCore.pyqtSignal(dict)  # Emits dict with MultiPV info
    engineNameChanged = QtCore.pyqtSignal(str)
    engineStarting = QtCore.pyqtSignal()
    engineReady = QtCore.pyqtSignal()
    engineError = QtCore.pyqtSignal(str)

    def __init__(self, engine_path="stockfish", parent=None):
        super().__init__(parent)
        self.engine_path = engine_path
        self.engine_name = self._infer_name_from_path(engine_path)
        self.engine_config = {
            "threads": 1,
            "hash": 16,
            "multipv": 1,
            "syzygy": "",
        }
        self.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.readyReadStandardOutput.connect(self.read_data)
        self.started.connect(self._on_started)
        self.errorOccurred.connect(self._on_error)
        self.finished.connect(self._on_finished)

        self.analysis_data = {}
        self.current_analyzing_fen = None
        self.searching = False
        self.next_analyzing_fen = None
        self.next_mode = "depth"
        self.next_options = {"depth": 20}

        self.is_uci_ready = False
        self.is_starting = False
        self.pending_search = None

    @staticmethod
    def _infer_name_from_path(path: str) -> str:
        if not path:
            return "Engine"
        import os
        base = os.path.splitext(os.path.basename(path))[0]
        if not base or base.lower() == "stockfish":
            return "Stockfish"
        return base.replace("-", " ").replace("_", " ").title()

    def _on_started(self):
        """Called asynchronously when engine process has started."""
        self.send_command("uci")

    def _on_error(self, error):
        """Handle process startup or runtime error without blocking."""
        self.is_uci_ready = False
        self.is_starting = False
        self.searching = False
        self.pending_search = None
        self.engineError.emit(str(error))

    def _on_finished(self, exit_code, exit_status):
        """Handle process termination."""
        self.is_uci_ready = False
        self.is_starting = False
        self.searching = False
        self.pending_search = None

    def read_data(self):
        try:
            raw_data = self.readAllStandardOutput().data().decode("utf-8", errors="replace")
        except Exception:
            return

        for line in raw_data.splitlines():
            line = line.strip()
            if line.startswith("id name "):
                name = line[len("id name "):].strip()
                if name:
                    self.engine_name = name
                    self.engineNameChanged.emit(name)

            if "uciok" in line:
                # Apply configured UCI options on handshake
                self.set_option("Threads", self.engine_config.get("threads", 1))
                self.set_option("Hash", self.engine_config.get("hash", 16))
                self.set_option("MultiPV", self.engine_config.get("multipv", 1))
                syzygy = self.engine_config.get("syzygy")
                if syzygy:
                    self.set_option("SyzygyPath", syzygy)
                self.send_command("isready")

            if "readyok" in line:
                self.is_uci_ready = True
                self.is_starting = False
                self.engineReady.emit()

                # If a search was queued while engine was launching/initializing, start it now
                if self.pending_search is not None:
                    pos, mode, opts = self.pending_search
                    self.pending_search = None
                    self.current_analyzing_fen = pos
                    self.next_analyzing_fen = None
                    self.searching = True
                    self._start_search(pos, mode, opts)

            if line.startswith("bestmove"):
                match = re.search(r"bestmove\s+(\S+)", line)
                if match:
                    self.moveFound.emit(match.group(1))
                if self.next_analyzing_fen is not None:
                    next_fen = self.next_analyzing_fen
                    next_mode = self.next_mode
                    next_opts = self.next_options

                    self.current_analyzing_fen = next_fen
                    self.next_analyzing_fen = None
                    self.searching = True
                    self._start_search(next_fen, next_mode, next_opts)
                else:
                    self.searching = False
                continue

            if line.startswith("info"):
                self.parse_info_line(line)

    def parse_info_line(self, line: str):
        # Extract depth
        depth_match = re.search(r"depth\s+(\d+)", line)
        if depth_match:
            depth = int(depth_match.group(1))
            self.depthChanged.emit(depth)

        # Extract MultiPV index
        multipv = 1
        multipv_match = re.search(r"multipv\s+(\d+)", line)
        if multipv_match:
            multipv = int(multipv_match.group(1))

        # Extract score
        score_type = None
        score_value = None
        cp_match = re.search(r"score cp (-?\d+)", line)
        mate_match = re.search(r"score mate (-?\d+)", line)

        if cp_match:
            score_type = "cp"
            score_value = int(cp_match.group(1))
        elif mate_match:
            score_type = "mate"
            score_value = int(mate_match.group(1))

        # Extract PV moves
        pv_match = re.search(r" pv\s+(.*)", line)
        pv_moves = []
        if pv_match:
            pv_moves = pv_match.group(1).split()

        if score_type and pv_moves:
            info = {
                "fen": self.current_analyzing_fen,
                "multipv": multipv,
                "score_type": score_type,
                "score_value": score_value,
                "pv": pv_moves,
                "depth": depth if depth_match else None,
            }
            self.analysisUpdated.emit(info)

    def set_option(self, name: str, value: Any):
        self.send_command(f"setoption name {name} value {value}")

    def set_multipv(self, count: int):
        """Dynamically update MultiPV, stopping search and syncing cleanly with UCI engine."""
        self.engine_config["multipv"] = count
        if not self.is_running() or not self.is_uci_ready:
            return

        # Stop current search and apply option
        self.send_command("stop")
        self.send_command(f"setoption name MultiPV value {count}")
        self.send_command("isready")

    def ensure_started(self) -> bool:
        """Start the engine process asynchronously without blocking the Qt event loop."""
        if self.is_running():
            if not self.is_uci_ready and not self.is_starting:
                self.send_command("uci")
            return True

        if not self.engine_path:
            return False

        self.is_uci_ready = False
        self.is_starting = True
        self.engineStarting.emit()

        self.setProgram(self.engine_path)
        self.start()
        return True

    def send_position(
        self, position: str, mode: Literal["depth", "time"] = "depth", options: dict = None
    ):
        if options is None:
            options = {"depth": 20}

        if not self.is_running() or not self.is_uci_ready:
            self.pending_search = (position, mode, options)
            self.ensure_started()
            return

        if self.searching:
            self.next_analyzing_fen = position
            self.next_mode = mode
            self.next_options = options
            self.send_command("stop")
        else:
            self.current_analyzing_fen = position
            self.next_analyzing_fen = None
            self.searching = True
            self._start_search(position, mode, options)

    def _start_search(self, position: str, mode: str, options: dict):
        self.send_command(f"position fen {position}")
        if mode == "depth":
            self.send_command(f"go depth {options.get('depth', 20)}")
        elif mode == "time":
            self.send_command(f"go movetime {options.get('time', 1000)}")
        else:
            self.send_command("go infinite")

    def stop_search(self):
        self.pending_search = None
        self.next_analyzing_fen = None
        self.searching = False
        if self.is_running():
            self.send_command("stop")

    def set_settings(self, settings: dict):
        """Update engine configuration without unnecessary process restarts."""
        path_changed = False
        if "path" in settings and settings["path"]:
            new_path = settings["path"]
            if new_path != self.engine_path:
                self.engine_path = new_path
                self.engine_name = self._infer_name_from_path(new_path)
                self.engineNameChanged.emit(self.engine_name)
                path_changed = True
        elif "path" in settings:
            self.engine_path = settings.get("path", self.engine_path)

        self.engine_config.update(settings)

        if path_changed and self.is_running():
            self.quit()
            self.ensure_started()
        elif self.is_running() and self.is_uci_ready:
            self.send_command("stop")
            self.set_option("Threads", self.engine_config.get("threads", 1))
            self.set_option("Hash", self.engine_config.get("hash", 16))
            self.set_option("MultiPV", self.engine_config.get("multipv", 1))
            syzygy = self.engine_config.get("syzygy")
            if syzygy:
                self.set_option("SyzygyPath", syzygy)
            self.send_command("isready")

    def send_command(self, command: str):
        if self.state() == QtCore.QProcess.Running:
            self.write(f"{command}\n".encode())

    def quit(self):
        """Cleanly terminate the engine process asynchronously without blocking the UI."""
        self.searching = False
        self.pending_search = None
        self.next_analyzing_fen = None
        self.current_analyzing_fen = None
        self.is_uci_ready = False
        self.is_starting = False
        if self.state() != QtCore.QProcess.NotRunning:
            self.send_command("quit")
            self.close()

    def is_running(self):
        return self.state() != QtCore.QProcess.NotRunning

