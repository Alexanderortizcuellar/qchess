from PyQt5 import QtCore, QtGui, QtWidgets
import sys
import json


MOVES = [
    {"black_wins": 1, "draws": 0, "move": "Bd6", "white_wins": 0},
    {"black_wins": 0, "draws": 0, "move": "Nb4", "white_wins": 1},
    {"black_wins": 1, "draws": 0, "move": "Nd4", "white_wins": 0},
    {"black_wins": 3, "draws": 1, "move": "Nf6", "white_wins": 3},
    {"black_wins": 1, "draws": 0, "move": "Qf6", "white_wins": 0},
    {"black_wins": 0, "draws": 0, "move": "a5", "white_wins": 1},
    {"black_wins": 64, "draws": 4, "move": "a6", "white_wins": 95},
    {"black_wins": 1, "draws": 0, "move": "d6", "white_wins": 3},
    {"black_wins": 1, "draws": 0, "move": "f5", "white_wins": 0},
    {"black_wins": 0, "draws": 0, "move": "g6", "white_wins": 1},
]


class PercentageBar(QtWidgets.QWidget):
    def __init__(self, white_win, draw, black_win, parent=None):
        super().__init__(parent)
        self.white_win = white_win
        self.draw = draw
        self.black_win = black_win
        self.setFixedHeight(30)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setMinimumWidth(150)
        total_w = self.width()
        h = self.height()
        radius = h / 2

        # Segment widths
        w_white = total_w * (self.white_win / 100)
        w_draw = total_w * (self.draw / 100)
        w_black = total_w * (self.black_win / 100)

        # Draw outer frame
        pen = QtGui.QPen(QtGui.QColor(120, 120, 120))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(0, 0, total_w, h, radius, radius)

        def draw_segment(x, w, start_color, end_color, text, text_color):
            if w <= 0:
                return

            # Gradient fill
            grad = QtGui.QLinearGradient(x, 0, x + w, 0)
            grad.setColorAt(0.0, QtGui.QColor(*start_color))
            grad.setColorAt(1.0, QtGui.QColor(*end_color))
            painter.setBrush(grad)
            painter.setPen(QtCore.Qt.NoPen)

            # Determine corner radii
            tl = radius if x == 0 else 0
            tr = radius if x + w == total_w else 0
            bl = tl
            br = tr

            # Build path
            path = QtGui.QPainterPath()
            path.moveTo(x + tl, 0)
            path.lineTo(x + w - tr, 0)
            if tr:
                path.arcTo(x + w - 2 * tr, 0, 2 * tr, 2 * tr, 90, -90)
            path.lineTo(x + w, h - br)
            if br:
                path.arcTo(x + w - 2 * br, h - 2 * br, 2 * br, 2 * br, 0, -90)
            path.lineTo(x + bl, h)
            if bl:
                path.arcTo(x, h - 2 * bl, 2 * bl, 2 * bl, 270, -90)
            path.lineTo(x, tl)
            if tl:
                path.arcTo(x, 0, 2 * tl, 2 * tl, 180, -90)
            path.closeSubpath()

            painter.drawPath(path)

            # Draw centered text
            painter.setPen(QtGui.QColor(*text_color))
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QtCore.QRectF(x, 0, w, h), QtCore.Qt.AlignCenter, text)

        # Draw each segment with its own colors and text style
        draw_segment(
            0,
            w_white,
            start_color=(250, 250, 250),  # near-white
            end_color=(230, 230, 230),
            text=f"{self.white_win:.1f}%",
            text_color=(30, 30, 30),  # dark text
        )
        draw_segment(
            w_white,
            w_draw,
            start_color=(100, 100, 100),  # mid-gray
            end_color=(80, 80, 80),
            # text=f"{self.draw:.1f}%",
            text="",
            text_color=(30, 30, 30),  # dark text
        )
        draw_segment(
            w_white + w_draw,
            w_black,
            start_color=(60, 60, 60),  # dark gray
            end_color=(30, 30, 30),
            text=f"{self.black_win:.1f}%",
            text_color=(245, 245, 245),  # light text
        )


