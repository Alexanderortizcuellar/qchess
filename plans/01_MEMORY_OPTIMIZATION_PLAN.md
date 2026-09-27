# Memory Optimization Plan (Python GUI & Data Layer)

> **Document Status**: Analysis & Proposal  
> **Target Scope**: Python GUI (`src/`, `gchessboard/`), backend client data exchange, and state management.  
> **Goal**: Eliminate memory leaks, bound dynamic caches, minimize object churn, and optimize data handling during long user sessions with large chess databases.

---

## 1. Executive Summary

A comprehensive scan of the Python codebase identified key areas where memory accumulates over time without eviction, processes/threads are not properly reaped, and excessive object allocations cause high garbage collection (GC) pressure.

| ID | Issue Area | Severity | Impact | Primary Files |
|---|---|---|---|---|
| **M1** | Unbounded Game List Table Chunk Cache | **High** | Linear RAM growth while scrolling large databases (up to 1M+ games) | `src/gui/widgets/game_list_table.py` |
| **M2** | Orphan Engine Processes on Window Close | **High** | Subprocesses (`stockfish.exe`) and memory retained per closed editor window | `src/gui/app_controller.py`, `src/gui/app.py`, `src/core/engine.py` |
| **M3** | Leaked Callbacks in Asynchronous Backend Client | **Medium** | Closures and request payloads accumulate if requests are dropped/cancelled | `src/core/scid_client.py`, `src/gui/home_window.py` |
| **M4** | Unbounded QPixmap & Diagram Caches | **Medium** | Infinite memory growth when browsing many diagrams or resizing windows | `src/gui/widgets/painter_pgn_browser.py`, `gchessboard/src/static_board.py` |
| **M5** | Repeated Application Font Registrations | **Low-Medium** | Leaks QFontDatabase table entries on repeated board instantiation | `gchessboard/src/painter_board.py` |
| **M6** | Full Game Tree Mapping Regeneration on Cursor Navigation | **Medium** | High heap object churn (stack frames, list rebuilds) on every arrow key press | `src/core/move_manager.py`, `src/core/pgn_to_html.py` |
| **M7** | Missing `__slots__` on High-Frequency Data Models | **Medium** | 50%+ extra memory per token/node/highlight instance | `gchessboard/src/models.py`, `src/gui/widgets/analysis_widget.py`, `painter_pgn_browser.py` |
| **M8** | High-Frequency Regex & Dict Churn in Engine Parser | **Low-Medium** | High allocation rate (~50+ dicts/sec during multi-threaded analysis) | `src/core/engine.py` |
| **M9** | `QGraphicsScene` Highlight Item Churn | **Low-Medium** | Continuous creation and removal of QGraphicsItem instances on hover/selection | `gchessboard/src/scene.py` |

---

## 2. Detailed Findings & Proposed Solutions

### M1. Unbounded Game List Table Cache (`cached_chunks`)

#### Finding
In `GameListTableModel` (`src/gui/widgets/game_list_table.py`):
```python
self.cached_chunks: Dict[int, list] = {}  # page_number -> list of 100 game dicts
```
When a user scrolls through a database containing 500,000 to 2,000,000 games, chunks are downloaded in blocks of 100 games and inserted into `self.cached_chunks`. There is **no cache size limit, eviction policy, or sliding window**.
- 10,000 rows scrolled = 100 chunks = 10,000 dictionaries retained.
- 100,000 rows scrolled = 1,000 chunks = 100,000 dictionaries retained.
Memory is only released when the database is closed or filters are completely reset.

#### Recommended Optimization
1. **LRU Cache / Sliding Window**:
   - Replace the plain `dict` with an `OrderedDict` or `collections.deque` / LRU structure with a configurable maximum (e.g., `MAX_CACHED_PAGES = 50` chunks = 5,000 games).
   - When `len(self.cached_chunks) > MAX_CACHED_PAGES`, pop the least recently accessed page (`self.cached_chunks.popitem(last=False)`).
2. **Compact Row Representation**:
   - Instead of storing a full dictionary with 15+ string keys per game, store lightweight tuples/namedtuples or slotted dataclasses (`GameSummaryRecord`) to reduce dictionary hash table overhead by ~60%.

---

### M2. Engine Subprocess & Thread Leakage on Window Close

