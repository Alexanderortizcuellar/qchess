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
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(os.path.dirname(current_dir), "assets")
    
    pix = QPixmap(os.path.join(assets_dir, "icon.png"))
    pix = pix.scaledToWidth(528, Qt.SmoothTransformation)

    # Create splash screen
    splash = QSplashScreen(pix, Qt.WindowStaysOnTopHint)
    splash.show()
    # load stylesheet
    style = load_stylesheet(os.path.join(assets_dir, "style.qss"))
    app.setStyleSheet(style)
    # import modules 
    from gui.app import ChessApp

    splash.finish(None)  # close splash
    window = ChessApp()
    window.setWindowIcon(QIcon(pix))
    window.set_html_style(True)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
