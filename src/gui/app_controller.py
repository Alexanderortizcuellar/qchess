from PyQt5.QtCore import QObject
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QApplication

from gui.home_window import HomeWindow
from gui.app import ChessApp


class ApplicationController(QObject):
    """Coordinates the application's two-window architecture.

    Responsibilities:
        - Creates and manages the HomeWindow (database browser).
        - Creates and reuses the GameEditorWindow (ChessApp).
        - Routes "Open Game" requests from HomeWindow to the editor.
        - Manages shared application state.

    Communication flow:
        HomeWindow ── emits ──► gameSelected(dict)
        ApplicationController ──► editor.load_game_from_dict(dict)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._editor = None  # Lazy-created GameEditorWindow (ChessApp)

        # Create the home window
        self.home = HomeWindow()

        # Connect signals
        self.home.gameSelected.connect(self._on_game_selected)
        self.home.openEditorRequested.connect(self._on_open_editor_requested)

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
        if pgn_text:
            editor.move_manager.update_pgn(pgn_text)
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

    def _on_open_editor_requested(self):
        """Handle 'New Analysis' request — open editor without loading a game."""
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
            self._editor.set_style("dark")
            self._editor.setWindowIcon(self.home.windowIcon())

        return self._editor
