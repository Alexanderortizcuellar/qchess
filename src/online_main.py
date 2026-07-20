import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

# Add src and root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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
