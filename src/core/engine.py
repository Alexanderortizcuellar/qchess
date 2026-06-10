import re
from typing import Literal, Any

from PyQt5 import QtCore


class ChessEngine(QtCore.QProcess):
    moveFound = QtCore.pyqtSignal(str)
    depthChanged = QtCore.pyqtSignal(int)
    analysisUpdated = QtCore.pyqtSignal(dict)  # Emits dict with MultiPV info

    def __init__(self, engine_path, parent=None):
        super().__init__(parent)
        self.engine_path = engine_path
        self.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.setProgram(self.engine_path)
        self.readyReadStandardOutput.connect(self.read_data)
        self.analysis_data = {}

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
        
        # We need to know who is to move to normalize to White POV if the engine doesn't
        # But UCI standard says score is relative to the side to move.
        # However, many implementations (including python-chess) expect absolute (White POV).
        # We'll normalize in the app or here if we have the board state.
        
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
                "multipv": multipv,
                "score_type": score_type,
                "score_value": score_value,
                "pv": pv_moves,
                "depth": depth if depth_match else None
            }
            self.analysisUpdated.emit(info)

    def set_option(self, name: str, value: Any):
        self.send_command(f"setoption name {name} value {value}")

    def send_position(
        self, position: str, mode: Literal["depth", "time"] = "depth", options: dict = None
    ):
        if options is None:
            options = {"depth": 20}
        
        self.send_command(f"position fen {position}")
        if mode == "depth":
            self.send_command(f"go depth {options.get('depth', 20)}")
        elif mode == "time":
            self.send_command(f"go time {options.get('time', 1000)}")
        else:
            self.send_command("go infinite")

    def set_settings(self, settings: dict):
        # settings keys: path, threads, hash, multipv, etc.
        is_running = self.is_running()
        if is_running:
            self.quit()
        
        self.engine_path = settings.get("path", self.engine_path)
        self.setProgram(self.engine_path)
        self.start()
        if not self.waitForStarted(3000):
            return
            
        self.send_command("uci")
        if not self.waitForReadyRead(3000):
            pass # Continue anyway
            
        self.set_option("Threads", settings.get("threads", 1))
        self.set_option("Hash", settings.get("hash", 16))
        self.set_option("MultiPV", settings.get("multipv", 1))
        
        # Syzygy
        syzygy = settings.get("syzygy")
        if syzygy:
            self.set_option("SyzygyPath", syzygy)

        self.send_command("isready")

    def send_command(self, command: str):
        if self.state() == QtCore.QProcess.Running:
            self.write(f"{command}\n".encode())

    def quit(self):
        if self.state() == QtCore.QProcess.Running:
            self.send_command("quit")
            if not self.waitForFinished(2000):
                self.terminate()

    def is_running(self):
        return self.state() == QtCore.QProcess.Running

