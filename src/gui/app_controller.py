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
                                ──► else: reload database in HomeWindow
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editor = None
        self._active_repertoire_node_id: int | None = None

        # Create the home window
        self.home = HomeWindow()

        # Connect signals
        self.home.gameSelected.connect(self._on_game_selected)
        self.home.openEditorRequested.connect(self._on_open_editor_requested)
        self.home.repertoireOpenRequested.connect(self._on_repertoire_open_requested)

    def show(self):
        """Show the home window (main entry point)."""
        self.home.showMaximized()

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
        self._set_repertoire_mode(editor, False)

        editor.current_pgn_path = game_data.get("_pgn_path") or self.home._current_db_path
        editor.current_pgn_offset = game_data.get("_offset")
        editor.current_pgn_length = game_data.get("_length")
        editor.move_manager.update_pgn(pgn_text or "")
        editor.move_manager.is_dirty = False
        editor.display_pgn()
        editor.chessboard.update_board(editor.move_manager.get_board().fen())

        white = game_data.get("White", "?")
        black = game_data.get("Black", "?")
        editor.setWindowTitle(f"Chess App — {white} vs {black}")

        editor.showMaximized()
        editor.raise_()
        editor.activateWindow()

    def _on_repertoire_open_requested(self, node_id: int, pgn_text: str):
        """Handle a repertoire open request from the Repertoire Manager."""
        editor = self._get_or_create_editor()
        self._active_repertoire_node_id = node_id
        self._set_repertoire_mode(editor, True)

        editor.current_pgn_path = None
        editor.current_pgn_offset = None
        editor.current_pgn_length = None

        if pgn_text.strip():
            editor.move_manager.update_pgn(pgn_text)
        else:
            editor.move_manager.update_pgn("")

        editor.move_manager.is_dirty = False
        editor.display_pgn()
        editor.chessboard.update_board(editor.move_manager.get_board().fen())

        node = self.home.repertoire_tree._repo.get_node(node_id)
        title = node.name if node else f"Repertoire #{node_id}"
        editor.setWindowTitle(f"QChess — {title}")

        editor.showMaximized()
        editor.raise_()
        editor.activateWindow()

    def _on_repertoire_save_requested(self, pgn_text: str):
        """Handle repertoireSaveRequested from the editor's File menu."""
        if self._active_repertoire_node_id is not None:
            self.home.repertoire_tree.on_repertoire_saved(
                self._active_repertoire_node_id, pgn_text
            )

    def _set_repertoire_mode(self, editor, is_repertoire: bool):
        """Show or hide the 'Save Repertoire' action in the editor's File menu."""
        try:
            editor.save_repertoire_action.setVisible(is_repertoire)
        except AttributeError:
            pass

    def _on_game_saved(self, pgn_path: str, old_offset, old_length):
        """Handle a game save notification from the editor."""
        if self._active_repertoire_node_id is not None:
            try:
                pgn_text = self._editor.move_manager.get_pgn()
            except Exception:
                pgn_text = ""
            self.home.repertoire_tree.on_repertoire_saved(
                self._active_repertoire_node_id, pgn_text
            )
            return

        # Regular database mode: refresh database view in HomeWindow
        if pgn_path:
            self.home.load_database_path(pgn_path)

    def _on_open_editor_requested(self):
        """Handle 'New Analysis' request — open editor without loading a game."""
        self._active_repertoire_node_id = None
        editor = self._get_or_create_editor()
        self._set_repertoire_mode(editor, False)
        editor.showMaximized()
        editor.raise_()
        editor.activateWindow()

    def _on_search_position_requested(self, fen: str):
        """Bring HomeWindow to front and open Advanced Search dialog pre-loaded with FEN."""
        self.home.showMaximized()
        self.home.raise_()
        self.home.activateWindow()
        self.home.open_search_dialog(initial_filter={"fen": fen})

    # ──────────────────────── Editor Management ────────────────────────

    def _get_or_create_editor(self) -> ChessApp:
        if self._editor is None or not self._editor.isVisible():
            if self._editor is not None:
                try:
                    self._editor.engine.quit()
                except Exception:
                    pass

            self._editor = ChessApp()
            self._editor.gameSaved.connect(self._on_game_saved)
            self._editor.repertoireSaveRequested.connect(self._on_repertoire_save_requested)
            self._editor.searchPositionRequested.connect(self._on_search_position_requested)
            self._editor.set_style("dark")
            self._editor.setWindowIcon(self.home.windowIcon())

        return self._editor
