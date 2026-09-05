import os
import sys
import json
import queue
import shutil
import subprocess
import threading
from typing import Optional, Dict, Any, Callable

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
        self.pending_callbacks: Dict[int, Callable[[dict], None]] = {}

        # Safely dispatch pending callbacks on the main GUI thread via Qt signal delivery
        self.response_received.connect(self._dispatch_response_on_main_thread)

    def _dispatch_response_on_main_thread(self, data: dict):
        req_id = data.get("id")
        if req_id in self.pending_callbacks:
            cb = self.pending_callbacks.pop(req_id)
            try:
                cb(data)
            except Exception as e:
                print(f"[ScidClient] Error in callback for req {req_id}: {e}")

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
            self.pending_callbacks[req_id] = callback

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
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if filter_dict:
            params.update(filter_dict)
            params["filter"] = filter_dict
        if sort_by:
            params["sort_by"] = sort_by
        if sort_direction:
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
        threads: Optional[int] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {"max_ply": max_ply}
        if threads and threads > 0:
            params["threads"] = threads
        return self.send_request("build_pos_index", params, callback)

    def pos_index_status(self, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("pos_index_status", {}, callback)

    def set_threads(self, threads: int, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("set_threads", {"threads": threads}, callback)

    def benchmark(self, heavy: bool = False, callback: Optional[Callable[[dict], None]] = None) -> int:
        return self.send_request("benchmark", {"heavy": heavy}, callback)

    def search_position(
        self,
        fen: str,
        max_ply: Optional[int] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {"fen": fen}
        if max_ply is not None:
            params["max_ply"] = max_ply
        return self.send_request("search_position", params, callback)

    def opening_tree(
        self,
        fen: Optional[str] = None,
        callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        params: Dict[str, Any] = {}
        if fen:
            params["fen"] = fen
        return self.send_request("opening_tree", params, callback)

    def stop(self):
        if not self.is_running():
            return

        try:
            self.send_request("shutdown")
        except Exception:
            pass

        self.running = False
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
