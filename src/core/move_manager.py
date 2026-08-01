from io import StringIO

import chess
import chess.pgn
from PyQt5.QtCore import QObject, pyqtSignal

from core.pgn_to_html import pgn_to_html


class MoveManager(QObject):
    pgnChanged = pyqtSignal(str)
    activeNodeChanged = pyqtSignal()

    def __init__(self, pgn_str: str | None = None):
        super().__init__()
        self.html, self.nodes = "", []
        self.html_style = False  # True for dark theme
        self.font_family = "sans-serif"
        self.game = chess.pgn.Game()
        self.is_dirty = False
        if pgn_str:
            self.update_pgn(pgn_str)
        self.current_node = self.game

    def load_fen(self, fen: str):
        self.game = chess.pgn.Game()
        board = chess.Board(fen)
        self.game.setup(board)
        self.current_node = self.game
        self.create_mapping()
        self.is_dirty = True

    def update_pgn(self, pgn_str: str):
        pgn_io = StringIO(pgn_str)
        game = chess.pgn.read_game(pgn_io)
        if game:
            self.game = game
            self.current_node = self.game
            self.create_mapping()
            self.is_dirty = True
            return
        self.game = chess.pgn.Game()
        self.current_node = self.game
        self.create_mapping()
        self.is_dirty = True

    def load_pgn_file(self, filename: str):
        with open(filename, "r") as f:
            game = chess.pgn.read_game(f)
        self.game = game
        self.current_node = self.game
        self.create_mapping()
        self.is_dirty = False

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
        self.is_dirty = True

    def undo(self):
        if self.current_node.parent:
            self.current_node = self.current_node.parent
            self.create_mapping()

    def get_current_node_variations(self):
        """Return a list of variations from the current node."""
        variations = {}
        for index, var in enumerate(self.current_node.variations):
            board = self.current_node.board()
            first_move_num = board.fullmove_number
            first_turn = board.turn
            first_san = board.san(var.move)
            
            if first_turn == chess.WHITE:
                first_move_formatted = f"{first_move_num}.{first_san}"
            else:
                first_move_formatted = f"{first_move_num}...{first_san}"
                
            board.push(var.move)
            
            continuation_formatted = []
            temp_node = var
            moves_shown = 1
            while moves_shown < 5 and temp_node.variations:
                next_node = temp_node.variations[0]
                san = board.san(next_node.move)
                turn = board.turn
                move_num = board.fullmove_number
                
                if turn == chess.WHITE:
                    continuation_formatted.append(f"{move_num}.{san}")
                else:
                    continuation_formatted.append(san)
                        
                board.push(next_node.move)
                temp_node = next_node
                moves_shown += 1
                
            if continuation_formatted:
                continuation_str = " ".join(continuation_formatted)
                line_str = f"{first_move_formatted} {continuation_str}"
            else:
                line_str = first_move_formatted

            variations[index] = {
                "uci": var.move.uci(),
                "san": first_san,
                "line": line_str
            }
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
        from datetime import date
        
        # Update headers if they are default or missing
        if self.game.headers.get("Event", "?") == "?":
            self.game.headers["Event"] = "Chess Analysis"
        
        if self.game.headers.get("Date", "????.??.??") == "????.??.??":
            self.game.headers["Date"] = date.today().strftime("%Y.%m.%d")
            
        return str(self.game)

    def create_mapping(self):
        self.html, self.nodes = pgn_to_html(self.game, self.current_node, self.html_style, self.font_family)
        # Emit empty string to avoid expensive PGN serialization during navigation
        self.pgnChanged.emit("")
        self.activeNodeChanged.emit()


    def add_comment(self, index: int, comment: str):
        node = self.get_node_by_index(index)
        node.comment = comment
        self.create_mapping()
        self.is_dirty = True

    def promote_to_main(self, index: int):
        node = self.get_node_by_index(index)
        parent = node.parent
        if parent:
            parent.promote_to_main(node)
            self.create_mapping()
            self.is_dirty = True

    def promote(self, index: int):
        node = self.get_node_by_index(index)
        parent = node.parent
        if parent:
            parent.promote(node)
            self.create_mapping()
            self.is_dirty = True

    def demote(self, index: int):
        node = self.get_node_by_index(index)
        parent = node.parent
        if parent:
            parent.demote(node)
            self.create_mapping()
            self.is_dirty = True

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
            self.is_dirty = True

    def change_html_style(self, html_style=False):
        self.html_style = html_style
        self.create_mapping()

    def clear(self):
        self.game = chess.pgn.Game()
        self.current_node = self.game
        self.create_mapping()
        self.is_dirty = False
