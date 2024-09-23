from PyQt5.QtWebSockets import QWebSocket, QWebSocketServer
from PyQt5.QtNetwork import QHostAddress

# from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtCore import QCoreApplication, QJsonDocument
from collections import Counter

import json


class Codes:
    update = "(:UPDATE:)"
    group = "(:GRP:)"
    message = "(:MSG:)"


class ChessServer(QWebSocketServer):
    def __init__(self, name, mode, parent=None):
        super().__init__(name, mode, parent)
        self.newConnection.connect(self.handle_connection)
        self.clients: dict[QWebSocket, dict[str, str]] = {}

    def start(self):
        if not self.listen(QHostAddress.LocalHost, 1234):
            print("Could not start server")
            return False
        print(f"Server started on port {self.serverPort()}")
        return True

    def handle_connection(self):
        websocket = self.nextPendingConnection()
        if websocket:
            print(f"Client connected: {websocket.peerAddress().toString()}")
            websocket.connected.connect(self.handle_connected)
            websocket.textMessageReceived.connect(self.handle_text_message)
            websocket.disconnected.connect(self.handle_disconnected)
            self.clients[websocket] = {}

    def handle_connected(self):
        print("Client connected")

    def handle_text_message(self, message: str):
        client = self.sender()
        if message.startswith("(:GRP:)"):
            print(":GRP: message received")
            self.clients[client]["group"] = str(message.split("(:GRP:)")[1])
            return
        if message.startswith("(:UPDATE:)"):
            print(":UPDATE: message received")
            avilable_groups = self.get_available_groups()
            client.sendTextMessage(Codes.update + json.dumps(avilable_groups))
            return
        if message.startswith("(:MSG:)"):
            print(":MSG: message received")
            for client_local in self.clients.keys():
                if (
                    self.clients[client_local]["group"] == self.clients[client]["group"]
                ) and (client_local != client):
                    print(message.split("(:MSG:)")[1], self.clients[client]["group"])
                    client_local.sendTextMessage(message)
        self.read_json(message)

    def read_json(self, text: str):
        try:
            json = QJsonDocument.fromJson(bytes(text, "utf-8"))
            data = json.object()["msg"].toString()
            return data
        except Exception:
            return text

    def jsonify(self, data):
        return QJsonDocument(QJsonDocument.fromVariant(data))

    def get_available_groups(self):
        group_names = [
            group.get("group") for group in self.clients.values() if group.get("group")
        ]
        group_counter = dict(Counter(group_names))
        available = [group for group in group_counter if group_counter[group] == 1]
        return available

    def handle_disconnected(self):
        client: QWebSocket = self.sender()
        self.clients.pop(client)
        client.deleteLater()
        print("Client disconnected")


if __name__ == "__main__":
    app = QCoreApplication([])
    server = ChessServer("chess server", QWebSocketServer.NonSecureMode)
    server.start()
    app.exec()
