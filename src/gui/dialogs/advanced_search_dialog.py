import chess
from typing import Optional, Dict, Any, List
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtGui import QFont, QColor, QKeySequence
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QTabWidget, QWidget, QRadioButton,
    QGroupBox, QSpinBox, QButtonGroup, QMessageBox, QApplication,
    QPlainTextEdit, QFrame, QScrollArea
)
import qtawesome as qta

try:
    from gui.widgets.board_widget import ChessBoardEditorWidget
except ImportError:
    from ..widgets.board_widget import ChessBoardEditorWidget


class AdvancedSearchDialog(QDialog):
    """
    Modern ChessBase-style Advanced Multi-Tab Search & CQL Query Dialog.

    Tabs:
      1. 🏷️ Game Info (Players, Result, ECO, Date, Event, Site, Deleted Status)
      2. ♟️ Position / Board (Visual Board Editor, FEN Pattern, Depth / Plies, Presets)
      3. ⚖️ Material (Piece counts for White & Black, Presets, Bishop colors, Scope)
      4. ⚡ Query Language (CQLite Query Editor, Realtime Validator, Presets, Helper Buttons)
    """

    CQL_PRESETS = [
        ("-- Select a Query Preset / Template --", ""),
        ("👑 Tactical: Knight Fork on King & Queen", "fork(knight, king, queen)"),
        ("📌 Tactical: Absolute Pin on King", "pin(bishop, knight, king) or pin(rook, knight, king)"),
        ("🏹 Tactical: Skewer on King & Queen", "skewer(bishop, king, queen) or skewer(rook, king, queen)"),
        ("🎯 Tactical: Trapped Queen", "trapped(queen)"),
        ("⚡ Tactical: Queen Sacrifice Line", "path [Qx... kx...] and material_diff < 0"),
        ("♟ Structure: Passed Pawn Race in Endgame", "passed_pawns white >= 1 and passed_pawns black >= 1 and [QqRrBbNn] == 0"),
        ("♟ Structure: Opposite-Colored Bishops Endgame", "opposite_bishops and material_diff == 0"),
        ("♟ Structure: Isolated Queen Pawn (d4 / d5)", "isolated [d4, d5] >= 1"),
        ("⭐ Header + Tactic: Kasparov Win with Exchange Sac", "player \"Kasparov\" and result \"1-0\" and [R] < [B]"),
        ("🔄 Symmetry: Any-Color Knight Fork (flipcolor)", "flipcolor { fork(knight, king, queen) }"),
        ("⚔ Spatial: White Dominates d-file Ray Attacks", "attacks(white_pieces, [d1..d8]) > attacks(black_pieces, [d1..d8])"),
        ("🛡 Defense: Kingside Pawn Shield Intact", "P[f2, g2, h2] == 3 and Kg1"),
    ]

    def __init__(self, current_filter: Optional[dict] = None, scid_client=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Search (Filter & CQL Query)")
        self.resize(880, 700)
        self.setMinimumSize(780, 580)
        self._loading = False
        self.client = scid_client or getattr(parent, "scid_client", None)
        self.is_dark = self._is_dark()

        # Validation debounce timer for query tab
        self._val_timer = QTimer(self)
        self._val_timer.setSingleShot(True)
        self._val_timer.setInterval(400)
        self._val_timer.timeout.connect(self._validate_cql_query)

        self._init_ui()
        self._apply_dialog_styles()

        if current_filter:
            self.load_filter(current_filter)
        else:
            self.update_category_chips()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(10)

        # ── 1. Top Active Categories Header Bar ───────────────────
        self.header_frame = QFrame(self)
        self.header_frame.setObjectName("searchCategoryHeader")
        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(10, 8, 10, 8)
        h_layout.setSpacing(12)

        lbl_cat_title = QLabel("Active Filters:")
        lbl_cat_title.setStyleSheet("font-weight: 700; font-size: 11px;")
        h_layout.addWidget(lbl_cat_title)

        self.chk_enable_info = QCheckBox("🏷 Game Info")
        self.chk_enable_info.setToolTip("Include Game Header criteria (Players, Result, ECO, Date, Event, Site)")
        self.chk_enable_info.toggled.connect(self.update_category_chips)
        h_layout.addWidget(self.chk_enable_info)

        self.chk_enable_pos = QCheckBox("♟ Position")
        self.chk_enable_pos.setToolTip("Include Board Position / FEN pattern criteria")
        self.chk_enable_pos.toggled.connect(self.update_category_chips)
        h_layout.addWidget(self.chk_enable_pos)

        self.chk_enable_mat = QCheckBox("⚖ Material")
        self.chk_enable_mat.setToolTip("Include Piece counts and Material combinations")
        self.chk_enable_mat.toggled.connect(self.update_category_chips)
        h_layout.addWidget(self.chk_enable_mat)

        self.chk_enable_query = QCheckBox("⚡ Query (CQL)")
        self.chk_enable_query.setToolTip("Include Chess Query Language (CQLite) script")
        self.chk_enable_query.toggled.connect(self.update_category_chips)
        h_layout.addWidget(self.chk_enable_query)

        h_layout.addStretch()

        btn_select_all = QPushButton("Select All")
        btn_select_all.setCursor(Qt.PointingHandCursor)
        btn_select_all.setFixedHeight(26)
        btn_select_all.clicked.connect(self.select_all_categories)
        h_layout.addWidget(btn_select_all)

        btn_clear_all = QPushButton("Clear All")
        btn_clear_all.setCursor(Qt.PointingHandCursor)
        btn_clear_all.setFixedHeight(26)
        btn_clear_all.clicked.connect(self.clear_all_categories)
        h_layout.addWidget(btn_clear_all)

        main_layout.addWidget(self.header_frame)

        # ── 2. Main Tab Widget ────────────────────────────────────
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("searchTabWidget")
        self.tabs.setDocumentMode(True)
        main_layout.addWidget(self.tabs, stretch=1)

        # ── TAB 1: Game Info ──────────────────────────────────────
        self.tab_info = QWidget()
        info_main_layout = QVBoxLayout(self.tab_info)
        info_main_layout.setContentsMargins(10, 10, 10, 10)
        info_main_layout.setSpacing(10)

        # Box 1: Players & Result
        grp_players = QGroupBox("Player & Result Criteria")
        grid_players = QGridLayout(grp_players)
        grid_players.setContentsMargins(12, 10, 12, 10)
        grid_players.setSpacing(10)

        grid_players.addWidget(QLabel("Player (Any):"), 0, 0)
        self.in_player = QLineEdit()
        self.in_player.setPlaceholderText("e.g. Carlsen or Kasparov")
        self.in_player.textChanged.connect(self.mark_info_modified)
        grid_players.addWidget(self.in_player, 0, 1)

        grid_players.addWidget(QLabel("Result:"), 0, 2)
        self.in_result = QComboBox()
        self.in_result.addItems(["All", "1-0", "0-1", "1/2-1/2", "*"])
        self.in_result.currentIndexChanged.connect(self.mark_info_modified)
        grid_players.addWidget(self.in_result, 0, 3)

        grid_players.addWidget(QLabel("White:"), 1, 0)
        self.in_white = QLineEdit()
        self.in_white.setPlaceholderText("e.g. Fischer")
        self.in_white.textChanged.connect(self.mark_info_modified)
        grid_players.addWidget(self.in_white, 1, 1)

        grid_players.addWidget(QLabel("Black:"), 1, 2)
        self.in_black = QLineEdit()
        self.in_black.setPlaceholderText("e.g. Spassky")
        self.in_black.textChanged.connect(self.mark_info_modified)
        grid_players.addWidget(self.in_black, 1, 3)

        info_main_layout.addWidget(grp_players)

        # Box 2: Tournament & Metadata
        grp_meta = QGroupBox("Tournament & Classification Metadata")
        grid_meta = QGridLayout(grp_meta)
        grid_meta.setContentsMargins(12, 10, 12, 10)
        grid_meta.setSpacing(10)

        grid_meta.addWidget(QLabel("ECO Code:"), 0, 0)
        self.in_eco = QLineEdit()
        self.in_eco.setPlaceholderText("e.g. B90 or E97")
        self.in_eco.textChanged.connect(self.mark_info_modified)
        grid_meta.addWidget(self.in_eco, 0, 1)

        grid_meta.addWidget(QLabel("Date / Year:"), 0, 2)
        self.in_date = QLineEdit()
        self.in_date.setPlaceholderText("e.g. 2024 or 1999.01")
        self.in_date.textChanged.connect(self.mark_info_modified)
        grid_meta.addWidget(self.in_date, 0, 3)

        grid_meta.addWidget(QLabel("Event:"), 1, 0)
        self.in_event = QLineEdit()
        self.in_event.setPlaceholderText("e.g. World Championship")
        self.in_event.textChanged.connect(self.mark_info_modified)
        grid_meta.addWidget(self.in_event, 1, 1)

        grid_meta.addWidget(QLabel("Site:"), 1, 2)
        self.in_site = QLineEdit()
        self.in_site.setPlaceholderText("e.g. London or Reyjkavik")
        self.in_site.textChanged.connect(self.mark_info_modified)
        grid_meta.addWidget(self.in_site, 1, 3)

        info_main_layout.addWidget(grp_meta)

        # Box 3: Status Filter
        del_box = QGroupBox("Database Status & Archive Filter")
        del_box_layout = QHBoxLayout(del_box)
        del_box_layout.setContentsMargins(12, 8, 12, 8)
        self.chk_include_del = QCheckBox("Include Deleted Games")
        self.chk_include_del.setChecked(True)
        self.chk_include_del.toggled.connect(self.mark_info_modified)
        del_box_layout.addWidget(self.chk_include_del)

        self.chk_only_del = QCheckBox("Only Deleted Games")
        self.chk_only_del.toggled.connect(self.mark_info_modified)
        del_box_layout.addWidget(self.chk_only_del)
        del_box_layout.addStretch()

        info_main_layout.addWidget(del_box)
        info_main_layout.addStretch()

        self.tabs.addTab(self.tab_info, "🏷 Game Info")

        # ── TAB 2: Position (Board Editor & FEN) ───────────────────
        self.tab_pos = QWidget()
        pos_layout = QHBoxLayout(self.tab_pos)
        pos_layout.setContentsMargins(10, 10, 10, 10)
        pos_layout.setSpacing(14)

        # Left Column: Visual Board Editor
        board_col = QVBoxLayout()
        board_col.setSpacing(6)
        self.board_editor = ChessBoardEditorWidget(self)
        self.board_editor.fen_changed.connect(self.on_board_fen_changed)
        board_col.addWidget(self.board_editor)

        board_btn_row = QHBoxLayout()
        board_btn_row.setSpacing(6)
        btn_paste_board = QPushButton("📋 Paste Active Board")
        btn_paste_board.setToolTip("Paste position from open chessboard window or clipboard")
        btn_paste_board.setCursor(Qt.PointingHandCursor)
        btn_paste_board.clicked.connect(self.paste_opened_board_position)
        board_btn_row.addWidget(btn_paste_board)

        btn_clear_b = QPushButton("Clear")
        btn_clear_b.setCursor(Qt.PointingHandCursor)
        btn_clear_b.clicked.connect(self.board_editor.clear_board)
        board_btn_row.addWidget(btn_clear_b)

        btn_init_b = QPushButton("Initial Pos")
        btn_init_b.setCursor(Qt.PointingHandCursor)
        btn_init_b.clicked.connect(self.board_editor.reset_to_initial)
        board_btn_row.addWidget(btn_init_b)

        board_col.addLayout(board_btn_row)
        pos_layout.addLayout(board_col, 0)

        # Right Column: Position Settings & Presets
        controls_col = QVBoxLayout()
        controls_col.setSpacing(8)

        # FEN Input Card
        grp_fen = QGroupBox("Board FEN / Piece Pattern")
        fen_layout = QVBoxLayout(grp_fen)
        fen_layout.setContentsMargins(10, 8, 10, 8)
        self.in_fen = QLineEdit()
        self.in_fen.setPlaceholderText("e.g. 8/8/8/8/3Q4/8/8/8 or full FEN")
        self.in_fen.textChanged.connect(self.on_fen_text_edited)
        fen_layout.addWidget(self.in_fen)
        controls_col.addWidget(grp_fen)

        # Options Card
        options_box = QGroupBox("Position Search Matching Options")
        options_layout = QVBoxLayout(options_box)
        options_layout.setContentsMargins(10, 8, 10, 8)
        options_layout.setSpacing(6)

        # Side to Move
        turn_row = QHBoxLayout()
        turn_row.addWidget(QLabel("<b>Side to Move:</b>"))
        self.rb_turn_any = QRadioButton("Any")
        self.rb_turn_any.setChecked(True)
        self.rb_turn_any.toggled.connect(self.mark_pos_modified)
        self.rb_turn_w = QRadioButton("White (w)")
        self.rb_turn_w.toggled.connect(self.mark_pos_modified)
        self.rb_turn_b = QRadioButton("Black (b)")
        self.rb_turn_b.toggled.connect(self.mark_pos_modified)
        self.turn_group = QButtonGroup(self)
        self.turn_group.addButton(self.rb_turn_any)
        self.turn_group.addButton(self.rb_turn_w)
        self.turn_group.addButton(self.rb_turn_b)
        turn_row.addWidget(self.rb_turn_any)
        turn_row.addWidget(self.rb_turn_w)
        turn_row.addWidget(self.rb_turn_b)
        turn_row.addStretch()
        options_layout.addLayout(turn_row)

        # Match Mode
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("<b>Match Mode:</b>"))
        self.rb_mode_board = QRadioButton("Board Layout")
        self.rb_mode_board.setChecked(True)
        self.rb_mode_board.setToolTip("Matches all 64 squares piece placement (ignores turn/castling discrepancies)")
        self.rb_mode_board.toggled.connect(self.mark_pos_modified)
        self.rb_mode_exact = QRadioButton("Exact (All Flags)")
        self.rb_mode_exact.toggled.connect(self.mark_pos_modified)
        self.rb_mode_partial = QRadioButton("Partial Placed")
        self.rb_mode_partial.setToolTip("Matches games where placed pieces appear on their specified squares")
        self.rb_mode_partial.toggled.connect(self.mark_pos_modified)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_mode_board)
        self.mode_group.addButton(self.rb_mode_exact)
        self.mode_group.addButton(self.rb_mode_partial)
        mode_row.addWidget(self.rb_mode_board)
        mode_row.addWidget(self.rb_mode_exact)
        mode_row.addWidget(self.rb_mode_partial)
        mode_row.addStretch()
        options_layout.addLayout(mode_row)

        # Depth
        depth_row = QHBoxLayout()
        depth_row.addWidget(QLabel("<b>Max Search Depth:</b>"))
        self.spin_max_ply = QSpinBox()
        self.spin_max_ply.setRange(1, 1000)
        self.spin_max_ply.setValue(250)
        self.spin_max_ply.setSuffix(" plies")
        self.spin_max_ply.valueChanged.connect(self.mark_pos_modified)
        depth_row.addWidget(self.spin_max_ply)
        depth_row.addStretch()
        options_layout.addLayout(depth_row)

        controls_col.addWidget(options_box)

        # Presets Card
        preset_box = QGroupBox("Common Position Presets")
        preset_grid = QGridLayout(preset_box)
        preset_grid.setContentsMargins(10, 8, 10, 8)
        preset_grid.setSpacing(6)

        btn_start_pos = QPushButton("Standard Start Pos")
        btn_start_pos.clicked.connect(lambda: self.board_editor.set_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"))
        preset_grid.addWidget(btn_start_pos, 0, 0)

        btn_alapin = QPushButton("Sicilian Alapin (2.c3)")
        btn_alapin.clicked.connect(lambda: self.board_editor.set_fen("rnbqkbnr/pp1ppppp/8/2p5/4P3/2P5/PP1P1PPP/RNBQKBNR b KQkq - 0 2"))
        preset_grid.addWidget(btn_alapin, 0, 1)

        btn_najdorf = QPushButton("Sicilian Najdorf (6.Be2)")
        btn_najdorf.clicked.connect(lambda: self.board_editor.set_fen("rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6"))
        preset_grid.addWidget(btn_najdorf, 1, 0)

        btn_french = QPushButton("French Defense (3.Nc3)")
        btn_french.clicked.connect(lambda: self.board_editor.set_fen("rnbqkbnr/ppp2ppp/4p3/3p4/3PP3/2N5/PPP2PPP/R1BQKBNR b KQkq - 1 3"))
        preset_grid.addWidget(btn_french, 1, 1)

        controls_col.addWidget(preset_box)
        controls_col.addStretch()
        pos_layout.addLayout(controls_col, 1)

        self.tabs.addTab(self.tab_pos, "♟ Position")

        # ── TAB 3: Material Search ────────────────────────────────
        self.tab_mat = QWidget()
        mat_layout = QVBoxLayout(self.tab_mat)
        mat_layout.setContentsMargins(10, 10, 10, 10)
        mat_layout.setSpacing(10)

        # Presets dropdown
        preset_frame = QFrame()
        p_row = QHBoxLayout(preset_frame)
        p_row.setContentsMargins(0, 0, 0, 0)
        p_row.addWidget(QLabel("<b>Material Preset:</b>"))
        self.combo_mat_preset = QComboBox()
        self.combo_mat_preset.addItems([
            "-- Custom Material --",
            "Rook Endgame (R+P vs R+P)",
            "Queen Endgame (Q+P vs Q+P)",
            "Minor Piece Endgame (B vs N)",
            "Queen vs Rook (Q vs R)",
            "Opposite-Colored Bishops (WB=1, BB=1)",
            "Queen Sacrifice / Queenless (WQ=0, BQ=1)",
            "Pawn Endgame (Pawns only)",
            "Reset All Pieces to Any",
        ])
        self.combo_mat_preset.currentIndexChanged.connect(self.on_material_preset_changed)
        p_row.addWidget(self.combo_mat_preset, 1)
        mat_layout.addWidget(preset_frame)

        # Piece Count Matrix
        grid_box = QGroupBox("Exact Piece Counts (Leave 'Any' for unconstrained)")
        grid = QGridLayout(grid_box)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setSpacing(8)

        pieces = [
            ("♕ Queen", "q"),
            ("♖ Rook", "r"),
            ("♗ Bishop", "b"),
            ("♘ Knight", "n"),
            ("♙ Pawn", "p"),
        ]

        grid.addWidget(QLabel("<b>Color</b>"), 0, 0)
        for col_idx, (pname, _) in enumerate(pieces, start=1):
            lbl_p = QLabel(f"<b>{pname}</b>")
            lbl_p.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl_p, 0, col_idx)

        grid.addWidget(QLabel("<b>White:</b>"), 1, 0)
        self.mat_white = {}
        for col_idx, (_, pkey) in enumerate(pieces, start=1):
            cb = QComboBox()
            cb.addItems(["Any"] + [str(i) for i in (range(9) if pkey == 'p' else range(3))])
            cb.currentIndexChanged.connect(self.mark_mat_modified)
            self.mat_white[pkey] = cb
            grid.addWidget(cb, 1, col_idx)

        grid.addWidget(QLabel("<b>Black:</b>"), 2, 0)
        self.mat_black = {}
        for col_idx, (_, pkey) in enumerate(pieces, start=1):
            cb = QComboBox()
            cb.addItems(["Any"] + [str(i) for i in (range(9) if pkey == 'p' else range(3))])
            cb.currentIndexChanged.connect(self.mark_mat_modified)
            self.mat_black[pkey] = cb
            grid.addWidget(cb, 2, col_idx)

        mat_layout.addWidget(grid_box)

        # Bishop Color Sub-options
        bish_box = QGroupBox("Bishop Color Verification")
        bish_layout = QHBoxLayout(bish_box)
        bish_layout.setContentsMargins(12, 8, 12, 8)
        self.chk_opposite_bishops = QCheckBox("Opposite-Colored Bishops (White & Black on different colors)")
        self.chk_same_bishops = QCheckBox("Same-Colored Bishops (White & Black on same color)")
        self.chk_opposite_bishops.toggled.connect(lambda on: on and self.chk_same_bishops.setChecked(False))
        self.chk_same_bishops.toggled.connect(lambda on: on and self.chk_opposite_bishops.setChecked(False))
        self.chk_opposite_bishops.toggled.connect(self.mark_mat_modified)
        self.chk_same_bishops.toggled.connect(self.mark_mat_modified)
        bish_layout.addWidget(self.chk_opposite_bishops)
        bish_layout.addWidget(self.chk_same_bishops)
        mat_layout.addWidget(bish_box)

        # Match Scope Box
        mode_box = QGroupBox("Search Scope")
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setContentsMargins(12, 8, 12, 8)
        mode_layout.setSpacing(4)
        self.rb_final_pos = QRadioButton("Final Position only (Endgames - Instant lookups)")
        self.rb_final_pos.setChecked(True)
        self.rb_final_pos.toggled.connect(self.mark_mat_modified)
        mode_layout.addWidget(self.rb_final_pos)
        self.rb_any_move = QRadioButton("Any Move during game (Middlegames / Sacrifices)")
        self.rb_any_move.toggled.connect(self.mark_mat_modified)
        mode_layout.addWidget(self.rb_any_move)
        mat_layout.addWidget(mode_box)

        mat_layout.addStretch()
        self.tabs.addTab(self.tab_mat, "⚖ Material")

        # ── TAB 4: ⚡ Query Language (CQL) ─────────────────────────
        self.tab_query = QWidget()
        query_layout = QVBoxLayout(self.tab_query)
        query_layout.setContentsMargins(10, 10, 10, 10)
        query_layout.setSpacing(8)

        # Top Presets Bar
        q_preset_row = QHBoxLayout()
        q_preset_row.addWidget(QLabel("<b>Query Preset:</b>"))
        self.combo_cql_preset = QComboBox()
        for title, _ in self.CQL_PRESETS:
            self.combo_cql_preset.addItem(title)
        self.combo_cql_preset.currentIndexChanged.connect(self._on_cql_preset_selected)
        q_preset_row.addWidget(self.combo_cql_preset, 1)

        btn_insert_demo = QPushButton("Insert Template")
        btn_insert_demo.setCursor(Qt.PointingHandCursor)
        btn_insert_demo.clicked.connect(lambda: self._on_cql_preset_selected(self.combo_cql_preset.currentIndex()))
        q_preset_row.addWidget(btn_insert_demo)
        query_layout.addLayout(q_preset_row)

        # Quick Snippet Insert Buttons
        snippet_bar = QHBoxLayout()
        snippet_bar.setSpacing(4)
        snippet_label = QLabel("Snippets:")
        snippet_label.setStyleSheet("font-weight: 600; font-size: 11px;")
        snippet_bar.addWidget(snippet_label)

        snippets = [
            ("fork()", "fork(knight, king, queen)"),
            ("pin()", "pin(bishop, knight, king)"),
            ("skewer()", "skewer(bishop, king, queen)"),
            ("trapped()", "trapped(queen)"),
            ("passed_pawns", "passed_pawns white >= 1"),
            ("path [...]", "path [e4 ... d5]"),
            ("flipcolor { }", "flipcolor { }"),
            ("material_diff", "material_diff == 0"),
        ]

        for s_name, s_code in snippets:
            btn_snip = QPushButton(s_name)
            btn_snip.setCursor(Qt.PointingHandCursor)
            btn_snip.setFixedHeight(24)
            btn_snip.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            btn_snip.clicked.connect(lambda _, code=s_code: self._insert_snippet(code))
            snippet_bar.addWidget(btn_snip)

        snippet_bar.addStretch()
        query_layout.addLayout(snippet_bar)

        # Code Editor
        self.txt_query = QPlainTextEdit(self)
        self.txt_query.setPlaceholderText(
            "Enter SCID-MGR CQLite query...\n\n"
            "Examples:\n"
            "  fork(knight, king, queen)\n"
            "  pin(bishop, knight, king) or pin(rook, knight, king)\n"
            "  player \"Carlsen\" and date >= \"2020\" and result \"1-0\"\n"
            "  path [e4 ... d5 ... Pe7xd8=Q]\n"
            "  passed_pawns white >= 1 and material_diff > 0\n"
            "  flipcolor { fork(knight, king, queen) }"
        )
        font_editor = QFont("Consolas", 11)
        font_editor.setStyleHint(QFont.Monospace)
        self.txt_query.setFont(font_editor)
        self.txt_query.setTabStopWidth(20)
        self.txt_query.textChanged.connect(self._on_query_text_changed)
        query_layout.addWidget(self.txt_query, stretch=1)

        # Status & Validation Card
        self.val_frame = QFrame(self)
        self.val_frame.setObjectName("cqlValFrame")
        val_layout = QHBoxLayout(self.val_frame)
        val_layout.setContentsMargins(10, 6, 10, 6)
        val_layout.setSpacing(10)

        self.lbl_cql_status = QLabel("⚡ Ready — Type a query above", self)
        self.lbl_cql_status.setStyleSheet("font-size: 11px; font-weight: 600;")
        val_layout.addWidget(self.lbl_cql_status, 1)

        btn_validate = QPushButton("✔ Validate Syntax")
        btn_validate.setCursor(Qt.PointingHandCursor)
        btn_validate.clicked.connect(self._validate_cql_query)
        val_layout.addWidget(btn_validate)

        btn_explain = QPushButton("💡 Explain Query")
        btn_explain.setCursor(Qt.PointingHandCursor)
        btn_explain.clicked.connect(self._explain_cql_query)
        val_layout.addWidget(btn_explain)

        query_layout.addWidget(self.val_frame)

        self.tabs.addTab(self.tab_query, "⚡ Query (CQL)")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # ── 3. Bottom Dialog Action Buttons ───────────────────────
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        btn_reset = QPushButton("🔄 Reset All Filters")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self.reset_all)
        btn_box.addWidget(btn_reset)

        btn_box.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)

        btn_search = QPushButton("🔍 Search Games")
        btn_search.setObjectName("btnSearchGames")
        btn_search.setCursor(Qt.PointingHandCursor)
        btn_search.clicked.connect(self.accept)
        btn_box.addWidget(btn_search)

        main_layout.addLayout(btn_box)

    def _apply_dialog_styles(self):
        is_dark = self.is_dark
        if is_dark:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1a1917;
                    color: #e2e8f0;
                }
                QFrame#searchCategoryHeader {
                    background-color: #21201d;
                    border: 1px solid #383531;
                    border-radius: 6px;
                }
                QFrame#cqlValFrame {
                    background-color: #21201d;
                    border: 1px solid #383531;
                    border-radius: 6px;
                }
                QGroupBox {
                    font-weight: 600;
                    border: 1px solid #383531;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 10px;
                    background-color: #21201d;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color: #94a3b8;
                }
                QPlainTextEdit {
                    background-color: #151413;
                    color: #f8fafc;
                    border: 1px solid #383531;
                    border-radius: 4px;
                    padding: 8px;
                }
                QPushButton#btnSearchGames {
                    font-weight: bold;
                    background-color: #2563eb;
                    color: #ffffff;
                    border: 1px solid #1d4ed8;
                    border-radius: 4px;
                    padding: 6px 22px;
                }
                QPushButton#btnSearchGames:hover {
                    background-color: #3b82f6;
                }
                QPushButton#btnSearchGames:pressed {
                    background-color: #1d4ed8;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f8fafc;
                    color: #0f172a;
                }
                QFrame#searchCategoryHeader {
                    background-color: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                }
                QFrame#cqlValFrame {
                    background-color: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                }
                QGroupBox {
                    font-weight: 600;
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 10px;
                    background-color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                    color: #475569;
                }
                QPlainTextEdit {
                    background-color: #ffffff;
                    color: #0f172a;
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 8px;
                }
                QPushButton#btnSearchGames {
                    font-weight: bold;
                    background-color: #2563eb;
                    color: #ffffff;
                    border: 1px solid #1d4ed8;
                    border-radius: 4px;
                    padding: 6px 22px;
                }
                QPushButton#btnSearchGames:hover {
                    background-color: #3b82f6;
                }
                QPushButton#btnSearchGames:pressed {
                    background-color: #1d4ed8;
                }
            """)

    def update_category_chips(self):
        """Cleanly highlights which search categories are actively included."""
        pass

    def select_all_categories(self):
        self.chk_enable_info.setChecked(True)
        self.chk_enable_pos.setChecked(True)
        self.chk_enable_mat.setChecked(True)
        self.chk_enable_query.setChecked(True)

    def clear_all_categories(self):
        self.chk_enable_info.setChecked(False)
        self.chk_enable_pos.setChecked(False)
        self.chk_enable_mat.setChecked(False)
        self.chk_enable_query.setChecked(False)

    def mark_info_modified(self):
        if not self._loading:
            self.chk_enable_info.setChecked(True)

    def mark_pos_modified(self):
        if not self._loading:
            self.chk_enable_pos.setChecked(True)

    def mark_mat_modified(self):
        if not self._loading:
            self.chk_enable_mat.setChecked(True)

    def mark_query_modified(self):
        if not self._loading:
            self.chk_enable_query.setChecked(True)

    def _on_cql_preset_selected(self, idx: int):
        if 0 <= idx < len(self.CQL_PRESETS):
            code = self.CQL_PRESETS[idx][1]
            if code:
                self.txt_query.setPlainText(code)
                self.mark_query_modified()
                self._validate_cql_query()

    def _insert_snippet(self, snippet: str):
        cursor = self.txt_query.textCursor()
        cursor.insertText(snippet)
        self.txt_query.setFocus()
        self.mark_query_modified()

    def _on_query_text_changed(self):
        text = self.txt_query.toPlainText().strip()
        if text:
            self.mark_query_modified()
            self._val_timer.start()
        else:
            self.lbl_cql_status.setText("⚡ Ready — Type a query above")
            self.lbl_cql_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #888;")

    def _validate_cql_query(self):
        query = self.txt_query.toPlainText().strip()
        if not query:
            self.lbl_cql_status.setText("⚡ Ready — Type a query above")
            self.lbl_cql_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #888;")
            return

        if self.client and self.client.is_running():
            def on_val(resp: dict):
                if resp.get("status") == "ok":
                    self.lbl_cql_status.setText("✅ Syntax Valid (CQLite Query Engine)")
                    self.lbl_cql_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #2e7d32;")
                else:
                    err = resp.get("error", "Syntax error")
                    data = resp.get("data") or {}
                    pos_info = ""
                    if "line" in data and "column" in data:
                        pos_info = f" [Line {data['line']}, Col {data['column']}]"
                    self.lbl_cql_status.setText(f"❌ {err}{pos_info}")
                    self.lbl_cql_status.setStyleSheet("font-size: 11px; font-weight: 700; color: #d32f2f;")

            try:
                self.client.validate_dsl(query, callback=on_val)
            except Exception as e:
                self.lbl_cql_status.setText(f"Query check: {e}")
        else:
            self.lbl_cql_status.setText("⚡ Query will be evaluated on search execution")
            self.lbl_cql_status.setStyleSheet("font-size: 11px; font-weight: 600; color: #0284c7;")

    def _explain_cql_query(self):
        query = self.txt_query.toPlainText().strip()
        if not query:
            QMessageBox.information(self, "Explain Query", "Please enter a CQL query first.")
            return

        if self.client and self.client.is_running():
            def on_explain(resp: dict):
                if resp.get("status") == "ok":
                    data = resp.get("data", {})
                    summary = data.get("summary") or str(data)
                    QMessageBox.information(self, "CQL Query Explanation", f"Parsed Query Plan:\n\n{summary}")
                else:
                    err = resp.get("error", "Failed to explain query")
                    QMessageBox.warning(self, "Query Explanation", f"Could not parse query:\n{err}")

            try:
                self.client.explain_dsl(query, callback=on_explain)
            except Exception as e:
                QMessageBox.warning(self, "Explain Error", str(e))
        else:
            QMessageBox.information(self, "CQL Query", f"Active Query:\n\n{query}")

    def on_material_preset_changed(self, idx: int):
        if idx == 0:
            return

        self.mark_mat_modified()

        for cb in self.mat_white.values(): cb.setCurrentIndex(0)
        for cb in self.mat_black.values(): cb.setCurrentIndex(0)
        self.chk_opposite_bishops.setChecked(False)
        self.chk_same_bishops.setChecked(False)
        self.rb_final_pos.setChecked(True)

        def set_val(side, pkey, val):
            d = self.mat_white if side == "w" else self.mat_black
            item_idx = d[pkey].findText(str(val))
            if item_idx >= 0: d[pkey].setCurrentIndex(item_idx)

        if idx == 1:
            set_val("w", "q", 0); set_val("w", "r", 1); set_val("w", "b", 0); set_val("w", "n", 0)
            set_val("b", "q", 0); set_val("b", "r", 1); set_val("b", "b", 0); set_val("b", "n", 0)
        elif idx == 2:
            set_val("w", "q", 1); set_val("w", "r", 0); set_val("w", "b", 0); set_val("w", "n", 0)
            set_val("b", "q", 1); set_val("b", "r", 0); set_val("b", "b", 0); set_val("b", "n", 0)
        elif idx == 3:
            set_val("w", "q", 0); set_val("w", "r", 0); set_val("w", "b", 1); set_val("w", "n", 0)
            set_val("b", "q", 0); set_val("b", "r", 0); set_val("b", "b", 0); set_val("b", "n", 1)
        elif idx == 4:
            set_val("w", "q", 1); set_val("w", "r", 0); set_val("w", "b", 0); set_val("w", "n", 0)
            set_val("b", "q", 0); set_val("b", "r", 1); set_val("b", "b", 0); set_val("b", "n", 0)
        elif idx == 5:
            set_val("w", "q", 0); set_val("w", "r", 0); set_val("w", "b", 1); set_val("w", "n", 0)
            set_val("b", "q", 0); set_val("b", "r", 0); set_val("b", "b", 1); set_val("b", "n", 0)
            self.chk_opposite_bishops.setChecked(True)
        elif idx == 6:
            set_val("w", "q", 0)
            set_val("b", "q", 1)
            self.rb_any_move.setChecked(True)
        elif idx == 7:
            set_val("w", "q", 0); set_val("w", "r", 0); set_val("w", "b", 0); set_val("w", "n", 0)
            set_val("b", "q", 0); set_val("b", "r", 0); set_val("b", "b", 0); set_val("b", "n", 0)

    def on_board_fen_changed(self, fen: str):
        self.mark_pos_modified()
        if self.in_fen.text().strip() != fen.strip():
            self.in_fen.blockSignals(True)
            self.in_fen.setText(fen)
            self.in_fen.blockSignals(False)

    def on_fen_text_edited(self, text: str):
        self.mark_pos_modified()
        t = text.strip()
        if t:
            self.board_editor.blockSignals(True)
            self.board_editor.set_fen(t)
            self.board_editor.blockSignals(False)

    def paste_opened_board_position(self):
        """Retrieve board position from any open chessboard window or clipboard."""
        fen = self._get_opened_chessboard_fen()
        if fen:
            self.board_editor.set_fen(fen)
            self.in_fen.setText(fen)
            parts = fen.split()
            if len(parts) >= 2:
                if parts[1] == 'w':
                    self.rb_turn_w.setChecked(True)
                elif parts[1] == 'b':
                    self.rb_turn_b.setChecked(True)
            self.mark_pos_modified()
            return

        clip_text = QApplication.clipboard().text().strip()
        if clip_text and len(clip_text.split("/")) >= 7:
            try:
                board = chess.Board(clip_text)
                self.board_editor.set_fen(board.fen())
                self.in_fen.setText(board.fen())
                if board.turn == chess.WHITE:
                    self.rb_turn_w.setChecked(True)
                else:
                    self.rb_turn_b.setChecked(True)
                self.mark_pos_modified()
                return
            except Exception:
                pass

        QMessageBox.information(
            self,
            "No Active Board Found",
            "No open chessboard window was detected.\n\n"
            "Tip: Open a game in the Analysis Editor or copy a FEN string to the clipboard and click Paste."
        )

    def _get_opened_chessboard_fen(self) -> Optional[str]:
        for widget in QApplication.topLevelWidgets():
            if widget == self:
                continue
            if hasattr(widget, "chessboard"):
                cb = getattr(widget, "chessboard")
                if cb and hasattr(cb, "fen"):
                    try:
                        f = cb.fen()
                        if f: return f
                    except Exception:
                        pass
            if hasattr(widget, "move_manager"):
                mm = getattr(widget, "move_manager")
                if mm and hasattr(mm, "get_board"):
                    try:
                        b = mm.get_board()
                        if b and hasattr(b, "fen"): return b.fen()
                    except Exception:
                        pass
            if hasattr(widget, "board") and widget != self.board_editor:
                b = getattr(widget, "board")
                if b and hasattr(b, "fen"):
                    try:
                        f = b.fen()
                        if f: return f
                    except Exception:
                        pass
        return None

    def reset_all(self):
        self._loading = True
        try:
            self.in_player.clear()
            self.in_white.clear()
            self.in_black.clear()
            self.in_result.setCurrentIndex(0)
            self.in_eco.clear()
            self.in_date.clear()
            self.in_event.clear()
            self.in_site.clear()
            self.chk_include_del.setChecked(True)
            self.chk_only_del.setChecked(False)
            self.board_editor.reset_to_initial()
            self.in_fen.clear()
            self.spin_max_ply.setValue(250)
            self.combo_mat_preset.setCurrentIndex(0)
            for cb in self.mat_white.values(): cb.setCurrentIndex(0)
            for cb in self.mat_black.values(): cb.setCurrentIndex(0)
            self.chk_opposite_bishops.setChecked(False)
            self.chk_same_bishops.setChecked(False)
            self.rb_final_pos.setChecked(True)
            self.combo_cql_preset.setCurrentIndex(0)
            self.txt_query.clear()

            self.chk_enable_info.setChecked(False)
            self.chk_enable_pos.setChecked(False)
            self.chk_enable_mat.setChecked(False)
            self.chk_enable_query.setChecked(False)
            self.update_category_chips()
        finally:
            self._loading = False

    def load_filter(self, f: dict):
        self._loading = True
        try:
            has_info = False
            if f.get("player"): self.in_player.setText(f["player"]); has_info = True
            if f.get("white"): self.in_white.setText(f["white"]); has_info = True
            if f.get("black"): self.in_black.setText(f["black"]); has_info = True
            if f.get("result") and f["result"] != "All":
                idx = self.in_result.findText(f["result"])
                if idx >= 0: self.in_result.setCurrentIndex(idx); has_info = True
            if f.get("eco"): self.in_eco.setText(f["eco"]); has_info = True
            if f.get("date"): self.in_date.setText(f["date"]); has_info = True
            if f.get("event"): self.in_event.setText(f["event"]); has_info = True
            if f.get("site"): self.in_site.setText(f["site"]); has_info = True
            if "include_deleted" in f:
                self.chk_include_del.setChecked(f["include_deleted"])
                if not f["include_deleted"]: has_info = True
            if f.get("only_deleted"):
                self.chk_only_del.setChecked(f["only_deleted"]); has_info = True

            has_pos = False
            if f.get("fen"):
                self.in_fen.setText(f["fen"])
                has_pos = True
            if f.get("turn"):
                t = f["turn"].lower()
                if t in ("w", "white"): self.rb_turn_w.setChecked(True)
                elif t in ("b", "black"): self.rb_turn_b.setChecked(True)
                else: self.rb_turn_any.setChecked(True)
            if f.get("match_mode"):
                m = f["match_mode"].lower()
                if m == "exact": self.rb_mode_exact.setChecked(True)
                elif m == "partial": self.rb_mode_partial.setChecked(True)
                else: self.rb_mode_board.setChecked(True)
            if f.get("max_ply"):
                self.spin_max_ply.setValue(int(f["max_ply"]))

            has_mat = False
            mat = f.get("material")
            if mat:
                mapping_w = {'white_queens': 'q', 'white_rooks': 'r', 'white_bishops': 'b', 'white_knights': 'n', 'white_pawns': 'p'}
                for f_key, pkey in mapping_w.items():
                    if f_key in mat and mat[f_key] is not None:
                        idx = self.mat_white[pkey].findText(str(mat[f_key]))
                        if idx >= 0: self.mat_white[pkey].setCurrentIndex(idx); has_mat = True
                mapping_b = {'black_queens': 'q', 'black_rooks': 'r', 'black_bishops': 'b', 'black_knights': 'n', 'black_pawns': 'p'}
                for f_key, pkey in mapping_b.items():
                    if f_key in mat and mat[f_key] is not None:
                        idx = self.mat_black[pkey].findText(str(mat[f_key]))
                        if idx >= 0: self.mat_black[pkey].setCurrentIndex(idx); has_mat = True
                if mat.get("opposite_bishops"):
                    self.chk_opposite_bishops.setChecked(True)
                    has_mat = True
                elif mat.get("same_bishops"):
                    self.chk_same_bishops.setChecked(True)
                    has_mat = True
                if mat.get("match_any_ply"):
                    self.rb_any_move.setChecked(True)
                else:
                    self.rb_final_pos.setChecked(True)

            has_query = False
            q_str = f.get("query") or f.get("cql")
            if q_str:
                self.txt_query.setPlainText(q_str)
                has_query = True

            self.chk_enable_info.setChecked(has_info)
            self.chk_enable_pos.setChecked(has_pos)
            self.chk_enable_mat.setChecked(has_mat)
            self.chk_enable_query.setChecked(has_query)
            self.update_category_chips()

            if has_query:
                self.tabs.setCurrentIndex(3)
            elif has_pos and not has_info and not has_mat:
                self.tabs.setCurrentIndex(1)
            elif has_mat and not has_info and not has_pos:
                self.tabs.setCurrentIndex(2)
            else:
                self.tabs.setCurrentIndex(0)
        finally:
            self._loading = False

    def _on_tab_changed(self, idx: int):
        if idx == 0:
            self.chk_enable_info.setChecked(True)
        elif idx == 1:
            self.chk_enable_pos.setChecked(True)
        elif idx == 2:
            self.chk_enable_mat.setChecked(True)
        elif idx == 3:
            self.chk_enable_query.setChecked(True)
        self.update_category_chips()

    def get_filter_dict(self) -> dict:
        f = {}
        active_tab = self.tabs.currentIndex()

        # 1. Game Info Tab
        if self.chk_enable_info.isChecked() or active_tab == 0:
            p = self.in_player.text().strip()
            if p: f["player"] = p
            w = self.in_white.text().strip()
            if w: f["white"] = w
            b = self.in_black.text().strip()
            if b: f["black"] = b
            res = self.in_result.currentText()
            if res != "All": f["result"] = res
            eco = self.in_eco.text().strip()
            if eco: f["eco"] = eco
            dt = self.in_date.text().strip()
            if dt: f["date"] = dt
            ev = self.in_event.text().strip()
            if ev: f["event"] = ev
            st = self.in_site.text().strip()
            if st: f["site"] = st
            f["include_deleted"] = self.chk_include_del.isChecked()
            f["only_deleted"] = self.chk_only_del.isChecked()
        else:
            f["include_deleted"] = True
            f["only_deleted"] = False

        # 2. Position Tab
        if self.chk_enable_pos.isChecked() or active_tab == 1 or bool(self.in_fen.text().strip()):
            fen = self.in_fen.text().strip()
            if fen:
                f["fen"] = fen
                f["turn"] = "w" if self.rb_turn_w.isChecked() else ("b" if self.rb_turn_b.isChecked() else "any")
                f["match_mode"] = "exact" if self.rb_mode_exact.isChecked() else ("partial" if self.rb_mode_partial.isChecked() else "board_only")
                f["max_ply"] = self.spin_max_ply.value()

        # 3. Material Tab
        if self.chk_enable_mat.isChecked() or active_tab == 2:
            mat = {}
            def parse_val(cb):
                t = cb.currentText()
                return None if t == "Any" else int(t)

            mapping_w = {'q': 'white_queens', 'r': 'white_rooks', 'b': 'white_bishops', 'n': 'white_knights', 'p': 'white_pawns'}
            for pkey, f_key in mapping_w.items():
                v = parse_val(self.mat_white[pkey])
                if v is not None: mat[f_key] = v

            mapping_b = {'q': 'black_queens', 'r': 'black_rooks', 'b': 'black_bishops', 'n': 'black_knights', 'p': 'black_pawns'}
            for pkey, f_key in mapping_b.items():
                v = parse_val(self.mat_black[pkey])
                if v is not None: mat[f_key] = v

            if self.chk_opposite_bishops.isChecked():
                mat["opposite_bishops"] = True
            elif self.chk_same_bishops.isChecked():
                mat["same_bishops"] = True

            if mat:
                mat["match_any_ply"] = self.rb_any_move.isChecked()
                mat["max_ply"] = self.spin_max_ply.value()
                f["material"] = mat

        # 4. Query Language (CQL) Tab
        if self.chk_enable_query.isChecked() or active_tab == 3 or bool(self.txt_query.toPlainText().strip()):
            q_text = self.txt_query.toPlainText().strip()
            if q_text:
                f["query"] = q_text

        return f

    def _is_dark(self) -> bool:
        if self.parent() is not None and hasattr(self.parent(), "is_dark"):
            return bool(self.parent().is_dark)
        return QSettings("QChessApp", "Theme").value("theme", "dark") == "dark"
