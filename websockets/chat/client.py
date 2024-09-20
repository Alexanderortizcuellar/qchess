from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtCore import QUrl

class Client(QWebSocket):

    def __init__(self, parent=None):
        super().__init__(parent)

    def connect(self, url):
        self.open(QUrl(url))

    def sendMessage(self, message):
        pass