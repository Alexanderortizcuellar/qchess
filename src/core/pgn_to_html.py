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
    out = []
    
    if not game.variations:
        return []
        
    class Frame:
        def __init__(self, node, sidelines=True):
            self.node = node
            self.state = "pre"
            self.variations = iter(node.parent.variations[1:]) if sidelines else iter([])

    stack = [Frame(game.variations[0], sidelines=True)]
    
    while stack:
        top = stack[-1]
        
        if top.state == "pre":
            if top.node.move is not None:
                out.append(top.node)
            top.state = "variations"
            
        elif top.state == "variations":
            try:
                variation = next(top.variations)
            except StopIteration:
                if top.node.variations:
                    stack.append(Frame(top.node.variations[0], sidelines=True))
                    top.state = "post"
                else:
                    top.state = "end"
            else:
                stack.append(Frame(variation, sidelines=False))
                
        elif top.state == "post":
            top.state = "end"
            
        else:
            stack.pop()
            
    if annotate_index:
        for i, n in enumerate(out):
            n.flat_index = i
            
    return out


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
        highlight_index: Optional[int] = None,
        font_family: str = "sans-serif",
        nodes: Optional[List[chess.pgn.GameNode]] = None,
        show_classifications: bool = True,
    ):
        self.columns = columns
        self.headers = headers
        self.comments = comments
        self.variations = variations
        self.highlight_index = highlight_index
        self.font_family = font_family
        self.nodes = nodes
        self.show_classifications = show_classifications

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
        else:
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
            self.parts.append(f'<span class="cmt">{{{safe}}}</span> ')
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
            is_highlighted = self.move_index == self.highlight_index
            highlight_class = " highlight" if is_highlighted else ""
            
            import re
            node_cls = None
            if self.nodes and self.move_index < len(self.nodes):
                node = self.nodes[self.move_index]
                if node.comment:
                    alz_match = re.search(r'\[%alz\s+([^\]]+)\]', node.comment)
                    if alz_match:
                        cls_tokens = alz_match.group(1).split()
                        for token in cls_tokens:
                            if token.startswith("cls="):
                                try:
                                    node_cls = int(token.split("=")[1])
                                except ValueError:
                                    pass

            CLS_CLASS_MAP = {
                4: "cls-inaccuracy",
                5: "cls-mistake",
                6: "cls-blunder",
                7: "cls-brilliant",
                8: "cls-miss",
            }
            cls_class = ""
            if self.show_classifications and node_cls in CLS_CLASS_MAP:
                cls_class = f" {CLS_CLASS_MAP[node_cls]}"

            move_html = (
                f'<span class="move">'
                f'{prefix}<a id="m{self.move_index}" href="move({self.move_index})" class="mv{highlight_class}{cls_class}">{san}</a>'
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
        light_style = f"""
        <style>
            body {{ font-family: 'Segoe UI', Arial, sans-serif; font-size: 20px; }}
            .move {{display: inline; }}
            .num {{ color: #757575; font-weight: bold; margin-right: 2px; }}
            .mv {{ font-family: {self.font_family}; color: #1A1A1A; text-decoration: none; padding: 4px 2px; }}
            .mv:hover {{ background: #eef6ff; }}
            .mv.highlight {{ background: #dbeafe; }}
            .mv.cls-inaccuracy {{ color: #b58900; }}
            .mv.cls-mistake {{ color: #e65100; }}
            .mv.cls-blunder {{ color: #b71c1c; font-weight: bold; }}
            .mv.cls-brilliant {{ color: #28c2a4; font-weight: bold; }}
            .mv.cls-miss {{ color: #d32f2f; }}
            .cmt {{ color: #388E3C; font-style: italic; margin-left: 4px; }}
            .variation {{ color: #9aa0a6; }}
            .hdr {{ color: #555; font-family: monospace; }}
            .res {{ font-weight: bold; }}
        </style>
        """
        dark_style = f"""
            <style>
                body {{ background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI', Arial, sans-serif; font-size: 20px; line-height: 1.6; }}
                .move {{ display: inline; }}
                .num {{ color: #9E9E9E; font-weight: bold; margin-right: 2px; }}
                .mv {{ font-family: {self.font_family}; color: #BB86FC; text-decoration: none; padding: 4px 2px; }}
                .mv:hover {{ background: #2A2A2A; }}
                .mv.highlight {{ background: #1a365d; }}
                .mv.cls-inaccuracy {{ color: #ffd54f; }}
                .mv.cls-mistake {{ color: #ffa726; }}
                .mv.cls-blunder {{ color: #ff5252; font-weight: bold; }}
                .mv.cls-brilliant {{ color: #28c2a4; font-weight: bold; }}
                .mv.cls-miss {{ color: #ff8a80; }}
                .cmt {{ color: #03DAC6; font-style: italic; margin-left: 4px; }}
                .variation {{ color: #B0BEC5; font-style: italic; }}
                .hdr {{ color: #8D99AE; font-family: monospace; }}
                .res {{ color: #FFB74D; font-weight: bold; }}
            </style>
            """


        style = dark_style if self.dark_mode else light_style
        return style + "<div class='moves'>" + " ".join(self.parts) + "</div>"

    def __str__(self) -> str:
        return self.result()

    def set_style(self, is_dark_style: bool):
        self.dark_mode = is_dark_style


def pgn_to_html(game: chess.pgn.Game, highlight_node: Optional[chess.pgn.GameNode] = None, style: bool = False, font_family: str = "sans-serif", show_classifications: bool = True):
    nodes = flatten_nodes_pgn_order(game)
    highlight_index = None
    if highlight_node is not None:
        highlight_index = getattr(highlight_node, "flat_index", None)
        
    exporter = HtmlExporter(variations=True, comments=True, headers=False, highlight_index=highlight_index, font_family=font_family, nodes=nodes, show_classifications=show_classifications)
    exporter.set_style(style)
    data = game.accept(exporter)
    return data, nodes

