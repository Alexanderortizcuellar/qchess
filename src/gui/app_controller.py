import time
from PyQt5.QtCore import QObject, QSettings, QTimer
from PyQt5.QtGui import QIcon
from typing import Optional, List

from gui.home_window import HomeWindow
from gui.app import ChessApp
from core.reference_filters import get_reference_filter_manager


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

        # Wire streaming backend progress signals for dynamic fallback scans
        if hasattr(self.home.scid_client, "opening_tree_progress"):
            self.home.scid_client.opening_tree_progress.connect(self._on_opening_tree_progress)
        if hasattr(self.home.scid_client, "continuations_progress"):
            self.home.scid_client.continuations_progress.connect(self._on_continuations_progress)

        # Wire global reference database filter manager
        self.ref_filter_mgr = get_reference_filter_manager()
        self.ref_filter_mgr.filtersChanged.connect(self._on_reference_filters_changed)

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
        if hasattr(editor, "position_games_widget"):
            editor.position_games_widget.set_client(self.home.scid_client)
            editor.position_games_widget.queryRequested.connect(lambda fen, flt, ed=editor: self._on_position_games_query_requested(fen, flt, ed))
            editor.position_games_widget.gameSelected.connect(lambda gid, summ, ed=editor: self._on_sample_game_selected(gid, summ, ed))
        editor.themeChanged.connect(self.set_style)
        if hasattr(editor, "referenceRequested"):
            editor.referenceRequested.connect(lambda fen, force, ed=editor: self._query_unified_reference(fen, None, ed, force=force))
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
        """When a database is opened in HomeWindow, refresh opening explorer, continuations, endgames, and games in all open windows."""
        for editor in self._editors:
            if editor.isVisible():
                editor._loaded_tree_fen = None
                editor._loaded_cont_fen = None
                editor._loaded_endg_fen = None
                editor._loaded_games_fen = None
                if hasattr(editor, "send_reference"):
                    editor.send_reference(editor.chessboard.fen(), force=True)
                elif hasattr(editor, "send_fen_to_opxl"):
                    editor.send_fen_to_opxl(editor.chessboard.fen(), force=True)

    def _on_opening_tree_progress(self, prog_data: dict):
        """Streaming progress event from backend during dynamic tree scan."""
        scanned = prog_data.get("scanned", 0)
        total = prog_data.get("total", 0)
        percent = float(prog_data.get("percent", 0.0))

        now = time.time()
        for editor in self._editors:
            start_t = getattr(editor, "_opxl_query_start_time", None)
            if start_t is not None and (now - start_t) >= 0.3:
                if hasattr(editor, "opxl") and hasattr(editor.opxl, "set_progress"):
                    editor.opxl.set_progress(scanned, total, percent)
                if hasattr(editor, "statusBar"):
                    editor.statusBar().showMessage(
                        f"Opening Tree: scanning {scanned:,} / {total:,} games ({percent:.1f}%)..."
                    )

    def _on_continuations_progress(self, prog_data: dict):
        """Streaming progress event from backend during dynamic continuations scan."""
        scanned = prog_data.get("scanned", 0)
        total = prog_data.get("total", 0)
        percent = float(prog_data.get("percent", 0.0))

        now = time.time()
        for editor in self._editors:
            start_t = getattr(editor, "_cont_query_start_time", None)
            if start_t is not None and (now - start_t) >= 0.3:
                if hasattr(editor, "continuations_widget") and hasattr(editor.continuations_widget, "set_progress"):
                    editor.continuations_widget.set_progress(scanned, total, percent)
                if hasattr(editor, "statusBar"):
                    editor.statusBar().showMessage(
                        f"Continuations: scanning {scanned:,} / {total:,} games ({percent:.1f}%)..."
                    )

    def _on_reference_filters_changed(self, filter_dict: dict):
        """When global reference filters change, immediately re-query active reference docks in all open editors."""
        for editor in self._editors:
            if editor.isVisible():
                editor._loaded_tree_fen = None
                editor._loaded_cont_fen = None
                editor._loaded_endg_fen = None
                editor._loaded_games_fen = None
                fen = editor.chessboard.fen()
                if hasattr(editor, "send_reference"):
                    editor.send_reference(fen, force=True)
                elif hasattr(editor, "send_fen_to_opxl"):
                    editor.send_fen_to_opxl(fen, force=True)

    def _on_explorer_query_requested(self, fen: str, filters: dict, editor: ChessApp):
        """Route Opening Explorer queries via the unified reference orchestrator."""
        self._query_unified_reference(fen, filters, editor)

    def _on_continuations_query_requested(self, fen: str, options: dict, editor: ChessApp):
        """Route Continuations queries via the unified reference orchestrator."""
        self._query_unified_reference(fen, None, editor, options=options)

    def _on_endgames_query_requested(self, fen: str, options: dict, editor: ChessApp):
        """Route Endgame Popularity queries via the unified reference orchestrator."""
        self._query_unified_reference(fen, None, editor, options=options)

    def _on_position_games_query_requested(self, fen: str, filters: dict, editor: ChessApp):
        """Route Matching Games queries via the unified reference orchestrator."""
        self._query_unified_reference(fen, filters, editor)

    def _query_unified_reference(
        self,
        fen: str,
        filters: Optional[dict],
        editor: ChessApp,
        options: Optional[dict] = None,
        force: bool = False,
    ):
        """Unified orchestrator querying Tree, Continuations, Endgames, and Games in a single pass."""
        if editor not in self._editors:
            return

        if not self.home.scid_client.is_running() or not self.home._current_db_path:
            if hasattr(editor, "opxl"):
                editor.opxl.show_status("Open a database in QChess to explore opening statistics.")
            if hasattr(editor, "continuations_widget"):
                editor.continuations_widget.show_status("Open a database in QChess to analyze common continuations.")
            if hasattr(editor, "endgames_widget"):
                editor.endgames_widget.show_status("Open a database in QChess to explore endgame statistics.")
            if hasattr(editor, "position_games_widget"):
                editor.position_games_widget.show_status("Open a database in QChess to explore matching games.")
            return

        # Check active dock / tab flags
        include_tree = hasattr(editor, "is_explorer_active") and editor.is_explorer_active()
        include_continuations = hasattr(editor, "is_continuations_active") and editor.is_continuations_active()
        include_endgames = hasattr(editor, "is_endgames_active") and editor.is_endgames_active()
        include_games = hasattr(editor, "is_games_active") and editor.is_games_active()

        # If none of the reference docks are active and not forced, nothing to query
        if not (include_tree or include_continuations or include_endgames or include_games) and not force:
            return

        # If forced and all False, enable tree and games by default
        if force and not (include_tree or include_continuations or include_endgames or include_games):
            include_tree = True
            include_games = True

        query_tree = include_tree and (getattr(editor, "_loaded_tree_fen", None) != fen)
        query_cont = include_continuations and (getattr(editor, "_loaded_cont_fen", None) != fen)
        query_endg = include_endgames and (getattr(editor, "_loaded_endg_fen", None) != fen)
        query_games = include_games and (getattr(editor, "_loaded_games_fen", None) != fen)

        if not (query_tree or query_cont or query_endg or query_games):
            return

        # Continuations parameters
        cont_depth = None
        max_lines = None
        min_games = None
        min_pct = None
        cw = getattr(editor, "continuations_widget", None)
        if cw:
            cont_depth = getattr(cw, "depth", 8)
            max_lines = getattr(cw, "max_lines", 6)
            min_games = getattr(cw, "min_games", 1)
            min_pct = getattr(cw, "min_pct", 0.0)
            if hasattr(cw, "spin_depth"):
                cont_depth = cw.spin_depth.value()
                max_lines = cw.spin_max_lines.value()
                min_games = cw.spin_min_games.value()
                min_pct = cw.spin_min_pct.value()
            if query_cont and hasattr(cw, "lbl_source_badge"):
                cw.lbl_source_badge.setText("⏳ Calculating...")

        if options:
            cont_depth = options.get("max_depth", cont_depth)
            max_lines = options.get("max_lines", max_lines)
            min_games = options.get("min_games", min_games)
            min_pct = options.get("min_percentage", min_pct)

        # Merge global filters
        global_filters = dict(self.ref_filter_mgr.get_filter_dict())
        if filters:
            global_filters.update(filters)
        active_filters = global_filters if global_filters else None

        # Show loading only on widgets that need fresh data
        if (query_tree or query_games) and hasattr(editor, "update_reference_header"):
            editor.update_reference_header(is_loading=True)
        if query_tree and hasattr(editor, "opxl"):
            editor._opxl_query_start_time = time.time()
        if query_cont and hasattr(editor, "continuations_widget"):
            editor._cont_query_start_time = time.time()
        if query_endg and hasattr(editor, "endgames_widget"):
            editor.endgames_widget.show_loading("Querying endgame statistics...")
        if query_games and hasattr(editor, "position_games_widget"):
            editor.position_games_widget.show_loading("Querying matching games...")
        editor._active_reference_fen = fen

        def on_reference_ready(resp: dict):
            if editor not in self._editors:
                return
            if getattr(editor, "_active_reference_fen", None) != fen:
                return
            editor._opxl_query_start_time = None
            editor._cont_query_start_time = None
            if hasattr(editor, "statusBar"):
                msg = editor.statusBar().currentMessage()
                if msg.startswith("Opening Tree:") or msg.startswith("Continuations:"):
                    editor.statusBar().clearMessage()

            if resp.get("status") == "ok":
                data = resp.get("data", {})
                search_id = data.get("search_id")
                total_games = data.get("total_games", 0)

                # Update unified reference header
                if hasattr(editor, "update_reference_header") and (query_tree or query_games or total_games > 0):
                    editor.update_reference_header(total_games=total_games)

                # 1. Opening Tree
                if query_tree and "tree" in data and data["tree"] is not None and hasattr(editor, "opxl"):
                    editor.opxl.set_tree_data(data["tree"])
                    editor._loaded_tree_fen = fen

                # 2. Continuations
                if query_cont and "continuations" in data and data["continuations"] is not None and hasattr(editor, "continuations_widget"):
                    cont_lines = data.get("continuations") or []
                    editor.continuations_widget.set_report({
                        "lines": cont_lines,
                        "total_games_processed": total_games,
                        "games_reaching_position": total_games,
                        "source": "booster",
                    })
                    editor._loaded_cont_fen = fen

                # 3. Endgames
                if query_endg and "endgames" in data and data["endgames"] is not None and hasattr(editor, "endgames_widget"):
                    editor.endgames_widget.set_report(data["endgames"])
                    editor._loaded_endg_fen = fen

                # 4. Matching Games Table Session
                if query_games and hasattr(editor, "position_games_widget"):
                    games_slice = data.get("games")
                    editor.position_games_widget.set_search_session(
                        search_id=search_id,
                        total_count=total_games,
                        filters=active_filters,
                        initial_games=games_slice if include_games else None,
                        owner="reference",
                    )
                    editor._loaded_games_fen = fen
            else:
                err = resp.get("error", "Error querying reference statistics")
                if hasattr(editor, "update_reference_header"):
                    editor.update_reference_header(message=f"⚠ {err}")
                if query_tree and hasattr(editor, "opxl"):
                    editor.opxl.show_status(f"Opening explorer: {err}")
                if query_cont and hasattr(editor, "continuations_widget"):
                    editor.continuations_widget.show_status(f"Continuations error: {err}")
                if query_endg and hasattr(editor, "endgames_widget"):
                    editor.endgames_widget.show_status(f"Endgames error: {err}")
                if query_games and hasattr(editor, "position_games_widget"):
                    editor.position_games_widget.show_status(f"Games error: {err}")

        try:
            self.home.scid_client.reference(
                fen=fen,
                include_tree=query_tree,
                include_continuations=query_cont,
                include_endgames=query_endg,
                include_games=query_games,
                page=0,
                page_size=25,
                filters=active_filters,
                continuation_depth=cont_depth,
                max_lines=max_lines,
                min_games=min_games,
                min_percentage=min_pct,
                callback=on_reference_ready,
            )
        except Exception as e:
            editor._opxl_query_start_time = None
            editor._cont_query_start_time = None
            if hasattr(editor, "opxl"):
                editor.opxl.show_status(f"Reference query error: {e}")

    def _on_build_hot_index_requested(self, editor: Optional[ChessApp] = None):
        """Open the Build Fast Indexes dialog pre-selecting Search Booster (.boost.idx)."""
        if not self.home.scid_client.is_running() or not self.home._current_db_path:
            parent_window = editor if (editor and editor in self._editors) else self.home
            if hasattr(parent_window, "statusBar"):
                parent_window.statusBar().showMessage("Open a database first to build indexes.", 3000)
            return
        from gui.dialogs.build_pos_index_dialog import BuildPosIndexDialog

        parent_window = editor if (editor and editor in self._editors) else self.home
        dlg = BuildPosIndexDialog(self.home.scid_client, parent=parent_window)
        if hasattr(dlg, "chk_booster"):
            dlg.chk_booster.setChecked(True)
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
        if hasattr(dlg, "chk_booster"):
            dlg.chk_booster.setChecked(False)
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
