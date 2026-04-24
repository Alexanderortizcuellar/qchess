import sys
from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon


def load_stylesheet(filename):
    with open(filename, "r") as f:
        return f.read()


def main():
    app = QApplication(sys.argv)

    # Load splash image
    pix = QPixmap("icon.png")
    pix = pix.scaledToWidth(528, Qt.SmoothTransformation)

    # Create splash screen
    splash = QSplashScreen(pix, Qt.WindowStaysOnTopHint)
    splash.show()
    # load stylesheet
    style = load_stylesheet("style.qss")
    app.setStyleSheet(style)
    # import modules
    from chessapp import ChessApp

    splash.finish(None)  # close splash
    window = ChessApp()
    window.setWindowIcon(QIcon(pix))
    window.set_html_style(True)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
