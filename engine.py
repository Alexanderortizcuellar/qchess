from typing import Literal

from PyQt5 import QtCore


class ChessEngine(QtCore.QProcess):
    moveFound = QtCore.pyqtSignal(str)
    depthChanged = QtCore.pyqtSignal(int)
    lineFound = QtCore.pyqtSignal(list)
    cpScoreFound = QtCore.pyqtSignal(int)
    mateFound = QtCore.pyqtSignal(int)

    def __init__(self, engine_path, parent=None):
        super().__init__(parent)
        self.engine_path = engine_path
        self.setProcessChannelMode(QtCore.QProcess.MergedChannels)
        self.setProgram(self.engine_path)
        self.readyReadStandardOutput.connect(self.read_data)
        self.stateChanged.connect(self.on_state_changed)

    def read_data(self):
        data = self.readAllStandardOutput().data().decode()
        if "uciok" in data:
            self.write("isready\n".encode())
        pattern = QtCore.QRegularExpression(r"(depth\s+)(\d+)")
        depth = pattern.match(data)
        if depth.hasMatch():
            self.depthChanged.emit(int(depth.captured(2)))
        pattern = QtCore.QRegularExpression(r"(bestmove\s+)(\w+)")
        best_move = pattern.match(data)

        if best_move.hasMatch():
            self.moveFound.emit(best_move.captured(2))
        pv_pattern = QtCore.QRegularExpression(r"(pv\s+)(.*)")
        pv_match = pv_pattern.match(data)
        if pv_match.hasMatch():
            pv_moves = pv_match.captured(2).split("pv")[-1].split()
            self.lineFound.emit(pv_moves)
        cp_pattern = QtCore.QRegularExpression(r"score cp (-?\d+)")
        cp_match = cp_pattern.match(data)
        if cp_match.hasMatch():
            self.cpScoreFound.emit(int(cp_match.captured(1)))
        if "mate" in data:
            mate_pattern = QtCore.QRegularExpression(r"score mate (-?\d+)")
            for line in data.splitlines():
                mate_match = mate_pattern.match(line)
                if mate_match.hasMatch():
                    self.mateFound.emit(int(mate_match.captured(1)))
            for line in data.splitlines():
                match_pv = pv_pattern.match(line)
                parts = match_pv.captured(0).split("pv")
                if len(parts) > 2:
                    moves = parts[-1].split()
                    self.lineFound.emit(moves)

    def set_threads(self, threads):
        self.write(f"setoption name Threads value {threads}\n".encode())

    def send_position(
        self, position: str, mode: Literal["depth", "time"], options: dict
    ):
        self.send_command(f"position fen {position}")
        if mode == "depth":
            self.send_command(f"go depth {options.get("depth")}")
        elif mode == "time":
            self.send_command(f"go time {options.get("time")}")

    def set_settings(self, settings: dict):
        if self.state() == QtCore.QProcess.Running:
            self.quit()
            self.waitForFinished()
            self.engine_path = settings["path"]
        self.setProgram(self.engine_path)
        self.set_threads(settings["threads"])
        self.start()
        self.waitForReadyRead()
        self.send_command("uci")

    def send_command(self, command: str):
        if self.state() == QtCore.QProcess.Running and self.isWritable():
            self.write(f"{command}\n".encode())

    def quit(self):
        if self.state() == QtCore.QProcess.Running:
            self.send_command("quit")
            self.waitForFinished()

    def is_running(self):
        return self.state() == QtCore.QProcess.Running

    def on_state_changed(self, state):
        if state == QtCore.QProcess.Running:
            print("Engine is running")
        elif state == QtCore.QProcess.NotRunning:
            print("Engine is not running or has stopped")
