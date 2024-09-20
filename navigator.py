from PyQt5.QtCore import QObject


class Navigator(QObject):
    def __init__(self, parent, moves: list[str]):
        super().__init__()
        self.parent = parent
        self.moves = moves
        self.index = 0

    def next(self):
        if self.index < len(self.moves):
            move = self.moves[self.index]
            self.index += 1
            return move

    def previous(self):
        if self.index > 0:
            move = self.moves[self.index]
            self.index -= 1
            return move

    def restart(self):
        self.index = 0

    def undo(self):
        pass

    def redo(self):
        pass

    def add_move(self, move_uci: str):
        self.moves.append(move_uci)

    def delete_move(self):
        pass

    def go_to(self, index: int):
        if index > 0 and index < len(self.moves):
            return self.moves[index]
