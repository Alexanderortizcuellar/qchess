import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget
from PyQt5.QtCore import QProcess, QRegularExpression

class ChessEngine(QMainWindow):
    def __init__(self):
        super().__init__()

        self.initUI()
        self.initProcess()

    def initUI(self):
        self.setWindowTitle("Stockfish Communicator")

        self.textEdit = QTextEdit(self)
        self.textEdit.setReadOnly(True)

        self.button = QPushButton("Get Best Move", self)
        self.button.clicked.connect(self.requestBestMove)

        layout = QVBoxLayout()
        layout.addWidget(self.textEdit)
        layout.addWidget(self.button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def initProcess(self):
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.readOutput)
        # Start Stockfish (replace 'path_to_stockfish' with the actual path)
        self.process.start("./stockfish")

    def requestBestMove(self):
        self.sendCommand("position startpos\n")
        self.sendCommand("go depth 30\n")

    def sendCommand(self, command):
        if self.process.state() == QProcess.Running:
            self.process.write((command + '\n').encode())

    def readOutput(self):
        output = self.process.readAllStandardOutput().data().decode()
        pattern = QRegularExpression(r"(bestmove\s+)(\w+)")
        result = pattern.match(output)
        if result.hasMatch():
            self.textEdit.setText(result.captured(2))


    def closeEvent(self, event):
        self.sendCommand("quit\n")
        self.process.terminate()
        self.process.waitForFinished(1000)
        if self.process.state() == QProcess.Running:
            self.process.kill()
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChessEngine()
    window.resize(400, 300)
    window.show()
    sys.exit(app.exec_())
