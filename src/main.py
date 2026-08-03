import sys
from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon


def load_stylesheet(filename):
    with open(filename, "r") as f:
        return f.read()


def main():
    import os
    # Add project root to sys.path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    app = QApplication(sys.argv)

    # Load splash image
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
    # import application controller
    from gui.app_controller import ApplicationController

    splash.finish(None)  # close splash

    controller = ApplicationController()
    controller.set_icon(QIcon(pix))
    controller.set_style("dark")
    controller.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
