# QChess Python GUI Optimization & Modularization Plans

This directory contains technical analysis and architecture proposals focused exclusively on the Python codebase (`src/`, `gchessboard/`, and Qt GUI layer).

---

## Documents

### 1. [01_MEMORY_OPTIMIZATION_PLAN.md](file:///C:/Users/ASUS/programming/qt_programs/chess/qchess/plans/01_MEMORY_OPTIMIZATION_PLAN.md)
Detailed findings and mitigation strategies for memory usage, cache bounds, object churn, and process management:
- **M1: Unbounded Table Cache (`cached_chunks`)** — Adding LRU sliding window bounds for 1M+ game databases.
- **M2: Subprocess Lifecycle** — Ensuring Stockfish engine processes and timers terminate cleanly on editor window close.
- **M3: Callback Leak Prevention** — Adding timeouts and cleanup for asynchronous SCID backend request callbacks.
- **M4: Diagram & Pixmap Cache Bounds** — Capping QPixmap memory usage during window resizing and diagram rendering.
- **M5: Font Registration Deduplication** — Globalizing font loading to prevent `QFontDatabase` table bloat.
- **M6: Game Tree Flattening Optimization** — Decoupling read-only cursor navigation from full PGN tree regeneration.
- **M7: Data Model `__slots__`** — Reducing object overhead across high-volume token, geometry, and highlight classes.
- **M8: UCI Parser Optimization** — Streamlining high-frequency engine analysis parsing.

### 2. [02_CODEBASE_MODULARIZATION_AND_ARCHITECTURE_PLAN.md](file:///C:/Users/ASUS/programming/qt_programs/chess/qchess/plans/02_CODEBASE_MODULARIZATION_AND_ARCHITECTURE_PLAN.md)
Structural decomposition strategy for large monolithic files to improve maintainability and developer velocity:
- **F1: `src/gui/app.py` (1,740 lines)** — Decomposing into slim `QMainWindow` coordinator + dedicated dock, navigation, game mode, and file controllers.
- **F2: `gchessboard/src/painter_board.py` (1,517 lines)** — Extracting rendering, input handling, shape drawing, and shared glyph cache.
- **F3: `src/gui/home_window.py` (1,334 lines)** — Splitting welcome view, database browser, and backend orchestration controller.
- **F4: `src/gui/dialogs/advanced_search_dialog.py` (1,112 lines)** — Modularizing into a `search_dialog/` sub-package with dedicated tab components.
- **F5: `src/gui/widgets/painter_pgn_browser.py` (1,049 lines)** — Separating layout measurement from QPainter rendering canvas.
- **F6: Domain vs. UI Layering** — Moving UI widgets out of `src/core/opening_explorer.py` into `src/gui/widgets/`.
- **F7: Component Deduplication** — Unifying repeated outcome percentage bars into a single reusable widget.
- **F8: Dead Code Cleanup** — Pruning unreferenced legacy widgets (`chessboard_old.py`).

---

## Action Plan & Phasing

```mermaid
flowchart TD
    subgraph Phase 1: High Priority Memory & Leaks
        A1[M2: Engine Process Termination on Close] --> A2[M3: ScidClient Callback Cleanup]
        A2 --> A3[M1: Table Model LRU Cache Limits]
    end

    subgraph Phase 2: Structural Decomposition
        B1[F4: Advanced Search Dialog Tabs Split] --> B2[F1: App Window Controllers Split]
        B2 --> B3[F3: PainterBoard Rendering & Input Split]
        B3 --> B4[F2: Home Window Views Split]
    end

    subgraph Phase 3: Performance & Churn Tuning
        C1[M6: Avoid Tree Flattening on Navigation] --> C2[M7: Add __slots__ to Models/Tokens]
        C2 --> C3[M4: LRU Limits on Diagram & Pixmap Caches]
        C3 --> C4[F7: Deduplicate Reusable Outcome Bar]
    end

    Phase 1 --> Phase 2 --> Phase 3
```

> [!NOTE]
> No functional code changes have been applied yet. All recommendations are ready for phased execution upon review.
