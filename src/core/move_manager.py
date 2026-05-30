from io import StringIO

import chess
import chess.pgn
from PyQt5.QtCore import QObject, pyqtSignal

from core.pgn_to_html import pgn_to_html


class MoveManager(QObject):
    pgnChanged = pyqtSignal(str)

    def __init__(self, pgn_str: str | None = None):
        super().__init__()
        self.html, self.nodes = "", []
        self.html_style = False  # True for dark theme
        self.game = chess.pgn.Game()
        if pgn_str:
            self.update_pgn(pgn_str)
        self.current_node = self.game

    def load_fen(self, fen: str):
        self.game = chess.pgn.Game()
        board = chess.Board(fen)
        self.game.setup(board)
        self.current_node = self.game
        self.create_mapping()

    def update_pgn(self, pgn_str: str):
        pgn_io = StringIO(pgn_str)
        game = chess.pgn.read_game(pgn_io)
        if game:
            self.game = game
            self.create_mapping()
            return
        self.game = chess.pgn.Game()
        self.create_mapping()

    def load_pgn_file(self, filename: str):
        with open(filename, "r") as f:
            game = chess.pgn.read_game(f)
        self.game = game
        self.create_mapping()

    def make_move(self, move_uci):
        move = chess.Move.from_uci(move_uci)

        # Check if move already exists from here
        for var in self.current_node.variations:
            if var.move == move:
                self.current_node = var
                return

        # Otherwise, create new variation
        temp_node = self.current_node.add_variation(move)
        self.current_node = temp_node
        if self.current_node.board().result() != "*":
            self.game.headers["Result"] = self.current_node.board().result()
        self.create_mapping()

    def undo(self):
        if self.current_node.parent:
            self.current_node = self.current_node.parent
            self.create_mapping()

    def get_current_node_variations(self):
        """Return a list of variations from the current node."""
        variations = {}
        for index, var in enumerate(self.current_node.variations):
            san = self.current_node.board().san(var.move)
            variations[index] = {"uci": var.move.uci(), "san": san}
        return variations

    def get_node_by_index(self, index: int):
        return self.nodes[index]

    def has_variations(self):
        """Check if the current node has variations."""
        return len(self.current_node.variations) > 0

    def redo(self, variation_index=0):
        """Go forward into a variation. Default is main line (index 0)."""
        if self.current_node.variations:
            self.current_node = self.current_node.variations[variation_index]
            self.create_mapping()

    def jump_to(self, index: int):
        self.current_node = self.nodes[index]
        self.create_mapping()

    def jump_to_start(self):
        self.current_node = self.game
        self.create_mapping()

    def jump_to_end(self):
        if self.nodes:
            self.current_node = self.nodes[-1]
            self.create_mapping()

    def get_board(self):
        return self.current_node.board()

    def to_dict(self):
        "Not Implemented yet"
        pass

    def get_pgn(self):
        return str(self.game)

    def create_mapping(self):
        self.html, self.nodes = pgn_to_html(self.game, self.current_node, self.html_style)
        self.pgnChanged.emit(self.get_pgn())


    def add_comment(self, index: int, comment: str):
        node = self.get_node_by_index(index)
        node.comment = comment
        self.create_mapping()

    def promote_to_main(self, index: int):
        node = self.get_node_by_index(index)
        parent = node.parent
        if parent:
            parent.promote_to_main(node)
            self.create_mapping()

    def promote(self, index: int):
        node = self.get_node_by_index(index)
        parent = node.parent
        if parent:
            parent.promote(node)
            self.create_mapping()

    def demote(self, index: int):
        node = self.get_node_by_index(index)
        parent = node.parent
        if parent:
            parent.demote(node)
            self.create_mapping()

    def delete_from_here(self, index: int):
        node = self.get_node_by_index(index)
        parent = node.parent
        if parent:
            parent.remove_variation(node)
            # If we deleted the current node or one of its parents, jump to the parent
            temp = self.current_node
            is_parent = False
            while temp:
                if temp == node:
                    is_parent = True
                    break
                temp = temp.parent
            
            if is_parent:
                self.current_node = parent
                
            self.create_mapping()

    def change_html_style(self, html_style=False):
        self.html_style = html_style
        self.create_mapping()

    def clear(self):
        self.game = chess.pgn.Game()
        self.current_node = self.game
        self.create_mapping()
