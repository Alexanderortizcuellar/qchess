# qchess

A feature-rich, modern chess application built with Python, PyQt5, and Rust, featuring a two-window database hub architecture, instant SQLite-backed PGN indexing, UCI engine analysis, and an ultra-fast custom `QPainter` PGN browser.

![Chessboard](assets/icon.png)

## Key Features

### 🏛️ Two-Window Architecture & Application Controller
- **Home Hub (`HomeWindow`)**:
  - Landing screen with quick-action launch buttons and recent database shortcuts.
  - Built-in PGN database browser with fast virtualized scrolling.
  - Collapsible dock panels including the new Repertoire Manager.
  - Decoupled from analysis mode via an `ApplicationController`.
- **Game & Analysis Editor (`ChessApp`)**:
  - Dedicated window for deep game analysis, engine evaluation, and move tree editing.
  - Full support for nested variations, inline move comments, and positional setup.

### 📚 Integrated Repertoire Manager
- **Hierarchical Library Structure**: Organize opening theory in collapsible, nested folders and repertoire nodes.
- **PGN as the Source of Truth**: Repertoire data is stored directly as full PGN text in a lightweight SQLite database (`~/.qchess/repertoires.db`), avoiding brittle custom move-tree serialization formats.
- **Interactive Drag & Drop**: Move repertoires and folders across branches with instant SQLite persistence.
- **Rich Context Management**: Create folders/subfolders, import/export PGNs, rename, delete, and open lines directly in the analysis editor.
- **Seamless Edit Cycle**: Opening a repertoire routes its PGN to the `ChessApp` analyzer, where edits can be saved directly back to the database with a single keystroke (`Ctrl+Shift+R` or **File → Save Repertoire**).

### ⚡ Blazing-Fast PGN Indexer (Rust Submodule)
- Powered by a custom Rust CLI tool (`pgn-indexer`) leveraging memory mapping (`memmap2`) and SQLite bulk transactions.
- Extracts game metadata and byte offsets (`offset`, `length`) directly from `.pgn` files into indexed SQLite sidecars (`.pgn.db`).
- **Instant Seek & Load**: Open individual games instantly without re-parsing giant PGN files.

### 📜 Optimized `QPainter` PGN Browser
- Custom viewport-based `QPainter` text layout engine designed for smooth performance on large annotated PGNs.
- **Node-Level SAN Caching**: SAN move notation, move numbers, and turn flags are computed once upon node creation (`node.san`), eliminating expensive runtime $O(N^2)$ board replays.
- Supports compact inline evaluation annotations (`+0.4`, `-1.2`, `#3`) and move classifications.

### 🖥️ Flexible Layout & Dock Persistence
- Full dock nesting (`AllowNestedDocks`) and grouped tab dragging (`GroupedDragging`).
- Move, split, float, or tab docks (Repertoire Manager, Engine Analysis, PGN Browser, Opening Explorer, Game Analytics, Game Review).
- **Layout Memory**: Saves custom window state, dock arrangements, and splitter proportions across sessions using `QSettings`.
- **On-Demand Dock Computation**: Heavy calculations for hidden docks are skipped automatically until the dock is toggled visible.

### ♟️ Core Chess Capabilities
- **High-Quality SVG Chessboard**: Responsive visuals, drag-and-drop movement, move highlights, and smooth piece animations.
- **UCI Engine Integration**: Async Stockfish evaluation bar, multi-PV analysis, and customizable search parameters.
- **Opening Explorer**: Integrated opening statistics and book move lookups.

## Installation

### Prerequisites

- Python 3.8+
- [Rust & Cargo](https://rustup.rs/) (to compile the `pgn-indexer` binary)
- [Stockfish](https://stockfishchess.org/download/) (or any UCI-compatible engine) available on your system path.

### Setup

1. Clone the repository with submodules:
   ```bash
   git clone --recursive https://github.com/alexanderortizcuellar/qchess.git
   cd qchess
   ```

2. Build the Rust `pgn-indexer` binary:
   ```bash
   cd pgn-indexer
   cargo build --release
   cd ..
   ```

3. Install Python dependencies:
   ```bash
   pip install PyQt5 chess qtawesome
   ```

## How to Run

Launch the application using:

```bash
python main.py
```

## Project Structure

- `main.py`: Root launcher.
- `src/main.py`: Application bootstrapper and stylesheet initializer.
- `src/gui/`: User interface components.
  - `home_window.py`: Database browser landing page and dock manager.
  - `app_controller.py`: Orchestrator managing two-window lifecycle and signal routing.
  - `app.py`: Main game editor and analysis window (`ChessApp`).
  - `widgets/`: Reusable widgets (`repertoire_tree_widget.py`, `chessboard.py`, `painter_pgn_browser.py`, `game_list_table.py`, `eval_bar.py`, etc.).
- `src/core/`: Core logic modules.
  - `repertoire_db.py`: SQLite-backed repertoire repository (adjacency-list tree + PGN payload).
  - `indexer.py`: Asynchronous `QProcess` runner for `pgn-indexer.exe`.
  - `move_manager.py`: Move tree navigation, SAN caching, and PGN state management.
  - `engine.py`: UCI Stockfish client.
  - `opening_explorer.py`: Opening explorer logic.
- `pgn-indexer/`: High-performance Rust PGN indexer submodule.

## Technical Stack

- **GUI Framework**: PyQt5
- **Indexing Engine**: Rust (`memmap2`, `rusqlite`)
- **Database Backend**: SQLite (`sqlite3`)
- **Chess Engine / Logic**: `python-chess`
- **Icons & Theme**: QtAwesome, Custom QSS Stylesheet
