from PyQt5 import QtGui, QtCore, QtWidgets


class Timer(QtCore.QObject):
    finished = QtCore.pyqtSignal(bool)
    timeChanged = QtCore.pyqtSignal(int)
    timeChangedFormatted = QtCore.pyqtSignal(str)
    timer_low = QtCore.pyqtSignal(bool)

    def __init__(self, parent, time: int):
        super().__init__(parent)
        self.parent = parent
        self.timer = QtCore.QTimer()
        self.initial_time = time
        self.time = time
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.update_time)

    def start(self):
        """
        start the timer
        time: number of milliseconds.
        """
        self.timer.start()

    def restart(self):
        self.timer.stop()
        print("restarting", self.initial_time)
        self.time = self.initial_time
        self.timer.start()

    def pause(self):
        self.timer.stop()

    def setTime(self, time: int):
        self.timer.stop()
        self.time = time
        self.initial_time = time
        self.timeChanged.emit(self.time)
        self.timeChangedFormatted.emit(self.format_time())

    def update_time(self):
        if self.time <= 0:
            self.time_over()
            return
        if self.time < 10 * 1000:
            self.timer_low.emit(True)
        self.time -= 1
        self.timeChanged.emit(self.time)
        self.timeChangedFormatted.emit(self.format_time())

    def format_time(self):
        _, mills_left = divmod(self.time, 60 * 60 * 1000)
        minutes, mills_left = divmod(mills_left, 60 * 1000)
        seconds, mills_left = divmod(mills_left, 1000)
        if self.time < 3 * 1000:
            return f"{minutes:02d}:{seconds:02d}:{mills_left:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    

    @QtCore.pyqtSlot()
    def time_over(self):
        self.timer.stop()
        self.finished.emit(True)
        print("Not more time")


class Clock(QtWidgets.QWidget):

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        color: str = "white",
    ) -> None:
        super().__init__(parent)
        fg = "black" if color == "white" else "white"
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.display = QtWidgets.QLabel(self)
        self.display.setText("00:00.0")
        self.display.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.display.setFont(QtGui.QFont("Times", 12, weight=QtGui.QFont.Bold))
        self.layout.addWidget(self.display)
        self.display.setStyleSheet(f"color: {fg};background-color: {color};border: 1px solid transparent;border-radius: 10px;padding: 5px 40px;")
        self.setMinimumWidth(150)

    def handle_low_time(self):
        self.display.setStyleSheet("color: red;")

    def showTime(self, time: str):
        print(time)

