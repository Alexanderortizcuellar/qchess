from PyQt5.QtCore import QObject, QSettings, QTimer
from PyQt5.QtGui import QIcon
from typing import Optional, List

from gui.home_window import HomeWindow
from gui.app import ChessApp


class ApplicationController(QObject):
    """Coordinates the application's multi-window architecture.

    Responsibilities:
        - Creates and manages the HomeWindow (database browser).
        - Creates and manages multiple concurrent ChessApp editor windows.
        - Routes 'Open Game' requests from HomeWindow to new/active editors.
        - Routes 'Open Repertoire' requests from Repertoire Manager to an editor.
        - Handles Opening Explorer and Continuations queries per editor window.
        - Handles sample game selection by opening a new, unrestricted ChessApp window.
        - Manages shared application theme, icon, and lifecycle shutdown.

    Communication flow:
        HomeWindow -- emits -> gameSelected(dict)
        ApplicationController -> creates ChessApp and loads game

        HomeWindow.repertoire_tree -- emits -> repertoireOpenRequested(node_id, pgn)
        ApplicationController -> creates ChessApp (loads PGN in repertoire mode)

        ChessApp.opxl -- emits -> sampleGameSelected(game_id, summary)
        ApplicationController -> fetches PGN and opens a new ChessApp window
    """

    def __init__(self) -> None:
        """Initialize ApplicationController, create HomeWindow and wire signals."""
        super().__init__()
        self._current_style: str = QSettings("QChessApp", "Theme").value("theme", "dark")
        self._icon: Optional[QIcon] = None

        # Managed editor windows
        self._editors: List[ChessApp] = []
        self._prewarmed_editor: Optional[ChessApp] = None

        # Core objects - HomeWindow creates the shared ScidClient
        self.home = HomeWindow()

        # Wire HomeWindow signals to controller slots
        self.home.gameSelected.connect(self._on_game_selected)
        self.home.repertoireOpenRequested.connect(self._on_repertoire_open_requested)
        self.home.openEditorRequested.connect(self._on_open_editor_requested)
        self.home.databaseOpened.connect(self._on_database_opened)
        self.home.themeChangeRequested.connect(self.set_style)
        self.home.destroyed.connect(self.shutdown)

        # Pre-warm an editor window in the background for fast startup
        QTimer.singleShot(250, self._prewarm_editor)

    def _prewarm_editor(self):
        """Pre-instantiate an editor window in the background so the first game opens quickly."""
        if self._prewarmed_editor is None and not self._editors:
            self._prewarmed_editor = self._build_editor()

    def shutdown(self):
        """Cleanly terminate engine processes on app exit."""
        if self._prewarmed_editor is not None:
            try:
                self._prewarmed_editor.engine.quit()
                self._prewarmed_editor.close()
            except Exception:
                pass
            self._prewarmed_editor = None

        for editor in list(self._editors):
            try:
                editor.engine.quit()
                editor.close()
            except Exception:
                pass
        self._editors.clear()

    def show(self):
        """Show the home window (main entry point)."""
        self.home.showMaximized()

    def set_icon(self, icon: QIcon):
        """Set the window icon on all managed windows."""
        self._icon = icon
        self.home.setWindowIcon(icon)
        if self._prewarmed_editor is not None:
            self._prewarmed_editor.setWindowIcon(icon)
        for editor in self._editors:
            editor.setWindowIcon(icon)

    def set_style(self, style_name: str):
        """Apply a style/theme to all managed windows and the global application."""
        import os
        from PyQt5.QtWidgets import QApplication

        self._current_style = style_name
        QSettings("QChessApp", "Theme").setValue("theme", style_name)
        is_dark = style_name == "dark"

        current_dir = os.path.dirname(os.path.abspath(__file__))
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "assets")
        qss_file = os.path.join(assets_dir, "style.qss" if is_dark else "light_style.qss")

        try:
            if os.path.exists(qss_file):
                with open(qss_file, "r", encoding="utf-8") as f:
                    app_inst = QApplication.instance()
                    if app_inst:
                        app_inst.setStyleSheet(f.read())
        except Exception as e:
            print(f"Error loading theme stylesheet: {e}")

        self.home.set_theme(is_dark)
        if self._prewarmed_editor is not None and self._prewarmed_editor.is_dark != is_dark:
            self._prewarmed_editor.set_style(style_name)
        for editor in self._editors:
            if editor.is_dark != is_dark:
                editor.set_style(style_name)

    # ----------------------------------------------------------------------
    # Window Creation and Management
    # ----------------------------------------------------------------------

    def _build_editor(self) -> ChessApp:
        """Instantiate a new ChessApp and connect all routing signals."""
        editor = ChessApp()
        editor._active_repertoire_node_id = None
        editor._current_table_row = None
        editor._current_game_id = None

        editor.gameSaved.connect(lambda p, o, l, ed=editor: self._on_game_saved(p, o, l, ed))
        editor.repertoireSaveRequested.connect(lambda pgn, ed=editor: self._on_repertoire_save_requested(pgn, ed))
        editor.searchPositionRequested.connect(self._on_search_position_requested)
        editor.previousGameRequested.connect(lambda ed=editor: self._on_previous_game_requested(ed))
        editor.nextGameRequested.connect(lambda ed=editor: self._on_next_game_requested(ed))
        editor.opxl.queryRequested.connect(lambda fen, flt, ed=editor: self._on_explorer_query_requested(fen, flt, ed))
        editor.opxl.sampleGameSelected.connect(lambda gid, summ, ed=editor: self._on_sample_game_selected(gid, summ, ed))
        editor.continuations_widget.queryRequested.connect(lambda fen, opt, ed=editor: self._on_continuations_query_requested(fen, opt, ed))
        editor.continuations_widget.buildHotIndexRequested.connect(lambda ed=editor: self._on_build_hot_index_requested(ed))
        editor.endgames_widget.queryRequested.connect(lambda fen, opt, ed=editor: self._on_endgames_query_requested(fen, opt, ed))
        editor.endgames_widget.buildEndgamesIndexRequested.connect(lambda ed=editor: self._on_build_endgames_index_requested(ed))
        editor.themeChanged.connect(self.set_style)
        editor.closed.connect(lambda ed=editor: self._on_editor_closed(ed))

        editor.set_style(self._current_style)
        if self._icon:
            editor.setWindowIcon(self._icon)
        else:
            editor.setWindowIcon(self.home.windowIcon())

        editor.destroyed.connect(lambda ed=editor: self._on_editor_closed(ed))
        return editor

    def _on_editor_closed(self, editor: ChessApp):
        """Cleanly unregister closed editor window from active tracking."""
        try:
            if hasattr(editor, "engine") and editor.engine:
                editor.engine.quit()
        except Exception:
            pass
        try:
            if editor in self._editors:
                self._editors.remove(editor)
        except Exception:
            pass

    def _create_editor(self) -> ChessApp:
        """Obtain a new ChessApp window (reusing pre-warmed if available)."""
        if self._prewarmed_editor is not None:
            editor = self._prewarmed_editor
            self._prewarmed_editor = None
        else:
            editor = self._build_editor()

        if editor not in self._editors:
            self._editors.append(editor)

        return editor

    def _load_game_into_editor(self, editor: ChessApp, game_data: dict) -> None:
        """Populate the given editor with game data."""
        pgn_text = game_data.get("PGN", "")
        editor._active_repertoire_node_id = None
        editor._current_table_row = game_data.get("_row_idx")
        editor._current_game_id = game_data.get("_id")
        self._set_repertoire_mode(editor, False)

        editor.current_pgn_path = game_data.get("_pgn_path") or self.home._current_db_path
        editor.current_pgn_offset = game_data.get("_offset")
        editor.current_pgn_length = game_data.get("_length")
        editor.move_manager.update_pgn(pgn_text or "")
        editor.move_manager.is_dirty = False
        editor.display_pgn()

        # Check for search session matching plies
        matching_plies = game_data.get("matching_plies") or game_data.get("_matching_plies") or []
        editor.set_matching_plies(matching_plies)
        if matching_plies:
            target_ply = matching_plies[0]
            editor.goto_ply(target_ply)
        else:
            editor.chessboard.update_board(editor.move_manager.get_board().fen())

        white = game_data.get("White", "?")
        black = game_data.get("Black", "?")
        row_idx = game_data.get("_row_idx")
        total_rows = game_data.get("_total_rows")
        if row_idx is not None and total_rows:
            editor.setWindowTitle(f"Chess App - Game {row_idx + 1}/{total_rows}: {white} vs {black}")
            if matching_plies:
                editor.statusBar().showMessage(f"Game {row_idx + 1} of {total_rows} ({white} vs {black}) — Jumped to match 1/{len(matching_plies)} at ply {matching_plies[0]}", 6000)
            else:
                editor.statusBar().showMessage(f"Game {row_idx + 1} of {total_rows} ({white} vs {black})", 4000)
        else:
            editor.setWindowTitle(f"Chess App - {white} vs {black}")

        editor.showMaximized()
        editor.raise_()
        editor.activateWindow()

    def _set_repertoire_mode(self, editor: ChessApp, is_repertoire: bool):
        """Show or hide the 'Save Repertoire' action in the editor's File menu."""
        try:
            editor.save_repertoire_action.setVisible(is_repertoire)
        except AttributeError:
            pass

    # ----------------------------------------------------------------------
    # Signal Handlers
    # ----------------------------------------------------------------------

    def _on_game_selected(self, game_data: dict):
        """Handle a game selection from HomeWindow: opens the game in a new window."""
        editor = self._create_editor()
        self._load_game_into_editor(editor, game_data)

    def _on_open_editor_requested(self):
        """Handle 'New Analysis' request - open a new editor window without loading a game."""
        editor = self._create_editor()
        editor._active_repertoire_node_id = None
        editor._current_table_row = None
        editor._current_game_id = None
        self._set_repertoire_mode(editor, False)
        editor.clear_pgn()
        editor.setWindowTitle("Chess App - New Analysis")
        editor.showMaximized()
        editor.raise_()
        editor.activateWindow()

    def _on_repertoire_open_requested(self, node_id: int, pgn_text: str):
        """Handle a repertoire open request from the Repertoire Manager in a new window."""
        editor = self._create_editor()
        editor._active_repertoire_node_id = node_id
        self._set_repertoire_mode(editor, True)

        editor.current_pgn_path = None
        editor.current_pgn_offset = None
        editor.current_pgn_length = None

        if pgn_text and pgn_text.strip():
            editor.move_manager.update_pgn(pgn_text)
        else:
            editor.move_manager.update_pgn("")

        editor.move_manager.is_dirty = False
        editor.display_pgn()
        editor.chessboard.update_board(editor.move_manager.get_board().fen())

        node = self.home.repertoire_tree._repo.get_node(node_id)
        title = node.name if node else f"Repertoire #{node_id}"
        editor.setWindowTitle(f"QChess - {title}")

        editor.showMaximized()
        editor.raise_()
        editor.activateWindow()

    def _on_repertoire_save_requested(self, pgn_text: str, editor: ChessApp):
        """Handle repertoireSaveRequested from an editor's File menu."""
        node_id = getattr(editor, "_active_repertoire_node_id", None)
        if node_id is not None:
            self.home.repertoire_tree.on_repertoire_saved(node_id, pgn_text)

    def _on_game_saved(self, pgn_path: str, old_offset, old_length, editor: ChessApp):
        """Handle a game save notification from an editor."""
        node_id = getattr(editor, "_active_repertoire_node_id", None)
        if node_id is not None:
            try:
                pgn_text = editor.move_manager.get_pgn()
            except Exception:
                pgn_text = ""
            self.home.repertoire_tree.on_repertoire_saved(node_id, pgn_text)
            return

        # Regular database mode: refresh database view in HomeWindow
        if pgn_path:
            self.home.load_database_path(pgn_path)

    def _on_search_position_requested(self, fen: str):
        """Bring HomeWindow to front and open Advanced Search dialog pre-loaded with FEN."""
        self.home.showMaximized()
        self.home.raise_()
        self.home.activateWindow()
        self.home.open_search_dialog(initial_filter={"fen": fen})

    def _on_database_opened(self, db_path: str, format_name: str):
        """When a database is opened in HomeWindow, refresh opening explorer, continuations, and endgames in all open windows."""
        for editor in self._editors:
            if editor.isVisible():
                if hasattr(editor, "opxl"):
                    editor.send_fen_to_opxl(editor.chessboard.fen())
                if hasattr(editor, "continuations_widget"):
                    editor.send_fen_to_continuations(editor.chessboard.fen())
                if hasattr(editor, "endgames_widget"):
                    editor.send_fen_to_endgames(editor.chessboard.fen())

    def _on_explorer_query_requested(self, fen: str, filters: dict, editor: ChessApp):
        """Route Opening Explorer queries from a specific editor to the background scid-mgr process."""
        if editor not in self._editors:
            return

        if not self.home.scid_client.is_running() or not self.home._current_db_path:
            editor.opxl.show_status("Open a database in QChess to explore opening statistics.")
            return

        def on_tree_ready(resp: dict):
            if editor not in self._editors:
                return
            if resp.get("status") == "ok":
                data = resp.get("data", {})
                editor.opxl.set_tree_data(data)
            else:
                err = resp.get("error", "Error querying opening tree")
                editor.opxl.show_status(f"Opening explorer: {err}")

        try:
            self.home.scid_client.opening_tree(
                fen=fen,
                filters=filters if filters else None,
                max_sample_games=20,
                callback=on_tree_ready,
            )
        except Exception as e:
            editor.opxl.show_status(f"Opening explorer error: {e}")

    def _on_continuations_query_requested(self, fen: str, options: dict, editor: ChessApp):
        """Route Common Continuations queries from a specific editor to the background scid-mgr process."""
        if editor not in self._editors:
            return

        if not self.home.scid_client.is_running() or not self.home._current_db_path:
            editor.continuations_widget.show_status("Open a database in QChess to analyze common continuations.")
            return

        def on_continuations_ready(resp: dict):
            if editor not in self._editors:
                return
            if resp.get("status") == "ok":
                data = resp.get("data", {})
                editor.continuations_widget.set_report(data)
            else:
                err = resp.get("error", "Error calculating continuations")
                editor.continuations_widget.show_status(f"Continuations error: {err}")

        try:
            self.home.scid_client.continuations(
                fen=fen,
                max_depth=options.get("max_depth", 8),
                max_lines=options.get("max_lines", 10),
                min_games=options.get("min_games", 1),
                min_percentage=options.get("min_percentage", 0.0),
                callback=on_continuations_ready,
            )
        except Exception as e:
            editor.continuations_widget.show_status(f"Continuations query error: {e}")

    def _on_endgames_query_requested(self, fen: str, options: dict, editor: ChessApp):
        """Route Endgame Popularity queries from a specific editor to the background scid-mgr process."""
        if editor not in self._editors:
            return

        if not self.home.scid_client.is_running() or not self.home._current_db_path:
            editor.endgames_widget.show_status("Open a database in QChess to explore endgame statistics.")
            return

        def on_endgames_ready(resp: dict):
            if editor not in self._editors:
                return
            if resp.get("status") == "ok":
                data = resp.get("data", {})
                editor.endgames_widget.set_report(data)
            else:
                err = resp.get("error", "Error calculating endgames")
                editor.endgames_widget.show_status(f"Endgames error: {err}")

        try:
            self.home.scid_client.endgames(
                fen=fen,
                category=options.get("category"),
                max_samples=options.get("max_samples", 20),
                callback=on_endgames_ready,
            )
        except Exception as e:
            editor.endgames_widget.show_status(f"Endgames query error: {e}")

    def _on_build_hot_index_requested(self, editor: Optional[ChessApp] = None):
        """Open the Build Fast Indexes dialog pre-selecting .hot.idx."""
        if not self.home.scid_client.is_running() or not self.home._current_db_path:
            parent_window = editor if (editor and editor in self._editors) else self.home
            if hasattr(parent_window, "statusBar"):
                parent_window.statusBar().showMessage("Open a database first to build indexes.", 3000)
            return
        from gui.dialogs.build_pos_index_dialog import BuildPosIndexDialog

        parent_window = editor if (editor and editor in self._editors) else self.home
        dlg = BuildPosIndexDialog(self.home.scid_client, parent=parent_window)
        dlg.chk_tree.setChecked(False)
        dlg.chk_pos.setChecked(False)
        dlg.chk_hot.setChecked(True)
        if hasattr(dlg, "chk_feat"):
            dlg.chk_feat.setChecked(False)
        dlg.exec_()

    def _on_build_endgames_index_requested(self, editor: Optional[ChessApp] = None):
        """Open the Build Fast Indexes dialog pre-selecting .feat.idx (Endgame Index)."""
        if not self.home.scid_client.is_running() or not self.home._current_db_path:
            parent_window = editor if (editor and editor in self._editors) else self.home
            if hasattr(parent_window, "statusBar"):
                parent_window.statusBar().showMessage("Open a database first to build indexes.", 3000)
            return
        from gui.dialogs.build_pos_index_dialog import BuildPosIndexDialog

        parent_window = editor if (editor and editor in self._editors) else self.home
        dlg = BuildPosIndexDialog(self.home.scid_client, parent=parent_window)
        dlg.chk_tree.setChecked(False)
        dlg.chk_pos.setChecked(False)
        dlg.chk_hot.setChecked(False)
        if hasattr(dlg, "chk_feat"):
            dlg.chk_feat.setChecked(True)
        dlg.exec_()

    def _on_sample_game_selected(self, game_id: int, summary: dict, source_editor: Optional[ChessApp] = None):
        """Handle sample game selection from Opening Explorer: opens the game in a new window."""
        if not self.home.scid_client.is_running():
            return

        def on_pgn_received(resp: dict):
            if resp.get("status") == "ok":
                pgn_text = resp.get("data", {}).get("pgn", "")
                game_data = {
                    "ID": str(game_id + 1),
                    "White": summary.get("white", "?"),
                    "EloW": str(summary.get("white_elo", "")),
                    "Black": summary.get("black", "?"),
                    "EloB": str(summary.get("black_elo", "")),
                    "Result": summary.get("result", "*"),
                    "ECO": summary.get("eco", ""),
                    "Date": summary.get("date", ""),
                    "Event": summary.get("event", ""),
                    "Site": summary.get("site", ""),
                    "Round": str(summary.get("round", "")),
                    "PGN": pgn_text,
                    "_pgn_path": self.home._current_db_path,
                    "_id": game_id,
                }
                new_editor = self._create_editor()
                new_editor.suppress_explorer_update = True
                try:
                    self._load_game_into_editor(new_editor, game_data)
                finally:
                    new_editor.suppress_explorer_update = False
            else:
                err = resp.get("error", "Failed to retrieve game PGN")
                if source_editor and source_editor in self._editors:
                    source_editor.statusBar().showMessage(f"Error loading sample game: {err}", 4000)

        self.home.scid_client.get_pgn(int(game_id), callback=on_pgn_received)

    # ----------------------------------------------------------------------
    # Navigation across Games for a Specific Window
    # ----------------------------------------------------------------------

    def _fetch_and_load_game_for_editor(self, editor: ChessApp, target_row: int):
        """Fetch game at target_row from active database and load it into the specified editor."""
        if not self.home.scid_client or not self.home.scid_client.is_running():
            editor.statusBar().showMessage("No database is currently opened.", 3000)
            return

        model = self.home.game_table.model
        total = model.total_count
        if total == 0:
            editor.statusBar().showMessage("The active database has no games.", 3000)
            return

        if target_row < 0 or target_row >= total:
            return

        def on_pgn_received(resp: dict, game_item: dict, gid: int):
            if editor not in self._editors:
                return
            if resp.get("status") == "ok":
                pgn_text = resp.get("data", {}).get("pgn", "")
                display_id = game_item.get("id", gid)
                if isinstance(display_id, int):
                    display_id = display_id + 1
                matching_plies = game_item.get("matching_plies") or []
                match_count = game_item.get("match_count", len(matching_plies))
                payload = {
                    "ID": str(display_id),
                    "White": game_item.get("white", "?"),
                    "EloW": str(game_item.get("white_elo", "")),
                    "Black": game_item.get("black", "?"),
                    "EloB": str(game_item.get("black_elo", "")),
                    "Result": game_item.get("result", "*"),
                    "ECO": game_item.get("eco", ""),
                    "Date": game_item.get("date", ""),
                    "Event": game_item.get("event", ""),
                    "Site": game_item.get("site", ""),
                    "Round": str(game_item.get("round", "")),
                    "PGN": pgn_text,
                    "matching_plies": matching_plies,
                    "match_count": match_count,
                    "_matching_plies": matching_plies,
                    "_pgn_path": self.home._current_db_path,
                    "_id": gid,
                    "_row_idx": target_row,
                    "_total_rows": total,
                }
                self._load_game_into_editor(editor, payload)
            else:
                err = resp.get("error", "Failed to retrieve game PGN")
                editor.statusBar().showMessage(f"Error loading game: {err}", 3000)

        game_item = model.get_game_at(target_row)
        if game_item:
            gid = game_item.get("id", target_row)
            self.home.scid_client.get_pgn(int(gid), callback=lambda resp: on_pgn_received(resp, game_item, gid))
        else:
            page = target_row // model.CHUNK_SIZE

            def on_chunk_loaded(resp: dict):
                if resp.get("status") == "ok":
                    model.on_backend_response(resp)
                item = model.get_game_at(target_row) or {}
                gid = item.get("id", target_row)
                self.home.scid_client.get_pgn(int(gid), callback=lambda r: on_pgn_received(r, item, gid))

            self.home.scid_client.query_games(
                page=page,
                page_size=model.CHUNK_SIZE,
                filter_dict=model.filters if not model.search_id else None,
                sort_by=model.filters.get("sort_by"),
                sort_direction=model.filters.get("sort_direction"),
                sort_asc=model.sort_asc,
                search_id=model.search_id,
                callback=on_chunk_loaded,
            )

    def _on_previous_game_requested(self, editor: ChessApp):
        """Navigate to the previous game in the active database for the requesting editor."""
        if not self.home.scid_client or not self.home.scid_client.is_running():
            editor.statusBar().showMessage("No database is currently opened.", 3000)
            return

        total = self.home.game_table.model.total_count
        if total == 0:
            editor.statusBar().showMessage("The active database has no games.", 3000)
            return

        current_row = getattr(editor, "_current_table_row", None)
        if current_row is None:
            target_row = 0
        else:
            target_row = current_row - 1

        if target_row >= 0:
            self._fetch_and_load_game_for_editor(editor, target_row)
        else:
            editor.statusBar().showMessage("Already at the first game in the database.", 3000)

    def _on_next_game_requested(self, editor: ChessApp):
        """Navigate to the next game in the active database for the requesting editor."""
        if not self.home.scid_client or not self.home.scid_client.is_running():
            editor.statusBar().showMessage("No database is currently opened.", 3000)
            return

        total = self.home.game_table.model.total_count
        if total == 0:
            editor.statusBar().showMessage("The active database has no games.", 3000)
            return

        current_row = getattr(editor, "_current_table_row", None)
        if current_row is None:
            target_row = 0
        else:
            target_row = current_row + 1

        if target_row < total:
            self._fetch_and_load_game_for_editor(editor, target_row)
        else:
            editor.statusBar().showMessage("Already at the last game in the database.", 3000)
