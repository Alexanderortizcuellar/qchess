from PyQt5.QtCore import QObject, pyqtSignal, QProcess, QRegularExpression


class Command:
    isready = "israedy\n"
    uci = "uci\n"
    fen = "position"
    go = "go depth 30\n"
    close = "quit\n"


class QEngine(QObject):
    bestMoveFound = pyqtSignal(str)
    depth = pyqtSignal(str)
    output_received = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QProcess()
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput(self.read_data)
        self.process.stateChanged.connect(self.on_state_change)

    def check_state(self) -> bool:
        self.send_command(Command.isready)
        return True

    def request_output(self, fen: str) -> None:
        if self.check_state():
            self.send_command(Command.fen + fen)
            self.send_command(Command.go)

    def read_data(self):
        bytes_data = self.process.readAllStandardOutput()
        string_data = bytes_data.data().decode("utf-8")
        pattern = QRegularExpression("depth\s+\d+")
        depth = pattern.match(string_data)
        if depth.hasMatch():
            self.depth.emit(depth.captured())
        pattern = QRegularExpression(r"(bestmove\s+)(\w+)")
        best_move = pattern.match(string_data)
        if best_move.hasMatch():
            self.bestMoveFound.emit(best_move.captured())
        self.output_received.emit(string_data)

    def on_state_change(self, state: QProcess.state):
        print(state)

    def send_command(self, command: str):
        self.process.write(command.encode("utf-8"))

    def start(self, path: str) -> bool:
        if not self.process.state() == QProcess.Running:
            self.process.start(path)
            return True
        return False

    def close(self):
        if self.process.isOpen():
            self.send_command(Command.close)
        self.process.terminate()
