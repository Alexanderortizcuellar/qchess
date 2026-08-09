import os
from io import StringIO
import chess
import chess.pgn

def save_game_to_pgn(game: chess.pgn.Game, pgn_path: str, offset: int = None, length: int = None):
    """
    Saves or updates a game inside the target PGN file.
    If offset (and length) is provided, seeks directly to it, validates
    that the chunk is a valid game as a safety check, and replaces the byte range.
    Otherwise, falls back to matching by headers (Event, Site, Date, Round, White, Black).
    """
    updated = False

    if offset is not None and length is not None and os.path.exists(pgn_path):
        try:
            with open(pgn_path, "rb") as f:
                content = f.read()
            
            # Check if the offset and length are within file bounds
            if 0 <= offset < len(content) and offset + length <= len(content):
                chunk = content[offset:offset+length]
                try:
                    chunk_str = chunk.decode("utf-8")
                except UnicodeDecodeError:
                    chunk_str = chunk.decode("latin-1", errors="ignore")
                
                # Check if it parses as a valid game to verify file/index consistency
                target_g = chess.pgn.read_game(StringIO(chunk_str))
                if target_g is not None:
                    # Format the new game
                    new_pgn_io = StringIO()
                    exporter = chess.pgn.FileExporter(new_pgn_io)
                    game.accept(exporter)
                    new_pgn_str = new_pgn_io.getvalue().rstrip() + "\n\n"
                    new_pgn_bytes = new_pgn_str.encode("utf-8")
                    
                    new_content = content[:offset] + new_pgn_bytes + content[offset+length:]
                    with open(pgn_path, "wb") as f:
                        f.write(new_content)
                    
                    updated = True
        except Exception as e:
            print(f"Direct offset replacement failed: {e}")

    if not updated:
        # Fallback to loading all games and matching by metadata
        existing_games = []
        if os.path.exists(pgn_path) and os.path.getsize(pgn_path) > 0:
            try:
                with open(pgn_path, "r", encoding="utf-8") as f:
                    while True:
                        g = chess.pgn.read_game(f)
                        if g is None:
                            break
                        existing_games.append(g)
            except UnicodeDecodeError:
                try:
                    with open(pgn_path, "r", encoding="latin-1") as f:
                        while True:
                            g = chess.pgn.read_game(f)
                            if g is None:
                                break
                            existing_games.append(g)
                except Exception as e:
                    print(f"Error reading existing games: {e}")
            except Exception as e:
                print(f"Error reading existing games: {e}")

        # Metadata-based fallback
        new_event = game.headers.get("Event", "?")
        new_site = game.headers.get("Site", "?")
        new_date = game.headers.get("Date", "????.??.??")
        new_round = game.headers.get("Round", "?")
        new_white = game.headers.get("White", "?")
        new_black = game.headers.get("Black", "?")

        fallback_updated = False
        for idx, g in enumerate(existing_games):
            if (g.headers.get("Event") == new_event and
                g.headers.get("Site") == new_site and
                g.headers.get("Date") == new_date and
                g.headers.get("Round") == new_round and
                g.headers.get("White") == new_white and
                g.headers.get("Black") == new_black):
                existing_games[idx] = game
                fallback_updated = True
                break

        if not fallback_updated:
            existing_games.append(game)

        # Write all games back to file
        with open(pgn_path, "w", encoding="utf-8") as f:
            for g in existing_games:
                exporter = chess.pgn.FileExporter(f)
                g.accept(exporter)
                f.write("\n\n")