#### Finding
In `src/gui/app_controller.py`:
When an editor window is closed:
```python
def _on_editor_closed(self, editor: ChessApp):
    if editor in self._editors:
        self._editors.remove(editor)
```
In `src/gui/app.py`:
```python
def closeEvent(self, a0):
    ...
    self.engine.stop_search()
    self.clear_pending_analysis()
    a0.accept()
```
`self.engine.stop_search()` sends `"stop"` to Stockfish, but does **not terminate** the `QProcess` or release OS process handles and engine hash tables (configured at 16MB–512MB per engine instance). If a user opens and closes 10 games from the database browser, 10 `stockfish.exe` background processes remain resident in Windows Task Manager, holding memory and threads until the whole application exits.

#### Recommended Optimization
1. In `ChessApp.closeEvent` or `app_controller._on_editor_closed`:
   - Explicitly call `editor.engine.quit()` (or `kill()` / `terminate()`) to cleanly exit UCI and reap the subprocess.
   - Stop and disconnect all active `QTimer` instances (`autoplay_timer`, `self_play_timer`, `analysis_update_timer`, `engine_debounce_timer`).
2. Alternatively, implement a **Shared Engine Pool**:
   - Keep a single managed engine instance (or a small worker pool) managed by `ApplicationController` rather than spawning a separate engine process per window.

---

### M3. Dangling Callback Closures in `ScidClient`

#### Finding
In `src/core/scid_client.py`:
```python
self.pending_callbacks: Dict[int, Callable[[dict], None]] = {}
```
In `src/gui/home_window.py`:
`_load_selected_row_preview` generates nested closures (`on_chunk_ready`, `on_pgn`) containing references to large `payload` dicts, table models, and window references.
If:
- The backend process is restarted or busy,
- A search session is cancelled or replaced with a new query,
- A request ID is dropped or produces an error,
the callback closures remain in `self.pending_callbacks` indefinitely, preventing referenced objects from being garbage collected.

#### Recommended Optimization
1. **Callback Timeout & Pruning**:
   - Store timestamp with callback: `self.pending_callbacks[req_id] = (callback, timestamp)`.
   - Periodically prune pending callbacks older than 30 seconds.
2. **Clear on Process Stop / Reset**:
   - In `ScidClient.stop()`, clear all entries from `pending_callbacks` and log cancelled requests.
3. **Cancel Prior In-Flight Preview Requests**:
   - Maintain a single active `_pending_preview_req_id`. When a new row is selected, invalidate/drop previous preview callbacks before issuing a new one.

---

### M4. Unbounded QPixmap & Diagram Caches

#### Finding
1. `src/gui/widgets/painter_pgn_browser.py`:
   ```python
   self._diagram_cache = {}  # (fen, size, is_dark) -> QPixmap
   ```
   Never evicted or cleared when loading a new PGN or navigating games.
2. `gchessboard/src/static_board.py`:
   ```python
   _GLOBAL_PIXMAP_CACHE: Dict[Tuple[str, int], Dict[Tuple[chess.PieceType, chess.Color], QPixmap]] = {}
   ```
   Keyed by `(font_family, int(sq_size))`. If a user smoothly resizes a window containing a static board or diagram, a new pixmap set is created for every single pixel step (e.g. sizes 40 to 120 = 80 distinct dictionary sets = 960 QPixmaps cached permanently).

#### Recommended Optimization
1. Use `collections.OrderedDict` with a maximum capacity (e.g. `MAX_DIAGRAMS = 64`) for `_diagram_cache`.
2. Clear or reset `_diagram_cache` when `set_game()` / `update_pgn()` is called on the browser.
3. Quantize square sizes in `_GLOBAL_PIXMAP_CACHE` to discrete step intervals (e.g., multiples of 4 or 8 pixels) or clamp cache size to the top 8 most recently used square sizes.

---

### M5. Repeated Application Font Registrations

#### Finding
In `gchessboard/src/painter_board.py`:
```python
def __init__(self, font_file: str = None, parent=None):
    font_path = font_file or self._DEFAULT_FONT_FILE
    self._font_family: str = _load_font(font_path)
```
Where `_load_font()` calls `QFontDatabase.addApplicationFont(font_path)`.
Every time a `PainterChessBoard` widget is created (e.g., board editors, preview panels, dialogs), a redundant font registration is performed in Qt's font table without checking if it was already loaded.

