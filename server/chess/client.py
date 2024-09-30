from PyQt5.QtNetwork import QAbstractSocket
from PyQt5.QtCore import QObject, QUrl, pyqtSignal, QJsonDocument
from PyQt5.QtWebSockets import QWebSocket
from PyQt5 import QtWidgets, QtCore
import json


class Codes:
    update = "(:UPDATE:)"
    group = "(:GRP:)"
    message = "(:MSG:)"


class ChessClient(QWebSocket):
    connected_signal = pyqtSignal()
    move_received = pyqtSignal(str)
    disconnected_signal = pyqtSignal(bool)
    state_changed = pyqtSignal(str)
    joined_group = pyqtSignal(str)
    leave_group = pyqtSignal(str)

    def __init__(self, parent, url):
        super().__init__()
        self.parent = parent
        self.url = url
        self.generator = QtCore.QUuid()
        self.connected.connect(self.handle_connected)
        self.textMessageReceived.connect(self.handle_text_message)
        self.stateChanged.connect(self.handle_state_changed)
        self.disconnected.connect(self.handle_disconnected)
        self.error.connect(self.handle_error)

    def start(self):
        self.open(QUrl(self.url))

    def join(self):

        self.joined_group.emit("alex")
        self.sendTextMessage(Codes.group + "alex")

    def handle_connected(self):
        self.sendTextMessage(Codes.update)

    def handle_state_changed(self, state):
        # Log state changes for debugging
        if state == QAbstractSocket.ConnectedState:
            print("WebSocket is connected.")
            self.state_changed.emit("Connected to server")
        elif state == QAbstractSocket.UnconnectedState:
            print("WebSocket is not connected.")
            self.state_changed.emit("Not connected to server")
            self.disconnected_signal.emit(True)
        elif state == QAbstractSocket.ConnectingState:
            print("WebSocket is connecting.")
            self.state_changed.emit("Connecting to server")
        elif state == QAbstractSocket.ClosingState:
            print("WebSocket is closing.")
            self.state_changed.emit("Closing connection")
        else:
            print("Unknown WebSocket state:", state)
            self.state_changed.emit("Unknown state")

    def handle_text_message(self, message: str):
        if message.startswith(Codes.update):
            groups = json.loads(message.split(Codes.update)[1])
            if len(groups) > 0:
                self.sendTextMessage(Codes.group + groups[0])
            else:
                self.join()
        elif message.startswith(Codes.message):
            print(f"received move {message}")
            self.move_received.emit(message.split(Codes.message)[1])

    def handle_disconnected(self):
        self.disconnected_signal.emit(True)
        print("Client disconnected")

    def handle_error(self, error: int):
        print("Client error", error)

    def send_move(self, move: str):
        self.sendTextMessage(Codes.message + move)

    def _create_group_name(self):
        return self.generator.createUuid().toString()


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.chess_client = ChessClient(self)
        self.chess_client.start()
        self.box = QtWidgets.QWidget()
        self.setCentralWidget(self.box)
        self.layout = QtWidgets.QVBoxLayout()
        self.box.setLayout(self.layout)
        self.button = QtWidgets.QPushButton("Send message")
        self.screen = QtWidgets.QTextEdit()
        self.screen.setReadOnly(True)
        self.chess_client.message_received.connect(self.screen.append)
        self.layout.addWidget(self.screen)
        # self.button.clicked.connect(self.send_message)
        self.layout.addWidget(self.button)
        self.label = QtWidgets.QLabel("")
        self.layout.addWidget(self.label)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = Window()
    window.show()
    app.exec()
