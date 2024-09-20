from PyQt5 import QtGui, QtWidgets, QtCore

from pieces import pieces_info

class PromotionDlg(QtWidgets.QDialog):
    pieceSelected = QtCore.pyqtSignal(str)
    def __init__(self, parent=None, side="white"):
        super().__init__(parent)
        self.setWindowTitle("Promotion")
        self.setFixedSize(410, 200)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.boxlayout = QtWidgets.QVBoxLayout()
        self.buttons_layout = QtWidgets.QHBoxLayout()
        self.buttons_layout.setContentsMargins(0, 0, 0, 50)
        self.boxlayout.addLayout(self.buttons_layout)
        self.setLayout(self.boxlayout)
        # Queen settings
        self.queen = QtWidgets.QToolButton()
        self.queen.setObjectName("Q" if side == "white" else "q")
        queen_icon = QtGui.QIcon(pieces_info["Q"] if side == "white" else pieces_info["q"])
        self.queen.setIcon(queen_icon)
        self.queen.clicked.connect(lambda: self.piece_selected(self.queen))
        self.queen.setIconSize(QtCore.QSize(100, 100))
        self.queen.setFixedSize(100, 100)
        # Knight settings
        self.knight = QtWidgets.QToolButton(self)
        self.knight.setObjectName("N" if side == "white" else "n")
        knight_icon = QtGui.QIcon(pieces_info["N"] if side == "white" else pieces_info["n"])       
        self.knight.setIcon(knight_icon)
        self.knight.clicked.connect(lambda: self.piece_selected(self.knight))
        self.knight.setIconSize(QtCore.QSize(100, 100))
        self.knight.setFixedSize(100, 100)
        # Rook settings
        self.rock = QtWidgets.QToolButton(self)
        self.rock.setObjectName("R" if side == "white" else "r")
        rock_icon = QtGui.QIcon(pieces_info["R"] if side == "white" else pieces_info["r"])
        self.rock.setIcon(rock_icon)
        self.rock.clicked.connect(lambda: self.piece_selected(self.rock))
        self.rock.setIconSize(QtCore.QSize(100, 100))
        self.rock.setFixedSize(100, 100)
        
        # Bishop settings
        self.bishop = QtWidgets.QToolButton(self)
        self.bishop.setObjectName("B" if side == "white" else "b")
        bishop_icon = QtGui.QIcon(pieces_info["B"] if side == "white" else pieces_info["b"])
        self.bishop.setIcon(bishop_icon)
        self.bishop.clicked.connect(lambda: self.piece_selected(self.bishop))
        self.bishop.setIconSize(QtCore.QSize(100, 100))
        self.bishop.setFixedSize(100, 100)

        # Add buttons
        self.buttons_layout.addWidget(self.queen)
        self.buttons_layout.addWidget(self.knight)
        self.buttons_layout.addWidget(self.rock)
        self.buttons_layout.addWidget(self.bishop)
        self.buttonbox = QtWidgets.QDialogButtonBox(self)
        self.buttonbox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonbox.setStandardButtons(
            QtWidgets.QDialogButtonBox.Cancel
        )
        self.buttonbox.rejected.connect(self.reject)
        self.boxlayout.addWidget(self.buttonbox)

    def piece_selected(self, piece):
        self.pieceSelected.emit(piece.objectName())
        print(piece.objectName())
        self.accept()