#### Recommended Optimization
- Cache the loaded font family at module level (as done in `static_board.py` with `_CACHED_FONT_FAMILY`), ensuring `QFontDatabase.addApplicationFont` is executed at most once across the entire application runtime.

---

### M6. Full Game Tree Mapping Regeneration on Cursor Navigation

#### Finding
In `src/core/move_manager.py`:
Every navigation call (`undo`, `redo`, `jump_to`, `goto_ply`, `jump_to_start`, `jump_to_end`) invokes:
```python
def create_mapping(self):
    self.nodes = flatten_nodes_pgn_order(self.game)
    self.pgnChanged.emit("")
    self.activeNodeChanged.emit()
```
`flatten_nodes_pgn_order()` in `src/core/pgn_to_html.py`:
- Allocates a new stack of `Frame` objects.
- Iterates and recreates the `self.nodes` list from scratch.
- Modifies `n.flat_index = i` on every node.
When simply browsing moves (read-only traversal), the tree structure has not changed at all. Rebuilding the entire node list on every keystroke causes unnecessary CPU load and memory churn.

#### Recommended Optimization
1. **Separate Structural Mutation from Active Node Cursor**:
   - Only call `create_mapping()` when moves/variations/comments are added, deleted, or reordered (write operations).
   - For read-only navigation (`jump_to`, `undo`, `redo`, `goto_ply`), update `self.current_node` and emit only `activeNodeChanged`.
2. **Flattened Tree Invalidation Flag**:
   - Cache `self.nodes` and only re-flatten when `self.is_dirty` or tree structure is modified.

---

### M7. Missing `__slots__` on High-Frequency Data Models

#### Finding
The following classes are instantiated in large numbers during PGN rendering, engine analysis, and board painting:
- `gchessboard/src/models.py`: `BoardState`, `BoardHighlight`, `BoardShape`, `PreviewConfig`, `MovableConfig`, `AnimationConfig`
- `src/gui/widgets/painter_pgn_browser.py`: `Token`, `PaintBlock`
- `src/gui/widgets/analysis_widget.py`: `EngineMoveToken`, `EngineLineData`

None of these classes define `__slots__` or `@dataclass(slots=True)`. In Python, standard object instances have an internal `__dict__` overhead (~150+ bytes per instance).

#### Recommended Optimization
- Add `__slots__` (or `@dataclass(slots=True)`) to all token, geometry, highlight, and shape data classes.
- Expected reduction: ~50-60% memory savings for token/geometry collections and faster attribute access.

---

### M8. High-Frequency UCI Parsing Allocations

#### Finding
In `src/core/engine.py`:
On every `info` line output by Stockfish (which can occur dozens of times per second):
- Runs 5 separate `re.search` regular expressions.
- Allocates new strings, lists, and dicts (`info = { ... }`).
- Emits Qt signals on every line.

#### Recommended Optimization
1. **Compile Regexes Once**: Store compiled regex patterns (`_DEPTH_RE = re.compile(...)`, etc.) at module level.
2. **Fast Token Scan**: Use simple string partitioning/splitting (`line.split()`) which is 3-5x faster and lighter than running multiple regex passes.
3. **Throttle / Buffer at Engine Layer**: Filter intermediate search depths below a minimum reporting threshold (or debounce before Qt signal emission).

---

## 3. Implementation Priority Matrix

```
Priority 1 (Immediate Stability & Leak Prevention):
├── [M2] Ensure ChessEngine processes & timers terminate on window close
├── [M3] Timeout & clear pending callbacks in ScidClient
└── [M1] Add LRU bounds (e.g. max 50 chunks) to GameListTableModel

Priority 2 (Memory Growth & Cache Bounds):
├── [M4] Add LRU / capacity limits to QPainterBrowser and StaticChessBoard caches
├── [M5] Globalize font registration in PainterChessBoard
└── [M6] Avoid flattening the PGN tree on read-only move navigation

Priority 3 (Micro-optimizations & Churn Reduction):
├── [M7] Add __slots__ to high-frequency dataclasses and tokens
└── [M8] Optimize UCI info line parsing in ChessEngine
```
