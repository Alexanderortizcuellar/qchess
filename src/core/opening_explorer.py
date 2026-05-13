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

class OpeningExplorerHeader(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        
        self.move_lbl = QtWidgets.QLabel("Move")
        self.move_lbl.setFixedWidth(50)
        
        self.stats_lbl = QtWidgets.QLabel("Stats (W / D / B)")
        self.stats_lbl.setAlignment(QtCore.Qt.AlignCenter)
        
        layout.addWidget(self.move_lbl)
        layout.addWidget(self.stats_lbl)
        
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        color = "#8b8987" if is_dark else "#555555"
        style = f"color: {color}; font-weight: bold; font-size: 11px;"
        self.move_lbl.setStyleSheet(style)
        self.stats_lbl.setStyleSheet(style)

class PercentageBar(QtWidgets.QWidget):
    def __init__(self, white_win, draw, black_win, parent=None):
        super().__init__(parent)
        self.white_win = white_win
        self.draw = draw
        self.black_win = black_win
        self.setFixedHeight(24)
        self.is_dark = True

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        total_w = self.width()
        h = self.height()
        
        total = self.white_win + self.draw + self.black_win
        if total == 0: return
        
        pw = (self.white_win / total) * total_w
        pd = (self.draw / total) * total_w
        pb = total_w - pw - pd

        # Colors
        color_white = QtGui.QColor("#ffffff")
        color_draw = QtGui.QColor("#888888")
        color_black = QtGui.QColor("#312e2b")

        painter.setPen(QtCore.Qt.NoPen)
        
        # White
        if pw > 0:
            painter.setBrush(color_white)
            painter.drawRect(QtCore.QRectF(0, 0, pw, h))
            if pw > 25:
                painter.setPen(QtGui.QColor("#000000"))
                painter.drawText(QtCore.QRectF(0, 0, pw, h), QtCore.Qt.AlignCenter, f"{self.white_win:.0f}%")
        
        # Draw
        if pd > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_draw)
            painter.drawRect(QtCore.QRectF(pw, 0, pd, h))
            if pd > 25:
                painter.setPen(QtGui.QColor("#ffffff"))
        
        # Black
        if pb > 0:
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(color_black)
            painter.drawRect(QtCore.QRectF(pw + pd, 0, pb, h))
            if pb > 25:
                painter.setPen(QtGui.QColor("#ffffff"))
                painter.drawText(QtCore.QRectF(pw + pd, 0, pb, h), QtCore.Qt.AlignCenter, f"{self.black_win:.0f}%")

class MoveItem(QtWidgets.QWidget):
    def __init__(self, move_data, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)
        
        self.move_lbl = QtWidgets.QLabel(move_data["move"])
        self.move_lbl.setFixedWidth(50)
        
        self.bar = PercentageBar(
            move_data["white_wins"], 
            move_data["draws"], 
            move_data["black_wins"]
        )
        
        layout.addWidget(self.move_lbl)
        layout.addWidget(self.bar)
        
        self.set_theme(True)

    def set_theme(self, is_dark: bool):
        color = "#ffffff" if is_dark else "#312e2b"
        self.move_lbl.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 13px;")
        self.bar.set_theme(is_dark)

class OpeningExplorer(QtWidgets.QWidget):
    def __init__(self, parent=None, positions=[]):
        super().__init__(parent)
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.header = OpeningExplorerHeader(self)
        self.main_layout.addWidget(self.header)
        
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(1)
        self.container_layout.addStretch()
        
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)
        
        self.set_theme(True)

        if positions:
            self.update_positions(positions)

    def set_theme(self, is_dark: bool):
        self.is_dark = is_dark
        bg = "#262421" if is_dark else "#ffffff"
        self.setStyleSheet(f"background-color: {bg};")
        self.header.set_theme(is_dark)
        for i in range(self.container_layout.count()):
            w = self.container_layout.itemAt(i).widget()
            if isinstance(w, MoveItem):
                w.set_theme(is_dark)

    def update_positions(self, positions):
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        for move in positions:
            item = MoveItem(move, self)
            item.set_theme(self.is_dark)
            self.container_layout.insertWidget(self.container_layout.count() - 1, item)

class OpeningProcess(QtCore.QObject):
    dataReady = QtCore.pyqtSignal(list)
    errorOcurred = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = QtCore.QProcess(self)
        self.process.setProgram(r"C:\Users\ASUS\programming\qt_programs\chess\expl\expl.exe")
        self.process.readyReadStandardOutput.connect(self.process_output)
        self.path = r"C:\Users\ASUS\Downloads\alex.pgn"

    def start(self, fen):
        if self.process.state() == QtCore.QProcess.Running:
            return
        fen_parts = fen.split(" ")
        if len(fen_parts) > 4:
            fen = " ".join(fen_parts[0:4])
        
        self.process.setArguments([self.path, fen])
        self.process.start()

    def process_output(self):
        try:
            raw = self.process.readAllStandardOutput().data().decode("utf-8")
            if raw:
                data = json.loads(raw)
                self.dataReady.emit(data)
        except Exception as e:
            self.errorOcurred.emit(f"Explorer Error: {str(e)}")

class OpeningExplorerLogic(QtWidgets.QWidget):
    errorOcurred = QtCore.pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.explorer = OpeningExplorer(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.explorer)
        
        self.opening_process = OpeningProcess(self)
        self.opening_process.dataReady.connect(self.on_data_ready)
        self.opening_process.errorOcurred.connect(self.errorOcurred.emit)

    def set_theme(self, is_dark: bool):
        self.explorer.set_theme(is_dark)

    def on_data_ready(self, data):
        if data:
            data = sorted(
                data,
                key=lambda x: x["white_wins"] + x["draws"] + x["black_wins"],
                reverse=True,
            )
            self.explorer.update_positions(data[:12])

    def send_fen(self, fen):
        self.opening_process.start(fen)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    w = OpeningExplorer(positions=MOVES)
    w.resize(300, 400)
    w.show()
    sys.exit(app.exec_())
