import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt

# Add src to path if necessary
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def load_stylesheet(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return f.read()
    return ""

def main():
    app = QApplication(sys.argv)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(os.path.dirname(current_dir), "assets")
    
    # Load stylesheet
    style = load_stylesheet(os.path.join(assets_dir, "style.qss"))
    app.setStyleSheet(style)
    
    from gui.online_app import OnlineChessApp
    
    window = OnlineChessApp()
    
    # Set icon if available
    icon_path = os.path.join(assets_dir, "icon.png")
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
        
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
