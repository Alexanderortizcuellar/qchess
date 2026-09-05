import re
from typing import Literal, Any

from PyQt5 import QtCore


class ChessEngine(QtCore.QProcess):
    moveFound = QtCore.pyqtSignal(str)
    depthChanged = QtCore.pyqtSignal(int)
    analysisUpdated = QtCore.pyqtSignal(dict)  # Emits dict with MultiPV info

    def __init__(self, engine_path="stockfish", parent=None):
        super().__init__(parent)
        self.engine_path = engine_path
        self.engine_config = {
            "threads": 1,
            "hash": 16,
            "multipv": 1,
            "syzygy": "",
        }
        self.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.readyReadStandardOutput.connect(self.read_data)
        self.analysis_data = {}
        self.current_analyzing_fen = None
        self.searching = False
        self.next_analyzing_fen = None
        self.next_mode = "depth"
        self.next_options = {"depth": 20}

    def read_data(self):
        try:
            raw_data = self.readAllStandardOutput().data().decode("utf-8", errors="replace")
        except Exception:
            return

        for line in raw_data.splitlines():
            line = line.strip()
            if not line:
                continue

            if "uciok" in line:
                self.send_command("isready")

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

    def ensure_started(self) -> bool:
        """Start the engine process if it is not already running and configure UCI."""
        if self.is_running():
            return True

        if not self.engine_path:
            return False

        self.setProgram(self.engine_path)
        self.start()
        if not self.waitForStarted(3000):
            return False

        self.send_command("uci")
        if not self.waitForReadyRead(1000):
            pass

        self.set_option("Threads", self.engine_config.get("threads", 1))
        self.set_option("Hash", self.engine_config.get("hash", 16))
        self.set_option("MultiPV", self.engine_config.get("multipv", 1))

        syzygy = self.engine_config.get("syzygy")
        if syzygy:
            self.set_option("SyzygyPath", syzygy)

        self.send_command("isready")
        return True

    def send_position(
        self, position: str, mode: Literal["depth", "time"] = "depth", options: dict = None
    ):
        if not self.is_running():
            if not self.ensure_started():
                return

        if options is None:
            options = {"depth": 20}

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
        self.next_analyzing_fen = None
        self.searching = False
        self.send_command("stop")

    def set_settings(self, settings: dict):
        """Update engine configuration. Restarts process only if it is already running."""
        was_running = self.is_running()
        if was_running:
            self.quit()

        self.engine_path = settings.get("path", self.engine_path)
        self.engine_config.update(settings)

        if was_running:
            self.ensure_started()

    def send_command(self, command: str):
        if self.state() == QtCore.QProcess.Running:
            self.write(f"{command}\n".encode())

    def quit(self):
        """Cleanly terminate the engine process and release all its resources."""
        self.searching = False
        self.next_analyzing_fen = None
        self.current_analyzing_fen = None
        if self.state() != QtCore.QProcess.NotRunning:
            self.send_command("quit")
            if not self.waitForFinished(1000):
                self.terminate()
                if not self.waitForFinished(1000):
                    self.kill()
                    self.waitForFinished(500)
        self.close()

    def is_running(self):
        return self.state() != QtCore.QProcess.NotRunning

