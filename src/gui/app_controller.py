from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon

from gui.home_window import HomeWindow
from gui.app import ChessApp


class ApplicationController(QObject):
    """Coordinates the application's two-window architecture.

    Responsibilities:
        - Creates and manages the HomeWindow (database browser).
        - Creates and reuses the GameEditorWindow (ChessApp).
        - Routes "Open Game" requests from HomeWindow to the editor.
        - Routes "Open Repertoire" requests from the Repertoire Manager to the editor.
        - Persists repertoire changes back through the Repertoire Manager.
        - Manages shared application state.

    Communication flow:
        HomeWindow ── emits ──► gameSelected(dict)
        ApplicationController ──► editor.load_game_from_dict(dict)

        HomeWindow.repertoire_tree ── emits ──► repertoireOpenRequested(node_id, pgn)
        ApplicationController ──► editor (loads PGN, remembers node_id)

        editor ── emits ──► gameSaved(path, offset, length)
        ApplicationController ──► if repertoire mode: home.repertoire_tree.on_repertoire_saved(node_id, pgn)
                               ──► else: trigger PGN file reindex
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editor = None  # Lazy-created GameEditorWindow (ChessApp)
        self._pending_reindex_game_idx = None

        # When editing a repertoire, stores the node_id so saves route correctly.
        self._active_repertoire_node_id: int | None = None

        # Create the home window
        self.home = HomeWindow()

        # Connect signals
        self.home.gameSelected.connect(self._on_game_selected)
        self.home.openEditorRequested.connect(self._on_open_editor_requested)
        self.home.indexer.finishedSuccessfully.connect(self._on_indexing_finished_successfully)
        self.home.repertoireOpenRequested.connect(self._on_repertoire_open_requested)

    def show(self):
        """Show the home window (main entry point)."""
        self.home.show()

    def set_icon(self, icon: QIcon):
        """Set the window icon on all managed windows."""
        self.home.setWindowIcon(icon)
        if self._editor:
            self._editor.setWindowIcon(icon)

    def set_style(self, style_name: str):
        """Apply a style/theme to all managed windows."""
        self.home.set_theme(style_name == "dark")
        if self._editor:
            self._editor.set_style(style_name)

    # ──────────────────────── Signal Handlers ────────────────────────

    def _on_game_selected(self, game_data: dict):
        """Handle a game selection from HomeWindow."""
        editor = self._get_or_create_editor()
        pgn_text = game_data.get("PGN", "")

        # Switching to a regular game — clear repertoire context
        self._active_repertoire_node_id = None

        if pgn_text:
            editor.current_pgn_path = game_data.get("_pgn_path")
            editor.current_pgn_offset = game_data.get("_offset")
            editor.current_pgn_length = game_data.get("_length")
            editor.move_manager.update_pgn(pgn_text)
            editor.move_manager.is_dirty = False
            editor.display_pgn()
            editor.chessboard.update_board(editor.move_manager.get_board().fen())

            # Update window title with game info
            white = game_data.get("White", "?")
            black = game_data.get("Black", "?")
            editor.setWindowTitle(f"Chess App — {white} vs {black}")

        # Bring editor to foreground
        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _on_repertoire_open_requested(self, node_id: int, pgn_text: str):
        """Handle a repertoire open request from the Repertoire Manager.

        Opens (or reuses) the Chess Analyzer with the repertoire's PGN.
        Remembers the node_id so that gameSaved routes back to the DB.
        """
        editor = self._get_or_create_editor()
        self._active_repertoire_node_id = node_id

        # Clear PGN file coordinates — this is a DB-backed repertoire
        editor.current_pgn_path = None
        editor.current_pgn_offset = None
        editor.current_pgn_length = None

        if pgn_text.strip():
            editor.move_manager.update_pgn(pgn_text)
        else:
            # Empty repertoire: start with a blank game
            editor.move_manager.update_pgn("")

        editor.move_manager.is_dirty = False
        editor.display_pgn()
        editor.chessboard.update_board(editor.move_manager.get_board().fen())

        # Find the node name for the title
        node = self.home.repertoire_tree._repo.get_node(node_id)
        title = node.name if node else f"Repertoire #{node_id}"
        editor.setWindowTitle(f"QChess — {title}")

        editor.show()
        editor.raise_()
        editor.activateWindow()

    def _on_game_saved(self, pgn_path: str, old_offset, old_length):
        """Handle a game save notification from the editor.

        If we are in repertoire mode (active_repertoire_node_id is set),
        persist the PGN to the database instead of triggering a PGN reindex.
        """
        if self._active_repertoire_node_id is not None:
            # Repertoire mode: save PGN back to the DB
            try:
                pgn_text = self._editor.move_manager.get_pgn()
            except Exception:
                pgn_text = ""
            self.home.repertoire_tree.on_repertoire_saved(
                self._active_repertoire_node_id, pgn_text
            )
            return

        # Regular PGN file mode
        import os
        import sqlite3

        self._pending_reindex_game_idx = None
        if old_offset is not None:
            conn = None
            try:
                db_path = pgn_path + ".db"
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM games WHERE offset < ?", (old_offset,))
                    self._pending_reindex_game_idx = cursor.fetchone()[0]
            except Exception as e:
                print(f"Error getting game index before reindexing: {e}")
                self._pending_reindex_game_idx = None
            finally:
                if conn:
                    conn.close()

        # Trigger reindexing in HomeWindow
        self.home.load_pgn_path(pgn_path)

    def _on_indexing_finished_successfully(self, db_path: str):
        """Handle successful reindexing completion and update the editor window's game coordinates."""
        if self._editor and self._editor.isVisible():
            import sqlite3
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                row = None

                if self._pending_reindex_game_idx is not None:
                    # Query by the 0-based index we found before reindexing
                    cursor.execute("SELECT offset, length FROM games ORDER BY offset LIMIT 1 OFFSET ?", (self._pending_reindex_game_idx,))
                    row = cursor.fetchone()

                if not row:
                    # Fallback matching by headers if index is not found or not available
                    white = self._editor.move_manager.game.headers.get("White", "?")
                    black = self._editor.move_manager.game.headers.get("Black", "?")
                    event = self._editor.move_manager.game.headers.get("Event", "?")
                    date = self._editor.move_manager.game.headers.get("Date", "????.??.??")

                    cursor.execute("""
                        SELECT g.offset, g.length
                        FROM games g
                        LEFT JOIN players pw ON g.white_id = pw.id
                        LEFT JOIN players pb ON g.black_id = pb.id
                        LEFT JOIN events e ON g.event_id = e.id
                        WHERE pw.name = ? AND pb.name = ? AND e.name = ? AND g.date = ?
                    """, (white, black, event, date))
                    row = cursor.fetchone()

                if row:
                    new_offset, new_length = row
                    self._editor.current_pgn_offset = new_offset
                    self._editor.current_pgn_length = new_length
                    print(f"Successfully updated editor game coordinates to offset: {new_offset}, length: {new_length}")

                conn.close()
            except Exception as e:
                print(f"Error updating editor after reindex: {e}")
            finally:
                self._pending_reindex_game_idx = None

    def _on_open_editor_requested(self):
        """Handle 'New Analysis' request — open editor without loading a game."""
        # Clear repertoire context
        self._active_repertoire_node_id = None
        editor = self._get_or_create_editor()
        editor.show()
        editor.raise_()
        editor.activateWindow()

    # ──────────────────────── Editor Management ────────────────────────

    def _get_or_create_editor(self) -> ChessApp:
        """Get the existing editor window or create a new one.

        Only one editor window is maintained. If it was closed, a new one is created.
        """
        if self._editor is None or not self._editor.isVisible():
            if self._editor is not None:
                # Clean up the old editor if it exists but is hidden/closed
                try:
                    self._editor.engine.quit()
                except Exception:
                    pass

            self._editor = ChessApp()
            self._editor.gameSaved.connect(self._on_game_saved)
            self._editor.set_style("dark")
            self._editor.setWindowIcon(self.home.windowIcon())

        return self._editor
