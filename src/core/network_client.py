import json
from PyQt5.QtCore import QObject, pyqtSignal, QUrl
from PyQt5.QtWebSockets import QWebSocket

class ChessClient(QObject):
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    errorOccurred = pyqtSignal(str)
    stateReceived = pyqtSignal(dict)
    gameListReceived = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = QWebSocket()
        self.client.connected.connect(self.connected.emit)
        self.client.disconnected.connect(self.disconnected.emit)
        self.client.textMessageReceived.connect(self._on_message)
        self.client.error.connect(self._on_error)

    def connect_to_server(self, url):
        self.client.open(QUrl(url))

    def disconnect_from_server(self):
        self.client.close()

    def _on_message(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "state":
                self.stateReceived.emit(data.get("snapshot", {}))
            elif msg_type == "game_list":
                self.gameListReceived.emit(data)
            elif msg_type == "error":
                self.errorOccurred.emit(data.get("message", "Unknown error"))
        except json.JSONDecodeError:
            self.errorOccurred.emit("Failed to decode server message")

    def _on_error(self, error_code):
        self.errorOccurred.emit(f"WebSocket error: {error_code}")

    def _send(self, payload):
        if self.client.isValid():
            self.client.sendTextMessage(json.dumps(payload))
        else:
            self.errorOccurred.emit("Not connected to server")

    def create_game(self, time_ms=600000, increment_ms=0, game_type="sudden_death"):
        config = {
            "type": game_type,
            "time_ms": time_ms
        }
        if game_type == "increment":
            config["increment_ms"] = increment_ms
            
        self._send({
            "type": "create_game", 
            "config": config
        })

    def join_game(self, game_id):
        self._send({"type": "join_game", "game_id": game_id})

    def make_move(self, game_id, uci):
        self._send({"type": "make_move", "game_id": game_id, "uci": uci})

    def resign(self, game_id):
        self._send({"type": "resign", "game_id": game_id})

    def abort(self, game_id):
        self._send({"type": "abort", "game_id": game_id})

    def get_state(self, game_id):
        self._send({"type": "get_state", "game_id": game_id})

    def list_games(self):
        self._send({"type": "list_games"})
