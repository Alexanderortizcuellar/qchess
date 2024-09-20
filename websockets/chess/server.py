from PyQt5.QtWebSockets import QWebSocket, QWebSocketServer
from PyQt5.QtCore import QObject, pyqtSignal


class ChessServer(QWebSocketServer):
    def __init__(self, parent):
        super().__init__(parent)
        