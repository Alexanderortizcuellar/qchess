import re
from typing import Dict, List, Tuple, Union, Optional
import chess
import chess.pgn

# Color mappings for standard PGN annotations ([%cal ...] and [%csl ...])
COLOR_MAP = {
    "G": "rgba(21, 128, 61, 0.7)",    # Green
    "R": "rgba(220, 38, 38, 0.7)",    # Red
    "Y": "rgba(234, 179, 8, 0.7)",    # Yellow
    "B": "rgba(37, 99, 235, 0.7)",    # Blue
    "O": "rgba(249, 115, 22, 0.7)",   # Orange
    "C": "rgba(6, 182, 212, 0.7)",    # Cyan
    "M": "rgba(168, 85, 247, 0.7)",   # Magenta / Purple
    "W": "rgba(255, 255, 255, 0.7)",  # White
    "K": "rgba(0, 0, 0, 0.7)",        # Black
}

COLOR_NAME_MAP = {
    "green": COLOR_MAP["G"],
    "red": COLOR_MAP["R"],
    "yellow": COLOR_MAP["Y"],
    "blue": COLOR_MAP["B"],
    "orange": COLOR_MAP["O"],
    "cyan": COLOR_MAP["C"],
    "magenta": COLOR_MAP["M"],
    "purple": COLOR_MAP["M"],
    "white": COLOR_MAP["W"],
    "black": COLOR_MAP["K"],
}

DEFAULT_COLOR = COLOR_MAP["G"]


def resolve_color(color_spec: Optional[str]) -> str:
    """Resolve color specification (single letter, name, or rgba/hex string) to RGBA."""
    if not color_spec:
        return DEFAULT_COLOR
    color_clean = color_spec.strip()
    if len(color_clean) == 1 and color_clean.upper() in COLOR_MAP:
        return COLOR_MAP[color_clean.upper()]
    lower_color = color_clean.lower()
    if lower_color in COLOR_NAME_MAP:
        return COLOR_NAME_MAP[lower_color]
    if color_clean.startswith("rgba") or color_clean.startswith("#") or color_clean.startswith("rgb"):
        return color_clean
    return DEFAULT_COLOR


def parse_pgn_shapes(comment: Optional[str]) -> Tuple[List[dict], Dict[chess.Square, str]]:
    """
    Parses [%cal ...] (color arrows) and [%csl ...] (color squares/circles) from a PGN comment string.

    Returns:
        tuple (shapes, highlights):
            shapes: list of dicts suitable for gchessboard (type="arrow" | "circle", orig, dest, color, width)
            highlights: dict mapping chess.Square -> color string
    """
    shapes: List[dict] = []
    highlights: Dict[chess.Square, str] = {}

    if not comment:
        return shapes, highlights

    # Match [%cal ...] or [%csl ...]
    tag_regex = re.compile(r"\[%(cal|csl)\s+([^\]]+)\]", re.IGNORECASE)

    for match in tag_regex.finditer(comment):
        tag_type = match.group(1).lower()
        items_str = match.group(2).strip()
        items = [item.strip() for item in items_str.split(",") if item.strip()]

        for item in items:
            if tag_type == "cal":
                # Arrow format: e.g. Ge2e4, Re4e5, g1f3, ye2e4
                m = re.match(r"^([A-Za-z]?)([a-h][1-8])([a-h][1-8])$", item)
                if m:
                    col_char = m.group(1)
                    color = resolve_color(col_char)
                    try:
                        orig_sq = chess.parse_square(m.group(2).lower())
                        dest_sq = chess.parse_square(m.group(3).lower())
                        shapes.append({
                            "type": "arrow",
                            "orig": orig_sq,
                            "dest": dest_sq,
                            "color": color,
                            "width": 4.0,
                        })
                    except ValueError:
                        continue
            elif tag_type == "csl":
                # Square / Circle format: e.g. Ge4, Rd4, e4, Yc3
                m = re.match(r"^([A-Za-z]?)([a-h][1-8])$", item)
                if m:
                    col_char = m.group(1)
                    color = resolve_color(col_char)
                    try:
                        sq = chess.parse_square(m.group(2).lower())
                        shapes.append({
                            "type": "circle",
                            "orig": sq,
                            "color": color,
                            "width": 4.0,
                        })
                        highlights[sq] = color
                    except ValueError:
                        continue

    return shapes, highlights


