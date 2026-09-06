from io import StringIO

import chess
import chess.pgn
from PyQt5.QtCore import QObject, pyqtSignal

from core.pgn_to_html import flatten_nodes_pgn_order
from core.pgn_annotations import extract_node_shapes, parse_pgn_shapes


MOVE_EVAL_NAGS = {
    1: "Good move (!)",
    2: "Poor or mistake move (?)",
    3: "Excellent or brilliant move (!!)",
    4: "Blunder (??)",
    5: "Interesting move (!?)",
    6: "Dubious move (?!)",
    9: "Miss",
}

POS_EVAL_NAGS = {
    10: "Equal position (=)",
    14: "White has a slight advantage (+=)",
    15: "Black has a slight advantage (=+)",
    16: "White has a moderate advantage (+/-)",
    17: "Black has a moderate advantage (-/+)",
    18: "White has a decisive advantage (+-)",
    19: "Black has a decisive advantage (-+)",
}

NAG_MOVE_SYMBOLS = {
    1: "!",
    2: "?",
    3: "!!",
    4: "??",
    5: "!?",
    6: "?!",
}

NAG_POS_SYMBOLS = {
    10: "=",
    14: "+=",
    15: "=+",
    16: "+/-",
    17: "-/+",
    18: "+-",
    19: "-+",
}

NAG_TO_CLS = {
    1: 1,  # Great / Good (!)
    2: 5,  # Mistake (?)
    3: 7,  # Brilliant (!!)
    4: 6,  # Blunder (??)
    5: 2,  # Interesting (!?)
    6: 4,  # Inaccuracy (?!)
    9: 8,  # Miss
}


def format_san_with_nags(san: str, nags) -> str:
    if not nags:
        return san
    move_suffix = ""
    for n in sorted(nags):
        if n in NAG_MOVE_SYMBOLS:
            move_suffix = NAG_MOVE_SYMBOLS[n]
            break
    pos_suffix = ""
    for n in sorted(nags):
        if n in NAG_POS_SYMBOLS:
            pos_suffix = f" {NAG_POS_SYMBOLS[n]}"
            break
    return f"{san}{move_suffix}{pos_suffix}"


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

    def _auto_set_result(self):
        """Auto-detect result if game is over / ended in checkmate and Result header is missing or '*'."""
        res_header = self.game.headers.get("Result", "*")
        if res_header in ("*", "?", "", None):
            end_node = self.game
            while end_node.variations:
                end_node = end_node.variations[0]
            board = end_node.board()
            if board.is_checkmate():
                self.game.headers["Result"] = board.result()
            elif board.is_game_over():
                self.game.headers["Result"] = board.result()

    def load_fen(self, fen: str):
        self.game = chess.pgn.Game()
        board = chess.Board(fen)
        self.game.setup(board)
        self.current_node = self.game
        self._auto_set_result()
        self.create_mapping()
        self.is_dirty = True

    def cache_node_metadata(self, game_node):
        """Traverse game tree once and cache san, move_number, and turn on every node."""
        stack = [(game_node, game_node.board())]
        while stack:
            parent_node, board = stack.pop()
            for var in parent_node.variations:
                b_copy = board.copy(stack=False)
                san = b_copy.san(var.move)
                var.san = san
                var.move_number = b_copy.fullmove_number
                var.turn = b_copy.turn
                b_copy.push(var.move)
                stack.append((var, b_copy))

    def update_pgn(self, pgn_str: str):
        pgn_io = StringIO(pgn_str)
        game = chess.pgn.read_game(pgn_io)
        if game:
            self.game = game
            self.cache_node_metadata(self.game)
            self._auto_set_result()
            self.current_node = self.game
            self.create_mapping()
            self.is_dirty = True
            return
        self.game = chess.pgn.Game()
        self.current_node = self.game
        self.create_mapping()
        self.is_dirty = True

    def load_pgn_file(self, filename: str):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                game = chess.pgn.read_game(f)
        except UnicodeDecodeError:
            with open(filename, "r", encoding="latin-1") as f:
                game = chess.pgn.read_game(f)
        self.game = game
        self.cache_node_metadata(self.game)
        self._auto_set_result()
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

        # Compute SAN while board is active at current position
        board = self.current_node.board()
        san = board.san(move)
        move_number = board.fullmove_number
        turn = board.turn

        # Otherwise, create new variation and cache SAN
        temp_node = self.current_node.add_variation(move)
        temp_node.san = san
        temp_node.move_number = move_number
        temp_node.turn = turn

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

    def get_current_shapes_and_highlights(self):
        """Extract shapes and highlights for the current active node."""
        return extract_node_shapes(self.current_node)

    def get_node_shapes_and_highlights(self, index: int):
        """Extract shapes and highlights for a node at the given index."""
        node = self.get_node_by_index(index)
        return extract_node_shapes(node)

    def to_dict(self):
        "Not Implemented yet"
        pass

    def get_pgn(self):
        from datetime import date
        
        self._auto_set_result()

        # Update headers if they are default or missing
        if self.game.headers.get("Event", "?") == "?":
            self.game.headers["Event"] = "Chess Analysis"
        
        if self.game.headers.get("Date", "????.??.??") == "????.??.??":
            self.game.headers["Date"] = date.today().strftime("%Y.%m.%d")
            
        return str(self.game)

    def create_mapping(self):
        self.html = ""
        self.nodes = flatten_nodes_pgn_order(self.game)
        # Emit empty string to avoid expensive PGN serialization during navigation
        self.pgnChanged.emit("")
        self.activeNodeChanged.emit()


    def add_comment(self, index: int, comment: str):
        node = self.get_node_by_index(index)
        node.comment = comment
        self.create_mapping()
        self.is_dirty = True

    def set_eval_annotation(self, index: int, eval_str: str):
        """Add or update [%eval ...] tag in the node's comment."""
        node = self.get_node_by_index(index)
        if not node:
            return
        eval_clean = eval_str.replace("[%eval", "").replace("]", "").strip()
        eval_tag = f"[%eval {eval_clean}]"
        if node.comment:
            if re.search(r'\[%eval\s+[^\]]+\]', node.comment):
                node.comment = re.sub(r'\[%eval\s+[^\]]+\]', eval_tag, node.comment)
            else:
                node.comment = f"{node.comment.strip()} {eval_tag}".strip()
        else:
            node.comment = eval_tag
        self.create_mapping()
        self.is_dirty = True

    def set_move_nag(self, index: int, nag: int):
        node = self.get_node_by_index(index)
        if not hasattr(node, "nags"):
            node.nags = set()
        if nag in node.nags:
            node.nags.remove(nag)
        else:
            for m_nag in list(MOVE_EVAL_NAGS.keys()) + [9]:
                node.nags.discard(m_nag)
            node.nags.add(nag)
        self.create_mapping()
        self.is_dirty = True

    def set_pos_nag(self, index: int, nag: int):
        node = self.get_node_by_index(index)
        if not hasattr(node, "nags"):
            node.nags = set()
        if nag in node.nags:
            node.nags.remove(nag)
        else:
            for p_nag in POS_EVAL_NAGS.keys():
                node.nags.discard(p_nag)
            node.nags.add(nag)
        self.create_mapping()
        self.is_dirty = True

    def clear_nags(self, index: int):
        node = self.get_node_by_index(index)
        if hasattr(node, "nags"):
            node.nags.clear()
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
