# Codebase Modularization & Architecture Plan (Python GUI)

> **Document Status**: Analysis & Proposal  
> **Target Scope**: File arrangement, structural decomposition of monolithic files, separation of concerns, and component deduplication in `src/` and `gchessboard/`.  
> **Goal**: Improve code maintainability, testability, readability, and reduce development friction without breaking existing functionality.

---

## 1. Overview of File Size & Complexity Hotspots

Several key files in the codebase have grown into multi-responsibility monoliths (1,000 to 1,700+ lines), blending UI layout, domain logic, event handling, timers, backend communications, and painting routines.

| File Path | Lines | Current Responsibilities | Target Decomposition |
|---|---|---|---|
| `src/gui/app.py` | **1,740** | Main analyzer window, dock management, engine sync, autoplay, game play/training modes, PGN saving, matching plies navigation, theme handling | **5 modular components** |
| `gchessboard/src/painter_board.py` | **1,517** | Board widget, glyph font rasterization, piece drawing, highlights, shape drawing (arrows/circles), drag-and-drop, animations, premoves | **4 modular components + shared cache** |
| `src/gui/home_window.py` | **1,334** | Main hub window, welcome screen, database browser, toolbar/menus, SCID progress handlers, preview loading, search filters | **4 modular components** |
| `src/gui/dialogs/advanced_search_dialog.py` | **1,112** | 4 full tabs (Header info, Position board editor, Material filters, CQL query editor), presets, live validator, chip headers | **Sub-package `search_dialog/` with 4 tab modules** |
| `src/gui/widgets/painter_pgn_browser.py` | **1,049** | Token model, flow layout calculation, custom QPainter rendering, mouse hover/clicks, comment dialogs, NAG rendering | **3 modular components** |
| `src/gui/widgets/repertoire_tree_widget.py` | **951** | Tree view, drag-and-drop reparenting, dialogs (New/Move/Rename), SQLite repository wiring, context menus | **Separate dialogs and tree controller** |
| `src/core/opening_explorer.py` | **732** | Domain logic mixed with PyQt5 GUI widgets (`PercentageBar`, `OpeningExplorerHeader`, `MoveItemWidget`, `OpeningExplorerWidget`) | **Move UI to `gui/widgets/`, keep logic in `core/`** |
| `src/gui/widgets/game_analytics.py` | **682** | `EvaluationChart`, `MoveClassificationChart`, `GameAccuracyWidget` all in a single file | **Separate chart widgets** |

---

## 2. Detailed Modularization Strategy

### F1. Decomposition of `src/gui/app.py` (1,740 lines)

#### Current State
`ChessApp` acts as the "God Object" of the analysis environment. It handles:
- Creating and laying out 5+ dock widgets and central board
- Engine analysis debouncing and multi-PV throttling
- Game / Train playing mode state machine (Engine vs Engine, Player vs Engine)
- Move navigation and matching plies stepping
- PGN file importing, exporting, and saving
- Dialog management (Headers, Settings, Board Editor, Variations)

#### Proposed Architecture
```
src/gui/
├── app.py                         # Slim QMainWindow shell & high-level coordinator (~300 lines)
└── app_components/
    ├── app_dock_manager.py        # Dock instantiation, arrangement, sizing, and state save/restore
    ├── app_navigation_controller.py # Move cursor jumping, autoplay timer, match plies stepping
    ├── app_game_mode_controller.py  # Play vs Engine, training, self-play timers and state transitions
    ├── app_menu_builder.py        # Menu bar, toolbars, and action definitions
    └── app_file_handler.py        # Save PGN, export board image, edit headers, repertoire persistence
```

#### Benefits
- Each component can be unit-tested in isolation.
- `ChessApp` becomes a clean coordinator with clear delegation.
- Navigation logic and game mode logic are decoupled from window layout.

---

### F2. Decomposition of `gchessboard/src/painter_board.py` (1,517 lines)

#### Current State
`PainterChessBoard` contains all drawing, math, state, event handling, and animation logic in one massive file.

#### Proposed Architecture
```
gchessboard/src/
├── painter_board.py               # Main PainterChessBoard QWidget (~350 lines)
├── glyph_cache.py                 # Shared font loading & QPixmap rasterization (used by painter & static boards)
├── rendering/
│   ├── board_renderer.py          # Drawing squares, coordinates, legal indicators, dragged piece
│   └── shape_renderer.py          # Drawing arrows, circles, crosses, custom highlights
├── interaction/
│   ├── board_input_handler.py     # Mouse press/move/release, drag & drop, right-click shape drawing
│   └── premove_handler.py         # Premove queueing, verification, and visual indication
└── animation/
    └── board_animator.py          # Move animation interpolation, QVariantAnimation handling
```

