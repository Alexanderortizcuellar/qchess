from PyQt5 import QtCore, QtWidgets, QtGui
from clock import Timer


class ClockManager(QtCore.QObject):
    finished = QtCore.pyqtSignal(bool)
    timeChanged = QtCore.pyqtSignal(dict)

    def __init__(
        self, parent: QtWidgets.QWidget | None = None, time: int = 30000
    ) -> None:
        super().__init__(parent)
        self.timer1 = Timer(self, time)
        self.timer2 = Timer(self, time)
        self.timer1.timeChanged.connect(self._process_update)
        self.timer2.timeChanged.connect(self._process_update)

    def _process_update(self):
        self.timeChanged.emit(
            {"player1": self.timer1.format_time(), "player2": self.timer2.format_time()}
        )
        print(self.timer1.format_time(), self.timer2.format_time())

    def start(self, player: int):
        if player == 1:
            self.timer1.start()
        else:
            self.timer2.start()

    def pause(self, player: int):
        if player == 1:
            self.timer1.pause()
        else:
            self.timer2.pause()

    def restart(self, player: int):
        if player == 1:
            self.timer1.restart()
        else:
            self.timer2.restart()

    def push(self, player: int, increment: int = 10000):
        if player == 1:
            self.timer1.pause()
            self.timer1.setTime(self.timer1.time + increment)
            self.timer2.start()
        else:
            self.timer2.pause()
            self.timer2.setTime(self.timer2.time + increment)
            self.timer1.start()

    def add_time(self, player: int, time: int):
        if player == 1:
            self.timer1.setTime(time)
        else:
            self.timer2.setTime(time)

    def pause_all(self):
        self.timer1.pause()
        self.timer2.pause()

    def restart_all(self):
        self.timer1.restart()
        self.timer2.restart()

    def start_all(self):
        self.timer1.start()
        self.timer2.start()


class ManagerTest(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.manager = ClockManager()
        self.label = QtWidgets.QLabel("")
        self.label1 = QtWidgets.QLabel("")
        self.manager.timer1.timeChangedFormatted.connect(self.label.setText)
        self.manager.timer2.timeChangedFormatted.connect(self.label1.setText)
        self.labeltimer = QtWidgets.QLabel("Timer: 1")
        self.button1 = QtWidgets.QPushButton("push 1")
        self.label1timer = QtWidgets.QLabel("Timer: 2")
        self.button2 = QtWidgets.QPushButton("push 2")
        self.pause1 = QtWidgets.QPushButton("Pause 1")
        self.pause2 = QtWidgets.QPushButton("Pause 2")
        self.restart1 = QtWidgets.QPushButton("Restart 1")
        self.restart2 = QtWidgets.QPushButton("Restart 2")
        self.strtBtn = QtWidgets.QPushButton("Start 1")
        self.strtBtn1 = QtWidgets.QPushButton("Start 2")
        self.strtBtn.clicked.connect(lambda: self.manager.start(1))
        self.strtBtn1.clicked.connect(lambda: self.manager.start(2))

        self.button1.clicked.connect(lambda: self.manager.push(1, 10000))
        self.button2.clicked.connect(lambda: self.manager.push(2, 10000))
        self.pause1.clicked.connect(lambda: self.manager.pause(1))
        self.pause2.clicked.connect(lambda: self.manager.pause(2))
        self.restart1.clicked.connect(lambda: self.manager.restart(1))
        self.restart2.clicked.connect(lambda: self.manager.restart(2))
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.labeltimer)
        layout.addWidget(self.label)
        layout.addWidget(self.label1timer)
        layout.addWidget(self.label1)
        layout.addWidget(self.button1)
        layout.addWidget(self.button2)
        layout.addWidget(self.pause1)
        layout.addWidget(self.pause2)
        layout.addWidget(self.restart1)
        layout.addWidget(self.restart2)
        layout.addWidget(self.strtBtn)
        layout.addWidget(self.strtBtn1)
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)


app = QtWidgets.QApplication([])
window = ManagerTest()
window.show()
app.exec()
