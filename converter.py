import json
import re
from typing import Any, Dict, List, Tuple

# Basic SAN move parser (very simplified)
move_regex = re.compile(
    r"(?P<fig>[KQRBN])?(?P<strike>x)?(?P<col>[a-h])(?P<row>[1-8])(?:=(?P<promotion>[QRBN]))?(?P<check>[+#])?"
)
move_id = 0


def parse_san(san: str) -> Dict[str, Any]:
    m = move_regex.match(san)
    return (
        {
            "fig": m.group("fig"),
            "strike": m.group("strike"),
            "col": m.group("col"),
            "row": m.group("row"),
            "check": m.group("check"),
            "promotion": m.group("promotion"),
            "notation": san,
        }
        if m
        else {"notation": san}
    )


def parse_pgn_tokens(tokens: List[str], turn: str = "w") -> Tuple[List[Dict], int]:
    global move_id
    moves = []
    i = 0
    move_number = None
    comment = None

    while i < len(tokens):
        token = tokens[i]
        if token.startswith("{"):  # Comment
            comment = token.strip("{} ").strip()
            if moves:
                moves[-1]["commentDiag"] = comment
            i += 1
            continue

        if token.endswith("."):  # Move number
            try:
                move_number = int(token.strip("."))
            except ValueError:
                print("err")
                move_number = None
            i += 1
            continue

        if token == "(":  # Start variation
            variation, consumed = parse_pgn_tokens(tokens[i + 1 :], turn)
            if moves:
                moves[-1]["variations"].append(variation)
            i += consumed + 2  # skip '(' and ')'
            continue

        if token == ")":  # End variation
            return moves, i

        if token.startswith("$"):  # NAG
            if moves:
                moves[-1]["nag"] = token
            i += 1
            continue

        move_id += 1
        # Regular move
        moves.append(
            {
                "moveId": move_id,
                "moveNumber": move_number,  # if turn == "w" else None,
                "notation": parse_san(token),
                "variations": [],
                "nag": None,
                "commentDiag": None,
                "turn": turn,
            }
        )
        turn = "b" if turn == "w" else "w"
        i += 1

    return moves, i


def tokenize_pgn(pgn: str) -> List[str]:
    # Split PGN into tokens: moves, comments, parentheses, NAGs
    tokens = re.findall(r"\(|\)|\{[^}]*\}|\$[0-9]+|\d+\.+|\S+", pgn)
    print(tokens)
    return tokens


def split_headers_and_moves(pgn_text: str):
    lines = pgn_text.strip().splitlines()
    headers = {}
    move_lines = []
    in_headers = True

    for line in lines:
        line = line.strip()
        if not line:  # empty line — headers end
            in_headers = False
            continue

        if in_headers:
            # Parse header line like [Key "Value"]
            if line.startswith("[") and line.endswith("]"):
                key_value = line[1:-1].split(" ", 1)
                key = key_value[0]
                value = key_value[1].strip('"') if len(key_value) > 1 else ""
                headers[key] = value
        else:
            move_lines.append(line)

    moves_str = " ".join(move_lines)
    return headers, moves_str


# Example PGN with variation
pgn_text = """
[Event "?"]
[Site "?"]
[Date "????.??.??"]
[Round "?"]
[White "?"]
[Black "?"]
[Result "*"]
[Link "https://www.chess.com/analysis"]


1. e4 {This is a strong opening move} e5 2. Nf3 Nc6 3. Bc4  Nf6 4. d3 (4. Ng5 d5 5. exd5 Nxd5 (5... Na5 6. Bb5+
c6 7. dxc6 bxc6 8. Bd3 (8. Be2 h6 9. Nf3) 8... Nd5) 6. Nxf7 Kxf7 7. Qf3+ Ke6 8.
Nc3 Nb4 9. O-O c6) 4... Bc5 5. O-O *
"""
data = {}
headers, moves = split_headers_and_moves(pgn_text)
tokens = tokenize_pgn(moves)
moves, _ = parse_pgn_tokens(tokens)
data["headers"] = headers
data["moves"] = moves


with open("data.json", "w") as f:
    json.dump(data, f, indent=2)