#### Benefits
- Reuses the `glyph_cache.py` across `PainterChessBoard` and `StaticChessBoard` without code duplication.
- Separates input handling (mouse/drag) from pure rendering math (painting squares/arrows).

---

### F3. Decomposition of `src/gui/home_window.py` (1,334 lines)

#### Current State
`HomeWindow` manages both the Welcome screen and the Database Browser, plus all SCID backend communication, progress bars, column configurations, recent files, and preview dock routing.

#### Proposed Architecture
```
src/gui/
├── home_window.py                 # QMainWindow shell & page switcher (~250 lines)
└── home_components/
    ├── welcome_view.py            # Welcome screen, recent database cards, quick action buttons
    ├── database_browser_view.py   # Database browser toolbar, status bar, and dock assembly
    ├── home_scid_controller.py    # SCID backend orchestration (search, import, export, index builders)
    └── recent_files_manager.py    # Persistent recent files list and thumbnail management
```

#### Benefits
- Keeps the browser UI separate from the backend communication layer.
- Simplifies modifying or restyling the welcome screen without touching table/query code.

---

### F4. Modularization of `src/gui/dialogs/advanced_search_dialog.py` (1,112 lines)

#### Current State
Contains all 4 complex search tabs inside a single 1,100+ line file with extensive UI setup and event handlers.

#### Proposed Architecture
```
src/gui/dialogs/search/
├── __init__.py
├── advanced_search_dialog.py      # Main dialog shell, header chips, Execute/Cancel actions (~200 lines)
├── search_presets.py              # CQL presets and query templates catalog
└── tabs/
    ├── game_info_tab.py           # Header filter inputs (Players, Result, ECO, Date, Event, Site)
    ├── position_tab.py            # Board editor, FEN input, depth & ply controls
    ├── material_tab.py            # Piece count spinboxes, bishop colors, material balance
    └── cql_query_tab.py           # CQLite editor, validation timer, syntax helper buttons
```

#### Benefits
- Each tab is self-contained and easily maintainable.
- CQL query presets and helpers can be edited without touching UI layout code.

---

### F5. Modularization of `src/gui/widgets/painter_pgn_browser.py` (1,049 lines)

#### Current State
Handles token building, geometric flow layout measurement, QPainter rendering, comment editing dialogs, and user interaction in a single file.

#### Proposed Architecture
```
src/gui/widgets/pgn_browser/
├── __init__.py
├── painter_pgn_browser.py         # QScrollArea container, keyboard shortcuts, context menus (~250 lines)
├── pgn_layout_engine.py           # Token parsing, font metrics measurement, word-wrap flow layout
├── pgn_canvas.py                  # Direct QPainter drawing (moves, evaluations, NAG glyphs, inline diagrams)
└── comment_dialog.py              # Extracted comment & annotation editing dialog
```

---

### F6. Clean Separation of GUI Widgets from `src/core/`

#### Current State
`src/core/opening_explorer.py` currently defines PyQt5 UI classes:
- `OpeningExplorerHeader`
- `PercentageBar`
- `MoveItemWidget`
- `OpeningExplorerWidget`

#### Proposed Architecture
1. Move UI widgets to `src/gui/widgets/opening_explorer_widget.py`.
2. Keep only domain logic, tree models, and query builders in `src/core/opening_explorer.py`.

---

### F7. Deduplication of Reusable UI Components

#### Current State
The 3-segment outcome percentage bar (White win / Draw / Black win) is implemented 3 separate times:
1. `PercentageBar` in `src/core/opening_explorer.py`
2. `ContinuationPercentageBar` in `src/gui/widgets/continuations_widget.py`
3. `EndgamePercentageBar` in `src/gui/widgets/endgames_widget.py`

#### Proposed Architecture
Create a single, robust `OutcomeDistributionBar` widget in `src/gui/widgets/common/outcome_bar.py` and reuse it across Opening Explorer, Continuations, and Endgames.

---

### F8. Cleanup of Dead & Legacy Files

| File | Status | Action |
|---|---|---|
| `src/gui/widgets/chessboard_old.py` (465 lines) | Unused legacy code | Remove or archive |
| `gchessboard/experiments/painter_chessboard_backup.py` | Backup file | Remove or move to experiments archive |
| `src/gui/widgets/pgn_browser.py` | Legacy QTextBrowser widget | Extract reusable `CommentDialog` and deprecate HTML browser |

---

## 3. Implementation Roadmap & Guardrails

To ensure complete safety and avoid regressions when these refactorings are executed in the future:

1. **Step-by-Step Refactoring**: Refactor one monolith at a time (e.g. `advanced_search_dialog` first, then `app.py`).
2. **Preserve Public APIs & Signatures**: All decomposed classes will maintain backward-compatible signal signatures and method interfaces.
3. **Automated Test Validation**: Run the existing test suite (`pytest tests/ gchessboard/tests/`) after each modularization step.
