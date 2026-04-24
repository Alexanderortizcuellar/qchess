import html
from typing import List, Optional

import chess.pgn


def flatten_nodes_pgn_order(
    game: chess.pgn.Game, annotate_index: bool = True
) -> List[chess.pgn.GameNode]:
    """
    Returns all move nodes of `game` flattened in the exact order a PGN exporter
    would print them (mainline with variations interleaved at the right spots).

    If `annotate_index` is True, attaches `node.flat_index = i` to each node.
    """

    class _Collector(chess.pgn.BaseVisitor[None]):
        def __init__(self, root: chess.pgn.Game):
            self.root = root
            # Stack tracks the "current position node" as accept() walks the tree
            # (same idea as GameBuilder.variation_stack).
            self.stack: List[chess.pgn.GameNode] = []
            self.out: List[chess.pgn.GameNode] = []

        def begin_game(self) -> None:
            self.stack = [self.root]

        def begin_variation(self) -> None:
            # python-chess jumps back to the branch point (parent of current node)
            # before descending into a side variation.
            parent = self.stack[-1].parent
            assert parent is not None, "begin_variation at root is invalid"
            self.stack.append(parent)

        def end_variation(self) -> None:
            self.stack.pop()

        def visit_move(self, board: chess.Board, move: chess.Move) -> None:
            # Current parent position:
            parent = self.stack[-1]

            # Find the child node under `parent` that corresponds to `move`.
            # Use both object equality and UCI as a robust fallback.
            found: Optional[chess.pgn.GameNode] = None
            u = move.uci()
            for child in parent.variations:
                if child.move == move or child.move.uci() == u:
                    found = child
                    break

            if found is None:
                # This should not happen unless the tree is inconsistent.
                raise RuntimeError("Could not map visitor move to a tree node.")

            # Record node in PGN order and advance the stack to that node.
            self.out.append(found)
            self.stack[-1] = found

        def result(self) -> None:
            # We don't need to return anything here; we'll read self.out.
            return None

    collector = _Collector(game)
    game.accept(collector)

    if annotate_index:
        for i, n in enumerate(collector.out):
            setattr(n, "flat_index", i)  # attach a handy index for later use

    return collector.out


class HtmlExporterMixin:
    def __init__(
        self,
        *,
        columns: Optional[
            int
        ] = None,  # not needed for HTML, but kept for compatibility
        headers: bool = True,
        comments: bool = True,
        variations: bool = True,
    ):
        self.columns = columns
        self.headers = headers
        self.comments = comments
        self.variations = variations

        self.force_movenumber = True
        self.variation_depth = 0
        self.move_index = 0
        self.parts: List[str] = []

    def flush_current_line(self) -> None:
        # HTML doesn’t wrap lines, so noop
        pass

    def write_token(self, token: str) -> None:
        self.parts.append(token)

    def write_line(self, line: str = "") -> None:
        # In HTML we just separate with <br> if needed
        if line:
            self.parts.append(f"<div>{html.escape(line)}</div>")
            print(line)
        else:
            print("not in a line")
            self.parts.append("<br>")

    def end_game(self) -> None:
        pass

    def begin_headers(self) -> None:
        self.found_headers = False

    def visit_header(self, tagname: str, tagvalue: str) -> None:
        if self.headers:
            self.parts.append(
                f'<div class="hdr">[{tagname} "{html.escape(tagvalue)}"]</div>'
            )

    def end_headers(self) -> None:
        if self.headers:
            self.parts.append("<br>")

    def begin_variation(self):
        self.variation_depth += 1
        if self.variations:
            self.parts.append("<br>")
            self.parts.append('<span class="variation">( ')
            self.force_movenumber = True
        else:
            return chess.pgn.SKIP

    def end_variation(self):
        self.variation_depth -= 1
        if self.variations:
            self.parts.append(" )</span>")
            self.parts.append("<br>")
            self.force_movenumber = True

    def visit_comment(self, comment: str) -> None:
        if self.comments and (self.variations or not self.variation_depth):
            safe = html.escape(comment.replace("}", "").strip())
            self.parts.append(f'<span class="cmt">{safe}</span> ')
            self.force_movenumber = True

    def visit_nag(self, nag: int) -> None:
        if self.comments and (self.variations or not self.variation_depth):
            self.parts.append(f'<span class="nag">${nag}</span> ')

    def visit_move(self, board: chess.Board, move: chess.Move) -> None:
        if self.variations or not self.variation_depth:
            move_number = board.fullmove_number

            prefix = ""
            if board.turn == chess.WHITE:
                prefix = f'<span class="num">{move_number}.</span> '
            elif self.force_movenumber:
                prefix = f'<span class="num">{move_number}...</span> '

            san = html.escape(board.san(move))

            # use current index as ID and href
            move_html = (
                f'<span class="move">'
                f'{prefix}<a id="m{self.move_index}" href="move({self.move_index})" class="mv">{san}</a>'
                f"</span>"
            )
            self.parts.append(move_html)

            # increment move index
            self.move_index += 1
            self.force_movenumber = False

    def visit_result(self, result: str) -> None:
        if result == "*":
            return
        self.parts.append(f'<span class="res">{result}</span> ')


class HtmlExporter(HtmlExporterMixin, chess.pgn.BaseVisitor[str]):
    def result(self) -> str:
        light_style = """
        <style>
        .move {display: inline; }
            .num { color: #757575; font-weight: bold; margin-right: 2px; }
            .mv { color: #1A1A1A; text-decoration: none; padding: 0 2px; }
            .mv:hover { background: #eef6ff; }
            .cmt { color: #388E3C; font-style: italic; margin-left: 4px; }
            .variation { color: #9aa0a6; }
            .hdr { color: #555; font-family: monospace; }
            .res { font-weight: bold; }
        </style>
        """
        dark_style = """
            <style>
                body { background-color: #121212; color: #E0E0E0; font-family: sans-serif; }
                .move { display: inline; }
                .num { color: #9E9E9E; font-weight: bold; margin-right: 2px; }
                .mv { color: #BB86FC; text-decoration: none; padding: 0 2px; }
                .mv:hover { background: #2A2A2A; border-radius: 3px; }
                .cmt { color: #03DAC6; font-style: italic; margin-left: 4px; }
                .variation { color: #B0BEC5; font-style: italic; }
                .hdr { color: #8D99AE; font-family: monospace; }
                .res { color: #FFB74D; font-weight: bold; }
            </style>
            """

        style = dark_style if self.dark_mode else light_style
        return style + "<div class='moves'>" + " ".join(self.parts) + "</div>"

    def __str__(self) -> str:
        return self.result()

    def set_style(self, is_dark_style: bool):
        self.dark_mode = is_dark_style


def pgn_to_html(game: chess.pgn.Game, style: bool = False):
    exporter = HtmlExporter(variations=True, comments=True, headers=False)
    exporter.set_style(style)
    data = game.accept(exporter)
    nodes = flatten_nodes_pgn_order(game)
    return data, nodes
