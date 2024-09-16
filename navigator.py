from PyQt5.QtCore import QObject


class Navigator(QObject):
    def __init__(self, parent, moves: list[str]):
        super().__init__()
        self.parent = parent
        self.moves = moves

    def next(self):
        pass

    def previous(self):
        pass

    def restart(self):
        pass

    def undo(self):
        pass

    def redo(self):
        pass
    def delete_move(self):
        pass