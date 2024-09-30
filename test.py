from app.playerbar import PlayerBar
from PyQt5 import QtWidgets




if __name__ == "__main__":
    app = QtWidgets.QApplication([])
    window = PlayerBar()
    window.show()
    app.exec()