class MoveBarContainer(QtWidgets.QFrame):
    def __init__(self, move_name, white, draw, black, parent=None):
        super().__init__(parent)

        # Frame styling: rounded corners + subtle border
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                border: 1px solid #888;
                border-radius: 6px;
                background-color: rgb(110, 110, 110);
            }
        """)

        # Layout: [Label] [PercentageBar]
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Move label
        label = QtWidgets.QLabel(f"{move_name}")
        label.setFixedWidth(40)
        label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
        font = label.font()
        font.setBold(True)
        font.setPointSize(10)
        label.setFont(font)
        label.setStyleSheet("color: rgb(245, 245, 245);border: none;")
        # Percentage bar
        bar = PercentageBar(white, draw, black, parent=self)
        bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # Assemble
        layout.addWidget(label)
        layout.addWidget(bar)


class OpeningExplorer(QtWidgets.QWidget):
    def __init__(self, parent=None, positions=[]):
        super().__init__()
        self.setStyleSheet("background-color: rgb(120, 120, 120);")

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)

        self.update_positions(positions)

    def clear_positions(self):
        for i in reversed(range(self.main_layout.count())):
            self.main_layout.itemAt(i).widget().deleteLater()

    def update_positions(self, positions):
        self.clear_positions()
        for move in positions:
            total = move["white_wins"] + move["draws"] + move["black_wins"]
            white_percentage = (move["white_wins"] / total) * 100
            draw_percentage = (move["draws"] / total) * 100
            black_percentage = (move["black_wins"] / total) * 100
            bar = MoveBarContainer(
                move["move"],
                white_percentage,
                draw_percentage,
                black_percentage,
                parent=self,
            )
            self.main_layout.addWidget(bar)


class OpeningProcess(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    dataReady = QtCore.pyqtSignal(list)
    errorOcurred = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QtCore.QProcess(self)
        self.process.setProgram(
            r"C:\Users\ASUS\programming\qt_programs\chess\expl\expl.exe"
        )
        self.process.readyReadStandardOutput.connect(self.process_output)
        # self.process.stateChanged.connect(self.on_state_changed)
        self.path = r"C:\Users\ASUS\Downloads\alex.pgn"

    def start(self, fen):
        if self.process.state() == QtCore.QProcess.Running:
            return
        fen = " ".join(fen.split(" ")[0:-2])
        self.process.setArguments([self.path, fen])
        self.process.start()

    def process_output(self):
        try:
            data = json.loads(
                self.process.readAllStandardOutput().data().decode("utf-8")
            )
            self.dataReady.emit(data)
        except Exception as e:
            self.errorOcurred.emit(
                str(
                    {
                        "error": str(e),
                        "data": self.process.readAllStandardOutput()
                        .data()
                        .decode("utf-8"),
                    }
                )
            )

    def on_state_changed(self, state):
        if state == QtCore.QProcess.Running:
            print("Engine is running")
        elif state == QtCore.QProcess.NotRunning:
            print("Engine is not running or has stopped")


class OpeningExplorerLogic(QtWidgets.QWidget):
    errorOcurred = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.explorer = OpeningExplorer(parent=self, positions=MOVES)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.explorer)
        self.opening_process = OpeningProcess(parent=self)
        self.opening_process.dataReady.connect(self.on_data_ready)
        self.opening_process.errorOcurred.connect(self.errorOcurred.emit)

    def on_data_ready(self, data):
        if data:
            data = sorted(
                data,
                key=lambda x: x["white_wins"] + x["draws"] + x["black_wins"],
                reverse=True,
            )
            if len(data) > 10:
                self.explorer.update_positions(data[0:10])
            else:
                self.explorer.update_positions(data)

    def send_fen(self, fen):
        self.opening_process.start(fen=fen)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    opening_explorer = OpeningExplorer(positions=MOVES)
    opening_explorer.show()
    sys.exit(app.exec_())
