import os
import sys
import json
import time
import queue
import shutil
import subprocess
import threading
from typing import Optional, Dict, Any, Callable, Tuple

from PyQt5.QtCore import QObject, pyqtSignal


def find_scid_mgr_executable() -> Optional[str]:
    """Resolve the scid_mgr executable path across common build locations."""
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(app_dir)

    names = ["scid-mgr.exe", "scid_mgr.exe", "scid-mgr", "scid_mgr"]
    folders = [
        os.path.join(project_root, "scid-mgr", "target", "release"),
        os.path.join(project_root, "scid-mgr", "target", "debug"),
        os.path.join(os.path.dirname(project_root), "scid-mgr", "target", "release"),
        os.path.join(os.path.dirname(project_root), "scid-mgr", "target", "debug"),
        os.path.join(project_root, "target", "release"),
        os.path.join(project_root, "target", "debug"),
    ]

    for folder in folders:
        for name in names:
            p = os.path.join(folder, name)
            if os.path.isfile(p):
                return p

    for name in names:
        w = shutil.which(name)
        if w:
            return w

    return None


class ScidClient(QObject):
    """
    Manages long-running Rust scid-mgr process communicating over stdin/stdout
    with non-blocking asynchronous request/response queues.
    """
    response_received = pyqtSignal(dict)
    search_progress = pyqtSignal(dict)
    import_progress = pyqtSignal(dict)
    export_progress = pyqtSignal(dict)
    pos_index_progress = pyqtSignal(dict)
    tree_index_progress = pyqtSignal(dict)
    continuations_progress = pyqtSignal(dict)
    endgame_index_progress = pyqtSignal(dict)
    process_error = pyqtSignal(str)
    process_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: Optional[subprocess.Popen] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.writer_thread: Optional[threading.Thread] = None
        self.write_queue: queue.Queue = queue.Queue()
        self.running = False
        self.request_id = 0
        self.pending_callbacks: Dict[int, Tuple[Callable[[dict], None], float]] = {}

        # Safely dispatch pending callbacks on the main GUI thread via Qt signal delivery
        self.response_received.connect(self._dispatch_response_on_main_thread)

    def _prune_stale_callbacks(self, timeout_sec: float = 60.0):
        """Remove pending callbacks older than timeout to prevent closure memory leaks."""
        now = time.time()
        stale_keys = [
            req_id for req_id, (_, ts) in self.pending_callbacks.items()
            if now - ts > timeout_sec
        ]
        for req_id in stale_keys:
            del self.pending_callbacks[req_id]

    def _dispatch_response_on_main_thread(self, data: dict):
        self._prune_stale_callbacks()
        req_id = data.get("id")
        if req_id in self.pending_callbacks:
            cb, _ = self.pending_callbacks.pop(req_id)
            try:
                cb(data)
            except Exception as e:
                print(f"[ScidClient] Error in callback for req {req_id}: {e}")

    def cancel_callback(self, req_id: Optional[int]):
        """Cancel a pending callback by request ID."""
        if req_id is not None:
            self.pending_callbacks.pop(req_id, None)

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self, db_path: Optional[str] = None, threads: Optional[int] = None) -> bool:
        if self.is_running():
            self.stop()

        exe_path = find_scid_mgr_executable()
        if not exe_path:
            self.process_error.emit(
                "scid-mgr executable not found. Please build it with:\n"
                "cd scid-mgr && cargo build --release"
            )
            return False

        cmd = [exe_path, "--interactive"]
        if threads and threads > 0:
            cmd.extend(["--threads", str(threads)])
        if db_path and os.path.exists(db_path):
            cmd.append(db_path)

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except Exception as e:
            self.process_error.emit(f"Failed to spawn scid-mgr backend: {e}")
            return False

        self.running = True
        self.write_queue = queue.Queue()

        self.reader_thread = threading.Thread(target=self._read_stdout_loop, daemon=True)
        self.reader_thread.start()

        self.writer_thread = threading.Thread(target=self._write_stdin_loop, daemon=True)
        self.writer_thread.start()

        threading.Thread(target=self._read_stderr_loop, daemon=True).start()
        return True

    def _read_stdout_loop(self):
        while self.running and self.process and self.process.stdout:
            line = self.process.stdout.readline()
            if not line:
                break
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                event_name = data.get("event")
                if event_name == "search_progress":
                    self.search_progress.emit(data.get("data", {}))
                elif event_name == "import_progress":
                    self.import_progress.emit(data.get("data", {}))
                elif event_name == "export_progress":
                    self.export_progress.emit(data.get("data", {}))
                elif event_name == "build_pos_index_progress":
                    self.pos_index_progress.emit(data.get("data", {}))
                elif event_name == "build_tree_progress":
                    self.tree_index_progress.emit(data.get("data", {}))
                elif event_name == "build_continuations_progress":
                    self.continuations_progress.emit(data.get("data", {}))
                elif event_name == "build_endgames_progress":
                    self.endgame_index_progress.emit(data.get("data", {}))
                else:
                    self.response_received.emit(data)
            except json.JSONDecodeError as e:
                self.process_error.emit(f"Invalid JSON from scid-mgr: {line_str} ({e})")

        self.running = False
        self.process_stopped.emit()

    def _write_stdin_loop(self):
        while self.running:
            try:
                msg = self.write_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if msg is None:
                break

            if self.process and self.process.stdin:
                try:
                    self.process.stdin.write(msg)
                    self.process.stdin.flush()
                except Exception as e:
                    self.process_error.emit(f"Error writing to scid-mgr stdin: {e}")
                    break

    def _read_stderr_loop(self):
        while self.running and self.process and self.process.stderr:
            line = self.process.stderr.readline()
            if not line:
                break
            err_str = line.strip()
            if err_str:
                self.process_error.emit(f"[stderr] {err_str}")

    def send_request(self, command: str, params: Optional[dict] = None, callback: Optional[Callable[[dict], None]] = None) -> int:
        if not self.is_running():
            raise RuntimeError("scid-mgr backend is not running.")

        self.request_id += 1
        req_id = self.request_id
        req_payload = {"id": req_id, "command": command}
        if params:
            req_payload.update(params)

        if callback:
            self.pending_callbacks[req_id] = (callback, time.time())

        msg = json.dumps(req_payload) + "\n"
        self.write_queue.put(msg)
        return req_id

    def open(self, db_path: str, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("open", {"path": db_path}, callback)

    def open_db(self, db_path: str, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.open(db_path, callback)

    def open_database(self, db_path: str, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.open(db_path, callback)

    def query_games(
        self,
        page: int = 0,
        page_size: int = 100,
        filter_dict: Optional[dict] = None,
        sort_by: Optional[str] = None,
        sort_direction: Optional[str] = None,
        sort_asc: Optional[bool] = None,
        search_id: Optional[str] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if search_id:
            params["search_id"] = search_id
        if filter_dict:
            params.update(filter_dict)
            params["filter"] = filter_dict
        if sort_by:
            params["sort_by"] = sort_by
        if sort_asc is not None:
            params["sort_asc"] = sort_asc
            params["sort_direction"] = "ASC" if sort_asc else "DESC"
        elif sort_direction:
            params["sort_direction"] = sort_direction
            params["sort_asc"] = (sort_direction.upper() == "ASC")

        return self.send_request("query_games", params, callback)

    def get_pgn(self, game_id: int, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("get_pgn", {"index": game_id}, callback)

    def get_game(self, game_id: int, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.get_pgn(game_id, callback)

    def create_database(self, db_path: str, format: str = "si5", callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("create", {"path": db_path, "format": format}, callback)

    def import_pgn(self, pgn_path: str, scid_exe: Optional[str] = None, callback: Optional[Callable[[dict], None]] = None) -> int:
        params = {"pgn_path": pgn_path}
        if scid_exe:
            params["scid_exe"] = scid_exe
        return self.send_request("import_pgn", params, callback)

    def export_pgn(self, output_path: str, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("export_pgn", {"output_path": output_path}, callback)

    def add_game(self, pgn_text: str, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("add_game", {"pgn": pgn_text}, callback)

    def update_game(self, game_id: int, pgn_text: str, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("update_game", {"index": game_id, "pgn": pgn_text}, callback)

    def delete_game(self, game_id: int, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("delete_game", {"index": game_id}, callback)

    def undelete_game(self, game_id: int, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("undelete_game", {"index": game_id}, callback)

    def save_database(self, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("save", {}, callback)

    def compact_database(self, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("compact", {}, callback)

    def build_pos_index(
        self,
        max_ply: int = 24,
        min_games: int = 1,
        threads: Optional[int] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {"max_ply": max_ply, "min_games": min_games}
        if threads and threads > 0:
            params["threads"] = threads
        return self.send_request("build_pos_index", params, callback)

    def build_tree(
        self,
        max_ply: int = 24,
        min_games: int = 1,
        threads: Optional[int] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {"max_ply": max_ply, "min_games": min_games}
        if threads and threads > 0:
            params["threads"] = threads
        return self.send_request("build_tree", params, callback)

    def pos_index_status(self, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("pos_index_status", {}, callback)

    def tree_index_status(self, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("tree_index_status", {}, callback)

    def set_threads(self, threads: int, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("set_threads", {"threads": threads}, callback)

    def benchmark(self, heavy: bool = False, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("benchmark", {"heavy": heavy}, callback)

    def search_position(
        self,
        fen: str,
        turn: Optional[str] = None,
        match_mode: Optional[str] = None,
        max_ply: Optional[int] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {"fen": fen}
        if turn:
            params["turn"] = turn
        if match_mode:
            params["match_mode"] = match_mode
        if max_ply is not None:
            params["max_ply"] = max_ply
        return self.send_request("search_position", params, callback)

    def search_material(
        self,
        filter_dict: dict,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        return self.send_request("search_material", filter_dict, callback)

    def opening_tree(
        self,
        fen: Optional[str] = None,
        filters: Optional[dict] = None,
        max_sample_games: Optional[int] = None,
        include_sample_games: bool = True,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {
            "include_sample_games": include_sample_games,
        }
        if fen:
            params["fen"] = fen
        if filters:
            params["filter"] = filters
        if max_sample_games is not None:
            params["max_sample_games"] = max_sample_games
        return self.send_request("opening_tree", params, callback)

    def continuations(
        self,
        fen: Optional[str] = None,
        max_depth: int = 8,
        max_lines: int = 10,
        min_games: int = 1,
        min_percentage: float = 0.0,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {
            "max_depth": max_depth,
            "max_lines": max_lines,
            "min_games": min_games,
            "min_percentage": min_percentage,
        }
        if fen:
            params["fen"] = fen
        return self.send_request("continuations", params, callback)

    def build_continuations(
        self,
        max_ply: int = 16,
        min_games: int = 1,
        threads: Optional[int] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {"max_ply": max_ply, "min_games": min_games}
        if threads and threads > 0:
            params["threads"] = threads
        return self.send_request("build_continuations", params, callback)

    def endgames(
        self,
        fen: Optional[str] = None,
        category: Optional[str] = None,
        feature_id: Optional[str] = None,
        max_samples: int = 20,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {
            "max_samples": max_samples,
        }
        if fen:
            params["fen"] = fen
        if category:
            params["category"] = category
        if feature_id:
            params["feature_id"] = feature_id
        return self.send_request("endgames", params, callback)

    def build_endgames(
        self,
        output_path: Optional[str] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {}
        if output_path:
            params["output_path"] = output_path
        return self.send_request("build_endgames", params, callback)

    def validate_dsl(self, query: str, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("validate_dsl", {"query": query}, callback)

    def explain_dsl(self, query: str, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("explain_dsl", {"query": query}, callback)

    def search(
        self,
        filter_dict: dict,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        """Unified multi-criteria search (combines headers, FEN, material, CQL)."""
        return self.send_request("search", filter_dict, callback)

    def search_query(
        self,
        query: str,
        pgn_path: Optional[str] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {"query": query}
        if pgn_path:
            params["pgn_path"] = pgn_path
        return self.send_request("search", params, callback)

    def search_cql(
        self,
        query: str,
        pgn_path: Optional[str] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        return self.search_query(query, pgn_path=pgn_path, callback=callback)

    def stop(self):
        if not self.is_running():
            return

        try:
            self.send_request("shutdown")
        except Exception:
            pass

        self.running = False
        self.pending_callbacks.clear()
        self.write_queue.put(None)

        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