def extract_node_shapes(node: Optional[chess.pgn.GameNode]) -> Tuple[List[dict], Dict[chess.Square, str]]:
    """
    Extracts all arrow shapes and square highlights from a chess.pgn node.
    """
    if node is None:
        return [], {}

    comment = getattr(node, "comment", "")
    shapes, highlights = parse_pgn_shapes(comment)

    # Fallback / merge with python-chess node.arrows() if any arrows were parsed by python-chess
    # that weren't captured by the regex (e.g. if custom node arrow objects were added)
    if hasattr(node, "arrows"):
        try:
            node_arrows = node.arrows()
            for arrow in node_arrows:
                tail = arrow.tail
                head = arrow.head
                color = resolve_color(arrow.color)
                if tail != head:
                    # Arrow
                    exists = any(
                        s.get("type") == "arrow"
                        and s.get("orig") == tail
                        and s.get("dest") == head
                        for s in shapes
                    )
                    if not exists:
                        shapes.append({
                            "type": "arrow",
                            "orig": tail,
                            "dest": head,
                            "color": color,
                            "width": 4.0,
                        })
                else:
                    # Circle / square
                    exists = any(
                        s.get("type") == "circle" and s.get("orig") == tail
                        for s in shapes
                    )
                    if not exists:
                        shapes.append({
                            "type": "circle",
                            "orig": tail,
                            "color": color,
                            "width": 4.0,
                        })
                    if tail not in highlights:
                        highlights[tail] = color
        except Exception:
            pass

    return shapes, highlights


def export_pgn_shapes(
    shapes: Optional[List[Union[dict, object]]] = None,
    highlights: Optional[Dict[chess.Square, str]] = None,
) -> str:
    """
    Converts shapes and highlights into [%cal ...] and [%csl ...] PGN tag strings.
    """
    cal_tokens = []
    csl_tokens = []

    # Map rgba back to primary color letter
    def get_color_char(col_str: str) -> str:
        for letter, rgba in COLOR_MAP.items():
            if rgba == col_str:
                return letter
        for name, rgba in COLOR_NAME_MAP.items():
            if name in col_str.lower():
                return name[0].upper()
        return "G"

    if shapes:
        for s in shapes:
            s_type = getattr(s, "type", None) if not isinstance(s, dict) else s.get("type")
            s_orig = getattr(s, "orig", None) if not isinstance(s, dict) else s.get("orig")
            s_dest = getattr(s, "dest", None) if not isinstance(s, dict) else s.get("dest")
            s_color = getattr(s, "color", "rgba(21, 128, 61, 0.7)") if not isinstance(s, dict) else s.get("color", "rgba(21, 128, 61, 0.7)")

            orig_sq = chess.parse_square(s_orig) if isinstance(s_orig, str) else s_orig
            dest_sq = chess.parse_square(s_dest) if isinstance(s_dest, str) else s_dest

            c_letter = get_color_char(s_color)

            if s_type == "arrow" and orig_sq is not None and dest_sq is not None:
                cal_tokens.append(f"{c_letter}{chess.square_name(orig_sq)}{chess.square_name(dest_sq)}")
            elif s_type == "circle" and orig_sq is not None:
                csl_tokens.append(f"{c_letter}{chess.square_name(orig_sq)}")

    if highlights:
        for sq, col in highlights.items():
            parsed_sq = chess.parse_square(sq) if isinstance(sq, str) else sq
            c_letter = get_color_char(col)
            token = f"{c_letter}{chess.square_name(parsed_sq)}"
            if token not in csl_tokens:
                csl_tokens.append(token)

    tags = []
    if cal_tokens:
        tags.append(f"[%cal {','.join(cal_tokens)}]")
    if csl_tokens:
        tags.append(f"[%csl {','.join(csl_tokens)}]")

    return " ".join(tags)
